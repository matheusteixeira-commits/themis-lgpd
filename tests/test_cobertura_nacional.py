"""Cobertura nacional: endereços, municípios, identificadores, saúde e nomes de todo o país.

Cada caso registra um formato que vazava antes da ampliação para além do Distrito Federal, ou um
texto de interesse público que não pode ser tarjado (excesso de tarja também é defeito: esconde
informação que a LAI manda publicar).
"""

import pytest

from themis_lgpd.reconhecedores.localizacao import ReconhecedorLocalidade, municipio_em

VAZAMENTOS = [
    # Endereços urbanos com abreviações, milhar e complementos
    ("Resido na Av. Gov. Agamenon Magalhães, 1.234, apto 501, Recife/PE.", ["Agamenon", "1.234", "501"]),
    ("Endereço: Trav. Padre Eutíquio, 230, Batista Campos, Belém/PA", ["Eutíquio", "230"]),
    ("Correspondência para Pça. da Liberdade, 45, sala 12, Belo Horizonte/MG", ["Liberdade, 45", "sala 12"]),
    # Ruas numeradas ou com letra (Goiânia, Palmas, Manaus, conjuntos habitacionais)
    ("Moro na Rua 15, nº 230, Setor Oeste, Goiânia/GO.", ["nº 230"]),
    ("Endereço: Rua B-15, Quadra 30, Lote 10, Palmas/TO", ["Quadra 30", "Lote 10"]),
    # Zona rural e localidades regionais
    ("Residente no Sítio Boa Esperança, zona rural de Caruaru/PE.", ["Boa Esperança"]),
    ("Moro no Povoado Bela Vista, município de Itabaiana/SE.", ["Bela Vista"]),
    ("Endereço: Linha 7, Lote 7, Gleba 11, Cacoal/RO", ["Lote 7", "Gleba 11"]),
    ("Resido no Assentamento Santa Rita, lote 12, Marabá/PA.", ["Santa Rita", "lote 12"]),
    ("Moradora do Ramal do Cupuaçu, km 8, Tefé/AM.", ["Cupuaçu", "km 8"]),
    # Rodovias estaduais de todas as regiões
    ("Resido na PE-060, km 10, Sítio Novo Horizonte.", ["PE-060, km 10"]),
    ("Moro no km 64 da BR-153, Chácara 5.", ["km 64", "Chácara 5"]),
    ("Endereço: RS-122, km 45, Caxias do Sul/RS", ["RS-122, km 45"]),
    # Município como local de residência, inclusive em minúsculas
    ("Eu moro em campinas desde 2010.", ["campinas"]),
    ("O servidor reside em Feira de Santana.", ["Feira de Santana"]),
    # Identificadores de abrangência nacional
    ("Meu benefício do INSS NB 123.456.789-0 foi suspenso.", ["123.456.789-0"]),
    ("Benefício previdenciário nº 1318609139 cessado.", ["1318609139"]),
    ("Veículo RENAVAM 12345678901 (dígito inválido, mas com a palavra-chave).", ["12345678901"]),
    ("Renavan: 0091.4728.630 do meu carro.", ["0091.4728.630"]),
    ("Número do chassi 9BWZZZ377VT004251.", ["9BWZZZ377VT004251"]),
    ("Recibo do CAR MT-5107925-1A2B.3C4D.5E6F.7A8B.9C0D.1E2F.3A4B.5C6D.", ["5107925-1A2B"]),
    ("Prontuário médico 2891163 do Hospital Regional.", ["2891163"]),
    ("Meu filho, RA 123456789-X, foi transferido.", ["123456789-X"]),
    ("Inscrição imobiliária 01.23.456.0789.001 do meu imóvel.", ["01.23.456.0789.001"]),
    ("Servidora MASP 1234567-8 e ID funcional 4455667-1.", ["1234567-8", "4455667-1"]),
    ("Transportador RNTRC 012345678 e guia CADASTUR 21.123456.10-0001.", ["012345678", "123456"]),
    ("Certidão de nascimento: termo 4521, livro A-32, folha 118.", ["4521"]),
    # Processos de sistemas estaduais
    ("Processo SEI 1500.01.0012345/2024-12 (MG) e 3900000017.000123/2023-45 (PE).", ["0012345", "000123"]),
    ("Expediente 019.1234.2024.0001234-56 da Bahia.", ["0001234-56"]),
    ("PROA 24/1200-0012345-6 no RS e e-protocolo 21.456.789-0 no PR.", ["0012345", "21.456.789-0"]),
    ("Proc. Adm. 4471/2023 e SGPe SEA 00012345/2024.", ["4471/2023", "00012345/2024"]),
    # Saúde: medicamentos, procedimentos, CID-11 e listas de CID
    ("Minha filha usa insulina glargina e cloridrato de metformina 500mg.", ["glargina", "metformina"]),
    ("Faço uso de fluoxetina 20mg desde 2020.", ["fluoxetina"]),
    ("Minha mãe faz tratamento com adalimumabe na rede estadual.", ["adalimumabe"]),
    ("Tenho CID F32.1, F41.1 e G40 conforme laudo.", ["F32.1", "F41.1", "G40"]),
    ("Laudo com C.I.D. 6A70.1 anexo.", ["6A70.1"]),
    ("Fiz laqueadura tubária em 2019 e tenho endometriose profunda.", ["laqueadura", "endometriose"]),
    ("Meu marido sofreu infarto agudo do miocárdio.", ["infarto", "miocárdio"]),
    # Nomes em CAIXA ALTA com sobrenome fora das listas
    ("REQUERENTE: BENEDITA FERREIRA LINS", ["BENEDITA", "LINS"]),
    ("Assinado: RAIMUNDA NONATA BEZERRA XAVIER", ["NONATA", "XAVIER"]),
    ("Eu, WELLINGTON JHONATAN DE SOUZA, solicito.", ["JHONATAN", "SOUZA"]),
    ("MARIA DAS GRAÇAS QUIRINO ARRUDA pede revisão.", ["GRAÇAS", "QUIRINO", "ARRUDA"]),
    ("Sou ODETE GUIMARÃES KRAEMER e solicito.", ["KRAEMER"]),
    # Prenomes regionais (IBGE)
    ("A requerente Quitéria Lustosa pede cópia.", ["Quitéria", "Lustosa"]),
    ("eu, cicera damiana, solicito informações.", ["cicera", "damiana"]),
]


@pytest.mark.parametrize("texto,proibidos", VAZAMENTOS)
def test_nada_vaza(anon, texto, proibidos):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


PUBLICOS = [
    # Municípios com nome de pessoa, citados como cidade
    "A Prefeitura Municipal de Dom Eliseu/PA publicou o edital.",
    "O Distrito Industrial de Vitória do Jari abriga 35 empresas.",
    "A Secretaria de Obras de Dom Expedito Lopes recapeou a avenida.",
    "A Câmara Municipal de José Bonifácio aprovou o orçamento.",
    # Homenageados em nomes de rua
    "A Rua Professora Maria Clara será recapeada no próximo mês.",
    "A Rua Coronel Antônio Pinheiro foi interditada para obras.",
    # Município cujo nome começa por tipo de propriedade rural
    "A Secretaria de Obras de Sítio Novo divulgou o cronograma.",
    # Órgãos com "Fazenda" e naturalidade (estado, não residência)
    "À Secretaria de Estado de Fazenda do Distrito Federal.",
    "Concluí o mestrado, mas sou natural do Paraná.",
    # Rodovias e localidades coletivas em notícia de interesse público
    "As obras de duplicação da GO-060 entre os quilômetros 10 e 40 foram concluídas.",
    "O Assentamento Santa Rita recebeu investimentos do Incra.",
    "A Comunidade Quilombola Pedra Branca foi certificada pela Fundação Palmares.",
    # Palavras que se confundiam com componentes de endereço ("mas" → "MA" + "s")
    "Todos os outros imóveis da rua fazem o mesmo, mas só nós recebemos a multa.",
    "Não há registros de minha passagem pela instituição nos sistemas consultados.",
    "Solicito a segunda via e se o agendamento eletrônico está disponível.",
    # Medicamento em pedido sobre estoque: interesse público, apenas sinalizado
    "Falta insulina glargina nas UBS do estado.",
    "O adalimumabe foi incorporado ao SUS em 2019.",
]


@pytest.mark.parametrize("texto", PUBLICOS)
def test_texto_publico_permanece(anon, texto):
    r = anon.anonimizar(texto)
    assert r.texto == texto, [(e.tipo, e.origem, e.valor) for e in r.entidades if e.acao == "tarjar"]


@pytest.mark.parametrize("texto", [
    "O pedido de Paulo Afonso Ribeiro foi negado.",  # pessoa com nome de município
    "Requerente: José Bonifácio Andrade",
])
def test_pessoa_com_nome_de_municipio_continua_tarjada(anon, texto):
    assert "[NOME]" in anon.anonimizar(texto).texto


@pytest.mark.parametrize("texto,nao_tarjar", [
    ("MARIA SILVA SOLICITA ACESSO AOS AUTOS.", "SOLICITA"),
    ("MARIA SILVA PROCURADORA DO ESTADO", "PROCURADORA"),
    ("ANA COSTA INFORMOU QUE NAO RECEBEU.", "INFORMOU"),
    ("PEDRO ALVES GOSTARIA DE SABER", "GOSTARIA"),
])
def test_nome_em_caixa_alta_nao_avanca_sobre_verbos_e_cargos(anon, texto, nao_tarjar):
    saida = anon.anonimizar(texto).texto
    assert "[NOME]" in saida and nao_tarjar in saida, saida


def test_alerta_amplo_nao_e_descartado_pelo_municipio_contido(anon):
    texto = "Quem foi o atendente do guiche 4 na unidade de Campo Grande no dia 12/05/2024 as 10h?"
    tipos = {e.tipo for e in anon.analisar(texto) if e.acao == "alertar"}
    assert {"QUASE_IDENTIFICADOR", "LOCALIDADE"} <= tipos


def _localidades(texto):
    return [(d.tipo, d.origem, texto[d.inicio:d.fim]) for d in ReconhecedorLocalidade().detectar(texto)]


def test_municipio_com_uf_confere_a_uf():
    ok = [d for d in ReconhecedorLocalidade().detectar("Evento em Joinville - SC.") if d.origem.endswith("uf")]
    errado = [d for d in ReconhecedorLocalidade().detectar("Evento em Joinville - BA.") if d.origem.endswith("uf")]
    assert ok[0].validado is True and errado[0].validado is False and ok[0].score > errado[0].score


@pytest.mark.parametrize("texto,esperado", [
    ("Moro em campinas.", ("ENDERECO", "localidade:residencia-municipio", "campinas")),
    ("Fica no município de Sorriso.", ("LOCALIDADE", "localidade:municipio", "Sorriso")),
    ("Recife (PE) registrou queda.", ("LOCALIDADE", "localidade:municipio-uf", "Recife (PE)")),
    ("Moro no Paraná.", ("LOCALIDADE", "localidade:residencia-estado", "Paraná")),
])
def test_classificacao_de_municipios(texto, esperado):
    assert esperado in _localidades(texto)


@pytest.mark.parametrize("texto", ["Natal é a capital.", "A Rua dos Andradas fica no centro.", "Ana Maria Santos"])
def test_municipio_ambiguo_isolado_nao_e_sinalizado(texto):
    assert not [x for x in _localidades(texto) if x[1].startswith("localidade:municipio")]


def test_municipio_em():
    texto = "Prefeitura de São Felipe D'Oeste"
    inicio = texto.index("São")
    assert municipio_em(texto, inicio) == len(texto)
    assert municipio_em(texto, 0) is None
