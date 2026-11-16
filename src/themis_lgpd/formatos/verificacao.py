"""Verificação independente do arquivo gerado.

Depois de produzir o arquivo anonimizado, cada formato extrai **todo** o conteúdo textual do
resultado — por um caminho diferente do usado na anonimização — e confirma que nenhum valor
tarjado continua legível. Se algum continuar, a operação falha com
:class:`~themis_lgpd.formatos.VazamentoDetectado` e nenhum arquivo é entregue.

Regras de comparação:

* caixa e acentos são ignorados;
* entre dois caracteres do valor são tolerados até três caracteres não alfanuméricos, o que cobre
  quebras de linha, hifenização, espaçamento entre letras e texto dividido entre elementos XML;
* o valor precisa começar e terminar em limite de palavra, para que "Costa" tarjado não seja
  confundido com "acostamento";
* números com oito dígitos ou mais também são procurados apenas pelos dígitos, para detectar o
  mesmo CPF ou telefone escrito com outra pontuação;
* trechos mantidos intencionalmente (lista de permissão, entidades com regra ``manter`` e nomes de
  lugares e organizações não tarjados) são desconsiderados, para que "Paulo" tarjado não seja
  acusado dentro de "São Paulo". São os mesmos trechos que a propagação preserva
  (ver :meth:`themis_lgpd.motor.Anonimizador._propagar`);
* valores de categorias que não se propagam (saúde, dados sensíveis, valores de pessoa natural,
  quase-identificadores) podem continuar legíveis em outro trecho do documento, onde não se referem
  à pessoa ("diabetes" tarjado no pedido do requerente e legível na nota técnica sobre o programa).
  Cada ocorrência deixada visível pela análise (ver :func:`texto_visivel`) é reconhecida pelo
  contexto — até duas palavras de cada lado, na mesma linha — e desconsiderada; uma ocorrência em
  outro contexto, como a de uma tarja que não chegou ao arquivo, continua sendo acusada.
"""

from __future__ import annotations

import html
import io
import re
import zipfile
from collections.abc import Iterable, Mapping

from ..catalogo import tipo as info_tipo
from ..motor import Resultado
from ..perfis import ALERTAR, MANTER, NOMES_NAO_PESSOAIS, TARJAR
from ..propagacao import CATEGORIAS_PROPAGAVEIS
from ..reconhecedores.nomes import contexto_nao_pessoal
from ..texto import dobrar

#: Valores com menos letras e dígitos que isto não são verificados: coincidências com palavras
#: comuns tornariam a verificação inútil. Eles continuam tarjados normalmente.
MINIMO_VERIFICAVEL = 5

#: Valores numéricos com pelo menos esta quantidade de dígitos são procurados também sem pontuação.
MINIMO_DIGITOS = 8

_ESPACOS = re.compile(r"\s+")
_NAO_ALNUM = re.compile(r"[^0-9a-z]")
_TAG_XML = re.compile(r"<[^>]+>")
_ATRIBUTO_XML = re.compile(r'="([^"]*)"')
_SEPARADOR = r"[^0-9a-z]{0,3}"


def _padrao(valor: str) -> re.Pattern[str] | None:
    """Expressão que localiza ``valor`` com a tolerância descrita no módulo."""
    caracteres = [c for c in dobrar(valor) if c.isascii() and c.isalnum()]
    if not caracteres:
        return None
    corpo = _SEPARADOR.join(re.escape(c) for c in caracteres)
    return re.compile(rf"(?<![0-9a-z]){corpo}(?![0-9a-z])")


def valores_tarjados(resultados: Iterable[Resultado]) -> dict[str, str]:
    """Valores tarjados que devem estar ausentes do arquivo final.

    Returns:
        Tipo de dado de cada valor, pelo valor.
    """
    valores: dict[str, str] = {}
    for r in resultados:
        for e in r.entidades:
            valor = " ".join(e.valor.split())
            if e.acao == TARJAR and sum(c.isalnum() for c in valor) >= MINIMO_VERIFICAVEL:
                valores.setdefault(valor, e.tipo)
    return valores


def valores_protegidos(resultados: Iterable[Resultado], permitir: Iterable[str] = ()) -> set[str]:
    """Trechos mantidos intencionalmente no arquivo final.

    São os termos da lista de permissão, as entidades com regra ``manter`` e os nomes de lugares e
    organizações não tarjados.
    """
    protegidos = {e.valor for r in resultados for e in r.entidades
                  if e.acao == MANTER or (e.acao == ALERTAR and e.categoria in NOMES_NAO_PESSOAIS)}
    protegidos.update(t for t in permitir if t and t.strip())
    return protegidos


def texto_visivel(resultados: Iterable[Resultado]) -> str:
    """Texto que a análise deixou visível de propósito: a saída em texto de cada parte do documento."""
    return "\n".join(r.texto for r in resultados)


def _propagavel(tipo: str) -> bool:
    """Indica se os valores do tipo são tarjados em todas as ocorrências do documento."""
    try:
        return info_tipo(tipo).categoria in CATEGORIAS_PROPAGAVEIS
    except KeyError:
        return True


def verificar_ausencia(texto_saida: str, valores: Mapping[str, str] | Iterable[str],
                       protegidos: Iterable[str] = (), visivel: str | None = None) -> list[str]:
    """Devolve os valores que ainda aparecem em ``texto_saida``.

    Args:
        texto_saida: Todo o conteúdo textual extraído do arquivo gerado.
        valores: Valores tarjados, com o tipo de cada um (ver :func:`valores_tarjados`) ou sem ele.
            Ocorrências de valores do tipo ``NOME`` dentro de nomes de lugares e instituições
            ("Paulo" em "São Paulo") são desconsideradas, como na propagação. Também como na
            propagação, um nome de uma só palavra escrito com inicial maiúscula ("Rocha") só é
            procurado com inicial maiúscula: a palavra comum "rocha" não é o sobrenome.
        protegidos: Trechos mantidos intencionalmente (ver :func:`valores_protegidos`). Uma ocorrência
            só é desconsiderada quando está inteiramente contida em um deles; permitir "Maria" não
            esconde "Maria Souza".
        visivel: Texto deixado visível pela análise (ver :func:`texto_visivel`). Quando informado, as
            ocorrências de valores de categorias que não se propagam que aparecem nele são
            desconsideradas pelo contexto (ver as regras do módulo).

    Returns:
        Lista vazia quando nada vazou.
    """
    tipos = dict(valores) if isinstance(valores, Mapping) else dict.fromkeys(valores, "")
    if not tipos:
        return []
    protegidos = list(protegidos)
    if visivel is not None:
        protegidos += _contextos_visiveis(visivel, [v for v, t in tipos.items() if t and not _propagavel(t)])
    # ``dobrar`` preserva o comprimento: as posições em ``texto`` valem em ``colapsado``, que mantém
    # as maiúsculas usadas pela regra de nomes de lugares ("São" × "são").
    colapsado = _ESPACOS.sub(" ", texto_saida)
    texto = dobrar(colapsado)
    faixas: list[tuple[int, int]] = []
    for protegido in protegidos:
        padrao = _padrao(protegido)
        if padrao is not None:
            faixas.extend(m.span() for m in padrao.finditer(texto))
    sem_protegidos = list(texto)
    for a, b in faixas:
        sem_protegidos[a:b] = " " * (b - a)
    so_alnum = _NAO_ALNUM.sub("", "".join(sem_protegidos))

    def desconsiderada(inicio: int, fim: int, tipo: str, so_maiuscula: bool) -> bool:
        return (any(a <= inicio and fim <= b for a, b in faixas)
                or (tipo == "NOME" and contexto_nao_pessoal(colapsado, inicio))
                or (so_maiuscula and not colapsado[inicio].isupper()))

    achados = []
    for valor, tipo in tipos.items():
        padrao = _padrao(valor)
        digitos = _NAO_ALNUM.sub("", dobrar(valor))
        so_maiuscula = tipo == "NOME" and " " not in valor and valor[:1].isupper()
        legivel = padrao is not None and any(not desconsiderada(*m.span(), tipo, so_maiuscula)
                                             for m in padrao.finditer(texto))
        if legivel or (len(digitos) >= MINIMO_DIGITOS and digitos.isdigit() and digitos in so_alnum):
            achados.append(valor)
    return achados


def sem_ocorrencia_visivel(valores: Mapping[str, str], visivel: str) -> dict[str, str]:
    """Valores tarjados, exceto os de categorias que não se propagam que aparecem em ``visivel``.

    Serve aos conteúdos em que o contexto de uma ocorrência não pode ser reconhecido, como o fluxo
    bruto de uma página de PDF, em que cada palavra é um operador à parte.
    """
    texto = dobrar(_ESPACOS.sub(" ", visivel))
    saida = {}
    for valor, tipo in valores.items():
        padrao = _padrao(valor)
        if not tipo or _propagavel(tipo) or padrao is None or not padrao.search(texto):
            saida[valor] = tipo
    return saida


def _contextos_visiveis(visivel: str, valores: Iterable[str]) -> list[str]:
    """Ocorrências dos valores em ``visivel``, cada uma com até duas palavras de cada lado na mesma linha.

    As palavras de um rótulo de tarja ("[DADO DE SAÚDE]") não entram no contexto.
    """
    padroes = [p for p in map(_padrao, valores) if p is not None]
    contextos = []
    for linha in visivel.splitlines():
        dobrada = dobrar(linha)
        for padrao in padroes:
            for m in padrao.finditer(dobrada):
                antes = _vizinhas(reversed(linha[:m.start()].split()))[::-1]
                depois = _vizinhas(linha[m.end():].split())
                contextos.append(" ".join([*antes, linha[m.start():m.end()], *depois]))
    return contextos


def _vizinhas(palavras: Iterable[str], limite: int = 2) -> list[str]:
    """Até ``limite`` palavras, parando no primeiro rótulo de tarja."""
    saida = []
    for palavra in palavras:
        if len(saida) == limite or "[" in palavra or "]" in palavra:
            break
        saida.append(palavra)
    return saida


def imagens_com_metadados(dados: bytes) -> list[str]:
    """Partes de um pacote Office (DOCX/XLSX) cujas imagens ainda têm metadados (EXIF, GPS, XMP…)."""
    from .midia import formato_imagem, metadados_restantes

    achados = []
    with zipfile.ZipFile(io.BytesIO(dados)) as pacote:
        for nome in pacote.namelist():
            conteudo = pacote.read(nome)
            if formato_imagem(conteudo) and metadados_restantes(conteudo):
                achados.append(nome)
    return achados


def texto_de_pacote(dados: bytes) -> str:
    """Todo o texto de um pacote Office (DOCX/XLSX).

    Inclui o conteúdo dos elementos e os valores de atributos de todas as partes XML, VML e de
    relacionamento — onde ficam, por exemplo, destinos de hiperlinks, textos alternativos de
    imagens e nomes de autores.
    """
    from . import metarquivo

    partes = []
    with zipfile.ZipFile(io.BytesIO(dados)) as pacote:
        for nome in pacote.namelist():
            conteudo = pacote.read(nome)
            if nome.endswith((".xml", ".rels", ".vml", ".svg")):
                xml = conteudo.decode("utf-8", errors="ignore")
                partes.append(html.unescape(_TAG_XML.sub(" ", xml)))
                partes.extend(html.unescape(v) for v in _ATRIBUTO_XML.findall(xml))
            elif metarquivo.tipo_metarquivo(conteudo):
                # O texto das imagens vetoriais (EMF/WMF) é legível por qualquer visualizador.
                partes.append(metarquivo.ler(conteudo).texto)
    return "\n".join(partes)
