"""Dados de saúde: cobertura do léxico por classe, trecho completo da condição e regra de vínculo.

Os exemplos são fictícios. Cobrem as três frentes da regra de saúde no perfil LAI:

* termos e qualificadores reconhecidos (localização anatômica, tipo, sigla entre parênteses);
* atribuição da condição a uma pessoa ("estou com", "sofri", "laudo de", "Condição clínica:");
* vínculo pela frase vizinha, que não se aplica quando a frase do termo trata de grupo ou estatística.
"""

import pytest

from themis_lgpd import Anonimizador


@pytest.fixture(scope="module")
def anon() -> Anonimizador:
    return Anonimizador("lai", usar_ner=False)


def _saude(r):
    return {e.valor: e.acao for e in r.entidades if e.tipo == "SAUDE"}


@pytest.mark.parametrize("texto,termo", [
    # Aparelho digestivo, respiratório e doenças do trabalho
    ("Eu tenho gastrite crônica há anos.", "gastrite crônica"),
    ("Meu pai está com colelitíase e aguarda a cirurgia.", "colelitíase"),
    ("Minha esposa desenvolveu silicose na fábrica.", "silicose"),
    ("Sofro de rinite alérgica todo inverno.", "rinite alérgica"),
    ("Desenvolvi lesão por esforço repetitivo no trabalho.", "lesão por esforço repetitivo"),
    # Alergias, infecções, nutrição
    ("Meu filho tem alergia à proteína do leite de vaca (APLV).", "alergia à proteína do leite de vaca (APLV)"),
    ("Minha tia pegou uma infecção por bactéria multirresistente.", "infecção por bactéria"),
    ("Minha neta tem fenilcetonúria e precisa de fórmula especial.", "fenilcetonúria"),
    # Visão, sintomas e deficiência
    ("Estou perdendo a visão e preciso do agendamento.", "perdendo a visão"),
    ("Meu quadro piorou com dores fortes e sangramento constante.", "dores fortes"),
    ("Minha filha é uma criança com deficiência e usa cadeira de rodas.", "cadeira de rodas"),
    # Procedimentos, exames, imunização e medicamentos
    ("Aguardo a minha facoemulsificação desde março.", "facoemulsificação"),
    ("Eu tomei a vacina contra febre amarela no posto.", "vacina contra febre"),
    ("Tomo losartana potássica 50mg todos os dias.", "losartana potássica 50mg"),
    ("O médico me receitou riluzol.", "riluzol"),
])
def test_classes_de_condicao_tarjadas_com_vinculo(anon, texto, termo):
    assert termo not in anon.anonimizar(texto).texto


@pytest.mark.parametrize("texto,trecho", [
    ("Minha mãe trata um carcinoma basocelular no rosto.", "carcinoma basocelular"),
    ("Meu irmão tem tuberculose pulmonar.", "tuberculose pulmonar"),
    ("Eu tenho hérnia de disco lombar e artrose no quadril.", "artrose no quadril"),
    ("Tenho hipertensão arterial sistêmica severa.", "hipertensão arterial sistêmica severa"),
    ("Sou portadora de esclerose lateral amiotrófica (ELA).", "(ELA)"),
])
def test_qualificadores_e_sigla_entram_no_trecho(anon, texto, trecho):
    assert trecho not in anon.anonimizar(texto).texto


def test_casamentos_sobrepostos_nao_cortam_a_condicao(anon):
    # "cirurgia de câncer" não pode impedir o reconhecimento de "câncer de próstata".
    saida = anon.anonimizar("Aguardo a cirurgia de câncer de próstata do meu avô.").texto
    assert "próstata" not in saida and "câncer" not in saida


@pytest.mark.parametrize("texto,termo", [
    ("Minha filha está com suspeita de gastroenterite.", "gastroenterite"),
    ("Ele sofreu uma fratura exposta na perna.", "fratura exposta na perna"),
    ("Solicito o prontuário referente à intoxicação por monóxido de carbono.", "intoxicação por monóxido"),
    ("Segue o laudo de autismo infantil emitido pela unidade.", "autismo infantil"),
    ("Condição clínica: paralisia cerebral", "paralisia cerebral"),
])
def test_atribuicao_e_registro_clinico_sao_contextuais(anon, texto, termo):
    r = anon.anonimizar(texto)
    assert termo not in r.texto, r.texto
    assert any(e.camada == "contextual" and e.acao == "tarjar" for e in r.entidades if e.tipo == "SAUDE")


def test_vinculo_pela_frase_vizinha(anon):
    r = anon.anonimizar("Solicito informações sobre a entrega de insulina glargina na unidade. "
                        "Minha filha depende do medicamento e o estoque acabou.")
    assert "insulina glargina" not in r.texto


def test_mesma_condicao_tarjada_em_todas_as_ocorrencias(anon):
    # A terceira frase, estatística e distante do relato, revelaria a condição tarjada na primeira.
    r = anon.anonimizar("Tive uma crise de asma grave no trabalho. Trabalho no setor de arquivo. "
                        "Qual o número de dias de licença previstos para asma grave?")
    assert "asma grave" not in r.texto


@pytest.mark.parametrize("texto,termo", [
    # Frase do termo trata de grupo ou estatística: a vizinha não o vincula a ninguém.
    ("Solicito o número de casos de tuberculose no município em 2024. Eu sou pesquisador da área.", "tuberculose"),
    ("Peço o cronograma da campanha de vacinação contra a gripe. Moro no bairro central.", "gripe"),
    ("Quantos pacientes com diabetes aguardam consulta na rede? Eu gostaria de saber.", "diabetes"),
    # Fórmula de contato na vizinha não cria vínculo.
    ("Solicito informações sobre a oferta de mamografias na rede municipal. Meu e-mail é a@b.com.", "mamografias"),
])
def test_mencao_publica_continua_legivel(anon, texto, termo):
    r = anon.anonimizar(texto)
    assert termo in r.texto, r.texto
    assert _saude(r).get(termo, "alertar") == "alertar"


@pytest.mark.parametrize("texto", [
    "O órgão designou o encarregado pelo tratamento de dados pessoais.",
    "A licitação para o tratamento de esgoto do bairro foi homologada.",
    "Houve deficiência no atendimento da unidade, conforme relatei.",
    "Aguardo com ansiedade a publicação do edital.",
    "Os portadores de deficiência têm direito a vaga reservada no estacionamento.",
])
def test_termos_administrativos_ou_coletivos_nao_sao_tarjados(anon, texto):
    r = anon.anonimizar(texto)
    assert [e for e in r.tarjadas if e.tipo == "SAUDE"] == [], [(e.valor, e.origem) for e in r.tarjadas]
