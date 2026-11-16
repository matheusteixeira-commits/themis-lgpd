"""Quase-identificadores: função somada ao posto, ao turno, à data ou à circunstância do encontro.

"A atendente do guichê 6 no turno da tarde" identifica uma pessoa sem citar o nome. No perfil LAI a
descrição é sinalizada para revisão; nos perfis de ouvidoria e de educação, tarjada. A função citada
em abstrato ("o servidor do plantão noturno deverá…") ou em uso adjetivo ("nota fiscal") não é
sinalizada, para não sobrecarregar o revisor.
"""

import pytest

from themis_lgpd import Anonimizador


def _alertas(anon, texto):
    return [e.valor for e in anon.analisar(texto) if e.tipo == "QUASE_IDENTIFICADOR" and e.acao == "alertar"]


@pytest.mark.parametrize("texto,trecho", [
    # Posto de atendimento identificado e dia da semana
    ("Reclamo da recepcionista do guichê 6 no turno da tarde de quinta-feira.",
     "recepcionista do guichê 6 no turno da tarde de quinta-feira"),
    # Oração relativa que narra o encontro, com horário
    ("O porteiro que estava na entrada às 22h40 não registrou a visita.", "porteiro que estava na entrada às 22h40"),
    # Linha de ônibus e horário, separados por vírgula
    ("Quero o nome do motorista da linha 731, que passou às 7h15 no ponto.",
     "motorista da linha 731, que passou às 7h15 no ponto"),
    # Data por extenso e numérica
    ("Fui atendido pela farmacêutica da unidade central na manhã de 03/09/2024.",
     "farmacêutica da unidade central na manhã de 03/09/2024"),
    # Função única
    ("A única intérprete de Libras da regional faltou.", "única intérprete de Libras da regional"),
    # Descrição do próprio requerente, com período de anos
    ("Trabalhei como merendeira da escola no turno da manhã entre 2016 e 2019.",
     "merendeira da escola no turno da manhã entre 2016 e 2019"),
    # Encontro narrado sem data
    ("O técnico que fez a vistoria no meu sítio não deixou o laudo.", "técnico que fez a vistoria no meu sítio"),
    # Posto fixo (portão, guichê, balcão, guarita)
    ("Peço a identificação do vigilante do portão lateral.", "vigilante do portão lateral"),
    # Rótulo de formulário
    ("Servidor envolvido: atendente do balcão 2 na sexta-feira.", "atendente do balcão 2 na sexta-feira"),
    # "Segurança" no masculino designa a pessoa
    ("Fui barrado pelo segurança da plataforma 3 ontem à noite.", "segurança da plataforma 3 ontem à noite"),
    # Indicação de responsável
    ("Solicito o nome do engenheiro responsável pela obra da praça.", "engenheiro responsável pela obra da praça"),
    # Texto em caixa alta
    ("O SUPERVISOR DO TURNO DA NOITE NÃO ME ATENDEU.", "SUPERVISOR DO TURNO DA NOITE"),
])
def test_funcao_com_elemento_individualizante_e_sinalizada(anon, texto, trecho):
    assert trecho in _alertas(anon, texto)


def test_descricao_termina_antes_da_oracao_principal(anon):
    texto = "O fiscal que esteve aqui no dia 12/05 às 10h disse que voltaria."
    assert _alertas(anon, texto) == ["fiscal que esteve aqui no dia 12/05 às 10h"]


@pytest.mark.parametrize("texto", [
    # Usos adjetivos e substantivos homônimos
    "A nota fiscal emitida em 12/05/2024 às 10h foi anexada ao processo.",
    "O parecer técnico do dia 10/03/2024 concluiu pela regularidade.",
    "A segurança do paciente no turno da noite depende da escala de enfermagem.",
    "A Guarda Municipal reforçou o patrulhamento durante o feriado.",
    "A operadora de telefonia reajustou as tarifas no mês passado.",
    "A cirurgia de catarata no período da manhã foi suspensa.",
    # Função citada em abstrato, em enunciado normativo
    "O servidor do plantão noturno deverá registrar as ocorrências no livro próprio.",
    "Compete ao diretor da escola, no início de cada semestre, divulgar o calendário.",
    "Cabe ao professor da rede pública cumprir a carga horária no período letivo.",
    "O servidor que tiver interesse deverá comparecer no dia 12/05 às 10h.",
    # Função sem elemento que individualize, ou no plural
    "O fiscal do contrato encaminhou o relatório mensal.",
    "O técnico de enfermagem tem jornada de 30 horas semanais.",
    "Os vigilantes do turno da noite receberão adicional noturno.",
    # Sem palavra que introduza a função como pessoa
    "Técnico de enfermagem: plantão de 12 horas.",
])
def test_funcao_em_abstrato_nao_e_sinalizada(anon, texto):
    assert _alertas(anon, texto) == []


def test_perfil_ouvidoria_tarja_a_descricao():
    saida = Anonimizador("ouvidoria").anonimizar("O atendente do guichê 7 no turno da tarde me tratou mal.").texto
    assert "guichê 7" not in saida and "turno da tarde" not in saida and "me tratou mal" in saida
