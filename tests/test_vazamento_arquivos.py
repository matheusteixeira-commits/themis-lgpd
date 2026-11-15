"""Regressão de vazamentos em arquivos: cada teste esconde dados pessoais em um ponto do arquivo que
não é texto corrido e confirma que nenhum deles sobrevive no arquivo gerado.

Os testes de "falha fechada" desativam uma etapa da anonimização e confirmam que a verificação
final impede a entrega do arquivo.
"""

import io
import zipfile

import pytest

from themis_lgpd.formatos import ArquivoInvalido, VazamentoDetectado, anonimizar_arquivo
from themis_lgpd.formatos.verificacao import verificar_ausencia

NOMES = ["Maria Aparecida Souza", "Ana Beatriz Fagundes", "Roberto Nogueira Lacerda", "Helena Prado Vasconcelos",
         "Joao Carlos Pereira", "Lucia Ferraz Monteiro", "Otavio Brandao Siqueira"]


def _conteudo_bruto(dados: bytes) -> str:
    """Todo o conteúdo de um pacote Office, sem interpretação (inclui partes que nenhum editor exibe)."""
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        return " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist()).lower()


def _sobrenomes_presentes(texto: str) -> list[str]:
    return [n for n in NOMES if n.split()[-1].lower() in texto.lower()]


# ---------------------------------------------------------------------------- PDF
def _pdf_adversarial() -> bytes:
    import pikepdf
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    c.setAuthor("Joao Carlos Pereira")
    c.setFont("Helvetica", 11)
    c.drawString(72, 780, "Despacho sobre o pedido de acesso a informacao.")
    c.saveState()
    c.translate(560, 200)
    c.rotate(90)
    c.drawString(0, 0, "Documento assinado por MARIA APARECIDA SOUZA CPF 529.982.247-25")
    c.restoreState()
    c.saveState()
    c.translate(30, 700)
    c.rotate(-90)
    c.drawString(0, 0, "Copia de HELENA PRADO VASCONCELOS")
    c.restoreState()
    c.drawString(72, 640, "Nome do requerente:")
    c.acroForm.textfield(name="nome", value="Ana Beatriz Fagundes", x=200, y=630, width=250, height=20, borderWidth=0)
    c.showPage()
    c.save()
    pdf = pikepdf.open(io.BytesIO(buf.getvalue()))
    nota = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Text, Rect=[10, 10, 30, 30],
                              Contents=pikepdf.String("Ligar para Roberto Nogueira Lacerda"))
    pdf.pages[0].obj.Annots.append(pdf.make_indirect(nota))
    pdf.attachments["lista.txt"] = pikepdf.AttachedFileSpec(pdf, b"Otavio Brandao Siqueira 111.444.777-35")
    saida = io.BytesIO()
    pdf.save(saida)
    return saida.getvalue()


def test_pdf_texto_girado_formulario_comentario_e_anexo(anon):
    from themis_lgpd.formatos.pdf import _texto_estrutural, _texto_extraido

    r = anonimizar_arquivo(_pdf_adversarial(), "despacho.pdf", anon)
    texto = _texto_extraido(r.dados) + _texto_estrutural(r.dados)
    assert _sobrenomes_presentes(texto) == []
    assert "529.982" not in texto and "111.444" not in texto
    assert any("anexado" in a for a in r.avisos)
    assert any("formulário" in a for a in r.avisos)


def test_pdf_texto_vertical_lido_no_sentido_correto():
    from themis_lgpd.formatos.pdf import _extrair

    paginas = _extrair(_pdf_adversarial(), 10, False, [])
    verticais = [s.texto for s in paginas[0].segmentos if s.origem == "texto-vertical"]
    assert any("MARIA APARECIDA SOUZA" in t for t in verticais)
    assert any("HELENA PRADO VASCONCELOS" in t for t in verticais)


def test_pdf_remove_metadados_de_imagens_em_paginas_sem_tarja(anon):
    import pikepdf
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    c.drawString(72, 780, "Requerente: Maria Aparecida Souza")
    c.showPage()
    c.drawString(72, 780, "Pagina sem dados pessoais.")
    c.drawImage(ImageReader(Image.new("RGB", (40, 40), "gray")), 72, 600, 40, 40)
    c.showPage()
    c.save()
    pdf = pikepdf.open(io.BytesIO(buf.getvalue()))
    for imagem in pdf.pages[1].images.values():
        imagem.Metadata = pdf.make_stream(b"<x:xmpmeta><dc:creator>Otavio Brandao Siqueira</dc:creator></x:xmpmeta>")
    entrada = io.BytesIO()
    pdf.save(entrada)
    r = anonimizar_arquivo(entrada.getvalue(), "despacho.pdf", anon)
    with pikepdf.open(io.BytesIO(r.dados)) as saida:
        assert not any("/Metadata" in o for o in saida.objects if isinstance(o, pikepdf.Dictionary | pikepdf.Stream))
    assert b"Siqueira" not in r.dados


# ---------------------------------------------------------------------------- DOCX
def _docx_adversarial() -> bytes:
    import docx
    from docx.oxml.ns import qn
    from lxml import etree
    from PIL import Image

    d = docx.Document()
    d.core_properties.author = "Joao Carlos Pereira"
    p = d.add_paragraph()
    p.add_run("A requerente Mar")
    p.add_run("ia Apa").bold = True
    p.add_run("recida Souza apresentou o pedido.")
    p2 = d.add_paragraph()
    p2.add_run("CPF")
    p2.add_run().add_tab()
    p2.add_run("529.982.247-25")
    tabela = d.add_table(rows=2, cols=1)
    tabela.cell(0, 0).text = "Nome"
    tabela.cell(1, 0).text = "Ana Beatriz Fagundes"
    d.sections[0].header.paragraphs[0].text = "Processo de Ana Beatriz Fagundes"
    p3 = d.add_paragraph("Comentado.")
    d.add_comment(p3.runs, text="Ligar para Roberto Nogueira Lacerda", author="Joao Carlos Pereira", initials="JCP")
    p4 = d.add_paragraph("Texto mantido.")
    exclusao = etree.SubElement(p4._p, qn("w:del"), {qn("w:id"): "9", qn("w:author"): "Joao Carlos Pereira"})
    etree.SubElement(etree.SubElement(exclusao, qn("w:r")), qn("w:delText")).text = "Lucia Ferraz Monteiro"
    p5 = d.add_paragraph()
    marca = etree.SubElement(p5._p, qn("w:smartTag"), {qn("w:element"): "PersonName"})
    propriedades = etree.SubElement(marca, qn("w:smartTagPr"))
    etree.SubElement(propriedades, qn("w:attr"), {qn("w:name"): "ProductID", qn("w:val"): "Helena Prado Vasconcelos"})
    etree.SubElement(etree.SubElement(marca, qn("w:r")), qn("w:t")).text = "Helena Prado Vasconcelos"
    etree.SubElement(p5._p, "{urn:teste}nota").text = "Contato de Otavio Brandao Siqueira"
    imagem = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(imagem, "PNG")
    imagem.seek(0)
    d.add_picture(imagem)
    for propriedade in d.element.body.iter(
            "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr"):
        propriedade.set("descr", "Foto de Ana Beatriz Fagundes")
    rid = d.part._settings_part.relate_to(
        "file:///C:/Users/ana.fagundes/Modelos/Normal.dotm",
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate", is_external=True)
    d.settings.element.insert(0, etree.Element(qn("w:attachedTemplate"), {qn("r:id"): rid}))
    buf = io.BytesIO()
    d.save(buf)
    entrada = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as z:
        for info in entrada.infolist():
            z.writestr(info, entrada.read(info))
        z.writestr("oculto/lista.txt", "Otavio Brandao Siqueira")
    return saida.getvalue()


def test_docx_todas_as_partes_e_atributos(anon):
    import docx

    r = anonimizar_arquivo(_docx_adversarial(), "pedido.docx", anon)
    bruto = _conteudo_bruto(r.dados)
    assert _sobrenomes_presentes(bruto) == []
    assert "529.982" not in bruto and "ana.fagundes" not in bruto and "users/" not in bruto
    assert "oculto/lista.txt" not in zipfile.ZipFile(io.BytesIO(r.dados)).namelist()
    documento = docx.Document(io.BytesIO(r.dados))
    textos = [p.text for p in documento.paragraphs]
    assert "A requerente [NOME] apresentou o pedido." in textos
    assert "CPF\t[CPF]" in textos
    assert documento.tables[0].cell(1, 0).text == "[NOME]"


def test_docx_falha_fechada_quando_a_tarja_nao_e_aplicada(anon, monkeypatch):
    from themis_lgpd.formatos import xml_office

    monkeypatch.setattr(xml_office, "_distribuir", lambda *a, **k: None)
    with pytest.raises(VazamentoDetectado):
        anonimizar_arquivo(_docx_adversarial(), "pedido.docx", anon)


def _pacote_com(substituir: dict[str, bytes], acrescentar: list[tuple[str, bytes]] = ()) -> bytes:
    import docx

    buf = io.BytesIO()
    docx.Document().save(buf)
    entrada = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as z:
        for info in entrada.infolist():
            z.writestr(info, substituir.get(info.filename, entrada.read(info)))
        for nome, conteudo in acrescentar:
            z.writestr(nome, conteudo)
    return saida.getvalue()


def test_docx_rejeita_dtd_entradas_duplicadas_e_formato_strict(anon):
    dtd = (b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e "Maria">]>'
           b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
    with pytest.raises(ArquivoInvalido):
        anonimizar_arquivo(_pacote_com({"word/document.xml": dtd}), "a.docx", anon)
    with pytest.warns(UserWarning):  # o próprio zipfile alerta sobre o nome repetido
        duplicado = _pacote_com({}, [("word/document.xml", b"<x/>")])
    with pytest.raises(ArquivoInvalido):
        anonimizar_arquivo(duplicado, "a.docx", anon)
    strict = b'<w:document xmlns:w="http://purl.oclc.org/ooxml/wordprocessingml/main"/>'
    with pytest.raises(ArquivoInvalido):
        anonimizar_arquivo(_pacote_com({"word/document.xml": strict}), "a.docx", anon)


# ---------------------------------------------------------------------------- planilhas
def _xlsx_adversarial() -> bytes:
    import openpyxl
    from openpyxl.chart import BarChart, Reference
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.workbook.defined_name import DefinedName
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ana Beatriz Fagundes"
    ws.append(["Maria Aparecida Souza", "529.982.247-25", 10])  # aba sem linha de cabeçalho
    ws.append(["Joao Carlos Pereira", "111.444.777-35", 20])
    ws["D1"] = '="Contato: Roberto Nogueira Lacerda"'
    validacao = DataValidation(type="list", formula1='"Helena Prado Vasconcelos,Otavio Brandao Siqueira"',
                               prompt="Escolha Helena Prado Vasconcelos")
    ws.add_data_validation(validacao)
    validacao.add("E1")
    ws.conditional_formatting.add("A1:A5", FormulaRule(formula=['$A1="Joao Carlos Pereira"']))
    ws.auto_filter.ref = "A1:C3"
    ws.auto_filter.add_filter_column(0, ["Joao Carlos Pereira"])
    wb.defined_names["contato"] = DefinedName("contato", attr_text='"Lucia Ferraz Monteiro"')
    ws.oddHeader.left.text = "Processo de Ana Beatriz Fagundes"
    grafico = BarChart()
    grafico.title = "Gastos de Maria Aparecida Souza"
    grafico.add_data(Reference(ws, min_col=3, min_row=1, max_row=2))
    ws.add_chart(grafico, "G2")
    resumo = wb.create_sheet("Resumo")
    resumo["B1"] = "='Ana Beatriz Fagundes'!C1+'Ana Beatriz Fagundes'!C2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_conteudo_fora_das_celulas(anon):
    import openpyxl

    r = anonimizar_arquivo(_xlsx_adversarial(), "dados.xlsx", anon)
    bruto = _conteudo_bruto(r.dados)
    assert _sobrenomes_presentes(bruto) == []
    assert "529.982" not in bruto and "111.444" not in bruto
    wb = openpyxl.load_workbook(io.BytesIO(r.dados))
    novo_titulo = wb.worksheets[0].title
    assert "Fagundes" not in novo_titulo
    assert wb["Resumo"]["B1"].value == f"='{novo_titulo}'!C1+'{novo_titulo}'!C2"
    assert [c.value for c in wb.worksheets[0][1]][:2] == ["[NOME]", "[CPF]"]


def test_avisos_de_planilha_nao_repetem_conteudo(anon):
    r = anonimizar_arquivo(_xlsx_adversarial(), "dados.xlsx", anon)
    assert _sobrenomes_presentes(" ".join(r.avisos)) == []


def test_csv_sem_cabecalho_analisa_a_primeira_linha(anon):
    entrada = b"Maria Aparecida Souza;529.982.247-25\nJoao Carlos Pereira;111.444.777-35\n"
    r = anonimizar_arquivo(entrada, "dados.csv", anon)
    saida = r.dados.decode("utf-8-sig")
    assert "Souza" not in saida and "529.982" not in saida and "Pereira" not in saida


# ---------------------------------------------------------------------------- verificação e propagação
def test_verificacao_respeita_limite_de_palavra_e_trechos_protegidos():
    assert verificar_ausencia("Obras no acostamento da via", ["Costa"]) == []
    assert verificar_ausencia("Reunião com Costa amanhã", ["Costa"]) == ["Costa"]
    assert verificar_ausencia("Unidade de São Paulo", ["Paulo"], protegidos=["São Paulo"]) == []
    assert verificar_ausencia("Unidade de São Paulo e Paulo", ["Paulo"], protegidos=["São Paulo"]) == ["Paulo"]
    # Permitir "Maria" não pode esconder o nome completo.
    assert verificar_ausencia("Assinado: Maria Souza", ["Maria Souza"], protegidos=["Maria"]) == ["Maria Souza"]
    # Texto dividido entre elementos, com quebra de linha e hifenização.
    assert verificar_ausencia("MARIA APA-\nRECIDA", ["Maria Aparecida"]) == ["Maria Aparecida"]
    assert verificar_ausencia("CPF 52998224725", ["529.982.247-25"]) == ["529.982.247-25"]


def test_propagacao_nao_tarja_parte_de_nome_de_lugar(anon):
    textos = ["O servidor Paulo Henrique Duarte atendeu o pedido.", "A unidade de São Paulo foi consultada."]
    resultados = anon.anonimizar_lote(textos, mesmo_documento=True)
    assert "São Paulo" in resultados[1].texto
    assert "Duarte" not in resultados[0].texto


# ---------------------------------------------------------------------------- OCR
def _pdf_digitalizado() -> bytes:
    from PIL import Image, ImageDraw
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    pagina = Image.new("RGB", (1240, 1754), "white")
    ImageDraw.Draw(pagina).text((100, 100), "Requerente: Maria Aparecida Souza", fill="black")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    c.drawImage(ImageReader(pagina), 0, 0, 595, 842)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_pdf_digitalizado_sem_ocr_disponivel_e_recusado(anon, monkeypatch):
    from themis_lgpd.formatos import FalhaOCR, ocr

    monkeypatch.setattr(ocr, "ocr_disponivel", lambda: False)
    with pytest.raises(FalhaOCR):
        anonimizar_arquivo(_pdf_digitalizado(), "digitalizado.pdf", anon)
    # Com o OCR desativado explicitamente, o arquivo é gerado e o usuário é avisado.
    r = anonimizar_arquivo(_pdf_digitalizado(), "digitalizado.pdf", anon, ocr=False)
    assert any("NÃO analisadas" in a for a in r.avisos)


def test_tesseract_recebe_a_imagem_pela_entrada_padrao_e_falha_fechado(monkeypatch):
    import subprocess

    from PIL import Image

    from themis_lgpd.formatos import FalhaOCR, ocr

    chamadas = []
    tsv = (b"level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
           b"5\t1\t1\t1\t1\t1\t10\t20\t30\t40\t96\tMaria\n")

    def executar(args, **kwargs):
        chamadas.append((args, kwargs))
        return subprocess.CompletedProcess(args, codigo, stdout=tsv, stderr=b"")

    monkeypatch.setattr(ocr, "_tesseract", lambda: "tesseract")
    monkeypatch.setattr(ocr.subprocess, "run", executar)
    codigo = 0
    palavras = ocr.reconhecer(Image.new("RGB", (50, 50), "white"))
    assert [p.texto for p in palavras] == ["Maria"]
    argumentos, opcoes = chamadas[0]
    assert argumentos[1] == "stdin" and opcoes["input"].startswith(b"\x89PNG")
    codigo = 1
    with pytest.raises(FalhaOCR):
        ocr.reconhecer(Image.new("RGB", (50, 50), "white"))


def test_planilha_propaga_colunas_integrais_e_mantem_pseudonimos_distintos():
    from themis_lgpd import Anonimizador

    entrada = ("Nome;Observação\nRosilene Fagundes;Rosilene Fagundes pediu revisão\n"
               "Heitor Vasconcelos;sem pendências\n").encode()
    r = anonimizar_arquivo(entrada, "dados.csv", Anonimizador(modo="pseudonimo"))
    linhas = [linha.split(";") for linha in r.dados.decode("utf-8-sig").splitlines()]
    assert "Fagundes" not in r.dados.decode("utf-8-sig")
    assert linhas[1][0] != linhas[2][0]  # pessoas diferentes, pseudônimos diferentes
    assert linhas[1][1].startswith(linhas[1][0])  # o mesmo nome recebe o mesmo pseudônimo em outra coluna


def test_pdf_com_texto_em_contornos_passa_por_ocr(monkeypatch):
    from reportlab.pdfgen import canvas

    from themis_lgpd.formatos import FalhaOCR, ocr

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    contorno = c.beginPath()
    for k in range(60):
        x, y = 60 + (k % 30) * 15, 780 - (k // 30) * 20
        contorno.moveTo(x, y)
        contorno.curveTo(x + 2, y + 8, x + 6, y + 8, x + 8, y)
        contorno.close()
    c.drawPath(contorno, fill=1, stroke=0)
    c.showPage()
    c.save()
    monkeypatch.setattr(ocr, "ocr_disponivel", lambda: False)
    with pytest.raises(FalhaOCR):  # a página exige OCR, embora não tenha caracteres nem imagens
        anonimizar_arquivo(buf.getvalue(), "contornos.pdf")
