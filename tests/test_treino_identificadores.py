"""Regressão dos identificadores processuais, profissionais, documentos e dados bancários.

Os exemplos são fictícios e cobrem classes de redação: o número ligado à designação por verbo ou
expressão de identificação ("o protocolo que recebi foi o …"), a sigla da unidade colada à numeração
do processo, o possessivo entre o documento e o número ("o RG dele é …"), registros profissionais em
formatos variados, documentos de estrangeiros e contas bancárias com pontuação.
"""

import pytest

VAZAMENTOS = [
    # (texto, trechos que NÃO podem sobrar na saída)
    ("O número do protocolo que recebi no balcão foi o 20230101-1234. Obrigado.", ["20230101", "1234"]),
    ("O processo que abri na regional de ensino é o 2023.0102.003 e aguardo.", ["0102.003"]),
    ("Já abri uma solicitação anterior no sistema sob o número 2023.01.02.0001, sem retorno.", ["02.0001"]),
    ("A ocorrência foi registrada na delegacia sob o número 20230101-55.", ["20230101-55"]),
    ("O número que me deram no papel foi 01234.567/2023-12.", ["01234.567"]),
    ("Me passaram o numero 12345/2023 por telefone.", ["12345/2023"]),
    ("O protocolo de reclamação anterior no sistema do órgão: 20240101-54321.", ["54321"]),
    ("O pedido de acesso, de acordo com o sistema, é o 12345/2024.", ["12345/2024"]),
    ("O rastreio da encomenda é BR123456789XX.", ["123456789"]),
    ("Gostaria do status do processo de baixa 12345/2023-RJ e do processo de pagamento 54321/2022-11.",
     ["12345/2023", "54321/2022"]),
    ("Número do processo: 2023.07.XYZ.0123", ["XYZ", "0123"]),
    ("O processo administrativo 12345/2023-ABC e o PROCESSO nº 00123/2022-SMX estão parados.", ["ABC", "SMX"]),
    ("Sou portador da cédula de identidade de estrangeiro RNM G123456-K.", ["G123456", "-K"]),
    ("O número do RNE dele é V765432-K e ele precisa viajar.", ["V765432", "-K"]),
    ("Passaporte: K12P45Z78, nacionalidade alemã.", ["K12P45Z78"]),
    ("O documento dele é 12.345.678-X e mora no centro.", ["12.345.678", "-X"]),
    ("Minha identidade militar é a 012345678-9.", ["012345678"]),
    ("O registro funcional dele é 123456-X.", ["123456"]),
    ("Registro funcional ABC-12345-X na unidade.", ["ABC-12345", "-X"]),
    ("Seguem dados: registro profissional 012345-DF; Registro Profissional: XYZ-12345.", ["012345", "-DF", "XYZ-12345"]),
    ("Engenheiro com registro profissional ABC/PR 12345/SP.", ["ABC/PR", "12345", "/SP"]),
    ("Conta para recebimento: 01234567-8.", ["01234567"]),
    ("Informo meu dado bancario 0123-4 para o depósito.", ["0123-4"]),
    ("Agência 0001 e conta corrente 12.345-X.", ["12.345", "-X"]),
    ("O valor foi depositado na cont 12345-6 da empresa.", ["12345-6"]),
]


@pytest.mark.parametrize("texto,proibidos", VAZAMENTOS)
def test_identificador_tarjado(anon, texto, proibidos):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


@pytest.mark.parametrize("texto", [
    "A Lei nº 12.527/2011 e a Lei Complementar nº 101/2000 regem o tema.",
    "O número da Lei é 12.527/2011 e o número do edital é 02/2024; o número do contrato é 123/2023.",
    "O processo seletivo nº 12345/2023 foi publicado pelo Edital nº 02/2024.",
    "O número de servidores foi 12.345 e o número de vagas é 12345 no período 2023/2024.",
    "O processo tem 1.234 folhas e o pedido foi feito em 15/03/2024.",
    "O valor do processo é 1.234,56 e o valor do pedido foi 2.345,67.",
    "Em caso de dúvida, o número do processo é o mesmo do pedido anterior.",
    "O registro de preços nº 12345/2023 foi homologado pelo pregão nº 54321/2023.",
    "Número SIAFI: 2023NE000123, liquidado pela ordem bancária 2023OB004567.",
    "O boletim epidemiológico nº 12345/2023 foi divulgado.",
    "Em atendimento ao Ofício nº 12345/2023-GAB, encaminhamos a resposta.",
])
def test_nao_tarja_numero_publico_ou_quantidade(anon, texto):
    r = anon.anonimizar(texto)
    assert r.tarjadas == [], [(e.tipo, e.valor) for e in r.tarjadas]


def test_cnpj_formatado_nao_vira_protocolo(anon):
    """O CNPJ citado junto a um pedido continua com o tratamento de CNPJ (mantido no perfil LAI)."""
    texto = "O CNPJ da empresa no pedido é 12.345.678/0001-95."
    r = anon.anonimizar(texto)
    assert "12.345.678/0001-95" in r.texto
    assert not [e for e in r.tarjadas if e.tipo == "PROTOCOLO"]


def test_registro_em_conselho_inteiro(anon):
    """Número, dígito e sufixo do registro ficam sob a tarja; a sigla do sistema funcional e a do
    conselho com a UF, que sem o número não identificam ninguém, não."""
    saida = anon.anonimizar("Matrícula SIAPE 1234567, OAB/SP 123.456, CRM-PE 12345 e COREN-DF 12345-P.").texto
    for p in ["1234567", "123.456", "12345", "12345-P"]:
        assert p not in saida, saida
    for p in ["SIAPE", "OAB/SP", "CRM-PE", "COREN-DF"]:
        assert p in saida, saida
