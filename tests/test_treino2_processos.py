"""Regressão dos identificadores processuais, profissionais e documentos em documentos oficiais.

Os exemplos são fictícios e cobrem classes de redação de laudos, relatórios sociais, portarias,
escalas e editais de resultado: número de documento sobre pessoa com qualificativos e sigla da
unidade emissora, registros policiais pela sigla da UF, registro em conselho com a região, matrícula
em formatos de cada ente, CPF mascarado, CNS com pontos e identificadores em colunas de tabelas.
As armadilhas são números de atos públicos, de tabelas públicas de códigos e de processos de
licitação e de contratos com pessoa jurídica.
"""

import pytest

from themis_lgpd.reconhecedores.financeiro import _contratacao_publica

VAZAMENTOS = [
    # (texto, trechos que NÃO podem sobrar na saída)
    ("CENTRO DE REFERÊNCIA DE ASSISTÊNCIA SOCIAL\nRELATÓRIO SOCIAL Nº 733/2030 – ACOMPANHAMENTO FAMILIAR",
     ["733/2030"]),
    ("RELATÓRIO DE ACOMPANHAMENTO PSICOSSOCIAL E ESCOLAR Nº 0918/2030-NAPX\nEducando: FULANO", ["0918/2030"]),
    ("A equipe multiprofissional (Relatório nº 561/2030-EMX) recomendou a guarda compartilhada.", ["561/2030"]),
    ("Referência: CRAS Norte – Relatório nº XYZ-QR 4471/2030.", ["4471/2030"]),
    ("Laudo nº 8806/2030-PTC, emitido pelo instituto de perícias, atesta lesão leve.", ["8806/2030"]),
    ("Conforme o laudo psicológico nº 3390/2030, a criança demanda acompanhamento.", ["3390/2030"]),
    ("PARECER MÉDICO-PERICIAL Nº 4.507/2030 – PERÍCIA OFICIAL\nServidora avaliada: FULANA", ["4.507/2030"]),
    ("Investigação nº QW-321/2030\nDeclaração de Óbito nº 61234567-8", ["321/2030", "61234567"]),
    ("Foi emitida a CAT nº 41122334455 e a Comunicação de Acidente de Trabalho nº 2030.5511.204-7.",
     ["41122334455", "2030.5511.204"]),
    ("Procedimento nº PQ-RST 0577/2030 instaurado pelo conselho tutelar.", ["0577/2030"]),
    ("Registrou BO nº 81234/2030 e depois o boletim pela internet (REDS 2030-000123456-001).",
     ["81234/2030", "000123456"]),
    ("Depoimento colhido sob o RAI nº 52.118.907 da delegacia regional.", ["52.118.907"]),
    ("Foi aberta a Sindicância Administrativa Punitiva nº 977/2030 contra o agente.", ["977/2030"]),
    ("AUTO DE INFRAÇÃO AMBIENTAL Nº 7D3K5M2P lavrado contra o proprietário; Termo de Interdição nº HX92Q4T6.",
     ["7D3K5M2P", "HX92Q4T6"]),
    ("Ficou preso em razão do auto de prisão em flagrante nº 6621/2030-DPY.", ["6621/2030"]),
    ("Foi lavrado o Termo Circunstanciado de Ocorrência (TCO) nº 0456/2030 na delegacia.", ["0456/2030"]),
    ("Investigação: QW-322/2030\nNotificante: unidade básica", ["322/2030"]),
    ("Processo GEDOC: SEPX-ADM-2030/55817\nServidora requerente: FULANA", ["2030/55817"]),
    ("Processo SPX: SGA 00071234/2030 – pedido de licença", ["00071234"]),
    ("Prontuário CAPS: KB4-7721/2030\nUsuária acompanhada desde 2029.", ["7721/2030"]),
    ("Prontuário: HXR-5512049 / Prontuário SUAS nº 27.418 / Prontuário prisional nº 553812",
     ["5512049", "27.418", "553812"]),
    ("Psicóloga – CRP 05ª Região nº 31.555 e assistente social – CRESS 6ª Região nº 6.402",
     ["05", "31.555", "6", "6.402"]),
    ("Médica neurologista – CRM-GO 7.115 – RQE 2.208", ["7.115", "2.208"]),
    ("Comissão: FULANO DE TAL (Matr. 071526) e BELTRANA (Matr. 618204).", ["071526", "618204"]),
    ("Fica designada a servidora FULANA, nº funcional 5512873, para compor a comissão.", ["5512873"]),
    ("Chefe do setor – Id. funcional 4419072/01", ["4419072"]),
    ("Nomear BELTRANO, RF 712.384.5/2, para o cargo em comissão.", ["712.384.5"]),
    ("Nomear FULANO DE TAL, CPF ***.418.207-**, para o cargo efetivo", ["418.207"]),
    ("Candidata: FULANA – CPF 071.XXX.XXX-38 – classificada em 3º lugar", ["071.", "-38"]),
    ("Usuário: FULANO   Cartão SUS: 702.4180.3311.5024", ["4180", "3311", "5024"]),
]


@pytest.mark.parametrize("texto,proibidos", VAZAMENTOS)
def test_identificador_em_documento_oficial(anon, texto, proibidos):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


TABELAS = [
    # Colunas de identificador reconhecidas pelo cabeçalho, inclusive com o nome quebrado em duas linhas
    # e com a linha da tabela partida pela extração do texto.
    ("PROFISSIONAL | MATRÍCULA | COREN-SP | PLANTÃO\nFULANA DE\nTAL | 512.338-7 B | 220417-ENF | D\n"
     "BELTRANO | 774.102-9 B | 618330-TE | N\n", ["512.338", "220417", "774.102", "618330"]),
    ("NOME | MASP | LOTAÇÃO\nFULANA | 1.522.418-3 | Superintendência Regional\n", ["1.522.418"]),
    ("Atribuição | Nome | SIAPE\nTitular | Fulana de Tal | 4417203\nSuplente | Beltrano\nde Souza | 6620184\n",
     ["4417203", "6620184"]),
    ("NB | SEGURADO(A) | CPF | VALOR\n741.226.880-3 | FULANA | ***.210.774-** | R$ 1.000,00\n",
     ["741.226.880", "210.774"]),
    ("Nº DE INSCRIÇÃO | CANDIDATO | SITUAÇÃO\n20417733 | FULANO | APROVADO\n", ["20417733"]),
    ("Nome\tCPF\tInscrição imobiliária\tDébito\nFulano\t***.330.512-**\t447120\t512,40\n", ["447120"]),
]


@pytest.mark.parametrize("texto,proibidos", TABELAS)
def test_coluna_de_identificador_em_tabela(anon, texto, proibidos):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


def test_tabela_sem_coluna_de_identificador_nao_e_tarjada(anon):
    """Quantidades, datas e valores de tabelas sem cabeçalho de documento continuam legíveis."""
    texto = "ITEM | DESCRIÇÃO | QUANTIDADE | VALOR\n1 | Cadeira escolar | 12000 | R$ 1.234,00\n"
    assert "12000" in anon.anonimizar(texto).texto


@pytest.mark.parametrize("texto", [
    "em atenção às recomendações do Relatório de Auditoria nº 58/2030, sobre o exercício anterior",
    "conforme o Relatório Anual de Gestão (RAG) nº 12/2030 aprovado pelo conselho",
    "RELATÓRIO DE INSPEÇÃO Nº 102/2030 – OBRAS DA PONTE MUNICIPAL",
    "LAUDO DE AVALIAÇÃO DE IMÓVEL Nº 118/2030 – valor de mercado do terreno",
    "Procedimento licitatório nº 12/2030, na modalidade concorrência.",
    "Relatório: 1.500 atendimentos realizados no ano.",
    "em conformidade com a Resolução CONTRAN nº 619/2016 e a Portaria GM/MS nº 2.436/2017.",
    "a promoção foi publicada no Boletim da Polícia Militar nº 214/2030 e no diário oficial",
    "EDITAL DE NOTIFICAÇÃO Nº 12/2030\n\nA Secretaria de Finanças torna público o lançamento",
    "Unidade notificadora: Hospital Municipal   Código IBGE: 5300108",
    "Enquadramento\nCódigo: 518-51 – Estacionar o veículo em local proibido",
    "Sessões de fisioterapia de 14/03 a 30/05/2030, duas vezes por semana.",
    "Veículo: hatch MODELO-X 150 TURBO, cor prata",
    "Assistente Social – CRESS 6ª Região",
    "O processo seletivo nº 12345/2030 foi publicado pelo Edital nº 02/2030.",
])
def test_numero_publico_continua_legivel(anon, texto):
    r = anon.anonimizar(texto)
    tarjas = [(e.tipo, e.valor) for e in r.tarjadas if e.tipo not in ("NOME", "LOCALIDADE")]
    assert tarjas == [], tarjas


AVISO_LICITACAO = ("PREFEITURA MUNICIPAL\nSECRETARIA DE ADMINISTRAÇÃO\n\nAVISO DE LICITAÇÃO\n"
                   "CONCORRÊNCIA ELETRÔNICA Nº 004/2030\nProcesso nº ADM-CPL-2030/30981\n\n"
                   "OBJETO: Contratação de empresa para reforma de unidades de saúde.")


def test_processo_de_licitacao_continua_legivel(anon):
    """O número do processo de licitação é de divulgação obrigatória (Lei nº 14.133/2021, art. 94)."""
    r = anon.anonimizar(AVISO_LICITACAO)
    assert "ADM-CPL-2030/30981" in r.texto, r.texto


def test_extrato_de_contrato_com_pessoa_natural_tarja_processo(anon):
    """Com CPF no documento, o contrato é com pessoa natural e o processo continua tarjado."""
    texto = ("EXTRATO DO CONTRATO Nº 090/2030\n\nPROCESSO ADMINISTRATIVO: 4410/2030-SECY\n"
             "CONTRATADO: FULANO DE TAL, CPF ***.645.300-**, palestrante.")
    saida = anon.anonimizar(texto).texto
    assert "4410/2030" not in saida, saida


@pytest.mark.parametrize("texto,esperado", [
    (AVISO_LICITACAO, True),
    ("EXTRATO DO TERMO ADITIVO Nº 2 AO CONTRATO Nº 77/2030\n\nPROCESSO: 31.220.507/2030\n"
     "CONTRATADA: Empresa Exemplo Ltda., CNPJ 12.345.678/0001-95", True),
    ("ATA DE JULGAMENTO – PREGÃO PRESENCIAL Nº 008/2030\nProcesso Administrativo nº 1207.008/2030", True),
    # Pedido de acesso em maiúsculas não é título de documento de licitação.
    ("SOLICITO CÓPIA DO PROCESSO 12345/2030 REFERENTE AO PREGÃO ELETRÔNICO 12/2030 DA SECRETARIA DE SAÚDE "
     "E DOS DOCUMENTOS DA EMPRESA VENCEDORA DA LICITAÇÃO", False),
    ("PORTARIA Nº 1.204/2030\n\nRESOLVE conceder licença ao servidor FULANO, Processo SEI nº 00410.002123/2030-11",
     False),
    ("TERMO DE REFERÊNCIA\nContratação de pessoa física para serviço de consultoria\nProcesso nº 12345/2030", False),
])
def test_reconhecimento_de_documento_de_contratacao(texto, esperado):
    assert _contratacao_publica(texto) is esperado
