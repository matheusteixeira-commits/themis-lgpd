"""Treinamento do classificador de trechos (``spancat`` do spaCy) para dados sensíveis e nomes de pessoas.

Dados de saúde descritos com palavras próprias ("dores fortes", "falta de ar") ou em linguagem clínica
("cisto renal simples de 1,1 cm", "insulina NPH 10 UI à noite"), a descrição de origem étnica, religião ou
filiação ("membro de uma congregação batista", "indígena da etnia X") e nomes de pessoas fora dos padrões
das regras (em caixa alta, em tabelas, em assinaturas) variam demais para listas e expressões
regulares. Este script treina um classificador de trechos sobre duas fontes:

* a partição ``ajuste`` do EliMC/esic-ner (CC BY 4.0), pedidos de acesso à informação;
* a partição ``ajuste`` do corpus de documentos oficiais fictícios (``benchmark/oficial``, produção
  própria): laudos, prontuários, relatórios sociais, portarias, processos disciplinares, atas.
  Este corpus é anotado de forma exaustiva (``benchmark/ouro/DIRETRIZES.md``): só é dado de saúde o
  que se refere a pessoa identificada; dados agregados e normativos ficam como negativos.

Rótulos (``--rotulos``): ``DADO_SAUDE``, ``DADO_SENSIVEL`` (só no corpus oficial), ``NOME_PESSOA`` e
``QUASI_IDENTIFICADOR``. Quais deles produzem achados é decidido depois, pela ablação no sistema
completo (``benchmark/treino/ablacao_spancat.py``), e registrado nos metadados do artefato.

* candidatos: n-gramas de 1 a 20 tokens com bordas e interior plausíveis
  (:func:`themis_lgpd.reconhecedores.aprendido.sugerir_sintagmas`: não começam nem terminam em
  pontuação ou palavra funcional e não atravessam fim de frase ou quebra de linha), os mesmos no treino
  e na detecção (``--sugestor-treino ngramas`` treina, como no ciclo anterior, com todos os n-gramas);
* entidades anotadas que atravessam uma dessas fronteiras ("Losartana 50 mg ---- 30 comprimidos" em
  duas linhas) ou que terminam em pontuação ("saturação de 93%") entram no treino pelas partes que o
  sugestor propõe, aparadas nas bordas (:func:`segmentar`): a cobertura de um valor exige as letras ou
  os dígitos, não a pontuação;
* representação de cada token: ``tok2vec`` próprio e pequeno (*hash* da forma normalizada, prefixo,
  sufixo e formato, largura 96, quatro camadas convolucionais *maxout*) somado à projeção aprendida
  dos vetores estáticos do ``pt_core_news_lg``. Os vetores não são copiados para o artefato: o Themis
  já os carrega (ver :mod:`themis_lgpd.reconhecedores.aprendido`);
* cada trecho é reduzido pela média, pelo máximo e pelos vetores do primeiro e do último token,
  seguidos de uma camada *maxout* e de uma saída *softmax* entre os rótulos e a classe negativa
  (``spancat_singlelabel``), com peso reduzido para os candidatos negativos (``--peso-negativo``).

Os documentos oficiais são longos e poucos; ``--repeticoes-oficial`` os repete a cada época. Textos fora do
domínio (inglês de modelos de documentos e apresentações, texto de preenchimento em latim; ver
:func:`textos_fora_do_dominio`) entram como exemplos sem nenhum trecho anotado (``--fora-do-dominio``).

Os textos passam pela mesma normalização da detecção (:func:`themis_lgpd.texto.normalizar`). O gabarito
anota valores, não posições: cada ocorrência do valor é localizada no texto (como em
``benchmark/esic_ner.py`` e, no corpus oficial, como palavra inteira, como em
``benchmark/ouro/ferramentas.py``) e alinhada aos tokens.

A cada época, o modelo é avaliado nas partições ``selecao`` dos dois corpora apenas por métricas
agregadas, para uma grade de limiares e para os dois modos de seleção de trechos sobrepostos (ver
:func:`themis_lgpd.reconhecedores.aprendido.selecionar`): fração das entidades anotadas cobertas (o
critério de ``benchmark/esic_ner.py``) e precisão por caractere. O estado de cada época é gravado em
``--pontos`` para a escolha da época no sistema completo; o artefato recebe o da época com a maior
média, entre os dois corpora, da média por rótulo do melhor F1. O treino para quando o tempo previsto
da próxima época ultrapassaria o limite (``--minutos``).

O artefato (``model``, ``cfg``, ``config.json`` e ``meta.json`` com a configuração, a semente, as
versões, o SHA-256 dos dados e os limiares do classificador isolado) é gravado em ``--saida``; o
relatório completo das épocas, em ``--relatorio``. O artefato sai desativado (``ativo_por_padrao:
false``): a ativação de cada rótulo só é feita pela ablação no sistema completo.

Uso::

    python benchmark/treino/treinar_spancat.py [--epocas 10] [--lote 16] [--minutos 50] [--peso-negativo 0.03]
        [--rotulos DADO_SAUDE DADO_SENSIVEL NOME_PESSOA QUASI_IDENTIFICADOR] [--repeticoes-oficial 2]
        [--sugestor-treino sintagmas] [--fora-do-dominio 1000] [--semente 20261116]
        [--saida src/themis_lgpd/dados/modelos/sensivel]
        [--relatorio benchmark/treino/resultado_spancat.json] [--pontos .trabalho/pontos_spancat]
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

from esic_ner import CACHE, coberto  # noqa: E402
from esic_ner import ocorrencias as ocorrencias_esic  # noqa: E402
from ouro.ferramentas import ler  # noqa: E402
from ouro.ferramentas import ocorrencias as ocorrencias_oficial  # noqa: E402
from particoes import ARQUIVO as ARQUIVO_PARTICOES  # noqa: E402
from particoes import carregar  # noqa: E402

from themis_lgpd.reconhecedores.aprendido import (  # noqa: E402
    NOME_COMPONENTE,
    fim_invalido,
    inicio_invalido,
    interior_invalido,
    selecionar,
    sugerir_sintagmas,
)
from themis_lgpd.texto import normalizar  # noqa: E402

MODELO_BASE = "pt_core_news_lg"
#: Corpus de documentos oficiais (partições ``ajuste`` e ``selecao``; ver ``benchmark/oficial/LEIAME.md``).
OFICIAL = RAIZ / "benchmark" / "oficial"
ROTULOS = ("DADO_SAUDE", "DADO_SENSIVEL", "NOME_PESSOA", "QUASI_IDENTIFICADOR")
#: Rótulos que entram no critério de escolha da época (o de quase-identificadores está desativado).
ROTULOS_ESCOLHA = ("DADO_SAUDE", "DADO_SENSIVEL", "NOME_PESSOA")
#: Grade de limiares avaliada na seleção. Com quatro rótulos e a classe negativa, a probabilidade do
#: rótulo escolhido é sempre maior que 1/5.
LIMIARES = tuple(round(0.05 * k, 2) for k in range(6, 20))
MODOS = ("maximo", "uniao")
#: Componente de rótulo único com classe negativa (``spancat_singlelabel``): a saída *softmax* com
#: gradiente de entropia cruzada não satura com a enorme maioria de candidatos negativos, ao contrário
#: da saída logística com erro quadrático do ``spancat`` multirrótulo, que converge para "nenhum trecho".
FABRICA = "spancat_singlelabel"
#: Sugestores de candidatos: todos os n-gramas ou só os de bordas plausíveis (o mesmo da detecção).
SUGESTORES = {
    "ngramas": {"@misc": "spacy.ngram_range_suggester.v1", "min_size": 1, "max_size": 20},
    "sintagmas": {"@misc": "themis.sugestor_sintagmas.v1", "min_size": 1, "max_size": 20},
}
CONFIG = {
    "spans_key": NOME_COMPONENTE,
    "negative_weight": 1.0,
    "allow_overlap": True,
    "suggester": SUGESTORES["sintagmas"],
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
#: Sugestor gravado no artefato e usado na detecção.
SUGESTOR_DETECCAO = SUGESTORES["sintagmas"]
#: Vocabulário de textos fora do domínio — inglês de modelos de documentos, planilhas e apresentações e
#: texto de preenchimento em latim —, que chegam ao classificador em arquivos de escritório (mestres de
#: slides, cabeçalhos de planilhas). Sem exemplos assim, palavras capitalizadas desconhecidas recebem
#: probabilidade alta de nome ou de condição de saúde. Os textos gerados com estas palavras entram no
#: treino sem nenhum trecho anotado (:func:`textos_fora_do_dominio`).
VOCABULARIO_FORA_DO_DOMINIO = (
    "the", "of", "and", "a", "in", "for", "with", "on", "at", "by", "from", "your", "this", "here", "is", "are",
    "will", "be", "or", "all", "new", "insert", "add", "type", "enter", "text", "heading", "subheading", "body",
    "caption", "chart", "table", "picture", "image", "logo", "company", "date", "page", "number", "footer",
    "header", "section", "agenda", "overview", "summary", "introduction", "conclusion", "thank", "you",
    "questions", "contact", "report", "quarterly", "annual", "results", "revenue", "growth", "market", "sales",
    "team", "project", "timeline", "goals", "objectives", "strategy", "plan", "review", "notes", "layout",
    "placeholder", "content", "column", "row", "item", "bullet", "point", "list", "first", "third", "fourth",
    "fifth", "main", "topic", "description", "details", "example", "sample", "draft", "version", "status",
    "pending", "approved", "comment", "slide", "theme", "font", "color", "background", "object", "shape",
    "sheet", "total", "average", "chapter", "figure", "source", "appendix", "index", "welcome", "lorem",
    "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit", "sed", "eiusmod", "tempor",
    "incididunt", "ut", "labore", "et", "dolore", "magna", "aliqua", "enim", "minim", "veniam", "quis",
    "nostrud", "exercitation", "ullamco", "laboris", "nisi", "aliquip", "ex", "ea", "commodo", "consequat",
)


def textos_fora_do_dominio(gerador: random.Random, quantidade: int) -> list[dict]:
    """Textos curtos com o vocabulário de :data:`VOCABULARIO_FORA_DO_DOMINIO`, sem trechos anotados.

    Cada texto tem de uma a três linhas de uma a dez palavras, em caixa de título, minúsculas ou
    maiúsculas, como nos textos-modelo de editores de documentos.
    """
    caixas = (str.title, str.lower, str.upper, str.capitalize)
    saida = []
    for _ in range(quantidade):
        linhas = []
        for _ in range(gerador.randint(1, 3)):
            frase = " ".join(gerador.choice(VOCABULARIO_FORA_DO_DOMINIO) for _ in range(gerador.randint(1, 10)))
            linhas.append(gerador.choice(caixas)(frase))
        saida.append({"text": "\n".join(linhas), "entities": [], "fonte": "fora_do_dominio"})
    return saida
#: Otimizador (os valores padrão do spaCy para treino de componentes).
OTIMIZADOR = {"learn_rate": 0.001, "beta1": 0.9, "beta2": 0.999, "eps": 1e-8, "L2": 0.01,
              "L2_is_weight_decay": True, "grad_clip": 1.0}


def sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def carregar_oficial(particao: str) -> list[dict]:
    """Documentos do corpus oficial no formato do esic-ner (``text``, ``entities`` com ``type`` e ``value``)."""
    return [{"text": d["texto"], "entities": [{"type": e["tipo"], "value": e["valor"]} for e in d["entidades"]],
             "fonte": "oficial"} for d in ler(OFICIAL / f"{particao}.jsonl")]


def posicoes_normalizadas(norm, ini: int, fim: int) -> tuple[int, int] | None:
    """Intervalo do texto normalizado que corresponde a ``original[ini:fim]``."""
    a = bisect_left(norm._ini, ini)
    b = bisect_right(norm._fim, fim)
    return (a, b) if a < b else None


def segmentar(doc, inicio: int, fim: int, maximo: int) -> list[tuple[int, int]]:
    """Partes do trecho ``doc[inicio:fim]`` que o sugestor da detecção pode propor.

    O trecho é dividido nos tokens que um candidato não atravessa (fim de frase, quebra de linha) e cada
    parte é aparada nas bordas que um candidato não pode ter (pontuação, palavra funcional). Um trecho
    que já é candidato volta inteiro; partes mais longas que ``maximo`` são descartadas.
    """
    partes, atual = [], []
    for i in range(inicio, fim):
        if interior_invalido(doc[i]):
            if atual:
                partes.append((atual[0], atual[-1] + 1))
            atual = []
        else:
            atual.append(i)
    if atual:
        partes.append((atual[0], atual[-1] + 1))
    saida = []
    for a, b in partes:
        while a < b and inicio_invalido(doc[a]):
            a += 1
        while b > a and fim_invalido(doc[b - 1]):
            b -= 1
        if 0 < b - a <= maximo:
            saida.append((a, b))
    return saida


def preparar(nlp, dados: list[dict], rotulos: tuple[str, ...]) -> list[dict]:
    """Documentos normalizados, com as entidades de cada rótulo em posições do texto normalizado.

    Cada item traz ``texto``, ``fonte``, ``doc`` (tokens), ``entidades`` (rótulo → lista de entidades,
    cada uma com a lista de ocorrências ``(início, fim)``, como no gabarito) e ``trechos`` (partes
    propostas pelo sugestor da detecção, ver :func:`segmentar`, para o treino).
    """
    maximo = SUGESTOR_DETECCAO["max_size"]
    saida = []
    for d in dados:
        fonte = d.get("fonte", "esic")
        localizar = ocorrencias_oficial if fonte == "oficial" else ocorrencias_esic
        norm = normalizar(d["text"])
        doc = nlp.make_doc(norm.texto)
        entidades: dict[str, list[list[tuple[int, int]]]] = {r: [] for r in rotulos}
        trechos: set[tuple[int, int, str]] = set()
        for e in d["entities"]:
            if e["type"] not in rotulos:
                continue
            occ = [p for a, b in localizar(d["text"], e["value"]) if (p := posicoes_normalizadas(norm, a, b))]
            if not occ:
                continue
            entidades[e["type"]].append(occ)
            for a, b in occ:
                span = doc.char_span(a, b, alignment_mode="expand")
                if span is not None and len(span):
                    trechos.update((x, y, e["type"]) for x, y in segmentar(doc, span.start, span.end, maximo))
        saida.append({"texto": norm.texto, "fonte": fonte, "doc": doc, "entidades": entidades,
                      "trechos": sorted(trechos)})
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
    """Fração dos n-gramas mantida pela poda da detecção e partes anotadas que ela descartaria."""
    minimo, maximo = SUGESTOR_DETECCAO["min_size"], SUGESTOR_DETECCAO["max_size"]
    mantidos = todos = descartadas = 0
    for it in itens:
        doc = it["doc"]
        sugeridos = sugerir_sintagmas([doc], minimo, maximo)
        pares = {(int(a), int(b)) for a, b in sugeridos.dataXd} if len(sugeridos.dataXd) else set()
        mantidos += len(pares)
        todos += sum(max(0, len(doc) - k + 1) for k in range(minimo, maximo + 1))
        descartadas += sum((a, b) not in pares for a, b, _ in it["trechos"])
    return {"candidatos_mantidos": round(mantidos / max(1, todos), 4), "partes_do_ajuste_descartadas": descartadas}


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
            if not n:
                saida.append([])
                continue
            classe = bloco.argmax(axis=1)
            linhas = numpy.nonzero((classe < len(rotulos)) & (bloco.max(axis=1) >= minimo))[0]
            saida.append([(doc[int(idx[i, 0])].idx, doc[int(idx[i, 1]) - 1].idx + len(doc[int(idx[i, 1]) - 1]),
                           rotulos[int(classe[i])], float(bloco[i, classe[i]])) for i in linhas])
    return saida


def metricas(itens: list[dict], previstos: list[list[tuple]], rotulos: tuple[str, ...]) -> dict:
    """Cobertura das entidades e precisão por caractere, por rótulo, limiar e modo (só agregados).

    Só entram os rótulos com entidades anotadas nos documentos. O modo escolhido é o de maior média,
    entre os rótulos de :data:`ROTULOS_ESCOLHA`, do melhor F1 de cada rótulo nesse modo; o limiar de
    cada rótulo é o de maior F1 no modo escolhido.
    """
    presentes = [r for r in rotulos if any(it["entidades"][r] for it in itens)]
    grades: dict = {}
    for rotulo in presentes:
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
                               "f1": round(f1, 4), "entidades": total})
            por_modo[modo] = linhas
        grades[rotulo] = por_modo

    escolha = [r for r in presentes if r in ROTULOS_ESCOLHA] or presentes

    def melhor(rotulo: str, modo: str) -> dict:
        return max(grades[rotulo][modo], key=lambda linha: (linha["f1"], -linha["limiar"]))

    def media(modo: str) -> float:
        return sum(melhor(r, modo)["f1"] for r in escolha) / max(1, len(escolha))

    modo = max(MODOS, key=media)
    return {"modo": modo, "f1_medio": round(media(modo), 4),
            "melhor_por_rotulo": {r: melhor(r, modo) for r in presentes}, "grade": grades}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--epocas", type=int, default=10)
    ap.add_argument("--lote", type=int, default=16, help="documentos por atualização")
    ap.add_argument("--minutos", type=float, default=50.0, help="tempo máximo de treino")
    ap.add_argument("--semente", type=int, default=20261116)
    ap.add_argument("--abandono", type=float, default=0.1, help="taxa de dropout")
    ap.add_argument("--peso-negativo", type=float, default=0.03, help="peso da classe negativa na perda")
    ap.add_argument("--rotulos", nargs="+", default=list(ROTULOS), choices=ROTULOS)
    ap.add_argument("--repeticoes-oficial", type=int, default=2, help="vezes que cada documento oficial entra por época")
    ap.add_argument("--sugestor-treino", choices=sorted(SUGESTORES), default="sintagmas")
    ap.add_argument("--fora-do-dominio", type=int, default=1000,
                    help="textos fora do domínio, sem trechos anotados, acrescentados ao treino")
    ap.add_argument("--limite", type=int, default=0, help="usa só os N primeiros documentos de cada fonte (teste rápido)")
    ap.add_argument("--saida", type=Path, default=RAIZ / "src" / "themis_lgpd" / "dados" / "modelos" / "sensivel")
    ap.add_argument("--relatorio", type=Path, default=PASTA / "resultado_spancat.json")
    ap.add_argument("--pontos", type=Path, default=RAIZ / ".trabalho" / "pontos_spancat",
                    help="pasta onde o estado de cada época é gravado")
    args = ap.parse_args()
    rotulos = tuple(r for r in ROTULOS if r in args.rotulos)

    fix_random_seed(args.semente)
    gerador = random.Random(args.semente)
    nlp = spacy.load(MODELO_BASE, exclude=["tok2vec", "morphologizer", "parser", "senter", "attribute_ruler",
                                           "lemmatizer", "ner"])
    esic_ajuste, esic_selecao = carregar("ajuste"), carregar("selecao")
    oficial_ajuste, oficial_selecao = carregar_oficial("ajuste"), carregar_oficial("selecao")
    if args.limite:
        esic_ajuste, esic_selecao = esic_ajuste[:args.limite], esic_selecao[:args.limite]
        oficial_ajuste, oficial_selecao = oficial_ajuste[:args.limite], oficial_selecao[:args.limite]
    t0 = time.perf_counter()
    externos = textos_fora_do_dominio(random.Random(args.semente + 1), args.fora_do_dominio)
    treino_itens = (preparar(nlp, esic_ajuste, rotulos) + preparar(nlp, oficial_ajuste, rotulos)
                    + preparar(nlp, externos, rotulos))
    selecoes = {"esic": preparar(nlp, esic_selecao, rotulos), "oficial": preparar(nlp, oficial_selecao, rotulos)}
    treino = [ex for ex, it in zip(exemplos(nlp, treino_itens), treino_itens)
              for _ in range(args.repeticoes_oficial if it["fonte"] == "oficial" else 1)]
    print(f"{len(treino)} exemplos de treino ({len(esic_ajuste)} pedidos, {len(oficial_ajuste)} documentos oficiais "
          f"x{args.repeticoes_oficial}, {len(externos)} textos fora do domínio), seleção: {len(esic_selecao)} pedidos e "
          f"{len(oficial_selecao)} documentos "
          f"({time.perf_counter() - t0:.0f} s de preparação)", flush=True)

    config = {**CONFIG, "negative_weight": args.peso_negativo, "suggester": SUGESTORES[args.sugestor_treino]}
    componente = nlp.add_pipe(FABRICA, name=NOME_COMPONENTE, config=config)
    componente.initialize(lambda: treino, nlp=nlp, labels=list(rotulos))
    otimizador = Adam(**OTIMIZADOR)
    args.pontos.mkdir(parents=True, exist_ok=True)

    epocas, melhor, melhor_pesos = [], None, None
    inicio = time.perf_counter()
    for epoca in range(1, args.epocas + 1):
        t_epoca = time.perf_counter()
        gerador.shuffle(treino)
        perdas: dict[str, float] = {}
        for lote in minibatch(treino, size=args.lote):
            componente.update(lote, drop=args.abandono, sgd=otimizador, losses=perdas)
        duracao_treino = time.perf_counter() - t_epoca
        pesos = componente.model.to_bytes()
        (args.pontos / f"epoca_{epoca:02d}.bin").write_bytes(pesos)
        t_aval = time.perf_counter()
        avaliacoes = {nome: metricas(itens, candidatos(componente, [it["doc"] for it in itens], min(LIMIARES)), rotulos)
                      for nome, itens in selecoes.items()}
        f1_medio = round(sum(a["f1_medio"] for a in avaliacoes.values()) / len(avaliacoes), 4)
        registro = {"epoca": epoca, "perda": round(perdas.get(NOME_COMPONENTE, 0.0), 2),
                    "segundos_treino": round(duracao_treino), "segundos_avaliacao": round(time.perf_counter() - t_aval),
                    "f1_medio_selecao": f1_medio,
                    "selecao": {nome: {k: a[k] for k in ("modo", "f1_medio", "melhor_por_rotulo")}
                                for nome, a in avaliacoes.items()},
                    "grade": {nome: a["grade"] for nome, a in avaliacoes.items()}}
        epocas.append(registro)
        print(json.dumps({k: v for k, v in registro.items() if k != "grade"}, ensure_ascii=False), flush=True)
        if melhor is None or f1_medio > melhor["f1_medio_selecao"]:
            melhor, melhor_pesos = registro, pesos
        decorrido = time.perf_counter() - inicio
        if decorrido + decorrido / epoca > args.minutos * 60:
            print(f"Limite de {args.minutos:g} minutos: treino encerrado na época {epoca}.", flush=True)
            break

    componente.model.from_bytes(melhor_pesos)
    vetores = nlp.vocab.vectors
    meta = {
        "versao": 2,
        "descricao": "Classificador de trechos (spaCy spancat) para dados de saúde, dados sensíveis e nomes de pessoas",
        "rotulos": list(rotulos),
        "fabrica": FABRICA,
        "limiares": {r: v["limiar"] for r, v in melhor["selecao"]["oficial"]["melhor_por_rotulo"].items()},
        "decodificacao": melhor["selecao"]["oficial"]["modo"],
        "ativo_por_padrao": False,
        "vetores": {"modelo": MODELO_BASE, "versao_modelo": nlp.meta.get("version"), "nome": vetores.name,
                    "forma": list(vetores.shape)},
        "treino": {
            "dados": ("EliMC/esic-ner (CC BY 4.0), partição ajuste; corpus de documentos oficiais fictícios "
                      "(benchmark/oficial, produção própria), partição ajuste; seleção da época e dos limiares nas "
                      "partições selecao dos dois corpora"),
            "sha256_train": sha256((CACHE / "esic-ner-train.jsonl").read_bytes()),
            "sha256_particoes": sha256(ARQUIVO_PARTICOES.read_bytes()),
            "sha256_documentos_ajuste": sha256("\n".join(sorted(d["text"] for d in esic_ajuste)).encode("utf-8")),
            "sha256_oficial_ajuste": sha256((OFICIAL / "ajuste.jsonl").read_bytes()),
            "documentos": {"esic_ajuste": len(esic_ajuste), "esic_selecao": len(esic_selecao),
                           "oficial_ajuste": len(oficial_ajuste), "oficial_selecao": len(oficial_selecao)},
            "repeticoes_oficial": args.repeticoes_oficial, "sugestor_treino": args.sugestor_treino,
            "textos_fora_do_dominio": args.fora_do_dominio,
            "semente": args.semente, "lote": args.lote, "abandono": args.abandono, "epocas_maximas": args.epocas,
            "epocas_executadas": len(epocas), "melhor_epoca": melhor["epoca"],
            "minutos": round((time.perf_counter() - inicio) / 60, 1),
            "otimizador": {"nome": "Adam", **OTIMIZADOR}, "config": config,
            "versoes": {"spacy": spacy.__version__, "thinc": thinc.__version__, "numpy": numpy.__version__,
                        "python": platform.python_version()},
        },
        "selecao": {"f1_medio": melhor["f1_medio_selecao"], "esic": melhor["selecao"]["esic"]["melhor_por_rotulo"],
                    "oficial": melhor["selecao"]["oficial"]["melhor_por_rotulo"]},
    }
    destino = args.saida
    with tempfile.TemporaryDirectory() as tmp:
        componente.to_disk(tmp, exclude=["vocab"])
        destino.mkdir(parents=True, exist_ok=True)
        for nome in ("cfg", "model"):
            shutil.copyfile(Path(tmp) / nome, destino / nome)
    cfg = json.loads((destino / "cfg").read_text(encoding="utf-8"))
    (destino / "cfg").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (destino / "config.json").write_text(json.dumps({**config, "suggester": SUGESTOR_DETECCAO}, ensure_ascii=False,
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
