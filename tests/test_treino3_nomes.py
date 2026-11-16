"""Nomes de pessoas em documentos difíceis: recall em formas atípicas e precisão em nomes próprios de
lugares, entidades, embarcações e empresas.

Recall: nomes estrangeiros e indígenas fora das listas, com partículas ("DEL", "VON DER"); nomes do
Leste Asiático com o sobrenome em CAIXA ALTA à frente; prenomes de devoção ou que são palavras comuns;
apelidos e nomes sociais; iniciais de duas letras repetidas no documento; nomes invertidos em listas
("SOBRENOME, Fulana"); nome de guerra após posto e matrícula; nomes em tabelas alinhadas por espaços,
inclusive o restante na linha de baixo; nomes um por linha; prenome que coincide com município.

Precisão: nome de pessoa em embarcação, equipamento, honraria, operação e programa; escola abreviada
em tabela; logradouro e município citados sem o tipo, como sujeito de oração, quando o próprio
documento os identifica; distrito e região administrativa; razão social com sobrenomes ou iniciais;
bairro na linha de endereço; sigla de órgão seguida do município. Todos os exemplos são fictícios.
"""

import pytest

from themis_lgpd.reconhecedores.nomes import ReconhecedorNomesContexto, contexto_nao_pessoal


def _saida(anon, texto):
    return anon.anonimizar(texto).texto


def _nomes(texto):
    return [texto[d.inicio:d.fim] for d in ReconhecedorNomesContexto().detectar(texto)]


# Nome, ou partes dele, que não pode ficar visível.
OCULTOS = [
    # Partículas de sobrenomes estrangeiros e rótulo com qualificação entre parênteses
    ("Nome (como consta no passaporte): ROSALBA DEL PILAR ITURRIAGA MONSALVE\nNacionalidade: chilena",
     ["ROSALBA", "PILAR", "ITURRIAGA", "MONSALVE"]),
    ("O casal reside no sítio. A esposa, HILDEGARD VON DER LINDEN, agricultora, acompanhou a visita.",
     ["HILDEGARD", "LINDEN"]),
    # Rótulo com flexão entre parênteses, inclusive colado ao valor
    ("Interessado(a): DORIVALDO DE MATOS BRAGA\nAssunto: segunda via", ["DORIVALDO", "BRAGA"]),
    ("Aluno(a):WANDEMBERG CORDOVIL PRATES Turma:5A", ["WANDEMBERG", "CORDOVIL"]),
    # Leste Asiático: sobrenome em CAIXA ALTA à frente e prenome hifenizado
    ("Nome: WANG Xiaoming (também grafado WANG Xiao Ming)\nMãe: CHOI Eun-ji, cozinheira",
     ["WANG", "Xiaoming", "Xiao Ming", "CHOI", "Eun-ji"]),
    ("TESTEMUNHAS\nLIU Hao-ran, natural de Taipé, auxiliar de cozinha.", ["LIU", "Hao-ran"]),
    # Parentesco em aposto
    ("O companheiro, ESTEBAN OSORIO CALLISAYA, é mecânico.", ["ESTEBAN", "CALLISAYA"]),
    ("Compareceu com seu marido, HWANG Min-jun, que traduziu o relato.", ["HWANG", "Min-jun"]),
    # Apelidos e nome social
    ('Abordado um senhor conhecido na vila como "Doutorzinho", sem documentos.', ["Doutorzinho"]),
    ("O sobrinho era chamado pelos colegas de Tonho.", ["Tonho"]),
    ("Nome pelo qual gosta de ser chamada: Belinha\nIdade: 9 anos", ["Belinha"]),
    ("Na feira, dois peruanos conhecidos como el Chato e la Limeña ofereceram serviço.", ["Chato", "Limeña"]),
    ('"Duda" (nome social), acompanhada pela equipe desde maio.', ["Duda"]),
    ("O gerente da loja, chamado pelos funcionários de Sr. Tanaka, controlava a escala.", ["Tanaka"]),
    # Iniciais de duas letras repetidas no documento
    ("Criança atendida: Y.J., 6 anos.\nA escola relatou faltas de Y.J. no bimestre.", ["Y.J"]),
    ("– X.W., filho do casal, 4 anos;\n– K.Q., sobrinha, 15 anos.", ["X.W", "K.Q"]),
    # Nome invertido em listas e tabelas
    ("30.111.222-3   2   QUEIROZ, Edinalva Moreira do        ASG    01  02\n"
     "                   Prado\n40.111.333-4   2   PEÇANHA, Ondina Aparecida           ASG    03  00",
     ["QUEIROZ", "Edinalva", "Prado", "PEÇANHA", "Ondina"]),
    ('1;"QUEIROZ, LUANA BEATRIZ COSTA";***.512.111-**;CANOAGEM\n2;"CORDOVIL, CAIO AUGUSTO LIMA";***.512.222-**;REMO',
     ["QUEIROZ", "LUANA", "CORDOVIL", "CAIO AUGUSTO"]),
    ("Escala do mês\nCAMPOS, R. T.       D  N  N  D\nSAMPAIO, E. L.      N  D  D  N", ["CAMPOS", "SAMPAIO"]),
    # Nome de guerra após posto, corporação e matrícula
    ("RP 2201 – CMT: 2º SGT PM 100.200-3 CORDOVIL | MOT: SD PM 100.300-4 WANDEMBERG\n"
     "– SD PM 100.400-5 DE ASSIS: em férias", ["CORDOVIL", "WANDEMBERG", "DE ASSIS"]),
    # Tabela alinhada por espaços, com o restante do nome na linha de baixo
    ("Nº   NOME                        CPF              MATRÍCULA\n"
     "01   ODALÍCIO BRANDEMBERG        111.222.333-96   1234567-2\n"
     "     DE ARAÚJO FROTA\n"
     "02   ETELVINA POLICARPO          222.333.444-05   2345678-3",
     ["ODALÍCIO", "BRANDEMBERG", "ARAÚJO FROTA", "ETELVINA", "POLICARPO"]),
    # Nomes um por linha
    ("RELAÇÃO DE BENEFICIÁRIOS\nFAUSTINA GOMES DE MELO\nWANDEMBERG SOUZA CRUZ\nODALÍCIO PEREIRA DO VALE",
     ["FAUSTINA", "WANDEMBERG", "ODALÍCIO"]),
    # Prenome de devoção e prenome que é palavra comum
    ("Responsável familiar: PIEDADE SOLEDADE DOS ANJOS\nNIS 123.45678.90-1", ["PIEDADE", "SOLEDADE"]),
    ("Dona Providência relatou o fato, e Seu Benvindo confirmou.", ["Providência", "Benvindo"]),
    ("3. CONSOLATA RIBAS DUARTE – avó da criança – 68 anos", ["CONSOLATA", "RIBAS"]),
    # Prenome que coincide com município, com idade em aposto e nas demais menções
    ("a filha Mariana, de 13 anos; o neto Irapuã, de 9 anos, aguarda vaga. A matrícula de Irapuã foi negada.",
     ["Mariana", "Irapuã"]),
    ("Os netos Caio, de seis anos, e Yasmine, de três anos, ficaram sem luz.", ["Caio", "Yasmine"]),
    # Apresentação explícita com nome fora das listas
    ("Disse que a moça se chama EULINA HUARACHI TICONA e trabalha na feira.", ["EULINA", "HUARACHI", "TICONA"]),
    # Papel em caixa alta e escola de alguém ("a escola de Fulano" é posse, não nome de instituição)
    ("QUALIFICADA A AUTORA DO FATO ODALÍCIA TERESO BRANDEMBERG, SEM APELIDO", ["ODALÍCIA", "TERESO"]),
    ("Ficou em casa. Kethellyn Rocha voltou depois; a mãe procurou a escola de Kethellyn.", ["Kethellyn"]),
]


@pytest.mark.parametrize("texto,proibidos", OCULTOS)
def test_nomes_dificeis_sao_tarjados(anon, texto, proibidos):
    saida = _saida(anon, texto)
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


# Trecho público que precisa continuar legível.
LEGIVEIS = [
    # Embarcações
    ("A reforma da lancha Comandante Euclides Barreto terminou.", "Euclides Barreto"),
    ("O B/M Tia Josefa transporta os alunos.", "Tia Josefa"),
    ("A balsa N/M Dona Corina Vasconcelos II segue em operação.", "Corina Vasconcelos"),
    # Equipamentos, honrarias, operações, programas e entidades
    ("A Operação Lampião Ferido foi deflagrada ontem.", "Lampião Ferido"),
    ("A sessão ocorreu no Plenário Vereador Osório Dantas.", "Osório Dantas"),
    ("Reforma do Mercado Público Seu Lalau Furtado.", "Lalau Furtado"),
    ("Apresentação da Orquestra Sinfônica Maestro Hélio Prates.", "Hélio Prates"),
    ("Pagamento da Bolsa Talento Esportivo Faustina Guimarães.", "Faustina Guimarães"),
    ("Entrega das casas do Conjunto Habitacional Vereadora Odalícia Lustoza.", "Odalícia Lustoza"),
    ("ASSOCIAÇÃO BENEFICENTE DOUTOR ODALÍCIO TERESO – CNPJ 00.000.000/0001-00", "ODALÍCIO TERESO"),
    ("Encaminhada ao CRAS Nossa Senhora das Graças.", "Nossa Senhora das Graças"),
    ("Atendida na Casa da Mulher Capixaba e orientada.", "Capixaba"),
    ("Ronda Ostensiva Tenente Policarpo Tereso reforçada.", "Policarpo Tereso"),
    # Escola abreviada em tabela e continuação do nome da escola na linha de baixo
    ("Código | Escola | Alunos\n12345678 | E.E.E.F. PROF.ª ZÉLIA PARANHOS | 312", "ZÉLIA PARANHOS"),
    ("01   ODALÍCIO BRANDEMBERG        111.222.333-96   EEF VEREADOR ETELVINO\n"
     "                                                  PEÇANHA LIMA", "PEÇANHA LIMA"),
    # Município citado em contexto inequívoco e retomado como sujeito
    ("PREFEITURA MUNICIPAL DE BENTO GONÇALVES\nBento Gonçalves ampliou o horário das unidades.", "Bento Gonçalves ampliou"),
    ("DECRETO DO PREFEITO MUNICIPAL DE GOVERNADOR EDISON LOBÃO", "GOVERNADOR EDISON LOBÃO"),
    ("CONSELHO MUNICIPAL DO IDOSO DE TEIXEIRA DE FREITAS", "TEIXEIRA DE FREITAS"),
    ("Compareceu, natural de Comendador Levy Gasparian, a requerente.", "Comendador Levy Gasparian"),
    # Distritos, regiões administrativas e logradouros sem o tipo
    ("Atendimento nos distritos de Quilombinho, Bento Ferraz e Jacinto Moura. Bento Ferraz recebe a unidade móvel.",
     "Bento Ferraz recebe"),
    ("Atendimento em Ceilândia, Samambaia e Vicente Pires. Vicente Pires ganhou nova equipe.", "Vicente Pires ganhou"),
    ("Pavimentação das ruas Osvaldo Peixoto, Ana Leopoldina Brito e Teodoro Valente. Ana Leopoldina Brito está "
     "concluída.", "Ana Leopoldina Brito está"),
    # Razão social
    ("Contratada: Peçanha & Vilela Engenharia Ltda., CNPJ 00.000.000/0001-00.", "Peçanha & Vilela"),
    ("Fornecedor: P. H. Lacerda Comércio de Ferragens Ltda.", "P. H. Lacerda"),
    # Sigla de órgão seguida do município
    ("Nº | NOME | CPF | LOTAÇÃO\n01 | ODALÍCIO BRANDEMBERG | 111.222.333-96 | SME ICÓ", "SME ICÓ"),
    # Pronome de tratamento abreviado, parentesco e gentílico em aposto
    ("Solicito a V. Sa. que encaminhe os documentos.", "V. Sa."),
    ("b) Edinalva Prates, filha, 11 anos; c) Ondina Prates, haitiana, 29 anos.", "haitiana"),
    ("b) Edinalva Prates, filha, 11 anos.", "filha"),
]


@pytest.mark.parametrize("texto,visivel", LEGIVEIS)
def test_nomes_proprios_nao_pessoais_ficam_legiveis(anon, texto, visivel):
    saida = _saida(anon, texto)
    assert visivel in saida, f"{visivel!r} deveria ficar visível em: {saida!r}"


def test_sigla_antes_de_nome_invertido_fica_legivel(anon):
    texto = "Segundo o presidente da AGERP, Osmar Lacerda Pinto, a fiscalização continua. A AGERP informou."
    saida = _saida(anon, texto)
    assert "Osmar" not in saida
    assert saida.count("AGERP") == 2


def test_assinatura_nao_continua_no_cargo(anon):
    texto = "Atenciosamente,\n\nOndina Peçanha\nOuvidora-Geral\nBento Gonçalves, 07/04/2027."
    saida = _saida(anon, texto)
    assert "Ondina" not in saida and "Ouvidora-Geral" in saida


def test_pessoa_homonima_de_lugar_do_documento_e_tarjada(anon):
    texto = ("PREFEITURA MUNICIPAL DE BENTO GONÇALVES\nBento Gonçalves ampliou o horário. "
             "A servidora Mariana Lustoza informou; a filha Mariana, de 13 anos, foi atendida.")
    saida = _saida(anon, texto)
    assert "Bento Gonçalves ampliou" in saida
    assert "Mariana" not in saida


@pytest.mark.parametrize("texto,nome", [
    ("a lancha Comandante Euclides Barreto", "Euclides"),
    ("Mercado Público Seu Lalau Furtado", "Lalau"),
    ("Praça Vereador Osório Dantas", "Praça"),
    ("Contratada: Peçanha & Vilela Engenharia Ltda.", "Vilela"),
    ("Atendimento no distrito de Jacinto Moura", "Jacinto"),
    ("CONSELHO TUTELAR DE TEIXEIRA DE FREITAS", "TEIXEIRA"),
    ("END.: R. DAS PALMEIRAS, 40, AP. 3 – RUBEM BERTA – GUARULHOS/SP", "RUBEM"),
    ("Endereço: Quadra 4, Conjunto B, Casa 9, Vicente Pires", "Vicente"),
])
def test_contexto_nao_pessoal_em_nomes_proprios(texto, nome):
    assert contexto_nao_pessoal(texto, texto.index(nome))


@pytest.mark.parametrize("texto,nome", [
    ("a mãe procurou a escola de Kethellyn", "Kethellyn"),
    ("o barco de Euclides Barreto afundou", "Euclides"),
    ("a filha ficou em casa. Ondina voltou", "Ondina"),
])
def test_posse_e_fim_de_frase_nao_sao_nome_de_instituicao(texto, nome):
    assert not contexto_nao_pessoal(texto, texto.index(nome))


def test_siglas_de_unidade_com_pontos_nao_sao_iniciais():
    assert not [n for n in _nomes("Escola: E.E.E.F. | E.M.E.B. | 12") if n in ("E.E.E.F", "E.M.E.B")]


def test_cabecalho_de_papel_e_grafia_alternativa():
    nomes = _nomes("VÍTIMA\nQIAN Mei-hua, chinesa, 42 anos\nTambém grafado QIAN Meihua.")
    assert "QIAN Mei-hua" in nomes and "QIAN Meihua" in nomes


@pytest.mark.parametrize("texto,nome", [
    ("Eu, Teodoro Casa Nova, residente em Sobral, solicito cópia do processo.", "Teodoro Casa Nova"),
    ("Eu, Iolanda da Ponte Siqueira, solicito informações sobre o pedido.", "Iolanda da Ponte Siqueira"),
])
def test_sobrenome_com_palavra_de_instituicao(anon, texto, nome):
    saida = anon.anonimizar(texto).texto
    assert not [p for p in nome.split() if len(p) > 3 and p in saida], saida


@pytest.mark.parametrize("texto,nome", [
    ("Encaminhe-se à Casa de Cultura Benedito Arruda para providências.", "Benedito"),
    ("A Escola Estadual Lindalva Prates recebeu a visita.", "Lindalva"),
])
def test_instituicao_com_nome_de_pessoa_continua_legivel(anon, texto, nome):
    assert nome in anon.anonimizar(texto).texto
