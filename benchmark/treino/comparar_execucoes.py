"""Comparação pareada de duas versões do sistema sobre os mesmos documentos.

Recebe os arquivos de ``--detalhes`` de duas execuções de ``benchmark/esic_ner.py`` (ou de
``benchmark/ouro.py``) e calcula, para cada métrica, a diferença entre a candidata e a base com:

* intervalo de confiança de 95% por *bootstrap pareado* (os mesmos documentos sorteados para as duas
  versões, 2.000 reamostragens, semente fixa);
* probabilidade, no *bootstrap*, de a candidata **não** ser melhor que a base (``p``): diferença ≤ 0
  em métricas em que maior é melhor (recall, preservação) e ≥ 0 nas demais (vazamento, tarja fora
  do gabarito);
* teste exato de McNemar sobre os documentos com vazamento (documentos que vazavam e deixaram de
  vazar contra os que passaram a vazar).

Uso::

    python benchmark/treino/comparar_execucoes.py base.jsonl candidata.jsonl [--json saida.json]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from esic_ner import agregadas  # noqa: E402

#: Métricas em que um valor menor é melhor.
MENOR_MELHOR = {"documentos_com_vazamento", "tarja_fora_do_gabarito", "precisao_erro"}


def ler(arquivo: Path) -> dict[str, dict]:
    return {d["chave"]: d for d in map(json.loads, arquivo.read_text(encoding="utf-8").splitlines()) if d}


def mcnemar(base: list[dict], cand: list[dict]) -> dict:
    """Teste exato de McNemar (bicaudal) sobre o vazamento por documento."""
    melhorou = sum(1 for b, c in zip(base, cand) if b["vazou"] and not c["vazou"])
    piorou = sum(1 for b, c in zip(base, cand) if not b["vazou"] and c["vazou"])
    n = melhorou + piorou
    if not n:
        return {"deixaram_de_vazar": 0, "passaram_a_vazar": 0, "p": 1.0}
    k = min(melhorou, piorou)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return {"deixaram_de_vazar": melhorou, "passaram_a_vazar": piorou, "p": round(p, 6)}


def comparar(base: dict[str, dict], cand: dict[str, dict], reamostragens: int = 2000,
             semente: int = 20261116) -> dict:
    """Diferenças, intervalos e significância (ver a descrição do módulo)."""
    chaves = sorted(set(base) & set(cand))
    if len(chaves) != len(base) or len(chaves) != len(cand):
        raise ValueError("as execuções não cobrem os mesmos documentos")
    b, c = [base[k] for k in chaves], [cand[k] for k in chaves]
    pontual_b, pontual_c = agregadas(b), agregadas(c)
    gerador = random.Random(semente)
    deltas = defaultdict(list)
    for _ in range(reamostragens):
        idx = [gerador.randrange(len(chaves)) for _ in chaves]
        mb, mc = agregadas([b[i] for i in idx]), agregadas([c[i] for i in idx])
        for nome in mb.keys() & mc.keys():
            deltas[nome].append(mc[nome] - mb[nome])
    saida = {"documentos": len(chaves), "metricas": {}, "mcnemar_vazamento": mcnemar(b, c)}
    for nome in sorted(pontual_b.keys() & pontual_c.keys()):
        valores = sorted(deltas[nome])
        if not valores:
            continue
        menor = nome in MENOR_MELHOR
        nao_melhor = sum(1 for v in valores if (v >= 0 if menor else v <= 0)) / len(valores)
        saida["metricas"][nome] = {
            "base": round(pontual_b[nome], 4), "candidata": round(pontual_c[nome], 4),
            "diferenca": round(pontual_c[nome] - pontual_b[nome], 4),
            "ic95": [round(valores[int(0.025 * len(valores))], 4), round(valores[int(0.975 * len(valores)) - 1], 4)],
            "p_nao_melhor": round(nao_melhor, 4),
        }
    return saida


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("base", type=Path)
    ap.add_argument("candidata", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    resultado = comparar(ler(args.base), ler(args.candidata))
    texto = json.dumps(resultado, ensure_ascii=False, indent=2)
    print(texto)
    if args.json:
        args.json.write_text(texto + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
