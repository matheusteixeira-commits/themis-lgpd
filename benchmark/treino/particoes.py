"""Partições do conjunto esic-ner para o ciclo de melhoria, reprodutíveis e sem sobreposição.

* ``ajuste`` (≈80% da partição ``train`` do conjunto): análise de erros, criação de regras e
  treinamento de modelos;
* ``selecao`` (≈20% de ``train``): escolha entre alternativas e limiares. Os erros desta partição
  não são examinados um a um — só as métricas agregadas —, para que ela continue medindo
  generalização;
* ``lockbox`` (a partição ``test`` do conjunto): avaliação final. Cada uso é registrado em
  ``registro_lockbox.jsonl`` com o motivo e o commit (ver ``benchmark/esic_ner.py --lockbox``).

A atribuição usa o SHA-256 do texto normalizado (espaços colapsados, minúsculas): é determinística,
não depende de semente aleatória e coloca duplicatas na mesma partição. Nenhum texto de ``train``
coincide com um de ``test`` (verificado ao gerar ``particoes.json``).

Uso::

    python benchmark/treino/particoes.py   # (re)gera particoes.json e confere as contagens
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

PASTA = Path(__file__).parent
ARQUIVO = PASTA / "particoes.json"
REGISTRO_LOCKBOX = PASTA / "registro_lockbox.jsonl"
#: Um em cada ``DIVISOR`` documentos de ``train`` vai para a seleção.
DIVISOR = 5


def chave(texto: str) -> str:
    """Identificador estável do documento: SHA-256 do texto normalizado."""
    return hashlib.sha256(" ".join(texto.split()).lower().encode("utf-8")).hexdigest()


def particao_de(texto: str) -> str:
    """``selecao`` ou ``ajuste``, pelo resumo do texto."""
    return "selecao" if int(chave(texto)[:8], 16) % DIVISOR == 0 else "ajuste"


def carregar(nome: str) -> list[dict]:
    """Documentos da partição ``ajuste`` ou ``selecao``.

    Raises:
        ValueError: Partição desconhecida (a ``lockbox`` é carregada por ``esic_ner.carregar("test")``).
        RuntimeError: O arquivo de ``train`` baixado difere do usado para gerar as partições.
    """
    sys.path.insert(0, str(PASTA.parent))
    from esic_ner import CACHE
    from esic_ner import carregar as carregar_split

    if nome not in ("ajuste", "selecao"):
        raise ValueError("partição deve ser 'ajuste' ou 'selecao'")
    dados = carregar_split("train")
    registro = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    resumo = hashlib.sha256((CACHE / "esic-ner-train.jsonl").read_bytes()).hexdigest()
    if resumo != registro["sha256_train"]:
        raise RuntimeError("o arquivo esic-ner-train.jsonl difere do usado para gerar as partições")
    excluidos = set(registro["contaminados"])
    return [d for d in dados if particao_de(d["text"]) == nome and chave(d["text"]) not in excluidos]


def main() -> None:
    """Gera ``particoes.json`` com os resumos dos arquivos e as contagens de cada partição."""
    sys.path.insert(0, str(PASTA.parent))
    from esic_ner import CACHE
    from esic_ner import carregar as carregar_split

    treino, teste = carregar_split("train"), carregar_split("test")
    chaves_teste = {chave(d["text"]) for d in teste}
    contaminados = sorted({chave(d["text"]) for d in treino} & chaves_teste)
    contagem: dict[str, Counter] = {"ajuste": Counter(), "selecao": Counter()}
    documentos = Counter()
    for d in treino:
        if chave(d["text"]) in contaminados:
            continue
        p = particao_de(d["text"])
        documentos[p] += 1
        contagem[p].update(e["type"] for e in d["entities"])
    registro = {
        "versao": 1,
        "sha256_train": hashlib.sha256((CACHE / "esic-ner-train.jsonl").read_bytes()).hexdigest(),
        "sha256_test": hashlib.sha256((CACHE / "esic-ner-test.jsonl").read_bytes()).hexdigest(),
        "documentos": dict(documentos) | {"lockbox": len(teste)},
        "entidades": {p: dict(sorted(c.items())) for p, c in contagem.items()},
        "contaminados": contaminados,
    }
    ARQUIVO.write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in registro.items() if k != "contaminados"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
