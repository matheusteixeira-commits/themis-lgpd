"""API: opções completas na rota de arquivos, relatório em JSON, tarefas assíncronas, configuração do
órgão, processos de trabalho e especificação OpenAPI versionada."""

import base64
import importlib
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[1]
CPF = "529.982.247-25"


def _modulo(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, str(v))
    import themis_lgpd.api.app as modulo

    return importlib.reload(modulo)


@pytest.fixture
def api(monkeypatch):
    modulo = _modulo(monkeypatch, THEMIS_LIMITE_REQ_MINUTO=1000, THEMIS_USAR_NER=0)
    with TestClient(modulo.app) as cliente:
        yield modulo, cliente


def _arquivo(texto: str, nome: str = "pedido.txt"):
    return {"arquivo": (nome, texto.encode("utf-8"), "text/plain")}


def _aguardar(cliente, id_tarefa: str, headers=None) -> dict:
    for _ in range(300):
        corpo = cliente.get(f"/v1/tarefas/{id_tarefa}", headers=headers).json()
        if corpo["situacao"] in {"concluida", "falhou"}:
            return corpo
        time.sleep(0.1)
    raise AssertionError("tarefa não terminou")


def test_rota_de_arquivos_com_opcoes_e_relatorio_em_json(api):
    _, cliente = api
    texto = f"Atendido no Hospital Regional de Taguatinga. CPF {CPF}. Código interno ZX-991."
    r = cliente.post("/v1/arquivos/anonimizar", files=_arquivo(texto),
                     data={"permitir": ["Hospital Regional de Taguatinga"], "bloquear": ["ZX-991"], "resposta": "json"})
    assert r.status_code == 200
    corpo = r.json()
    saida = base64.b64decode(corpo["conteudo_base64"]).decode("utf-8")
    assert "Hospital Regional de Taguatinga" in saida and CPF not in saida and "ZX-991" not in saida
    assert corpo["tarjados"] == 2 and corpo["relatorio"]["resumo"]["tarjados"] == 2
    assert "NOTA DE TARJAMENTO" in corpo["nota_de_tarjamento"]
    assert all("valor_original" not in i for i in corpo["relatorio"]["itens"])


def test_rota_de_arquivos_coluna_integral(api):
    _, cliente = api
    csv = "processo;observacao\n123;texto livre sem padrao\n"
    r = cliente.post("/v1/arquivos/anonimizar", files=_arquivo(csv, "base.csv"), data={"coluna_integral": ["observacao"]})
    assert r.status_code == 200 and "texto livre" not in r.content.decode("utf-8-sig")


def test_rota_de_arquivos_rejeita_opcao_invalida_sem_ecoar(api):
    _, cliente = api
    r = cliente.post("/v1/arquivos/anonimizar", files=_arquivo(f"CPF {CPF}"), data={"perfil": "inexistente"})
    assert r.status_code == 422 and CPF not in r.text


def test_tarefa_assincrona_ciclo_completo(api):
    modulo, cliente = api
    r = cliente.post("/v1/tarefas", files=_arquivo(f"Requerente com CPF {CPF}."))
    assert r.status_code == 202
    id_tarefa = r.json()["id"]
    assert len(id_tarefa) >= 32
    estado = _aguardar(cliente, id_tarefa)
    assert estado["situacao"] == "concluida" and estado["tarjados"] == 1 and CPF not in str(estado)
    baixado = cliente.get(f"/v1/tarefas/{id_tarefa}/resultado")
    assert baixado.status_code == 200 and "[CPF]" in baixado.content.decode("utf-8")
    # O resultado é apagado da memória após o download.
    assert cliente.get(f"/v1/tarefas/{id_tarefa}/resultado").status_code == 404
    assert id_tarefa not in modulo._TAREFAS


def test_tarefa_que_falha_informa_o_motivo(api):
    _, cliente = api
    r = cliente.post("/v1/tarefas", files=_arquivo("isto não é um PDF", "renomeado.pdf"))
    estado = _aguardar(cliente, r.json()["id"])
    assert estado["situacao"] == "falhou" and "extensão .pdf" in estado["mensagem"]


def test_resultado_expira(api):
    modulo, cliente = api
    id_tarefa = cliente.post("/v1/tarefas", files=_arquivo(f"CPF {CPF}")).json()["id"]
    _aguardar(cliente, id_tarefa)
    modulo._TAREFAS[id_tarefa].concluida_em -= modulo.CFG.tarefa_ttl_s + 1
    assert cliente.get(f"/v1/tarefas/{id_tarefa}").status_code == 404
    assert id_tarefa not in modulo._TAREFAS


def test_tarefa_so_e_acessivel_pela_chave_que_a_criou(monkeypatch):
    modulo = _modulo(monkeypatch, THEMIS_LIMITE_REQ_MINUTO=1000, THEMIS_USAR_NER=0, THEMIS_CHAVES_API="chave-a,chave-b")
    with TestClient(modulo.app) as cliente:
        id_tarefa = cliente.post("/v1/tarefas", files=_arquivo(f"CPF {CPF}"), headers={"X-API-Key": "chave-a"}).json()["id"]
        _aguardar(cliente, id_tarefa, headers={"X-API-Key": "chave-a"})
        assert cliente.get(f"/v1/tarefas/{id_tarefa}/resultado", headers={"X-API-Key": "chave-b"}).status_code == 404
        assert cliente.get(f"/v1/tarefas/{id_tarefa}/resultado", headers={"X-API-Key": "chave-a"}).status_code == 200


def test_limite_de_tarefas(monkeypatch):
    modulo = _modulo(monkeypatch, THEMIS_LIMITE_REQ_MINUTO=1000, THEMIS_USAR_NER=0, THEMIS_MAX_TAREFAS=1)
    with TestClient(modulo.app) as cliente:
        assert cliente.post("/v1/tarefas", files=_arquivo("texto")).status_code == 202
        assert cliente.post("/v1/tarefas", files=_arquivo("texto")).status_code == 503


def test_apagar_tarefa(api):
    _, cliente = api
    id_tarefa = cliente.post("/v1/tarefas", files=_arquivo(f"CPF {CPF}")).json()["id"]
    _aguardar(cliente, id_tarefa)
    assert cliente.delete(f"/v1/tarefas/{id_tarefa}").status_code == 204
    assert cliente.get(f"/v1/tarefas/{id_tarefa}").status_code == 404


def test_configuracao_do_orgao_na_api(monkeypatch):
    modulo = _modulo(monkeypatch, THEMIS_LIMITE_REQ_MINUTO=1000, THEMIS_USAR_NER=0,
                     THEMIS_CONFIG=RAIZ / "exemplos" / "orgao.toml")
    with TestClient(modulo.app) as cliente:
        perfis = cliente.get("/v1/perfis").json()
        assert perfis["padrao"] == "ouvidoria_estadual"
        assert "ouvidoria_estadual" in [p["nome"] for p in perfis["perfis"]]
        r = cliente.post("/v1/anonimizar", json={"texto": "O adolescente do PSE nº 2024/00123 foi ouvido."})
        assert "2024/00123" not in r.json()["texto_anonimizado"]
        assert cliente.get("/saude").json()["configuracao_do_orgao"] is True


def test_configuracao_invalida_impede_o_inicio(monkeypatch, tmp_path):
    arq = tmp_path / "orgao.toml"
    arq.write_text('[padrao]\nperfil = "nenhum"\n', encoding="utf-8")
    from themis_lgpd.configuracao import ConfiguracaoInvalida

    with pytest.raises(ConfiguracaoInvalida):
        _modulo(monkeypatch, THEMIS_CONFIG=arq)
    monkeypatch.delenv("THEMIS_CONFIG")
    _modulo(monkeypatch)  # restaura o módulo para os demais testes


def test_processos_de_trabalho(monkeypatch):
    modulo = _modulo(monkeypatch, THEMIS_LIMITE_REQ_MINUTO=1000, THEMIS_USAR_NER=0, THEMIS_PROCESSOS=2)
    try:
        with TestClient(modulo.app) as cliente:
            r = cliente.post("/v1/anonimizar", json={"texto": f"CPF {CPF}"})
            assert r.status_code == 200 and r.json()["texto_anonimizado"] == "CPF [CPF]"
            assert modulo._POOL is not None and cliente.get("/saude").json()["processos"] == 2
    finally:
        if modulo._POOL is not None:
            modulo._POOL.shutdown()


def test_openapi_versionado_esta_sincronizado():
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "gerar_openapi.py"), "--verificar"],  # noqa: S603
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
