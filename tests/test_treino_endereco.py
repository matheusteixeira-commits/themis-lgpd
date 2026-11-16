"""Endereço residencial completo: do logradouro ao complemento, ao bairro e ao CEP.

O trecho tarjado cobre logradouro, número, complemento, lote, bairro e CEP. Município e UF no fim,
sozinhos, ficam visíveis (não identificam ninguém), assim como o endereço de órgão ou equipamento
público citado em contexto institucional. Os exemplos são fictícios.
"""

import pytest

from themis_lgpd.reconhecedores.localizacao import ReconhecedorEndereco


def _enderecos(texto):
    return [texto[d.inicio:d.fim] for d in ReconhecedorEndereco().detectar(texto) if d.tipo == "ENDERECO"]


# Bairro, setor, loteamento, zona rural e CEP que antes sobravam ao lado da tarja.
COMPLEMENTOS = [
    ("Moro na Rua dos Ipês, 120, no bairro Vila Esperança, em Londrina.", ["Ipês", "120", "Esperança"], ["Londrina"]),
    ("Resido na Rua Alfa, 88 no Bairro Industrial em Maringá.", ["Alfa", "88", "Industrial"], ["Maringá"]),
    ("Endereço: Rua Seis, 45 - Setor Leste - Goiânia/GO", ["Seis, 45", "Setor Leste"], ["Goiânia/GO"]),
    ("Endereço para resposta: Avenida Brasil, 900, Centro, conforme cadastro.", ["Brasil, 900", "Centro"], ["cadastro"]),
    ("Moro na Rua das Acácias, 77, apto 3, no Setor Habitacional Vale Verde em Sobradinho.",
     ["Acácias", "Vale Verde"], ["Sobradinho"]),
    ("Moro na Rua Beta, 10, Loteamento Bela Vista, Itu.", ["Beta, 10", "Loteamento Bela Vista"], []),
    ("Moro no Sítio Ipê Roxo, Km 9 da Rodovia BR-070, Zona Rural e preciso do laudo.", ["Ipê Roxo", "Zona Rural"],
     ["preciso"]),
    ("Envio para Rua Gama, 7, apto 2, Vicente Pires, CEP 72000-100.", ["Gama, 7", "Vicente Pires", "72000-100"], []),
    ("Resido na Rua Delta, 31, Jardim Itália, Recife - CEP 50000-000, desde 2015.", ["Jardim Itália", "Recife"],
     ["desde 2015"]),
    ("O lote fica na Quadra 15, Conjunto 3, Lote 8, Riacho Fundo, CEP 71800-000.", ["Riacho Fundo", "71800"], []),
]


@pytest.mark.parametrize("texto,proibidos,visiveis", COMPLEMENTOS)
def test_bairro_e_cep_integram_o_endereco(anon, texto, proibidos, visiveis):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"
    for v in visiveis:
        assert v in saida, f"{v!r} deveria ficar visível em: {saida!r}"


@pytest.mark.parametrize("texto,visivel", [
    ("Moro na Rua Beta, 10, centro de Sinop.", "centro de Sinop"),
    ("Moro no Sítio Lagoa Azul, zona rural de Formosa.", "zona rural de Formosa"),
    ("Moro na Rua Gama, 5 em Vila Velha.", "Vila Velha"),
    ("Moro na Rua Delta, 7, Distrito Federal.", "Distrito Federal"),
    ("Moro na Rua Ômega, 3, em Taguatinga.", "Taguatinga"),
    ("Preciso levar na Rua das Acácias, 14 no setor de RH amanhã.", "setor de RH"),
    ("Moro na Rua do Ouro, 44, no centro histórico de Mariana.", "centro histórico de Mariana"),
])
def test_municipio_no_fim_fica_visivel(anon, texto, visivel):
    saida = anon.anonimizar(texto).texto
    assert visivel in saida and "[ENDEREÇO]" in saida, saida


@pytest.mark.parametrize("texto,trecho", [
    ("Moro no Sítio Lagoa Azul na Estrada do Pontal, km 4.", "Sítio Lagoa Azul na Estrada do Pontal, km 4"),
    ("Moro no Assentamento Nova Aurora, no Km 15 da Rodovia GO-020, lote 42.",
     "Assentamento Nova Aurora, no Km 15 da Rodovia GO-020, lote 42"),
    ("Resido no Sítio Bom Retiro, KM 9 da Rodovia MGC-120.", "Sítio Bom Retiro, KM 9 da Rodovia MGC-120"),
    ("O imóvel fica no Lote 9, Quadra 20, Setor Norte.", "Lote 9, Quadra 20, Setor Norte"),
    ("Moro no Setor Leste, Rua 3, nº 40.", "Setor Leste, Rua 3, nº 40"),
])
def test_partes_do_mesmo_endereco_sao_unidas(texto, trecho):
    assert trecho in _enderecos(texto)


# Formatos que antes não eram reconhecidos.
NOVOS_FORMATOS = [
    ("Residente na Gleba 7, Lote 3 da GO-020, Formosa/GO.", ["Gleba 7", "Lote 3", "GO-020"]),
    ("Meu imóvel fica no Trecho 2 Lote 310, Arniqueira.", ["Trecho 2", "310"]),
    ("Moro no Conjunto C, Casa 9, Vila Operária.", ["Conjunto C", "Casa 9", "Operária"]),
    ("Localidade: Projeto de Assentamento Nova Vida, Lote 30, Gleba C", ["Nova Vida", "Lote 30", "Gleba C"]),
    ("Moro na Av. W3 Sul, quadra 507, bloco B.", ["W3 Sul", "507"]),
    ("Moro na Rodovia Estadual, km 40, Lote Rural 8.", ["Lote Rural 8"]),
    ("Moro na Estrada Velha, km 3, s/n, Gleba 2, Loteamento Bela Vista", ["s/n", "Gleba 2", "Bela Vista"]),
    ("Moro na Rua das Flores, altura do número 300, no bairro Jardim Alvorada.", ["300", "Alvorada"]),
    ("Moro na Rua 15 de Novembro, 300, Centro.", ["15 de Novembro", "300"]),
    ("Resido na Avenida 7 de Setembro, nº 1200, apto 3.", ["7 de Setembro", "1200"]),
    ("Endereço: Rua 1º de Maio, 45 - Vila Operária", ["1º de Maio", "45", "Operária"]),
    ("O imóvel fica no Setor de Oficinas, Lote 12, Bloco B.", ["Oficinas", "Lote 12", "Bloco B"]),
    ("Moro no Setor de Mansões, Quadra 4, Lote 9.", ["Mansões", "Quadra 4"]),
    # Texto todo em minúsculas
    ("moradia: chácara bela vista, lote 7, núcleo rural ribeirão, planaltina/df", ["bela vista", "ribeirão"]),
    ("sou moradora da rua das flores 30 setor sul e preciso de ajuda", ["flores 30", "setor sul"]),
    ("A padaria fica na Rua Onze, 30 bairro vila nova e ninguém resolve.", ["Onze, 30", "vila nova"]),
]


@pytest.mark.parametrize("texto,proibidos", NOVOS_FORMATOS)
def test_novos_formatos_de_endereco(anon, texto, proibidos):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


# Endereço institucional, rua sem número e data: nada a acrescentar à tarja.
@pytest.mark.parametrize("texto", [
    "A escola fica localizada na Gleba 6, Lote 2 da GO-118.",
    "O posto de saúde do Conjunto F, Casa 1 atende 300 famílias.",
    "A Rua 15 de Novembro será recapeada pela prefeitura.",
    "O semáforo da Avenida Central com a rua 15 de novembro está desregulado.",
    "O Assentamento Santa Rita, em Marabá, recebeu investimentos.",
    "O Distrito Industrial de Vitória do Jari abriga 35 empresas.",
    "Fui atendido no Posto de Saúde da Vila Planalto no dia 12 de maio.",
])
def test_texto_publico_permanece(anon, texto):
    r = anon.anonimizar(texto)
    assert "[ENDEREÇO]" not in r.texto, [(e.tipo, e.origem, e.valor) for e in r.entidades if e.acao == "tarjar"]


def test_endereco_de_orgao_nao_e_estendido_ao_bairro(anon):
    saida = anon.anonimizar("O posto de saúde da Rua Sete, 120, no bairro Novo Horizonte atende 3 mil famílias.").texto
    assert "no bairro Novo Horizonte" in saida, saida


def test_residencia_prevalece_sobre_mencao_a_orgao(anon):
    saida = anon.anonimizar("Sou servidora da Secretaria de Saúde e moro na Rua Sete, 120, no bairro Novo "
                            "Horizonte.").texto
    assert "Novo Horizonte" not in saida and "Secretaria de Saúde" in saida, saida
