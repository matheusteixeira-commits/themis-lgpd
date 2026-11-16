"""Tarja manual por região (assinaturas, fotos, carimbos) e páginas de PDF com rotação declarada."""

import io

import pikepdf
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from themis_lgpd.formatos import ArquivoInvalido, VazamentoDetectado, anonimizar_arquivo
from themis_lgpd.formatos.regioes import Regiao, interpretar, interpretar_lista

#: Região da "assinatura" desenhada pelos PDFs de teste, em frações da página A4 em pé.
ASSINATURA = Regiao(1, 0.05, 0.80, 0.70, 0.90)


def _pdf(rotacao: int = 0) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 16)
    c.drawString(60, 790, "Despacho publico sobre o pedido.")
    c.drawString(60, 500, "Requerente CPF 529.982.247-25 solicita copia.")
    c.setFillColorRGB(0.1, 0.2, 0.8)
    c.rect(60, 110, 300, 40, fill=1, stroke=0)  # "assinatura manuscrita"
    c.setFillColorRGB(0, 0, 0)
    c.drawString(60, 120, "Rubrica ZXQWERTY do servidor")
    c.showPage()
    c.save()
    if not rotacao:
        return buf.getvalue()
    with pikepdf.open(io.BytesIO(buf.getvalue())) as pdf:
        pdf.pages[0].obj["/Rotate"] = rotacao
        saida = io.BytesIO()
        pdf.save(saida)
    return saida.getvalue()


def _render(dados: bytes, pagina: int = 0):
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(dados)
    img = doc[pagina].render(scale=2).to_pil().convert("RGB")
    doc.close()
    return img


def _texto(dados: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(dados)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _escura(img, regiao: Regiao) -> bool:
    """A região está inteiramente coberta (pixels pretos), descontada uma borda de 2 pixels."""
    x0, y0, x1, y1 = regiao.caixa(img.width, img.height)
    recorte = img.crop((int(x0) + 2, int(y0) + 2, int(x1) - 2, int(y1) - 2))
    return all(maximo <= 10 for _, maximo in recorte.getextrema())


# ---------------------------------------------------------------------------- rotação declarada
@pytest.mark.parametrize("rotacao", [0, 90, 180, 270])
def test_pagina_girada_tarjada_na_posicao_exibida(anon, rotacao):
    """Regressão: com /Rotate, as tarjas eram desenhadas na página sem rotação e o CPF ficava visível."""
    from themis_lgpd.formatos.ocr import ocr_disponivel, reconhecer

    entrada = _pdf(rotacao)
    res = anonimizar_arquivo(entrada, "girado.pdf", anon)
    assert any(e.tipo == "CPF" and e.acao == "tarjar" for e in res.entidades)  # lido na ordem certa, até a 180°
    assert _render(res.dados).size == _render(entrada).size  # mesma orientação de exibição
    with pikepdf.open(io.BytesIO(res.dados)) as pdf:
        assert int(pdf.pages[0].obj.get("/Rotate", 0)) == 0  # a imagem gerada já está na orientação exibida
    if ocr_disponivel():
        lido = " ".join(p.texto for p in reconhecer(_render(res.dados)))
        assert "529" not in lido and "982" not in lido, lido


# ---------------------------------------------------------------------------- regiões
def test_interpretar_regiao():
    assert interpretar("1:10,70,45,85") == Regiao(1, 0.10, 0.70, 0.45, 0.85)
    assert interpretar(" 2 : 0 , 0 , 100 , 50 ") == Regiao(2, 0, 0, 1, 0.5)
    assert str(Regiao(1, 0.1, 0.7, 0.45, 0.85)) == "1:10,70,45,85"
    assert interpretar_lista("1:0,0,10,10; 2:5,5,20,20\n3:1,1,2,2") == [
        Regiao(1, 0, 0, 0.1, 0.1), Regiao(2, 0.05, 0.05, 0.2, 0.2), Regiao(3, 0.01, 0.01, 0.02, 0.02)]
    for invalida in ("1:10,70,45", "0:10,10,20,20", "1:50,10,20,20", "1:10,10,120,20", "a:1,2,3,4", ""):
        with pytest.raises(ValueError):
            interpretar(invalida)


def test_regiao_em_pdf_cobre_pixels_e_remove_texto(anon):
    res = anonimizar_arquivo(_pdf(), "assinado.pdf", anon, regioes=[ASSINATURA])
    assert _escura(_render(res.dados), ASSINATURA)
    texto = _texto(res.dados)
    assert "ZXQWERTY" not in texto and "Rubrica" not in texto
    assert "Despacho publico" in texto  # o restante da página continua pesquisável
    assert any("região(ões) tarjada(s) manualmente" in a for a in res.avisos)


def test_regiao_em_pagina_girada_segue_a_orientacao_exibida(anon):
    """Em página com /Rotate 90 (exibida deitada), a região é marcada sobre a página como é vista."""
    regiao = Regiao(1, 0.60, 0.05, 0.95, 0.40)
    res = anonimizar_arquivo(_pdf(90), "girado.pdf", anon, regioes=[regiao])
    img = _render(res.dados)
    assert img.width > img.height and _escura(img, regiao)


def test_verificacao_detecta_texto_dentro_da_regiao(anon, monkeypatch):
    """Se a camada de texto mantivesse palavras sob a região, a verificação impediria a entrega."""
    from themis_lgpd.formatos import pdf as modulo_pdf

    monkeypatch.setattr(modulo_pdf, "_palavras_visiveis", lambda pag, origens=("texto", "ocr"): [
        par for seg in pag.segmentos if seg.origem in origens for par in seg.palavras])
    with pytest.raises(VazamentoDetectado):
        anonimizar_arquivo(_pdf(), "assinado.pdf", anon, regioes=[ASSINATURA])


def test_regiao_fora_do_documento_ou_em_formato_sem_paginas(anon):
    with pytest.raises(ArquivoInvalido, match="página 3"):
        anonimizar_arquivo(_pdf(), "a.pdf", anon, regioes=[Regiao(3, 0, 0, 0.5, 0.5)])
    with pytest.raises(ArquivoInvalido, match="PDFs e imagens"):
        anonimizar_arquivo(b"Texto simples.", "a.txt", anon, regioes=[Regiao(1, 0, 0, 0.5, 0.5)])


@pytest.mark.lento
def test_regiao_em_imagem_e_em_tiff(anon):
    from PIL import Image, ImageSequence

    from themis_lgpd.formatos.ocr import ocr_disponivel

    if not ocr_disponivel():
        pytest.skip("OCR indisponível")
    foto = Image.new("RGB", (800, 600), "white")
    foto.paste((200, 150, 120), (100, 100, 400, 450))  # "rosto"
    buf = io.BytesIO()
    foto.save(buf, "PNG")
    regiao = Regiao(1, 0.10, 0.15, 0.52, 0.77)
    res = anonimizar_arquivo(buf.getvalue(), "foto.png", anon, regioes=[regiao])
    assert _escura(Image.open(io.BytesIO(res.dados)).convert("RGB"), regiao)

    paginas = [Image.new("L", (600, 800), 255) for _ in range(2)]
    for p in paginas:
        p.paste(90, (50, 600, 400, 700))  # carimbo
    buf = io.BytesIO()
    paginas[0].save(buf, "TIFF", save_all=True, append_images=paginas[1:])
    carimbo = Regiao(2, 0.05, 0.72, 0.70, 0.90)
    res = anonimizar_arquivo(buf.getvalue(), "digitalizado.tif", anon, regioes=[carimbo])
    with Image.open(io.BytesIO(res.dados)) as tiff:
        saida = [p.convert("RGB") for p in ImageSequence.Iterator(tiff)]
    assert _escura(saida[1], carimbo) and not _escura(saida[0], carimbo)  # só a página indicada


def test_regiao_pela_cli(tmp_path):
    from themis_lgpd.cli import main

    entrada = tmp_path / "assinado.pdf"
    entrada.write_bytes(_pdf())
    saida = tmp_path / "saida.pdf"
    assert main(["anonimizar", str(entrada), "-o", str(saida), "--regiao", str(ASSINATURA)]) == 0
    assert _escura(_render(saida.read_bytes()), ASSINATURA)
    assert main(["anonimizar", str(entrada), "-o", str(saida), "--regiao", "1:90,10,20,20"]) == 1
    outro = tmp_path / "outro.pdf"
    outro.write_bytes(_pdf())
    assert main(["anonimizar", str(entrada), str(outro), "--regiao", str(ASSINATURA)]) == 1


def test_regiao_pela_api(monkeypatch):
    import importlib

    from fastapi.testclient import TestClient

    import themis_lgpd.api.app as modulo

    monkeypatch.setenv("THEMIS_LIMITE_REQ_MINUTO", "1000")
    modulo = importlib.reload(modulo)
    with TestClient(modulo.app) as cliente:
        r = cliente.post("/v1/arquivos/anonimizar", files={"arquivo": ("assinado.pdf", _pdf(), "application/pdf")},
                         data={"regiao": [str(ASSINATURA)]})
        assert r.status_code == 200, r.text
        assert _escura(_render(r.content), ASSINATURA)
        r = cliente.post("/v1/arquivos/anonimizar", files={"arquivo": ("assinado.pdf", _pdf(), "application/pdf")},
                         data={"regiao": ["1:10,10"]})
        assert r.status_code == 422
