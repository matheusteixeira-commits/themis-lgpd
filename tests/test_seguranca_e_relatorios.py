"""Testes de segurança da interface (HTML escapado) e dos relatórios de tarjamento."""

import json
from html.parser import HTMLParser

import pytest

from themis_lgpd import Anonimizador, relatorio
from themis_lgpd.ui.realce import legenda, realcar_original, realcar_saida

PAYLOADS = [
    '<img src=x onerror="alert(1)"',          # tag não fechada: contornaria um escape restrito a tags completas
    "<script>alert(document.cookie)</script>",
    "![rastreio](https://atacante.example/pixel.png)",  # Markdown → requisição externa
    "[clique](javascript:alert(1))",
    "&lt;b&gt;entidade&lt;/b&gt;",
]


class _Coletor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.atributos = set(), set()

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        self.atributos |= {nome for nome, _ in attrs}


@pytest.mark.parametrize("payload", PAYLOADS)
def test_interface_nunca_renderiza_html_do_documento(anon, payload):
    texto = f"Maria Souza, CPF 529.982.247-25. {payload}"
    r = anon.anonimizar(texto)
    for html in (realcar_original(texto, anon.analisar(texto)), realcar_saida(r)):
        coletor = _Coletor()
        coletor.feed(html)
        assert coletor.tags <= {"div", "mark", "sup", "span"}, coletor.tags  # só as tags da própria interface
        assert coletor.atributos <= {"style", "title", "aria-hidden"}, coletor.atributos  # nenhum on*, href, src


def test_marcacoes_acessiveis_sem_depender_de_cor(anon):
    """A ação e a base legal de cada trecho estão em texto (leitores de tela), não só na cor ou no title."""
    import re

    texto = "Maria Souza, CPF 529.982.247-25, natural de Campinas/SP."
    entidades = anon.analisar(texto)
    acoes = {e.acao for e in entidades}
    assert {"tarjar", "alertar"} <= acoes, acoes
    html = realcar_original(texto, entidades)
    sem_title = re.sub(r'title="[^"]*"', "", html)  # o que resta é lido mesmo sem passar o mouse
    assert "será tarjado" in sem_title and "alerta para revisão" in sem_title
    cpf = next(e for e in entidades if e.tipo == "CPF")
    assert cpf.base_legal and cpf.base_legal in sem_title
    assert "2px solid" in html and "2px dashed" in html  # tarjar e revisar diferem também no sublinhado
    assert "■ CPF" in html  # símbolo visível ao lado do rótulo
    item = legenda()
    for descricao in ("Será tarjado", "Alerta para revisão", "Mantido", "contínuo", "tracejado", "pontilhado"):
        assert descricao in item, descricao


def test_relatorio_padrao_nao_contem_valores(anon):
    r = anon.anonimizar("Maria Aparecida Souza, CPF 529.982.247-25, e-mail maria@x.com")
    for saida in (relatorio.para_json([r]), relatorio.para_csv([r]), relatorio.nota_de_tarjamento([r])):
        assert "529.982" not in saida and "Maria" not in saida and "maria@x.com" not in saida
    dados = json.loads(relatorio.para_json([r]))
    assert dados["resumo"]["tarjados"] >= 3 and dados["resumo"]["fundamentacao"]


def test_relatorio_com_valores_so_sob_pedido_e_com_aviso(anon):
    r = anon.anonimizar("CPF 529.982.247-25")
    j = relatorio.para_json([r], incluir_valores=True)
    assert "529.982.247-25" in j and relatorio.AVISO_VALORES in j
    assert relatorio.AVISO_VALORES in relatorio.para_csv([r], incluir_valores=True)


def test_csv_do_relatorio_neutraliza_formulas():
    linha = relatorio._sem_formula({"a": "=HYPERLINK(\"http://x\")", "b": "+1", "c": "normal"})
    assert linha["a"].startswith("'=") and linha["b"].startswith("'+") and linha["c"] == "normal"


def test_xlsx_do_relatorio_abre(anon):
    import io

    import openpyxl

    r = anon.anonimizar("Maria Souza, CPF 529.982.247-25")
    wb = openpyxl.load_workbook(io.BytesIO(relatorio.para_xlsx([r])))
    assert {"Resumo", "Itens"} <= set(wb.sheetnames)


def test_cofre_reversao_com_senha():
    pytest.importorskip("cryptography")
    from themis_lgpd.cofre import criar_cofre, reverter

    texto = "Maria Aparecida Souza, CPF 529.982.247-25, pediu cópia."
    r = Anonimizador(modo="pseudonimo").anonimizar(texto)
    cofre = criar_cofre(r, "senha-bem-longa-123")
    assert b"529.982" not in cofre and b"Maria" not in cofre
    assert reverter(r.texto, cofre, "senha-bem-longa-123") == texto
    with pytest.raises(ValueError):
        reverter(r.texto, cofre, "senha-errada-000000")
    with pytest.raises(ValueError):
        criar_cofre(r, "curta")
