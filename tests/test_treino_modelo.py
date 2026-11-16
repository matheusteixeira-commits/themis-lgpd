"""Classificador de trechos para dados de saúde (reconhecedor aprendido; rótulo de quase-identificadores desativado).

Cobre a seleção dos trechos, a conversão da probabilidade em confiança, o funcionamento sem o artefato
e o carregamento sobre o vocabulário e os vetores do modelo de linguagem. Os exemplos são fictícios.
"""

import pytest
import spacy

from themis_lgpd.reconhecedores import aprendido as A
from themis_lgpd.reconhecedores.base import SEMANTICA

LIMIARES = {"DADO_SAUDE": 0.5, "QUASI_IDENTIFICADOR": 0.5}


def test_modo_maximo_fica_com_o_trecho_mais_provavel_entre_sobrepostos():
    candidatos = [(0, 10, "DADO_SAUDE", 0.7), (0, 15, "DADO_SAUDE", 0.9), (12, 20, "DADO_SAUDE", 0.6),
                  (30, 40, "DADO_SAUDE", 0.4)]
    assert A.selecionar(candidatos, LIMIARES, "maximo") == [(0, 15, "DADO_SAUDE", 0.9)]


def test_modo_uniao_funde_trechos_sobrepostos_do_mesmo_rotulo():
    candidatos = [(0, 10, "QUASI_IDENTIFICADOR", 0.6), (5, 25, "QUASI_IDENTIFICADOR", 0.8),
                  (25, 30, "QUASI_IDENTIFICADOR", 0.7)]
    assert A.selecionar(candidatos, LIMIARES, "uniao") == [(0, 25, "QUASI_IDENTIFICADOR", 0.8),
                                                         (25, 30, "QUASI_IDENTIFICADOR", 0.7)]


def test_rotulos_diferentes_nao_disputam_o_mesmo_trecho():
    candidatos = [(0, 40, "QUASI_IDENTIFICADOR", 0.8), (10, 20, "DADO_SAUDE", 0.6)]
    assert len(A.selecionar(candidatos, LIMIARES, "maximo")) == 2


def test_limiar_proprio_de_cada_rotulo():
    candidatos = [(0, 5, "DADO_SAUDE", 0.55), (10, 20, "QUASI_IDENTIFICADOR", 0.55)]
    assert A.selecionar(candidatos, {"DADO_SAUDE": 0.6, "QUASI_IDENTIFICADOR": 0.5}) == [candidatos[1]]


def test_confianca_parte_do_minimo_do_perfil_no_limiar():
    assert A.confianca(0.55, 0.55) == A.CONFIANCA_NO_LIMIAR == 0.6
    assert A.confianca(1.0, 0.55) == A.CONFIANCA_MAXIMA
    assert A.confianca(0.6, 0.55) < A.confianca(0.8, 0.55) < A.confianca(0.95, 0.55)


@pytest.fixture
def sem_artefato(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "PASTA", tmp_path)
    A.metadados.cache_clear()
    yield
    A.metadados.cache_clear()


def test_sem_artefato_o_pipeline_fica_como_antes(sem_artefato, monkeypatch):
    monkeypatch.setenv("THEMIS_MODELO_SENSIVEL", "1")
    nlp = spacy.blank("pt")
    assert A.metadados() is None and not A.ativo()
    assert not A.acoplar(nlp) and nlp.pipe_names == []
    assert A.deteccoes(nlp("Tenho asma desde criança.")) == []
    assert A.ReconhecedorAprendido().analyze("Tenho asma desde criança.", ["SAUDE"], None) == []


requer_artefato = pytest.mark.skipif(A.metadados() is None, reason="artefato do classificador não instalado")


@requer_artefato
def test_variavel_de_ambiente_liga_e_desliga(monkeypatch):
    monkeypatch.setenv("THEMIS_MODELO_SENSIVEL", "0")
    assert not A.ativo()
    monkeypatch.setenv("THEMIS_MODELO_SENSIVEL", "1")
    assert A.ativo()
    monkeypatch.delenv("THEMIS_MODELO_SENSIVEL")
    assert A.ativo() is bool(A.metadados()["ativo_por_padrao"])


@requer_artefato
def test_artefato_nao_inclui_os_vetores_e_cabe_no_limite():
    tamanho = sum(p.stat().st_size for p in A.PASTA.iterdir())
    assert tamanho <= 25_000_000
    assert sorted(p.name for p in A.PASTA.iterdir()) == ["cfg", "config.json", "meta.json", "model"]


@requer_artefato
def test_vetores_diferentes_dos_do_treino_nao_acoplam(monkeypatch):
    monkeypatch.setenv("THEMIS_MODELO_SENSIVEL", "1")
    nlp = spacy.blank("pt")  # sem vetores
    assert not A.acoplar(nlp) and A.NOME_COMPONENTE not in nlp.pipe_names


@pytest.fixture(scope="module")
def nlp_classificador():
    """Pipeline separado, com o vocabulário e os vetores do modelo já carregado pelo Themis."""
    if A.metadados() is None:
        pytest.skip("artefato do classificador não instalado")
    from themis_lgpd.reconhecedores.nomes import carregar_spacy

    base = carregar_spacy("pt_core_news_lg")
    nlp = spacy.blank("pt", vocab=base.vocab)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("THEMIS_MODELO_SENSIVEL", "1")
        assert A.acoplar(nlp)
    assert A.acoplar(nlp) and nlp.pipe_names.count(A.NOME_COMPONENTE) == 1  # idempotente
    return nlp


def _achados(nlp, texto):
    return [(d.tipo, texto[d.inicio:d.fim], d.camada, d.score) for d in A.deteccoes(nlp(texto))]


def test_saude_descrita_com_palavras_proprias(nlp_classificador):
    achados = _achados(nlp_classificador, "Sinto dores fortes no joelho desde o acidente de trânsito.")
    assert any(t == "SAUDE" and "dores fortes" in v and c == SEMANTICA for t, v, c, _ in achados), achados
    achados = _achados(nlp_classificador, "Tenho tonturas frequentes desde o ano passado.")
    assert any(t == "SAUDE" and "tonturas" in v for t, v, _, _ in achados), achados


def test_rotulo_de_quase_identificador_desativado(nlp_classificador):
    # O classificador continua estimando o rótulo, mas só as regras produzem o achado: no sistema
    # integrado o rótulo aprendido não acrescentava acertos e sinalizava frases de expediente.
    texto = "Reclamo do cobrador do ônibus da linha 210 que passou às 7h40 de ontem."
    doc = nlp_classificador(texto)
    assert "QUASI_IDENTIFICADOR" not in A.metadados()["limiares"]
    assert any(r == "QUASI_IDENTIFICADOR" and "7h40" in texto[i:f] for i, f, r, _ in A.candidatos_do_doc(doc))
    assert not any(t == "QUASE_IDENTIFICADOR" for t, *_ in _achados(nlp_classificador, texto))


@pytest.mark.parametrize("texto", [
    "O relatório anual da secretaria foi publicado em março.",
    "Solicito cópia do contrato de limpeza urbana firmado em 2023.",
])
def test_texto_sem_dado_sensivel_nao_gera_achado(nlp_classificador, texto):
    assert _achados(nlp_classificador, texto) == []


@pytest.mark.parametrize("texto", [
    # Textos-modelo de apresentações (mestres e layouts), fora do domínio do treino
    "Click to edit Master title style",
    "Second level",
])
def test_texto_de_modelo_de_apresentacao_nao_gera_achado(nlp_classificador, texto):
    assert _achados(nlp_classificador, texto) == []


def test_confianca_dos_achados_fica_na_faixa_do_classificador(nlp_classificador):
    for _, _, _, score in _achados(nlp_classificador, "Tenho hérnia de disco lombar e sinto dores fortes."):
        assert A.CONFIANCA_NO_LIMIAR <= score <= A.CONFIANCA_MAXIMA


def test_poda_de_candidatos_respeita_bordas_e_frases(nlp_classificador):
    doc = nlp_classificador.make_doc("O paciente tem asma grave. Mora em Goiás")
    pares = {(int(a), int(b)) for a, b in A.sugerir_sintagmas([doc]).dataXd}
    textos = {doc[a:b].text for a, b in pares}
    assert "asma grave" in textos and "paciente tem asma" in textos
    assert not any(t.split()[0] in A.PALAVRAS_FUNCIONAIS or t.split()[-1] in A.PALAVRAS_FUNCIONAIS for t in textos)
    assert not any(". " in t or t.endswith(".") for t in textos)  # não atravessa nem termina no ponto final


requer_ativo = pytest.mark.skipif(not A.ativo(), reason="classificador desativado")


@requer_ativo
def test_saude_de_pessoa_e_tarjada_no_perfil_lai(anon):
    r = anon.anonimizar("Sinto dores fortes no joelho desde o acidente de trânsito.")
    assert "dores fortes" not in r.texto
    assert any(e.origem.startswith("aprendido:") for e in r.tarjadas)


@requer_ativo
@pytest.mark.parametrize("texto", [
    "A Secretaria de Saúde ampliou o atendimento a pacientes com diabetes na rede básica.",
    "Solicito o número de casos de dengue notificados no município no último ano.",
])
def test_saude_em_texto_de_interesse_publico_so_e_sinalizada(anon, texto):
    r = anon.anonimizar(texto)
    assert r.texto == texto
    assert any(e.tipo == "SAUDE" for e in r.alertas)
