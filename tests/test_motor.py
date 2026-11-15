"""Testes do motor: perfis, regra de vínculo, modos de saída, listas e propagação."""

import pytest

from themis_lgpd import Anonimizador, Resultado
from themis_lgpd.texto import normalizar


def test_fidelidade_texto_fora_das_tarjas_e_identico(anon):
    """Bug original: NFKC trocava 'nº' por 'no', colapsava espaços e removia recuos."""
    texto = "  Processo  nº 123 —   texto   com espaços\n\tE “aspas”, ½ e ﬁ ligadura. CPF 529.982.247-25."
    r = anon.anonimizar(texto)
    assert r.texto == texto.replace("529.982.247-25", "[CPF]").replace("Processo  nº 123", "Processo  nº [PROCESSO]")


def test_mapa_de_posicoes_volta_ao_original():
    n = normalizar("Jo\u200bão ﬁm ½ Ｃ")
    assert n.texto == "João fim 1⁄2 C"
    ini, fim = n.para_original(n.texto.index("fim"), n.texto.index("fim") + 3)
    assert n.original[ini:fim] == "ﬁm"


def test_encoding_corrompido_e_corrigido(anon):
    r = anon.anonimizar("SolicitaÃ§Ã£o da requerente Maria Souza")
    assert r.texto.startswith("Solicitação") and "Maria" not in r.texto
    assert any("mojibake" in a for a in r.avisos)


def test_texto_vazio(anon):
    assert anon.anonimizar("").texto == ""
    assert anon.analisar("") == []


@pytest.mark.parametrize("modo,esperado", [
    ("etiqueta", "CPF [CPF]"), ("tarja", "CPF ████████"), ("mascara", "CPF ***.***.***-**"),
])
def test_modos(modo, esperado):
    assert Anonimizador(modo=modo, usar_ner=False).anonimizar("CPF 529.982.247-25").texto == esperado


def test_pseudonimo_consistente_e_correferencia():
    a = Anonimizador(modo="pseudonimo")
    r = a.anonimizar("Maria Aparecida Souza pediu. Depois Maria voltou com João Pereira. "
                     "CPF 529.982.247-25 e de novo 52998224725.")
    assert r.texto.count("Pessoa 1") == 2 and "Pessoa 2" in r.texto
    assert r.texto.count("[CPF 1]") == 2


def test_pseudonimo_consistente_no_lote():
    a = Anonimizador(modo="pseudonimo")
    r1, r2 = a.anonimizar_lote(["Ana Lima reclamou.", "A servidora Ana Lima respondeu."])
    assert "Pessoa 1" in r1.texto and "Pessoa 1" in r2.texto


def test_hmac_depende_da_chave():
    t = "CPF 529.982.247-25"
    a = Anonimizador(modo="hmac", chave_hmac="chave-1", usar_ner=False).anonimizar(t).texto
    b = Anonimizador(modo="hmac", chave_hmac="chave-1", usar_ner=False).anonimizar(t).texto
    c = Anonimizador(modo="hmac", chave_hmac="chave-2", usar_ner=False).anonimizar(t).texto
    assert a == b != c and "529" not in a


def test_listas_de_permissao_e_bloqueio():
    a = Anonimizador(permitir=["Hospital Regional de Taguatinga"], bloquear=["Projeto Sigilo X"], perfil="maxima")
    r = a.anonimizar("No Hospital Regional de Taguatinga discutimos o projeto sigilo x.")
    assert "Hospital Regional de Taguatinga" in r.texto and "sigilo x" not in r.texto


def test_agente_publico_preservado_somente_com_opcao():
    texto = "A Secretária de Estado de Saúde, Lucilene Florêncio, e o requerente João Pereira."
    assert "Lucilene" not in Anonimizador().anonimizar(texto).texto
    r = Anonimizador(preservar_agentes_publicos=True).anonimizar(texto)
    assert "Lucilene Florêncio" in r.texto and "João Pereira" not in r.texto


def test_sensivel_isolado_vira_alerta_e_vinculado_e_tarjado(anon):
    geral = anon.anonimizar("A política de saúde mental do DF prevê atendimento para depressão.")
    assert geral.tarjadas == [] and any(e.tipo == "SAUDE" for e in geral.alertas)
    pessoal = anon.anonimizar("Eu tenho depressão desde 2019.")
    assert "depressão" not in pessoal.texto


def test_perfil_saude_tarja_termos_de_saude_sempre():
    r = Anonimizador("saude").anonimizar("A política de saúde mental prevê atendimento para depressão.")
    assert "depressão" not in r.texto


def test_perfil_identificadores_nao_tarja_sensiveis():
    r = Anonimizador("identificadores").anonimizar("Maria Souza tem diabetes.")
    assert "Maria" not in r.texto and "diabetes" in r.texto


def test_revisao_humana_respeitada(anon):
    texto = "O servidor João Pereira, CPF 529.982.247-25, pediu férias."
    ents = anon.analisar(texto)
    for e in ents:
        if e.tipo == "NOME":
            e.acao = "alertar"  # revisor decidiu manter o nome
    r = anon.anonimizar(texto, ents)
    assert "João Pereira" in r.texto and "529" not in r.texto


def test_resultado_serializa_sem_valores_por_padrao(anon):
    r: Resultado = anon.anonimizar("Maria Souza, CPF 529.982.247-25")
    d = r.para_dict()
    assert "texto_original" not in d and all("valor" not in e for e in d["entidades"])
    assert any(e["valor"] == "529.982.247-25" for e in r.para_dict(incluir_valores=True)["entidades"])


def test_perfil_ou_modo_invalido():
    with pytest.raises(ValueError):
        Anonimizador(perfil="inexistente", usar_ner=False)
    with pytest.raises(ValueError):
        Anonimizador(modo="inexistente", usar_ner=False)


def test_texto_grande_e_dividido_para_o_modelo(anon):
    texto = ("Parágrafo sem dados. " * 300 + "\n") * 25 + "Assinado por Maria Aparecida Souza."
    assert len(texto) > 100_000
    assert "Maria" not in anon.anonimizar(texto).texto
