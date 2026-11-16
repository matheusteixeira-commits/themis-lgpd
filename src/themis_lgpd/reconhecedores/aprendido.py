"""Reconhecedor aprendido de dados de saúde e de quase-identificadores.

Complementa as regras de :mod:`themis_lgpd.reconhecedores.sensiveis` com um classificador de trechos
(componente ``spancat`` do spaCy) treinado sobre pedidos de acesso à informação — conjunto
EliMC/esic-ner, CC BY 4.0; ver ``benchmark/treino/treinar_spancat.py``. O classificador avalia os
trechos de 1 a 20 tokens com bordas plausíveis (ver :func:`sugerir_sintagmas`) e estima, para cada um,
a probabilidade de ser:

``DADO_SAUDE``
    Doença, sintoma, procedimento, medicamento ou condição de saúde, inclusive quando descrito com
    palavras próprias ("dores fortes", "falta de ar"). Produz achados do tipo ``SAUDE`` na camada
    semântica: o perfil continua decidindo, pela regra de vínculo, se o termo é tarjado (frase que
    se refere a uma pessoa) ou apenas sinalizado (conteúdo de interesse público).
``QUASI_IDENTIFICADOR``
    Descrição que aponta para uma pessoa sem nomeá-la ("a atendente do guichê 4 no plantão da
    manhã"). Produz achados do tipo ``QUASE_IDENTIFICADOR``.

O componente é acrescentado ao pipeline do ``pt_core_news_lg`` já carregado pelo Themis e usa o mesmo
vocabulário e os mesmos vetores estáticos, que não fazem parte do artefato. Sem o artefato, sem modelo
de linguagem ou com vetores diferentes dos usados no treino, nada é acrescentado e a detecção segue
apenas com as regras. A ativação padrão vem dos metadados do artefato (``ativo_por_padrao``, definido
pela avaliação na partição de seleção) e pode ser alterada pela variável de ambiente
``THEMIS_MODELO_SENSIVEL`` (``1`` liga, ``0`` desliga).

A confiança de cada achado deriva da probabilidade estimada: o limiar escolhido na seleção corresponde
à confiança 0,6 — a mínima do perfil LAI para aplicar a regra da categoria — e a probabilidade 1, a 0,9.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

import numpy
from presidio_analyzer import AnalysisExplanation, EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts
from spacy.util import registry
from thinc.api import get_current_ops
from thinc.types import Ragged

from .base import CONTEXTUAL, SEMANTICA, Deteccao

#: Pasta do artefato: pesos (``model``), configuração do componente e metadados do treino.
PASTA = Path(__file__).resolve().parent.parent / "dados" / "modelos" / "sensivel"
#: Nome do componente no pipeline do spaCy e chave dos trechos candidatos em ``Doc.spans``.
NOME_COMPONENTE = "themis_sensivel"
#: Rótulo do classificador → (tipo de dado do Themis, camada).
TIPOS = {"DADO_SAUDE": ("SAUDE", SEMANTICA), "QUASI_IDENTIFICADOR": ("QUASE_IDENTIFICADOR", CONTEXTUAL)}
#: Confiança atribuída a um trecho com probabilidade igual ao limiar e com probabilidade 1.
CONFIANCA_NO_LIMIAR, CONFIANCA_MAXIMA = 0.6, 0.9
#: Tamanho mínimo, em tokens, por rótulo: um quase-identificador combina função e local ou horário
#: ("motorista da linha 12"), o que exige ao menos três tokens.
MINIMO_DE_TOKENS = {"QUASI_IDENTIFICADOR": 3}

#: Artigos, preposições (e contrações), conjunções e pronomes oblíquos: classes fechadas que não começam
#: nem terminam a descrição de uma condição de saúde ou de uma pessoa. A comparação diferencia
#: maiúsculas ("Hepatite A", tipo sanguíneo "O").
PALAVRAS_FUNCIONAIS = frozenset({
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "em", "no", "na", "nos",
    "nas", "num", "numa", "por", "pelo", "pela", "pelos", "pelas", "para", "pra", "com", "sem", "ao", "aos",
    "à", "às", "entre", "sobre", "até", "desde", "sob", "e", "ou", "mas", "nem", "que", "se", "porque", "pois",
    "como", "quando", "onde", "me", "te", "lhe", "lhes",
})
#: Pontuação que encerra frase: um trecho não a atravessa.
_FIM_DE_FRASE = frozenset(".!?;")

_log = logging.getLogger(__name__)


def _inicio_invalido(token) -> bool:
    return token.is_punct or token.is_space or token.text in PALAVRAS_FUNCIONAIS


def _fim_invalido(token) -> bool:
    # O parêntese que fecha uma sigla integra o trecho: "Lesão por Esforço Repetitivo (LER)".
    return (token.is_punct and token.text != ")") or token.is_space or token.text in PALAVRAS_FUNCIONAIS


def _interior_invalido(token) -> bool:
    return token.is_space or token.text in _FIM_DE_FRASE or "\n" in token.text


def sugerir_sintagmas(docs, min_size: int = 1, max_size: int = 20, *, ops=None) -> Ragged:
    """Trechos candidatos: n-gramas de ``min_size`` a ``max_size`` tokens com bordas e interior plausíveis.

    Descarta os que começam ou terminam em pontuação, espaço ou palavra funcional ("de", "a", "que") e
    os que atravessam fim de frase ou quebra de linha. O classificador pontua cada trecho de forma
    independente, de modo que a poda não altera a probabilidade dos demais; ela reduz a cerca de um
    quinto o número de candidatos e, na mesma proporção, o custo da classificação. Na partição de ajuste,
    nenhuma entidade anotada é descartada.
    """
    ops = ops or get_current_ops()
    pares: list[tuple[int, int]] = []
    tamanhos: list[int] = []
    for doc in docs:
        antes = len(pares)
        inicio_ruim = [_inicio_invalido(t) for t in doc]
        fim_ruim = [_fim_invalido(t) for t in doc]
        interior_ruim = [_interior_invalido(t) for t in doc]
        n = len(doc)
        for i in range(n):
            if inicio_ruim[i]:
                continue
            for j in range(i + min_size, min(n, i + max_size) + 1):
                if j - i > 2 and interior_ruim[j - 2]:
                    break  # o token j - 2 é interior deste trecho e de todos os mais longos
                if not fim_ruim[j - 1]:
                    pares.append((i, j))
        tamanhos.append(len(pares) - antes)
    if not pares:
        return Ragged(ops.xp.zeros((0, 0), dtype="i"), ops.asarray1i(tamanhos))
    return Ragged(ops.asarray2i(numpy.asarray(pares, dtype="i")), ops.asarray1i(tamanhos))


@registry.misc("themis.sugestor_sintagmas.v1")
def criar_sugestor_sintagmas(min_size: int = 1, max_size: int = 20):
    """Sugestor de candidatos do classificador (ver :func:`sugerir_sintagmas`), registrado no spaCy."""

    def sugerir(docs, *, ops=None) -> Ragged:
        return sugerir_sintagmas(docs, min_size, max_size, ops=ops)

    return sugerir


@lru_cache(maxsize=1)
def metadados() -> dict | None:
    """Metadados do artefato (``meta.json``), ou ``None`` se o artefato não estiver instalado."""
    meta = PASTA / "meta.json"
    if not (meta.is_file() and (PASTA / "model").is_file() and (PASTA / "config.json").is_file()):
        return None
    return json.loads(meta.read_text(encoding="utf-8"))


def ativo() -> bool:
    """Indica se o classificador deve ser usado: artefato instalado e ativação padrão ou por variável."""
    meta = metadados()
    if meta is None:
        return False
    valor = os.environ.get("THEMIS_MODELO_SENSIVEL", "").strip().lower()
    if valor:
        return valor in {"1", "true", "sim", "yes", "on"}
    return bool(meta.get("ativo_por_padrao"))


def acoplar(nlp) -> bool:
    """Acrescenta o classificador ao fim do pipeline ``nlp``, compartilhando o vocabulário e os vetores.

    A operação é idempotente. Nada é acrescentado se o classificador estiver desativado ou se os
    vetores do pipeline não forem os usados no treino (a projeção aprendida não se aplicaria a eles).

    Returns:
        Se o componente está no pipeline.
    """
    if NOME_COMPONENTE in nlp.pipe_names:
        return True
    meta = metadados()
    if meta is None or not ativo():
        return False
    vetores = nlp.vocab.vectors
    esperado = meta["vetores"]
    if list(vetores.shape) != list(esperado["forma"]) or vetores.name != esperado["nome"]:
        _log.warning("Classificador de dados sensíveis não carregado: vetores do modelo de linguagem diferentes "
                     "dos usados no treino (%s %s).", esperado["nome"], esperado["forma"])
        return False
    config = json.loads((PASTA / "config.json").read_text(encoding="utf-8"))
    componente = nlp.add_pipe(meta.get("fabrica", "spancat_singlelabel"), name=NOME_COMPONENTE, config=config)
    componente.from_disk(PASTA, exclude=["vocab"])
    return True


def confianca(probabilidade: float, limiar: float) -> float:
    """Converte a probabilidade estimada em confiança (ver a descrição do módulo)."""
    fracao = (probabilidade - limiar) / max(1e-6, 1.0 - limiar)
    return round(CONFIANCA_NO_LIMIAR + (CONFIANCA_MAXIMA - CONFIANCA_NO_LIMIAR) * min(1.0, max(0.0, fracao)), 3)


def selecionar(candidatos: list[tuple[int, int, str, float]], limiares: dict[str, float],
               modo: str = "maximo") -> list[tuple[int, int, str, float]]:
    """Escolhe os trechos a reportar entre os candidatos ``(início, fim, rótulo, probabilidade)``.

    Candidatos abaixo do limiar do rótulo são descartados. Entre os demais, do mesmo rótulo e
    sobrepostos, o modo ``maximo`` mantém o de maior probabilidade (e descarta os que o cruzam); o
    modo ``uniao`` funde-os num único trecho, com a maior probabilidade do grupo.
    """
    saida: list[tuple[int, int, str, float]] = []
    for rotulo, limiar in limiares.items():
        acima = [c for c in candidatos if c[2] == rotulo and c[3] >= limiar]
        if modo == "uniao":
            fundidos: list[list] = []
            for ini, fim, _, prob in sorted(acima):
                if fundidos and ini < fundidos[-1][1]:
                    fundidos[-1][1] = max(fundidos[-1][1], fim)
                    fundidos[-1][3] = max(fundidos[-1][3], prob)
                else:
                    fundidos.append([ini, fim, rotulo, prob])
            saida += [tuple(f) for f in fundidos]
            continue
        aceitos: list[tuple[int, int, str, float]] = []
        for c in sorted(acima, key=lambda c: (-c[3], c[0], -c[1])):
            if not any(a[0] < c[1] and c[0] < a[1] for a in aceitos):
                aceitos.append(c)
        saida += aceitos
    return sorted(saida)


def candidatos_do_doc(doc) -> list[tuple[int, int, str, float]]:
    """Trechos ``(início, fim, rótulo, probabilidade)`` registrados pelo componente no documento.

    Trechos mais curtos que o mínimo do rótulo (:data:`MINIMO_DE_TOKENS`) são descartados.
    """
    if NOME_COMPONENTE not in doc.spans:
        return []
    grupo = doc.spans[NOME_COMPONENTE]
    probabilidades = grupo.attrs.get("scores", ())
    return [(s.start_char, s.end_char, s.label_, float(p)) for s, p in zip(grupo, probabilidades)
            if len(s) >= MINIMO_DE_TOKENS.get(s.label_, 1)]


def deteccoes(doc) -> list[Deteccao]:
    """Achados do classificador num documento já processado pelo pipeline."""
    meta = metadados()
    if meta is None:
        return []
    limiares = meta["limiares"]
    saida = []
    for ini, fim, rotulo, prob in selecionar(candidatos_do_doc(doc), limiares, meta.get("decodificacao", "maximo")):
        tipo, camada = TIPOS[rotulo]
        saida.append(Deteccao(ini, fim, tipo, confianca(prob, limiares[rotulo]), f"aprendido:{rotulo.lower()}",
                              camada, contexto_aplicado=True))
    return saida


class ReconhecedorAprendido(EntityRecognizer):
    """Achados do classificador a partir do documento já processado pelo ``SpacyNlpEngine``.

    Não executa o modelo: lê os trechos que o componente ``themis_sensivel`` registrou no documento
    durante o processamento em lote (ver :func:`acoplar`). Sem o componente, não produz achados.
    """

    def __init__(self, idioma: str = "pt"):
        super().__init__(supported_entities=sorted({t for t, _ in TIPOS.values()}), name="BR_Sensivel_Aprendido",
                         supported_language=idioma)

    def load(self) -> None:
        """Nada a carregar: o componente pertence ao pipeline do ``SpacyNlpEngine``."""

    def analyze(self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None):
        """Converte os achados do classificador em ``RecognizerResult``."""
        if nlp_artifacts is None or nlp_artifacts.tokens is None:
            return []
        saida = []
        for d in deteccoes(nlp_artifacts.tokens):
            saida.append(RecognizerResult(d.tipo, d.inicio, d.fim, d.score,
                                          analysis_explanation=AnalysisExplanation(
                                              recognizer=self.name, original_score=d.score,
                                              textual_explanation="Classificador de trechos treinado"),
                                          recognition_metadata={
                                              RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                                              RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id,
                                              RecognizerResult.IS_SCORE_ENHANCED_BY_CONTEXT_KEY: True,
                                              "origem": d.origem, "camada": d.camada}))
        return saida
