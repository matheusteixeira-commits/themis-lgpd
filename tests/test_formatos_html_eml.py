"""HTML (documentos do SEI) e mensagens de e-mail: casos adversariais."""

import base64
import email
import email.policy
import io
from email.message import EmailMessage
from pathlib import Path

import pytest

from apoio.odf import _jpeg_com_exif
from themis_lgpd.formatos import anonimizar_arquivo, detectar_formato
from themis_lgpd.formatos.email_eml import ENDERECO_RESERVADO, texto_eml
from themis_lgpd.formatos.midia import metadados_restantes

PROIBIDOS = ["529.982.247-25", "529&#46;982", "52998224725", "111.444.777-35", "Maria", "Aparecida",
             "Beatriz Helena", "Carlos Eduardo", "João Pereira", "joao.silva", "maria.souza", "99999-8888",
             "189.40.12.7"]

HTML = (
    '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="author" content="Beatriz Helena">'
    "<title>Despacho - Maria Aparecida Souza</title><script>var cpf = '529.982.247-25';</script></head>"
    '<body onload="enviar()"><p>Requerente: <b>Maria</b> Aparecida Souza, CPF 529&#46;982&#46;247&#45;25.</p>'
    '<p>Contato: <a href="mailto:joao.silva@gmail.com" title="E-mail de João Pereira Lima">clique</a>, '
    "telefone (61) 99999-8888.</p>"
    '<img alt="Foto de Maria Aparecida Souza" src="data:image/jpeg;base64,{foto}">'
    '<input type="hidden" name="cpf" value="111.444.777-35"><!-- revisado por Carlos Eduardo Lima -->'
    '<p><a href="https://www.gov.br/cgu">Portal da CGU</a> e '
    '<a href="https://exemplo.gov.br/consulta?cpf=52998224725">consulta</a>.</p></body></html>'
)


def _html() -> bytes:
    foto = base64.b64encode(_jpeg_com_exif("Maria Aparecida Souza")).decode()
    return HTML.replace("{foto}", foto).encode("utf-8")


@pytest.fixture(scope="module")
def html(anon_modulo):
    return anonimizar_arquivo(_html(), "despacho.html", anon_modulo, ocr=False)


@pytest.fixture(scope="module")
def anon_modulo():
    from themis_lgpd import Anonimizador

    return Anonimizador("lai")


def test_html_detectado():
    assert detectar_formato(_html(), "despacho.html") == "html"


def test_html_nada_vaza(html):
    texto = html.dados.decode("utf-8")
    for p in PROIBIDOS:
        assert p not in texto, p


def test_html_estrutura_e_links(html):
    texto = html.dados.decode("utf-8")
    assert "<script" not in texto and "onload" not in texto and "<!--" not in texto and 'name="author"' not in texto
    assert "[NOME]" in texto and "[CPF]" in texto and "Requerente:" in texto
    assert 'href="https://www.gov.br/cgu"' in texto and 'href="#"' in texto


def test_html_imagem_incorporada_sem_metadados(html):
    import re

    dados = base64.b64decode(re.search(r'src="data:image/\w+;base64,([^"]+)"', html.dados.decode()).group(1))
    assert metadados_restantes(dados) == []


def _eml() -> bytes:
    msg = EmailMessage()
    msg["From"] = "Maria Aparecida Souza <maria.souza@gmail.com>"
    msg["To"] = "Ouvidoria <ouvidoria@exemplo.gov.br>"
    msg["Subject"] = "Pedido de Maria Aparecida Souza - CPF 529.982.247-25"
    msg["Date"] = "Mon, 10 Nov 2026 10:00:00 -0300"
    msg["Message-ID"] = "<abc123@pc-de-maria.local>"
    msg["Received"] = "from pc-de-maria ([189.40.12.7]) by mx.exemplo.gov.br"
    msg["X-Originating-IP"] = "189.40.12.7"
    msg.set_content("Eu, Maria Aparecida Souza, CPF 529.982.247-25, telefone (61) 99999-8888, solicito cópia.",
                    cte="base64")
    msg.add_alternative("<p>Eu, <b>Maria</b> Aparecida Souza, CPF 529.982.247-25, solicito cópia.</p>",
                        subtype="html")
    msg.add_attachment(b"Laudo: Maria Aparecida Souza, CPF 111.444.777-35", maintype="text",
                       subtype="plain", filename="laudo de Maria Aparecida Souza.txt")
    docx = (Path(__file__).parents[1] / "exemplos" / "oficio_ficticio.docx").read_bytes()
    msg.add_attachment(docx, maintype="application",
                       subtype="vnd.openxmlformats-officedocument.wordprocessingml.document", filename="oficio.docx")
    return msg.as_bytes()


@pytest.fixture(scope="module")
def eml(anon_modulo):
    return anonimizar_arquivo(_eml(), "pedido.eml", anon_modulo, ocr=False)


def test_eml_detectado():
    assert detectar_formato(_eml(), "pedido.eml") == "eml"


def test_eml_nada_vaza(eml):
    texto = texto_eml(eml.dados)
    msg = email.message_from_bytes(eml.dados, policy=email.policy.default)
    for parte in msg.iter_attachments():
        texto += "\n" + (parte.get_payload(decode=True) or b"").decode("utf-8", "ignore")
    texto += "\n" + eml.dados.decode("utf-8", "ignore")
    for p in PROIBIDOS:
        assert p not in texto, p


def test_eml_cabecalhos_e_anexos(eml):
    msg = email.message_from_bytes(eml.dados, policy=email.policy.default)
    assert msg["Received"] is None and msg["X-Originating-IP"] is None and msg["Message-ID"] is None
    assert ENDERECO_RESERVADO in str(msg["From"]) and "[NOME]" in str(msg["From"])
    assert "[NOME]" in str(msg["Subject"]) and "[CPF]" in str(msg["Subject"])
    nomes = sorted(p.get_filename() for p in msg.iter_attachments())
    assert nomes == ["laudo de [NOME].txt", "oficio.docx"]
    assert "[CPF]" in str(msg["Subject"]) and "PROTOCOLO" not in str(msg["Subject"])
    docx = next(p for p in msg.iter_attachments() if p.get_filename().endswith(".docx")).get_payload(decode=True)
    from docx import Document

    texto_docx = "\n".join(par.text for par in Document(io.BytesIO(docx)).paragraphs)
    assert "João Pereira" not in texto_docx and "[CPF]" in texto_docx
