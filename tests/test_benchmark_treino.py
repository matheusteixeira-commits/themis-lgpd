"""Ferramentas de medição do ciclo de melhoria: partições, comparação pareada e conjunto de referência."""

import math
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "benchmark"))

from avaliar_ouro import avaliar_documento  # noqa: E402
from esic_ner import agregadas  # noqa: E402
from ouro.ferramentas import concordancia, ocorrencias, validar  # noqa: E402
from treino.comparar_execucoes import comparar, mcnemar  # noqa: E402
from treino.particoes import chave, particao_de  # noqa: E402


def test_particao_deterministica_e_proporcional():
    textos = [f"Pedido de informação número {i} sobre o programa." for i in range(2000)]
    assert [particao_de(t) for t in textos] == [particao_de(t) for t in textos]
    assert particao_de("Texto  QUALQUER") == particao_de("texto qualquer")  # duplicatas na mesma partição
    proporcao = sum(particao_de(t) == "selecao" for t in textos) / len(textos)
    assert 0.17 < proporcao < 0.23
    assert len(chave("x")) == 64


def _doc(i, vazou, protegidas=1):
    return {"chave": f"{i:064d}", "total": {"NOME_PESSOA": 1}, "protegidas": {"NOME_PESSOA": protegidas},
            "estritas": {}, "tem_pii": True, "vazou": vazou, "chars_tarjados": 10, "chars_fora": 1}


def test_mcnemar_exato():
    base = [_doc(i, i < 10) for i in range(40)]
    cand = [_doc(i, i in (0, 1) or i == 39) for i in range(40)]  # 8 deixaram de vazar, 1 passou a vazar
    r = mcnemar(base, cand)
    esperado = 2 * sum(math.comb(9, k) for k in range(2)) / 2 ** 9
    assert r["deixaram_de_vazar"] == 8 and r["passaram_a_vazar"] == 1 and math.isclose(r["p"], round(esperado, 6))


def test_comparacao_pareada_detecta_melhora():
    base = {d["chave"]: d for d in (_doc(i, i < 20, protegidas=0 if i < 20 else 1) for i in range(100))}
    cand = {d["chave"]: d for d in (_doc(i, False) for i in range(100))}
    r = comparar(base, cand, reamostragens=300)
    m = r["metricas"]["recall_entidades"]
    assert m["diferenca"] == 0.2 and m["ic95"][0] > 0 and m["p_nao_melhor"] == 0.0
    assert r["metricas"]["documentos_com_vazamento"]["diferenca"] == -0.2


def test_ocorrencias_por_palavra_inteira_e_validacao():
    assert ocorrencias("Ana e Banana", "Ana") == [(0, 3)]
    docs = [{"id": "X-1", "texto": "Maria pediu à Secretaria.", "entidades": [{"tipo": "NOME_PESSOA", "valor": "Maria"},
                                                                               {"tipo": "CPF", "valor": "123"}],
             "publicos": ["Secretaria", "Prefeitura"]}]
    problemas = validar(docs)
    assert any("rótulo desconhecido" in p for p in problemas)
    assert any("'123'" in p for p in problemas) and any("Prefeitura" in p for p in problemas)


def test_concordancia_entre_anotadores():
    a = [{"id": "1", "entidades": [{"tipo": "NOME_PESSOA", "valor": "Maria"}, {"tipo": "CONTATO", "valor": "x@y.br"}]}]
    b = [{"id": "1", "entidades": [{"tipo": "NOME_PESSOA", "valor": "Maria"}, {"tipo": "DOC_PESSOAL", "valor": "x@y.br"}]}]
    r, divergencias = concordancia(a, b)
    assert r["f1_por_valor"] == 1.0 and r["f1_por_rotulo"] == 0.5 and len(divergencias) == 1


def test_precisao_e_preservacao_no_conjunto_de_referencia():
    texto = "A Secretaria de Saúde atendeu Maria Souza no Hospital Regional."
    d = {"id": "R-1", "texto": texto, "entidades": [{"tipo": "NOME_PESSOA", "valor": "Maria Souza"}],
         "publicos": ["Secretaria de Saúde", "Hospital Regional"]}

    def ent(trecho, acao="tarjar"):
        inicio = texto.index(trecho)
        return SimpleNamespace(inicio=inicio, fim=inicio + len(trecho), acao=acao)

    r = avaliar_documento(d, [ent("Maria Souza"), ent("Hospital Regional")])
    assert r["protegidas"] == {"NOME_PESSOA": 1} and not r["vazou"]
    assert r["tarjas_total"] == 2 and r["tarjas_fora"] == 1
    assert r["publicos_total"] == 2 and r["publicos_preservados"] == 1
    m = agregadas([r])
    assert m["precisao_tarjas"] == 0.5 and m["preservacao_publicos"] == 0.5
    assert avaliar_documento(d, [ent("Maria Souza", "alertar")])["vazou"]


def test_erros_por_documento_e_recusa_fora_do_ajuste(tmp_path):
    import pytest
    from avaliar_ouro import PASTA, _somente_ajuste, erros_documento

    texto = "A Secretaria de Saúde atendeu Maria Souza no Hospital Regional."
    d = {"id": "R-1", "texto": texto, "entidades": [{"tipo": "NOME_PESSOA", "valor": "Maria Souza"}],
         "publicos": ["Hospital Regional"]}
    inicio = texto.index("Hospital Regional")
    r = erros_documento(d, [SimpleNamespace(inicio=inicio, fim=inicio + 17, acao="tarjar", tipo="NOME")])
    assert r["vazou"] and r["nao_protegidas"][0]["situacao"] == "nao_detectada"
    assert r["tarjas_fora"][0]["trecho"] == "Hospital Regional" and len(r["publicos_tarjados"]) == 1
    _somente_ajuste([tmp_path / "ajuste.jsonl"])
    for proibido in (PASTA / "ouro_a.jsonl", tmp_path / "selecao.jsonl", PASTA / "ajuste.jsonl"):
        with pytest.raises(SystemExit):
            _somente_ajuste([proibido])
