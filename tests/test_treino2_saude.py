"""Dados de saúde e dados sensíveis em documentos oficiais: vínculo no nível do documento.

Os exemplos são fictícios. Cobrem:

* o documento centrado em pessoa identificada (laudo, prontuário, relatório social), em que o dado
  sensível se refere a essa pessoa, e o registro clínico, em que o trecho tarjado vai até a fronteira
  da frase sem atravessar nome de instituição, programa ou norma;
* as classes do registro clínico: exame com resultado, sinal vital, escala, posologia, lista de
  códigos da CID, tabela de exames e campo de formulário;
* as armadilhas de tarja indevida: documento agregado ou normativo, título, rótulo de campo, negação,
  linha de assinatura, nome próprio com termo de cor ou etnia, órgão de proteção citado pelo nome e
  faixa de idade.
"""

import pytest

from themis_lgpd import Anonimizador
from themis_lgpd.reconhecedores import sensiveis as S


@pytest.fixture(scope="module")
def anon() -> Anonimizador:
    return Anonimizador("lai", usar_ner=False)


LAUDO = """PREFEITURA MUNICIPAL DE VALE DAS PALMEIRAS
SECRETARIA MUNICIPAL DE SAÚDE
Policlínica Central de Vale das Palmeiras

LAUDO MÉDICO PARA AVALIAÇÃO DE DEFICIÊNCIA

Paciente: Fulana de Teste Exemplar
Data de nascimento: 01/02/1970
Prontuário: 000-1234

HISTÓRICO
Refere cansaço aos esforços e edema nos tornozelos há seis meses, com piora progressiva. Nega alergias.
Foi encaminhada ao Hospital Universitário Modelo para avaliação cardiológica.

EXAME FÍSICO
PA 150 x 95 mmHg; FC 102 bpm; peso 88 kg; IMC 33,1 kg/m².
Marcha: lenta, com base alargada.

EXAMES
EXAME | RESULTADO | REFERÊNCIA
Creatinina | 2,4 mg/dL | 0,6 a 1,1 mg/dL
Hemoglobina glicada | 9,8% | até 5,7%

Diagnósticos: N18.4; E11.2; I50.0.

Prescrição: furosemida 40 mg pela manhã; insulina NPH 18 UI antes do café.
Classificada com grau de dependência II, conforme a Lei nº 99.999/2099.

Vale das Palmeiras, 3 de março de 2099.

Dra. Exemplo Fictício
Médica nefrologista – CRM-XX 0.000
"""


def _tarjado(resultado, trecho: str) -> bool:
    """Todo caractere alfanumérico do trecho está coberto por tarja."""
    ini = resultado.original.index(trecho)
    cobertos = set()
    for e in resultado.tarjadas:
        cobertos.update(range(e.inicio, e.fim))
    return all(k in cobertos for k in range(ini, ini + len(trecho)) if resultado.original[k].isalnum())


def _legivel(resultado, trecho: str) -> bool:
    ini = resultado.original.index(trecho)
    return not any(e.inicio < ini + len(trecho) and ini < e.fim for e in resultado.tarjadas)


def test_contexto_documental_reconhece_laudo_e_documento_agregado():
    ctx = S.contexto_documental(LAUDO)
    assert ctx.centrado and ctx.clinico
    boletim = ("BOLETIM EPIDEMIOLÓGICO Nº 7/2099\n\nForam notificados 1.204 casos de dengue no estado, com "
               "incidência de 98,1 por 100 mil habitantes.")
    assert not S.contexto_documental(boletim).centrado


@pytest.mark.parametrize("trecho", [
    "cansaço aos esforços e edema nos tornozelos há seis meses, com piora progressiva",
    "150 x 95 mmHg", "102 bpm", "88 kg", "33,1 kg/m²",
    "lenta, com base alargada",
    "2,4 mg/dL", "9,8%",
    "N18.4; E11.2; I50.0",
    "furosemida 40 mg pela manhã", "insulina NPH 18 UI antes do café",
    "grau de dependência II",
])
def test_registro_clinico_tarjado(anon, trecho):
    assert _tarjado(anon.anonimizar(LAUDO), trecho)


@pytest.mark.parametrize("trecho", [
    "Policlínica Central de Vale das Palmeiras", "Hospital Universitário Modelo", "Lei nº 99.999/2099",
    "LAUDO MÉDICO PARA AVALIAÇÃO DE DEFICIÊNCIA", "3 de março de 2099", "Médica nefrologista",
    "Nega alergias", "EXAME | RESULTADO | REFERÊNCIA", "Diagnósticos:",
])
def test_registro_clinico_preserva_instituicao_norma_titulo_e_assinatura(anon, trecho):
    assert _legivel(anon.anonimizar(LAUDO), trecho)


def test_documento_agregado_mantem_saude_legivel(anon):
    texto = ("NOTA TÉCNICA Nº 3/2099\n\nAssunto: vacinação contra a influenza.\n\nAs crianças de 6 meses a menores de "
             "6 anos devem receber duas doses. Os casos de síndrome respiratória aguda grave aumentaram 20% no "
             "período, e 5% das vagas são reservadas a pessoas com deficiência.")
    r = anon.anonimizar(texto)
    assert not [e for e in r.tarjadas if e.tipo in ("SAUDE", "DADO_DE_MENOR")]


def test_relatorio_social_vincula_saude_e_atributos_da_condicao(anon):
    texto = ("RELATÓRIO SOCIAL Nº 12/2099\n\n1. IDENTIFICAÇÃO\nUsuário: Beltrano de Teste\nIdade: 51 anos\n\n"
             "3. SAÚDE\nRecebeu diagnóstico de tuberculose pulmonar, em tratamento desde fevereiro de 2099. "
             "A filha é cadeirante em razão de paralisia cerebral.")
    r = anon.anonimizar(texto)
    assert _tarjado(r, "tuberculose pulmonar, em tratamento desde fevereiro de 2099")
    assert _tarjado(r, "cadeirante em razão de paralisia cerebral")


def test_licenca_que_enuncia_motivo_de_saude_em_documento_de_servidor(anon):
    texto = ("DESPACHO Nº 8/2099\n\nServidor: Sicrano de Exemplo\nMatrícula: 0000000\n\nDefiro ao servidor licença "
             "para tratamento de saúde por 30 dias.")
    assert "licença para tratamento de saúde" not in anon.anonimizar(texto).texto


@pytest.mark.parametrize("texto,trecho", [
    ("Ficha de cadastro\nNome: Fulana de Teste\nCPF: 000\nRaça/cor: parda\nEscolaridade: médio", "parda"),
    ("Relatório de acompanhamento\nUsuária: Fulana de Teste\nIdade: 40 anos\nDeclarou-se membro da Igreja Exemplo "
     "do Bairro Novo e frequenta os cultos semanais.", "membro da Igreja Exemplo do Bairro Novo"),
    ("Requerimento\nRequerente: Fulana de Teste\nMatrícula: 1\nSolicita a exclusão da mensalidade sindical, "
     "por ter se desfiliado do Sindicato dos Servidores de Exemplo (SINDEX).",
     "desfiliado do Sindicato dos Servidores de Exemplo (SINDEX)"),
    ("Decisão\nRequerente: Fulana de Teste\nIdade: 30 anos\nA requerente mantém relacionamento homoafetivo há dois "
     "anos.", "relacionamento homoafetivo"),
])
def test_dado_sensivel_em_documento_centrado(anon, texto, trecho):
    assert _tarjado(anon.anonimizar(texto), trecho)


@pytest.mark.parametrize("texto,trecho", [
    # Termo de cor ou etnia dentro de nome próprio (lugar, território, sistema)
    ("Termo de acolhimento\nAdolescente: F.T.E.\nIdade: 15 anos\nFoi abordado no Terminal Rodoviário de Pedra "
     "Preta pela equipe.", "Pedra Preta"),
    ("Relatório\nCriança: F.T.E.\nIdade: 6 anos\nResidência: aldeia Exemplo, Terra Indígena Rio Claro.",
     "Terra Indígena Rio Claro"),
    # Órgão de proteção e vara citados pelo nome
    ("Ofício\nInteressado: Fulano de Teste\nIdade: 9 anos\nEncaminhe-se ao Conselho Tutelar de Exemplo.",
     "Conselho Tutelar de Exemplo"),
    ("PODER JUDICIÁRIO\nVARA DE VIOLÊNCIA DOMÉSTICA E FAMILIAR CONTRA A MULHER\nProcesso nº 1", "VIOLÊNCIA DOMÉSTICA"),
    # Rótulo de campo e campo respondido com "não"
    ("Ficha\nNome: Fulano de Teste\nData de nascimento: 01/01/2000\nOrientação sexual: não se aplica",
     "Orientação sexual"),
    ("Ficha\nNome: Fulano de Teste\nData de nascimento: 01/01/2000\nPossui alguma deficiência? não", "deficiência"),
])
def test_armadilhas_de_tarja_indevida(anon, texto, trecho):
    assert _legivel(anon.anonimizar(texto), trecho)


def test_negacao_vale_no_registro_e_nao_no_pedido(anon):
    pedido = "Estou desesperada: o plano de saúde negou o tratamento quimioterápico que o meu médico indicou."
    assert "quimioterápico" not in anon.anonimizar(pedido).texto


@pytest.mark.parametrize("texto,esperado", [
    ("Meu filho de 8 anos precisa de transporte escolar.", True),
    ("A vacina é indicada para crianças de 6 meses a menores de 9 anos.", False),
    ("O serviço atende menores de 15 anos.", False),
])
def test_idade_de_menor_exata_e_faixa(anon, texto, esperado):
    r = anon.anonimizar(texto)
    assert bool([e for e in r.tarjadas if e.tipo == "DADO_DE_MENOR"]) is esperado


@pytest.mark.parametrize("texto,tarjar", [
    ("Fui vítima de violência doméstica e preciso de abrigo.", True),
    ("Quantas famílias em situação de vulnerabilidade foram atendidas em 2099?", False),
    ("O canal recebe denúncias de assédio moral contra servidores?", False),
])
def test_violencia_com_e_sem_enquadramento(anon, texto, tarjar):
    r = anon.anonimizar(texto)
    assert bool([e for e in r.tarjadas if e.tipo == "VIOLENCIA"]) is tarjar


def test_tabela_com_coluna_de_pessoa(anon):
    texto = ("RESULTADO DA PERÍCIA DE CANDIDATOS COM DEFICIÊNCIA\n\nINSCRIÇÃO | NOME | CARGO | CONDIÇÃO | PARECER\n"
             "1001 | FULANO DE TESTE | Agente | deficiência auditiva bilateral, com perda de grau moderado | APTO\n"
             "1002 | BELTRANA EXEMPLO | Agente | visão monocular | APTO\n")
    r = anon.anonimizar(texto)
    assert _tarjado(r, "deficiência auditiva bilateral, com perda de grau moderado")
    assert _tarjado(r, "visão monocular")


def test_dor_no_singular_com_qualificador(anon):
    texto = "Meu pai apresentava dor torácica intensa quando chegou ao pronto-socorro."
    assert "dor torácica intensa" not in anon.anonimizar(texto).texto
