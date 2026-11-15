"""Anonimização de PDF com remoção efetiva do conteúdo tarjado.

Desenhar retângulos pretos sobre o texto não basta: o texto continua no arquivo e pode ser
selecionado, copiado ou extraído. Este módulo segue o processo abaixo.

1. **Incorporação de anotações.** Campos de formulário preenchidos, carimbos de assinatura e caixas
   de texto livre visíveis são incorporados ao conteúdo da página (pikepdf), para que sejam
   analisados como o restante do texto.
2. **Extração com posição.** O texto de cada página é extraído com a caixa de cada caractere
   (pdfplumber). Texto horizontal e texto girado — como as notas de margem verticais comuns em
   documentos assinados digitalmente — são lidos separadamente, no sentido correto de leitura.
3. **OCR quando necessário.** Páginas digitalizadas, imagens grandes dentro de páginas com texto e
   páginas cujas fontes não permitem decodificar o texto (glifos sem mapeamento Unicode) passam por
   OCR local.
4. **Análise.** Todas as partes do documento são analisadas em lote como um único documento, de modo
   que um valor tarjado em uma página seja tarjado em todas.
5. **Rasterização das páginas com tarja.** Essas páginas são renderizadas como imagem (pypdfium2), as
   tarjas são aplicadas sobre os pixels e uma camada de texto invisível é recriada apenas com as
   palavras não tarjadas — o documento continua pesquisável e acessível. Páginas sem tarja são
   copiadas sem alteração.
6. **Reescrita e saneamento.** O arquivo é reescrito integralmente (pikepdf), sem metadados
   (Info/XMP), anotações remanescentes (comentários, campos ocultos, links), anexos, JavaScript,
   marcadores, miniaturas, estrutura de tags, dados de validação de assinatura (DSS) nem
   atualizações incrementais.
7. **Verificação independente.** O arquivo gerado é relido por dois extratores de texto (pdfplumber e
   PDFium) e todas as suas cadeias de caracteres e fluxos de metadados são inspecionados. Se qualquer
   valor tarjado continuar legível, a operação falha e nenhum arquivo é entregue.

Todas as bibliotecas usadas têm licença compatível com MIT.
"""

from __future__ import annotations

import io
import unicodedata
from dataclasses import dataclass, field

from ..motor import Anonimizador, Resultado
from . import ArquivoInvalido, FalhaOCR, ResultadoArquivo, VazamentoDetectado
from .verificacao import valores_protegidos, valores_tarjados, verificar_ausencia

#: Resolução de renderização das páginas rasterizadas (pontos por polegada).
DPI = 200

#: Limite de pixels por página renderizada; páginas maiores são renderizadas em escala menor.
MAX_PIXELS = 40_000_000

#: Fração da área da página ocupada por imagens a partir da qual a página passa por OCR mesmo tendo
#: camada de texto (ex.: documento de identidade digitalizado anexado a um despacho).
LIMIAR_AREA_IMAGEM = 0.15

#: Fração de caracteres não decodificáveis a partir da qual a camada de texto da página é
#: considerada não confiável e a página passa por OCR.
LIMIAR_TEXTO_ILEGIVEL = 0.10

#: Número de curvas a partir do qual uma página sem camada de texto passa por OCR. Texto convertido
#: em contornos (comum em PDFs gerados por programas de desenho e em alguns carimbos de assinatura)
#: não tem caracteres extraíveis, mas é lido pelo OCR na página renderizada.
LIMIAR_CURVAS = 40

#: Caixa delimitadora em pontos, com origem no canto superior esquerdo: (x0, topo, x1, base).
Caixa = tuple[float, float, float, float]

#: Palavra com sua caixa e, quando disponível, a caixa de cada caractere.
Palavra = tuple[str, Caixa, list[Caixa] | None]


@dataclass
class Segmento:
    """Texto de uma fonte da página (camada de texto ou OCR) e a caixa de cada caractere.

    Attributes:
        texto: Texto montado em ordem de leitura.
        caixas: Caixa de cada caractere de ``texto``; ``None`` para espaços e quebras inseridos.
        palavras: Palavras e suas caixas, usadas para recriar a camada de texto invisível.
        origem: ``texto``, ``texto-vertical`` ou ``ocr``.
    """

    texto: str
    caixas: list[Caixa | None]
    palavras: list[tuple[str, Caixa]]
    origem: str = "texto"


@dataclass
class Pagina:
    """Estado de uma página durante o processamento.

    Attributes:
        indice: Posição da página no documento (a partir de 0).
        largura: Largura em pontos (caixa visível da página).
        altura: Altura em pontos.
        rotacao: Rotação declarada na página (``/Rotate``), em graus.
        segmentos: Fontes de texto da página.
        tarjas: Regiões a cobrir.
        rotulos: Texto a escrever dentro de cada tarja (etiqueta ou pseudônimo).
        imagem_area: Fração da área ocupada por imagens.
        imagens_nao_analisadas: Indica imagens que não passaram por OCR.
    """

    indice: int
    largura: float
    altura: float
    rotacao: int
    segmentos: list[Segmento] = field(default_factory=list)
    tarjas: list[Caixa] = field(default_factory=list)
    rotulos: list[tuple[Caixa, str]] = field(default_factory=list)
    imagem_area: float = 0.0
    imagens_nao_analisadas: bool = False


# ---------------------------------------------------------------------------- montagem do texto
def _montar_segmento(palavras: list[Palavra], origem: str) -> Segmento:
    """Ordena palavras horizontais em linhas e monta o texto com o mapa caractere → caixa."""
    palavras = sorted(palavras, key=lambda p: (round(p[1][1] / 3), p[1][0]))
    linhas: list[list[Palavra]] = []
    for p in palavras:
        altura = max(1.0, p[1][3] - p[1][1])
        if linhas and abs(linhas[-1][0][1][1] - p[1][1]) <= max(2.0, altura * 0.5):
            linhas[-1].append(p)
        else:
            linhas.append([p])
    return _segmento_de_linhas([sorted(lin, key=lambda p: p[1][0])
                                for lin in sorted(linhas, key=lambda lin: lin[0][1][1])], origem)


def _segmento_de_linhas(linhas: list[list[Palavra]], origem: str) -> Segmento:
    """Concatena linhas já ordenadas: palavras separadas por espaço, linhas por quebra de linha."""
    texto: list[str] = []
    caixas: list[Caixa | None] = []
    lista: list[tuple[str, Caixa]] = []
    for li, linha in enumerate(linhas):
        if li:
            texto.append("\n")
            caixas.append(None)
        for wi, (t, caixa, chars) in enumerate(linha):
            if wi:
                texto.append(" ")
                caixas.append(None)
            texto.append(t)
            caixas.extend(chars if chars and len(chars) == len(t) else [caixa] * len(t))
            lista.append((t, caixa))
    return Segmento("".join(texto), caixas, lista, origem)


def _linhas_verticais(chars: list[dict], x_off: float, y_off: float) -> list[list[Palavra]]:
    """Reconstrói o texto girado (não horizontal) na ordem correta de leitura.

    O sentido de leitura vem da matriz de transformação de cada caractere: componente vertical
    positiva no espaço do PDF (eixo y para cima) indica leitura de baixo para cima (rotação de 90°);
    negativa, de cima para baixo (rotação de −90°). Os caracteres são agrupados em colunas pelo
    centro horizontal e, em cada coluna, divididos em palavras por espaços ou intervalos.
    """
    por_sentido: dict[bool, list[dict]] = {True: [], False: []}
    for ch in chars:
        if ch.get("upright", True):
            continue
        matriz = ch.get("matrix") or (1, 0, 0, 1, 0, 0)
        por_sentido[matriz[1] > 0].append(ch)
    linhas: list[list[Palavra]] = []
    for de_baixo_para_cima, lista in por_sentido.items():
        colunas: list[list[dict]] = []
        for ch in sorted(lista, key=lambda c: (c["x0"] + c["x1"]) / 2):
            centro = (ch["x0"] + ch["x1"]) / 2
            if colunas and abs((colunas[-1][-1]["x0"] + colunas[-1][-1]["x1"]) / 2 - centro) <= 2.0:
                colunas[-1].append(ch)
            else:
                colunas.append([ch])
        for coluna in colunas:
            coluna.sort(key=lambda c: c["top"], reverse=de_baixo_para_cima)
            palavras = [_palavra_vertical(grupo, x_off, y_off) for grupo in _grupos_de_palavra(coluna, de_baixo_para_cima)]
            if palavras:
                linhas.append(palavras)
    return linhas


def _grupos_de_palavra(coluna: list[dict], de_baixo_para_cima: bool) -> list[list[dict]]:
    """Divide uma coluna de caracteres, já em ordem de leitura, em palavras.

    Uma palavra termina em um caractere de espaço ou quando o intervalo até o caractere seguinte
    excede 30% do tamanho da fonte.
    """
    grupos: list[list[dict]] = []
    atual: list[dict] = []
    for ch in coluna:
        if not ch["text"].strip():
            if atual:
                grupos.append(atual)
            atual = []
            continue
        if atual:
            anterior = atual[-1]
            intervalo = (anterior["top"] - ch["bottom"]) if de_baixo_para_cima else (ch["top"] - anterior["bottom"])
            if intervalo > max(1.0, 0.3 * float(ch.get("size") or 10)):
                grupos.append(atual)
                atual = []
        atual.append(ch)
    if atual:
        grupos.append(atual)
    return grupos


def _palavra_vertical(grupo: list[dict], x_off: float, y_off: float) -> Palavra:
    """Palavra com a caixa de cada caractere e a caixa que as envolve."""
    caixas = [(c["x0"] - x_off, c["top"] - y_off, c["x1"] - x_off, c["bottom"] - y_off) for c in grupo]
    uniao = (min(c[0] for c in caixas), min(c[1] for c in caixas), max(c[2] for c in caixas),
             max(c[3] for c in caixas))
    return "".join(c["text"] for c in grupo), uniao, caixas


def _proporcao_ilegivel(chars: list[dict]) -> float:
    """Fração de caracteres sem mapeamento Unicode (``(cid:N)``, caractere de substituição, área privada)."""
    if not chars:
        return 0.0
    ruins = 0
    for ch in chars:
        t = ch.get("text") or ""
        if t.startswith("(cid:") or "�" in t or any(unicodedata.category(c) in ("Co", "Cn") for c in t):
            ruins += 1
    return ruins / len(chars)


# ---------------------------------------------------------------------------- geometria
def _uniao_por_linha(caixas: list[Caixa], folga: float = 1.0, *, vertical: bool = False) -> list[Caixa]:
    """Une caixas de caracteres em uma caixa por linha, com margem de ``folga`` pontos.

    A tarja contínua não revela o tamanho de cada palavra. Com ``vertical``, a união é feita por
    coluna (texto girado), transpondo os eixos.
    """
    if vertical:
        transpostas = _uniao_por_linha([(c[1], c[0], c[3], c[2]) for c in caixas], folga)
        return [(c[1], c[0], c[3], c[2]) for c in transpostas]
    linhas: list[list[Caixa]] = []
    for c in sorted(caixas, key=lambda c: (c[1], c[0])):
        if linhas and abs(linhas[-1][-1][1] - c[1]) <= max(2.0, (c[3] - c[1]) * 0.5) and c[0] - linhas[-1][-1][2] < 30:
            linhas[-1].append(c)
        else:
            linhas.append([c])
    return [(min(c[0] for c in lin) - folga, min(c[1] for c in lin) - folga,
             max(c[2] for c in lin) + folga, max(c[3] for c in lin) + folga) for lin in linhas]


def _intersecta(a: Caixa, b: Caixa) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# ---------------------------------------------------------------------------- extração
def _extrair(pdf_bytes: bytes, limite_paginas: int, ocr: bool, avisos: list[str]) -> list[Pagina]:
    """Extrai o texto de todas as páginas, com OCR onde a camada de texto não é suficiente."""
    import pdfplumber
    import pypdfium2 as pdfium

    from . import ocr as mod_ocr

    paginas: list[Pagina] = []
    try:
        plumb = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as erro:
        raise ArquivoInvalido("PDF inválido, corrompido ou protegido por senha.") from erro
    ocr_ativo = ocr and mod_ocr.ocr_disponivel()
    sem_ocr: list[int] = []
    sem_texto: list[int] = []
    ilegiveis: list[int] = []
    with plumb:
        if len(plumb.pages) > limite_paginas:
            raise ArquivoInvalido(f"PDF com {len(plumb.pages)} páginas excede o limite de {limite_paginas}.")
        doc_pdfium = None
        for i, page in enumerate(plumb.pages):
            x_off, y_off = page.bbox[0], page.bbox[1]
            pag = Pagina(i, float(page.width), float(page.height), int(page.rotation or 0) % 360)
            chars = page.chars
            horizontais = page.filter(lambda o: o.get("object_type") != "char" or o.get("upright", True))
            palavras: list[Palavra] = []
            for w in horizontais.extract_words(keep_blank_chars=False, use_text_flow=False, return_chars=True,
                                               x_tolerance=1.5, y_tolerance=2):
                caixa = (w["x0"] - x_off, w["top"] - y_off, w["x1"] - x_off, w["bottom"] - y_off)
                cxs = [(c["x0"] - x_off, c["top"] - y_off, c["x1"] - x_off, c["bottom"] - y_off)
                       for c in w.get("chars", [])]
                palavras.append((w["text"], caixa, cxs))
            if palavras:
                pag.segmentos.append(_montar_segmento(palavras, "texto"))
            verticais = _linhas_verticais(chars, x_off, y_off)
            if verticais:
                pag.segmentos.append(_segmento_de_linhas(verticais, "texto-vertical"))

            area = sum(abs((im["x1"] - im["x0"]) * (im["bottom"] - im["top"])) for im in page.images)
            pag.imagem_area = area / max(1.0, pag.largura * pag.altura)
            n_chars = sum(len(s.texto.strip()) for s in pag.segmentos)
            texto_ilegivel = len(chars) >= 5 and _proporcao_ilegivel(chars) > LIMIAR_TEXTO_ILEGIVEL
            vetorial = n_chars < 25 and len(page.curves) >= LIMIAR_CURVAS
            precisa_ocr = (pag.imagem_area > LIMIAR_AREA_IMAGEM or (n_chars < 25 and page.images) or texto_ilegivel
                           or vetorial)
            if texto_ilegivel:
                ilegiveis.append(i + 1)
            if precisa_ocr and ocr and not ocr_ativo:
                # Sem OCR, a página seria entregue sem análise. Só quem desativa o OCR explicitamente
                # aceita esse risco (e recebe o aviso abaixo).
                raise FalhaOCR("O PDF tem páginas digitalizadas, imagens ou texto em contornos, que exigem OCR: instale o "
                               "Tesseract (idioma 'por') ou 'pip install themis-lgpd[ocr]', ou desative o OCR "
                               "para processar sem analisá-las.")
            if precisa_ocr and ocr_ativo:
                doc_pdfium = doc_pdfium or pdfium.PdfDocument(pdf_bytes)
                img, escala = _renderizar(doc_pdfium, i, pag)
                ocr_palavras: list[Palavra] = [
                    (p.texto, (p.x0 / escala, p.topo / escala, p.x1 / escala, p.base / escala),
                     [tuple(v / escala for v in c) for c in p.chars] if p.chars else None)
                    for p in mod_ocr.reconhecer(img)
                ]
                if not texto_ilegivel:
                    # Descarta o que a camada de texto já cobre, para não analisar duas vezes.
                    existentes = [c for s in pag.segmentos for _, c in s.palavras]
                    ocr_palavras = [p for p in ocr_palavras if not any(_intersecta(p[1], e) for e in existentes)]
                if ocr_palavras:
                    pag.segmentos.append(_montar_segmento(ocr_palavras, "ocr"))
                elif n_chars < 25:
                    sem_texto.append(i + 1)
            elif precisa_ocr:
                sem_ocr.append(i + 1)
            elif page.images:
                pag.imagens_nao_analisadas = True
            paginas.append(pag)
        if doc_pdfium is not None:
            doc_pdfium.close()
    if sem_ocr:
        avisos.append("Páginas digitalizadas, com imagens grandes, texto em contornos ou texto não decodificável "
                      "NÃO analisadas (OCR desativado): " + _lista_paginas(sem_ocr) + ". Revise-as manualmente.")
    if sem_texto:
        avisos.append("Páginas sem camada de texto em que o OCR não reconheceu texto (manuscritos, baixa resolução, "
                      "desenhos ou páginas em branco): " + _lista_paginas(sem_texto) + ". Revise-as manualmente.")
    if ilegiveis and ocr_ativo:
        avisos.append("Páginas com fontes sem mapeamento de texto foram analisadas por OCR: "
                      + _lista_paginas(ilegiveis) + ".")
    pequenas = [p.indice + 1 for p in paginas if p.imagens_nao_analisadas]
    if pequenas:
        avisos.append("Páginas com imagens pequenas não analisadas por OCR (assinaturas digitalizadas, fotos, "
                      "carimbos podem conter dados pessoais): " + _lista_paginas(pequenas) + ".")
    return paginas


def _lista_paginas(numeros: list[int]) -> str:
    return ", ".join(map(str, numeros[:30])) + (" …" if len(numeros) > 30 else "")


def _renderizar(doc_pdfium, indice: int, pag: Pagina):
    """Renderiza a página sem a rotação declarada, no mesmo sistema de coordenadas do pdfplumber."""
    page = doc_pdfium[indice]
    if pag.rotacao:
        page.set_rotation(0)
    escala = DPI / 72
    if pag.largura * pag.altura * escala * escala > MAX_PIXELS:
        escala = (MAX_PIXELS / (pag.largura * pag.altura)) ** 0.5
    img = page.render(scale=escala, may_draw_forms=True).to_pil().convert("RGB")
    page.close()
    return img, escala


# ---------------------------------------------------------------------------- composição
def _desenhar(img, pag: Pagina, escala: float):
    """Aplica as tarjas sobre a imagem e escreve o rótulo de cada uma quando houver espaço."""
    from PIL import ImageDraw, ImageFont

    desenho = ImageDraw.Draw(img)
    for x0, y0, x1, y1 in pag.tarjas:
        desenho.rectangle([x0 * escala, y0 * escala, x1 * escala, y1 * escala], fill=(0, 0, 0))
    for (x0, y0, x1, y1), rotulo in pag.rotulos:
        # A fonte embutida do Pillow não tem caracteres acentuados.
        rotulo = "".join(c for c in unicodedata.normalize("NFD", rotulo) if not unicodedata.combining(c))
        alt = (y1 - y0) * escala
        if alt < 8:
            continue
        try:
            fonte = ImageFont.load_default(size=max(8, int(alt * 0.62)))
        except TypeError:  # Pillow anterior à 10.1
            fonte = ImageFont.load_default()
        if desenho.textlength(rotulo, font=fonte) <= (x1 - x0) * escala:
            desenho.text((x0 * escala + 1, y0 * escala + alt * 0.12), rotulo, fill=(255, 255, 255), font=fonte)
    return img


def _pagina_rasterizada(img, pag: Pagina) -> bytes:
    """Gera um PDF de uma página: a imagem tarjada e a camada de texto invisível das palavras restantes."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(pag.largura, pag.altura), invariant=True, pageCompression=1)
    c.drawImage(ImageReader(img), 0, 0, width=pag.largura, height=pag.altura)
    texto = c.beginText()
    texto.setTextRenderMode(3)  # texto invisível: serve à busca, à seleção e a leitores de tela
    for seg in pag.segmentos:
        if seg.origem == "texto-vertical":
            continue  # texto girado não é recriado na camada invisível
        for palavra, caixa in seg.palavras:
            if any(_intersecta(caixa, t) for t in pag.tarjas):
                continue
            seguro = palavra.encode("cp1252", "replace").decode("cp1252")
            tam = max(1.0, (caixa[3] - caixa[1]) * 0.85)
            largura = stringWidth(seguro, "Helvetica", tam) or 1.0
            texto.setFont("Helvetica", tam)
            texto.setHorizScale(max(10.0, min(400.0, 100.0 * (caixa[2] - caixa[0]) / largura)))
            texto.setTextOrigin(caixa[0], pag.altura - caixa[3] + (caixa[3] - caixa[1]) * 0.2)
            texto.textOut(seguro)
    c.drawText(texto)
    c.showPage()
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------- saneamento
# Entradas do catálogo que podem conter dados pessoais ou executar ações ao abrir o arquivo.
_CHAVES_RAIZ = ("/Metadata", "/Names", "/OpenAction", "/AA", "/AcroForm", "/Outlines", "/StructTreeRoot",
                "/MarkInfo", "/PieceInfo", "/Threads", "/SpiderInfo", "/URI", "/Perms", "/Collection", "/Dests",
                "/OCProperties", "/Legal", "/AF", "/DSS")
# Entradas de página com o mesmo risco (anotações e comentários, miniaturas, ações, metadados).
_CHAVES_PAGINA = ("/Annots", "/AA", "/Thumb", "/PieceInfo", "/Metadata", "/B", "/StructParents", "/AF")


def _preparar(dados: bytes, avisos: list[str]) -> bytes:
    """Incorpora ao conteúdo das páginas os campos de formulário e as anotações visíveis.

    Valores preenchidos em formulários, carimbos de assinatura e caixas de texto livre ficam em
    anotações, fora do fluxo de conteúdo da página; os extratores de texto não os leem. Ao
    incorporá-los antes da extração, eles passam a ser analisados e tarjados como o restante da
    página. O que não é visível (comentários, campos ocultos, anexos) é removido mais adiante, no
    saneamento, sem ser incorporado.

    Returns:
        O PDF com as anotações visíveis incorporadas, ou ``dados`` sem alteração quando não há
        anotações.

    Raises:
        ArquivoInvalido: PDF protegido por senha ou ilegível.
    """
    import pikepdf

    try:
        pdf = pikepdf.open(io.BytesIO(dados))
    except pikepdf.PasswordError as erro:
        raise ArquivoInvalido("PDF protegido por senha.") from erro
    except Exception as erro:
        raise ArquivoInvalido("PDF inválido ou corrompido.") from erro
    with pdf:
        nomes = pdf.Root.get("/Names")
        if nomes is not None and "/EmbeddedFiles" in nomes:
            avisos.append("O PDF tinha arquivo(s) anexado(s), removido(s) sem análise.")
        anotacoes = [a for p in pdf.pages for a in p.obj.get("/Annots", [])]
        if not anotacoes:
            return dados
        if any(a.get("/Subtype") == "/FileAttachment" for a in anotacoes):
            avisos.append("O PDF tinha arquivo(s) anexado(s) a anotações, removido(s) sem análise.")
        try:
            if "/AcroForm" in pdf.Root:
                pdf.generate_appearance_streams()
            pdf.flatten_annotations(mode="screen")
            buf = io.BytesIO()
            pdf.save(buf)
        except Exception:  # noqa: BLE001 - anotação malformada: segue sem incorporar, com aviso
            avisos.append("Não foi possível incorporar os campos de formulário e anotações ao conteúdo das "
                          "páginas; eles foram removidos sem análise.")
            return dados
    avisos.append("Campos de formulário e anotações visíveis foram incorporados às páginas e analisados; "
                  "comentários e campos ocultos foram removidos.")
    return buf.getvalue()


def _sanear(pdf) -> None:
    """Remove do documento tudo o que não é conteúdo visível das páginas.

    Além do catálogo e das páginas, metadados XMP e dados privados de aplicativos são removidos de
    todos os objetos: imagens e formulários incorporados podem ter metadados próprios (o XMP de uma
    foto costuma registrar o nome do autor).
    """
    import pikepdf

    if "/Info" in pdf.trailer:
        del pdf.trailer["/Info"]
    raiz = pdf.Root
    for chave in _CHAVES_RAIZ:
        if chave in raiz:
            del raiz[chave]
    for page in pdf.pages:
        for chave in _CHAVES_PAGINA:
            if chave in page.obj:
                del page.obj[chave]
    for obj in pdf.objects:
        if isinstance(obj, pikepdf.Dictionary | pikepdf.Stream):
            for chave in ("/Metadata", "/PieceInfo"):
                if chave in obj:
                    del obj[chave]
    pdf.remove_unreferenced_resources()


# ---------------------------------------------------------------------------- verificação
def _texto_extraido(pdf_bytes: bytes) -> str:
    """Texto do PDF gerado, extraído por dois mecanismos independentes (pdfplumber e PDFium)."""
    import pdfplumber
    import pypdfium2 as pdfium

    partes = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as p:
        partes += [pg.extract_text() or "" for pg in p.pages]
        partes.append(str(p.metadata))
    doc = pdfium.PdfDocument(pdf_bytes)
    for pg in doc:
        tp = pg.get_textpage()
        partes.append(tp.get_text_range())
        tp.close()
        pg.close()
    doc.close()
    return "\n".join(partes)


def _texto_estrutural(pdf_bytes: bytes) -> str:
    """Cadeias de caracteres de todos os objetos e conteúdo de fluxos de metadados/anexos.

    Cobre o que os extratores de texto não leem: dicionários de informação, anotações, campos,
    marcadores, metadados XMP e arquivos incorporados. Fluxos de conteúdo de página e de imagem
    ficam de fora (o conteúdo de página já é verificado por :func:`_texto_extraido`).
    """
    import pikepdf

    partes: list[str] = []
    vistos: set[tuple[int, int]] = set()

    def visitar(obj, profundidade: int = 0) -> None:
        if profundidade > 50:
            return
        if isinstance(obj, pikepdf.Object) and obj.is_indirect:
            chave = obj.objgen
            if chave in vistos:
                return
            vistos.add(chave)
        if isinstance(obj, pikepdf.String):
            partes.append(str(obj))
        elif isinstance(obj, pikepdf.Array):
            for item in obj:
                visitar(item, profundidade + 1)
        elif isinstance(obj, pikepdf.Stream):
            dic = obj.stream_dict
            for valor in dic.values():
                visitar(valor, profundidade + 1)
            if dic.get("/Type") in ("/Metadata", "/EmbeddedFile") or dic.get("/Subtype") == "/XML":
                try:
                    partes.append(obj.read_bytes().decode("utf-8", errors="ignore"))
                except pikepdf.PdfError as erro:
                    raise VazamentoDetectado("Não foi possível verificar um fluxo de metadados do PDF gerado.") from erro
        elif isinstance(obj, pikepdf.Dictionary):
            for valor in obj.values():
                visitar(valor, profundidade + 1)

    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        visitar(pdf.trailer)
        for obj in pdf.objects:
            visitar(obj)
    return "\n".join(partes)


# ---------------------------------------------------------------------------- ponto de entrada
def anonimizar_pdf(dados: bytes, anon: Anonimizador, nome: str, *, limite_paginas: int = 500, ocr: bool = True,
                   verificar: bool = True) -> ResultadoArquivo:
    """Anonimiza um PDF.

    Args:
        dados: Conteúdo do arquivo.
        anon: Anonimizador configurado (perfil, modo, listas).
        nome: Nome do arquivo de saída.
        limite_paginas: Número máximo de páginas aceito.
        ocr: Permite OCR em páginas digitalizadas e imagens.
        verificar: Executa a verificação independente do arquivo gerado.

    Returns:
        O PDF anonimizado, os resultados por segmento de texto e os avisos ao usuário.

    Raises:
        ArquivoInvalido: PDF corrompido, protegido por senha ou acima dos limites.
        FalhaOCR: O PDF exige OCR e nenhum mecanismo está disponível, ou o OCR falhou.
        VazamentoDetectado: A verificação encontrou valor tarjado legível no arquivo gerado.
    """
    try:
        import pikepdf
        import pypdfium2 as pdfium
    except ImportError as erro:  # pragma: no cover - dependência opcional
        raise ArquivoInvalido("Suporte a PDF requer: pip install 'themis-lgpd[arquivos]'") from erro

    avisos: list[str] = []
    dados = _preparar(dados, avisos)
    paginas = _extrair(dados, limite_paginas, ocr, avisos)
    segmentos = [(pag, seg) for pag in paginas for seg in pag.segmentos]
    resultados: list[Resultado] = anon.anonimizar_lote([seg.texto for _, seg in segmentos], mesmo_documento=True)
    for (pag, seg), r in zip(segmentos, resultados):
        for s in r.substituicoes:
            caixas = [seg.caixas[k] for k in range(s["inicio"], min(s["fim"], len(seg.caixas))) if seg.caixas[k]]
            # Caixas de OCR são estimadas a partir dos pixels: margem maior contra imprecisão.
            folga = 2.0 if seg.origem == "ocr" else 1.0
            for caixa in _uniao_por_linha(caixas, folga, vertical=seg.origem == "texto-vertical"):
                pag.tarjas.append(caixa)
                if anon.modo != "tarja" and seg.origem != "texto-vertical":
                    pag.rotulos.append((caixa, s["substituto"]))

    try:
        origem = pikepdf.open(io.BytesIO(dados))
    except pikepdf.PasswordError as erro:
        raise ArquivoInvalido("PDF protegido por senha.") from erro
    except Exception as erro:
        raise ArquivoInvalido("PDF inválido ou corrompido.") from erro
    saida = pikepdf.new()
    doc_pdfium = pdfium.PdfDocument(dados)
    rasterizadas = 0
    with origem:
        for pag in paginas:
            if pag.tarjas:
                img, escala = _renderizar(doc_pdfium, pag.indice, pag)
                _desenhar(img, pag, escala)
                nova = pikepdf.open(io.BytesIO(_pagina_rasterizada(img, pag)))
                saida.pages.append(nova.pages[0])
                if pag.rotacao:
                    saida.pages[-1].obj["/Rotate"] = pag.rotacao
                rasterizadas += 1
            else:
                saida.pages.append(origem.pages[pag.indice])
        doc_pdfium.close()
        _sanear(saida)
        buf = io.BytesIO()
        saida.save(buf, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate,
                   fix_metadata_version=False, deterministic_id=True)
    pdf_final = buf.getvalue()
    if verificar:
        sobras = verificar_ausencia(_texto_extraido(pdf_final) + "\n" + _texto_estrutural(pdf_final),
                                    valores_tarjados(resultados), valores_protegidos(resultados, anon.permitir))
        if sobras:
            raise VazamentoDetectado(f"{len(sobras)} trecho(s) tarjado(s) ainda legível(is) no PDF gerado.")
    if rasterizadas:
        avisos.append(f"{rasterizadas} página(s) com tarja foram convertidas em imagem com camada de texto "
                      "pesquisável (garante que o conteúdo tarjado não possa ser recuperado).")
    return ResultadoArquivo(pdf_final, "pdf", nome, resultados, avisos)
