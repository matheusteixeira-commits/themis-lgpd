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

Cada métrica principal acompanha o intervalo de confiança de 95% por *bootstrap* de documentos
(1.000 reamostragens, semente fixa). Com ``--detalhes``, o resultado de cada documento é gravado para a
comparação pareada entre duas versões (``benchmark/treino/comparar_execucoes.py``).

O conjunto é baixado do Hugging Face na primeira execução e mantido em ``benchmark/.cache``.

Partições (ver ``benchmark/treino/particoes.py``): ``ajuste`` e ``selecao`` dividem a partição
``train`` do conjunto; ``lockbox`` é a partição ``test``, reservada à avaliação final — cada uso exige
``--lockbox MOTIVO`` e fica registrado em ``benchmark/treino/registro_lockbox.jsonl``. Os exemplos de
erro (``--erros``, ``--erros-arquivo``) só são emitidos para a partição ``ajuste``.

Uso::

    python benchmark/esic_ner.py [--particao selecao] [--perfil lai] [--json saida.json]
        [--detalhes docs.jsonl] [--erros 20] [--erros-arquivo erros.jsonl] [--lockbox MOTIVO]
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess  # noqa: S404 - apenas "git rev-parse", para registrar o commit avaliado  # nosec B404
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
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


def metricas(dados: list[dict], trechos: list[list[tuple]], duracao: float,
             rotulo: str = "", detalhes: list | None = None) -> tuple[dict, list]:
    """Calcula as métricas a partir dos trechos produzidos por um sistema.

    A função é independente do sistema avaliado, o que permite comparar o Themis com outras
    ferramentas sobre os mesmos critérios (ver ``benchmark/comparar.py``).

    Args:
        dados: Documentos do conjunto, com ``text`` e ``entities``.
        trechos: Para cada documento, os trechos ``(início, fim, ação[, tipo])`` produzidos pelo
            sistema; ``ação`` é ``tarjar`` ou ``alertar`` (sinalizado para revisão).
        duracao: Tempo total de processamento, em segundos.
        rotulo: Nome do sistema, registrado no resultado.
        detalhes: Lista que, se informada, recebe o resultado de cada documento (contagens por
            rótulo, vazamento, caracteres tarjados), usado nos intervalos de confiança e na
            comparação pareada.

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
        for ini, fim, acao, *_ in ents:
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
        doc_total, doc_prot, doc_estr = Counter(), Counter(), Counter()
        for e in pessoais:
            occ = ocorrencias(texto, e["value"])
            if not occ:
                continue
            total[e["type"]] += 1
            doc_total[e["type"]] += 1
            alvo = revisao if e["type"] in SO_ALERTA else mascara
            if all(coberto(texto, a, b, mascara, estrito=True) for a, b in occ):
                estritas[e["type"]] += 1
                doc_estr[e["type"]] += 1
            if all(coberto(texto, a, b, alvo) for a, b in occ):
                protegidas[e["type"]] += 1
                doc_prot[e["type"]] += 1
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
        doc_tarjados = doc_fora = 0
        for k, m in enumerate(mascara):
            if m and texto[k].isalnum():
                doc_tarjados += 1
                doc_fora += not gabarito[k]
        chars_tarjados += doc_tarjados
        chars_fora += doc_fora
        if detalhes is not None:
            detalhes.append({"chave": chave(texto), "total": dict(doc_total), "protegidas": dict(doc_prot),
                             "estritas": dict(doc_estr), "tem_pii": tem_pii, "vazou": tem_pii and vazou,
                             "chars_tarjados": doc_tarjados, "chars_fora": doc_fora})
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


def trechos_themis(anon: Anonimizador, textos: list[str]) -> list[list[tuple[int, int, str, str]]]:
    """Trechos ``(início, fim, ação, tipo)`` do Themis; cada pedido é analisado como documento independente."""
    return [[(e.inicio, e.fim, e.acao, e.tipo) for e in ents] for ents in anon.analisar_lote(textos)]


def chave(texto: str) -> str:
    """Identificador estável do documento (ver ``benchmark/treino/particoes.py``)."""
    import hashlib

    return hashlib.sha256(" ".join(texto.split()).lower().encode("utf-8")).hexdigest()


def agregadas(docs: list[dict]) -> dict[str, float]:
    """Métricas principais a partir dos resultados por documento."""
    total, prot, estr = Counter(), Counter(), Counter()
    for d in docs:
        total.update(d["total"])
        prot.update(d["protegidas"])
        estr.update(d["estritas"])
    com_pii = sum(d["tem_pii"] for d in docs)
    tarjados = sum(d["chars_tarjados"] for d in docs)
    saida = {
        "recall_entidades": sum(prot.values()) / max(1, sum(total.values())),
        "recall_estrito": sum(estr.values()) / max(1, sum(total.values())),
        "documentos_com_vazamento": sum(d["vazou"] for d in docs) / max(1, com_pii),
        "tarja_fora_do_gabarito": sum(d["chars_fora"] for d in docs) / max(1, tarjados),
    }
    saida.update({f"recall:{r}": prot[r] / total[r] for r in total})
    if any("tarjas_total" in d for d in docs):  # conjunto de referência, com anotação exaustiva
        saida["precisao_tarjas"] = 1 - sum(d["tarjas_fora"] for d in docs) / max(1, sum(d["tarjas_total"] for d in docs))
        saida["preservacao_publicos"] = (sum(d["publicos_preservados"] for d in docs)
                                         / max(1, sum(d["publicos_total"] for d in docs)))
    return saida


def intervalos(docs: list[dict], reamostragens: int = 1000, semente: int = 20261116) -> dict[str, list[float]]:
    """Intervalo de confiança de 95% (percentis 2,5 e 97,5) de cada métrica, por *bootstrap* de documentos."""
    gerador = random.Random(semente)
    amostras = defaultdict(list)
    for _ in range(reamostragens):
        sorteio = [docs[gerador.randrange(len(docs))] for _ in docs]
        for nome, valor in agregadas(sorteio).items():
            amostras[nome].append(valor)
    saida = {}
    for nome, valores in sorted(amostras.items()):
        valores.sort()
        saida[nome] = [round(valores[int(0.025 * len(valores))], 4), round(valores[int(0.975 * len(valores)) - 1], 4)]
    return saida


def erros_detalhados(dados: list[dict], trechos: list[list[tuple]]) -> list[dict]:
    """Falsos negativos (entidade anotada visível) e trechos tarjados fora do gabarito, com contexto."""
    saida = []
    for d, ents in zip(dados, trechos):
        texto = d["text"]
        mascara, revisao, gabarito = [False] * len(texto), [False] * len(texto), [False] * len(texto)
        for ini, fim, acao, *_ in ents:
            for k in range(ini, min(fim, len(texto))):
                revisao[k] = True
                mascara[k] = mascara[k] or acao == "tarjar"
        for e in d["entities"]:
            for a, b in ocorrencias(texto, e["value"]):
                gabarito[a:b] = [True] * (b - a)
        for e in d["entities"]:
            if e["type"] in NAO_PESSOAIS:
                continue
            occ = ocorrencias(texto, e["value"])
            alvo = revisao if e["type"] in SO_ALERTA else mascara
            if occ and not all(coberto(texto, a, b, alvo) for a, b in occ):
                a, b = occ[0]
                situacao = "sinalizada" if all(coberto(texto, x, y, revisao) for x, y in occ) else "nao_detectada"
                saida.append({"erro": "nao_tarjada", "rotulo": e["type"], "valor": e["value"], "situacao": situacao,
                              "contexto": texto[max(0, a - 80): b + 80], "chave": chave(texto)})
        for ini, fim, acao, *resto in ents:
            alnum = [k for k in range(ini, min(fim, len(texto))) if texto[k].isalnum()]
            if acao == "tarjar" and alnum and not any(gabarito[k] for k in alnum):
                saida.append({"erro": "tarja_fora_do_gabarito", "tipo_themis": resto[0] if resto else "",
                              "valor": texto[ini:fim], "contexto": texto[max(0, ini - 80): fim + 80],
                              "chave": chave(texto)})
    return saida


def _registrar_lockbox(motivo: str, perfil: str, resultado: dict) -> None:
    from treino.particoes import REGISTRO_LOCKBOX

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,  # noqa: S607
                                cwd=Path(__file__).parent, timeout=20, check=False).stdout.strip()  # nosec B603 B607
    except OSError:
        commit = ""
    linha = {"data": datetime.now(UTC).isoformat(timespec="seconds"), "motivo": motivo, "commit": commit,
             "perfil": perfil, "recall_entidades": resultado["recall_entidades"],
             "documentos_com_vazamento": resultado["documentos_com_vazamento"]}
    with REGISTRO_LOCKBOX.open("a", encoding="utf-8", newline="\n") as arq:
        arq.write(json.dumps(linha, ensure_ascii=False) + "\n")


def main() -> None:
    """Executa a avaliação pela linha de comando."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--particao", default="selecao", choices=["ajuste", "selecao", "train", "lockbox"],
                    help="ajuste e selecao dividem train; lockbox é a partição test (exige --lockbox)")
    ap.add_argument("--perfil", default="lai")
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--erros", type=int, default=0, help="mostra N exemplos de vazamento (só na partição ajuste)")
    ap.add_argument("--erros-arquivo", type=Path, help="grava os erros com contexto em JSONL (só na partição ajuste)")
    ap.add_argument("--json", type=Path, help="salva as métricas em JSON")
    ap.add_argument("--detalhes", type=Path, help="grava o resultado de cada documento em JSONL")
    ap.add_argument("--sem-intervalos", action="store_true", help="não calcula os intervalos de confiança")
    ap.add_argument("--lockbox", metavar="MOTIVO", help="autoriza e registra a avaliação na partição lockbox")
    args = ap.parse_args()

    if args.particao == "lockbox" and not args.lockbox:
        ap.error("a partição lockbox é reservada à avaliação final: informe --lockbox MOTIVO (o uso é registrado)")
    if (args.erros or args.erros_arquivo) and args.particao != "ajuste":
        ap.error("exemplos de erro só podem ser examinados na partição ajuste")
    if args.particao in ("ajuste", "selecao"):
        from treino.particoes import carregar as carregar_particao

        dados = carregar_particao(args.particao)
    else:
        dados = carregar("test" if args.particao == "lockbox" else "train")
    if args.limite:
        dados = dados[: args.limite]
    anon = Anonimizador(perfil=args.perfil)
    t0 = time.perf_counter()
    trechos = trechos_themis(anon, [d["text"] for d in dados])
    docs: list[dict] = []
    resultado, erros = metricas(dados, trechos, time.perf_counter() - t0, f"Themis LGPD (perfil {args.perfil})", docs)
    resultado["dataset"] = f"EliMC/esic-ner ({args.particao})"
    if not args.sem_intervalos:
        resultado["intervalos_95"] = intervalos(docs)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    if args.json:
        args.json.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.detalhes:
        args.detalhes.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs), encoding="utf-8",
                                 newline="\n")
    if args.particao == "lockbox":
        _registrar_lockbox(args.lockbox, args.perfil, resultado)
    if args.erros_arquivo:
        args.erros_arquivo.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n"
                                              for e in erros_detalhados(dados, trechos)),
                                      encoding="utf-8", newline="\n")
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
