"""Partições do corpus de desenvolvimento de documentos oficiais.

Os lotes anotados (``lotes/*.jsonl``, mesmas diretrizes e mesmo formato do conjunto de referência,
ver ``benchmark/ouro/DIRETRIZES.md``) são divididos pela mesma regra do esic-ner
(``benchmark/treino/particoes.py``: SHA-256 do texto normalizado, um em cada cinco documentos na
seleção):

* ``ajuste.jsonl``: análise de erros (``benchmark/avaliar_ouro.py --erros``) e treinamento;
* ``selecao.jsonl``: escolha entre alternativas, só por métricas agregadas.

O conjunto de referência congelado (``benchmark/ouro``) continua reservado à avaliação.

Uso::

    python benchmark/oficial/particionar.py   # valida os lotes e (re)gera as duas partições
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

PASTA = Path(__file__).parent
sys.path.insert(0, str(PASTA.parent))

from ouro.ferramentas import ler, validar  # noqa: E402
from treino.particoes import particao_de  # noqa: E402


def main() -> None:
    lotes = sorted((PASTA / "lotes").glob("*.jsonl"))
    docs = [d for arq in lotes for d in ler(arq)]
    problemas = validar(docs)
    if problemas:
        raise SystemExit("\n".join(problemas))
    particoes = {"ajuste": [], "selecao": []}
    for d in docs:
        particoes[particao_de(d["texto"])].append(d)
    registro = {"lotes": [arq.name for arq in lotes]}
    for nome, lista in particoes.items():
        arquivo = PASTA / f"{nome}.jsonl"
        arquivo.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in lista),
                           encoding="utf-8", newline="\n")
        registro[nome] = {
            "documentos": len(lista), "sha256": hashlib.sha256(arquivo.read_bytes()).hexdigest(),
            "entidades": dict(sorted(Counter(e["tipo"] for d in lista for e in d["entidades"]).items())),
        }
    (PASTA / "PARTICOES.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8", newline="\n")
    print(json.dumps(registro, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
