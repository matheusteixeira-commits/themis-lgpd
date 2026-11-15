"""Testes dos validadores de dígito verificador dos documentos brasileiros."""

import random

import pytest

from themis_lgpd import validadores as v


@pytest.mark.parametrize("valor,ok", [
    ("529.982.247-25", True), ("52998224725", True), ("123.456.789-00", False),
    ("111.111.111-11", False), ("000.000.000-00", False), ("5299822472", False),
])
def test_cpf(valor, ok):
    assert v.cpf_valido(valor) is ok


@pytest.mark.parametrize("valor,ok", [
    ("11.222.333/0001-81", True),
    ("12.ABC.345/01DE-35", True),  # exemplo oficial da Receita Federal (CNPJ alfanumérico)
    ("12.ABC.345/01DE-36", False), ("00.000.000/0000-00", False), ("11.222.333/0001-8A", False),
])
def test_cnpj_numerico_e_alfanumerico(valor, ok):
    assert v.cnpj_valido(valor) is ok


@pytest.mark.parametrize("gerador,validador", [
    (v.gerar_cpf, v.cpf_valido), (v.gerar_pis, v.pis_valido), (v.gerar_titulo, v.titulo_eleitor_valido),
    (v.gerar_cns, v.cns_valido), (v.gerar_cnh, v.cnh_valida), (v.gerar_renavam, v.renavam_valido),
    (v.gerar_processo_cnj, v.processo_cnj_valido), (v.gerar_cartao, v.luhn_valido),
    (lambda r: v.gerar_cnpj(r, alfanumerico=True), v.cnpj_valido),
])
def test_geradores_produzem_documentos_validos(gerador, validador):
    rng = random.Random(42)
    for _ in range(300):
        assert validador(gerador(rng))


@pytest.mark.parametrize("gerador,validador", [
    (v.gerar_pis, v.pis_valido), (v.gerar_cns, v.cns_valido), (v.gerar_cartao, v.luhn_valido),
    (v.gerar_titulo, v.titulo_eleitor_valido), (v.gerar_renavam, v.renavam_valido),
])
def test_digito_errado_e_rejeitado(gerador, validador):
    rng = random.Random(7)
    for _ in range(50):
        valido = gerador(rng)
        ultimo = valido.rstrip()[-1]
        errado = valido.rstrip()[:-1] + str((int(ultimo) + 1) % 10)
        assert not validador(errado), errado


def test_cnj_e_ip():
    assert v.processo_cnj_valido(v.gerar_processo_cnj(random.Random(1)))
    assert not v.processo_cnj_valido("0701234-56.2024.8.07.0001")
    assert v.ip_valido("189.40.12.7") and v.ip_valido("2001:db8::1")
    assert not v.ip_valido("12:30:45") and not v.ip_valido("999.1.1.1")
