"""Avaliação no conjunto público EliMC/esic-ner (pedidos de acesso à informação sintéticos, CC-BY-4.0).

Métricas calculadas:

* **Recall por rótulo**: fração das entidades pessoais anotadas cujas ocorrências estão
  integralmente cobertas pela tarja. Em identificadores, basta que todos os dígitos estejam
  cobertos — a palavra-chave anotada junto ("SIAPE 1984235") pode ficar visível. O *recall
  estrito* exige toda letra e todo dígito cobertos.
* **Documentos com vazamento**: fração dos pedidos com dado pessoal em que ao menos uma entidade
  ficou visível. É a métrica mais próxima do risco real de publicação.
* **Entidades não tarjadas, por causa**: as que ficaram visíveis se dividem em *sinalizadas para
  revisão* (detectadas, mas que o perfil manda revisar em vez de tarjar — o revisor as vê
  destacadas) e *não detectadas* (nenhum aviso: o risco que depende só da atenção humana).

Para ajustar regras use a partição ``train``; a ``test`` fica reservada para os números publicados.
* **Triagem** (o pedido contém dado pessoal?): precisão, recall e F1, comparáveis aos publicados
  para o BR-Access-NER no mesmo conjunto.
* **Tarja fora do gabarito**: fração dos caracteres tarjados que não pertencem a nenhuma entidade
  anotada. É um indicador aproximado de excesso de tarja, pois o gabarito não anota todo dado
  pessoal presente.

O conjunto é baixado do Hugging Face na primeira execução e mantido em ``benchmark/.cache``.

Uso::

    python benchmark/esic_ner.py [--split test] [--perfil lai] [--limite N] [--erros 20] [--json saida.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from themis_lgpd import Anonimizador

URL = "https://huggingface.co/datasets/EliMC/esic-ner/resolve/main/{split}.jsonl"
#: Rótulos do gabarito que não são dado pessoal (pessoa jurídica) e ficam fora do recall.
NAO_PESSOAIS = {"ORG_JURIDICA", "DOC_EMPRESA"}
#: Rótulos que o perfil LAI sinaliza para revisão em vez de tarjar: contam como protegidos quando
#: sinalizados, e sua ausência de tarja não é contada como vazamento.
SO_ALERTA = {"QUASI_IDENTIFICADOR"}
CACHE = Path(__file__).parent / ".cache"


def carregar(split: str) -> list[dict]:
    """Documentos da partição ``split`` (``train`` ou ``test``), com cache local."""
    CACHE.mkdir(exist_ok=True)
    arq = CACHE / f"esic-ner-{split}.jsonl"
    if not arq.exists():
        print(f"Baixando {URL.format(split=split)} …", file=sys.stderr)
        urllib.request.urlretrieve(URL.format(split=split), arq)  # noqa: S310 - URL fixa e conhecida
    return [json.loads(linha) for linha in arq.read_text(encoding="utf-8").splitlines() if linha.strip()]


def ocorrencias(texto: str, valor: str) -> list[tuple[int, int]]:
    """Todas as ocorrências de ``valor`` no texto; o gabarito anota valores, não posições."""
    saida, i = [], texto.find(valor)
    while i >= 0:
        saida.append((i, i + len(valor)))
        i = texto.find(valor, i + 1)
    return saida


def coberto(texto: str, ini: int, fim: int, mascara: list[bool], estrito: bool = False) -> bool:
    """Indica se a ocorrência ``texto[ini:fim]`` está protegida pela máscara.

    Valores com dígitos estão protegidos quando todos os dígitos estão cobertos: palavras-chave
    incluídas na anotação ("SIAPE 1984235", "OAB/DF 76.541") podem ficar visíveis. Valores sem
    dígitos precisam de todas as letras cobertas. No modo ``estrito``, toda letra e todo dígito
    precisam estar cobertos.
    """
    chars = [k for k in range(ini, fim) if texto[k].isalnum()]
    digitos = [k for k in chars if texto[k].isdigit()]
    alvo = chars if estrito or not digitos else digitos
    return all(mascara[k] for k in alvo)


def metricas(dados: list[dict], trechos: list[list[tuple[int, int, str]]], duracao: float,
             rotulo: str = "") -> tuple[dict, list]:
    """Calcula as métricas a partir dos trechos produzidos por um sistema.

    A função é independente do sistema avaliado, o que permite comparar o Themis com outras
    ferramentas sobre os mesmos critérios (ver ``benchmark/comparar.py``).

    Args:
        dados: Documentos do conjunto, com ``text`` e ``entities``.
        trechos: Para cada documento, os trechos ``(início, fim, ação)`` produzidos pelo sistema;
            ``ação`` é ``tarjar`` ou ``alertar`` (sinalizado para revisão).
        duracao: Tempo total de processamento, em segundos.
        rotulo: Nome do sistema, registrado no resultado.

    Returns:
        ``(métricas, vazamentos)``; cada vazamento é ``(rótulo, valor, contexto)``.
    """
    total, protegidas, estritas = Counter(), Counter(), Counter()
    sinalizadas, nao_detectadas = Counter(), Counter()
    vp = fp = fn = 0
    docs_pii = docs_vazados = 0
    chars_tarjados = chars_fora = 0
    erros = []
    for d, ents in zip(dados, trechos):
        texto = d["text"]
        mascara = [False] * len(texto)
        revisao = [False] * len(texto)  # tarjado ou sinalizado para revisão humana
        for ini, fim, acao in ents:
            for k in range(ini, min(fim, len(texto))):
                revisao[k] = True
                if acao == "tarjar":
                    mascara[k] = True
        gabarito = [False] * len(texto)
        pessoais = [e for e in d["entities"] if e["type"] not in NAO_PESSOAIS]
        for e in d["entities"]:
            for a, b in ocorrencias(texto, e["value"]):
                for k in range(a, b):
                    gabarito[k] = True
        vazou = False
        for e in pessoais:
            occ = ocorrencias(texto, e["value"])
            if not occ:
                continue
            total[e["type"]] += 1
            alvo = revisao if e["type"] in SO_ALERTA else mascara
            if all(coberto(texto, a, b, mascara, estrito=True) for a, b in occ):
                estritas[e["type"]] += 1
            if all(coberto(texto, a, b, alvo) for a, b in occ):
                protegidas[e["type"]] += 1
                continue
            if all(coberto(texto, a, b, revisao) for a, b in occ):
                sinalizadas[e["type"]] += 1
            else:
                nao_detectadas[e["type"]] += 1
            if e["type"] not in SO_ALERTA:
                vazou = True
                erros.append((e["type"], e["value"], texto[max(0, occ[0][0] - 50): occ[0][1] + 50]))
        tem_pii, previu = bool(pessoais), any(mascara)
        docs_pii += tem_pii
        docs_vazados += tem_pii and vazou
        vp += tem_pii and previu
        fp += (not tem_pii) and previu
        fn += tem_pii and not previu
        for k, m in enumerate(mascara):
            if m and texto[k].isalnum():
                chars_tarjados += 1
                chars_fora += not gabarito[k]
    precisao = vp / (vp + fp) if vp + fp else 1.0
    recall = vp / (vp + fn) if vp + fn else 1.0
    f1 = 2 * precisao * recall / (precisao + recall) if precisao + recall else 0.0
    rec_total = sum(protegidas.values()) / max(1, sum(total.values()))
    resultado = {
        "sistema": rotulo, "documentos": len(dados),
        "recall_entidades": round(rec_total, 4),
        "recall_por_rotulo": {k: round(protegidas[k] / total[k], 4) for k in sorted(total)},
        "recall_estrito": round(sum(estritas.values()) / max(1, sum(total.values())), 4),
        "recall_estrito_por_rotulo": {k: round(estritas[k] / total[k], 4) for k in sorted(total)},
        "entidades_por_rotulo": dict(sorted(total.items())),
        "nao_tarjadas": {
            "sinalizadas_para_revisao": sum(sinalizadas.values()), "nao_detectadas": sum(nao_detectadas.values()),
            "por_rotulo": {k: {"sinalizadas": sinalizadas[k], "nao_detectadas": nao_detectadas[k]}
                           for k in sorted(set(sinalizadas) | set(nao_detectadas))},
        },
        "documentos_com_vazamento": round(docs_vazados / max(1, docs_pii), 4),
        "triagem": {"precisao": round(precisao, 4), "recall": round(recall, 4), "f1": round(f1, 4)},
        "tarja_fora_do_gabarito": round(chars_fora / max(1, chars_tarjados), 4),
        "segundos_por_documento": round(duracao / max(1, len(dados)), 4),
    }
    return resultado, erros


def trechos_themis(anon: Anonimizador, textos: list[str]) -> list[list[tuple[int, int, str]]]:
    """Trechos ``(início, fim, ação)`` do Themis; cada pedido é analisado como documento independente."""
    return [[(e.inicio, e.fim, e.acao) for e in ents] for ents in anon.analisar_lote(textos)]


def main() -> None:
    """Executa a avaliação pela linha de comando."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--perfil", default="lai")
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--erros", type=int, default=0, help="mostra N exemplos de vazamento")
    ap.add_argument("--json", type=Path, help="salva as métricas em JSON")
    args = ap.parse_args()

    dados = carregar(args.split)
    if args.limite:
        dados = dados[: args.limite]
    anon = Anonimizador(perfil=args.perfil)
    t0 = time.perf_counter()
    trechos = trechos_themis(anon, [d["text"] for d in dados])
    resultado, erros = metricas(dados, trechos, time.perf_counter() - t0, f"Themis LGPD (perfil {args.perfil})")
    resultado["dataset"] = f"EliMC/esic-ner ({args.split})"
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    if args.json:
        args.json.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.erros:
        por_tipo = defaultdict(list)
        for t, v, ctx in erros:
            por_tipo[t].append((v, ctx))
        for t, lst in por_tipo.items():
            print(f"\n### {t} ({len(lst)} vazamentos)")
            for v, ctx in lst[: args.erros]:
                print(f"  - {v!r}  …{ctx.replace(chr(10), ' ')}…")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
