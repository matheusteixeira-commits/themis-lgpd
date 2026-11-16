"""Camada de detecção, construída sobre o ``AnalyzerEngine`` do Microsoft Presidio.

Componentes do Presidio utilizados:

* ``SpacyNlpEngine`` com o modelo ``pt_core_news_lg``, que fornece tokens, lemas e entidades
  nomeadas. O modelo é carregado localmente, sem download automático (ver :class:`MotorSpacyThemis`).
* ``RecognizerRegistry`` em português com os reconhecedores brasileiros do Themis (documentos com
  dígito verificador, contatos, endereços, dados financeiros, processos, nomes e dados sensíveis),
  adaptados ao contrato ``EntityRecognizer`` por :class:`ReconhecedorThemis`.
* Classificador de trechos treinado (componente ``spancat`` do spaCy) para dados de saúde e
  quase-identificadores, acrescentado ao pipeline quando o artefato está instalado e ativado (ver
  :mod:`themis_lgpd.reconhecedores.aprendido`).
* Reconhecedores predefinidos do Presidio, configurados para os tipos do Themis: telefone
  (biblioteca ``phonenumbers``, região BR), IP, cartão de crédito (Luhn), IBAN e carteiras de
  criptomoeda.
* ``LemmaContextAwareEnhancer``, que eleva a confiança de um achado quando palavras de contexto
  aparecem nos lemas vizinhos.
* Remoção de duplicatas, limiar de confiança e registro da explicação de cada decisão
  (``return_decision_process``).

Os reconhecedores de e-mail e URL do Presidio não são registrados porque dependem da lista pública
de sufixos de domínio, obtida pela internet (``tldextract``); o Themis opera sem acesso à rede e usa
reconhecedores próprios para esses tipos.

Os reconhecedores brasileiros podem ser registrados em qualquer ``AnalyzerEngine``::

    from themis_lgpd.analisador import reconhecedores_brasileiros

    for reconhecedor in reconhecedores_brasileiros():
        engine.registry.add_recognizer(reconhecedor)
"""

from __future__ import annotations

import logging
import threading
from bisect import bisect_right
from collections.abc import Iterable, Sequence
from functools import lru_cache

from presidio_analyzer import (
    AnalysisExplanation,
    AnalyzerEngine,
    EntityRecognizer,
    RecognizerRegistry,
    RecognizerResult,
)
from presidio_analyzer.context_aware_enhancers import LemmaContextAwareEnhancer
from presidio_analyzer.nlp_engine import NerModelConfiguration, NlpArtifacts, SpacyNlpEngine
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    CryptoRecognizer,
    IbanRecognizer,
    IpRecognizer,
    PhoneRecognizer,
)

from .catalogo import tipo as info_tipo
from .reconhecedores import (
    aprendido,
    contatos,
    documentos,
    financeiro,
    localizacao,
    nomes,
    pessoais,
    sensiveis,
    tabelas,
)
from .reconhecedores import base as B
from .reconhecedores.institucional import reclassificar as reclassificar_institucionais

#: Código de idioma usado em todo o registro do Presidio.
IDIOMA = "pt"

# Os registros de depuração do Presidio descrevem o processamento de cada texto. O nível mínimo é
# fixado em WARNING para que uma aplicação hospedeira configurada em DEBUG não passe a registrar
# informações sobre documentos analisados.
logging.getLogger("presidio-analyzer").setLevel(logging.WARNING)

# O pipeline do spaCy não é seguro para uso simultâneo por várias threads; a API e a interface web
# compartilham a mesma instância.
_TRAVA_NLP = threading.Lock()

#: Rótulos do ``pt_core_news_lg`` e as entidades correspondentes no Presidio. ``MISC`` é mantido porque
#: o modelo eventualmente rotula nomes de pessoas dessa forma; o filtro de nomes decide se o aceita.
ROTULOS_MODELO = {"PER": "PERSON", "LOC": "LOCATION", "ORG": "ORGANIZATION", "MISC": "MISC"}

#: Palavras de contexto por grupo de reconhecedores. O ``LemmaContextAwareEnhancer`` compara cada uma,
#: por substring, com os lemas das palavras vizinhas ao achado; por isso algumas são radicais
#: ("telefon", "resid").
CONTEXTO = {
    "documentos": ["cpf", "identidade", "rg", "cnh", "habilitação", "pis", "pasep", "nis", "título", "eleitor",
                   "sus", "matrícula", "siape", "documento", "inscrição", "nascimento", "nascer"],
    "contatos": ["telefon", "celular", "fone", "whats", "contato", "ramal", "ligar", "recado", "instagram",
                 "insta", "twitter", "tiktok", "perfil", "arroba", "telegram"],
    "localizacao": ["resid", "morar", "morador", "endereço", "domicíli", "imóvel", "localiz", "cep"],
    "financeiro": ["conta", "agência", "banco", "pix", "cartão", "depósito", "transferência", "crédito"],
    "veiculos": ["placa", "veículo", "carro", "moto", "renavam", "automóvel"],
    "processos": ["processo", "protocolo", "autos", "sei", "requerimento", "ocorrência", "boletim"],
}


def _tipos(padroes: Iterable[B.Padrao]) -> list[str]:
    return sorted({p.tipo for p in padroes})


# E-mails e telefones ficam em reconhecedores separados porque têm palavras de contexto diferentes.
_EMAILS = [p for p in contatos.PADROES if p.tipo == "EMAIL"]
_TELEFONES = [p for p in contatos.PADROES if p.tipo != "EMAIL"]


class RealceDeContexto(LemmaContextAwareEnhancer):
    """``LemmaContextAwareEnhancer`` do Presidio com localização do token do achado por busca binária.

    O original percorre os tokens do documento desde o início para cada achado, o que torna o
    reforço de confiança quadrático no tamanho do texto: num documento de 100 mil caracteres, mais
    da metade do tempo de análise. Aqui, o fim de cada token é calculado uma vez por documento e o
    token é encontrado por busca binária, com o mesmo resultado: o primeiro token que termina depois
    do início do achado.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ultimo: tuple = (None, ())

    def _find_index_of_match_token(self, word: str, start: int, tokens, tokens_indices: list[int]) -> int:
        doc, fins = self._ultimo
        if doc is not tokens:
            fins = [i + len(t.text) for i, t in zip(tokens_indices, tokens)]
            self._ultimo = (tokens, fins)  # atribuição única: segura entre threads
        i = bisect_right(fins, start)
        if i >= len(fins):
            raise ValueError(f"Did not find word '{word}' in the list of tokens although it is expected to be found")
        return i


class ReconhecedorThemis(EntityRecognizer):
    """Adapta um reconhecedor do Themis ao contrato ``EntityRecognizer`` do Presidio.

    O reconhecedor de origem expõe ``detectar(texto) -> list[Deteccao]``. Os metadados de cada
    resultado preservam a origem do achado, a camada de detecção (usada pela política de perfis) e o
    resultado da validação do dígito verificador.

    Args:
        fonte: Objeto com o método ``detectar``.
        entidades: Tipos de dado que este reconhecedor pode produzir.
        nome: Nome exibido na explicação da decisão.
        contexto: Palavras de contexto para o ``LemmaContextAwareEnhancer``.
    """

    def __init__(self, fonte, entidades: Sequence[str], nome: str, contexto: Sequence[str] = ()):
        self.fonte = fonte
        super().__init__(supported_entities=list(entidades), name=nome, supported_language=IDIOMA,
                         context=list(contexto))

    def load(self) -> None:
        """Nada a carregar: as expressões regulares são compiladas na importação dos módulos."""

    def analyze(self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None):
        """Executa o reconhecedor de origem e converte os achados em ``RecognizerResult``.

        O filtro é feito pelas entidades suportadas pelo próprio reconhecedor, e não pelo parâmetro
        ``entities``: em uma análise completa, o Presidio informa apenas as entidades do registro, o
        que descartaria os achados de reconhecedores ad hoc (por exemplo, a lista de bloqueio).
        """
        saida = []
        for d in self.fonte.detectar(text):
            if d.tipo not in self.supported_entities:
                continue
            explicacao = AnalysisExplanation(recognizer=self.name, original_score=d.score, pattern_name=d.origem,
                                             validation_result=d.validado)
            saida.append(RecognizerResult(d.tipo, d.inicio, d.fim, d.score, analysis_explanation=explicacao,
                                          recognition_metadata={
                                              RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                                              RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id,
                                              # Impede um segundo reforço quando o próprio padrão já
                                              # exigiu a palavra de contexto.
                                              RecognizerResult.IS_SCORE_ENHANCED_BY_CONTEXT_KEY: d.contexto_aplicado,
                                              "origem": d.origem, "camada": d.camada, "validado": d.validado,
                                          }))
        return saida


class ReconhecedorNomesModelo(EntityRecognizer):
    """Nomes de pessoas a partir das entidades já extraídas pelo ``SpacyNlpEngine``.

    Substitui o ``SpacyRecognizer`` padrão do Presidio. Não executa o modelo novamente: lê as
    entidades dos artefatos de NLP e aplica os filtros de :func:`themis_lgpd.reconhecedores.nomes.filtrar_entidade_nlp`
    (pronomes de tratamento, texto em caixa alta, nomes de instituições, normas e lugares). Entidades
    ``MISC`` e ``LOC`` são aceitas quando começam por um prenome conhecido.
    """

    def __init__(self):
        super().__init__(supported_entities=["NOME"], name="BR_Nomes_Modelo", supported_language=IDIOMA)

    def load(self) -> None:
        """Nada a carregar: o modelo pertence ao ``SpacyNlpEngine``."""

    def analyze(self, text: str, entities: list[str], nlp_artifacts: NlpArtifacts | None = None):
        """Converte as entidades do modelo aprovadas pelo filtro em ``RecognizerResult`` do tipo ``NOME``."""
        if nlp_artifacts is None or not nlp_artifacts.entities:
            return []
        doc = nlp_artifacts.tokens
        confiancas = nlp_artifacts.scores or [0.85] * len(nlp_artifacts.entities)
        saida = []
        for ent, score in zip(nlp_artifacts.entities, confiancas):
            d = nomes.filtrar_entidade_nlp(doc, ent, rotulo_pessoa="PERSON", score=score, texto=text)
            if d is None:
                continue
            saida.append(RecognizerResult("NOME", d.inicio, d.fim, d.score,
                                          analysis_explanation=AnalysisExplanation(
                                              recognizer=self.name, original_score=d.score,
                                              textual_explanation=f"Entidade {ent.label_} do modelo spaCy, filtrada"),
                                          recognition_metadata={
                                              RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                                              RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id,
                                              "origem": "nomes:modelo", "camada": B.NER}))
        return saida


class MotorSpacyThemis(SpacyNlpEngine):
    """``SpacyNlpEngine`` que carrega o modelo localmente.

    Difere do motor padrão em dois pontos: nunca tenta baixar o modelo (a ausência dele produz um
    erro com a instrução de instalação) e exclui o analisador sintático, desnecessário para a
    detecção e responsável por boa parte do tempo de processamento. Com ``modelo=None``, usa um
    pipeline vazio com lematização simples, o que mantém o reforço por contexto em funcionamento.
    """

    def __init__(self, modelo: str | None):
        super().__init__(models=[{"lang_code": IDIOMA, "model_name": modelo or "blank"}],
                         ner_model_configuration=NerModelConfiguration(
                             model_to_presidio_entity_mapping=dict(ROTULOS_MODELO), labels_to_ignore=[]))
        self.modelo = modelo

    def load(self) -> None:
        """Carrega o pipeline (ver :func:`themis_lgpd.reconhecedores.nomes.carregar_spacy`).

        Com modelo de linguagem, acrescenta o classificador de dados sensíveis, se ativado (ver
        :func:`themis_lgpd.reconhecedores.aprendido.acoplar`).
        """
        nlp = nomes.carregar_spacy(self.modelo)
        if self.modelo is not None:
            aprendido.acoplar(nlp)
        self.nlp = {IDIOMA: nlp}


def reconhecedores_brasileiros(com_modelo: bool = True) -> list[EntityRecognizer]:
    """Reconhecedores usados pelo Themis, prontos para registro em um ``AnalyzerEngine``.

    Args:
        com_modelo: Inclui os reconhecedores baseados no modelo de linguagem (nomes e, quando
            ativado, o classificador de dados sensíveis); exige um ``SpacyNlpEngine`` com
            reconhecimento de entidades.

    Returns:
        Os reconhecedores brasileiros do Themis e os reconhecedores predefinidos do Presidio
        configurados para os tipos do Themis.
    """
    recs: list[EntityRecognizer] = [
        ReconhecedorThemis(B.ReconhecedorPadroes("documentos", documentos.PADROES), _tipos(documentos.PADROES),
                           "BR_Documentos", CONTEXTO["documentos"]),
        ReconhecedorThemis(B.ReconhecedorPadroes("emails", _EMAILS), ["EMAIL"], "BR_Email", ["mail", "correio"]),
        ReconhecedorThemis(B.ReconhecedorPadroes("telefones_perfis", _TELEFONES), _tipos(_TELEFONES),
                           "BR_Telefones_Perfis", CONTEXTO["contatos"]),
        ReconhecedorThemis(contatos.ReconhecedorURL(), ["PERFIL_REDE_SOCIAL", "URL"], "BR_URL"),
        ReconhecedorThemis(localizacao.ReconhecedorEndereco(), ["CEP", "ENDERECO"], "BR_Enderecos",
                           CONTEXTO["localizacao"]),
        ReconhecedorThemis(localizacao.ReconhecedorLocalidade(), ["LOCALIDADE", "ENDERECO"], "BR_Localidades"),
        ReconhecedorThemis(B.ReconhecedorPadroes("financeiro", financeiro.FINANCEIRO), _tipos(financeiro.FINANCEIRO),
                           "BR_Financeiro", CONTEXTO["financeiro"]),
        ReconhecedorThemis(B.ReconhecedorPadroes("veiculos", financeiro.VEICULOS), _tipos(financeiro.VEICULOS),
                           "BR_Veiculos", CONTEXTO["veiculos"]),
        ReconhecedorThemis(B.ReconhecedorPadroes("processos", financeiro.PROCESSOS), _tipos(financeiro.PROCESSOS),
                           "BR_Processos", CONTEXTO["processos"]),
        ReconhecedorThemis(pessoais.ReconhecedorIdades(), ["IDADE", "DATA_NASCIMENTO"], "BR_Idades"),
        ReconhecedorThemis(pessoais.ReconhecedorValores(), ["VALOR_PESSOAL"], "BR_Valores"),
        ReconhecedorThemis(nomes.ReconhecedorNomesLista(), ["NOME"], "BR_Nomes_Lista"),
        ReconhecedorThemis(nomes.ReconhecedorNomesContexto(), ["NOME"], "BR_Nomes_Gatilho"),
        ReconhecedorThemis(tabelas.ReconhecedorTabelas(), tabelas.TIPOS, "BR_Tabelas"),
        PhoneRecognizer(supported_language=IDIOMA, supported_entity="TELEFONE", supported_regions=("BR",),
                        context=CONTEXTO["contatos"], name="Presidio_Telefone_BR"),
        IpRecognizer(supported_language=IDIOMA, supported_entity="IP", context=["ip", "acesso", "endereço"],
                     name="Presidio_IP"),
        CreditCardRecognizer(supported_language=IDIOMA, supported_entity="CARTAO",
                             context=["cartão", "crédito", "débito", "visa", "master", "elo", "amex"],
                             name="Presidio_Cartao"),
        IbanRecognizer(supported_language=IDIOMA, supported_entity="CONTA_BANCARIA",
                       context=["iban", "conta", "banco", "transferência"], name="Presidio_IBAN"),
        CryptoRecognizer(supported_language=IDIOMA, supported_entity="CARTEIRA_CRIPTO",
                         context=["bitcoin", "btc", "carteira", "cripto"], name="Presidio_Cripto"),
    ]
    for grupo in sensiveis.reconhecedores():
        recs.append(ReconhecedorThemis(grupo, _tipos(grupo.padroes), f"BR_{grupo.nome.title()}"))
    if com_modelo:
        recs.append(ReconhecedorNomesModelo())
        recs.append(aprendido.ReconhecedorAprendido(IDIOMA))
    return recs


@lru_cache(maxsize=4)
def obter_analisador(modelo: str | None) -> AnalyzerEngine:
    """``AnalyzerEngine`` configurado para documentos brasileiros.

    A instância é criada uma vez por modelo e compartilhada; o carregamento do modelo de linguagem
    leva alguns segundos.

    Args:
        modelo: Nome do pacote spaCy (ex.: ``pt_core_news_lg``) ou ``None`` para operar sem modelo.
    """
    nlp = MotorSpacyThemis(modelo)
    nlp.load()
    registro = RecognizerRegistry(supported_languages=[IDIOMA])
    for r in reconhecedores_brasileiros(com_modelo=modelo is not None):
        registro.add_recognizer(r)
    return AnalyzerEngine(
        registry=registro, nlp_engine=nlp, supported_languages=[IDIOMA],
        # Em português, a palavra de contexto costuma vir antes do dado ("CPF nº ..."); por isso a
        # janela anterior é maior que a posterior.
        context_aware_enhancer=RealceDeContexto(context_prefix_count=6, context_suffix_count=2),
    )


def _deteccao(r: RecognizerResult, desloc: int) -> B.Deteccao:
    """Converte um ``RecognizerResult`` em :class:`~themis_lgpd.reconhecedores.base.Deteccao`.

    Args:
        r: Resultado do Presidio.
        desloc: Posição do trecho analisado dentro do texto completo.
    """
    meta = r.recognition_metadata or {}
    camada = meta.get("camada")
    if camada is None:
        # Reconhecedores sem metadados do Themis (predefinidos do Presidio, GLiNER): um dado sensível
        # isolado segue a regra de vínculo do perfil; os demais são tratados como estruturais.
        sensivel = info_tipo(r.entity_type).categoria in {"SENSIVEL", "INTIMIDADE", "MENOR"}
        camada = B.SEMANTICA if sensivel else B.ESTRUTURAL
    origem = meta.get("origem") or f"presidio:{meta.get(RecognizerResult.RECOGNIZER_NAME_KEY, '?')}"
    exp = r.analysis_explanation
    if exp is not None and exp.supportive_context_word:
        origem += f" (contexto: {exp.supportive_context_word})"
    return B.Deteccao(r.start + desloc, r.end + desloc, r.entity_type, round(float(r.score), 3), origem, camada,
                      meta.get("validado"))


def analisar_textos(textos: Sequence[str], modelo: str | None, extras: Sequence[EntityRecognizer] = (),
                    score_minimo: float = 0.0) -> list[list[B.Deteccao]]:
    """Analisa um lote de textos.

    Textos longos são divididos em partes com sobreposição (ver
    :func:`themis_lgpd.reconhecedores.nomes.partes`). O modelo de linguagem processa todas as partes
    de uma vez (``process_batch``), o que é significativamente mais rápido que analisar texto a texto.

    Args:
        textos: Textos já normalizados.
        modelo: Modelo spaCy ou ``None``.
        extras: Reconhecedores adicionais desta análise (lista de bloqueio, reconhecedores do usuário).
        score_minimo: Confiança mínima para que um achado seja devolvido.

    Returns:
        As detecções de cada texto, com posições relativas ao texto completo.
    """
    engine = obter_analisador(modelo)
    blocos: list[tuple[int, int, str]] = [(i, d, parte) for i, t in enumerate(textos) for d, parte in nomes.partes(t)]
    with _TRAVA_NLP:
        artefatos = [a for _, a in engine.nlp_engine.process_batch([b[2] for b in blocos], IDIOMA, batch_size=32)]
    saida: list[list[B.Deteccao]] = [[] for _ in textos]
    for (i, desloc, parte), art in zip(blocos, artefatos):
        if not parte.strip():
            continue
        resultados = engine.analyze(text=parte, language=IDIOMA, nlp_artifacts=art, score_threshold=score_minimo,
                                    ad_hoc_recognizers=list(extras) or None, return_decision_process=True)
        saida[i].extend(_deteccao(r, desloc) for r in resultados)
    # Contatos, endereços e placas do próprio órgão, reconhecidos pelo contexto do texto inteiro.
    for texto, dets in zip(textos, saida):
        reclassificar_institucionais(texto, dets)
        # Nome de pessoa em célula de coluna de unidade ou lugar ("Lotação", "Destino"): nome da unidade.
        tabelas.preservar_unidades(texto, dets)
    return saida
