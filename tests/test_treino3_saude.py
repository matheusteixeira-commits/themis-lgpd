"""Dados de saúde e dados sensíveis fora do registro clínico, e a precisão das categorias sensíveis.

Os exemplos são fictícios. Cobrem:

* saúde descrita em linguagem leiga, em fala relatada ou pelo serviço que atende a pessoa: sintoma e
  comportamento, uso de substância por verbo, tratamento no CAPS ou em comunidade terapêutica,
  dispositivo e ato assistencial, gestação em semanas ou meses, deficiência e vacina abreviadas, nome
  comercial de medicamento, lesão com partes do corpo coordenadas;
* dado sensível em terceira pessoa ou perífrase: prática religiosa, função num terreiro ou igreja,
  pertença étnica ou cigana, relação afetiva, identidade de gênero, mandato sindical, atuação
  partidária, campo de cadastro;
* as armadilhas de tarja indevida: enunciado normativo ou de protocolo, contagem e estatística, "nome
  social" como rótulo, internação socioeducativa, providência policial, topônimo, nome de unidade e
  trecho do classificador sem termo de saúde.
"""

import pytest

from themis_lgpd import Anonimizador
from themis_lgpd.reconhecedores import sensiveis as S


@pytest.fixture(scope="module")
def anon() -> Anonimizador:
    return Anonimizador("lai", usar_ner=False)


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


# --------------------------------------------------------------------------- Saúde fora do registro clínico
def test_sintoma_e_comportamento_em_linguagem_leiga(anon):
    r = anon.anonimizar("Minha irmã ouve vozes de madrugada e não sai do quarto desde a mudança. Ela também parou de "
                        "comer e chora escondida todos os dias.")
    for trecho in ("ouve vozes de madrugada", "não sai do quarto", "parou de comer", "chora escondida todos os dias"):
        assert _tarjado(r, trecho), trecho


def test_uso_de_substancia_por_verbo_e_perifrase(anon):
    r = anon.anonimizar("Contou que o companheiro cheira cola de sapateiro nos fins de semana e vive tomando pinga desde "
                        "que perdeu o emprego.")
    assert _tarjado(r, "cheira cola de sapateiro nos fins de semana")
    assert _tarjado(r, "vive tomando pinga desde que perdeu o emprego")


def test_tratamento_descrito_pelo_servico(anon):
    r = anon.anonimizar("O filho da requerente faz acompanhamento semanal no CAPS AD e teve três internações em "
                        "comunidade terapêutica.")
    assert _tarjado(r, "acompanhamento semanal no CAPS AD")
    assert _tarjado(r, "três internações em comunidade terapêutica")


def test_unidade_citada_pelo_nome_fica_legivel(anon):
    r = anon.anonimizar("A adolescente, diagnosticada com transtorno de ansiedade, é acompanhada no CAPS Infantojuvenil "
                        "Primavera.")
    assert _tarjado(r, "transtorno de ansiedade")
    assert _legivel(r, "CAPS Infantojuvenil Primavera")


def test_dispositivo_ato_assistencial_e_marca_comercial(anon):
    r = anon.anonimizar("Meu neto tem bronquite, usa bombinha e nebulizador e toma Singulair à noite.")
    for trecho in ("bombinha", "nebulizador", "Singulair à noite"):
        assert _tarjado(r, trecho), trecho


def test_falta_de_medicamento_nao_e_negacao(anon):
    texto = ("Requerente: Fulana de Teste\nData de nascimento: 02/03/1990\n\n"
             "Relato: o meu filho ficou três dias sem a bombinha porque a farmácia estava fechada.")
    assert _tarjado(anon.anonimizar(texto), "bombinha")


def test_gestacao_em_semanas_ou_meses_e_prematuridade(anon):
    r = anon.anonimizar("A usuária, gestante de oito meses, procurou a unidade. A filha dela nasceu prematura e a irmã "
                        "está grávida de 20 semanas.")
    for trecho in ("gestante de oito meses", "prematura", "grávida de 20 semanas"):
        assert _tarjado(r, trecho), trecho


def test_deficiencia_vacina_e_licenca_abreviadas(anon):
    r = anon.anonimizar("O filho é PcD (def. visual total). A criança recebeu a TRÍPLICE VIRAL D2 nesta data. "
                        "A servidora esteve em Licença-saúde de 3 a 5 de maio.")
    for trecho in ("PcD (def. visual total)", "TRÍPLICE VIRAL D2", "Licença-saúde"):
        assert _tarjado(r, trecho), trecho


def test_lesoes_com_partes_do_corpo_coordenadas(anon):
    r = anon.anonimizar("A vítima apresentava escoriações no cotovelo esquerdo e no joelho direito.")
    assert _tarjado(r, "escoriações no cotovelo esquerdo e no joelho direito")


def test_termo_coordenado_a_outro_tarjado(anon):
    r = anon.anonimizar("No acolhimento, a criança apresentava febre e tosse.")
    assert _tarjado(r, "febre") and _tarjado(r, "tosse")


def test_campo_de_ficha_com_dado_de_saude(anon):
    r = anon.anonimizar("Aluno(a): Fulano de Teste   Turma: 4º B\nAlergias: camarão e penicilina   Turno: manhã")
    assert _tarjado(r, "camarão e penicilina")
    assert _legivel(r, "Turno")


# --------------------------------------------------------------------------- Dado sensível em perífrase
def test_pratica_e_funcao_religiosa_em_terceira_pessoa(anon):
    r = anon.anonimizar("A avó frequenta a Igreja Batista Monte Sião e o tio é ogã de um terreiro de candomblé.")
    assert _tarjado(r, "Igreja Batista Monte Sião")
    assert _tarjado(r, "ogã de um terreiro de candomblé")


def test_pertenca_etnica_cigana_e_autodeclaracao(anon):
    r = anon.anonimizar("A família se declara cigana da etnia Calon. O pai declarou-se pardo no cadastro.")
    assert _tarjado(r, "cigana da etnia Calon")
    assert _tarjado(r, "pardo")


def test_relacao_afetiva_e_identidade_de_genero(anon):
    texto = ("Nome: Fulana de Teste\nIdentidade de gênero: mulher transexual\n\n"
             "Relatou que mantém relacionamento afetivo com outra interna da unidade.")
    r = anon.anonimizar(texto)
    assert _tarjado(r, "mulher transexual")
    assert _tarjado(r, "relacionamento afetivo com outra interna")


def test_mandato_sindical_e_atuacao_partidaria(anon):
    r = anon.anonimizar("O servidor ficará liberado para mandato classista na diretoria do sindicato dos vigilantes. "
                        "O depoente é filiado ao mesmo partido do prefeito.")
    assert _tarjado(r, "liberado para mandato classista na diretoria do sindicato dos vigilantes")
    assert _tarjado(r, "filiado ao mesmo partido do prefeito")


# --------------------------------------------------------------------------- Armadilhas de tarja indevida
def test_enunciado_normativo_ou_de_protocolo_fica_legivel(anon):
    r = anon.anonimizar("ORIENTAÇÕES À REDE\n3.1 O paciente com suspeita de dengue deve receber hidratação oral.\n"
                        "3.2 A vítima de violência sexual deve ser acolhida em até 72 horas.")
    assert _legivel(r, "dengue")
    assert _legivel(r, "violência sexual")


def test_relato_com_verbo_modal_continua_tarjado(anon):
    r = anon.anonimizar("Em atenção ao pedido da mãe, que é evangélica, a aluna poderá faltar às aulas de sábado.")
    assert _tarjado(r, "evangélica")


def test_contagem_e_estatistica_ficam_legiveis(anon):
    r = anon.anonimizar("A secretária informou que, em 2024, foram 312 casos de violência doméstica, 41 deles com "
                        "gravidez, e que a rede atende 57 estudantes com deficiência auditiva.")
    for trecho in ("violência doméstica", "gravidez", "deficiência auditiva"):
        assert _legivel(r, trecho), trecho
    estatistica = "foram 312 casos de dengue"
    assert S.agregado(estatistica, estatistica.index("dengue"), len(estatistica))
    relato = "Paciente nascida em 2015 diabética"
    assert not S.agregado(relato, relato.index("diabética"), len(relato))


def test_nome_social_como_rotulo_fica_legivel(anon):
    r = anon.anonimizar("Meu nome social foi cadastrado. O uso do nome social é assegurado nos serviços de saúde.")
    assert "nome social" in r.texto


def test_internacao_socioeducativa_nao_e_dado_de_saude():
    texto = ("O adolescente cumpre medida socioeducativa desde março. Antes da internação, frequentava a escola "
             "do bairro.")
    ctx = S.contexto_documental(texto)
    ini = texto.index("internação")
    assert ctx.isencao(texto, ini, ini + len("internação"), "semantica", "saude:termo", "SAUDE") == S.ISENCAO_SOCIOEDUCATIVA
    hospital = "O adolescente cumpre medida socioeducativa. Precisou de internação no hospital regional por pneumonia."
    ini = hospital.index("internação")
    assert S.contexto_documental(hospital).isencao(hospital, ini, ini + 10, "semantica", "saude:termo", "SAUDE") == ""


def test_exame_pericial_so_requisitado_fica_legivel(anon):
    r = anon.anonimizar("Providências: requisitado exame de corpo de delito ao instituto médico-legal.")
    assert _legivel(r, "exame de corpo de delito")


def test_toponimo_e_nome_de_unidade_ficam_legiveis(anon):
    r = anon.anonimizar("Participam os municípios de Vila Nova Batista e Serra Alta. Assina a Coordenadora de Apoio a "
                        "Pessoas em Situação de Violência, que me atendeu.")
    assert _legivel(r, "Batista")
    assert _legivel(r, "Situação de Violência")


def test_trecho_do_classificador_sem_termo_de_saude():
    texto = "A laje foi concretada com fck 35 MPa. Em entrevista, o morador confirmou a obra."
    ctx = S.contexto_documental(texto)
    ini = texto.index("fck")
    assert ctx.isencao(texto, ini, ini + len("fck 35 MPa"), "semantica", "aprendido:dado_saude", "SAUDE") == S.ISENCAO_FRAGMENTO
    ini = texto.index("Em entrevista")
    assert ctx.isencao(texto, ini, ini + 13, "semantica", "aprendido:dado_saude", "SAUDE") == S.ISENCAO_FRAGMENTO
