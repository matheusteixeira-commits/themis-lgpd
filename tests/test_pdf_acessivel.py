"""PDF acessível, pesquisável e de arquivamento: camada de texto Unicode, rótulos das tarjas para leitores
de tela, idioma, OCR em páginas digitalizadas sem tarja, sumário e links filtrados, e PDF/A-2b."""

import io
import sys
from pathlib import Path

import pdfplumber
import pikepdf
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from themis_lgpd.formatos import anonimizar_arquivo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validar_pdfa  # noqa: E402

CPF = "529.982.247-25"


def _texto(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        return "\n".join(pg.extract_text() or "" for pg in p.pages)


def _rotulos(pdf: bytes) -> list[str]:
    with pikepdf.open(io.BytesIO(pdf)) as p:
        return [str(i.operands[1].get("/ActualText")) for pg in p.pages for i in pikepdf.parse_content_stream(pg)
                if str(i.operator) == "BDC" and isinstance(i.operands[1], pikepdf.Dictionary)]


def _fontes(pdf: bytes) -> list[tuple[str, bool]]:
    saida = []
    with pikepdf.open(io.BytesIO(pdf)) as p:
        for pg in p.pages:
            for _, fonte in (pg.Resources.get("/Font") or {}).items():
                descritor = fonte.get("/FontDescriptor")
                saida.append((str(fonte.get("/BaseFont")),
                              bool(descritor and any(k in descritor for k in ("/FontFile", "/FontFile2", "/FontFile3")))))
    return saida


def test_camada_de_texto_unicode_e_rotulos_das_tarjas(anon):
    from themis_lgpd.formatos.pdfa import registrar_fonte

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(registrar_fonte(), 11)  # fonte Unicode na entrada: a Helvetica padrão não codifica "≥"
    c.drawString(60, 790, f"Requerente: Maria Aparecida Souza, CPF {CPF}, idade ≥ 18 anos, ação e coração.")
    c.showPage()
    c.save()
    res = anonimizar_arquivo(buf.getvalue(), "pedido.pdf", anon)
    texto = _texto(res.dados)
    assert CPF not in texto and "Maria" not in texto
    assert "≥" in texto and "coração" in texto  # antes, caracteres fora do cp1252 viravam "?"
    assert {"[NOME]", "[CPF]"} <= set(_rotulos(res.dados))
    assert all(embutida for _, embutida in _fontes(res.dados))


def test_idioma_declarado(anon):
    res = anonimizar_arquivo((Path(__file__).parents[1] / "exemplos" / "despacho_ficticio.pdf").read_bytes(),
                             "despacho.pdf", anon)
    with pikepdf.open(io.BytesIO(res.dados)) as p:
        assert str(p.Root.Lang) == "pt-BR"


def test_pagina_digitalizada_sem_tarja_fica_pesquisavel(anon):
    from themis_lgpd.formatos.ocr import ocr_disponivel

    if not ocr_disponivel():
        pytest.skip("OCR indisponível")
    import reportlab
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader

    img = Image.new("RGB", (1654, 2339), "white")
    fonte = ImageFont.truetype(str(Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"), 48)
    ImageDraw.Draw(img).text((140, 200), "Relatorio anual de gestao do programa", fill="black", font=fonte)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(img), 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()
    assert _texto(buf.getvalue()).strip() == ""
    res = anonimizar_arquivo(buf.getvalue(), "digitalizado.pdf", anon)
    assert "gestao" in _texto(res.dados).lower()
    assert any("pesquisáveis" in a for a in res.avisos)
    with pikepdf.open(io.BytesIO(res.dados)) as p:  # a imagem original foi mantida, sem rasterização
        assert len(list(p.pages[0].images)) == 1 or "/XObject" in p.pages[0].Resources


def _pdf_com_sumario_e_links() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(60, 790, "Capítulo 1 — relatório público.")
    c.bookmarkPage("p1")
    c.addOutlineEntry("Laudo de Maria Aparecida Souza", "p1", level=0)
    c.linkURL("https://www.gov.br/cgu/pt-br", (60, 700, 300, 720))
    c.linkURL("mailto:joao.silva@gmail.com", (60, 650, 300, 670))
    c.linkURL(f"https://exemplo.gov.br/consulta?cpf={CPF.replace('.', '').replace('-', '')}", (60, 600, 300, 620))
    c.showPage()
    c.drawString(60, 790, "Capítulo 2.")
    c.bookmarkPage("p2")
    c.addOutlineEntry("Anexo estatístico", "p2", level=0)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_sumario_anonimizado_e_links_filtrados(anon):
    res = anonimizar_arquivo(_pdf_com_sumario_e_links(), "relatorio.pdf", anon)
    with pikepdf.open(io.BytesIO(res.dados)) as p:
        with p.open_outline() as sumario:
            itens = [(str(i.title), p.pages.index(pikepdf.Page(i.destination[0]))) for i in sumario.root]
        uris = [str(a.A.URI) for pg in p.pages for a in pg.obj.get("/Annots", []) if "/A" in a]
    assert itens == [("Laudo de [NOME]", 0), ("Anexo estatístico", 1)]
    assert uris == ["https://www.gov.br/cgu/pt-br"]
    assert any("link(s) com dado pessoal" in a for a in res.avisos)


def test_pdfa_estrutura(anon):
    res = anonimizar_arquivo(validar_pdfa._texto_fontes_padrao(), "fontes_padrao.pdf", anon, pdfa=True)
    with pikepdf.open(io.BytesIO(res.dados)) as p:
        assert p.pdf_version == "1.7"
        intento = p.Root.OutputIntents[0]
        assert str(intento.S) == "/GTS_PDFA1" and int(intento.DestOutputProfile.N) == 3
        meta = p.open_metadata()
        assert meta["pdfaid:part"] == "2" and meta["pdfaid:conformance"] == "B"
        assert "/Info" not in p.trailer
        # Todas as páginas viram imagem com camada de texto: nenhuma fonte original (Times, Helvetica)
        # não incorporada sobra no arquivo.
        assert all(len(list(pg.images)) == 1 for pg in p.pages)
    assert _fontes(res.dados) and all(embutida for _, embutida in _fontes(res.dados))
    assert CPF not in _texto(res.dados) and "ação" in _texto(res.dados)


def test_pdfa_pela_linha_de_comando(tmp_path):
    from themis_lgpd.cli import main

    entrada = tmp_path / "despacho.pdf"
    entrada.write_bytes((Path(__file__).parents[1] / "exemplos" / "despacho_ficticio.pdf").read_bytes())
    assert main(["anonimizar", str(entrada), "--pdfa", "--sem-ner"]) == 0
    with pikepdf.open(tmp_path / "despacho_anonimizado.pdf") as p:
        assert "/OutputIntents" in p.Root
