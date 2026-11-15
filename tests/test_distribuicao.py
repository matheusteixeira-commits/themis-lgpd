"""Distribuição: versão em fonte única, README publicável no PyPI e verificação de saúde do contêiner."""

import http.server
import importlib.metadata
import re
import threading
from pathlib import Path

import pytest

from themis_lgpd import __version__
from themis_lgpd.cli import main

RAIZ = Path(__file__).resolve().parents[1]


def test_versao_em_fonte_unica():
    assert importlib.metadata.version("themis-lgpd") == __version__
    assert 'dynamic = ["version"]' in (RAIZ / "pyproject.toml").read_text(encoding="utf-8")


def test_readme_sem_links_relativos():
    """A página do PyPI exibe o README fora do repositório: links relativos ficariam quebrados."""
    texto = (RAIZ / "README.md").read_text(encoding="utf-8")
    relativos = re.findall(r"\]\((?!https?://|#|mailto:)([^)\s]+)\)", texto)
    assert relativos == []


@pytest.fixture
def servidor_local():
    class Saudavel(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - interface do http.server
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Saudavel)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/saude"
    srv.shutdown()


def test_saude_responde(servidor_local):
    assert main(["saude", "--url", servidor_local]) == 0


def test_saude_sem_servico():
    assert main(["saude", "--url", "http://127.0.0.1:9/saude", "--tempo", "0.5"]) == 1


def test_saude_so_consulta_enderecos_locais():
    assert main(["saude", "--url", "http://exemplo.gov.br/saude"]) == 1


def test_imagem_docker_usa_a_verificacao_e_dispensa_o_rapidocr():
    dockerfile = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
    assert 'CMD ["themis", "saude"]' in dockerfile
    assert "grep -vE '^(rapidocr|onnxruntime)=='" in dockerfile


def test_composicao_inclui_a_api():
    compose = (RAIZ / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")
    assert re.search(r"\n  api:\n(?:    .*\n)*?    profiles: \[\"api\"\]", compose)
    assert '"api", "--endereco", "0.0.0.0"' in compose
