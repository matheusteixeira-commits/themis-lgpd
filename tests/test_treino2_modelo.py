"""Classificador de trechos retreinado com documentos oficiais (ciclo 2 do reconhecedor aprendido).

Cobre a divisão das entidades anotadas em partes que o sugestor de candidatos propõe, a inferência da
categoria de um dado sensível a partir do trecho, o limiar contextual e o mapeamento dos rótulos novos;
com o artefato instalado, os acertos em documentos oficiais e as armadilhas de tarja indevida. Todos os
exemplos são fictícios.
"""

import sys
from pathlib import Path

import pytest
import spacy
from spacy.tokens import SpanGroup

from themis_lgpd.reconhecedores import aprendido as A
from themis_lgpd.reconhecedores.base import CONTEXTUAL, NER, SEMANTICA

sys.path.insert(0, str(Path(__file__).parents[1] / "benchmark" / "treino"))


@pytest.fixture(scope="module")
def nlp_vazio():
    return spacy.blank("pt")


# ---------------------------------------------------------------- partes treináveis das entidades
@pytest.fixture(scope="module")
def segmentar():
    from treinar_spancat import segmentar

    return segmentar


def _partes(nlp, segmentar, texto, trecho):
    doc = nlp.make_doc(texto)
    inicio = texto.index(trecho)
    span = doc.char_span(inicio, inicio + len(trecho), alignment_mode="expand")
    return [doc[a:b].text for a, b in segmentar(doc, span.start, span.end, 20)]


def test_entidade_que_ja_e_candidata_volta_inteira(nlp_vazio, segmentar):
    texto = "Diagnóstico: insuficiência cardíaca descompensada, em acompanhamento."
    assert _partes(nlp_vazio, segmentar, texto, "insuficiência cardíaca descompensada") == [
        "insuficiência cardíaca descompensada"]


def test_entidade_em_duas_linhas_vira_duas_partes(nlp_vazio, segmentar):
    texto = "Prescrição:\nCaptopril 25 mg ...... 60 cp\n1 cp de 12/12 h\nValidade: 30 dias."
    partes = _partes(nlp_vazio, segmentar, texto, "Captopril 25 mg ...... 60 cp\n1 cp de 12/12 h")
    assert partes == ["Captopril 25 mg ...... 60 cp", "1 cp de 12/12 h"]


def test_pontuacao_final_e_palavra_funcional_ficam_fora_da_parte(nlp_vazio, segmentar):
    texto = "Exame recente: creatinina de 2,4%. Sem outras alterações."
    assert _partes(nlp_vazio, segmentar, texto, "creatinina de 2,4%") == ["creatinina de 2,4"]
    texto = "Relata que a tosse persiste há dois meses; nega febre."
    assert _partes(nlp_vazio, segmentar, texto, "a tosse persiste há dois meses; nega febre") == [
        "tosse persiste há dois meses", "nega febre"]


def test_partes_seguem_o_sugestor_da_deteccao(nlp_vazio, segmentar):
    texto = "Queixa: dor lombar irradiada para a perna esquerda;\nusa ibuprofeno 600 mg se necessário."
    doc = nlp_vazio.make_doc(texto)
    pares = {(int(a), int(b)) for a, b in A.sugerir_sintagmas([doc]).dataXd}
    span = doc.char_span(texto.index("dor"), len(texto) - 1, alignment_mode="expand")
    partes = segmentar(doc, span.start, span.end, 20)
    assert partes and all(p in pares for p in partes)


# ---------------------------------------------------------------- categoria do dado sensível
@pytest.mark.parametrize(("trecho", "tipo"), [
    ("filiada ao sindicato dos servidores municipais", "FILIACAO_SINDICAL"),
    ("desconto da contribuição sindical", "FILIACAO_SINDICAL"),
    ("integrante do diretório estadual do partido", "OPINIAO_POLITICA"),
    ("autodeclarada parda", "ORIGEM_RACIAL"),
    ("pertencente ao povo indígena da região do alto rio", "ORIGEM_RACIAL"),
    ("remanescente de comunidade quilombola", "ORIGEM_RACIAL"),
    ("frequenta a congregação batista do bairro", "RELIGIAO"),
    ("praticante de umbanda", "RELIGIAO"),
    ("mulher transexual", "VIDA_SEXUAL"),
    ("mantém união homoafetiva há seis anos", "VIDA_SEXUAL"),
    ("cadastro biométrico com impressões digitais", "GENETICO_BIOMETRICO"),
])
def test_categoria_do_dado_sensivel_pelo_vocabulario(trecho, tipo):
    assert A.tipo_sensivel(trecho) == tipo


@pytest.mark.parametrize("trecho", [
    "Praça da Matriz",          # "praça" não é "raça"
    "transferência de lotação",  # "trans" sem relação com gênero
    "homologação do resultado",
    "comprovante de residência",
    "jogador do time do bairro",
])
def test_trecho_sem_categoria_sensivel(trecho):
    assert A.tipo_sensivel(trecho) is None


# ---------------------------------------------------------------- mapeamento dos rótulos e limiar contextual
def _doc_com_candidatos(nlp, texto, candidatos):
    doc = nlp(texto)
    spans = []
    for trecho, rotulo, _ in candidatos:
        inicio = texto.index(trecho)
        spans.append(doc.char_span(inicio, inicio + len(trecho), label=rotulo))
    doc.spans[A.NOME_COMPONENTE] = SpanGroup(doc, name=A.NOME_COMPONENTE, spans=spans,
                                             attrs={"scores": [p for *_, p in candidatos]})
    return doc


@pytest.fixture
def meta_falso(monkeypatch):
    def aplicar(limiares, contextuais=None):
        meta = {"limiares": limiares, "limiares_contextuais": contextuais or {}, "decodificacao": "maximo"}
        monkeypatch.setattr(A, "metadados", lambda: meta)

    return aplicar


TEXTO = ("Periciado: ANTÔNIO CARLOS VIEIRA. Apresenta cardiopatia isquêmica e cefaleia ocasional. "
         "Declara-se umbandista e frequenta o clube de xadrez.")
CANDIDATOS = [("ANTÔNIO CARLOS VIEIRA", "NOME_PESSOA", 0.97), ("cardiopatia isquêmica", "DADO_SAUDE", 0.98),
              ("cefaleia ocasional", "DADO_SAUDE", 0.7), ("umbandista", "DADO_SENSIVEL", 0.9),
              ("frequenta o clube de xadrez", "DADO_SENSIVEL", 0.8)]


def test_rotulos_novos_e_limiar_contextual(nlp_vazio, meta_falso):
    meta_falso({"DADO_SAUDE": 0.6, "NOME_PESSOA": 0.6, "DADO_SENSIVEL": 0.6}, {"DADO_SAUDE": 0.95})
    achados = {TEXTO[d.inicio:d.fim]: (d.tipo, d.camada) for d in A.deteccoes(_doc_com_candidatos(nlp_vazio, TEXTO,
                                                                                                    CANDIDATOS))}
    assert achados["ANTÔNIO CARLOS VIEIRA"] == ("NOME", NER)
    assert achados["cardiopatia isquêmica"] == ("SAUDE", CONTEXTUAL)  # acima do limiar contextual
    assert achados["cefaleia ocasional"] == ("SAUDE", SEMANTICA)  # segue a regra de vínculo
    assert achados["umbandista"] == ("RELIGIAO", SEMANTICA)
    assert "frequenta o clube de xadrez" not in achados  # sem categoria sensível, nenhum achado


def test_idade_ou_duracao_sozinha_nao_e_dado_de_saude(nlp_vazio, meta_falso):
    meta_falso({"DADO_SAUDE": 0.6})
    texto = ("Candidata com idade ≥ 18 anos, afastada por 30 dias. Gestação de 34 semanas, com dor lombar há 3 "
             "meses.")
    candidatos = [("≥ 18 anos", "DADO_SAUDE", 0.97), ("30 dias", "DADO_SAUDE", 0.9),
                  ("34 semanas", "DADO_SAUDE", 0.9), ("dor lombar há 3 meses", "DADO_SAUDE", 0.9)]
    achados = {texto[d.inicio:d.fim] for d in A.deteccoes(_doc_com_candidatos(nlp_vazio, texto, candidatos))}
    assert achados == {"34 semanas", "dor lombar há 3 meses"}


def test_rotulo_sem_limiar_nao_produz_achado(nlp_vazio, meta_falso):
    meta_falso({"DADO_SAUDE": 0.6})
    achados = A.deteccoes(_doc_com_candidatos(nlp_vazio, TEXTO, CANDIDATOS))
    assert {d.tipo for d in achados} == {"SAUDE"}
    assert all(d.camada == SEMANTICA for d in achados)  # sem limiar contextual


# ---------------------------------------------------------------- com o artefato instalado
@pytest.fixture(scope="module")
def nlp_classificador():
    """Pipeline separado, com o vocabulário e os vetores do modelo já carregado pelo Themis."""
    if A.metadados() is None:
        pytest.skip("artefato do classificador não instalado")
    from themis_lgpd.reconhecedores.nomes import carregar_spacy

    nlp = spacy.blank("pt", vocab=carregar_spacy("pt_core_news_lg").vocab)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("THEMIS_MODELO_SENSIVEL", "1")
        assert A.acoplar(nlp)
    return nlp


def _achados(nlp, texto):
    return [(d.tipo, texto[d.inicio:d.fim]) for d in A.deteccoes(nlp(texto))]


def _ativo(rotulo):
    return rotulo in (A.metadados() or {}).get("limiares", {})


@pytest.mark.parametrize(("texto", "esperado"), [
    ("Portaria nº 45/2025. Designar a servidora ADALGISA RIBEIRO MOTTA, matrícula 552.311-2, para compor a "
     "comissão.", "ADALGISA RIBEIRO MOTTA"),
    ("Assinam: IRANI GOMES TAVARES (presidente) e J.R.S. (secretário).", "J.R.S."),
    ("Ficha de notificação. Paciente: Zenaide Correia Lobo. Agravo: tuberculose pulmonar.", "Zenaide Correia Lobo"),
])
def test_nomes_em_caixa_alta_iniciais_e_campos_de_formulario(nlp_classificador, texto, esperado):
    if not _ativo("NOME_PESSOA"):
        pytest.skip("rótulo de nomes desativado")
    assert ("NOME", esperado) in _achados(nlp_classificador, texto)


@pytest.mark.parametrize(("texto", "trecho"), [
    ("Em uso de carvedilol 25 mg de 12/12 horas e furosemida 40 mg pela manhã.", "carvedilol 25 mg de 12/12 horas"),
    ("Ao exame, apresenta edema de membros inferiores e dispneia aos médios esforços.", "edema de membros inferiores"),
    ("Ficha de notificação. Paciente: Zenaide Correia Lobo. Agravo: tuberculose pulmonar.", "tuberculose pulmonar"),
])
def test_saude_em_linguagem_clinica(nlp_classificador, texto, trecho):
    assert any(t == "SAUDE" and trecho in v for t, v in _achados(nlp_classificador, texto))


@pytest.mark.parametrize(("texto", "tipo"), [
    ("A requerente declarou ser indígena da etnia Pankararu.", "ORIGEM_RACIAL"),
    ("Autodeclarou-se parda no cadastro.", "ORIGEM_RACIAL"),
])
def test_dado_sensivel_com_categoria_inferida(nlp_classificador, texto, tipo):
    if not _ativo("DADO_SENSIVEL"):
        pytest.skip("rótulo de dados sensíveis desativado")
    assert any(t == tipo for t, _ in _achados(nlp_classificador, texto))


@pytest.mark.parametrize("texto", [
    # Nome de homenageado em instituição e nome de município não são nome de pessoa
    "Encaminhe-se ao Hospital Estadual Professor Ernani Viana para as providências.",
    "Ofício à Prefeitura Municipal de Conselheiro Lafaiete.",
    # Dado de saúde agregado, de interesse público
    "O boletim registrou 118 internações por pneumonia em idosos no trimestre.",
    # Textos-modelo em inglês, com palavras que não estão no vocabulário fora do domínio do treino
    "Double-tap to rename this frame",
    "Swipe left to dismiss",
])
def test_armadilhas_sem_achado(nlp_classificador, texto):
    assert _achados(nlp_classificador, texto) == []


def test_saude_agregada_nao_e_tarjada_no_sistema(anon):
    texto = "O boletim registrou 118 internações por pneumonia em idosos no trimestre."
    assert anon.anonimizar(texto).texto == texto


def test_nome_de_homenageado_em_instituicao_fica_legivel(anon):
    texto = "Encaminhe-se ao Hospital Estadual Professor Ernani Viana para as providências."
    assert anon.anonimizar(texto).texto == texto


def test_vocabulario_fora_do_dominio_nao_inclui_as_palavras_dos_testes():
    # Os testes de textos-modelo medem generalização: suas palavras não podem estar no treino.
    from treinar_spancat import VOCABULARIO_FORA_DO_DOMINIO

    palavras = {"click", "to", "edit", "master", "title", "style", "second", "level", "double", "tap", "rename",
                "frame", "swipe", "left", "dismiss"}
    assert not palavras & set(VOCABULARIO_FORA_DO_DOMINIO)
