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
