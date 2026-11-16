"""Teste de ponta a ponta da interface (Streamlit AppTest, sem navegador)."""

from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = Path(__file__).parents[1] / "src" / "themis_lgpd" / "ui" / "app.py"


def test_fluxo_analisar_revisar_gerar():
    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    assert not at.exception
    at.text_area(key="texto").input("Eu, Maria Aparecida Souza, CPF 529.982.247-25. <img src=x onerror=alert(1)>").run()
    at.button[0].click().run()  # 1 · Analisar
    assert not at.exception
    previa = at.get("html")[0].proto.body
    assert "&lt;img" in previa and "<img" not in previa  # conteúdo do documento nunca vira HTML
    at.button[1].click().run()  # 3 · Gerar
    assert not at.exception
    saida = at.get("html")[-1].proto.body
    assert "[NOME]" in saida and "[CPF]" in saida and "Maria" not in saida and "529.982" not in saida
    rotulos = [d.proto.label for d in at.get("download_button")]
    assert "Baixar texto anonimizado (TXT)" in rotulos and "Nota de tarjamento (TXT)" in rotulos


def test_revisor_pode_desmarcar_item():
    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    at.text_area(key="texto").input("O servidor João Pereira, CPF 529.982.247-25, pediu férias.").run()
    at.button[0].click().run()
    editor = at.get("arrow_data_frame") or at.get("data_editor")
    assert editor  # tabela de revisão exibida


def _botao(at, rotulo: str):
    return next(b for b in at.button if b.label == rotulo)


def test_varios_arquivos_geram_zip_com_manifesto():
    import io
    import json
    import zipfile

    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    at.file_uploader[0].set_value([
        ("requerimento.txt", b"Requerente: Maria Aparecida Souza, CPF 529.982.247-25.", "text/plain"),
        ("despacho.txt", b"Defiro o pedido do CPF 529.982.247-25.", "text/plain"),
    ]).run()
    _botao(at, "Anonimizar arquivos").click().run()
    assert not at.exception
    rotulos = [d.proto.label for d in at.get("download_button")]
    assert "Baixar arquivos anonimizados (ZIP, com manifesto)" in rotulos
    res = at.session_state["lote"][1]
    with zipfile.ZipFile(io.BytesIO(res.dados)) as z:
        manifesto = json.loads(z.read("manifesto_anonimizacao.json"))
        textos = [z.read(n).decode("utf-8") for n in ("requerimento.txt", "despacho.txt")]
    assert [linha["situacao"] for linha in manifesto["arquivos"]] == ["anonimizado", "anonimizado"]
    assert all("529.982.247-25" not in t and "[CPF]" in t for t in textos) and "Maria" not in textos[0]


def _pdf_duas_paginas() -> bytes:
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(60, 790, "Despacho publico, primeira pagina.")
    c.showPage()
    c.drawString(60, 790, "Segunda pagina do despacho.")
    c.drawString(60, 120, "Rubrica ZXQWERTY do servidor")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_previa_paginada_e_tarja_manual_por_regiao():
    import io

    import pdfplumber

    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    at.file_uploader[0].set_value(("despacho.pdf", _pdf_duas_paginas(), "application/pdf")).run()
    _botao(at, "Anonimizar arquivo").click().run()
    assert not at.exception
    at.number_input(key="pagina_previa").set_value(2).run()
    assert "Página 2 de 2" in at.image[0].captions[0]
    at.toggle(key="marcar_regioes").set_value(True).run()
    for chave, valor in {"regiao_x0": 5, "regiao_y0": 82, "regiao_x1": 70, "regiao_y1": 90}.items():
        at.number_input(key=chave).set_value(valor)
    at.run()
    _botao(at, "Adicionar região na página 2").click().run()
    assert not at.exception
    assert any("ainda não aplicadas" in w.value for w in at.warning)
    _botao(at, "Anonimizar arquivo").click().run()
    assert not at.exception and not at.warning
    res = at.session_state["arquivo"][1]
    with pdfplumber.open(io.BytesIO(res.dados)) as pdf:
        assert "ZXQWERTY" not in (pdf.pages[1].extract_text() or "")
        assert "primeira pagina" in (pdf.pages[0].extract_text() or "")
    assert any("manualmente na(s) página(s) 2" in a for a in res.avisos)
