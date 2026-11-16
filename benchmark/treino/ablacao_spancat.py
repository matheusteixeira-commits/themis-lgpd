"""Ablação do classificador de trechos (``spancat``) na partição de seleção: sem o modelo × com o modelo.

Para cada par de limiares (dados de saúde, quase-identificadores) da grade informada, o Themis é
avaliado na partição ``selecao`` com o classificador acoplado ao pipeline, e o resultado por documento é
comparado, de forma pareada, com a execução sem o classificador (``comparar_execucoes.py``). Também é
medido o tempo por documento das duas configurações, nas mesmas condições.

Só métricas agregadas são produzidas: os textos da seleção não são lidos nem gravados.

A execução sem o classificador é feita em outro processo (``THEMIS_MODELO_SENSIVEL=0``), pois o pipeline do
spaCy é compartilhado dentro do processo. Os limiares do artefato não são alterados: a grade é aplicada
substituindo, só neste processo, os metadados lidos pelo reconhecedor.

Uso::

    python benchmark/treino/ablacao_spancat.py --saude 0.5 0.6 0.7 --quasi 0.5 [--saida ablacao.json]
        [--detalhes-dir pasta]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess  # noqa: S404 - executa benchmark/esic_ner.py sem o classificador  # nosec B404
import sys
import time
from pathlib import Path

PASTA = Path(__file__).parent
sys.path.insert(0, str(PASTA.parent))
sys.path.insert(0, str(PASTA))

from comparar_execucoes import comparar, ler  # noqa: E402
from esic_ner import metricas, trechos_themis  # noqa: E402
from particoes import carregar  # noqa: E402

#: Métricas resumidas da comparação pareada.
RESUMO = ("recall_entidades", "documentos_com_vazamento", "tarja_fora_do_gabarito", "recall:DADO_SAUDE",
          "recall:QUASI_IDENTIFICADOR")


def executar_base(destino: Path) -> dict:
    """Avalia a seleção sem o classificador, em outro processo; devolve as métricas."""
    ambiente = {**os.environ, "THEMIS_MODELO_SENSIVEL": "0"}
    saida_json = destino.with_suffix(".json")
    subprocess.run([sys.executable, str(PASTA.parent / "esic_ner.py"), "--particao", "selecao", "--sem-intervalos",  # noqa: S603
                    "--json", str(saida_json), "--detalhes", str(destino)], env=ambiente, check=True,
                   stdout=subprocess.DEVNULL, timeout=3600)  # nosec B603
    return json.loads(saida_json.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saude", type=float, nargs="+", required=True, help="limiares para DADO_SAUDE")
    ap.add_argument("--quasi", type=float, nargs="+", required=True, help="limiares para QUASI_IDENTIFICADOR")
    ap.add_argument("--saida", type=Path, default=PASTA / "ablacao_spancat.json")
    ap.add_argument("--detalhes-dir", type=Path, default=PASTA.parents[1] / ".trabalho" / "ablacao")
    args = ap.parse_args()
    args.detalhes_dir.mkdir(parents=True, exist_ok=True)

    base_docs = args.detalhes_dir / "selecao_sem_modelo.jsonl"
    base = executar_base(base_docs)

    os.environ["THEMIS_MODELO_SENSIVEL"] = "1"
    from themis_lgpd import Anonimizador
    from themis_lgpd.reconhecedores import aprendido

    meta_original = aprendido.metadados()
    if meta_original is None:
        raise SystemExit("artefato do classificador não encontrado")
    dados = carregar("selecao")
    textos = [d["text"] for d in dados]
    anon = Anonimizador(perfil="lai")
    resultados = []
    for saude in args.saude:
        for quasi in args.quasi:
            meta = {**meta_original, "limiares": {"DADO_SAUDE": saude, "QUASI_IDENTIFICADOR": quasi}}
            aprendido.metadados = lambda meta=meta: meta  # só neste processo
            t0 = time.perf_counter()
            trechos = trechos_themis(anon, textos)
            docs: list[dict] = []
            res, _ = metricas(dados, trechos, time.perf_counter() - t0, "Themis LGPD + classificador", docs)
            arq = args.detalhes_dir / f"selecao_saude{saude:g}_quasi{quasi:g}.jsonl"
            arq.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs), encoding="utf-8",
                           newline="\n")
            comp = comparar(ler(base_docs), ler(arq))
            item = {"limiares": {"DADO_SAUDE": saude, "QUASI_IDENTIFICADOR": quasi},
                    "recall_por_rotulo": res["recall_por_rotulo"], "recall_entidades": res["recall_entidades"],
                    "documentos_com_vazamento": res["documentos_com_vazamento"],
                    "tarja_fora_do_gabarito": res["tarja_fora_do_gabarito"],
                    "segundos_por_documento": res["segundos_por_documento"],
                    "comparacao": {k: comp["metricas"][k] for k in RESUMO if k in comp["metricas"]},
                    "perdas_por_rotulo": {k.split(":", 1)[1]: v["diferenca"] for k, v in comp["metricas"].items()
                                          if k.startswith("recall:") and v["diferenca"] < 0},
                    "mcnemar_vazamento": comp["mcnemar_vazamento"]}
            resultados.append(item)
            print(json.dumps(item, ensure_ascii=False), flush=True)
    saida = {"base": {k: base[k] for k in ("recall_entidades", "recall_por_rotulo", "documentos_com_vazamento",
                                           "tarja_fora_do_gabarito", "segundos_por_documento")},
             "artefato": {"limiares": meta_original["limiares"], "decodificacao": meta_original.get("decodificacao"),
                          "sha256_model": meta_original.get("sha256_model")},
             "grade": resultados}
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
