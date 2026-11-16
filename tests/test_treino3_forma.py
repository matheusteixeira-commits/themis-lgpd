"""Dado pessoal que escapa pela forma do documento: tabelas, formulários, quebras e ruído de digitalização.

Os exemplos são fictícios. Cobrem:

* a normalização do texto (:mod:`themis_lgpd.texto`): hifenização em caixa alta, com "¬" e com espaço
  depois do hífen, número partido depois do hífen, campos em quadrícula, rótulo colado ao valor e zero no
  lugar da letra O, sempre com o mapa de posições até o original;
* o reconhecedor de tabelas (:mod:`themis_lgpd.reconhecedores.tabelas`): colunas tipificadas pelo
  cabeçalho em tabelas alinhadas por espaços, com separador e em bloco, formulários em grade e em bloco;
* as armadilhas: tabelas de itens, de empresas e de estatística, linha de totais, linha de pessoa
  jurídica, formulário de linha única e nome de pessoa dentro de nome de unidade, que ficam legíveis.
"""

import pytest

from themis_lgpd import Anonimizador
from themis_lgpd.catalogo import categoria_de
from themis_lgpd.perfis import ALERTAR, obter_perfil
from themis_lgpd.reconhecedores.tabelas import ReconhecedorTabelas, tipificar
from themis_lgpd.texto import normalizar


def _achados(texto: str) -> list[tuple[str, str]]:
    n = normalizar(texto)
    saida = []
    for d in ReconhecedorTabelas().detectar(n.texto):
        a, b = n.para_original(d.inicio, d.fim)
        saida.append((d.tipo, n.original[a:b]))
    return saida


def _valores(texto: str, tipo: str) -> list[str]:
    return [v for t, v in _achados(texto) if t == tipo]


# --------------------------------------------------------------------------- normalização
def test_hifenizacao_em_caixa_alta_e_mapa():
    n = normalizar("requerente LEOPOLDINO SAMPER QUIN-\nTELA, residente")
    assert "LEOPOLDINO SAMPER QUINTELA," in n.texto
    i = n.texto.index("QUINTELA")
    a, b = n.para_original(i, i + len("QUINTELA"))
    assert n.original[a:b] == "QUIN-\nTELA"


@pytest.mark.parametrize("texto", [
    "DIRETOR-\nGERAL", "registro COREN-\nSP 123456", "o VICE-\nPREFEITO", "Rio-\nGrande", "SEGUNDA-\nFEIRA",
    "parágrafo -\n2 itens", "fim da página-\n\nNOVA",
])
def test_hifen_legitimo_permanece(texto):
    assert normalizar(texto).texto == texto


def test_marca_de_hifenizacao_e_hifen_com_espaco():
    assert normalizar("a usuária Clo¬\ntilde e a técnica Ber- \nnadete").texto == "a usuária Clotilde e a técnica Bernadete"


def test_numero_partido_depois_do_hifen_mantem_o_hifen():
    n = normalizar("CPF 123.456.789-\n09, telefone (61) 97531-\n4321 e placa QWE-\n8R21")
    assert n.texto == "CPF 123.456.789-09, telefone (61) 97531-4321 e placa QWE-8R21"


def test_campo_em_quadricula():
    texto = "NOME COMPLETO\nL E O P O L D I N O   S A M P E R\nCPF\n1 2 3 4 5 6 7 8 9 0 0"
    n = normalizar(texto)
    assert n.texto == "NOME COMPLETO\nLEOPOLDINO SAMPER\nCPF\n12345678900"
    i = n.texto.index("LEOPOLDINO")
    a, b = n.para_original(i, i + len("LEOPOLDINO SAMPER"))
    assert n.original[a:b] == "L E O P O L D I N O   S A M P E R"


@pytest.mark.parametrize("texto", [
    "( X ) AUXÍLIO   (   ) OUTROS", "N  D  N  D  F  F", "alíneas a b c", "PLANTÃO  A  B  C",
])
def test_texto_que_nao_e_quadricula(texto):
    assert normalizar(texto).texto == texto


def test_rotulo_colado_ao_valor():
    n = normalizar("Estudante:LEOPOLDINO SAMPER Turma:B Nasc.:01/02/2015 Tel.:(61)3333-4444")
    assert n.texto == "Estudante: LEOPOLDINO SAMPER Turma: B Nasc.: 01/02/2015 Tel.: (61)3333-4444"
    i = n.texto.index("LEOPOLDINO")
    assert n.original[slice(*n.para_original(i, i + 10))] == "LEOPOLDINO"


@pytest.mark.parametrize("texto", ["às 10:30 de hoje", "em https://exemplo.gov.br/x", "rota fe80::1:2", "C:\\dados"])
def test_dois_pontos_que_nao_sao_rotulo(texto):
    assert normalizar(texto).texto == texto


def test_zero_no_lugar_da_letra_o():
    assert normalizar("MARIETA QUINTEL0S e Leopoldino Sampe0").texto == "MARIETA QUINTELOS e Leopoldino Sampe0"
    assert normalizar("CASIMIRO ARAG0NÊS").texto == "CASIMIRO ARAGONÊS"
    for codigo in ("lote AB12C0D9", "COVID-19", "placa ABC0D12", "B0X"):
        assert normalizar(codigo).texto == codigo


def test_rn_lido_como_m_em_nomes_e_rotulos():
    n = normalizar("o munícipe Sarnuel, filho de rnãe solteira, norne social")
    assert n.texto == "o munícipe Samuel, filho de mãe solteira, nome social"
    i = n.texto.index("Samuel")
    assert n.original[slice(*n.para_original(i, i + 6))] == "Sarnuel"
    for texto in ("o governo e o turno da tarde", "Bernardo e Arnaldo", "NATAL/RN", "o RN e o RS"):
        assert normalizar(texto).texto == texto


# --------------------------------------------------------------------------- tabelas alinhadas por espaços
FOLHA = (
    "RESUMO MENSAL DE PAGAMENTO – 03/2031\n"
    "\n"
    "MATR.   SERVIDOR(A)                FUNÇÃO          VENC.      DESC.      LÍQUIDO\n"
    "                                                   BASE\n"
    "070201  LEOPOLDINO SAMPER QUINTELA AUXILIAR        2.100,00   210,00     1.890,00\n"
    "070377  MARIETA OSTERNE            ASSISTENTE      3.250,10   348,77     2.901,33\n"
    "        PRAXEDES\n"
    "        SOMA DO SETOR                              5.350,10   558,77     4.791,33\n"
)


def test_folha_alinhada_por_espacos():
    achados = _achados(FOLHA)
    assert ("MATRICULA", "070201") in achados and ("MATRICULA", "070377") in achados
    assert ("NOME", "LEOPOLDINO SAMPER QUINTELA") in achados
    assert ("NOME", "MARIETA OSTERNE") in achados and ("NOME", "PRAXEDES") in achados
    assert {"2.100,00", "210,00", "1.890,00", "3.250,10", "348,77", "2.901,33"} <= set(_valores(FOLHA, "VALOR_PESSOAL"))
    # Linha de totais, cargos e a continuação do rótulo ficam de fora.
    assert not {"5.350,10", "558,77", "4.791,33"} & set(_valores(FOLHA, "VALOR_PESSOAL"))
    assert not any(v in ("AUXILIAR", "ASSISTENTE", "BASE") for _, v in achados)


def test_folha_anonimizada(anon):
    saida = anon.anonimizar(FOLHA).texto
    for valor in ("070201", "LEOPOLDINO", "QUINTELA", "PRAXEDES", "2.100,00", "2.901,33"):
        assert valor not in saida
    assert "5.350,10" in saida and "4.791,33" in saida


def test_cabecalho_com_rotulos_colados_e_celula_partida():
    texto = (
        "POS. INSCRIÇÃO     CANDIDATO(A)                  NASCIMENTO   NOTA\n"
        "1º   31000412357   TEODORA LIMEIRA DE            04/05/1988   88,5\n"
        "                   ARAGONÊS VEIGA\n"
        "2º   31000497531   HILDEBRANDO OSTERNE VEIGA     17/11/1979   86,0\n"
    )
    achados = _achados(texto)
    assert ("DOCUMENTO", "31000412357") in achados and ("DOCUMENTO", "31000497531") in achados
    assert ("NOME", "TEODORA LIMEIRA DE") in achados and ("NOME", "ARAGONÊS VEIGA") in achados
    assert ("DATA_NASCIMENTO", "04/05/1988") in achados
    assert not _valores(texto, "VALOR_PESSOAL")


def test_registro_em_duas_linhas():
    texto = (
        "SERVIDOR(A)              SIAPE       FUNÇÃO\n"
        "  LOCALIDADE / DATAS     DIAS        TOTAL (R$)\n"
        "LEOPOLDINO SAMPER        1234567     Motorista\n"
        "  Cidade Alfa 02 a 04    2,5         317,40\n"
        "MARIETA OSTERNE          7654321     Analista\n"
        "  Cidade Beta 05 a 05    0,5         73,85\n"
    )
    achados = _achados(texto)
    assert ("MATRICULA", "1234567") in achados and ("MATRICULA", "7654321") in achados
    assert set(_valores(texto, "VALOR_PESSOAL")) == {"317,40", "73,85"}
    assert ("NOME", "MARIETA OSTERNE") in achados


def test_registro_profissional_e_iniciais():
    texto = (
        "PROFISSIONAL                   COREN-XX     SITUAÇÃO  21 22 23\n"
        "ENFª TEODORA LIMEIRA ARAGONÊS  123.456-ENF  ATIVA     N  D  F\n"
        "TÉC. ENF. CASIMIRO O. VEIGA    654.321-TE   ATIVA     D  N  D\n"
        "\n"
        "PROFISSIONAL          24 25 26  CH\n"
        "ARAGONÊS, T. L.       N  N  F   36\n"
    )
    achados = _achados(texto)
    assert ("NOME", "TEODORA LIMEIRA ARAGONÊS") in achados and ("NOME", "CASIMIRO O. VEIGA") in achados
    assert ("REGISTRO_PROFISSIONAL", "123.456-ENF") in achados
    assert ("NOME", "ARAGONÊS, T. L.") in achados


def test_tabela_de_vacinacao():
    texto = (
        "SEQ  PACIENTE                 D.N.        CARTÃO SUS       VACINA            LOTE\n"
        "01   ZULMIRA PRAXEDES VEIGA   02/03/2030  700000000000001  HEPATITE B D2  LT0001AB\n"
        "02   CASIMIRO ARAGONÊS        11/12/2029  700000000000002  —  LT0002CD\n"
    )
    achados = _achados(texto)
    assert ("DATA_NASCIMENTO", "02/03/2030") in achados
    assert ("CNS", "700000000000001") in achados
    assert ("SAUDE", "HEPATITE B D2") in achados
    assert not any(v.startswith("LT0") for _, v in achados)
    assert len(_valores(texto, "SAUDE")) == 1


def test_formulario_em_grade_com_quadricula(anon):
    texto = (
        "1. QUALIFICAÇÃO DO SOLICITANTE\n"
        "NOME COMPLETO\n"
        "Z E N Ó B I A   L I M E I R A   V E I G A\n"
        "CPF                                   NASCIMENTO\n"
        "1 2 3 4 5 6 7 8 9 0 9                0 4 0 5 1 9 8 8\n"
        "ENDEREÇO\n"
        "R U A   D O S   I P Ê S   1 0   F U N D O S\n"
    )
    achados = _achados(texto)
    assert ("NOME", "Z E N Ó B I A   L I M E I R A   V E I G A") in achados
    assert ("DATA_NASCIMENTO", "0 4 0 5 1 9 8 8") in achados
    assert ("ENDERECO", "R U A   D O S   I P Ê S   1 0   F U N D O S") in achados
    saida = anon.anonimizar(texto).texto
    assert "Z E N Ó B I A" not in saida and "0 4 0 5 1 9 8 8" not in saida and "I P Ê S" not in saida


# --------------------------------------------------------------------------- tabelas com separador
def test_csv_com_ponto_e_virgula():
    texto = (
        "SEQ;BOLSISTA;CPF;VALOR DA BOLSA;BCO;AG.;C/C\n"
        '1;"SAMPER, LEOPOLDINO QUINTELA";***.123.456-**;652,30;001;1234-5;97531-4\n'
        '2;"OSTERNE, MARIETA PRAXEDES";***.654.321-**;718,90;104;4321-X;51972-3\n'
        "SOMA;;;1371,20;;;\n"
    )
    achados = _achados(texto)
    assert ("NOME", "SAMPER, LEOPOLDINO QUINTELA") in achados
    assert ("CPF", "***.123.456-**") in achados
    assert set(_valores(texto, "VALOR_PESSOAL")) == {"652,30", "718,90"}
    assert {"1234-5", "97531-4", "4321-X", "51972-3"} <= set(_valores(texto, "CONTA_BANCARIA"))
    assert not any(v in ("001", "104") for _, v in achados)


def test_tabela_com_barra_e_coluna_de_raca():
    texto = "Titular | Vínculo | Etnia | NIS\nLEOPOLDINO SAMPER | sobrinho | parda | 123.45678.90-1\n"
    achados = _achados(texto)
    assert ("ORIGEM_RACIAL", "parda") in achados and ("PIS", "123.45678.90-1") in achados


# --------------------------------------------------------------------------- blocos
def test_colunas_em_bloco():
    texto = (
        "CONTEMPLADOS NA SEGUNDA CHAMADA\n"
        "\n"
        "SEQ.\n01\n02\n"
        "NOME DO TITULAR\nLEOPOLDINO SAMPER QUINTELA\nMARIETA OSTERNE PRAXEDES\n"
        "NIS\n123.45678.90-1\n234.56789.01-2\n"
        "BENEFÍCIO MENSAL\nR$ 250,00\nR$ 310,00\n"
    )
    achados = _achados(texto)
    assert ("NOME", "LEOPOLDINO SAMPER QUINTELA") in achados and ("NOME", "MARIETA OSTERNE PRAXEDES") in achados
    assert set(_valores(texto, "PIS")) == {"123.45678.90-1", "234.56789.01-2"}
    assert set(_valores(texto, "VALOR_PESSOAL")) == {"R$ 250,00", "R$ 310,00"}


def test_formulario_em_bloco():
    texto = (
        "1. LOCATÁRIO\n"
        "Nome:\nCPF:\nTelefone:\n"
        "2. IMÓVEL\n"
        "Bairro:\nValor do aluguel (R$):\n"
        "Assumo a responsabilidade pelo conteúdo deste formulário eletrônico.\n"
        "\n"
        "LEOPOLDINO SAMPER QUINTELA\n123.456.789-09\n(61) 97531-4321\nVila Alfa\n1.237,55\n"
    )
    achados = _achados(texto)
    assert ("NOME", "LEOPOLDINO SAMPER QUINTELA") in achados and ("CPF", "123.456.789-09") in achados
    assert ("TELEFONE", "(61) 97531-4321") in achados and ("VALOR_PESSOAL", "1.237,55") in achados
    assert not any(v == "Vila Alfa" for _, v in achados)


def test_formulario_em_bloco_com_contagem_diferente_nao_atribui():
    texto = "Nome:\nCPF:\nTelefone:\n\nLEOPOLDINO SAMPER QUINTELA\n123.456.789-09\n"
    assert _achados(texto) == []


# --------------------------------------------------------------------------- armadilhas
@pytest.mark.parametrize("texto", [
    # Tabela de itens: sem coluna de pessoa.
    "ITEM   DESCRIÇÃO            QUANTIDADE   VALOR (R$)\n01     Cadeira giratória    10           4.500,00\n",
    # Tabela de empresas.
    "EMPRESA                 CNPJ                   VALOR\nAlfa Comércio Ltda      12.345.678/0001-90     10.433,20\n",
    # Estatística.
    "Município | Casos | Óbitos\nCidade Alfa | 1.713 | 2\nCidade Beta | 486 | 0\n",
    # Rótulo com ano: contagem de matrículas, não matrícula funcional.
    "Unidade escolar | Matrícula 2031 | IDEB\nEscola Alfa | 2.093 | 6,3\n",
    # Formulário de linha única, com rótulo e valor na mesma célula.
    "Cor/raça: preta   Instrução: superior\nNascimento: 01/02/1990   Sexo: F\n",
    # Opções de formulário não são cabeçalho.
    "VÍNCULO (X) SERVIDOR  ( ) PENSIONISTA\nMATR 46813   FUNÇÃO AGENTE   SETOR SEDE\n",
    # Edital: cargo e remuneração fixada.
    "FUNÇÃO | VAGAS | LOTAÇÃO | REMUNERAÇÃO\nEnfermeiro | 2 | Hospital Municipal | R$ 5.120,00\n",
])
def test_tabelas_sem_dado_pessoal(texto):
    assert _achados(texto) == []


def test_linha_de_pessoa_juridica_em_tabela_de_pessoas():
    texto = (
        "PLACA     AIT         PROPRIETÁRIO                  VALOR (R$)\n"
        "QWE8R21   X1234567    LEOPOLDINO SAMPER QUINTELA    137,92\n"
        "RTY5U43   X7654321    TRANSPORTES BETA LTDA         873,19\n"
    )
    achados = _achados(texto)
    assert ("VALOR_PESSOAL", "137,92") in achados and ("PROTOCOLO", "X1234567") in achados
    assert not any(v in ("873,19", "X7654321", "RTY5U43") or "BETA" in v for _, v in achados)


def test_cabecalho_repetido_nao_vira_nome():
    texto = (
        "NOME                    MATRÍCULA   FUNÇÃO\n"
        "LEOPOLDINO SAMPER       123.456-7   Motorista\n"
        "NOME                    MATRÍCULA   FUNÇÃO\n"
        "MARIETA OSTERNE         234.567-8   Servidor\n"
    )
    achados = _achados(texto)
    assert ("NOME", "MARIETA OSTERNE") in achados
    assert not any(v in ("NOME", "Servidor", "Motorista") for _, v in achados)


def test_texto_corrido_encerra_a_tabela():
    texto = (
        "NOME                    MATRÍCULA\n"
        "LEOPOLDINO SAMPER       123.456-7\n"
        "Os servidores acima deverão apresentar a documentação com os originais na sala de protocolo.\n"
    )
    assert _achados(texto) == [("NOME", "LEOPOLDINO SAMPER"), ("MATRICULA", "123.456-7")]


def test_nome_de_pessoa_em_coluna_de_lotacao_fica_legivel(anon):
    texto = (
        "Nº   NOME COMPLETO            MATRÍCULA   ESCOLA / LOTAÇÃO\n"
        "01   LEOPOLDINO SAMPER        123.456-7   EE PROFESSORA ALZIRA\n"
        "                                          BOTELHO GUSMÕES\n"
        "02   MARIETA OSTERNE          234.567-8   EE PROFESSORA ALZIRA\n"
        "                                          BOTELHO GUSMÕES\n"
    )
    r = anon.anonimizar(texto)
    assert "LEOPOLDINO" not in r.texto and "123.456-7" not in r.texto
    assert r.texto.count("ALZIRA") == 2 and r.texto.count("BOTELHO GUSMÕES") == 2


def test_tipo_de_unidade_e_sinalizado():
    assert categoria_de("UNIDADE_INSTITUCIONAL").codigo == "INSTITUCIONAL"
    assert obter_perfil("lai").regra("INSTITUCIONAL") == ALERTAR


@pytest.mark.parametrize("rotulo,tipo", [
    ("NOME DO(A) SEGURADO(A)", "NOME"), ("SERVIDOR(A)", "NOME"), ("MÃE/RESPONSÁVEL", "NOME"),
    ("MATR.", "MATRICULA"), ("Nº FUNCIONAL", "MATRICULA"), ("COREN-SP", "REGISTRO_PROFISSIONAL"),
    ("DT. NASC.", "DATA_NASCIMENTO"), ("DN", "DATA_NASCIMENTO"), ("AG.", "CONTA_BANCARIA"),
    ("VALOR (R$)", "VALOR_PESSOAL"), ("LÍQUIDO", "VALOR_PESSOAL"), ("NE / OB", "PROTOCOLO"),
    ("IMUNOBIOLÓGICO/DOSE", "SAUDE"), ("Nome do programa", ""), ("Unidade escolar", ""), ("Matrícula 2031", ""),
    ("Valor unitário", ""), ("Categoria profissional", ""),
])
def test_tipificacao_do_cabecalho(rotulo, tipo):
    assert tipificar(rotulo).tipo == tipo


def test_anonimizador_sem_modelo_tambem_reconhece_tabelas():
    anon = Anonimizador(usar_ner=False)
    saida = anon.anonimizar(FOLHA).texto
    assert "070201" not in saida and "1.890,00" not in saida and "5.350,10" in saida
