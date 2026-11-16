"""Treinamento do classificador de trechos (``spancat`` do spaCy) para dados de saúde e quase-identificadores.

Dados de saúde descritos com palavras próprias ("dores fortes", "falta de ar") e descrições que apontam
para uma pessoa sem nomeá-la ("o vigilante do turno da noite na guarita") variam demais para listas e
expressões regulares. Este script treina, sobre a partição ``ajuste`` do EliMC/esic-ner (CC BY 4.0), um
classificador de trechos para os rótulos ``DADO_SAUDE`` e ``QUASI_IDENTIFICADOR``:

* candidatos: todos os n-gramas de 1 a 20 tokens (no ajuste, 99% dos quase-identificadores têm até 20
  tokens e todos os dados de saúde, até 10);
* representação de cada token: ``tok2vec`` próprio e pequeno (*hash* da forma normalizada, prefixo,
  sufixo e formato, largura 96, quatro camadas convolucionais *maxout*) somado à projeção aprendida
  dos vetores estáticos do ``pt_core_news_lg``. Os vetores não são copiados para o artefato: o Themis
  já os carrega (ver :mod:`themis_lgpd.reconhecedores.aprendido`);
* cada trecho é reduzido pela média, pelo máximo e pelos vetores do primeiro e do último token,
  seguidos de uma camada *maxout* e de uma saída *softmax* entre os dois rótulos e a classe negativa
  (``spancat_singlelabel``), com peso reduzido para os candidatos negativos (``--peso-negativo``), que
  são centenas por documento para cada trecho anotado.

Na detecção, os candidatos são podados (:func:`themis_lgpd.reconhecedores.aprendido.sugerir_sintagmas`):
trechos que começam ou terminam em pontuação ou palavra funcional, ou que atravessam fim de frase, não
são avaliados. A poda não altera a probabilidade dos demais trechos e reduz o custo da classificação a
cerca de um quinto; o script confere que nenhuma entidade anotada do ajuste é descartada por ela. A
avaliação por época, abaixo, mede o classificador sem a poda; o efeito da poda e dos limiares no sistema
completo é medido por ``benchmark/treino/ablacao_spancat.py``.

Os textos passam pela mesma normalização da detecção (:func:`themis_lgpd.texto.normalizar`). O gabarito
anota valores, não posições: cada ocorrência do valor é localizada no texto e alinhada aos tokens.

A cada época, o modelo é avaliado na partição ``selecao`` apenas por métricas agregadas, para uma grade
de limiares e para os dois modos de seleção de trechos sobrepostos (ver
:func:`themis_lgpd.reconhecedores.aprendido.selecionar`): fração das entidades anotadas cobertas (o
critério de ``benchmark/esic_ner.py``) e precisão por caractere. Vale o estado da época com a maior
média, entre os rótulos, do melhor F1 de cada um. O treino para quando o tempo previsto da próxima
época ultrapassaria o limite (``--minutos``).

O artefato (``model``, ``cfg``, ``config.json`` e ``meta.json`` com a configuração, a semente, as
versões, o SHA-256 dos dados e os limiares escolhidos) é gravado em ``--saida``; o relatório completo
das épocas, em ``--relatorio``. O artefato sai desativado (``ativo_por_padrao: false``): a ativação só é
feita depois da comparação pareada com a linha de base na seleção.

Uso::

    python benchmark/treino/treinar_spancat.py [--epocas 10] [--lote 16] [--minutos 45] [--peso-negativo 0.03]
        [--semente 20261116] [--saida src/themis_lgpd/dados/modelos/sensivel]
        [--relatorio benchmark/treino/resultado_spancat.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import shutil
import sys
import tempfile
import time
from bisect import bisect_left, bisect_right
from pathlib import Path

import numpy
import spacy
import thinc
from spacy.tokens import Span
from spacy.training import Example
from spacy.util import fix_random_seed, minibatch
from thinc.api import Adam

PASTA = Path(__file__).parent
RAIZ = PASTA.parents[1]
sys.path.insert(0, str(PASTA.parent))
sys.path.insert(0, str(PASTA))

from esic_ner import CACHE, coberto, ocorrencias  # noqa: E402
from particoes import ARQUIVO as ARQUIVO_PARTICOES  # noqa: E402
from particoes import carregar  # noqa: E402

from themis_lgpd.reconhecedores.aprendido import NOME_COMPONENTE, selecionar, sugerir_sintagmas  # noqa: E402
from themis_lgpd.texto import normalizar  # noqa: E402

MODELO_BASE = "pt_core_news_lg"
ROTULOS = ("DADO_SAUDE", "QUASI_IDENTIFICADOR")
#: Grade de limiares avaliada na seleção. O classificador escolhe, para cada trecho, o rótulo mais
#: provável entre os dois e a classe negativa; a probabilidade do rótulo escolhido é sempre maior que 1/3.
LIMIARES = tuple(round(0.05 * k, 2) for k in range(7, 20))
MODOS = ("maximo", "uniao")
#: Componente de rótulo único com classe negativa (``spancat_singlelabel``): a saída *softmax* com
#: gradiente de entropia cruzada não satura com a enorme maioria de candidatos negativos, ao contrário
#: da saída logística com erro quadrático do ``spancat`` multirrótulo, que converge para "nenhum trecho".
FABRICA = "spancat_singlelabel"
CONFIG = {
    "spans_key": NOME_COMPONENTE,
    "negative_weight": 1.0,
    "allow_overlap": True,
    "suggester": {"@misc": "spacy.ngram_range_suggester.v1", "min_size": 1, "max_size": 20},
    "model": {
        "@architectures": "spacy.SpanCategorizer.v1",
        "reducer": {"@layers": "spacy.mean_max_reducer.v1", "hidden_size": 128},
        "scorer": {"@layers": "Softmax.v2"},
        "tok2vec": {
            "@architectures": "spacy.Tok2Vec.v2",
            "embed": {"@architectures": "spacy.MultiHashEmbed.v2", "width": 96,
                      "attrs": ["NORM", "PREFIX", "SUFFIX", "SHAPE"], "rows": [5000, 1000, 2500, 2500],
                      "include_static_vectors": True},
            "encode": {"@architectures": "spacy.MaxoutWindowEncoder.v2", "width": 96, "depth": 4,
                       "window_size": 1, "maxout_pieces": 3},
        },
    },
}
#: Sugestor gravado no artefato e usado na detecção: o mesmo modelo, com a poda de candidatos.
SUGESTOR_DETECCAO = {"@misc": "themis.sugestor_sintagmas.v1", "min_size": 1, "max_size": 20}
#: Otimizador (os valores padrão do spaCy para treino de componentes).
OTIMIZADOR = {"learn_rate": 0.001, "beta1": 0.9, "beta2": 0.999, "eps": 1e-8, "L2": 0.01,
              "L2_is_weight_decay": True, "grad_clip": 1.0}


def sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def posicoes_normalizadas(norm, ini: int, fim: int) -> tuple[int, int] | None:
    """Intervalo do texto normalizado que corresponde a ``original[ini:fim]``."""
    a = bisect_left(norm._ini, ini)
    b = bisect_right(norm._fim, fim)
    return (a, b) if a < b else None


def preparar(nlp, dados: list[dict]) -> list[dict]:
    """Documentos normalizados, com as entidades de cada rótulo em posições do texto normalizado.

    Cada item traz ``texto``, ``doc`` (tokens), ``entidades`` (rótulo → lista de entidades, cada uma
    com a lista de ocorrências ``(início, fim)``, como no gabarito) e ``trechos`` (spans alinhados aos
    tokens com ``alignment_mode="expand"``, para o treino).
    """
    saida = []
    for d in dados:
        norm = normalizar(d["text"])
        doc = nlp.make_doc(norm.texto)
        entidades: dict[str, list[list[tuple[int, int]]]] = {r: [] for r in ROTULOS}
        trechos: set[tuple[int, int, str]] = set()
        for e in d["entities"]:
            if e["type"] not in ROTULOS:
                continue
            occ = [p for a, b in ocorrencias(d["text"], e["value"]) if (p := posicoes_normalizadas(norm, a, b))]
            if not occ:
                continue
            entidades[e["type"]].append(occ)
            for a, b in occ:
                span = doc.char_span(a, b, alignment_mode="expand")
                if span is not None and len(span):
                    trechos.add((span.start, span.end, e["type"]))
        saida.append({"texto": norm.texto, "doc": doc, "entidades": entidades, "trechos": sorted(trechos)})
    return saida


def exemplos(nlp, itens: list[dict]) -> list[Example]:
    """``Example`` do spaCy com as entidades anotadas em ``Doc.spans``."""
    saida = []
    for it in itens:
        referencia = nlp.make_doc(it["texto"])
        referencia.spans[NOME_COMPONENTE] = [Span(referencia, a, b, label=r) for a, b, r in it["trechos"]]
        saida.append(Example(nlp.make_doc(it["texto"]), referencia))
    return saida


def verificar_poda(itens: list[dict]) -> dict:
    """Fração dos n-gramas mantida pela poda da detecção e entidades anotadas que ela descartaria."""
    minimo, maximo = SUGESTOR_DETECCAO["min_size"], SUGESTOR_DETECCAO["max_size"]
    mantidos = todos = descartadas = 0
    for it in itens:
        doc = it["doc"]
        sugeridos = sugerir_sintagmas([doc], minimo, maximo)
        pares = {(int(a), int(b)) for a, b in sugeridos.dataXd} if len(sugeridos.dataXd) else set()
        mantidos += len(pares)
        todos += sum(max(0, len(doc) - k + 1) for k in range(minimo, maximo + 1))
        descartadas += sum((a, b) not in pares for a, b, _ in it["trechos"] if b - a <= maximo)
    return {"candidatos_mantidos": round(mantidos / max(1, todos), 4), "entidades_do_ajuste_descartadas": descartadas}


def candidatos(componente, docs: list, minimo: float, lote: int = 64) -> list[list[tuple[int, int, str, float]]]:
    """Trechos ``(início, fim, rótulo, probabilidade)`` cujo rótulo mais provável não é a classe negativa.

    É o mesmo critério do componente ao registrar os trechos no documento, na detecção.
    """
    saida = []
    rotulos = list(componente.labels)
    ops = componente.model.ops
    for k in range(0, len(docs), lote):
        parte = docs[k:k + lote]
        indices, scores = componente.predict(parte)
        scores, idx_todos = ops.to_numpy(scores), ops.to_numpy(indices.dataXd)
        deslocamento = 0
        for doc, n in zip(parte, ops.to_numpy(indices.lengths)):
            bloco, idx = scores[deslocamento:deslocamento + n], idx_todos[deslocamento:deslocamento + n]
            deslocamento += n
            classe = bloco.argmax(axis=1)
            linhas = numpy.nonzero((classe < len(rotulos)) & (bloco.max(axis=1) >= minimo))[0]
            saida.append([(doc[int(idx[i, 0])].idx, doc[int(idx[i, 1]) - 1].idx + len(doc[int(idx[i, 1]) - 1]),
                           rotulos[int(classe[i])], float(bloco[i, classe[i]])) for i in linhas])
    return saida


def metricas(itens: list[dict], previstos: list[list[tuple]]) -> dict:
    """Cobertura das entidades e precisão por caractere, por rótulo, limiar e modo (só agregados).

    O modo escolhido é o de maior média, entre os rótulos, do melhor F1 de cada rótulo nesse modo; o
    limiar de cada rótulo é o de maior F1 no modo escolhido.
    """
    grades: dict = {}
    for rotulo in ROTULOS:
        por_modo = {}
        for modo in MODOS:
            linhas = []
            for limiar in LIMIARES:
                total = cobertas = tarjados = certos = 0
                for it, cand in zip(itens, previstos):
                    texto = it["texto"]
                    mascara = [False] * len(texto)
                    for a, b, _, _ in selecionar(cand, {rotulo: limiar}, modo):
                        mascara[a:b] = [True] * (b - a)
                    gabarito = [False] * len(texto)
                    for occ in it["entidades"][rotulo]:
                        total += 1
                        cobertas += all(coberto(texto, a, b, mascara) for a, b in occ)
                        for a, b in occ:
                            gabarito[a:b] = [True] * (b - a)
                    for k, m in enumerate(mascara):
                        if m and texto[k].isalnum():
                            tarjados += 1
                            certos += gabarito[k]
                recall = cobertas / max(1, total)
                precisao = certos / tarjados if tarjados else 1.0
                f1 = 2 * precisao * recall / (precisao + recall) if precisao + recall else 0.0
                linhas.append({"limiar": limiar, "recall": round(recall, 4), "precisao_caracteres": round(precisao, 4),
                               "f1": round(f1, 4)})
            por_modo[modo] = linhas
        grades[rotulo] = por_modo

    def melhor(rotulo: str, modo: str) -> dict:
        return max(grades[rotulo][modo], key=lambda linha: (linha["f1"], -linha["limiar"]))

    def media(modo: str) -> float:
        return sum(melhor(r, modo)["f1"] for r in ROTULOS) / len(ROTULOS)

    modo = max(MODOS, key=media)
    return {"modo": modo, "f1_medio": round(media(modo), 4),
            "melhor_por_rotulo": {r: melhor(r, modo) for r in ROTULOS}, "grade": grades}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--epocas", type=int, default=10)
    ap.add_argument("--lote", type=int, default=16, help="documentos por atualização")
    ap.add_argument("--minutos", type=float, default=45.0, help="tempo máximo de treino")
    ap.add_argument("--semente", type=int, default=20261116)
    ap.add_argument("--abandono", type=float, default=0.1, help="taxa de dropout")
    ap.add_argument("--peso-negativo", type=float, default=0.03, help="peso da classe negativa na perda")
    ap.add_argument("--limite", type=int, default=0, help="usa só os N primeiros documentos (teste rápido)")
    ap.add_argument("--saida", type=Path, default=RAIZ / "src" / "themis_lgpd" / "dados" / "modelos" / "sensivel")
    ap.add_argument("--relatorio", type=Path, default=PASTA / "resultado_spancat.json")
    args = ap.parse_args()

    fix_random_seed(args.semente)
    gerador = random.Random(args.semente)
    nlp = spacy.load(MODELO_BASE, exclude=["tok2vec", "morphologizer", "parser", "senter", "attribute_ruler",
                                           "lemmatizer", "ner"])
    ajuste, selecao = carregar("ajuste"), carregar("selecao")
    if args.limite:
        ajuste, selecao = ajuste[:args.limite], selecao[:args.limite]
    t0 = time.perf_counter()
    treino_itens, selecao_itens = preparar(nlp, ajuste), preparar(nlp, selecao)
    treino = exemplos(nlp, treino_itens)
    selecao_docs = [it["doc"] for it in selecao_itens]
    print(f"{len(treino)} documentos de treino, {len(selecao_docs)} de seleção "
          f"({time.perf_counter() - t0:.0f} s de preparação)", flush=True)

    CONFIG["negative_weight"] = args.peso_negativo
    componente = nlp.add_pipe(FABRICA, name=NOME_COMPONENTE, config=CONFIG)
    componente.initialize(lambda: treino, nlp=nlp, labels=list(ROTULOS))
    otimizador = Adam(**OTIMIZADOR)

    epocas, melhor, melhor_pesos = [], None, None
    inicio = time.perf_counter()
    for epoca in range(1, args.epocas + 1):
        t_epoca = time.perf_counter()
        gerador.shuffle(treino)
        perdas: dict[str, float] = {}
        for lote in minibatch(treino, size=args.lote):
            componente.update(lote, drop=args.abandono, sgd=otimizador, losses=perdas)
        duracao_treino = time.perf_counter() - t_epoca
        t_aval = time.perf_counter()
        avaliacao = metricas(selecao_itens, candidatos(componente, selecao_docs, min(LIMIARES)))
        registro = {"epoca": epoca, "perda": round(perdas.get(NOME_COMPONENTE, 0.0), 2),
                    "segundos_treino": round(duracao_treino), "segundos_avaliacao": round(time.perf_counter() - t_aval),
                    "f1_medio_selecao": avaliacao["f1_medio"], "modo": avaliacao["modo"],
                    "melhor_por_rotulo": avaliacao["melhor_por_rotulo"], "grade": avaliacao["grade"]}
        epocas.append(registro)
        print(json.dumps({k: v for k, v in registro.items() if k != "grade"}, ensure_ascii=False), flush=True)
        if melhor is None or avaliacao["f1_medio"] > melhor["f1_medio_selecao"]:
            melhor, melhor_pesos = registro, componente.model.to_bytes()
        decorrido = time.perf_counter() - inicio
        if decorrido + decorrido / epoca > args.minutos * 60:
            print(f"Limite de {args.minutos:g} minutos: treino encerrado na época {epoca}.", flush=True)
            break

    componente.model.from_bytes(melhor_pesos)
    escolhido = melhor["melhor_por_rotulo"]
    vetores = nlp.vocab.vectors
    meta = {
        "versao": 1,
        "descricao": "Classificador de trechos (spaCy spancat) para dados de saúde e quase-identificadores",
        "rotulos": list(ROTULOS),
        "fabrica": FABRICA,
        "limiares": {r: escolhido[r]["limiar"] for r in ROTULOS},
        "decodificacao": melhor["modo"],
        "ativo_por_padrao": False,
        "vetores": {"modelo": MODELO_BASE, "versao_modelo": nlp.meta.get("version"), "nome": vetores.name,
                    "forma": list(vetores.shape)},
        "treino": {
            "dados": "EliMC/esic-ner (CC BY 4.0), partição ajuste; seleção da época e dos limiares na partição selecao",
            "sha256_train": sha256((CACHE / "esic-ner-train.jsonl").read_bytes()),
            "sha256_particoes": sha256(ARQUIVO_PARTICOES.read_bytes()),
            "sha256_documentos_ajuste": sha256("\n".join(sorted(d["text"] for d in ajuste)).encode("utf-8")),
            "documentos": {"ajuste": len(ajuste), "selecao": len(selecao)},
            "semente": args.semente, "lote": args.lote, "abandono": args.abandono, "epocas_maximas": args.epocas,
            "epocas_executadas": len(epocas), "melhor_epoca": melhor["epoca"], "minutos": round((time.perf_counter() - inicio) / 60, 1),
            "otimizador": {"nome": "Adam", **OTIMIZADOR}, "config": CONFIG,
            "versoes": {"spacy": spacy.__version__, "thinc": thinc.__version__, "numpy": numpy.__version__,
                        "python": platform.python_version()},
        },
        "selecao": {"f1_medio": melhor["f1_medio_selecao"], "por_rotulo": escolhido},
    }
    destino = args.saida
    with tempfile.TemporaryDirectory() as tmp:
        componente.to_disk(tmp, exclude=["vocab"])
        destino.mkdir(parents=True, exist_ok=True)
        for nome in ("cfg", "model"):
            shutil.copyfile(Path(tmp) / nome, destino / nome)
    cfg = json.loads((destino / "cfg").read_text(encoding="utf-8"))
    (destino / "cfg").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (destino / "config.json").write_text(json.dumps({**CONFIG, "suggester": SUGESTOR_DETECCAO}, ensure_ascii=False,
                                                    indent=2) + "\n", encoding="utf-8", newline="\n")
    meta["poda_de_candidatos"] = verificar_poda(treino_itens)
    meta["sha256_model"] = sha256((destino / "model").read_bytes())
    (destino / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                                       newline="\n")
    print(f"Artefato gravado em {destino} ({(destino / 'model').stat().st_size / 1e6:.1f} MB)")
    relatorio = {"meta": meta, "epocas": epocas}
    args.relatorio.parent.mkdir(parents=True, exist_ok=True)
    args.relatorio.write_text(json.dumps(relatorio, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(meta["selecao"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
