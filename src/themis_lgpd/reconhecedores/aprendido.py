"""Reconhecedor aprendido de dados de saúde, dados sensíveis, nomes de pessoas e quase-identificadores.

Complementa as regras de :mod:`themis_lgpd.reconhecedores.sensiveis` e de
:mod:`themis_lgpd.reconhecedores.nomes` com um classificador de trechos (componente ``spancat`` do
spaCy) treinado sobre pedidos de acesso à informação — conjunto EliMC/esic-ner, CC BY 4.0 — e sobre um
corpus de documentos oficiais fictícios de produção própria (laudos, prontuários, relatórios sociais,
portarias, processos disciplinares); ver ``benchmark/treino/treinar_spancat.py``. O classificador
avalia os trechos de 1 a 20 tokens com bordas plausíveis (ver :func:`sugerir_sintagmas`) e estima, para
cada um, a probabilidade de ser:

``DADO_SAUDE``
    Doença, sintoma, achado de exame, procedimento, medicamento ou condição de saúde de uma pessoa,
    inclusive quando descrito com palavras próprias ("dores fortes", "falta de ar") ou em linguagem
    clínica. Produz achados do tipo ``SAUDE`` na camada semântica: o perfil continua decidindo, pela
    regra de vínculo, se o termo é tarjado (frase que se refere a uma pessoa) ou apenas sinalizado
    (conteúdo de interesse público). Acima do limiar contextual do rótulo (``limiares_contextuais``
    nos metadados), quando definido, o achado vai para a camada contextual e é tarjado sem a regra de
    vínculo.
``DADO_SENSIVEL``
    Origem racial ou étnica, convicção religiosa, opinião política, filiação sindical, vida ou
    orientação sexual e dado biométrico ligados a pessoa ("indígena da etnia …", "membro da igreja
    …"). O tipo do achado é inferido do próprio trecho (:func:`tipo_sensivel`); trecho sem indicação
    da categoria não produz achado. Segue a regra de vínculo, como os termos sensíveis das regras.
``NOME_PESSOA``
    Nome de pessoa natural, inclusive em caixa alta, em tabelas e em assinaturas. Produz achados do
    tipo ``NOME``, tratados como os do modelo de linguagem.
``QUASI_IDENTIFICADOR``
    Descrição que aponta para uma pessoa sem nomeá-la ("a atendente do guichê 4 no plantão da
    manhã"). Produziria achados do tipo ``QUASE_IDENTIFICADOR``; está desativado no artefato atual,
    porque sinalizava frases de expediente e funções descritas em abstrato.

Só os rótulos com limiar em ``limiares`` produzem achados; os demais ficam em ``rotulos_desativados``,
com o motivo registrado pela ablação no sistema completo (``benchmark/treino/ablacao_spancat.py``).

O componente é acrescentado ao pipeline do ``pt_core_news_lg`` já carregado pelo Themis e usa o mesmo
vocabulário e os mesmos vetores estáticos, que não fazem parte do artefato. Sem o artefato, sem modelo
de linguagem ou com vetores diferentes dos usados no treino, nada é acrescentado e a detecção segue
apenas com as regras. A ativação padrão vem dos metadados do artefato (``ativo_por_padrao``, definido
pela avaliação nas partições de seleção) e pode ser alterada pela variável de ambiente
``THEMIS_MODELO_SENSIVEL`` (``1`` liga, ``0`` desliga).

A confiança de cada achado deriva da probabilidade estimada: o limiar escolhido na seleção corresponde
à confiança 0,6 — a mínima do perfil LAI para aplicar a regra da categoria — e a probabilidade 1, a 0,9.
"""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path

import numpy
from presidio_analyzer import AnalysisExplanation, EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts
from spacy.util import registry
from thinc.api import get_current_ops
from thinc.types import Ragged

from . import localizacao, nomes
from .base import CONTEXTUAL, NER, SEMANTICA, Deteccao

#: Pasta do artefato: pesos (``model``), configuração do componente e metadados do treino.
PASTA = Path(__file__).resolve().parent.parent / "dados" / "modelos" / "sensivel"
#: Nome do componente no pipeline do spaCy e chave dos trechos candidatos em ``Doc.spans``.
NOME_COMPONENTE = "themis_sensivel"
#: Rótulo do classificador → (tipo de dado do Themis, camada). O tipo de ``DADO_SENSIVEL`` é inferido
#: do trecho (:func:`tipo_sensivel`).
TIPOS = {"DADO_SAUDE": ("SAUDE", SEMANTICA), "DADO_SENSIVEL": (None, SEMANTICA), "NOME_PESSOA": ("NOME", NER),
         "QUASI_IDENTIFICADOR": ("QUASE_IDENTIFICADOR", CONTEXTUAL)}
#: Categoria de dado sensível (LGPD, art. 5º, II) pelo vocabulário do trecho, na ordem de verificação:
#: a sigla ou o nome de sindicato e de partido decidem antes das demais palavras ("filiado ao
#: sindicato", "filiado ao partido").
CATEGORIAS_SENSIVEIS = (
    ("FILIACAO_SINDICAL", r"sindic|sindical|centra(?:l|is) sindica"),
    ("OPINIAO_POLITICA", r"partid[oá]|diret[óo]rio|militan|pol[íi]tic[oa]|ideolog|eleitor"),
    ("VIDA_SEXUAL", r"sexua|homoss|homoaf|homof|bissex|heteross|l[ée]sbic|\bgays?\b|"
                    r"trans(?:g[êe]ner|sex|exua|fobia)|travesti|cisg[êe]ner|lgbt|intersex|queer|g[êe]nero|afetiv"),
    ("ORIGEM_RACIAL", r"ind[íi]gena|etnia|[ée]tnic|quilomb|\bra[çc]as?\b|\bcor\b|\bpret[oa]s?\b|\bpard[oa]s?\b|"
                      r"\bnegr[oa]s?\b|\bbranc[oa]s?\b|\bamarel[oa]s?\b|afrodescend|afro-brasileir|cigan|aldeia"),
    ("RELIGIAO", r"relig|igreja|templo|terreiro|esp[íi]rit[ai]|cat[óo]lic|evang[ée]lic|protestant|pentecost|"
                 r"batista|luteran|presbiter|metodista|adventista|jeov[áa]|m[óo]rmon|candombl|umband|orix|"
                 r"\bde santo\b|budis|judai|judeu|judia|sinagoga|isl[âa]m|mu[çc]ulman|mesquita|\bateu\b|\bateia\b|"
                 r"agn[óo]stic|crist[ãa]|par[óo]quia|\bcultos?\b|\bmissas?\b|\bf[ée]\b|cren[çc]a|devot"),
    ("GENETICO_BIOMETRICO", r"biometr|impress(?:ão|ões) digita|gen[ée]tic|\bdna\b|genoma|\b[íi]ris\b|"
                            r"reconhecimento facial"),
)
_CATEGORIAS_SENSIVEIS = tuple((tipo, re.compile(padrao, re.IGNORECASE)) for tipo, padrao in CATEGORIAS_SENSIVEIS)
#: Trecho que é só uma idade ou uma duração ("≥ 18 anos", "maiores de 60 anos", "30 dias"): não é dado de
#: saúde, ainda que o classificador o confunda com as medidas que acompanham achados clínicos. A idade
#: de pessoa é tratada pelas regras de data de nascimento; a duração de um afastamento, sozinha, não
#: revela a condição. Semanas ficam fora, porque a idade gestacional é dado de saúde ("38 semanas").
_SO_IDADE_OU_DURACAO = re.compile(
    r"(?:idade\s*(?:de\s*)?)?(?:[<>≤≥=]=?|(?:maior|menor)(?:es)?\s+(?:ou\s+igua(?:l|is)\s+a\s+)?(?:de|que)|"
    r"acima\s+de|abaixo\s+de|at[ée]|a\s+partir\s+de|entre)?\s*\d+(?:[.,]\d+)?(?:\s*(?:a|e)\s*\d+(?:[.,]\d+)?)?"
    r"\s*(?:\(\w+\)\s*)?(?:anos?|mes(?:es)?|m[êe]s|dias?|horas?)(?:\s+de\s+idade)?",
    re.IGNORECASE,
)
#: Primeira palavra de um trecho e o espaço seguinte (para retirar pronomes de tratamento).
_PALAVRA_INICIAL = re.compile(r"(\S+)\s+")
#: Nome próprio de unidade, instituição, logradouro, norma ou honraria que termina pelo nome de quem é
#: homenageado: a palavra que designa a entidade seguida só de palavras capitalizadas, abreviaturas e
#: conectivos, separados por espaços, até o nome ("Unidade Básica de Saúde Dr. Fulano", "Escola
#: Municipal de Ensino Fundamental Professora Fulana", "Prêmio Estadual de Inovação Fulano de Tal").
#: Tabulação, quebra de linha e pontuação encerram a sequência (célula de tabela, linha de assinatura).
_INSTITUICAO_ANTES = re.compile(
    r"(?i:\b(?:hospital|maternidade|policl[íi]nica|cl[íi]nica|unidade|ubs|upa|caps|cras|creas|centro|posto|"
    r"escola|col[ée]gio|creche|instituto|funda[çc][ãa]o|universidade|faculdade|campus|biblioteca|museu|teatro|"
    r"audit[óo]rio|plen[áa]rio|sala|gin[áa]sio|est[áa]dio|parque|pra[çc]a|rua|avenida|travessa|alameda|rodovia|"
    r"estrada|viaduto|ponte|conjunto|residencial|loteamento|edif[íi]cio|lei|decreto|programa|projeto|pr[êe]mio|"
    r"medalha|comenda|ordem|c[áa]tedra|turma|f[óo]rum|distrito|munic[íi]pio|cidade|comarca))"
    r"(?: +(?:[A-ZÀ-Ý][\wÀ-ÿ]*\.?|d[aeo]s?|e))* +$"
)
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


def inicio_invalido(token) -> bool:
    """Indica que um trecho candidato não pode começar no token."""
    return token.is_punct or token.is_space or token.text in PALAVRAS_FUNCIONAIS


def fim_invalido(token) -> bool:
    """Indica que um trecho candidato não pode terminar no token."""
    # O parêntese que fecha uma sigla integra o trecho: "Lesão por Esforço Repetitivo (LER)".
    return (token.is_punct and token.text != ")") or token.is_space or token.text in PALAVRAS_FUNCIONAIS


def interior_invalido(token) -> bool:
    """Indica que um trecho candidato não pode atravessar o token (fim de frase ou quebra de linha)."""
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
        inicio_ruim = [inicio_invalido(t) for t in doc]
        fim_ruim = [fim_invalido(t) for t in doc]
        interior_ruim = [interior_invalido(t) for t in doc]
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

    Trechos mais curtos que o mínimo do rótulo (:data:`MINIMO_DE_TOKENS`) são descartados. O componente de
    rótulo único grava as probabilidades com formato ``(n, 1)``; o vetor é achatado antes da conversão.
    """
    if NOME_COMPONENTE not in doc.spans:
        return []
    grupo = doc.spans[NOME_COMPONENTE]
    probabilidades = numpy.ravel(grupo.attrs.get("scores", ()))
    return [(s.start_char, s.end_char, s.label_, float(p)) for s, p in zip(grupo, probabilidades)
            if len(s) >= MINIMO_DE_TOKENS.get(s.label_, 1)]


def tipo_sensivel(trecho: str) -> str | None:
    """Tipo de dado sensível (ver :data:`CATEGORIAS_SENSIVEIS`) indicado pelo vocabulário do trecho, ou ``None``."""
    for tipo, padrao in _CATEGORIAS_SENSIVEIS:
        if padrao.search(trecho):
            return tipo
    return None


def limites_do_nome(texto: str, inicio: int, fim: int) -> tuple[int, int] | None:
    """Limites de um nome de pessoa proposto pelo classificador, ou ``None`` se o trecho não designa pessoa.

    Pronomes de tratamento e títulos iniciais saem do trecho ("Dra. Fulana" → "Fulana"), como nas
    regras. É descartado o nome que integra o de lugar, instituição, norma ou programa ("Hospital
    Estadual Dr. Fulano", "Lei Fulana de Tal", "Prefeitura de Conselheiro Lafaiete") — mesmo critério do
    reconhecimento de nomes e da propagação (:func:`themis_lgpd.reconhecedores.nomes.contexto_nao_pessoal`)
    —, o que encerra o nome próprio de uma unidade ou honraria (:data:`_INSTITUICAO_ANTES`) e o trecho
    que é, por inteiro, o nome de um município ("Presidente Prudente", "Teixeira de Freitas").
    """
    while (m := _PALAVRA_INICIAL.match(texto, inicio, fim)) is not None and nomes.TITULOS.match(m.group(1)):
        inicio = m.end()
    if inicio >= fim or nomes.contexto_nao_pessoal(texto, inicio) or localizacao.municipio_em(texto, inicio) == fim:
        return None
    if _INSTITUICAO_ANTES.search(texto, max(0, inicio - 120), inicio):
        return None
    return inicio, fim


def deteccoes(doc) -> list[Deteccao]:
    """Achados do classificador num documento já processado pelo pipeline.

    Só os rótulos com limiar nos metadados produzem achados. Um trecho com probabilidade igual ou
    superior ao limiar contextual do rótulo (``limiares_contextuais``) vai para a camada contextual.
    Nomes de pessoas passam por :func:`limites_do_nome`; dados sensíveis, por :func:`tipo_sensivel`;
    trechos de saúde que são só idade ou duração (:data:`_SO_IDADE_OU_DURACAO`) são descartados.
    """
    meta = metadados()
    if meta is None:
        return []
    limiares = {r: v for r, v in meta["limiares"].items() if r in TIPOS}
    contextuais = meta.get("limiares_contextuais", {})
    texto = doc.text
    saida = []
    for ini, fim, rotulo, prob in selecionar(candidatos_do_doc(doc), limiares, meta.get("decodificacao", "maximo")):
        tipo, camada = TIPOS[rotulo]
        if tipo is None and (tipo := tipo_sensivel(texto[ini:fim])) is None:
            continue
        if rotulo == "DADO_SAUDE" and _SO_IDADE_OU_DURACAO.fullmatch(texto[ini:fim].strip()):
            continue
        if rotulo == "NOME_PESSOA":
            if (limites := limites_do_nome(texto, ini, fim)) is None:
                continue
            ini, fim = limites
        if prob >= contextuais.get(rotulo, 2.0):
            camada = CONTEXTUAL
        saida.append(Deteccao(ini, fim, tipo, confianca(prob, limiares[rotulo]), f"aprendido:{rotulo.lower()}",
                              camada, contexto_aplicado=True))
    return saida


class ReconhecedorAprendido(EntityRecognizer):
    """Achados do classificador a partir do documento já processado pelo ``SpacyNlpEngine``.

    Não executa o modelo: lê os trechos que o componente ``themis_sensivel`` registrou no documento
    durante o processamento em lote (ver :func:`acoplar`). Sem o componente, não produz achados.
    """

    def __init__(self, idioma: str = "pt"):
        entidades = {t for t, _ in TIPOS.values() if t} | {t for t, _ in CATEGORIAS_SENSIVEIS}
        super().__init__(supported_entities=sorted(entidades), name="BR_Sensivel_Aprendido",
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
