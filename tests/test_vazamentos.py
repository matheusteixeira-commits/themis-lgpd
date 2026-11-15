"""Regressão dos vazamentos encontrados na revisão do projeto original — nenhum pode voltar."""

import pytest

CASOS = [
    # (texto, trechos que NÃO podem sobrar na saída)
    ("A requerente Maria Aparecida Souza, filha de Antônio Pereira, informou que Carlos Eduardo Lima a ameaçou.",
     ["Maria", "Aparecida", "Souza", "Antônio", "Pereira", "Carlos", "Eduardo", "Lima"]),
    ("meu nome é jose carlos de oliveira e quero informações", ["jose", "carlos", "oliveira"]),
    ("MARIA APARECIDA SOUZA REQUER CÓPIA DO PROCESSO", ["MARIA", "APARECIDA", "SOUZA"]),
    ("Atenciosamente,\nBeatriz Helena de Souza Matos", ["Beatriz", "Helena", "Matos"]),
    ("Fico no aguardo, vlw!\n\nAbraço, Thiago.", ["Thiago"]),
    ("cpf 52998224725 e cpf com espaço 529 982 247 25", ["52998224725", "529 982 247 25"]),
    ("CPF quebrado 529.982.\n247-25 no fim da linha", ["529.982", "247-25"]),
    ("CPF 123.456.789-00 (dígito inválido, mas formatado)", ["123.456.789-00"]),
    ("CPF 1Z3.456.789-OO lido por OCR", ["1Z3.456.789-OO"]),
    ("Contato: joao.silva [arroba] gmail [ponto] com", ["joao.silva"]),
    ("Contato: joao.silva @ gmail . com", ["joao.silva"]),
    ("Meu RG é o 12.345.678-9 e o processo é o 44920/2024.", ["12.345.678-9", "44920/2024"]),
    ("Nutricionista CRN-3 88421, psicóloga CRP-06 123456, fisioterapeuta CREFITO-3 12345-F.",
     ["88421", "123456", "12345-F"]),
    ("Advogado inscrito na oab/sp 123456; médica crm-df 12.345; inscrita na OAB sob o nº 654.321.",
     ["123456", "12.345", "654.321"]),
    ("Foram inscritas as CDAs 2023.0012.345 e 2023.0012.346; os CPFs 529.982.247-25, 111.444.777-35 e "
     "123.456.789-09 constam do processo.", ["2023.0012.346", "111.444.777-35", "123.456.789-09"]),
    ("RG 1.234.567 SSP/DF e meu rg é MG-18.442.903", ["1.234.567", "18.442.903"]),
    ("CNH 01234567890 e PIS 123.45678.90-1", ["01234567890", "45678"]),
    ("título de eleitor 0123 4567 8901 e cartão SUS 898 0012 3456 7890", ["4567 8901", "3456 7890"]),
    ("Chave PIX: 61999998888. Agência 1234-5 conta corrente 12345-6.", ["61999998888", "1234-5", "12345-6"]),
    ("Veículo placa JKL-1A23 e RENAVAM 12345678901, nascido em 12/03/1985.", ["JKL-1A23", "12345678901", "12/03/1985"]),
    ("minha data de nascimento é 22/03/1988 e meu niver é 14/05/1962", ["22/03/1988", "14/05/1962"]),
    ("CPF 529\u200b.982.247-25 e email jo\u200bao@gov.br", ["982.247", "gov.br"]),
    ("email: јоао@gov.br (letras cirílicas)", ["јоао"]),
    ("acessou do IP 189.40.12.7 e postou em https://facebook.com/joao.silva.123", ["189.40.12.7", "joao.silva"]),
    ("Processo nº 0701234-56.2024.8.07.0001 e SEI 00410.002123/2024-11", ["0701234", "002123"]),
    ("Contato: (61) 99999-8888, (11) 9540-7859 e 61 3333-4444", ["99999-8888", "9540-7859", "3333-4444"]),
    ("Endereço: Quadra 12, Conjunto B, Casa 45, CEP 72300-100", ["Casa 45", "72300-100"]),
    ("moro na SHIS QI 09 Conjunto 12 Casa 15, Lago Sul", ["QI 09", "Casa 15"]),
    ("domiciliado na Rua das Tulipas, 88, Bairro Vila Nova, Joinville - SC", ["Tulipas", "88"]),
    ("matrícula SIAPE 1984235 e OAB/DF 76.541", ["1984235", "76.541"]),
    ("a ocorrência é a 2023-88741 e o protocolo de número 2023/118742", ["88741", "118742"]),
    ("CID F41.1 e diagnosticado com esclerose múltipla", ["F41.1", "esclerose"]),
    ("Minha filha tem autismo e eu faço tratamento psiquiátrico.", ["autismo", "psiquiátrico"]),
    ("Sofro violência doméstica e tenho medida protetiva.", ["violência doméstica", "medida protetiva"]),
    ("OCR colou a sigla: CPF529.982.247-25 e RG12345678", ["529.982", "12345678"]),
    ("taxa paga através da conta 104/3392-1 para liberar os autos", ["104/3392", "3392-1"]),
    ("Requerente: Maria Aparecida Souza\nCPF 529.982.247-25", ["Maria", "529.982"]),
]


@pytest.mark.parametrize("texto,proibidos", CASOS)
def test_nada_vaza(anon, texto, proibidos):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


def test_mascaramento_parcial_nao_deixa_digitos(anon):
    """Bug original: 'CNH 0<TELEFONE>' — sobra de dígito quando duas regras se sobrepõem."""
    saida = anon.anonimizar("CNH 01234567890, SUS 898 0012 3456 7890, título 0123 4567 8901").texto
    restos = [tok for tok in saida.replace(",", " ").split() if any(c.isdigit() for c in tok)]
    assert restos == [], saida


def test_cnpj_mantido_no_perfil_lai_e_tarjado_no_maximo(anon, anon_maxima):
    texto = "Contrato com a empresa CNPJ 12.ABC.345/01DE-35."
    assert "12.ABC.345/01DE-35" in anon.anonimizar(texto).texto
    assert "12.ABC.345/01DE-35" not in anon_maxima.anonimizar(texto).texto


@pytest.mark.parametrize("texto", [
    "Lei Maria da Penha (Lei nº 11.340/2006).",
    "O Hospital Regional de Taguatinga ampliou o atendimento.",
    "A política de saúde mental do DF prevê atendimento para depressão.",
    "Solicito informações sobre a Lei nº 12.527/2011 e o Edital 85/2009.",
    "Nota fiscal 7421 vinculada ao empenho 2023NE00456.",
    "Os nomes são citados no relatório anual de 2024.",
])
def test_nao_tarja_informacao_publica(anon, texto):
    r = anon.anonimizar(texto)
    assert r.tarjadas == [], [(e.tipo, e.valor) for e in r.tarjadas]
