"""Anonimização de páginas HTML, o formato dos documentos produzidos no SEI e em portais.

O HTML é interpretado (entidades como ``&#46;`` e ``&eacute;`` decodificadas, comentários
descartados) e todo o texto da página entra num único fluxo de análise, como em um documento do
Office: um nome dividido entre elementos de formatação (``<b>Maria</b> Souza``) é visto inteiro.
Também são analisados os atributos que guardam texto escrito pelo autor (``title``, ``alt``,
``placeholder``, valores de formulário, ``aria-label``, atributos ``data-``), os endereços de links e
de recursos — um link com dado pessoal (``mailto:``, CPF na URL) deixa de apontar para ele — e as
imagens incorporadas em ``data:`` (OCR, QR codes e metadados).

São removidos: scripts e manipuladores de eventos (``on…``), quadros e objetos incorporados
(``iframe``, ``object``, ``embed``), que trariam conteúdo não analisado, e metadados (``<meta>``
de autor, descrição e semelhantes). A página gerada é gravada em UTF-8 e relida na verificação
final.
"""

from __future__ import annotations

import base64
import re

from ..motor import Anonimizador
from . import ArquivoInvalido, ResultadoArquivo, VazamentoDetectado
from . import xml_office as X
from .imagem import analisar_incorporadas, aviso_imagens
from .midia import limpar_imagens
from .verificacao import valores_protegidos, valores_tarjados, verificar_ausencia

#: Elementos que iniciam um novo bloco de texto (separador de linha no fluxo).
_BLOCOS = frozenset({
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "td", "th", "tr", "table", "thead", "tbody",
    "section", "article", "header", "footer", "nav", "aside", "blockquote", "pre", "dd", "dt", "dl", "title",
    "caption", "figure", "figcaption", "form", "fieldset", "legend", "address", "main", "option", "label", "hr",
})
#: Elementos removidos por inteiro: conteúdo executável ou externo, não analisável.
_REMOVER = ("script", "noscript", "iframe", "frame", "frameset", "object", "embed", "applet", "template")
#: Atributos de texto livre.
_ATRIBUTOS = ("title", "alt", "placeholder", "value", "label", "aria-label", "aria-description", "summary",
              "abbr", "download")
#: Atributos com endereço (URL).
_ENDERECOS = ("href", "src", "action", "cite", "poster", "background", "longdesc")
_DATA_URI = re.compile(r"^data:image/[\w.+-]+;base64,(?P<dados>[A-Za-z0-9+/=\s]+)$", re.IGNORECASE)


def decodificar(dados: bytes) -> str:
    """Texto da página: BOM ou ``charset`` declarado; senão UTF-8 e, por fim, Windows-1252."""
    if dados.startswith(b"\xef\xbb\xbf"):
        return dados[3:].decode("utf-8")
    declarado = re.search(rb"<meta[^>]+charset\s*=\s*[\"']?([\w-]+)", dados[:4096], re.IGNORECASE)
    if declarado:
        try:
            return dados.decode(declarado.group(1).decode("ascii"))
        except (LookupError, UnicodeDecodeError):
            pass
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode("cp1252", errors="replace")


def _documento(texto: str):
    import lxml.html

    parser = lxml.html.HTMLParser(remove_comments=True, remove_pis=True, no_network=True, encoding=None)
    try:
        return lxml.html.document_fromstring(texto, parser=parser)
    except Exception as erro:
        raise ArquivoInvalido("HTML inválido.") from erro


def _trechos(raiz) -> tuple[list, list[str]]:
    """Fluxo de texto da página com os trechos de origem (texto do elemento ou texto que o segue)."""
    from .odf import _Trecho

    elementos: list = []
    textos: list[str] = []

    def separar() -> None:
        if textos and textos[-1] != "\n":
            elementos.append(None)
            textos.append("\n")

    def visitar(el) -> None:
        tag = el.tag if isinstance(el.tag, str) else ""
        if tag in ("style",):
            return
        if tag in _BLOCOS:
            separar()
        if tag == "br":
            elementos.append(None)
            textos.append("\n")
        if el.text and tag not in ("style",):
            elementos.append(_Trecho(el, "text"))
            textos.append(el.text)
        for filho in el:
            visitar(filho)
            if filho.tail:
                elementos.append(_Trecho(filho, "tail"))
                textos.append(filho.tail)
        if tag in _BLOCOS:
            separar()

    visitar(raiz)
    return elementos, textos


def anonimizar_html(dados: bytes, anon: Anonimizador, nome: str, *, ocr: bool = True,
                    verificar: bool = True) -> ResultadoArquivo:
    """Anonimiza uma página HTML (ver a descrição do módulo).

    Raises:
        ArquivoInvalido: HTML ilegível ou imagem incorporada corrompida.
        FalhaOCR: Há imagens incorporadas, o OCR foi pedido e nenhum mecanismo está disponível.
        VazamentoDetectado: A verificação encontrou valor tarjado legível na página gerada.
    """
    import lxml.html

    raiz = _documento(decodificar(dados))
    removidos = 0
    for el in list(raiz.iter(*_REMOVER)):
        el.drop_tree()  # preserva o texto que segue o elemento
        removidos += 1
    metas = 0
    for meta in list(raiz.iter("meta")):
        if meta.get("charset") is None and (meta.get("name") or meta.get("property") or meta.get("itemprop")) \
                and (meta.get("name") or "").lower() != "viewport":
            meta.drop_tree()
            metas += 1
    for el in raiz.iter():
        if isinstance(el.tag, str):
            for atributo in [a for a in el.attrib if a.lower().startswith("on")]:
                del el.attrib[atributo]

    elementos, textos = _trechos(raiz)
    unidades: list[X.Unidade] = []
    if any(t.strip() for el, t in zip(elementos, textos) if el is not None):
        from .odf import _aplicador_fluxo

        unidades.append(X.Unidade("".join(textos), _aplicador_fluxo(elementos, textos, anon)))

    imagens_dados: dict[str, bytes] = {}
    portadores: dict[str, object] = {}
    for el in raiz.iter():
        if not isinstance(el.tag, str):
            continue
        for atributo in list(el.attrib):
            valor = el.get(atributo) or ""
            nome_attr = atributo.lower()
            if nome_attr in _ENDERECOS:
                m = _DATA_URI.match(valor.strip())
                if m:
                    chave = f"imagem{len(imagens_dados) + 1}"
                    try:
                        imagens_dados[chave] = base64.b64decode(m.group("dados"))
                    except ValueError as erro:
                        raise ArquivoInvalido("Imagem incorporada ao HTML corrompida.") from erro
                    portadores[chave] = (el, atributo)
                elif valor and not valor.startswith("#"):
                    neutro = "#" if nome_attr == "href" else ""
                    unidades.append(X.Unidade(valor, X.aplicador(lambda _t, el=el, at=atributo, n=neutro:
                                                                  el.set(at, n))))
            elif (nome_attr in _ATRIBUTOS or nome_attr.startswith("data-")) and X.tem_conteudo(valor):
                unidades.append(X.Unidade(valor, X.aplicador(lambda t, el=el, at=atributo: el.set(at, t))))
            elif nome_attr == "content" and el.tag == "meta" and X.tem_conteudo(valor):
                unidades.append(X.Unidade(valor, X.aplicador(lambda t, el=el: el.set("content", t))))

    imagens = analisar_incorporadas(imagens_dados, sorted(imagens_dados), anon.modo, ocr=ocr)
    for analise, _f in imagens.values():
        unidades += analise.unidades()
    resultados = X.analisar(unidades, anon)

    novas: dict[str, bytes] = {}
    tarjadas = 0
    for chave, (analise, formato) in imagens.items():
        if analise.tarjada:
            analise.desenhar()
            if verificar:
                analise.verificar(resultados, anon.permitir)
            novas[chave] = analise.codificar(formato)
            tarjadas += 1
    novas.update(limpar_imagens(imagens_dados, [c for c in imagens_dados if c not in novas]))
    for chave, (el, atributo) in portadores.items():
        conteudo = novas.get(chave, imagens_dados[chave])
        tipo = "png" if conteudo.startswith(b"\x89PNG") else "jpeg"
        el.set(atributo, f"data:image/{tipo};base64,{base64.b64encode(conteudo).decode('ascii')}")

    cabeca = raiz.find("head")
    if cabeca is not None and cabeca.find("meta[@charset]") is None:
        cabeca.insert(0, lxml.html.Element("meta", charset="utf-8"))
    saida = b"<!DOCTYPE html>\n" + lxml.html.tostring(raiz, encoding="utf-8", method="html")

    avisos: list[str] = []
    if removidos:
        avisos.append(f"{removidos} script(s), quadro(s) ou objeto(s) incorporado(s) removido(s) sem análise.")
    if metas:
        avisos.append(f"{metas} metadado(s) da página (<meta>) removido(s).")
    avisos += aviso_imagens(len(imagens), tarjadas, ocr)
    if verificar:
        _verificar(saida, resultados, anon)
    return ResultadoArquivo(saida, "html", nome, resultados, avisos)


def texto_html(dados: bytes) -> str:
    """Todo o texto e todos os valores de atributo da página (verificação final)."""
    raiz = _documento(decodificar(dados))
    partes: list[str] = []
    for el in raiz.iter():
        if isinstance(el.tag, str):
            partes += [el.text or "", el.tail or ""]
            partes += [v for a, v in el.attrib.items() if not v.startswith("data:image/")]
    return "\n".join(p for p in partes if p and p.strip())


def _verificar(saida: bytes, resultados, anon: Anonimizador) -> None:
    sobras = verificar_ausencia(texto_html(saida), valores_tarjados(resultados),
                                valores_protegidos(resultados, anon.permitir))
    if sobras:
        raise VazamentoDetectado(f"{len(sobras)} trecho(s) tarjado(s) ainda legível(is) na página gerada.")
