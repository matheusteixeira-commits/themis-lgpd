"""Anonimização de documentos ODF (ODT e ODS), o formato aberto adotado pelo e-PING.

Um documento ODF é um ZIP com o conteúdo em XML (``content.xml``, ``styles.xml`` — que guarda
cabeçalhos e rodapés —, e ``Object N/content.xml`` para gráficos e fórmulas incorporados), um
manifesto (``META-INF/manifest.xml``), metadados, configurações e imagens. O processamento:

* **aceita as alterações controladas**: o texto excluído (``text:tracked-changes``) e os autores das
  alterações são removidos; o texto inserido permanece;
* **remove** comentários (``office:annotation``), miniatura, configurações (``settings.xml``, que
  registram impressora e caminhos), macros, objetos binários incorporados e imagens em formatos que
  não podem ser analisados (StarView), e substitui os metadados por um registro mínimo;
* **analisa num único lote** o texto de todos os parágrafos — inclusive o conteúdo misto, em que um
  nome pode estar dividido entre trechos de formatação (``text:span``) e espaços codificados
  (``text:s``) —, atributos de texto livre (títulos, nomes de objetos e planilhas, links, valores de
  formulários), fórmulas e valores de células, todo texto residual e o texto das imagens (OCR e QR
  codes);
* em planilhas, uma célula cujo texto foi tarjado perde o valor numérico ou de data guardado à parte
  (``office:value``) e a fórmula, que poderiam reconstituir o dado;
* regrava o pacote com o ``mimetype`` em primeiro lugar e sem compressão, como exige a norma, e o
  manifesto apenas com as partes mantidas;
* **verifica** o arquivo gerado: nenhum valor tarjado pode continuar legível em texto, atributo ou
  imagem.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

from ..motor import Anonimizador
from . import ArquivoInvalido, ResultadoArquivo, VazamentoDetectado
from . import metarquivo as M
from . import xml_office as X
from .imagem import analisar_incorporadas, aviso_imagens
from .midia import formato_imagem, limpar_imagens, metadados_restantes
from .pacote import gravar_xml, ler_xml
from .verificacao import valores_protegidos, valores_tarjados, verificar_ausencia

TIPOS = {
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
}
NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "form": "urn:oasis:names:tc:opendocument:xmlns:form:1.0",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
    "calcext": "urn:org:documentfoundation:names:experimental:calc:xmlns:calcext:1.0",
}


def q(prefixo: str, nome: str) -> str:
    """Nome qualificado no formato do lxml."""
    return f"{{{NS[prefixo]}}}{nome}"


_PARAGRAFOS = (q("text", "p"), q("text", "h"))
#: Elementos sem texto que separam palavras no fluxo.
_SEPARADORES = {q("text", "tab"): "\t", q("text", "line-break"): "\n", q("text", "soft-page-break"): ""}
#: Comentários, alterações controladas e dados binários: removidos antes da análise.
_REMOVER = (q("office", "annotation"), q("office", "annotation-end"), q("text", "tracked-changes"),
            q("text", "change"), q("text", "change-start"), q("text", "change-end"), q("office", "binary-data"))
#: Atributos de texto livre, analisados como unidades isoladas.
_ATRIBUTOS = (q("office", "title"), q("xlink", "title"), q("office", "string-value"), q("draw", "name"),
              q("table", "name"), q("text", "description"), q("text", "string-value"), q("form", "label"),
              q("form", "value"), q("form", "current-value"), q("form", "title"), q("form", "help-message"))
#: Atributos de uma célula que guardam o valor à parte do texto exibido.
_VALORES_CELULA = (q("office", "value"), q("office", "date-value"), q("office", "time-value"),
                   q("office", "boolean-value"), q("office", "string-value"), q("table", "formula"))
#: Partes descartadas: miniatura, configurações, macros, assinaturas e prévias de objetos.
_DESCARTAR = ("Thumbnails/", "Configurations2/", "Basic/", "Scripts/", "ObjectReplacements/", "settings.xml",
              "META-INF/documentsignatures.xml", "META-INF/macrosignatures.xml", "layout-cache")
_META_MINIMO = (b'<?xml version="1.0" encoding="UTF-8"?>\n<office:document-meta '
                b'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
                b'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" office:version="1.3">'
                b"<office:meta><meta:generator>Themis LGPD</meta:generator></office:meta></office:document-meta>")
_DATA_FIXA = (1980, 1, 1, 0, 0, 0)


@dataclass
class _Trecho:
    """Texto de um elemento (``text``) ou o texto que o segue (``tail``), no conteúdo misto do ODF."""

    el: object
    campo: str

    def gravar(self, texto: str) -> None:
        setattr(self.el, self.campo, texto)


def _remover(el) -> None:
    """Remove o elemento preservando o texto que o segue (``tail``), que pertence ao parágrafo."""
    pai = el.getparent()
    if pai is None:
        return
    if el.tail:
        anterior = el.getprevious()
        if anterior is not None:
            anterior.tail = (anterior.tail or "") + el.tail
        else:
            pai.text = (pai.text or "") + el.tail
    pai.remove(el)


def _gravar(trecho: _Trecho, texto: str) -> None:
    trecho.gravar(texto)


def _trechos(paragrafo, cobertos: set) -> list[tuple[_Trecho | None, str]]:
    """Texto de um parágrafo em ordem de leitura; parágrafos aninhados (notas, quadros) ficam de fora."""
    saida: list[tuple[_Trecho | None, str]] = []

    def visitar(el) -> None:
        if el.text:
            saida.append((_Trecho(el, "text"), el.text))
            cobertos.add((id(el), "text"))
        for filho in el:
            if not isinstance(filho.tag, str):
                pass
            elif filho.tag in _PARAGRAFOS:
                saida.append((None, "\n"))
            elif filho.tag == q("text", "s"):
                saida.append((None, " " * int(filho.get(q("text", "c"), "1") or 1)))
            elif filho.tag in _SEPARADORES:
                saida.append((None, _SEPARADORES[filho.tag]))
            else:
                visitar(filho)
            if filho.tail:
                saida.append((_Trecho(filho, "tail"), filho.tail))
                cobertos.add((id(filho), "tail"))

    visitar(paragrafo)
    return saida


def _unidades(raiz, anon: Anonimizador, celulas: list) -> list[X.Unidade]:
    """Unidades de análise de uma parte XML do ODF."""
    unidades: list[X.Unidade] = []
    cobertos: set = set()
    elementos: list = []
    textos: list[str] = []
    for paragrafo in raiz.iter(*_PARAGRAFOS):
        if textos:
            elementos.append(None)
            textos.append("\n")
        for trecho, texto in _trechos(paragrafo, cobertos):
            elementos.append(trecho)
            textos.append(texto)
    if any(t.strip() for el, t in zip(elementos, textos) if el is not None):
        unidades.append(X.Unidade("".join(textos), _aplicador_fluxo(elementos, textos, anon)))

    for celula in raiz.iter(q("table", "table-cell"), q("table", "covered-table-cell")):
        celulas.append((celula, _texto_celula(celula)))
        formula = celula.get(q("table", "formula"))
        if formula and X.tem_conteudo(formula):
            unidades.append(X.Unidade(formula, X.aplicador(lambda _t, c=celula: _limpar_valores(c))))
    for el in raiz.iter():
        if not isinstance(el.tag, str):
            continue
        for atributo in _ATRIBUTOS:
            valor = el.get(atributo)
            if valor and X.tem_conteudo(valor):
                unidades.append(X.Unidade(valor, X.aplicador(lambda t, el=el, at=atributo: el.set(at, t))))
        href = el.get(q("xlink", "href"))
        if href and not _interno(href):
            unidades.append(X.Unidade(href, X.aplicador(lambda _t, el=el: el.set(q("xlink", "href"), "#"))))
        if X.tem_conteudo(el.text) and (id(el), "text") not in cobertos:
            unidades.append(X.Unidade(el.text, X.aplicador(lambda t, el=el: setattr(el, "text", t))))
        if X.tem_conteudo(el.tail) and (id(el), "tail") not in cobertos:
            unidades.append(X.Unidade(el.tail, X.aplicador(lambda t, el=el: setattr(el, "tail", t))))
    return unidades


def _aplicador_fluxo(elementos: list, textos: list[str], anon: Anonimizador):
    def aplicar(r):
        if r.original == "".join(textos):
            X._distribuir(elementos, textos, r.substituicoes, _gravar)  # noqa: SLF001 - mesma regra do Office
            return []
        # O motor corrigiu a codificação (mojibake): cada trecho é reanalisado isoladamente.
        reais = [(el, t) for el, t in zip(elementos, textos) if el is not None and t.strip()]
        novos = anon.anonimizar_lote([t for _, t in reais], mesmo_documento=True, continuar=True)
        for (el, _), novo in zip(reais, novos):
            el.gravar(novo.texto)
        return novos
    return aplicar


def _texto_celula(celula) -> str:
    return "\n".join("".join(p.itertext()) for p in celula.iter(*_PARAGRAFOS))


def _limpar_valores(celula) -> None:
    """A célula passa a ser texto: valor numérico, de data e fórmula, que reconstituiriam o dado, saem."""
    for atributo in _VALORES_CELULA:
        celula.attrib.pop(atributo, None)
    if celula.get(q("office", "value-type")):
        celula.set(q("office", "value-type"), "string")
    if celula.get(q("calcext", "value-type")):
        celula.set(q("calcext", "value-type"), "string")


def _interno(href: str) -> bool:
    """Referência a uma parte do próprio pacote ("Pictures/…", "./Object 1") ou a um marcador interno."""
    return href.startswith(("#", "./Object", "Object ", "Pictures/", "./Pictures/"))


def _texto_xml(dados: bytes) -> str:
    """Todo o texto e todos os valores de atributo de uma parte XML (verificação final)."""
    raiz = ler_xml(dados, dtd_externa=True)
    partes = []
    for el in raiz.iter():
        if not isinstance(el.tag, str):
            continue
        partes += [el.text or "", el.tail or "", *el.attrib.values()]
    return "\n".join(p for p in partes if p and p.strip())


def tipo_odf(dados: bytes) -> str | None:
    """``odt``, ``ods`` ou ``None``, pelo ``mimetype`` do pacote; ``"outro"`` para os demais ODF."""
    try:
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            if "mimetype" not in z.namelist():
                return None
            mime = z.read("mimetype").decode("ascii", "replace").strip()
    except zipfile.BadZipFile:
        return None
    if mime.startswith("application/vnd.oasis.opendocument."):
        return TIPOS.get(mime, "outro")
    return None


def anonimizar_odf(dados: bytes, anon: Anonimizador, nome: str, *, ocr: bool = True,
                   verificar: bool = True) -> ResultadoArquivo:
    """Anonimiza um documento ODT ou ODS (ver a descrição do módulo).

    Raises:
        ArquivoInvalido: Pacote corrompido, protegido por senha, de tipo não suportado ou com imagem
            corrompida.
        FalhaOCR: O documento tem imagens, o OCR foi pedido e nenhum mecanismo está disponível.
        VazamentoDetectado: A verificação encontrou valor tarjado legível no arquivo gerado.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            nomes = [i.filename for i in z.infolist() if not i.is_dir()]
            if len(set(nomes)) != len(nomes):
                raise ArquivoInvalido("Documento ODF com partes duplicadas.")
            partes = {n: z.read(n) for n in nomes}
    except zipfile.BadZipFile as erro:
        raise ArquivoInvalido("Documento ODF corrompido.") from erro
    formato = TIPOS.get(partes.get("mimetype", b"").decode("ascii", "replace").strip())
    if formato is None:
        raise ArquivoInvalido("Documento ODF de tipo não suportado: use ODT (texto) ou ODS (planilha).")
    manifesto_bruto = partes.get("META-INF/manifest.xml")
    if manifesto_bruto is None or b"encryption-data" in manifesto_bruto:
        raise ArquivoInvalido("Documento ODF protegido por senha ou sem manifesto: remova a senha e salve de novo.")

    avisos: list[str] = []
    descartadas = [n for n in nomes if n.startswith(_DESCARTAR)]
    manter = [n for n in nomes if n not in descartadas and n != "META-INF/manifest.xml"]
    arvores: dict[str, object] = {}
    unidades: list[X.Unidade] = []
    celulas: list = []
    comentarios = alteracoes = binarios = 0
    metarquivos: dict[str, M.Metarquivo] = {}
    sem_analise: list[str] = []
    for parte in manter:
        if parte == "mimetype" or parte == "meta.xml":
            continue
        if parte.endswith(".xml") or parte.endswith(".svg"):
            try:
                raiz = ler_xml(partes[parte], dtd_externa=parte.endswith(".svg"))
            except Exception as erro:
                raise ArquivoInvalido("Documento ODF com XML inválido.") from erro
            for el in list(raiz.iter(*_REMOVER)):
                if el.tag == q("office", "annotation"):
                    comentarios += 1
                elif el.tag == q("office", "binary-data"):
                    binarios += 1
                elif el.tag == q("text", "tracked-changes"):
                    alteracoes += len(el)
                _remover(el)
            arvores[parte] = raiz
            unidades += _unidades(raiz, anon, celulas)
        elif M.tipo_metarquivo(partes[parte]):
            try:
                meta = M.ler(partes[parte])
            except M.MetarquivoInvalido as erro:
                raise ArquivoInvalido("O documento contém um metarquivo (EMF/WMF) corrompido.") from erro
            if meta.trechos:
                from .docx import _aplicador_metarquivo

                metarquivos[parte] = meta
                unidades.append(X.Unidade(meta.texto, _aplicador_metarquivo(meta)))
        elif formato_imagem(partes[parte]) is None:
            sem_analise.append(parte)  # StarView (.svm), objetos binários e formatos desconhecidos
    manter = [n for n in manter if n not in sem_analise]

    imagens = analisar_incorporadas(partes, sorted(p for p in manter if p not in arvores and p not in metarquivos
                                                   and p != "mimetype"), anon.modo, ocr=ocr)
    for analise, _f in imagens.values():
        unidades += analise.unidades()

    resultados = X.analisar(unidades, anon)
    for celula, texto in celulas:
        if _texto_celula(celula) != texto:
            _limpar_valores(celula)

    substituir = {parte: gravar_xml(raiz) for parte, raiz in arvores.items()}
    substituir.update({parte: bytes(meta.dados) for parte, meta in metarquivos.items()})
    tarjadas = 0
    for parte, (analise, formato_img) in imagens.items():
        if analise.tarjada:
            analise.desenhar()
            if verificar:
                analise.verificar(resultados, anon.permitir)
            substituir[parte] = analise.codificar(formato_img)
            tarjadas += 1
    substituir.update(limpar_imagens(partes, [p for p in manter if p not in substituir and p != "mimetype"]))
    if "meta.xml" in manter:
        substituir["meta.xml"] = _META_MINIMO
    substituir["META-INF/manifest.xml"] = _manifesto(manifesto_bruto, set(manter))
    saida = _gravar_pacote(partes, manter, substituir)

    if alteracoes:
        avisos.append(f"{alteracoes} alteração(ões) controlada(s) aceita(s): o texto excluído foi removido do arquivo.")
    if comentarios:
        avisos.append(f"{comentarios} comentário(s) removido(s).")
    if binarios or sem_analise:
        avisos.append(f"{binarios + len(sem_analise)} objeto(s) ou imagem(ns) em formato não analisável (StarView, "
                      "objetos binários) removido(s); confira se o documento está completo.")
    if any(n.startswith(("Basic/", "Scripts/")) for n in descartadas):
        avisos.append("Macros removidas.")
    avisos.append("Metadados (autor, datas, estatísticas), miniatura e configurações do documento removidos.")
    avisos += aviso_imagens(len(imagens), tarjadas, ocr)
    if verificar:
        _verificar(saida, resultados, anon)
    return ResultadoArquivo(saida, formato, nome, resultados, avisos)


def _manifesto(bruto: bytes, mantidas: set[str]) -> bytes:
    """Manifesto apenas com as partes mantidas (e as pastas que as contêm)."""
    raiz = ler_xml(bruto)
    for entrada in list(raiz.iter(q("manifest", "file-entry"))):
        caminho = entrada.get(q("manifest", "full-path"), "")
        if caminho == "/" or caminho in mantidas or (caminho.endswith("/") and any(m.startswith(caminho)
                                                                                     for m in mantidas)):
            continue
        entrada.getparent().remove(entrada)
    return gravar_xml(raiz)


def _gravar_pacote(partes: dict[str, bytes], manter: list[str], substituir: dict[str, bytes]) -> bytes:
    """ZIP com o ``mimetype`` em primeiro lugar e sem compressão, como exige a norma ODF."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        ordem = ["mimetype"] + [n for n in manter if n != "mimetype"] + ["META-INF/manifest.xml"]
        for nome in dict.fromkeys(ordem):
            info = zipfile.ZipInfo(nome, date_time=_DATA_FIXA)
            info.compress_type = zipfile.ZIP_STORED if nome == "mimetype" else zipfile.ZIP_DEFLATED
            z.writestr(info, substituir.get(nome, partes.get(nome, b"")))
    return buf.getvalue()


def _verificar(saida: bytes, resultados, anon: Anonimizador) -> None:
    """Relê o pacote gerado: texto, atributos e metadados de imagens."""
    textos = []
    with zipfile.ZipFile(io.BytesIO(saida)) as z:
        for nome in z.namelist():
            dados = z.read(nome)
            if nome.endswith((".xml", ".svg")):
                textos.append(_texto_xml(dados))
            elif formato_imagem(dados) and metadados_restantes(dados):
                raise VazamentoDetectado("Imagem com metadados (EXIF, GPS ou XMP) no documento gerado.")
            elif M.tipo_metarquivo(dados):
                textos.append(M.ler(dados).texto)
    sobras = verificar_ausencia("\n".join(textos), valores_tarjados(resultados),
                                valores_protegidos(resultados, anon.permitir))
    if sobras:
        raise VazamentoDetectado(f"{len(sobras)} trecho(s) tarjado(s) ainda legível(is) no documento gerado.")
