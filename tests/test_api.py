"""Testes da API HTTP: respostas, limites, autenticação e ausência de conteúdo em erros e logs."""

import importlib

import pytest
from fastapi.testclient import TestClient


def _cliente(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, str(v))
    import themis_lgpd.api.app as modulo

    modulo = importlib.reload(modulo)
    return TestClient(modulo.app)


@pytest.fixture
def cliente(monkeypatch):
    return _cliente(monkeypatch, THEMIS_LIMITE_REQ_MINUTO=1000)


def test_anonimizar_texto(cliente):
    r = cliente.post("/v1/anonimizar", json={"texto": "Maria Souza, CPF 529.982.247-25"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["texto_anonimizado"] == "[NOME], CPF [CPF]"
    assert "texto_original" not in corpo and all("valor" not in e for e in corpo["entidades"])
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
    assert "NOTA DE TARJAMENTO" in corpo["nota_de_tarjamento"]


def test_validacao_nao_ecoa_conteudo(cliente):
    r = cliente.post("/v1/anonimizar", json={"texto": "CPF 529.982.247-25", "perfil": "nao-existe"})
    assert r.status_code == 422 and "529.982" not in r.text


def test_limite_de_tamanho(monkeypatch):
    c = _cliente(monkeypatch, THEMIS_MAX_CARACTERES=50, THEMIS_MAX_MB=1, THEMIS_LIMITE_REQ_MINUTO=1000)
    assert c.post("/v1/anonimizar", json={"texto": "a" * 51}).status_code == 422
    grande = c.post("/v1/arquivos/anonimizar", files={"arquivo": ("a.txt", b"x" * (2 * 1024 * 1024))})
    assert grande.status_code == 413


def test_limite_de_requisicoes(monkeypatch):
    c = _cliente(monkeypatch, THEMIS_LIMITE_REQ_MINUTO=2)
    codigos = [c.post("/v1/anonimizar", json={"texto": "oi"}).status_code for _ in range(3)]
    assert codigos[:2] == [200, 200] and codigos[2] == 429


def test_chave_de_api(monkeypatch):
    c = _cliente(monkeypatch, THEMIS_CHAVES_API="segredo-1,segredo-2", THEMIS_LIMITE_REQ_MINUTO=1000)
    assert c.post("/v1/anonimizar", json={"texto": "oi"}).status_code == 401
    assert c.post("/v1/anonimizar", json={"texto": "oi"}, headers={"X-API-Key": "segredo-2"}).status_code == 200


def test_modo_demo_desliga_docs(monkeypatch):
    c = _cliente(monkeypatch, THEMIS_DEMO="true")
    assert c.get("/docs").status_code == 404
    assert c.get("/saude").json()["demo"] is True


def test_arquivo(cliente):
    r = cliente.post("/v1/arquivos/anonimizar", files={"arquivo": ("a.txt", b"Ana Lima, CPF 529.982.247-25")},
                     data={"perfil": "lai", "modo": "etiqueta"})
    assert r.status_code == 200 and r.content.decode() == "[NOME], CPF [CPF]"
    assert r.headers["x-themis-tarjados"] == "2"


def test_arquivo_invalido(cliente):
    r = cliente.post("/v1/arquivos/anonimizar", files={"arquivo": ("a.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")})
    assert r.status_code == 422


def test_erro_interno_nao_expoe_conteudo_na_resposta_nem_no_log(cliente, monkeypatch, caplog):
    from themis_lgpd.motor import Anonimizador

    def falhar(self, texto):
        raise ValueError(f"falha ao processar {texto}")

    monkeypatch.setattr(Anonimizador, "anonimizar", falhar)
    with caplog.at_level("DEBUG"):
        r = cliente.post("/v1/anonimizar", json={"texto": "Maria Souza, CPF 529.982.247-25"})
    assert r.status_code == 500 and "Maria" not in r.text and "529" not in r.text
    assert "Maria" not in caplog.text and "529" not in caplog.text


def test_filtro_de_log_do_servidor_reduz_excecao_ao_tipo():
    import logging
    import sys

    from themis_lgpd.api.app import _SemConteudo

    try:
        raise ValueError("Maria Souza 529.982.247-25")
    except ValueError:
        registro = logging.LogRecord("uvicorn.error", logging.ERROR, __file__, 1, "Exception in ASGI application",
                                     None, sys.exc_info())
    assert _SemConteudo().filter(registro)
    texto = logging.Formatter().format(registro)
    assert "Maria" not in texto and "529" not in texto and "ValueError" in texto


def test_rota_de_arquivos_valida_perfil_e_usa_formato_unico_de_erro(cliente):
    r = cliente.post("/v1/arquivos/anonimizar", files={"arquivo": ("a.txt", b"CPF 529.982.247-25")},
                     data={"perfil": "nao-existe"})
    assert r.status_code == 422 and "erro" in r.json() and "529" not in r.text
    invalido = cliente.post("/v1/arquivos/anonimizar", files={"arquivo": ("a.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")})
    assert invalido.status_code == 422 and "erro" in invalido.json()
