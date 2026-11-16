"""Portão de não regressão nas partições de seleção, só com métricas agregadas.

As partições de seleção (do esic-ner e do corpus de documentos oficiais) servem para escolher entre
alternativas e não podem ser examinadas documento a documento. Durante o desenvolvimento, este script
é a via de acesso a elas: avalia o sistema importado (``PYTHONPATH``) nas duas seleções, compara de
forma pareada com a execução de referência (``benchmark/treino/comparar_execucoes.py``) e devolve só
as métricas agregadas, as diferenças com intervalo de confiança e o veredito de cada portão. Nenhum
resultado por documento é exibido ou gravado.

Cada consulta é registrada (data, diretório, commit, motivo e veredito) no arquivo de ``--registro``.
O número de consultas por ciclo é limitado, o que reduz o sobreajuste adaptativo à seleção.

Portões (diferença em relação à referência):

* esic-ner, seleção: nenhum rótulo perde mais de 0,5 ponto de recall e a tarja fora do gabarito não
  sobe mais de 0,5 ponto;
* documentos oficiais, seleção: a precisão das tarjas e a preservação de trechos públicos não caem
  mais de 0,5 ponto e nenhum rótulo perde mais de 1 ponto de recall.

Uso::

    python benchmark/treino/portao.py --motivo TEXTO --registro ARQUIVO.jsonl
        [--referencia benchmark/treino/ciclo2] [--selecao-oficial benchmark/oficial/selecao.jsonl]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PASTA = Path(__file__).parent
RAIZ = PASTA.parents[1]
sys.path.insert(0, str(PASTA.parent))
sys.path.insert(0, str(PASTA))

from avaliar_ouro import avaliar_documento  # noqa: E402
from comparar_execucoes import comparar, ler  # noqa: E402
from esic_ner import metricas, trechos_themis  # noqa: E402
from ouro.ferramentas import ler as ler_oficial  # noqa: E402
from particoes import carregar  # noqa: E402

#: Tolerâncias por corpus: perda máxima de recall por rótulo e variação máxima das demais métricas.
TOLERANCIAS = {
    "esic_selecao": {"recall": 0.005, "tarja_fora_do_gabarito": 0.005},
    "oficial_selecao": {"recall": 0.01, "precisao_tarjas": 0.005, "preservacao_publicos": 0.005},
}
#: Arquivo de resultado por documento da referência, por corpus.
REFERENCIAS = {"esic_selecao": "selecao_docs.jsonl", "oficial_selecao": "oficial_selecao_docs.jsonl"}


def vereditos(corpus: str, comparacao: dict) -> list[str]:
    """Portões reprovados de um corpus (lista vazia quando todos passam)."""
    tol = TOLERANCIAS[corpus]
    falhas = []
    for nome, m in comparacao["metricas"].items():
        if nome.startswith("recall:") and m["diferenca"] < -tol["recall"]:
            falhas.append(f"{corpus}: {nome} caiu {-m['diferenca']:.4f}")
    for nome in ("tarja_fora_do_gabarito",):
        if nome in tol and comparacao["metricas"][nome]["diferenca"] > tol[nome]:
            falhas.append(f"{corpus}: {nome} subiu {comparacao['metricas'][nome]['diferenca']:.4f}")
    for nome in ("precisao_tarjas", "preservacao_publicos"):
        if nome in tol and comparacao["metricas"][nome]["diferenca"] < -tol[nome]:
            falhas.append(f"{corpus}: {nome} caiu {-comparacao['metricas'][nome]['diferenca']:.4f}")
    return falhas


def _esic(anon) -> list[dict]:
    dados = carregar("selecao")
    docs: list[dict] = []
    metricas(dados, trechos_themis(anon, [d["text"] for d in dados]), 0.0, "", docs)
    return docs


def _oficial(anon, arquivo: Path) -> list[dict]:
    docs = ler_oficial(arquivo)
    return [avaliar_documento(d, ents) for d, ents in zip(docs, anon.analisar_lote([d["texto"] for d in docs]))]


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,  # noqa: S607
                              cwd=RAIZ, timeout=20, check=False).stdout.strip()  # nosec B603 B607
    except OSError:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--motivo", required=True, help="o que está sendo verificado (vai para o registro)")
    ap.add_argument("--registro", type=Path, required=True, help="arquivo JSONL de registro das consultas")
    ap.add_argument("--referencia", type=Path, default=PASTA / "ciclo2")
    ap.add_argument("--selecao-oficial", type=Path, default=RAIZ / "benchmark" / "oficial" / "selecao.jsonl")
    args = ap.parse_args()

    from themis_lgpd import Anonimizador

    anon = Anonimizador(perfil="lai")
    execucoes = {"esic_selecao": _esic(anon), "oficial_selecao": _oficial(anon, args.selecao_oficial)}
    resultado, falhas = {}, []
    for corpus, docs in execucoes.items():
        comparacao = comparar(ler(args.referencia / REFERENCIAS[corpus]), {d["chave"]: d for d in docs})
        resultado[corpus] = comparacao
        falhas += vereditos(corpus, comparacao)
    resultado["aprovado"] = not falhas
    resultado["falhas"] = falhas
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    linha = {"data": datetime.now(UTC).isoformat(timespec="seconds"), "diretorio": str(RAIZ), "commit": _commit(),
             "motivo": args.motivo, "aprovado": not falhas, "falhas": falhas,
             **{f"{c}:{m}": resultado[c]["metricas"][m]["candidata"]
                for c in execucoes for m in ("recall_entidades", "precisao_tarjas", "tarja_fora_do_gabarito")
                if m in resultado[c]["metricas"]}}
    args.registro.parent.mkdir(parents=True, exist_ok=True)
    with args.registro.open("a", encoding="utf-8", newline="\n") as arq:
        arq.write(json.dumps(linha, ensure_ascii=False) + "\n")
    sys.exit(0 if not falhas else 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
