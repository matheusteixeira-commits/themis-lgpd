"""Anonimização de documentos Word (.docx, e também .docm e .dotx, gravados como .docx).

O pacote é tratado diretamente no nível do XML, parte por parte, para que nenhum conteúdo dependa
do que uma biblioteca de alto nível sabe interpretar.

**Conteúdo analisado e tarjado** (ver :mod:`themis_lgpd.formatos.xml_office`)

* Texto de todas as partes: corpo, tabelas, caixas de texto, cabeçalhos e rodapés, notas de rodapé
  e de fim, equações, gráficos (títulos, rótulos e valores em cache), SmartArt e formas.
* Instruções de campo (ex.: ``HYPERLINK "mailto:..."``) e campos simples.
* Atributos de texto livre: texto alternativo e nome de imagens e formas, dicas de hiperlinks,
  rótulos e itens de controles de conteúdo e de campos de formulário, texto de WordArt.
* Destinos de hiperlinks externos. Referências a arquivos locais são sempre removidas, pois o
  caminho costuma conter o nome do usuário ou do servidor.

**Conteúdo removido**

* Alterações controladas, que são aceitas: o texto excluído é descartado e os nomes dos revisores
  desaparecem.
* Comentários e a lista de autores.
* Propriedades do documento (autor, empresa, gerente, título, palavras-chave, propriedades
  personalizadas) e a miniatura da primeira página.
* Dados XML personalizados, variáveis do documento, modelo anexado, configuração de mala direta,
  propriedades de marcas inteligentes e assinaturas digitais.
* Objetos incorporados (planilhas de gráficos, objetos OLE, controles ActiveX), blocos de conteúdo
  importado (``altChunk``), glossário e macros. O usuário é avisado.
* Partes do pacote não referenciadas pelo documento.

Ao final, todo o texto e todos os atributos do pacote gerado são relidos e comparados com os
valores tarjados (ver :mod:`themis_lgpd.formatos.verificacao`).
"""

from __future__ import annotations

import posixpath
import re
from collections import Counter
from urllib.parse import unquote

from ..motor import Anonimizador
from . import ArquivoInvalido, ResultadoArquivo, VazamentoDetectado
from . import metarquivo as M
from . import xml_office as X
from .imagem import analisar_incorporadas, aviso_imagens
from .midia import limpar_imagens
from .pacote import NS_R, TIPOS_CONTEUDO, Pacote, externo, gravar_xml, ler_xml, tipo_relacionamento
from .verificacao import (
    imagens_com_metadados,
    texto_de_pacote,
    valores_protegidos,
    valores_tarjados,
    verificar_ausencia,
)

_DCTERMS = "http://purl.org/dc/terms/"

#: Prefixo dos namespaces do formato OOXML Strict, que não é suportado.
_NS_STRICT = "http://purl.oclc.org/ooxml/"

#: Revisões cujo conteúdo é descartado (texto excluído ou movido) ao aceitar as alterações.
_REVISOES_DESCARTAR = ("del", "moveFrom")
#: Revisões cujo conteúdo permanece (texto inserido ou movido) ao aceitar as alterações.
_REVISOES_INCORPORAR = ("ins", "moveTo")
#: Marcas de revisão sem conteúdo próprio; todas registram o autor da alteração.
_MARCAS_REVISAO = (
    "rPrChange", "pPrChange", "sectPrChange", "tblPrChange", "tblPrExChange", "trPrChange", "tcPrChange",
    "tblGridChange", "numberingChange", "cellIns", "cellDel", "cellMerge", "moveFromRangeStart",
    "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd", "customXmlInsRangeStart", "customXmlInsRangeEnd",
    "customXmlDelRangeStart", "customXmlDelRangeEnd", "customXmlMoveFromRangeStart", "customXmlMoveFromRangeEnd",
    "customXmlMoveToRangeStart", "customXmlMoveToRangeEnd",
)
#: Elementos removidos onde aparecerem: variáveis do documento, modelo anexado (caminho local), mala
#: direta (fonte de dados e consulta), propriedades de marcas inteligentes e de XML personalizado
#: (repetem o texto marcado, ex.: o nome de uma pessoa) e dados binários de campos.
_ELEMENTOS_REMOVER = frozenset({X.q("w", "docVars"), X.q("w", "attachedTemplate"), X.q("w", "mailMerge"),
                                X.q("w", "smartTagPr"), X.q("w", "customXmlPr"), X.q("w", "fldData"),
                                X.q("w", "rsids"), X.q("w", "rsid")})

_NS_W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
_NS_W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
_NS_P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
#: Identificadores gerados pelo Word e pelo PowerPoint a cada sessão de edição, parágrafo e slide. Não
#: são visíveis, mas permitem correlacionar o arquivo anonimizado com a versão original e com outras.
_ELEMENTOS_IDENTIFICADORES = frozenset({f"{{{_NS_W14}}}docId", f"{{{_NS_W15}}}docId", f"{{{_NS_P14}}}creationId"})
_ATRIBUTOS_IDENTIFICADORES = frozenset({f"{{{_NS_W14}}}paraId", f"{{{_NS_W14}}}textId"})
#: Pasta e prefixo dos nomes neutros dados às partes de mídia.
_PREFIXO_MIDIA = "midia"

#: Relacionamentos removidos do pacote, pelo último segmento do tipo, e a categoria usada nos avisos.
_RELACIONAMENTOS_REMOVER = {
    "extended-properties": None, "custom-properties": None, "thumbnail": None,
    "comments": None, "commentsextended": None, "commentsids": None, "commentsextensible": None, "people": None,
    "customxml": None, "glossarydocument": None, "attachedtemplate": None, "printersettings": None,
    "mailmergesource": None, "mailmergeheadersource": None, "recipientdata": None,
    "webextensiontaskpanes": None, "extensibility": None,
    "package": "objetos", "oleobject": "objetos", "control": "objetos", "activexcontrolbinary": "objetos",
    "afchunk": "blocos",
    "origin": "assinatura",
    "vbaproject": "macros", "wordvbadata": "macros", "keymapcustomizations": "macros", "attachedtoolbars": "macros",
}

#: Tipos de conteúdo da parte principal que são convertidos para documento comum: o arquivo de saída
#: não tem macros e é sempre um documento, não um modelo.
_TIPO_DOCUMENTO = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
_TIPOS_PRINCIPAIS = {
    "application/vnd.ms-word.document.macroEnabled.main+xml": _TIPO_DOCUMENTO,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml": _TIPO_DOCUMENTO,
    "application/vnd.ms-word.template.macroEnabledTemplate.main+xml": _TIPO_DOCUMENTO,
}

#: Destinos externos aceitos como URL; qualquer outro destino externo é caminho de arquivo.
_URL = re.compile(r"^(?:https?|mailto|ftp|tel):", re.IGNORECASE)
#: Extensões de imagens rasterizadas.
IMAGENS_RASTER = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp")
#: Extensões de imagens vetoriais (metarquivos do Windows e SVG).
METARQUIVOS = (".emf", ".wmf", ".svg")
IMAGENS = IMAGENS_RASTER + METARQUIVOS


# ---------------------------------------------------------------------------- revisões e comentários
def _aceitar_revisoes(raiz) -> int:
    """Aceita todas as alterações controladas e devolve quantas foram encontradas."""
    total = 0
    for nome in _REVISOES_DESCARTAR:
        for el in list(raiz.iter(X.q("w", nome))):
            el.getparent().remove(el)
            total += 1
    for nome in _REVISOES_INCORPORAR:
        for el in list(raiz.iter(X.q("w", nome))):
            pai = el.getparent()
            posicao = pai.index(el)
            for filho in list(el):
                pai.insert(posicao, filho)
                posicao += 1
            pai.remove(el)
            total += 1
    for nome in _MARCAS_REVISAO:
        for el in list(raiz.iter(X.q("w", nome))):
            el.getparent().remove(el)
    return total


def _remover_comentarios(raiz) -> int:
    """Remove as âncoras e referências de comentários e devolve quantos comentários havia."""
    for nome in ("commentRangeStart", "commentRangeEnd"):
        for el in list(raiz.iter(X.q("w", nome))):
            el.getparent().remove(el)
    total = 0
    for el in list(raiz.iter(X.q("w", "commentReference"))):
        pai = el.getparent()
        if pai.tag == X.q("w", "r"):
            pai.getparent().remove(pai)  # o trecho só existe para exibir a marca do comentário
        else:
            pai.remove(el)
        total += 1
    return total


def _remover_elementos(raiz, ids_removidos: set[str]) -> None:
    """Remove elementos de privacidade, identificadores de revisão e os que apontam para
    relacionamentos removidos; dá nome neutro às imagens e formas."""
    from lxml import etree

    imagens = 0
    for el in list(raiz.iter()):
        if not isinstance(el.tag, str):
            continue
        if el.tag in _ELEMENTOS_REMOVER or el.tag in _ELEMENTOS_IDENTIFICADORES or \
                etree.QName(el).localname == "dataBinding" or (
                ids_removidos and any(etree.QName(a).namespace == NS_R and v in ids_removidos
                                      for a, v in el.attrib.items())):
            pai = el.getparent()
            if pai is not None:
                pai.remove(el)
            continue
        for atributo in list(el.attrib):
            nome = etree.QName(atributo)
            if (nome.namespace == X.NS["w"] and nome.localname.startswith("rsid")) or \
                    atributo in _ATRIBUTOS_IDENTIFICADORES:
                del el.attrib[atributo]
        # O nome interno de imagens e formas costuma ser o nome do arquivo de origem.
        if etree.QName(el).localname in ("docPr", "cNvPr") and el.get("name"):
            imagens += 1
            el.set("name", f"Imagem {imagens}")


def _aplicador_metarquivo(meta: M.Metarquivo):
    """Mascara no metarquivo os trechos tarjados do seu texto."""
    def aplicar(r):
        if r.original == meta.texto:
            for s in r.substituicoes:
                meta.mascarar(s["inicio"], s["fim"])
        elif r.tarjadas:
            # A codificação do texto foi corrigida e as posições deixaram de corresponder: o texto
            # inteiro do metarquivo é mascarado.
            meta.mascarar(0, len(meta.texto))
        return []
    return aplicar


def _nomes_neutros(partes: set[str]) -> dict[str, str]:
    """Nomes neutros para as partes de mídia (``word/media/midia1.png``…), mantendo pasta e extensão.

    O nome de uma imagem no pacote costuma ser o nome do arquivo no computador de quem a inseriu.
    """
    midias = sorted(p for p in partes if "/media/" in p.lower() or p.lower().endswith(METARQUIVOS + IMAGENS))
    ocupados = {p.lower() for p in partes}
    renomear: dict[str, str] = {}
    for indice, parte in enumerate(midias, start=1):
        pasta, arquivo = posixpath.split(parte)
        extensao = posixpath.splitext(arquivo)[1].lower()
        novo = posixpath.join(pasta, f"{_PREFIXO_MIDIA}{indice}{extensao}")
        if novo.lower() != parte.lower() and novo.lower() not in ocupados:
            renomear[parte] = novo
            ocupados.add(novo.lower())
    return renomear


def _sanear_propriedades(conteudo: bytes) -> bytes:
    """Propriedades básicas reduzidas às datas de criação e modificação."""
    raiz = ler_xml(conteudo)
    manter = {f"{{{_DCTERMS}}}created", f"{{{_DCTERMS}}}modified"}
    for filho in list(raiz):
        if filho.tag not in manter:
            raiz.remove(filho)
    return gravar_xml(raiz)


# ---------------------------------------------------------------------------- ponto de entrada
def anonimizar_docx(dados: bytes, anon: Anonimizador, nome: str, *, ocr: bool = True,
                    verificar: bool = True) -> ResultadoArquivo:
    """Anonimiza um documento Word.

    Args:
        dados: Conteúdo do arquivo.
        anon: Anonimizador configurado.
        nome: Nome do arquivo de saída.
        ocr: Analisa por OCR o texto das imagens incorporadas.
        verificar: Relê o pacote gerado e confirma que nenhum valor tarjado continua presente.

    Returns:
        O documento anonimizado, os resultados da análise e os avisos ao usuário.

    Raises:
        ArquivoInvalido: Pacote corrompido, criptografado, no formato Strict ou com XML inválido.
        FalhaOCR: Há imagens a analisar e nenhum mecanismo de OCR está disponível.
        VazamentoDetectado: A verificação encontrou valor tarjado no documento gerado.
    """
    return anonimizar_ooxml(dados, anon, nome, formato="docx", relacionamentos=_RELACIONAMENTOS_REMOVER,
                            tipos_principais=_TIPOS_PRINCIPAIS, ocr=ocr, verificar=verificar)


def anonimizar_ooxml(dados: bytes, anon: Anonimizador, nome: str, *, formato: str, relacionamentos: dict,
                     tipos_principais: dict[str, str], ocr: bool = True, verificar: bool = True) -> ResultadoArquivo:
    """Núcleo comum aos pacotes OOXML de documentos (DOCX) e apresentações (PPTX).

    Args:
        dados: Conteúdo do arquivo.
        anon: Anonimizador configurado.
        nome: Nome do arquivo de saída.
        formato: ``docx`` ou ``pptx``, usado nas mensagens e no resultado.
        relacionamentos: Relacionamentos removidos, pelo último segmento do tipo, e a categoria do
            aviso correspondente (``None`` quando a remoção não gera aviso).
        tipos_principais: Tipos de conteúdo da parte principal convertidos para o tipo comum
            (sem macros, documento em vez de modelo).
        ocr: Analisa por OCR o texto das imagens incorporadas.
        verificar: Relê o pacote gerado e confirma que nenhum valor tarjado continua presente.
    """
    try:
        import lxml  # noqa: F401
    except ImportError as erro:  # pragma: no cover - dependência opcional
        raise ArquivoInvalido(f"Suporte a {formato.upper()} requer: pip install 'themis-lgpd[arquivos]'") from erro

    pacote = Pacote.ler(dados)
    antes = pacote.partes_a_manter()
    removidos_por_parte: dict[str, set[str]] = {}
    categorias: Counter[str] = Counter()
    externos = []
    nucleo = None
    for origem, arvore, rel in pacote.iterar_relacionamentos():
        tipo = tipo_relacionamento(rel)
        if tipo in relacionamentos:
            removidos_por_parte.setdefault(origem, set()).add(rel.get("Id"))
            arvore.remove(rel)
            if relacionamentos[tipo]:
                categorias[relacionamentos[tipo]] += 1
        elif externo(rel):
            externos.append(rel)
        elif tipo == "core-properties" and origem == "":
            nucleo = pacote.destino(origem, rel)
    manter = pacote.partes_a_manter()
    orfas = sum(1 for n in pacote.ordem if n not in antes)

    arvores: dict[str, object] = {}
    unidades: list[X.Unidade] = []
    revisoes = comentarios = 0
    for parte in pacote.ordem:
        if (parte not in manter or parte in pacote.relacionamentos or parte in (nucleo, TIPOS_CONTEUDO)
                or not parte.lower().endswith((".xml", ".vml", ".svg"))):
            continue
        raiz = ler_xml(pacote.partes[parte], dtd_externa=parte.lower().endswith(".svg"))
        if isinstance(raiz.tag, str) and raiz.tag.startswith("{" + _NS_STRICT):
            raise ArquivoInvalido("Documento no formato OOXML Strict, que não é suportado: salve-o no formato "
                                  f"padrão do Office (.{formato}) e tente novamente.")
        revisoes += _aceitar_revisoes(raiz)
        comentarios += _remover_comentarios(raiz)
        _remover_elementos(raiz, removidos_por_parte.get(parte, set()))
        unidades += X.unidades(raiz, anon)
        arvores[parte] = raiz

    metarquivos: dict[str, M.Metarquivo] = {}
    ilegiveis = 0
    for parte in sorted(manter):
        if parte in arvores or not M.tipo_metarquivo(pacote.partes[parte]):
            continue
        try:
            meta = M.ler(pacote.partes[parte])
        except M.MetarquivoInvalido as erro:
            raise ArquivoInvalido("O documento contém um metarquivo (EMF/WMF) corrompido.") from erro
        ilegiveis += meta.ilegivel
        if meta.trechos:
            metarquivos[parte] = meta
            unidades.append(X.Unidade(meta.texto, _aplicador_metarquivo(meta)))

    # Imagens rasterizadas: o texto (OCR) e os QR codes entram no mesmo lote do documento.
    imagens = analisar_incorporadas(pacote.partes, sorted(p for p in manter if p not in arvores and
                                                          p not in metarquivos), anon.modo, ocr=ocr)
    for analise, _formato in imagens.values():
        unidades += analise.unidades()

    locais = 0
    for rel in externos:
        destino = rel.get("Target") or ""
        if _URL.match(destino):
            unidades.append(X.Unidade(unquote(destino), X.aplicador(lambda _t, rel=rel: rel.set("Target", "#"))))
        else:
            rel.set("Target", "#")
            locais += 1

    resultados = X.analisar(unidades, anon)

    substituir = {parte: gravar_xml(raiz) for parte, raiz in arvores.items()}
    substituir.update({parte: bytes(meta.dados) for parte, meta in metarquivos.items()})
    tarjadas = 0
    for parte, (analise, tipo_imagem) in imagens.items():
        if analise.tarjada:
            analise.desenhar()
            if verificar:
                analise.verificar(resultados, anon.permitir)
            substituir[parte] = analise.codificar(tipo_imagem)
            tarjadas += 1
    substituir.update(limpar_imagens(pacote.partes, [p for p in manter if p not in substituir]))
    if nucleo:
        substituir[nucleo] = _sanear_propriedades(pacote.partes[nucleo])
    renomear = _nomes_neutros(manter)
    pacote.renomear_partes(renomear)
    if TIPOS_CONTEUDO in pacote.partes:
        substituir[TIPOS_CONTEUDO] = pacote.ajustar_tipos(manter, tipos_principais, renomear)
    saida = pacote.gravar(manter, substituir, renomear)

    avisos: list[str] = []
    if revisoes:
        avisos.append(f"{revisoes} alteração(ões) controlada(s) aceita(s): o texto excluído foi removido do arquivo.")
    if comentarios or categorias["comentarios"]:
        avisos.append(f"{comentarios or categorias['comentarios']} comentário(s) removido(s).")
    if categorias["objetos"]:
        avisos.append(f"{categorias['objetos']} objeto(s) incorporado(s) (planilhas de gráficos, objetos OLE, "
                      "controles) removido(s) sem análise; gráficos mantêm a aparência, mas deixam de ser editáveis.")
    if categorias["blocos"]:
        avisos.append(f"{categorias['blocos']} bloco(s) de conteúdo importado (altChunk) removido(s) sem análise: "
                      "confira se o documento está completo.")
    if categorias["assinatura"]:
        avisos.append("A assinatura digital do documento foi removida (ela identifica o signatário e deixaria de "
                      "ser válida após a anonimização).")
    if categorias["midia"]:
        avisos.append(f"{categorias['midia']} áudio(s) ou vídeo(s) incorporado(s) removido(s) sem análise (podem "
                      "conter voz ou imagem de pessoas); a imagem de capa permanece.")
    if categorias["macros"]:
        avisos.append("Macros e personalizações removidas.")
    if locais:
        avisos.append(f"{locais} referência(s) a arquivos locais removida(s) (o caminho pode conter o nome do "
                      "usuário ou do servidor).")
    if orfas:
        avisos.append(f"{orfas} parte(s) interna(s) sem referência no documento descartada(s).")
    avisos += aviso_imagens(len(imagens), tarjadas, ocr)
    if metarquivos:
        avisos.append(f"Texto de {len(metarquivos)} imagem(ns) vetorial(is) (EMF/WMF, como tabelas coladas do "
                      "Excel) analisado; trechos tarjados foram mascarados na própria imagem.")
    if ilegiveis:
        avisos.append(f"{ilegiveis} imagem(ns) vetorial(is) com texto em glifos que não pode ser lido: revise-a(s) "
                      "manualmente.")

    if verificar:
        sobras = verificar_ausencia(texto_de_pacote(saida), valores_tarjados(resultados),
                                    valores_protegidos(resultados, anon.permitir))
        if sobras:
            raise VazamentoDetectado(f"{len(sobras)} trecho(s) tarjado(s) ainda presente(s) no {formato.upper()} "
                                     "gerado.")
        if imagens_com_metadados(saida):
            raise VazamentoDetectado(f"Imagem com metadados (EXIF, GPS ou XMP) no {formato.upper()} gerado.")
    return ResultadoArquivo(saida, formato, nome, resultados, avisos)
