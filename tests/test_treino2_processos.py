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
    ("RELATÓRIO SOCIAL Nº 052/2031 – EQUIPE VOLANTE\n\n1. IDENTIFICAÇÃO DA FAMÍLIA", ["052/2031"]),
    ("RELATÓRIO DE CONDUTA E AVALIAÇÃO PSICOSSOCIAL Nº 0444/2031-UPX\n\nFinalidade: livramento condicional.",
     ["0444/2031"]),
    ("Conforme o estudo da equipe técnica do juízo (Relatório nº 377/2031-ETJ), a moradia é adequada.",
     ["377/2031"]),
    ("Encaminhamento: CREAS Centro – Relatório nº ABC-XY 0912/2031.", ["0912/2031"]),
    ("LAUDO DE EXAME DE CORPO DE DELITO\nLaudo nº 4410/2031-PCX\nRequisição: Delegacia de Polícia.", ["4410/2031"]),
    ("A perícia oficial, no laudo médico pericial nº 2731/2031, concluiu pela incapacidade.", ["2731/2031"]),
    ("PARECER MÉDICO-PERICIAL Nº 6.218/2031 – JMX/GEPX\n\nPericiada: FULANA", ["6.218/2031"]),
    ("Investigação nº QW-321/2031\nDeclaração de Óbito nº 61234567-8", ["321/2031", "61234567"]),
    ("Foi emitida a CAT nº 41122334455 e a Comunicação de Acidente de Trabalho nº 2031.5511.204-7.",
     ["41122334455", "2031.5511.204"]),
    ("Procedimento nº XY-ABC 0577/2031\n\nÀ Secretaria Municipal de Educação", ["0577/2031"]),
    ("A vítima registrou BO nº 81234/2031 e, depois, a ocorrência pela internet (REDS 2031-000123456-001).",
     ["81234/2031", "000123456"]),
    ("TERMO DE DECLARAÇÕES\n\nRAI nº 52.118.907 – Inquérito Policial nº 211/2031-DPX", ["52.118.907", "211/2031"]),
    ("A Corregedoria instaurou a Sindicância Administrativa Investigatória nº 433/2031 para apurar o caso.",
     ["433/2031"]),
    ("AUTO DE INFRAÇÃO Nº 7D3K5M2P\nTermo de Embargo nº HX92Q4T6. Termo de Apreensão nº LP38R7W2.",
     ["7D3K5M2P", "HX92Q4T6", "LP38R7W2"]),
    ("A materialidade consta do auto de prisão em flagrante nº 0815/2031-DPX e do laudo pericial.", ["0815/2031"]),
    ("Foi lavrado o Termo Circunstanciado de Ocorrência (TCO) nº 0456/2031 na delegacia.", ["0456/2031"]),
    ("Investigação: QW-322/2031\nNotificante: unidade básica", ["322/2031"]),
    ("Processo SIGADOC: SEDX-PRO-2031/20417\n\nServidor avaliado: FULANO", ["2031/20417"]),
    ("Processo SGPe: SAD 00071234/2031\nRequerente: FULANA", ["00071234"]),
    ("Prontuário CAPS: AD7-0442/2031\nUsuário: FULANO", ["0442/2031"]),
    ("Prontuário: HXR-5512049 / Prontuário SUAS nº 27.418 / Prontuário prisional nº 553812", ["5512049", "27.418",
                                                                                              "553812"]),
    ("Assistente Social – CRESS 13ª Região nº 6.402", ["13", "6.402"]),
    ("Médica neurologista – CRM-GO 7.115 – RQE 2.208", ["7.115", "2.208"]),
    ("Presidente: FULANO DE TAL – Matr. 071526 / Membro: BELTRANA – Matr. 618204", ["071526", "618204"]),
    ("CONCEDER à servidora FULANA, nº funcional 5512873, vínculo 01, ocupante do cargo", ["5512873"]),
    ("Diretor da Unidade – Id. funcional 4419072/01", ["4419072"]),
    ("Exonerar o senhor FULANO, RF 712.384.5/2, do cargo de Assessor", ["712.384.5"]),
    ("Exonerar FULANO DE TAL, CPF ***.418.207-**, do cargo comissionado", ["418.207"]),
    ("Matrícula: 7712054   Vínculo: 1\nCPF: 071.XXX.XXX-38\nCargo: Professor", ["071.", "-38"]),
    ("Paciente: FULANO   CNS: 702.4180.3311.5024", ["4180", "3311", "5024"]),
]


@pytest.mark.parametrize("texto,proibidos", VAZAMENTOS)
def test_identificador_em_documento_oficial(anon, texto, proibidos):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


TABELAS = [
    # Colunas de identificador reconhecidas pelo cabeçalho, inclusive com o nome quebrado em duas linhas
    # e com a linha da tabela partida pela extração do texto.
    ("SERVIDOR(A) | MATRÍCULA | COREN-AM | TURNO\nFULANA DE\nTAL | 512.338-7 A | 220417-ENF | SD\n"
     "BELTRANO | 774.102-9 A | 618330-TE | SN\n", ["512.338", "220417", "774.102", "618330"]),
    ("MASP | NOME | CARGO | DESTINO\n1.522.418-3 | FULANA | PEB | Escola Estadual\n", ["1.522.418"]),
    ("Função | Servidor(a) | SIAPE\nGestora | Fulana de Tal | 4417203\nFiscal | Beltrano\nde Souza | 6620184\n",
     ["4417203", "6620184"]),
    ("NB | BENEFICIÁRIO(A) | CPF | DIB\n741.226.880-3 | FULANA | ***.210.774-** | 10/02/2031\n",
     ["741.226.880", "210.774"]),
    ("INSCRIÇÃO | NOME | CARGO | RESULTADO\n20417733 | FULANO | Agente | DEFERIDO\n", ["20417733"]),
    ("Contribuinte\tCPF\tInscrição municipal\tValor devido (R$)\nFulano\t***.330.512-**\t447120\t512,40\n",
     ["447120"]),
]


@pytest.mark.parametrize("texto,proibidos", TABELAS)
def test_coluna_de_identificador_em_tabela(anon, texto, proibidos):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


def test_tabela_sem_coluna_de_identificador_nao_e_tarjada(anon):
    """Datas, valores e códigos de tabelas sem cabeçalho de documento continuam legíveis."""
    texto = "ITEM | DESCRIÇÃO | QUANTIDADE | VALOR\n1 | Cadeira escolar | 12000 | R$ 1.234,00\n"
    assert "12000" in anon.anonimizar(texto).texto


@pytest.mark.parametrize("texto", [
    "considerando as constatações do Relatório de Auditoria nº 31/2031, relativo ao exercício",
    "conforme o Relatório Anual de Gestão (RAG) nº 12/2031 aprovado pelo conselho",
    "Relatório: 1.500 atendimentos realizados no ano.",
    "RELATÓRIO DE FISCALIZAÇÃO Nº 044/2031 – GEOBR\n\nContrato de obra rodoviária",
    "LAUDO DE AVALIAÇÃO DE IMÓVEL Nº 118/2031 – valor de mercado do terreno",
    "Procedimento licitatório nº 12/2031, na modalidade concorrência.",
    "nos termos da Resolução CONTRAN nº 918/2031 e da Portaria GM/MS nº 1.119/2031.",
    "conforme publicado no Boletim do Comando-Geral nº 37/2031, e recebeu ajuda de custo",
    "EDITAL DE NOTIFICAÇÃO Nº 07/2031\n\nO Diretor do Departamento de Receita torna público",
    "Município de notificação: Fulanópolis   Código IBGE: 1300607",
    "INFRAÇÃO\nCódigo: 745-50 – Transitar em velocidade superior à máxima permitida",
    "Atendimento ambulatorial de 02/06 a 29/08/2031, três vezes por semana.",
    "Marca/modelo: VW/T-CROSS 200 TSI   Cor: branca",
    "Assistente Social – CRESS 13ª Região",
    "O processo seletivo nº 12345/2031 foi publicado pelo Edital nº 02/2031.",
])
def test_numero_publico_continua_legivel(anon, texto):
    r = anon.anonimizar(texto)
    tarjas = [(e.tipo, e.valor) for e in r.tarjadas if e.tipo not in ("NOME", "LOCALIDADE")]
    assert tarjas == [], tarjas


AVISO_LICITACAO = ("GOVERNO DO ESTADO\nSECRETARIA DE ESTADO DE EDUCAÇÃO\n\nAVISO DE LICITAÇÃO\n"
                   "PREGÃO ELETRÔNICO Nº 031/2031 – SISTEMA DE REGISTRO DE PREÇOS\n"
                   "Processo nº SEDX-PRO-2031/18442\n\nOBJETO: Registro de preços para aquisição de mobiliário.")


def test_processo_de_licitacao_continua_legivel(anon):
    """O número do processo de licitação é de divulgação obrigatória (Lei nº 14.133/2021, art. 94)."""
    r = anon.anonimizar(AVISO_LICITACAO)
    assert "SEDX-PRO-2031/18442" in r.texto, r.texto


def test_extrato_de_contrato_com_pessoa_natural_tarja_processo(anon):
    """Com CPF no documento, o contrato é com pessoa natural e o processo continua tarjado."""
    texto = ("EXTRATO DO CONTRATO Nº 027/2031\n\nPROCESSO ADMINISTRATIVO: 6768/2031-SECX\n"
             "CONTRATADA: FULANA DE TAL, CPF ***.982.121-**, artista popular.")
    saida = anon.anonimizar(texto).texto
    assert "6768/2031" not in saida, saida


@pytest.mark.parametrize("texto,esperado", [
    (AVISO_LICITACAO, True),
    ("EXTRATO DO CONVÊNIO Nº 31.207/2031\n\nPROCESSO: 57.000.418/2031\nPARTÍCIPES: Estado e Município, "
     "CNPJ 12.345.678/0001-95", True),
    ("ATA DA SESSÃO PÚBLICA – PREGÃO ELETRÔNICO Nº 019/2031\nProcesso Administrativo nº 0805.019/2031", True),
    # Pedido de acesso em maiúsculas não é título de documento de licitação.
    ("SOLICITO CÓPIA DO PROCESSO 12345/2031 REFERENTE AO PREGÃO ELETRÔNICO 12/2031 DA SECRETARIA DE SAÚDE "
     "E DOS DOCUMENTOS DA EMPRESA VENCEDORA DA LICITAÇÃO", False),
    ("PORTARIA Nº 1.204/2031\n\nRESOLVE conceder licença ao servidor FULANO, Processo SEI nº 00410.002123/2031-11",
     False),
    ("TERMO DE REFERÊNCIA\nContratação de pessoa física para serviço de consultoria\nProcesso nº 12345/2031", False),
])
def test_reconhecimento_de_documento_de_contratacao(texto, esperado):
    assert _contratacao_publica(texto) is esperado
