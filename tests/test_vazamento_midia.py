"""Regressão de vazamentos por imagens, QR codes, metarquivos e conteúdo oculto de PDF.

Cada teste insere um dado pessoal em um ponto que a revisão visual não enxerga — metadados de foto,
QR code, texto de imagem incorporada, metarquivo, SVG, conteúdo marcado de PDF — e confirma que ele
não sobrevive no arquivo gerado. Os testes de falha fechada desativam uma proteção e confirmam que a
verificação final bloqueia a entrega.
"""

import io
import struct
import zipfile

import pytest

from apoio.metarquivos import emf, wmf
from themis_lgpd import Anonimizador
from themis_lgpd.formatos import ArquivoInvalido, VazamentoDetectado, anonimizar_arquivo, detectar_formato
from themis_lgpd.formatos.midia import limpar_imagem, metadados_restantes

PIX = ("00020126580014BR.GOV.BCB.PIX0136123e4567-e12b-12d1-a456-4266554400005204000053039865802BR"
       "5918JOANA PEREIRA LIMA6008BRASILIA62070503***6304ABCD")
XMP = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><dc:creator>Joana Pereira Lima</dc:creator></x:xmpmeta>'


def _ocr_disponivel() -> bool:
    from themis_lgpd.formatos.ocr import ocr_disponivel

    return ocr_disponivel()


requer_ocr = pytest.mark.skipif(not _ocr_disponivel(), reason="OCR indisponível")


def _exif():
    from PIL import Image

    exif = Image.Exif()
    exif[0x013B] = "Joana Pereira Lima"  # Artist
    exif[0x8825] = {1: "S", 2: (15.0, 47.0, 30.0), 3: "W", 4: (47.0, 52.0, 10.0)}  # GPSInfo
    return exif


def _foto(formato: str = "JPEG") -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (120, 90), (90, 140, 200)).save(buf, formato, exif=_exif(), xmp=XMP)
    return buf.getvalue()


def _figura(linhas: list[str], qr: str | None = None) -> bytes:
    import segno
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1100, 420), "white")
    desenho = ImageDraw.Draw(img)
    for k, linha in enumerate(linhas):
        desenho.text((30, 30 + 60 * k), linha, fill="black", font_size=38)
    if qr:
        buf = io.BytesIO()
        segno.make(qr, error="m").save(buf, kind="png", scale=3, border=4)
        from PIL import Image as Img

        img.paste(Img.open(buf).convert("RGB"), (800, 150))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _bytes_do_pacote(dados: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        return b"".join(z.read(n) for n in z.namelist())


# ---------------------------------------------------------------------------- metadados de imagens
@pytest.mark.parametrize("formato", ["JPEG", "PNG", "WEBP"])
def test_metadados_removidos_sem_alterar_os_pixels(formato):
    from PIL import Image

    original = _foto(formato)
    limpo = limpar_imagem(original)
    assert metadados_restantes(original) and not metadados_restantes(limpo)
    assert b"Joana" not in limpo and b"GPS" not in limpo
    antes, depois = Image.open(io.BytesIO(original)), Image.open(io.BytesIO(limpo))
    assert antes.convert("RGB").tobytes() == depois.convert("RGB").tobytes()


def test_jpeg_perde_video_anexado_e_comentario():
    original = _foto() + b"\x00\x00\x00\x18ftypmp42" + b"Joana" * 10
    limpo = limpar_imagem(original)
    assert limpo.endswith(b"\xff\xd9") and b"Joana" not in limpo


def test_docx_e_xlsx_sem_metadados_de_foto(anon):
    import docx
    import openpyxl
    from openpyxl.drawing.image import Image as ImagemPlanilha

    documento = docx.Document()
    documento.add_paragraph("Relatório de vistoria.")
    documento.add_picture(io.BytesIO(_foto()))
    buf = io.BytesIO()
    documento.save(buf)
    assert b"Joana" not in _bytes_do_pacote(anonimizar_arquivo(buf.getvalue(), "v.docx", anon).dados)

    pasta = openpyxl.Workbook()
    pasta.active["A1"] = "Vistoria"
    pasta.active.add_image(ImagemPlanilha(io.BytesIO(_foto())), "C3")
    buf = io.BytesIO()
    pasta.save(buf)
    assert b"Joana" not in _bytes_do_pacote(anonimizar_arquivo(buf.getvalue(), "v.xlsx", anon).dados)


def test_pdf_sem_metadados_dentro_do_jpeg(anon):
    import pikepdf
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    pagina = canvas.Canvas(buf)
    pagina.drawString(72, 780, "Foto da vistoria")
    pagina.drawImage(ImageReader(io.BytesIO(_foto())), 72, 600, 120, 90)
    pagina.showPage()
    pagina.save()
    r = anonimizar_arquivo(buf.getvalue(), "v.pdf", anon)
    with pikepdf.open(io.BytesIO(r.dados)) as pdf:
        imagens = [o.read_raw_bytes() for o in pdf.objects
                   if isinstance(o, pikepdf.Stream) and o.get("/Subtype") == "/Image"]
    assert imagens and not any(b"Exif" in i or b"Joana" in i for i in imagens)


def test_docx_falha_fechada_se_metadados_permanecem(anon, monkeypatch):
    import docx

    from themis_lgpd.formatos import docx as modulo_docx

    documento = docx.Document()
    documento.add_picture(io.BytesIO(_foto()))
    buf = io.BytesIO()
    documento.save(buf)
    monkeypatch.setattr(modulo_docx, "limpar_imagens", lambda partes, nomes: {})
    with pytest.raises(VazamentoDetectado):
        anonimizar_arquivo(buf.getvalue(), "v.docx", anon)


# ---------------------------------------------------------------------------- QR codes
def test_qr_pix_e_dado_pessoal_tarjados_url_publica_mantida(anon):
    import segno
    from PIL import Image

    from themis_lgpd.formatos.qr import localizar

    img = Image.new("RGB", (1300, 520), "white")
    for k, conteudo in enumerate([PIX, "https://www.gov.br/acessoainformacao", "Servidora Joana Pereira Lima"]):
        buf = io.BytesIO()
        segno.make(conteudo, error="m").save(buf, kind="png", scale=3, border=4)
        img.paste(Image.open(buf).convert("RGB"), (40 + 420 * k, 80))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    r = anonimizar_arquivo(buf.getvalue(), "boleto.png", anon)
    legiveis = [c.conteudo for c in localizar(Image.open(io.BytesIO(r.dados)))]
    assert legiveis == ["https://www.gov.br/acessoainformacao"]


def test_qr_pix_vetorial_em_pdf(anon):
    import pypdfium2 as pdfium
    import segno
    from reportlab.pdfgen import canvas

    from themis_lgpd.formatos.qr import localizar

    buf = io.BytesIO()
    pagina = canvas.Canvas(buf, pagesize=(595, 842))
    pagina.drawString(72, 780, "Guia de recolhimento - pague com PIX:")
    for y, linha in enumerate(segno.make(PIX, error="m").matrix):
        for x, modulo in enumerate(linha):
            if modulo:
                pagina.rect(72 + x * 2.2, 700 - y * 2.2, 2.2, 2.2, stroke=0, fill=1)
    pagina.showPage()
    pagina.save()
    r = anonimizar_arquivo(buf.getvalue(), "guia.pdf", anon)
    imagem = pdfium.PdfDocument(r.dados)[0].render(scale=200 / 72).to_pil()
    assert not any(c.pix for c in localizar(imagem))


# ---------------------------------------------------------------------------- imagens incorporadas
@requer_ocr
def test_texto_de_imagem_em_docx_e_tarjado_nos_pixels(anon):
    import docx
    from PIL import Image

    from themis_lgpd.formatos.ocr import reconhecer
    from themis_lgpd.formatos.qr import localizar

    documento = docx.Document()
    documento.add_paragraph("Segue copia do documento apresentado.")
    documento.add_picture(io.BytesIO(_figura(["Requerente: Joana Pereira Lima", "CPF 529.982.247-25"], qr=PIX)))
    buf = io.BytesIO()
    documento.save(buf)
    r = anonimizar_arquivo(buf.getvalue(), "a.docx", anon)
    with zipfile.ZipFile(io.BytesIO(r.dados)) as z:
        nome = next(n for n in z.namelist() if n.endswith(".png"))
        imagem = Image.open(io.BytesIO(z.read(nome))).convert("RGB")
    texto = " ".join(p.texto for p in reconhecer(imagem))
    assert "Joana" not in texto and "529" not in texto and not localizar(imagem)


@requer_ocr
def test_valor_tarjado_nas_celulas_e_propagado_para_imagem_da_planilha(anon):
    import openpyxl
    from openpyxl.drawing.image import Image as ImagemPlanilha
    from PIL import Image

    from themis_lgpd.formatos.ocr import reconhecer

    pasta = openpyxl.Workbook()
    pasta.active.append(["Nome", "Situacao"])
    pasta.active.append(["Heitor Vasconcelos Prado", "Deferido"])
    pasta.active.add_image(ImagemPlanilha(io.BytesIO(_figura(["Recibo emitido para", "Heitor Vasconcelos Prado"]))),
                           "D2")
    buf = io.BytesIO()
    pasta.save(buf)
    r = anonimizar_arquivo(buf.getvalue(), "a.xlsx", anon)
    with zipfile.ZipFile(io.BytesIO(r.dados)) as z:
        nome = next(n for n in z.namelist() if n.startswith("xl/media/"))
        texto = " ".join(p.texto for p in reconhecer(Image.open(io.BytesIO(z.read(nome))).convert("RGB")))
    assert "Vasconcelos" not in texto


def test_palavras_coladas_pelo_ocr_sao_separadas():
    from themis_lgpd.formatos.ocr import Palavra, _separar_coladas

    texto = "formuladoporJoanaPereiraLima"
    palavra = Palavra(texto, 0, 0, len(texto), 1, [(k, 0, k + 1, 1) for k in range(len(texto))])
    assert [p.texto for p in _separar_coladas(palavra)] == ["formuladopor", "Joana", "Pereira", "Lima"]


# ---------------------------------------------------------------------------- metarquivos e SVG
def _docx_com_midia(midias: dict[str, bytes], tipos: dict[str, str]) -> bytes:
    import docx

    documento = docx.Document()
    documento.add_paragraph("A requerente Joana Pereira Lima apresentou a tabela abaixo.")
    buf = io.BytesIO()
    documento.save(buf)
    entrada = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as z:
        for info in entrada.infolist():
            dados = entrada.read(info)
            if info.filename == "word/_rels/document.xml.rels":
                rels = "".join(f'<Relationship Id="rIdT{k}" Type="http://schemas.openxmlformats.org/officeDocument/'
                               f'2006/relationships/image" Target="media/{nome}"/>' for k, nome in enumerate(midias))
                dados = dados.replace(b"</Relationships>", rels.encode() + b"</Relationships>")
            if info.filename == "[Content_Types].xml":
                padroes = "".join(f'<Default Extension="{ext}" ContentType="{tipo}"/>' for ext, tipo in tipos.items())
                dados = dados.replace(b"<Default ", padroes.encode() + b"<Default ", 1)
            z.writestr(info, dados)
        for nome, conteudo in midias.items():
            z.writestr(f"word/media/{nome}", conteudo)
    return saida.getvalue()


def test_texto_de_emf_wmf_e_svg_em_docx(anon):
    from themis_lgpd.formatos.metarquivo import ler

    svg = ('<?xml version="1.0"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
           '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg xmlns="http://www.w3.org/2000/svg" '
           'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" inkscape:label="Assinatura de Carlos '
           'Alberto Nogueira"><text x="1" y="2">CPF 529.982.247-25</text><desc>Carlos Alberto Nogueira</desc></svg>')
    dados = _docx_com_midia(
        {"tabela_Joana_Lima.emf": emf(["Nome", "Joana Pereira Lima", "CPF 529.982.247-25"], emfplus="Joana Pereira Lima"),
         "anexo.wmf": wmf(["Joana Pereira Lima"]), "assinatura.svg": svg.encode()},
        {"emf": "image/x-emf", "wmf": "image/x-wmf", "svg": "image/svg+xml"})
    r = anonimizar_arquivo(dados, "t.docx", anon)
    with zipfile.ZipFile(io.BytesIO(r.dados)) as z:
        nomes = z.namelist()
        textos = [ler(z.read(n)).texto for n in nomes if n.endswith((".emf", ".wmf"))]
        svg_saida = next(z.read(n) for n in nomes if n.endswith(".svg")).decode()
    assert not any("Joana" in t or "529" in t for t in textos)
    assert "Nogueira" not in svg_saida and "529" not in svg_saida
    assert not any("Joana" in n or "Lima" in n for n in nomes)  # nomes de mídia neutros


def test_identificadores_de_revisao_do_word_removidos(anon):
    import docx

    documento = docx.Document()
    documento.add_paragraph("Texto qualquer.")
    buf = io.BytesIO()
    documento.save(buf)
    entrada = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as z:
        for info in entrada.infolist():
            dados = entrada.read(info)
            if info.filename == "word/document.xml":
                dados = dados.replace(b"<w:p>", b'<w:p w:rsidR="00A1B2C3" w:rsidRDefault="00A1B2C3">', 1)
            z.writestr(info, dados)
    r = anonimizar_arquivo(saida.getvalue(), "a.docx", anon)
    assert b"rsid" not in _bytes_do_pacote(r.dados)


# ---------------------------------------------------------------------------- PDF: conteúdo oculto
def test_pdf_texto_alternativo_e_nome_de_camada_em_pagina_sem_tarja(anon):
    import pikepdf
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    pagina = canvas.Canvas(buf, pagesize=(595, 842))
    pagina.drawString(72, 780, "Pagina sem dados pessoais visiveis.")
    pagina.showPage()
    pagina.drawString(72, 780, "Requerente: Joana Pereira Lima, CPF 529.982.247-25.")
    pagina.showPage()
    pagina.save()
    pdf = pikepdf.open(io.BytesIO(buf.getvalue()))
    primeira = pdf.pages[0]
    camada = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.OCG,
                                                  Name=pikepdf.String("Assinatura de Joana Pereira Lima")))
    primeira.Resources.Properties = pikepdf.Dictionary(
        MC0=camada, MC1=pikepdf.Dictionary(Alt=pikepdf.String("Foto de Joana Pereira Lima")))
    marcado = b"\n/Span <</ActualText (CPF 529.982.247-25)>> BDC EMC /OC /MC0 BDC EMC /Figure /MC1 BDC EMC"
    primeira.Contents = pdf.make_stream(primeira.Contents.read_bytes() + marcado)
    entrada = io.BytesIO()
    pdf.save(entrada)
    r = anonimizar_arquivo(entrada.getvalue(), "a.pdf", anon)
    with pikepdf.open(io.BytesIO(r.dados)) as saida:
        bruto = b"".join(o.read_bytes() if isinstance(o, pikepdf.Stream) else repr(o).encode() for o in saida.objects)
    assert b"Joana" not in bruto and b"529.982" not in bruto


@requer_ocr
def test_pdf_digitalizado_falha_fechada_se_a_tarja_nao_cobre_os_pixels(anon, monkeypatch):
    from PIL import Image, ImageDraw
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    from themis_lgpd.formatos import pdf as modulo_pdf

    folha = Image.new("RGB", (1654, 2339), "white")
    ImageDraw.Draw(folha).text((150, 200), "Requerente: Joana Pereira Lima, CPF 529.982.247-25", fill="black",
                               font_size=44)
    buf = io.BytesIO()
    pagina = canvas.Canvas(buf, pagesize=(595, 842))
    pagina.drawImage(ImageReader(folha), 0, 0, 595, 842)
    pagina.showPage()
    pagina.save()
    monkeypatch.setattr(modulo_pdf, "_desenhar", lambda img, pag, escala: img)  # tarja não é desenhada
    with pytest.raises(VazamentoDetectado):
        anonimizar_arquivo(buf.getvalue(), "digitalizado.pdf", anon)


# ---------------------------------------------------------------------------- formatos estruturados
@pytest.mark.parametrize("conteudo", [
    b"<!DOCTYPE html><html><body><p>CPF 123&#46;456&#46;789-09</p></body></html>",
    b"<?xml version='1.0'?><pedido><cpf>52998224725</cpf></pedido>",
    rb"{\rtf1\ansi Jo\'e3o da Concei\'e7\'e3o}",
    b"From: Joana <j@exemplo.com>\r\nTo: ouvidoria@exemplo.gov.br\r\nSubject: Pedido\r\n"
    b"Content-Transfer-Encoding: base64\r\n\r\nQ1BGIDUyOS45ODIuMjQ3LTI1",
    b"II*\x00" + b"\x00" * 32,
])
def test_formatos_estruturados_nao_sao_tratados_como_texto(conteudo):
    with pytest.raises(ArquivoInvalido):
        detectar_formato(conteudo, "arquivo.txt")


def test_texto_comum_continua_aceito():
    assert detectar_formato(b"<= 5 anos de servico; From: setor de pessoal\n", "a.txt") == "txt"
    assert detectar_formato(struct.pack("<3s", b"abc"), "a.csv") == "csv"


@pytest.fixture(scope="module")
def anon() -> Anonimizador:
    return Anonimizador()
