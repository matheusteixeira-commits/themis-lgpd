"""Avaliação no conjunto de referência independente (``benchmark/ouro``).

Como todo dado pessoal dos documentos está anotado (ver ``benchmark/ouro/DIRETRIZES.md``), além do
recall este conjunto mede a **precisão real**:

* **recall por rótulo** e **recall estrito**: mesmos critérios de ``benchmark/esic_ner.py``;
* **precisão das tarjas**: fração das tarjas do sistema que atingem algum dado pessoal anotado;
* **tarja fora do gabarito**: fração dos caracteres tarjados fora de todo dado pessoal anotado;
* **preservação de trechos públicos**: fração dos trechos que devem permanecer legíveis (órgãos,
  normas, programas) que ficaram intactos;
* **documentos com vazamento**: documentos com algum dado pessoal visível;
* **entidades não tarjadas, por causa**: *sinalizadas* (detectadas e enviadas à revisão, como
  manda o perfil) ou *não detectadas*, como em ``benchmark/esic_ner.py``.

Cada métrica acompanha o intervalo de confiança de 95% por *bootstrap* de documentos, e
``--detalhes`` grava o resultado por documento para a comparação pareada
(``benchmark/treino/comparar_execucoes.py``).

O conjunto é exclusivamente de avaliação: não examine erros nele para ajustar regras.

Uso::

    python benchmark/avaliar_ouro.py [ARQUIVOS.jsonl ...] [--perfil lai] [--json r.json] [--detalhes d.jsonl]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from esic_ner import chave, coberto, intervalos  # noqa: E402
from ouro.ferramentas import SO_ALERTA, ler, ocorrencias  # noqa: E402

from themis_lgpd import Anonimizador  # noqa: E402

PASTA = Path(__file__).parent / "ouro"


def avaliar_documento(d: dict, ents) -> dict:
    """Resultado de um documento a partir das entidades do sistema."""
    texto = d["texto"]
    mascara, revisao, pessoal = [False] * len(texto), [False] * len(texto), [False] * len(texto)
    for e in ents:
        for k in range(e.inicio, min(e.fim, len(texto))):
            revisao[k] = True
            mascara[k] = mascara[k] or e.acao == "tarjar"
    ocorr = {(e["tipo"], e["valor"]): ocorrencias(texto, e["valor"]) for e in d["entidades"]}
    for lista in ocorr.values():
        for a, b in lista:
            pessoal[a:b] = [True] * (b - a)
    total, prot, estr = Counter(), Counter(), Counter()
    sinalizadas, nao_detectadas = Counter(), Counter()
    vazou = False
    for (tipo, _valor), lista in ocorr.items():
        if not lista:
            continue
        total[tipo] += 1
        alvo = revisao if tipo in SO_ALERTA else mascara
        if all(coberto(texto, a, b, mascara, estrito=True) for a, b in lista):
            estr[tipo] += 1
        if all(coberto(texto, a, b, alvo) for a, b in lista):
            prot[tipo] += 1
            continue
        if all(coberto(texto, a, b, revisao) for a, b in lista):
            sinalizadas[tipo] += 1
        else:
            nao_detectadas[tipo] += 1
        vazou = vazou or tipo not in SO_ALERTA
    tarjas = [e for e in ents if e.acao == "tarjar"]
    tarjas_fora = sum(1 for e in tarjas if not any(pessoal[k] for k in range(e.inicio, min(e.fim, len(texto)))
                                                   if texto[k].isalnum()))
    chars = [k for k, m in enumerate(mascara) if m and texto[k].isalnum()]
    publicos = [(a, b) for p in d.get("publicos", []) for a, b in ocorrencias(texto, p)]
    return {
        "chave": chave(texto), "id": d["id"], "total": dict(total), "protegidas": dict(prot), "estritas": dict(estr),
        "tem_pii": bool(total), "vazou": vazou, "chars_tarjados": len(chars),
        "sinalizadas": dict(sinalizadas), "nao_detectadas": dict(nao_detectadas),
        "chars_fora": sum(1 for k in chars if not pessoal[k]),
        "tarjas_total": len(tarjas), "tarjas_fora": tarjas_fora,
        "publicos_total": len(publicos),
        "publicos_preservados": sum(1 for a, b in publicos if not any(mascara[a:b])),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivos", type=Path, nargs="*", help="padrão: todos os .jsonl congelados em benchmark/ouro")
    ap.add_argument("--perfil", default="lai")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--detalhes", type=Path)
    args = ap.parse_args()
    arquivos = args.arquivos or sorted(PASTA.glob("*.jsonl"))
    docs = [d for arq in arquivos for d in ler(arq)]
    anon = Anonimizador(perfil=args.perfil)
    t0 = time.perf_counter()
    analises = anon.analisar_lote([d["texto"] for d in docs])
    duracao = time.perf_counter() - t0
    detalhes = [avaliar_documento(d, ents) for d, ents in zip(docs, analises)]
    from esic_ner import agregadas

    pontual = agregadas(detalhes)
    total, sinalizadas, nao_detectadas = Counter(), Counter(), Counter()
    for x in detalhes:
        total.update(x["total"])
        sinalizadas.update(x["sinalizadas"])
        nao_detectadas.update(x["nao_detectadas"])
    resultado = {
        "sistema": f"Themis LGPD (perfil {args.perfil})", "documentos": len(docs),
        "arquivos": [Path(a).name for a in arquivos],
        "entidades_por_rotulo": dict(sorted(total.items())),
        **{k: round(v, 4) for k, v in sorted(pontual.items())},
        "nao_tarjadas": {k: {"sinalizadas": sinalizadas[k], "nao_detectadas": nao_detectadas[k]}
                         for k in sorted(set(sinalizadas) | set(nao_detectadas))},
        "segundos_por_documento": round(duracao / max(1, len(docs)), 4),
        "intervalos_95": intervalos(detalhes),
    }
    texto = json.dumps(resultado, ensure_ascii=False, indent=2)
    print(texto)
    if args.json:
        args.json.write_text(texto + "\n", encoding="utf-8", newline="\n")
    if args.detalhes:
        args.detalhes.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in detalhes),
                                 encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
