"""Extração e regravação do texto de partes XML do Office (WordprocessingML, DrawingML, gráficos, VML).

Cada parte é convertida em *unidades de análise*: um texto submetido ao motor e a função que grava
o resultado de volta no XML. Há quatro tipos de unidade:

* **Fluxo de texto**: o texto de todos os parágrafos da parte, em ordem de documento, com
  parágrafos, tabulações e quebras de linha convertidos em separadores. O texto de um parágrafo
  costuma estar dividido em vários trechos de formatação ("Mar" em negrito, "ia" sem negrito); a
  análise do fluxo enxerga a palavra inteira e o contexto entre parágrafos e células.
* **Instruções de campo** (ex.: ``HYPERLINK "mailto:..."``), agrupadas por parágrafo.
* **Valores e atributos isolados**: valores em cache de gráficos e atributos de texto livre (texto
  alternativo de imagens, dicas de hiperlinks, rótulos de controles e de campos de formulário).
* **Texto residual**: qualquer outro texto presente na parte. Garante que nenhum texto deixe de ser
  analisado por estar em um elemento não previsto (ex.: gráficos do Office 2016, extensões).
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from ..motor import Anonimizador, Entidade, Resultado

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
}


def q(prefixo: str, nome: str) -> str:
    """Nome qualificado no formato do lxml (``{namespace}nome``)."""
    return f"{{{NS[prefixo]}}}{nome}"


_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

#: Elementos cujo texto é conteúdo do documento.
_TAGS_TEXTO = frozenset({q("w", "t"), q("w", "delText"), q("a", "t"), q("m", "t")})
#: Elementos sem texto que separam palavras, e o separador usado no fluxo de análise.
_SEPARADORES = {q("w", "tab"): "\t", q("w", "ptab"): "\t", q("w", "br"): "\n", q("w", "cr"): "\n",
                q("w", "noBreakHyphen"): "-", q("a", "br"): "\n"}
_TAGS_PARAGRAFO = (q("w", "p"), q("a", "p"))
#: Elementos cujo texto é tratado por uma unidade específica (fluxo, campo ou valor de gráfico).
_TRATADOS = _TAGS_TEXTO | {q("w", "instrText"), q("c", "v")}
#: Elementos em que espaços nas bordas precisam ser preservados explicitamente.
_PRESERVAR_ESPACO = frozenset({q("w", "t"), q("w", "delText"), q("w", "instrText"), q("m", "t")})


@dataclass
class Unidade:
    """Texto submetido à análise e a função que grava o resultado de volta no documento.

    ``aplicar`` devolve resultados adicionais quando precisa reanalisar o texto em partes menores.
    ``entidades``, quando informadas, dispensam a análise do texto (ex.: célula de uma coluna de dado
    pessoal, tarjada por inteiro); a unidade continua participando da propagação.
    """

    texto: str
    aplicar: Callable[[Resultado], list[Resultado]]
    entidades: list[Entidade] | None = None


def tem_conteudo(texto: str | None) -> bool:
    """Indica se o texto pode conter dado pessoal: tem letras ou um número longo."""
    return bool(texto) and (any(c.isalpha() for c in texto) or sum(c.isdigit() for c in texto) >= 8)


def analisar(unidades: list[Unidade], anon: Anonimizador, *, continuar: bool = False) -> list[Resultado]:
    """Analisa as unidades como um único documento e grava os resultados.

    Args:
        unidades: Unidades de análise.
        anon: Anonimizador configurado.
        continuar: Mantém a numeração de pseudônimos de uma etapa anterior do mesmo arquivo.

    Returns:
        Um resultado por unidade, seguido dos resultados de eventuais reanálises.
    """
    definidas = [u.entidades for u in unidades]
    resultados = anon.anonimizar_lote([u.texto for u in unidades],
                                      definidas if any(d is not None for d in definidas) else None,
                                      mesmo_documento=True, continuar=continuar)
    for unidade, r in zip(unidades, list(resultados)):
        resultados += unidade.aplicar(r)
    return resultados


# ---------------------------------------------------------------------------- coleta
def _paragrafo(el):
    return next(el.iterancestors(*_TAGS_PARAGRAFO), None)


def _fluxo(raiz) -> tuple[list, list[str]]:
    """Texto da parte em ordem de documento, com separadores entre parágrafos e palavras.

    Returns:
        ``(elementos, textos)``: para cada trecho, o elemento de origem (``None`` para separadores,
        que não existem no XML) e o texto.
    """
    elementos: list = []
    textos: list[str] = []
    dono_atual = None
    for el in raiz.iter(*_TAGS_TEXTO, *_SEPARADORES):
        if el.tag == q("w", "tab") and el.getparent().tag == q("w", "tabs"):
            continue  # definição de parada de tabulação, não uma tabulação no texto
        dono = _paragrafo(el)
        if textos and dono is not dono_atual:
            elementos.append(None)
            textos.append("\n")
        dono_atual = dono
        if el.tag in _TAGS_TEXTO:
            elementos.append(el)
            textos.append(el.text or "")
        else:
            elementos.append(None)
            textos.append(_SEPARADORES[el.tag])
    return elementos, textos


def _instrucoes(raiz) -> list[list]:
    """Nós de instrução de campo agrupados por parágrafo."""
    grupos: list[list] = []
    dono_atual = None
    for el in raiz.iter(q("w", "instrText")):
        dono = _paragrafo(el)
        if not grupos or dono is not dono_atual:
            grupos.append([])
        grupos[-1].append(el)
        dono_atual = dono
    return grupos


def _atributos_livres(raiz) -> Iterator[tuple[object, str]]:
    """Atributos que guardam texto escrito pelo autor do documento."""
    from lxml import etree

    w = NS["w"]
    for el in raiz.iter():
        if not isinstance(el.tag, str):
            continue
        nome = etree.QName(el)
        pai = el.getparent()
        pai_tag = pai.tag if pai is not None else None
        atributos: tuple[str, ...] = ()
        if nome.localname in ("docPr", "cNvPr"):
            atributos = ("descr", "title", "name")
        elif nome.namespace == NS["a"] and nome.localname in ("hlinkClick", "hlinkHover"):
            atributos = ("tooltip",)
        elif nome.namespace == w:
            if nome.localname == "hyperlink":
                atributos = (q("w", "tooltip"),)
            elif nome.localname == "fldSimple":
                atributos = (q("w", "instr"),)
            elif nome.localname in ("name", "helpText", "statusText") and pai_tag == q("w", "ffData") or (nome.localname == "default" and pai_tag == q("w", "textInput")) or nome.localname == "listEntry" or nome.localname in ("alias", "tag") and pai_tag == q("w", "sdtPr"):
                atributos = (q("w", "val"),)
            elif nome.localname == "listItem":
                atributos = (q("w", "displayText"), q("w", "value"))
        elif nome.namespace == NS["v"]:
            atributos = ("alt", "string", "href", q("o", "title"))
        for atributo in atributos:
            valor = el.get(atributo)
            if valor and valor.strip():
                yield el, atributo


# ---------------------------------------------------------------------------- regravação
def _gravar_texto(el, texto: str) -> None:
    el.text = texto
    if el.tag in _PRESERVAR_ESPACO:
        el.set(_XML_SPACE, "preserve")


def _distribuir(elementos: list, textos: list[str], substituicoes: list[dict]) -> None:
    """Aplica as substituições, feitas sobre o texto concatenado, aos elementos de origem.

    O substituto é gravado no primeiro elemento real alcançado pelo trecho; a parte do trecho que cai
    nos elementos seguintes é apagada. Separadores não existem no XML e são ignorados.
    """
    inicios: list[int] = []
    posicao = 0
    for t in textos:
        inicios.append(posicao)
        posicao += len(t)
    edicoes: dict[int, list[tuple[int, int, str]]] = {}
    for s in substituicoes:
        a, b = s["inicio"], s["fim"]
        colocado = False
        k = max(0, bisect_right(inicios, a) - 1)
        while k < len(textos) and inicios[k] < b:
            ini, fim = inicios[k], inicios[k] + len(textos[k])
            if elementos[k] is not None and fim > a:
                edicoes.setdefault(k, []).append((max(a, ini) - ini, min(b, fim) - ini,
                                                  "" if colocado else s["substituto"]))
                colocado = True
            k += 1
    for k, lista in edicoes.items():
        texto = textos[k]
        for ini, fim, novo in sorted(lista, reverse=True):
            texto = texto[:ini] + novo + texto[fim:]
        _gravar_texto(elementos[k], texto)


def _aplicador_fluxo(elementos: list, textos: list[str], anon: Anonimizador) -> Callable[[Resultado], list[Resultado]]:
    def aplicar(r: Resultado) -> list[Resultado]:
        if r.original == "".join(textos):
            _distribuir(elementos, textos, r.substituicoes)
            return []
        # O motor corrigiu a codificação do texto (mojibake) e as posições deixaram de corresponder
        # aos nós. Cada nó é reanalisado isoladamente e recebe o próprio texto corrigido.
        reais = [(el, t) for el, t in zip(elementos, textos) if el is not None and t.strip()]
        novos = anon.anonimizar_lote([t for _, t in reais], mesmo_documento=True, continuar=True)
        for (el, _), novo in zip(reais, novos):
            _gravar_texto(el, novo.texto)
        return novos
    return aplicar


def aplicador(gravar: Callable[[str], None]) -> Callable[[Resultado], list[Resultado]]:
    """Aplicador genérico: chama ``gravar`` com o texto anonimizado quando algo foi tarjado."""
    def aplicar(r: Resultado) -> list[Resultado]:
        if r.tarjadas:
            gravar(r.texto)
        return []
    return aplicar


def unidades(raiz, anon: Anonimizador) -> list[Unidade]:
    """Unidades de análise de uma parte XML (ver a descrição do módulo)."""
    lista: list[Unidade] = []
    elementos, textos = _fluxo(raiz)
    if any(t.strip() for el, t in zip(elementos, textos) if el is not None):
        lista.append(Unidade("".join(textos), _aplicador_fluxo(elementos, textos, anon)))
    for nos in _instrucoes(raiz):
        textos_instr = [n.text or "" for n in nos]
        if any(t.strip() for t in textos_instr):
            lista.append(Unidade("".join(textos_instr), _aplicador_fluxo(nos, textos_instr, anon)))
    for v in raiz.iter(q("c", "v")):
        if v.text and v.text.strip():
            lista.append(Unidade(v.text, aplicador(lambda t, el=v: _gravar_texto(el, t))))
    for el, atributo in _atributos_livres(raiz):
        lista.append(Unidade(el.get(atributo), aplicador(lambda t, el=el, at=atributo: el.set(at, t))))
    for el in raiz.iter():
        if not isinstance(el.tag, str):
            continue
        if el.tag not in _TRATADOS and tem_conteudo(el.text):
            lista.append(Unidade(el.text, aplicador(lambda t, el=el: setattr(el, "text", t))))
        if tem_conteudo(el.tail):
            lista.append(Unidade(el.tail, aplicador(lambda t, el=el: setattr(el, "tail", t))))
    return lista
