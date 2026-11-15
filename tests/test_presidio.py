"""O Themis é construído sobre o Microsoft Presidio: estes testes garantem que continue sendo."""

import pytest
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.context_aware_enhancers import LemmaContextAwareEnhancer
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    CryptoRecognizer,
    IbanRecognizer,
    IpRecognizer,
    PhoneRecognizer,
)

from themis_lgpd.analisador import MotorSpacyThemis, obter_analisador, reconhecedores_brasileiros
from themis_lgpd.operadores import Substituidor, aplicar_com_presidio


def test_deteccao_usa_o_analyzer_engine_do_presidio(anon):
    engine = obter_analisador("pt_core_news_lg")
    assert isinstance(engine, AnalyzerEngine)
    assert isinstance(engine.context_aware_enhancer, LemmaContextAwareEnhancer)
    nomes = {r.name for r in engine.registry.get_recognizers(language="pt", all_fields=True)}
    assert {"BR_Documentos", "BR_Nomes_Modelo", "BR_Enderecos", "BR_Saude"} <= nomes
    tipos_presidio = {type(r) for r in engine.registry.recognizers}
    assert {PhoneRecognizer, IpRecognizer, CreditCardRecognizer, IbanRecognizer, CryptoRecognizer} <= tipos_presidio


def test_reconhecedores_prontos_do_presidio_entram_no_resultado(anon):
    r = anon.anonimizar("IBAN BR1500000000000010932840814P2, IP 189.40.12.7 e bitcoin 1BoatSLRHtKNngkdXEeobR76b53LETtpyT")
    origens = {e.tipo: e.origem for e in r.tarjadas}
    assert origens["CONTA_BANCARIA"].startswith("presidio:Presidio_IBAN")
    assert origens["IP"].startswith("presidio:Presidio_IP")
    assert origens["CARTEIRA_CRIPTO"].startswith("presidio:Presidio_Cripto")
    assert "BR15" not in r.texto and "189.40" not in r.texto


def test_reforco_de_contexto_do_presidio(anon):
    # "telefone" antes do número: o LemmaContextAwareEnhancer registra a palavra de apoio na explicação
    e = next(e for e in anon.analisar("Meu telefone é (61) 99999-8888.") if e.tipo == "TELEFONE")
    assert "contexto: telefon" in e.origem and e.score == 1.0


def test_reconhecedores_brasileiros_funcionam_em_outro_analyzer_engine():
    nlp = MotorSpacyThemis(None)  # só tokenização: suficiente para os reconhecedores de padrão
    nlp.load()
    registro = RecognizerRegistry(supported_languages=["pt"])
    for r in reconhecedores_brasileiros(com_modelo=False):
        registro.add_recognizer(r)
    engine = AnalyzerEngine(registry=registro, nlp_engine=nlp, supported_languages=["pt"])
    tipos = {r.entity_type for r in engine.analyze("CPF 529.982.247-25 e CNPJ 12.ABC.345/01DE-35", language="pt")}
    assert {"CPF", "CNPJ"} <= tipos


def test_substituicao_feita_pelo_presidio_anonymizer():
    class E:  # entidade mínima
        def __init__(self, tipo, valor):
            self.tipo, self.valor = tipo, valor

    texto = "Ana Lima, CPF 529.982.247-25, e Ana Lima de novo."
    segs = [(0, 8, E("NOME", "Ana Lima")), (14, 28, E("CPF", "529.982.247-25")), (32, 40, E("NOME", "Ana Lima"))]
    saida, subs = aplicar_com_presidio(texto, segs, Substituidor("pseudonimo"))
    assert saida == "Pessoa 1, CPF [CPF 1], e Pessoa 1 de novo."
    assert [saida[s["inicio_saida"]:s["fim_saida"]] for s in subs] == ["Pessoa 1", "[CPF 1]", "Pessoa 1"]


def test_lista_de_bloqueio_entra_como_reconhecedor_ad_hoc():
    from themis_lgpd import Anonimizador

    r = Anonimizador(bloquear=["Operação Sigilo"]).anonimizar("A operação sigilo começou.")
    assert r.texto == "A [TARJADO] começou."


@pytest.mark.parametrize("modo,esperado", [("etiqueta", "[CPF]"), ("tarja", "████████"), ("mascara", "***.***.***-**")])
def test_operadores_do_presidio_por_modo(modo, esperado):
    class E:
        tipo, valor = "CPF", "529.982.247-25"

    saida, _ = aplicar_com_presidio("529.982.247-25", [(0, 14, E())], Substituidor(modo))
    assert saida == esperado
