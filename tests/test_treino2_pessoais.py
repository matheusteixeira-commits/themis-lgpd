"""Idade, data de nascimento e valores monetários de pessoa natural.

Os exemplos são fictícios. Cobrem as regras de :mod:`themis_lgpd.reconhecedores.pessoais` e o padrão
de data de nascimento de :mod:`themis_lgpd.reconhecedores.documentos`:

* idade exata de pessoa identificável (campo de formulário, aposto ao nome, às iniciais ou ao papel,
  idade com verbo, idade ao lado da data de nascimento, coluna de tabela) e as armadilhas — faixas,
  requisitos, durações, grupos e disposições normativas, que ficam legíveis;
* data de nascimento em outros formatos e em colunas de tabela;
* valores recebidos, pagos ou devidos por pessoa natural (tarjados no perfil LAI) e valores públicos —
  contratos com empresas, orçamento, repasses, valores fixados em norma, médias e totais — que ficam
  legíveis.
"""

import pytest

from themis_lgpd import Anonimizador
from themis_lgpd.catalogo import categoria_de
from themis_lgpd.perfis import ALERTAR, TARJAR, obter_perfil
from themis_lgpd.reconhecedores.pessoais import ReconhecedorIdades, ReconhecedorValores, classificar_valor


@pytest.fixture(scope="module")
def anon() -> Anonimizador:
    return Anonimizador("lai", usar_ner=False)


def _trechos(reconhecedor, texto: str, tipo: str) -> list[str]:
    return [texto[d.inicio:d.fim] for d in reconhecedor.detectar(texto) if d.tipo == tipo]


# --------------------------------------------------------------------------- idade
@pytest.mark.parametrize("texto,idade", [
    ("Paciente: Otávio Lemes Barbosa\nIdade: 52 anos   Sexo: M", "52 anos"),
    ("IDADE: 34 ANOS", "34 ANOS"),
    ("Pcte: Joaquim Silva | Idade: 61 a | Sexo: M", "61 a"),
    ("Idade: 4 anos e 7 meses", "4 anos e 7 meses"),
    ("Interessado: Bruno Tavares Lima, 33 anos, CPF 111.444.777-35", "33 anos"),
    ("VÍTIMA: CLÁUDIA REGINA MOTTA, 41 anos, comerciária", "41 anos"),
    ("Filhos: P.R.S., 8 anos; L.R.S., 3 anos; M.R.S., 5 meses.", "5 meses"),
    ("Criança: T.A.M., sexo feminino, 9 anos, aluna do 4º ano", "9 anos"),
    ("Genitor: Paulo Henrique Dias, 37 anos, pedreiro", "37 anos"),
    ("A genitora, de 29 anos, informou que o filho Davi, de 4 anos, frequenta a creche.", "4 anos"),
    ("Reside com a avó e um sobrinho de 12 anos.", "12 anos"),
    ("A autora, hoje com 3 anos, aguarda vaga em creche.", "3 anos"),
    ("o adolescente R.S.T., então com 15 anos, foi apreendido", "15 anos"),
    ("o réu contava 20 anos na data do fato", "20 anos"),
    ("O aluno tem 9 anos e cursa o 4º ano.", "9 anos"),
    ("possuindo 62 (sessenta e dois) anos de idade e 35 anos de contribuição", "62 (sessenta e dois) anos"),
    ("Data de nascimento: 10/10/2010 (15 anos)", "15 anos"),
    ("Nascimento: 01/02/1990 – 35 anos", "35 anos"),
    ("brasileiro, solteiro, 27 anos, nascido em 02/02/1998", "27 anos"),
])
def test_idade_de_pessoa_identificavel(texto, idade):
    assert idade in _trechos(ReconhecedorIdades(), texto, "IDADE")


@pytest.mark.parametrize("texto", [
    "Vacinação de crianças de 6 meses a menores de 5 anos e de idosos a partir de 60 anos.",
    "Ter idade mínima de 18 anos na data da posse. Idade limite: 65 anos.",
    "Podem participar pessoas com 18 anos ou mais, residentes no município.",
    "O programa atende jovens de 15 a 29 anos há 10 anos.",
    "Hipertensa há 10 anos; iniciou o uso de álcool aos 14 anos.",
    "Fixo a pena definitiva em 6 anos e 2 meses de reclusão.",
    "O servidor conta com 28 anos de serviço e 3 meses de licença não usufruídos.",
    "Afastamento pelo prazo de 2 (dois) anos. Tempo na função: 12 anos e 3 meses.",
    "A escola tem 50 anos de história e a obra tem prazo de 12 meses.",
    "Art. 3º O servidor com 75 anos de idade será aposentado compulsoriamente.",
    "Reexaminar os contatos anualmente por 5 anos.",
    "Faixa etária | Casos\n0 a 4 anos | 120\n60 anos ou mais | 98",
])
def test_idade_em_faixa_requisito_duracao_ou_norma_fica_legivel(texto):
    assert _trechos(ReconhecedorIdades(), texto, "IDADE") == []


def test_tabela_de_composicao_familiar():
    texto = ("NOME | PARENTESCO | IDADE | RENDA\n"
             "Ana Souza | responsável | 40 anos | R$ 900,00 (Bolsa Família)\n"
             "Davi Souza | filho | 9 anos | —")
    assert _trechos(ReconhecedorIdades(), texto, "IDADE") == ["40 anos", "9 anos"]
    assert _trechos(ReconhecedorValores(), texto, "VALOR_PESSOAL") == ["R$ 900,00"]


def test_idade_tarjada_no_perfil_lai(anon):
    r = anon.anonimizar("Usuária: Helena Prado Vieira, 47 anos, encaminhada ao CAPS.")
    assert "47 anos" not in r.texto and "[IDADE]" in r.texto
    assert categoria_de("IDADE").codigo == "DADO_PESSOAL"


# --------------------------------------------------------------------------- data de nascimento
@pytest.mark.parametrize("texto,data", [
    ("nascida em 1º de março de 1987, natural de Picos/PI", "1º de março de 1987"),
    ("Data de nascimento: 1987-03-12", "1987-03-12"),
    ("Nasc.: 12/mar/1987", "12/mar/1987"),
    ("nascido aos 12 dias do mês de março de 1987", "12 dias do mês de março de 1987"),
    ("nascido em 1987, filho de Maria", "1987"),
])
def test_data_de_nascimento_em_outros_formatos(anon, texto, data):
    assert data not in anon.anonimizar(texto).texto


def test_data_de_nascimento_em_coluna_de_tabela(anon):
    texto = ("DEPENDENTES\nNOME | PARENTESCO | DATA DE NASCIMENTO | ADMISSÃO\n"
             "Carla Dias | cônjuge | 03/04/1985 | —\n")
    assert _trechos(ReconhecedorIdades(), texto, "DATA_NASCIMENTO") == ["03/04/1985"]
    assert "03/04/1985" not in anon.anonimizar(texto).texto


def test_datas_de_atos_e_nascidos_em_contagem_ficam_legiveis(anon):
    texto = "Portaria nº 12, de 03/04/2025. Foram registrados 1.204 nascidos em 2023 no município."
    r = anon.anonimizar(texto)
    assert "03/04/2025" in r.texto and "2023" in r.texto


# --------------------------------------------------------------------------- valores
@pytest.mark.parametrize("texto,valor", [
    ("A requerente recebe aposentadoria de R$ 1.600,00 e paga aluguel de R$ 500,00.", "R$ 500,00"),
    ("com remuneração bruta de R$ 7.100,20 e descontos obrigatórios de R$ 1.300,00", "R$ 7.100,20"),
    ("A renda familiar per capita declarada é de R$ 230,00.", "R$ 230,00"),
    ("Informou dívida de R$ 1.240,50 com o mercado do bairro.", "R$ 1.240,50"),
    ("contribuição previdenciária do servidor, atualmente de R$ 980,15 mensais", "R$ 980,15"),
    ("VALOR DA MULTA: R$ 880,41", "R$ 880,41"),
    ("subtraiu a quantia de R$ 640,00 e um celular avaliado em R$ 1.200,00", "R$ 1.200,00"),
    ("A declarante estima o prejuízo em R$ 2.700,00.", "R$ 2.700,00"),
    ("recebe pensão por morte de um salário mínimo", "um salário mínimo"),
    ("o desconto corresponderá a R$ 410,00 (quatrocentos e dez reais)", "R$ 410,00 (quatrocentos e dez reais)"),
    ("Foi arbitrada fiança de R$ 3.000,00 ao autuado.", "R$ 3.000,00"),
    ("O reclamante ganhava R$ 2.300,00 por mês como vigilante.", "R$ 2.300,00"),
    ("Afirmou ter comprado a bicicleta de um vizinho por R$ 450,00.", "R$ 450,00"),
    ("desconto a título de pensão alimentícia de 30% (trinta por cento) dos rendimentos líquidos",
     "30% (trinta por cento)"),
])
def test_valor_de_pessoa_natural(texto, valor):
    assert valor in _trechos(ReconhecedorValores(), texto, "VALOR_PESSOAL")


@pytest.mark.parametrize("texto", [
    "Valor do contrato: R$ 1.200.000,00. A empresa contratada apresentou proposta de R$ 980.000,00.",
    "O edital prevê bolsa mensal de R$ 2.100,00 para cada residente.",
    "Fica fixado o subsídio do cargo de Prefeito em R$ 18.000,00.",
    "O servidor fará jus a diárias no valor de R$ 300,00 por dia de deslocamento.",
    "Aplica-se multa de R$ 500,00 por dia de atraso, devida pela contratada.",
    "A renda média das famílias atendidas pelo programa é de R$ 812,00.",
    "O auxílio será pago no valor de R$ 600,00 por família beneficiária.",
    "Remuneração inicial: R$ 4.200,00 para jornada de 40 horas semanais.",
    "As famílias com renda mensal de até R$ 660,00 por pessoa têm prioridade.",
    "A infração sujeita o infrator a multa de R$ 1.000,00 a R$ 10.000,00.",
    "O Município recebeu repasse de R$ 2.000.000,00 do Fundo Nacional.",
    "O débito do Município com o INSS soma R$ 4.500.000,00.",
    "O prejuízo ao erário foi apurado em R$ 55.000,00.",
    "Dotação orçamentária de R$ 300.000,00. Taxa de inscrição: R$ 120,00.",
    "O salário mínimo nacional passou a R$ 1.518,00 em janeiro.",
    "os autores levaram R$ 3.100,00 do caixa da empresa",
    "Dá-se à causa o valor de R$ 1.000,00.",
    "Cargo | Vagas | Vencimento\nAnalista | 3 | R$ 5.100,00",
    "Empresa | CNPJ | Valor (R$)\nAlfa Ltda. | 11.222.333/0001-81 | 98.000,00",
    "Município | Beneficiários | Valor (R$)\nCampo Alto | 1.204 | 845.000,00",
    "O desconto em folha não pode exceder 30% da remuneração do servidor.",
    "O reajuste de 5% dos vencimentos dos servidores foi aprovado.",
    "Segundo o edital, eu ganho ajuda de custo de 50% do salário inicial durante o curso de formação.",
])
def test_valor_publico_fica_legivel(texto):
    assert _trechos(ReconhecedorValores(), texto, "VALOR_PESSOAL") == []


def test_tabela_de_pessoas_com_valores():
    texto = ("Contribuinte\tCPF\tValor devido (R$)\n"
             "Paulo Reis\t111.444.777-35\t1.284,60\n")
    assert _trechos(ReconhecedorValores(), texto, "VALOR_PESSOAL") == ["1.284,60"]


def test_notas_e_tempo_de_servico_em_tabela_de_pessoas_nao_sao_valor_nem_idade():
    texto = ("INSCRIÇÃO | NOME | NOTA | TEMPO DE SERVIÇO\n"
             "1023 | Paulo Reis | 72,50 | 12 anos\n"
             "1088 | Lia Matos | 68,25 | 4 anos\n")
    assert _trechos(ReconhecedorValores(), texto, "VALOR_PESSOAL") == []
    assert _trechos(ReconhecedorIdades(), texto, "IDADE") == []


def test_declaracao_de_bens_tem_todos_os_valores_tarjados():
    texto = ("DECLARAÇÃO DE BENS E VALORES\n\n1. BENS IMÓVEIS\n"
             "1.1 | Casa residencial no endereço declarado | 2015 | 250.000,00\n\n"
             "2. VEÍCULOS\n2.1 | Automóvel ano 2019 - VALOR: R$ 48.000,00\n")
    assert _trechos(ReconhecedorValores(), texto, "VALOR_PESSOAL") == ["250.000,00", "R$ 48.000,00"]


def test_extrato_de_contrato_com_pessoa_fisica():
    pf = "CONTRATADA: FULANA DE TAL, CPF ***.123.456-**, artista popular.\nVALOR: R$ 7.000,00 (sete mil reais)."
    pj = "CONTRATADA: Beta Serviços Ltda., CNPJ 11.222.333/0001-81.\nVALOR: R$ 7.000,00 (sete mil reais)."
    assert _trechos(ReconhecedorValores(), pf, "VALOR_PESSOAL") == ["R$ 7.000,00 (sete mil reais)"]
    assert _trechos(ReconhecedorValores(), pj, "VALOR_PESSOAL") == []


def test_mesmo_valor_repetido_no_documento():
    texto = ("O acusado subtraiu a quantia de R$ 730,00 da vítima. Fixo, nos termos do art. 387, IV, do CPP, "
             "o valor de R$ 730,00, a ser pago no prazo de 30 dias.")
    assert _trechos(ReconhecedorValores(), texto, "VALOR_PESSOAL") == ["R$ 730,00", "R$ 730,00"]


def test_classificacao_pela_expressao_mais_proxima():
    texto = "A cessão ocorre sem ônus; a remuneração da servidora é de R$ 6.000,00, conforme contrato de gestão."
    i = texto.index("R$")
    assert classificar_valor(texto, i, i + len("R$ 6.000,00")) == "pessoal"
    texto = "Pela remuneração dos serviços, o contrato prevê R$ 6.000,00."
    i = texto.index("R$")
    assert classificar_valor(texto, i, i + len("R$ 6.000,00")) == "publico"


def test_regras_dos_perfis_para_valores():
    assert categoria_de("VALOR_PESSOAL").codigo == "ECONOMICO"
    assert obter_perfil("lai").regra("ECONOMICO") == TARJAR
    assert obter_perfil("identificadores").regra("ECONOMICO") == ALERTAR
    assert all(obter_perfil(p).regra("ECONOMICO") == TARJAR for p in ("saude", "ouvidoria", "educacao", "maxima"))


def test_valor_tarjado_no_perfil_lai_e_publico_mantido(anon):
    r = anon.anonimizar("A família sobrevive do Programa Bolsa Família, cujo benefício atual é de R$ 650,00. "
                        "O programa tem orçamento anual de R$ 3.000.000,00.")
    assert "R$ 650,00" not in r.texto and "[VALOR]" in r.texto
    assert "R$ 3.000.000,00" in r.texto
