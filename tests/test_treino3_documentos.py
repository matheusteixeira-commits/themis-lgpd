"""Regressão de identificadores documentais, profissionais e processuais (ciclo 3).

Os exemplos são fictícios e cobrem classes de redação de documentos oficiais: tabelas alinhadas por
espaços e planilhas em CSV com o rótulo só no cabeçalho, rótulos abreviados, militares identificados
por posto e quadro, documentos de identidade e de viagem estrangeiros, assentos de registro civil
por livro e folha, carteiras sem formato nacional, registros em sistemas de saúde e instrumentos
individuais da proteção à criança e da execução penal. As armadilhas são números de atos públicos
e de contratações, contas de entes públicos, numeração de itens com forma de endereço IP, chaves de
nota fiscal, quantidades, protocolos de publicação e a sigla e a UF do órgão emissor ao lado do
número.
"""

import pytest

from themis_lgpd import validadores as v

VAZAMENTOS = [
    # (texto, trechos que NÃO podem sobrar na saída)
    # Tabela alinhada por espaços, com o rótulo só no cabeçalho e o nome em duas linhas.
    ("LISTA DE PRESENÇA\n\nNº   NOME                     MATRÍCULA    LOTAÇÃO\n"
     "01   FULANA DE TAL            7731205-4    ESCOLA ALFA\n"
     "     DOS ANJOS                             CENTRO\n"
     "02   BELTRANO SOUSA           6620913-1    ESCOLA BETA\n",
     ["7731205-4", "6620913-1"]),
    # O cabeçalho da coluna pode ser uma palavra de uma célula maior.
    ("ORD. INSCRIÇÃO     CANDIDATO              PONTOS\n"
     "1º   31009876542   FULANO DE TAL          88,0\n"
     "2º   31009812345   BELTRANA DE TAL        86,5\n",
     ["31009876542", "31009812345"]),
    # Escala com a numeração dos dias no cabeçalho e o registro do conselho na coluna.
    ("PROFISSIONAL                 COREN-TO     01 02 03 04\n"
     "ENFª FULANA DE TAL           123.987-ENF  M  T  F  SN\n"
     "TÉC. ENF. BELTRANO           456.321-TE   F  M  T  F\n",
     ["123.987", "456.321"]),
    # Planilha exportada em CSV: agência e conta de cada bolsista.
    ("Nº;NOME;CPF;VALOR;BANCO;AGENCIA;CONTA\n1;\"FULANA DE TAL\";***.111.222-**;300,00;001;4321-0;77889-1\n",
     ["4321-0", "77889-1"]),
    # Tabela alinhada com agência e conta, inclusive a operação separada por espaço.
    ("Nº  BOLSISTA            MATR.       AG.     CONTA          VALOR\n"
     "01  FULANO DE TAL       202611223   3344    013 556677-8   500,00\n",
     ["202611223", "3344", "556677"]),
    # Militar identificado pelo posto, pelo quadro e pelo número.
    ("SUPERVISOR: 1º TEN QOPM 130.555-2 FULANO\nPATRULHA: SD PM 140.777-9 BELTRANO e CB BM 150.888-1 CICRANO",
     ["130.555", "140.777", "150.888"]),
    # Rótulos abreviados sem ponto, em maiúsculas, de formulários.
    ("VÍNCULO: SERVIDOR   MATR 55123   CARGO AGENTE\nRECEBIDO POR FULANA MAT 44.321 – PROTOC 2026/007788",
     ["55123", "44.321", "2026/007788"]),
    ("Nº FICHA: 0789/2026        Data do cadastro: 02/03/2026", ["0789/2026"]),
    ("Ref.: PAJ nº 2026/0099-321 – Assistido: FULANO DE TAL", ["2026/0099"]),
    # Número e ano separados por espaço, como em formulário lido por OCR.
    ("PROCESSO ADMINISTRATIVO N 77123 2026\nCERTIDAO DE TEMPO DE CONTRIBUICAO N 0456 2026", ["77123", "0456"]),
    # Documentos de estrangeiros com o país entre a designação e o número.
    ("Requerente: FULANO, passaporte peruano nº AB1234567, NIF haitiano: 001-234-567-8.", ["AB1234567", "234-567"]),
    ("Portadora da cédula V-12.345.678 e da cédula de identidad boliviana nº 7.123.456 LP.",
     ["12.345.678", "7.123.456"]),
    ("Apresentou carta d'identità elettronica nº XY12345ZW e o DPRNM nº 2026.0101.555.", ["XY12345ZW", "0101.555"]),
    ("Codice fiscale BNCLCU75C12F205G; documento de identidade chinês: 33010619880315123X",
     ["BNCLCU75C12F205G", "33010619880315123X"]),
    # Assento de registro civil ou ato de notas por livro, folha e termo.
    ("Certidão de nascimento: termo 1.234, livro A-56, folha 78", ["1.234", "56", "78"]),
    ("pacto antenupcial lavrado no Livro 91, fls. 23, do Tabelionato de Notas", ["91", "23"]),
    ("apresentou partida de nacimiento, acta nº 55, tomo 3, folio 9, do registro civil", ["55", "3, folio 9"]),
    # Carteiras e registros sem formato nacional.
    ("CIPTEA nº 2026-TO-7654321; pescador com RGP PA-00123456; técnica com registro MTE PI/001122.3",
     ["7654321", "00123456", "001122"]),
    # Registros em sistemas de saúde e acadêmicos.
    ("Registro SIASI: 3.210.987\nR.A.: 123.456.789-0\nProntuário na unidade: 7788",
     ["3.210.987", "456.789", "7788"]),
    # Instrumentos individuais da proteção à criança e da execução penal.
    ("Assunto: comunicação de faltas – FICAI nº 2026/0456", ["2026/0456"]),
    ("RELATÓRIO DE REAVALIAÇÃO – PIA nº 321/2026-XYZ", ["321/2026"]),
    ("FICHA DE ACOLHIMENTO Nº 0912/2026\nProcedência: rodoviária", ["0912/2026"]),
    ("FICHA DE MATRÍCULA – ANO LETIVO 2026 – Nº 2026/001234", ["001234"]),
    ("PARECER DE ACOMPANHAMENTO CLÍNICO INDIVIDUAL Nº 33/2026\nPaciente: FULANO", ["33/2026"]),
    ("PARECER TÉCNICO Nº 044/2026-CTX\n\nFinalidade: instruir pedido de progressão para o regime semiaberto",
     ["044/2026"]),
    ("COMUNICADO À FAMÍLIA Nº 21/2026\n\nSenhores responsáveis pelo estudante", ["21/2026"]),
]


@pytest.mark.parametrize("texto,proibidos", VAZAMENTOS)
def test_identificador_tarjado(anon, texto, proibidos):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


PUBLICOS = [
    # (texto, trechos que DEVEM permanecer legíveis)
    # Processo citado junto ao número da contratação ou do repasse.
    ("EXTRATO DO CONTRATO Nº 015/2026\nProcesso Administrativo nº 0101/2026 – Pregão Eletrônico nº 07/2026. "
     "CONTRATADA: Empresa Exemplo Ltda., CNPJ 12.345.678/0001-95; pela contratada, o sócio FULANO, "
     "CPF 526.018.159-06.", ["0101/2026"]),
    ("Contrato: Contrato nº 33/2026/DER – Processo SEI nº 00000.000123/2026-11.\nContratada: Construtora Alfa Ltda.",
     ["00000.000123/2026-11"]),
    ("equipamento adquirido com recursos da Proposta FNS nº 36000.000777/2026-00, entregue em março.",
     ["36000.000777/2026-00"]),
    ("O acordo encerra a Ação Civil Pública nº 0716202-44.2008.8.07.8769, movida contra o Município.",
     ["0716202-44.2008.8.07.8769"]),
    ("nos termos do art. 318 do Código de Processo Penal e do Habeas Corpus coletivo nº 123.456/XX.", ["123.456"]),
    # Notificação, auto e laudo dirigidos a pessoa jurídica ou sobre obra.
    ("Foi lavrada a Notificação nº 9/2026 contra a Construtora Beta Ltda., com prazo de dez dias.", ["9/2026"]),
    ("A medição atrasou, apesar da Notificação nº 31/2026. Por isso, a Pavimentadora Gama Ltda. foi multada.",
     ["31/2026"]),
    ("o Laudo de Ensaio de Compressão nº EC-12/2026 indicou resistência do concreto acima do projeto.", ["12/2026"]),
    # Sigla de conselho seguida do número de um ato ou do registro de pessoa jurídica.
    ("conforme o Ofício OAB/TO nº 12/2026 e o Parecer Técnico CREA-PI nº 5/2026.", ["12/2026", "5/2026"]),
    ("apresentou certidão de registro de pessoa jurídica no CRA-AC nº 1.234/2020.", ["1.234/2020"]),
    # Numeração de itens e códigos com forma de endereço IP.
    ("conforme o subitem 9.2.1.3 do Termo de Referência e a cláusula 12.4.1.2 do contrato; COBRADE 1.2.3.4.5",
     ["9.2.1.3", "12.4.1.2", "1.2.3.4.5"]),
    # Ano e contagem junto a palavras-chave de identificador.
    ("A matrícula de 2026 é de 1.234 estudantes.\nUnidade | Matrícula 2026 | Turmas\nEscola Alfa | 812 | 20\n"
     "Cidade Exemplo, 5 de maio de 2026.", ["2026", "5 de maio de 2026"]),
    ("No ano, o hospital fez 12.345 atendimentos de urgência e 2.004 partos.", ["2.004"]),
    # Contas de fundo, de convênio e de entidade parceira.
    ("Doações podem ser feitas por depósito na conta do fundo: agência 1234-5, conta corrente 98.765-4.",
     ["1234-5", "98.765-4"]),
    ("CONTA ESPECÍFICA DO CONVÊNIO: Banco Exemplo, agência 4321, conta 55.667-8.", ["4321", "55.667-8"]),
    ("nomeado para o cargo em comissão de Diretor, símbolo CC-2, a partir de 1º de março.", ["CC-2"]),
    # Chave de acesso de nota fiscal eletrônica em grupos de quatro dígitos.
    ("NF-e nº 1.234, chave de acesso 1234 5678 9012 3456 7890 1234 5678 9012 3456 7890 1234.", ["9012 3456 7890"]),
    # Protocolo de publicação no diário oficial e código de autenticação do documento.
    ("DIÁRIO OFICIAL DO MUNICÍPIO DE EXEMPLO\nPORTARIA Nº 12, DE 2 DE MARÇO DE 2026\nNomear o servidor.\n"
     "Protocolo 7654321", ["7654321"]),
    ("A autenticidade pode ser conferida informando o código verificador 1234567 e o código CRC 1A2B3C4D.",
     ["1A2B3C4D"]),
    # Data do próprio ato após "registro".
    ("Data do registro: 10/02/2026\nNatureza: reclamação", ["10/02/2026"]),
    # Órgão emissor e UF do documento ficam visíveis; o número não.
    ("RG 1.234.567 SSP/TO e COREN-TO 123.456", ["SSP/TO", "COREN-TO"]),
    # Linha de pessoa jurídica numa tabela de notificados.
    ("PLACA     AIT         PROPRIETÁRIO                  VALOR\n"
     "ABC1D23   X1234567    TRANSPORTES ALFA LTDA         130,16\n", ["X1234567"]),
]


@pytest.mark.parametrize("texto,legiveis", PUBLICOS)
def test_trecho_publico_continua_legivel(anon, texto, legiveis):
    saida = anon.anonimizar(texto).texto
    for p in legiveis:
        assert p in saida, f"tarjou {p!r} em: {saida!r}"


def test_tabela_de_pessoa_natural_tarja_ait(anon):
    """Na mesma tabela, o auto de infração do proprietário pessoa natural é tarjado."""
    texto = ("PLACA     AIT         PROPRIETÁRIO                  VALOR\n"
             "ABC1D23   X7654321    FULANO DE TAL                 130,16\n")
    assert "X7654321" not in anon.anonimizar(texto).texto


def test_conta_pessoal_continua_tarjada_perto_de_empresa(anon):
    """A conta da pessoa é tarjada mesmo quando a frase menciona uma empresa ou um órgão."""
    texto = "A empresa contratada não pagou; meus dados para depósito são agência 1122-3 e conta 44556-7."
    saida = anon.anonimizar(texto).texto
    assert "1122-3" not in saida and "44556-7" not in saida, saida


def test_contrato_com_pessoa_natural_tarja_processo(anon):
    """Quando a contratada é pessoa natural, o processo junto ao número do contrato é dado pessoal."""
    texto = ("EXTRATO DO CONTRATO Nº 090/2026\n\nPROCESSO ADMINISTRATIVO: 4410/2026-SECY\n"
             "CONTRATADA: FULANA DE TAL, CPF ***.645.300-**, artista.")
    assert "4410/2026" not in anon.anonimizar(texto).texto


@pytest.mark.parametrize("texto,numero", [
    ("Gostaria de cópia do auto de infração nº 2026/0099 lavrado contra a empresa Delta Ltda.", "2026/0099"),
    ("Solicito o andamento do processo nº 4321/2026 – Pregão Eletrônico nº 3/2026, em que sou interessado.",
     "4321/2026"),
    ("Preciso validar o documento: código verificador 7654321.", "7654321"),
])
def test_pedido_em_primeira_pessoa_mantem_tarja(anon, texto, numero):
    """No pedido redigido em primeira pessoa, o número citado pelo autor continua tarjado, ainda que
    envolva empresa, contratação ou documento eletrônico."""
    assert numero not in anon.anonimizar(texto).texto


def test_auto_contra_pessoa_natural_continua_tarjado(anon):
    texto = "Auto de Infração nº 123/2026 lavrado contra o proprietário, Sr. Fulano, que tem obra em andamento."
    assert "123/2026" not in anon.anonimizar(texto).texto


@pytest.mark.parametrize("valor,esperado", [
    ("BNCLCU75C12F205G", True), ("BNCLCU75C12F205H", False), ("BNCLCU75C12F20", False),
])
def test_codice_fiscale(valor, esperado):
    assert v.codice_fiscale_valido(valor) is esperado


@pytest.mark.parametrize("valor,esperado", [
    ("33010619880315123X", True), ("440305199207204563", True), ("440305199207204564", False),
    ("440305199213204563", False),  # mês inexistente
])
def test_identidade_chinesa(valor, esperado):
    assert v.identidade_chinesa_valida(valor) is esperado


@pytest.mark.parametrize("texto,trecho,esperado", [
    ("conforme o subitem 8.1.2.3 do edital", "8.1.2.3", True),
    ("código de classificação 1.2.3.4.5", "1.2.3.4", True),
    ("acesso pelo IP 10.20.30.40 às 10h", "10.20.30.40", False),
])
def test_numeracao_de_item(texto, trecho, esperado):
    i = texto.index(trecho)
    assert v.numeracao_de_item(texto, i, i + len(trecho)) is esperado


def test_parte_de_sequencia():
    texto = "chave 1234 5678 9012 3456 7890 1234 e cartão 4111 1111 1111 1111 válido"
    i = texto.index("5678")
    assert v.parte_de_sequencia(texto, i, i + 19)
    j = texto.index("4111")
    assert not v.parte_de_sequencia(texto, j, j + 19)
