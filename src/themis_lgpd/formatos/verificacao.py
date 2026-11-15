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
  (ver :meth:`themis_lgpd.motor.Anonimizador._propagar`).
"""

from __future__ import annotations

import html
import io
import re
import zipfile
from collections.abc import Iterable, Mapping

from ..motor import Resultado
from ..perfis import ALERTAR, MANTER, NOMES_NAO_PESSOAIS, TARJAR
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


def verificar_ausencia(texto_saida: str, valores: Mapping[str, str] | Iterable[str],
                       protegidos: Iterable[str] = ()) -> list[str]:
    """Devolve os valores que ainda aparecem em ``texto_saida``.

    Args:
        texto_saida: Todo o conteúdo textual extraído do arquivo gerado.
        valores: Valores tarjados, com o tipo de cada um (ver :func:`valores_tarjados`) ou sem ele.
            Ocorrências de valores do tipo ``NOME`` dentro de nomes de lugares e instituições
            ("Paulo" em "São Paulo") são desconsideradas, como na propagação.
        protegidos: Trechos mantidos intencionalmente (ver :func:`valores_protegidos`). Uma ocorrência
            só é desconsiderada quando está inteiramente contida em um deles; permitir "Maria" não
            esconde "Maria Souza".

    Returns:
        Lista vazia quando nada vazou.
    """
    tipos = dict(valores) if isinstance(valores, Mapping) else dict.fromkeys(valores, "")
    if not tipos:
        return []
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

    def desconsiderada(inicio: int, fim: int, tipo: str) -> bool:
        return (any(a <= inicio and fim <= b for a, b in faixas)
                or (tipo == "NOME" and contexto_nao_pessoal(colapsado, inicio)))

    achados = []
    for valor, tipo in tipos.items():
        padrao = _padrao(valor)
        digitos = _NAO_ALNUM.sub("", dobrar(valor))
        legivel = padrao is not None and any(not desconsiderada(*m.span(), tipo) for m in padrao.finditer(texto))
        if legivel or (len(digitos) >= MINIMO_DIGITOS and digitos.isdigit() and digitos in so_alnum):
            achados.append(valor)
    return achados


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
