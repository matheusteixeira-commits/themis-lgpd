"""Nomes de pessoas em documentos oficiais: recall em atos, tabelas e assinaturas; precisão em nomes
de instituições, municípios e empresas.

Portarias, despachos, escalas, laudos e relatórios trazem nomes em CAIXA ALTA após rótulos de campo
("Membro:", "Periciada:") e papéis ("a servidora FULANA"), antes de identificadores ("FULANO,
matrícula"), em blocos de assinatura (nome sobre o cargo) e em células de tabela, inclusive com
sobrenomes de imigrantes e indígenas fora das listas, iniciais de crianças e nomes partidos por quebra
de linha. Em sentido inverso, o nome que homenageia alguém num órgão, escola ou unidade de saúde, o
município com nome de pessoa e a razão social continuam legíveis. Todos os exemplos são fictícios.
"""

import pytest

from themis_lgpd.reconhecedores.nomes import ReconhecedorNomesContexto, contexto_nao_pessoal


def _saida(anon, texto):
    return anon.anonimizar(texto).texto


# Nome, ou partes dele, que não pode ficar visível.
OCULTOS = [
    # Rótulo de campo com sobrenomes fora das listas
    ("Membro: YURIKO AMAMIYA OKUBO – Matr. 381927", ["YURIKO", "AMAMIYA", "OKUBO"]),
    ("Periciado: NADIM CHAHINE BOUSTANI\nCPF: 529.982.247-25", ["NADIM", "CHAHINE", "BOUSTANI"]),
    ("Nome: TOMOKO WATANUKI HIRAYAMA\nRG: 12.345.678-9", ["TOMOKO", "WATANUKI", "HIRAYAMA"]),
    ("Recorrente: Ivoneide Tabosa Quixadá\nCargo: Agente Comunitário de Saúde", ["Ivoneide", "Tabosa", "Quixadá"]),
    # Papel ou ato de pessoal antes do nome
    ("Instaurar processo em face do servidor GUNTHER VOGELSANG KRAMBECK, matrícula nº 7788123.",
     ["GUNTHER", "VOGELSANG", "KRAMBECK"]),
    ("Conceder licença à servidora ODALÉIA MATSUBARA ESCOBAR, nº funcional 99812.", ["ODALÉIA", "MATSUBARA", "ESCOBAR"]),
    ("Exonerar, a pedido, a senhora RAJA ZAIDAN BITTENCOURT, RF 112.334.5/1, do cargo.", ["RAJA", "ZAIDAN"]),
    ("O veículo era conduzido por EDIVALDO PIRAJÁ TOSCANO, que não portava habilitação.",
     ["EDIVALDO", "PIRAJÁ", "TOSCANO"]),
    # Nome antes de identificador, idade ou cargo
    ("Notificação nº 1234\nIgor Wachowski Pereira, sexo masculino, 15 anos, estudante.", ["Wachowski"]),
    ("Presidente: ODILON KAWAKAMI RIBAS\nRELATORA: SUZETE TAKAHARA BENTES – Matrícula 33.441-2",
     ["KAWAKAMI", "TAKAHARA", "BENTES"]),
    # Bloco de assinatura: nome sobre o cargo
    ("Publique-se.\n\nHELMUT VOGELSANG BRÜGGEMANN\nSuperintendente de Administração", ["VOGELSANG", "BRÜGGEMANN"]),
    ("Publique-se.\n\nEnf.ª ROSALVA BENTES QUARESMA\nResponsável Técnica de Enfermagem", ["ROSALVA", "QUARESMA"]),
    # Célula de tabela em linha com CPF ou matrícula
    ("Nº | NOME | CPF\n3º | ELIANDRO RIBAMAR TUPINAMBÁ | ***.123.456-**", ["RIBAMAR", "TUPINAMBÁ"]),
    ("Matrícula | Nome | Cargo\n10293847 | CLEUZIMAR APARECIDO FRAGOSO | Agente Administrativo",
     ["CLEUZIMAR", "FRAGOSO"]),
    ("Contribuinte\tCPF\tValor\nNagib Rahme Salomão\t529.982.247-25\t812,40", ["Nagib", "Rahme"]),
    # Nome partido por quebra de linha
    ("SERVIDOR(A) | MATRÍCULA\nOSMARINA QUEIROGA\nTAVEIRA LUSTOSA | 456.789-1 A", ["OSMARINA", "TAVEIRA", "LUSTOSA"]),
    ("Exonerar GUMERCINDO PAIVA DE\nALBUQUERQUE, CPF ***.123.456-**, do cargo.", ["GUMERCINDO", "ALBUQUERQUE"]),
    ("NOME: ADALGISO FRANÇA TEIXEIRA\nNETO\nCPF: 529.982.247-25", ["ADALGISO", "NETO"]),
    ("Fiscal do contrato | Wesley Barbosa\nde Albuquerque | 6283517", ["Wesley", "Albuquerque"]),
    # Iniciais e nomes com inicial no meio
    ("Filhos: P.R.S., 8 anos; L.M.S., 5 anos.", ["P.R.S", "L.M.S"]),
    ("Alimentandos: R. T. M. S. e L. V. P. N., menores.", ["R. T. M. S", "L. V. P. N"]),
    ("As servidoras A. C. e B. D. confirmaram o fato.", ["A. C", "B. D"]),
    ("Interessada: Ivanilde K. Sarmento", ["Ivanilde", "K. Sarmento"]),
    # Prenome que também é palavra comum, dentro do nome
    ("Mãe: MARIA DA GLÓRIA PIMENTEL\nPai: não declarado", ["GLÓRIA", "PIMENTEL"]),
    # Apelidos
    ("Foi denunciado Josenildo Carvalho Sales, vulgo \"Tatu Bola\", pelo crime.", ["Tatu Bola"]),
    ("Um homem conhecido apenas como Baixinho ameaçou os moradores.", ["Baixinho"]),
    # Dois nomes coordenados após rótulo
    ("Requeridos: JOVELINA SANTOS ARRUDA e EPAMINONDAS KRÜGER VALADÃO", ["EPAMINONDAS", "KRÜGER", "VALADÃO"]),
    # Cargo antes do nome
    ("Requerimento de autoria do Vereador Joaquim Tavares Siqueira sobre a obra.", ["Joaquim Tavares Siqueira"]),
]


@pytest.mark.parametrize("texto,proibidos", OCULTOS)
def test_nomes_em_documentos_oficiais_sao_tarjados(anon, texto, proibidos):
    saida = _saida(anon, texto)
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


# Trecho público que precisa continuar legível.
LEGIVEIS = [
    # Unidade, escola, hospital, prêmio e programa com nome de pessoa
    ("Encaminhada à Unidade Básica de Saúde Doutor Anísio Cavalcanti Brandão para curativo.",
     "Unidade Básica de Saúde Doutor Anísio Cavalcanti Brandão"),
    ("HOSPITAL REGIONAL DR. AMÉRICO FONTENELE LIMA\nServiço de Arquivo Médico", "DR. AMÉRICO FONTENELE LIMA"),
    ("Lotação: EE Professora Zuleide Matos Arruda", "Zuleide Matos Arruda"),
    ("Recolhido à Penitenciária Estadual Joaquim Barreto Pires desde 2024.", "Joaquim Barreto Pires"),
    ("Encaminhe-se ao Centro de Referência Dandara Moreira Lima.", "Dandara Moreira Lima"),
    ("Fica instituído o Prêmio Professora Carmelita Rocha de Boas Práticas.", "Carmelita Rocha"),
    ("Atendida na UBS Dona Benedita Sales Cordeiro.", "Benedita Sales Cordeiro"),
    ("Escola Municipal Professora Iracilda Maria Vasconcelos", "Iracilda Maria Vasconcelos"),
    # Município com nome de pessoa
    ("Teotônio Vilela, 12 de maio de 2025.", "Teotônio Vilela"),
    ("A equipe atenderá em Antônio Prado na próxima semana.", "Antônio Prado"),
    ("Município de residência: Fernando Pedroza", "Fernando Pedroza"),
    ("Superintendência Regional de Ensino de Carlos Chagas", "Carlos Chagas"),
    ("As remessas seguirão para Floriano Peixoto, Erechim e Bernardino de Campos.", "Floriano Peixoto"),
    ("EE Doutor Hilário Moura – Luís Eduardo Magalhães", "Luís Eduardo Magalhães"),
    # Razão social
    ("A Panificadora Juvêncio Mota Ltda. venceu o lote 3.", "Juvêncio Mota"),
    # Cabeçalhos e cargos sob o nome
    ("PREFEITURA DE GOVERNADOR VALADARES\nSecretaria Municipal de Saúde\n\nOfício nº 12/2025",
     "PREFEITURA DE GOVERNADOR VALADARES"),
    ("Publique-se.\n\nMARCELINO TEIXEIRA ROCHA\nSuperintendente de Recursos Humanos", "Superintendente de Recursos Humanos"),
    # Siglas com pontos e de corporação
    ("Contrato com o Banco do Brasil S.A. para a U.E. Monte Alegre.", "S.A."),
    ("Foi ouvido o Sargento PM Gildásio Moura Teles.", "PM"),
    # Cargo e classe funcional antes da matrícula
    ("ocupante do cargo de Analista Ambiental, Classe B, Padrão III, matrícula nº 0061482-3", "Padrão III"),
    ("ocupante do cargo de Operador de Máquinas, matrícula nº 4455661", "Operador de Máquinas"),
    # Tabela de materiais com código numérico
    ("Item | Descrição | Código\n03 | FEIJÃO CARIOCA | 456789\n04 | CANETA AZUL | 456790", "FEIJÃO CARIOCA"),
    # Rótulo seguido de órgão
    ("Membro: Comissão Permanente de Licitação", "Comissão Permanente de Licitação"),
]


@pytest.mark.parametrize("texto,visivel", LEGIVEIS)
def test_trechos_publicos_com_nomes_ficam_legiveis(anon, texto, visivel):
    saida = _saida(anon, texto)
    assert visivel in saida, f"{visivel!r} deveria ficar visível em: {saida!r}"


def test_cargo_na_linha_seguinte_nao_entra_no_nome(anon):
    texto = ("Atenciosamente,\n\nRosicleide Amaral Fontes\nTécnica de Enfermagem da Estratégia Saúde da Família\n"
             "COREN-PB 123.456")
    saida = _saida(anon, texto)
    assert "Rosicleide" not in saida and "Fontes" not in saida
    assert "Estratégia Saúde da Família" in saida


def test_sargento_e_nome_seguinte(anon):
    saida = _saida(anon, "Foi ouvido o Sargento PM Gildásio Moura Teles.")
    assert "Gildásio" not in saida and "Teles" not in saida


def test_dois_genitores_sao_duas_pessoas(anon):
    texto = "filha de Raimunda Pinheiro Lustosa e de Gerson Albuquerque Mendes, residente em Teresina."
    nomes = [e.valor for e in anon.analisar(texto) if e.tipo == "NOME"]
    assert "Raimunda Pinheiro Lustosa" in nomes and "Gerson Albuquerque Mendes" in nomes


@pytest.mark.parametrize("texto", [
    "A nota foi publicada no D.O.U. de ontem.",
    "Consulte o C.P.F. no cadastro.",
    "Banco do Brasil S.A.",
    "Ver P.S. no fim da carta.",
])
def test_siglas_com_pontos_nao_sao_iniciais(texto):
    assert not [d for d in ReconhecedorNomesContexto().detectar(texto) if d.origem == "nomes:iniciais"]


def test_duas_iniciais_sem_contexto_pessoal_nao_sao_tarjadas():
    texto = "O documento N.B. menciona a regra."
    assert not [d for d in ReconhecedorNomesContexto().detectar(texto) if d.origem == "nomes:iniciais"]


@pytest.mark.parametrize("texto,nome", [
    ("Unidade Básica de Saúde da Família Doutor Anísio Brandão", "Anísio"),
    ("HOSPITAL DE CLÍNICAS AMÉRICO FONTENELE", "AMÉRICO"),
    ("Rua Doutor Manoel Pereira Lustosa, 45", "Pereira"),
    ("CRAS Irmã Benedita", "Benedita"),
])
def test_contexto_institucional(texto, nome):
    assert contexto_nao_pessoal(texto, texto.index(nome))


@pytest.mark.parametrize("texto,nome", [
    ("O Médico Perito Dr. Anísio Brandão examinou a paciente.", "Anísio"),
    ("Juiz de Direito Dr. Américo Fontenele", "Américo"),
    ("encaminhado ao Hospital Regional, o paciente José Lustosa", "José"),
])
def test_cargo_antes_do_titulo_e_pessoa(texto, nome):
    assert not contexto_nao_pessoal(texto, texto.index(nome))
