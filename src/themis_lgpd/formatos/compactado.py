"""Anonimização de arquivos ZIP, como a exportação de um processo do SEI.

Cada arquivo do ZIP é anonimizado pelo próprio formato (PDF, DOCX, planilha, imagem, mensagem,
outro ZIP…) e gravado num ZIP novo, com a mesma estrutura de pastas:

* **nomes de pastas e arquivos** são analisados — com os valores tarjados nos documentos propagados
  para eles — e tarjados como o texto (``Requerimento de [NOME].pdf``). A codificação dos nomes
  gravados por programas antigos do Windows (página de código 850) é identificada antes da análise;
* **arquivos que não podem ser anonimizados** (formato não suportado, protegidos por senha,
  criptografados, ilegíveis) são removidos, assim como arquivos de sistema (``__MACOSX``,
  ``Thumbs.db``, ``.DS_Store``, ``desktop.ini``) e ligações simbólicas;
* **manifesto** (``manifesto_anonimizacao.json``, na raiz): para cada arquivo, o nome de saída, o
  formato, a situação, o motivo de remoção, os SHA-256 de entrada e de saída, a contagem de dados
  tarjados por tipo e os avisos. O manifesto não contém nomes originais nem conteúdo;
* comentários do ZIP, datas, atributos e campos extras das entradas não são copiados.

Mensagens anexadas e ZIPs dentro de ZIPs são processados até :data:`PROFUNDIDADE_MAXIMA` níveis.
Os nomes gravados e o manifesto passam pela verificação final; cada arquivo, pela verificação do
seu formato.
"""

from __future__ import annotations

import hashlib
import io
import json
import posixpath
import zipfile
from collections import Counter

from .. import __version__
from ..motor import Anonimizador, Resultado
from . import ArquivoInvalido, FalhaOCR, ResultadoArquivo, VazamentoDetectado, detectar_formato, verificar_zip
from .verificacao import texto_visivel, valores_protegidos, valores_tarjados, verificar_ausencia

#: Profundidade máxima de ZIPs dentro de ZIPs.
PROFUNDIDADE_MAXIMA = 3
#: Nome do manifesto gravado na raiz do ZIP gerado.
MANIFESTO = "manifesto_anonimizacao.json"
#: Arquivos e pastas criados pelo sistema operacional, sem conteúdo do processo; registram nomes de
#: arquivos, miniaturas de imagens e preferências do usuário.
_ARQUIVOS_DE_SISTEMA = frozenset({".ds_store", "thumbs.db", "desktop.ini", "ehthumbs.db"})
_PASTAS_DE_SISTEMA = frozenset({"__macosx", ".spotlight-v100", ".trashes", ".fseventsd"})
#: Caracteres que não podem compor nomes de arquivo no Windows.
_PROIBIDOS_NO_NOME = frozenset('<>:"/\\|?*')
_TAMANHO_MAXIMO_NOME = 120
_DATA_FIXA = (1980, 1, 1, 0, 0, 0)


def _nome_decodificado(info: zipfile.ZipInfo) -> str:
    """Nome da entrada com a codificação correta.

    Sem a marca de UTF-8 (bit 11), o módulo ``zipfile`` decodifica o nome como CP437; o Windows em
    português grava na página de código 850, e outros programas gravam UTF-8 sem a marca.
    """
    if info.flag_bits & 0x800:
        return info.filename
    bruto = info.filename.encode("cp437")
    try:
        return bruto.decode("utf-8")
    except UnicodeDecodeError:
        return bruto.decode("cp850")


def _componentes(nome: str) -> list[str]:
    """Pastas e arquivo do caminho, sem raiz, unidade, ``.`` ou ``..`` (proteção contra *zip slip*)."""
    partes = [p.strip() for p in nome.replace("\\", "/").split("/")]
    partes = [p for p in partes if p and p not in (".", "..")]
    if partes and len(partes[0]) == 2 and partes[0][1] == ":":
        partes = partes[1:]
    return partes


def _de_sistema(componentes: list[str]) -> bool:
    return any(c.lower() in _PASTAS_DE_SISTEMA for c in componentes[:-1]) or \
        componentes[-1].lower() in _ARQUIVOS_DE_SISTEMA or componentes[-1].startswith("._")


def _ligacao_simbolica(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def _limpar_nome(texto: str, padrao: str) -> str:
    texto = "".join("_" if c in _PROIBIDOS_NO_NOME or ord(c) < 32 else c for c in texto)
    texto = " ".join(texto.split()).strip(" .")[:_TAMANHO_MAXIMO_NOME].strip(" .")
    return texto or padrao


def _sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


class _Entrada:
    """Arquivo do ZIP: caminho de origem, conteúdo e o que se apurou ao processá-lo."""

    def __init__(self, componentes: list[str], conteudo: bytes):
        self.componentes = componentes
        self.conteudo = conteudo
        self.resultado: ResultadoArquivo | None = None
        self.motivo = ""

    @property
    def extensao_original(self) -> str:
        arquivo = self.componentes[-1]
        return arquivo.rsplit(".", 1)[-1].lower() if "." in arquivo.strip(".") else ""


def anonimizar_zip(dados: bytes, anon: Anonimizador, nome: str, *, ocr: bool = True, verificar: bool = True,
                   limite_paginas: int = 500, limite_bytes: int | None = None, colunas_integrais=None,
                   pdfa: bool = False, profundidade: int = 0) -> ResultadoArquivo:
    """Anonimiza os arquivos de um ZIP (ver a descrição do módulo).

    Raises:
        ArquivoInvalido: ZIP corrompido, acima dos limites, aninhado além do limite ou sem nenhum arquivo.
        VazamentoDetectado: A verificação encontrou valor tarjado num arquivo, num nome ou no manifesto.
    """
    from . import LIMITE_BYTES_PADRAO, anonimizar_arquivo

    if profundidade > PROFUNDIDADE_MAXIMA:
        raise ArquivoInvalido("Arquivos ZIP dentro de outros além do limite de profundidade.")
    limite_bytes = limite_bytes or LIMITE_BYTES_PADRAO
    try:
        verificar_zip(dados)
        arquivo_zip = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile as erro:
        raise ArquivoInvalido("Arquivo compactado corrompido.") from erro

    entradas: list[_Entrada] = []
    sistema = criptografados = ligacoes = 0
    with arquivo_zip:
        for info in arquivo_zip.infolist():
            if info.is_dir():
                continue
            componentes = _componentes(_nome_decodificado(info))
            if not componentes:
                continue
            if _de_sistema(componentes):
                sistema += 1
                continue
            if _ligacao_simbolica(info):
                ligacoes += 1
                continue
            if info.flag_bits & 0x1:
                criptografados += 1
                entradas.append(_Entrada(componentes, b""))
                entradas[-1].motivo = "protegido por senha"
                continue
            try:
                conteudo = arquivo_zip.read(info)
            except (zipfile.BadZipFile, NotImplementedError, OSError) as erro:
                raise ArquivoInvalido("Arquivo compactado corrompido ou com compressão não suportada.") from erro
            entradas.append(_Entrada(componentes, conteudo))
    if not entradas:
        raise ArquivoInvalido("O arquivo compactado não contém documentos.")

    resultados: list[Resultado] = []
    for entrada in entradas:
        if entrada.motivo:
            continue
        arquivo = entrada.componentes[-1]
        try:
            if not entrada.conteudo:
                raise ArquivoInvalido("Arquivo vazio.")
            if detectar_formato(entrada.conteudo, arquivo) == "zip":
                res = anonimizar_zip(entrada.conteudo, anon, arquivo, ocr=ocr, verificar=verificar,
                                     limite_paginas=limite_paginas, limite_bytes=limite_bytes,
                                     colunas_integrais=colunas_integrais, pdfa=pdfa, profundidade=profundidade + 1)
            else:
                res = anonimizar_arquivo(entrada.conteudo, arquivo, anon, ocr=ocr, limite_bytes=limite_bytes,
                                         limite_paginas=limite_paginas, colunas_integrais=colunas_integrais,
                                         verificar=verificar, pdfa=pdfa)
        except (ArquivoInvalido, FalhaOCR) as erro:
            entrada.motivo = str(erro)
            continue
        entrada.resultado = res
        resultados += res.resultados

    caminhos = _nomes_de_saida(entradas, anon, resultados)
    resultados += caminhos.resultados

    saida_zip = io.BytesIO()
    linhas = []
    with zipfile.ZipFile(saida_zip, "w", zipfile.ZIP_DEFLATED) as novo:
        for entrada, caminho in zip(entradas, caminhos.nomes):
            res = entrada.resultado
            linha = {"arquivo": caminho, "sha256_entrada": _sha256(entrada.conteudo) if entrada.conteudo else None}
            if res is None:
                linha.update(situacao="removido", motivo=entrada.motivo)
            else:
                tarjadas = [e for r in res.resultados for e in r.tarjadas]
                linha.update(situacao="anonimizado", formato=res.formato, sha256_saida=_sha256(res.dados),
                             tarjados=len(tarjadas), por_tipo=dict(Counter(e.tipo for e in tarjadas).most_common()),
                             avisos=res.avisos)
                info = zipfile.ZipInfo(caminho, date_time=_DATA_FIXA)
                info.compress_type = zipfile.ZIP_DEFLATED
                novo.writestr(info, res.dados)
            linhas.append(linha)
        manifesto = json.dumps({"ferramenta": "Themis LGPD", "versao": __version__, "perfil": anon.perfil.nome,
                                "modo": anon.modo, "arquivos": linhas}, ensure_ascii=False, indent=2)
        info = zipfile.ZipInfo(MANIFESTO, date_time=_DATA_FIXA)
        info.compress_type = zipfile.ZIP_DEFLATED
        novo.writestr(info, manifesto.encode("utf-8"))
    saida = saida_zip.getvalue()

    anonimizados = sum(1 for e in entradas if e.resultado is not None)
    removidos = len(entradas) - anonimizados
    avisos = [f"{anonimizados} arquivo(s) anonimizado(s); o manifesto {MANIFESTO} registra a situação de cada um."]
    if caminhos.tarjados:
        avisos.append(f"{caminhos.tarjados} nome(s) de arquivo ou pasta com dados tarjados.")
    if removidos:
        avisos.append(f"{removidos} arquivo(s) removido(s) por não poderem ser anonimizados (formato não suportado, "
                      "protegidos por senha, ilegíveis ou sem OCR disponível): veja os motivos no manifesto.")
    if sistema:
        avisos.append(f"{sistema} arquivo(s) de sistema (miniaturas, preferências de pasta) removido(s).")
    if ligacoes:
        avisos.append(f"{ligacoes} ligação(ões) simbólica(s) removida(s).")
    if criptografados:
        avisos.append(f"{criptografados} arquivo(s) criptografado(s) dentro do ZIP não pode(m) ser analisado(s).")

    if verificar:
        sobras = verificar_ausencia("\n".join(caminhos.nomes) + "\n" + manifesto, valores_tarjados(resultados),
                                    valores_protegidos(resultados, anon.permitir), texto_visivel(resultados))
        if sobras:
            raise VazamentoDetectado(f"{len(sobras)} trecho(s) tarjado(s) ainda legível(is) em nomes de arquivo "
                                     "ou no manifesto do ZIP gerado.")
    return ResultadoArquivo(saida, "zip", nome, resultados, avisos)


class _Nomes:
    def __init__(self, nomes: list[str], resultados: list[Resultado], tarjados: int):
        self.nomes = nomes
        self.resultados = resultados
        self.tarjados = tarjados


def _nomes_de_saida(entradas: list[_Entrada], anon: Anonimizador, resultados: list[Resultado]) -> _Nomes:
    """Caminhos do ZIP gerado: pastas e nomes analisados, extensão do arquivo gerado, sem colisões.

    Sublinhados e pontos separam palavras em nomes de arquivo (``requerimento_maria_souza``) e são
    trocados por espaços na análise. Os valores tarjados nos documentos são propagados para os nomes.
    """
    textos: list[str] = []
    for entrada in entradas:
        for i, componente in enumerate(entrada.componentes):
            base = componente
            if i == len(entrada.componentes) - 1 and "." in componente.strip("."):
                base = componente.rsplit(".", 1)[0]
            texto = base.replace("_", " ").replace(".", " ")
            if texto not in textos:
                textos.append(texto)
    externos = [(tipo, valor) for valor, tipo in valores_tarjados(resultados).items()]
    analisados = anon.anonimizar_lote(textos, mesmo_documento=True, externos=externos)
    por_texto = dict(zip(textos, analisados))

    nomes, ocupados = [], {MANIFESTO.lower()}
    for entrada in entradas:
        pastas = []
        for i, componente in enumerate(entrada.componentes):
            ultimo = i == len(entrada.componentes) - 1
            base = componente.rsplit(".", 1)[0] if ultimo and "." in componente.strip(".") else componente
            r = por_texto[base.replace("_", " ").replace(".", " ")]
            texto = r.texto if r.tarjadas else base
            pastas.append(_limpar_nome(texto, "documento" if ultimo else "pasta"))
        extensao = entrada.resultado.nome.rsplit(".", 1)[-1] if entrada.resultado else entrada.extensao_original
        caminho = posixpath.join(*pastas) + (f".{extensao}" if extensao else "")
        candidato, n = caminho, 2
        while candidato.lower() in ocupados:
            raiz, ext = posixpath.splitext(caminho)
            candidato, n = f"{raiz} ({n}){ext}", n + 1
        ocupados.add(candidato.lower())
        nomes.append(candidato)
    tarjados = sum(1 for r in analisados if r.tarjadas)
    return _Nomes(nomes, analisados, tarjados)
