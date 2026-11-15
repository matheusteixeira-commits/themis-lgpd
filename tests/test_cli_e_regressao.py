"""Testes da linha de comando e casos de regressão do conjunto de casos difíceis."""

import json
from collections import Counter
from pathlib import Path

from themis_lgpd import Anonimizador
from themis_lgpd.cli import main

DADOS = Path(__file__).parent / "data" / "casos_dificeis_participa.jsonl"


def test_cli_anonimiza_arquivo_e_gera_relatorio(tmp_path, capsys):
    entrada = tmp_path / "pedido.txt"
    entrada.write_text("Eu, Maria Aparecida Souza, CPF 529.982.247-25, solicito cópia.", encoding="utf-8")
    rel = tmp_path / "relatorio.json"
    assert main(["anonimizar", str(entrada), "-r", str(rel)]) == 0
    saida = (tmp_path / "pedido_anonimizado.txt").read_text(encoding="utf-8")
    assert saida == "Eu, [NOME], CPF [CPF], solicito cópia."
    assert json.loads(rel.read_text(encoding="utf-8"))["resumo"]["tarjados"] == 2
    assert "529" not in rel.read_text(encoding="utf-8")


def test_cli_nao_sobrescreve_entrada(tmp_path):
    entrada = tmp_path / "a.txt"
    entrada.write_text("CPF 529.982.247-25", encoding="utf-8")
    assert main(["anonimizar", str(entrada), "-o", str(entrada)]) == 1
    assert entrada.read_text(encoding="utf-8") == "CPF 529.982.247-25"


def test_cli_perfis(capsys):
    assert main(["perfis"]) == 0
    assert "lai" in capsys.readouterr().out


def test_casos_dificeis_do_projeto_original_identificadores():
    """1.000 casos do hackathon: todo identificador direto precisa ser tarjado (perfil LAI)."""
    casos = [json.loads(linha) for linha in DADOS.read_text(encoding="utf-8").splitlines()]
    casos = [c for c in casos if c["cat"] in {"GDF_DOCUMENTOS", "LGPD_PESSOAL"}]
    resultados = Anonimizador().anonimizar_lote([c["text"] for c in casos])
    falhas = [c["text"] for c, r in zip(casos, resultados) if not r.tarjadas]
    assert falhas == [], falhas[:10]


def test_casos_dificeis_sem_dados_nao_sao_tarjados():
    casos = [json.loads(linha) for linha in DADOS.read_text(encoding="utf-8").splitlines()]
    negativos = [c["text"] for c in casos if not c["expected"]]
    resultados = Anonimizador().anonimizar_lote(negativos)
    assert [r.texto for r in resultados if r.tarjadas] == []


def test_casos_dificeis_cobertura_minima_perfil_maximo():
    casos = [json.loads(linha) for linha in DADOS.read_text(encoding="utf-8").splitlines() if '"expected": []' not in linha]
    resultados = Anonimizador("maxima").anonimizar_lote([c["text"] for c in casos])
    cobertos = Counter(c["cat"] for c, r in zip(casos, resultados) if r.tarjadas)
    total = Counter(c["cat"] for c in casos)
    assert sum(cobertos.values()) / sum(total.values()) >= 0.80, dict(cobertos)
