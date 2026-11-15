"""Testes de anonimização de arquivos: PDF, DOCX, XLSX, CSV, TXT e imagens."""

import io
import zipfile

import pytest

from themis_lgpd.formatos import ArquivoInvalido, anonimizar_arquivo, detectar_formato

CPF = "529.982.247-25"


def _pdf(linhas_por_pagina, autor="Autor Secreto"):
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    c.setAuthor(autor)
    c.setTitle("Processo de Maria Aparecida Souza")
    for linhas in linhas_por_pagina:
        c.setFont("Helvetica", 11)
        for i, linha in enumerate(linhas):
            c.drawString(60, 780 - 20 * i, linha)
        c.linkURL("mailto:maria.souza@gmail.com", (60, 735, 300, 750))
        c.showPage()
    c.save()
    return buf.getvalue()


def _texto_pdf(dados):
    import pdfplumber
    import pypdfium2 as pdfium

    with pdfplumber.open(io.BytesIO(dados)) as p:
        a = " ".join(pg.extract_text() or "" for pg in p.pages)
    doc = pdfium.PdfDocument(dados)
    b = " ".join(pg.get_textpage().get_text_range() for pg in doc)
    return a + " " + b


def test_pdf_tarja_real_remove_texto_metadados_e_anotacoes(anon):
    import pikepdf

    dados = _pdf([[f"Requerente: Maria Aparecida Souza, CPF {CPF}", "e-mail maria.souza@gmail.com",
                   "O pedido trata de política pública de transporte."],
                  [f"Página 2 sem dados pessoais. Rodapé: {CPF}"]])
    r = anonimizar_arquivo(dados, "processo.pdf", anon)
    texto = _texto_pdf(r.dados)
    for proibido in ("Maria", "Souza", "529.982", "maria.souza", "Autor Secreto"):
        assert proibido not in texto
    assert "política pública de transporte" in texto  # o restante continua pesquisável
    with pikepdf.open(io.BytesIO(r.dados)) as p:
        assert "/Info" not in p.trailer and "/Metadata" not in p.Root
        assert all("/Annots" not in pg.obj for pg in p.pages)


def test_pdf_sem_dados_pessoais_nao_e_rasterizado(anon):
    dados = _pdf([["Relatório anual de atividades da ouvidoria."]])
    r = anonimizar_arquivo(dados, "relatorio.pdf", anon)
    assert "Relatório anual" in _texto_pdf(r.dados)
    assert not any("convertidas em imagem" in a for a in r.avisos)


def test_pdf_corrompido(anon):
    with pytest.raises(ArquivoInvalido):
        anonimizar_arquivo(b"%PDF-1.7\nlixo", "x.pdf", anon)


def test_docx_corpo_tabela_cabecalho_comentarios_e_propriedades(anon):
    import docx

    d = docx.Document()
    d.core_properties.author = "Autor Secreto"
    d.sections[0].header.paragraphs[0].text = "Servidor João Pereira - matrícula 123.456-7"
    p = d.add_paragraph("O requerente ")
    p.add_run("José Carlos").bold = True
    p.add_run(f" de Oliveira, CPF {CPF}, mora na Rua das Flores, 123.")
    t = d.add_table(rows=1, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "E-mail", "jose@exemplo.com.br"
    d.add_comment(p.runs[0], text="Comentário com CPF 111.444.777-35", author="Revisor X")
    buf = io.BytesIO()
    d.save(buf)
    r = anonimizar_arquivo(buf.getvalue(), "oficio.docx", anon)
    with zipfile.ZipFile(io.BytesIO(r.dados)) as z:
        xml = " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith((".xml", ".rels")))
        nomes = z.namelist()
    for proibido in ("José", "Oliveira", "529.982", "jose@", "João", "123.456-7", "Autor Secreto", "Revisor X",
                     "111.444.777-35"):
        assert proibido not in xml
    assert not any("comments" in n or n.startswith("docProps/app") or "thumbnail" in n for n in nomes)
    d2 = docx.Document(io.BytesIO(r.dados))
    assert d2.paragraphs[0].runs[0].text == "O requerente "  # formatação preservada fora das tarjas


def test_docx_alteracoes_controladas_nao_vazam(anon):
    import docx
    from docx.oxml.ns import qn
    from lxml import etree

    d = docx.Document()
    p = d.add_paragraph("Texto final.")
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    dele = etree.SubElement(p._p, qn("w:del"), {qn("w:id"): "1", qn("w:author"): "X"})
    run = etree.SubElement(dele, qn("w:r"))
    etree.SubElement(run, f"{{{w}}}delText").text = f"CPF excluído {CPF}"
    buf = io.BytesIO()
    d.save(buf)
    r = anonimizar_arquivo(buf.getvalue(), "rev.docx", anon)
    with zipfile.ZipFile(io.BytesIO(r.dados)) as z:
        assert "529.982" not in z.read("word/document.xml").decode()
    assert any("alteração" in a for a in r.avisos)


def test_xlsx_colunas_pessoais_comentarios_e_propriedades(anon):
    import openpyxl
    from openpyxl.comments import Comment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Nome", "CPF", "Descrição do pedido", "Órgão"])
    ws.append(["Maria", "52998224725", "Minha filha tem autismo", "Secretaria de Saúde"])
    ws["C2"].comment = Comment("CPF 111.444.777-35", "Autor")
    wb.properties.creator = "Criador Secreto"
    buf = io.BytesIO()
    wb.save(buf)
    r = anonimizar_arquivo(buf.getvalue(), "planilha.xlsx", anon)
    ws2 = openpyxl.load_workbook(io.BytesIO(r.dados)).active
    linha = [c.value for c in ws2[2]]
    assert linha[0] == "[NOME]" and linha[1] == "[CPF]" and "autismo" not in linha[2]
    assert linha[3] == "Secretaria de Saúde" and ws2["C2"].comment is None
    with zipfile.ZipFile(io.BytesIO(r.dados)) as z:
        assert "Criador Secreto" not in z.read("docProps/core.xml").decode()


def test_csv_mantem_delimitador_e_estrutura(anon):
    entrada = b"nome;email;texto\nAna Lima;ana@x.com;Moro na QNM 12 Conjunto B Casa 4\n"
    r = anonimizar_arquivo(entrada, "dados.csv", anon)
    linhas = r.dados.decode("utf-8-sig").splitlines()
    assert linhas[0] == "nome;email;texto" and linhas[1].startswith("[NOME];[E-MAIL];Moro na [ENDEREÇO]")


def test_txt_latin1_e_detecao_por_conteudo(anon):
    r = anonimizar_arquivo("Requerente Joaquim Barbosa, CPF 529.982.247-25".encode("cp1252"), "a.txt", anon)
    assert r.dados.decode("utf-8") == "Requerente [NOME], CPF [CPF]"
    assert detectar_formato(b"%PDF-1.4 ...") == "pdf"
    with pytest.raises(ArquivoInvalido):
        detectar_formato(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")  # .doc antigo


def test_zip_bomb_e_limite_de_tamanho(anon):
    from themis_lgpd.formatos import verificar_zip

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<x/>")
        z.writestr("word/document.xml", "0" * (5 * 1024 * 1024))
    assert len(buf.getvalue()) < 100_000  # 5 MB descompactados em poucos KB
    with pytest.raises(ArquivoInvalido):
        verificar_zip(buf.getvalue(), limite=1024 * 1024)
    with pytest.raises(ArquivoInvalido):
        anonimizar_arquivo(b"x" * 1024, "a.txt", anon, limite_bytes=100)


def _imagem_com_texto():
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1400, 300), "white")
    d = ImageDraw.Draw(img)
    try:
        fonte = ImageFont.truetype("DejaVuSans.ttf", 40)
    except OSError:
        try:
            fonte = ImageFont.truetype("arial.ttf", 40)
        except OSError:
            fonte = ImageFont.load_default(size=40)
    d.text((40, 40), "Requerente: Maria Aparecida Souza", fill="black", font=fonte)
    d.text((40, 120), "CPF 529.982.247-25  Tel (61) 99999-8888", fill="black", font=fonte)
    d.text((40, 200), "Solicita copia do processo administrativo.", fill="black", font=fonte)
    return img


@pytest.mark.lento
def test_imagem_e_pdf_digitalizado_com_ocr(anon):
    from PIL import Image

    from themis_lgpd.formatos.ocr import ocr_disponivel, reconhecer

    if not ocr_disponivel():
        pytest.skip("OCR indisponível")
    img = _imagem_com_texto()
    png = io.BytesIO()
    img.save(png, "PNG")
    r = anonimizar_arquivo(png.getvalue(), "scan.png", anon)
    relido = " ".join(p.texto for p in reconhecer(Image.open(io.BytesIO(r.dados))))
    for proibido in ("Maria", "Souza", "529", "247", "99999"):
        assert proibido not in relido, relido  # nem o próprio OCR recupera o que foi tarjado
    assert "processo" in relido
    pdf = io.BytesIO()
    img.save(pdf, "PDF", resolution=150)
    r2 = anonimizar_arquivo(pdf.getvalue(), "scan.pdf", anon)
    texto = _texto_pdf(r2.dados)
    assert "529.982" not in texto and "Maria" not in texto and "processo" in texto
