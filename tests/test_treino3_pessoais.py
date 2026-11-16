"""Idade, data de nascimento e valores de pessoa natural em formas menos usuais.

Os exemplos são fictícios. Complementam ``test_treino2_pessoais.py`` com as formas cobertas por
:mod:`themis_lgpd.reconhecedores.pessoais` e pelo padrão de data de nascimento de
:mod:`themis_lgpd.reconhecedores.documentos`:

* idade separada do nome por nacionalidade, ocupação, parentesco ou documento, idade por extenso, em
  aposto a prenome isolado e entre parênteses depois do nome de criança; e as armadilhas — idade de
  bem, de lugar ou de programa, prazos —, que ficam legíveis;
* data de nascimento com o mês em algarismos romanos, com espaços no lugar das barras, com o ano
  primeiro, toda por extenso, em espanhol, italiano e francês, e o ano declarado; "nasceu" com sujeito
  que é iniciativa, projeto ou evento não é data de nascimento;
* valores de pessoa natural por extenso, em fração do salário mínimo, em moeda estrangeira, em dinheiro
  levado, após gasto, credor pessoa jurídica ou pecúlio, em seção de renda de ficha e em texto com
  quebras de linha; e os valores públicos — média, valor pago a um grupo, limite, rendimento de
  aplicação, receita de convênio, prejuízo de fundo público, multa em documento só de pessoas jurídicas.
"""

import pytest

from themis_lgpd import Anonimizador
from themis_lgpd.reconhecedores.documentos import PADROES
from themis_lgpd.reconhecedores.pessoais import ReconhecedorIdades, ReconhecedorValores


@pytest.fixture(scope="module")
def anon() -> Anonimizador:
    return Anonimizador("lai", usar_ner=False)


def _trechos(reconhecedor, texto: str, tipo: str) -> list[str]:
    return [texto[d.inicio:d.fim] for d in reconhecedor.detectar(texto) if d.tipo == tipo]


def _datas_de_nascimento(texto: str) -> list[str]:
    return [texto[d.inicio:d.fim] for p in PADROES if getattr(p, "tipo", "") == "DATA_NASCIMENTO"
            for d in p.detectar(texto)]


# --------------------------------------------------------------------------- idade
@pytest.mark.parametrize("texto,idade", [
    # Nacionalidade, ocupação, estado civil, parentesco ou documento entre o nome e a idade.
    ("Declarante: Odila Bastião, uruguaia, cozinheira, 52 anos, CPF 111.444.777-35.", "52 anos"),
    ("NGUYEN Thi Lan, vietnamita, 33 anos, passaporte C1234567.", "33 anos"),
    ("o servidor Anselmo Alcione, CPF 111.444.777-35, de 47 anos.", "47 anos"),
    ("– K.L., neta do declarante, 3 anos e meio;", "3 anos e meio"),
    ("Cônjuge: MARTA HELENA BOSCO, aposentada, com 61 anos completos, residente na zona rural.", "61 anos"),
    ("Requerente: Ilse Kühn Wessel, de 44 anos, agricultora.", "44 anos"),
    ("Mulher trans, 29 anos, acolhida no abrigo municipal.", "29 anos"),
    # Prenome isolado e idade por extenso.
    ("O filho mais velho, Belmiro, de 15 anos, estuda à noite.", "15 anos"),
    ("Os netos Ícaro, de sete anos, e Leda, de três anos, dormem na sala.", "sete anos"),
    ("Os netos Ícaro, de sete anos, e Leda, de três anos, dormem na sala.", "três anos"),
    ("Iolanda, com quarenta anos de idade, compareceu ao atendimento.", "quarenta anos"),
    ("Ele tem dezessete anos e mora com a tia.", "dezessete anos"),
    ("Idade informada: quarenta e um anos.", "quarenta e um anos"),
    ("Idade referida: 58 anos", "58 anos"),
    ("Esperei na recepção até o meio-dia, com 68 anos, sem nenhuma cadeira livre.", "68 anos"),
    # Ao lado de data de nascimento atípica e entre parênteses depois do nome.
    ("Data de nascimento: 2011-07-21 (14 anos)", "14 anos"),
    ("Data de nascimento: 03/XI/2015 (10 anos)", "10 anos"),
    ("a criança Juvenal Rocha Bento (8), aluno do 3º ano", "8"),
])
def test_idade_em_formas_menos_usuais(texto, idade):
    assert idade in _trechos(ReconhecedorIdades(), texto, "IDADE")


@pytest.mark.parametrize("texto", [
    "A ponte, que tem 80 anos, será recuperada com recursos do convênio.",
    "O Ginásio Municipal Abigail Wessel, que tem 45 anos, foi reformado.",
    "A vila completa 120 anos de fundação neste ano.",
    "O programa completa dez anos em março.",
    "O servidor tem dois anos para concluir o curso de formação.",
    "Atendemos crianças de zero a seis anos de idade.",
    "A unidade, de 30 anos, é referência regional.",
    "O Conselho, com 35 anos de atuação, reúne as entidades do setor.",
    "A obra, com dois anos de atraso, será retomada.",
])
def test_idade_de_bem_programa_ou_prazo_fica_legivel(texto):
    assert _trechos(ReconhecedorIdades(), texto, "IDADE") == []


# --------------------------------------------------------------------------- data de nascimento
@pytest.mark.parametrize("texto,data", [
    ("NASC 21 09 2014 RESPONSAVEL LEGAL", "21 09 2014"),
    ("NASCIDO EM 08 02 1969 PEDREIRO", "08 02 1969"),
    ("nascida aos vinte e oito dias do mês de novembro de mil novecentos e sessenta e nove, residente",
     "vinte e oito dias do mês de novembro de mil novecentos e sessenta e nove"),
    ("nascido no dia primeiro de outubro de dois mil e seis, filho de", "primeiro de outubro de dois mil e seis"),
    ("Data de nascimento: 03/XI/2015", "03/XI/2015"),
    ("Data de nascimento: 2011.07.21", "2011.07.21"),
    ("nacida el 9 de octubre de 1999 en Arequipa", "9 de octubre de 1999"),
    ("nata a Napoli il 03/02/1961", "03/02/1961"),
    ("née le 4 février 1988 à Lyon", "4 février 1988"),
    ("Ano de nascimento declarado: 1958", "1958"),
    ("Solicito a vaga do projeto Crescer para minha neta, que nasceu em 03/05/2016.", "03/05/2016"),
])
def test_data_de_nascimento_em_formas_menos_usuais(anon, texto, data):
    assert data in _datas_de_nascimento(texto)
    assert data not in anon.anonimizar(texto).texto


@pytest.mark.parametrize("texto,data", [
    ("A iniciativa nasceu em 03/04/2018 com apoio da Secretaria.", "03/04/2018"),
    ("Destaca-se o projeto Semear, que nasceu em 10/10/2010 no bairro.", "10/10/2010"),
    ("O festival Vozes do Sertão nasceu em 15/08/2001, na praça da matriz.", "15/08/2001"),
])
def test_nasceu_com_sujeito_que_nao_e_pessoa(texto, data):
    assert data not in _datas_de_nascimento(texto)


# --------------------------------------------------------------------------- valores
@pytest.mark.parametrize("texto,valor", [
    ("Disse que trabalha como faxineira, recebendo R$ 76,40 por diária.", "R$ 76,40"),
    ("Relatou que gasta perto de R$ 365,00 mensais com remédios.", "R$ 365,00"),
    ("Gastou em média R$ 145,00 por semana com a feira.", "R$ 145,00"),
    ("O filho tira uns dois mil por mês na colheita.", "dois mil"),
    ("Afirmou que já gastou trezentos e cinquenta reais com transporte.", "trezentos e cinquenta reais"),
    ("ela pagou noventa reais de táxi para chegar à consulta.", "noventa reais"),
    ("O companheiro faz fretes com a carroça e ganha \"uns quarenta reais por dia\".", "quarenta reais"),
    ("COM PREJUIZO DE 2300 REAIS AO COMERCIANTE", "2300 REAIS"),
    ("A família sobrevive com dois salários e meio.", "dois salários e meio"),
    ("Pela vaga na marcenaria, o reeducando ganha dois terços do salário mínimo.",
     "dois terços do salário mínimo"),
    ("O reeducando tem pecúlio acumulado de R$ 412,30.", "R$ 412,30"),
    ("Acumulou débito de R$ 2.410,00 junto à concessionária de saneamento.", "R$ 2.410,00"),
    ("Dona Lurdes ainda deve R$ 380,00 na mercearia.", "R$ 380,00"),
    ("Severina trabalha na feira, recebendo R$ 50,00 por dia.", "R$ 50,00"),
    ("Os assaltantes levaram R$ 1.500,00 em dinheiro do armário.", "R$ 1.500,00"),
    ("Foram subtraídos € 750,00 e US$ 420,00 da bolsa da vítima.", "€ 750,00"),
    ("Foram subtraídos € 750,00 e US$ 420,00 da bolsa da vítima.", "US$ 420,00"),
    ("Segundo o requerente, os alimentos foram fixados em 25% do salário mínimo e estão atrasados.", "25%"),
    ("Sua avó, costureira, tem renda média de R$ 1.176,50 por mês.", "R$ 1.176,50"),
    ("O casal se sustenta com o\nBolsa Família e com a pensão\nda filha, de R$ 520,00 por\nmês, além de bicos.",
     "R$ 520,00"),
    ("A renda per capita da família fica em\nR$ 260,00.", "R$ 260,00"),
])
def test_valor_de_pessoa_natural_em_formas_menos_usuais(texto, valor):
    assert valor in _trechos(ReconhecedorValores(), texto, "VALOR_PESSOAL")


def test_valores_da_secao_de_renda_de_ficha():
    texto = ("FICHA DE ACOMPANHAMENTO FAMILIAR\nResponsável: Zélia Wessel, CPF 111.444.777-35\n\n"
             "3. RENDA FAMILIAR\nBolsa Família: R$ 694,00.\nVenda de doces: cerca de R$ 237,80 por mês.\n\n"
             "4. ENCAMINHAMENTOS\nTaxa de inscrição no curso: R$ 50,00.")
    assert _trechos(ReconhecedorValores(), texto, "VALOR_PESSOAL") == ["R$ 694,00", "R$ 237,80"]


@pytest.mark.parametrize("texto", [
    "As 120 aposentadorias do regime próprio têm valor médio de R$ 1.950,00.",
    "Foram concedidos R$ 480,00 mensais de auxílio a 40 famílias atingidas pela enchente.",
    "Rendimento das aplicações no período: R$ 12.345,67",
    "Valor recebido do convênio (em três parcelas): R$ 900.000,00",
    "O prejuízo causado ao fundo previdenciário soma R$ 4 milhões.",
    "Foram atendidas mais de mil pessoas na campanha.",
    "Ano de dois mil e dezenove, às nove horas.",
    "As multas dos veículos leiloados (R$ 260,00 e R$ 390,00) serão pagas pelo Município.",
    "Fica fixada a pensão especial de R$ 2.000,00 aos ex-combatentes.",
    "O auxílio será de R$ 150,00 a R$ 320,00, conforme a faixa de renda.",
    "EXTRATO DE TERMO. Compromissário: Município de Exemplo, CNPJ 11.222.333/0001-81. Em caso de "
    "inadimplência, multa diária de R$ 4.500,00 até o teto de R$ 80.000,00.",
])
def test_valor_publico_ou_agregado_fica_legivel(texto):
    assert _trechos(ReconhecedorValores(), texto, "VALOR_PESSOAL") == []


def test_valores_e_idade_tarjados_no_perfil_lai(anon):
    texto = ("Relato da usuária: Iolanda, de 39 anos, informou que gasta noventa e cinco reais por semana com "
             "transporte e que o marido ganha cerca de mil e quinhentos por mês.")
    saida = anon.anonimizar(texto).texto
    for trecho in ("39 anos", "noventa e cinco reais", "mil e quinhentos"):
        assert trecho not in saida
