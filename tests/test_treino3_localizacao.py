"""Endereços atípicos, quase-identificadores, contatos e veículos do órgão e de empresas.

Moradias rurais, de aldeia, de ocupação e de pessoas em situação de rua descritas por referência, e não
por logradouro e número; endereços no exterior; lotes de assentamento; coordenadas da moradia;
quase-identificadores por função comunitária, língua ou origem. Do lado da precisão: endereço, CEP e
telefone do órgão no rodapé repetido a cada página, contatos e endereços de empresa, canais do órgão
(inclusive celular e provedor gratuito) e veículos oficiais citados no singular, em tabela da frota ou
em leilão. Os exemplos são fictícios.
"""

import pytest

from themis_lgpd import Anonimizador
from themis_lgpd.reconhecedores.base import ReconhecedorPadroes
from themis_lgpd.reconhecedores.localizacao import ReconhecedorEndereco
from themis_lgpd.reconhecedores.sensiveis import QUASE_IDENTIFICADORES


def _enderecos(texto):
    return [texto[d.inicio:d.fim] for d in ReconhecedorEndereco().detectar(texto) if d.tipo == "ENDERECO"]


def _quase(texto):
    return [texto[d.inicio:d.fim] for d in ReconhecedorPadroes("q", QUASE_IDENTIFICADORES).detectar(texto)]


#: Timbre de documento expedido pelo órgão: algumas regras de precisão só valem nele.
TIMBRE = "PREFEITURA MUNICIPAL DE SERRA ALTA\nSECRETARIA MUNICIPAL DE ADMINISTRAÇÃO\n\n"


def _tipos(anon, texto, trecho):
    """Tipos e ações das entidades que cobrem ``trecho``."""
    i = texto.index(trecho)
    return {(e.tipo, e.acao) for e in anon.analisar(texto) if e.inicio <= i and i + len(trecho) <= e.fim}


# ---------------------------------------------------------------------------- moradias sem logradouro
@pytest.mark.parametrize("texto,proibidos,visiveis", [
    # Campo de moradia com referência descritiva; o território fica fora.
    ("Endereço: Aldeia Pirajuí, casa de barro ao lado da escola indígena, Terra Indígena Serra Azul",
     ["Pirajuí", "casa de barro", "escola indígena"], ["Terra Indígena Serra Azul"]),
    ("Residência: Comunidade Remanso, segunda casa depois do campo de futebol", ["Remanso", "campo de futebol"], []),
    # Ponto de pernoite em campo de formulário e em relato.
    ("Local de pernoite: Praça das Mangueiras, banco próximo ao coreto.", ["Mangueiras", "coreto"], []),
    ("O usuário pernoita sob o Viaduto das Andorinhas, perto da escada rolante. Recusou acolhimento.",
     ["Andorinhas", "escada rolante"], ["Recusou acolhimento"]),
    ("Dorme debaixo da marquise da antiga rodoviária e trabalha como chapa.", ["marquise da antiga rodoviária"],
     ["trabalha como chapa"]),
    # Povoado com casa sem número e posição da casa.
    ("residente no Povoado Canafístula, casa sem número, terceira à direita depois do açude, município de Itaúna",
     ["Canafístula", "terceira à direita depois do açude"], ["município de Itaúna"]),
    # Localidade seguida da casa e da distância.
    ("2. LOCALIZAÇÃO\nlocalidade Barro Branco, casa de taipa perto do riacho, a 8 km da escola municipal",
     ["Barro Branco", "casa de taipa", "8 km"], []),
    # Comunidade ribeirinha: margem do rio e casa.
    ("Localização: Comunidade Boa Fé, margem esquerda do rio Tapará, casa 6", ["Boa Fé", "Tapará", "casa 6"], []),
    # Linha das colônias do Sul com quilômetro.
    ("Moradora da Linha Bela Vista, s/n, km 12, interior do município.", ["Bela Vista", "km 12"], ["interior"]),
    # Propriedade seguida do córrego.
    ("residente no Sítio Pau-Ferro, Córrego da Onça, município de Itaúna", ["Pau-Ferro", "Córrego da Onça"],
     ["município de Itaúna"]),
    # Ocupação com beco e ponto de referência.
    ("residente na Ocupação Esperança Viva, beco 5, casa 21, vizinha à igreja, bairro Pedreira",
     ["Esperança Viva", "beco 5", "21"], []),
    # Unidade de abrigo.
    ("Acolhida no abrigo municipal, unidade habitacional 112 do setor B, com os dois filhos.", ["112"], []),
])
def test_moradia_descrita_por_referencia(anon, texto, proibidos, visiveis):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"
    for v in visiveis:
        assert v in saida, f"{v!r} deveria ficar visível em: {saida!r}"


@pytest.mark.parametrize("texto,proibidos", [
    # Complementos atípicos.
    ("Endereço: Rua Sete de Abril, 310, fundos, quarto 2", ["310", "quarto 2"]),
    ("Endereço: Avenida Atlântica, 55, 3º andar, sobreloja", ["55", "3º andar"]),
    ("Endereço: Rua Pioneiros, 90, Edifício Porto di Mare, apto 701", ["90", "701"]),
    # Endereço abreviado e sem pontuação, em caixa alta.
    ("END R CORONEL LIMA 455 AP 12 B SAO JOSE", ["455", "AP 12"]),
    ("End.:Travessa Boa Sorte,77,2ºandar Bairro:Centro", ["77", "2ºandar"]),
    # Hífen de fim de linha dentro do nome do logradouro.
    ("residente na Rua Antônio Ma- \nchado, 1.204, casa C, bairro Vila Rica", ["1.204", "casa C"]),
    # Endereço de Marabá: folha, quadra e lote.
    ("residente na Folha 22, Quadra 9, Lote 14, CEP 68500-000", ["Folha 22", "Quadra 9", "Lote 14"]),
])
def test_endereco_urbano_atipico(anon, texto, proibidos):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


@pytest.mark.parametrize("texto,proibidos", [
    ("Último endereço no país de origem: Calle 22 con Carrera 15, casa nº 8, Barquisimeto",
     ["Calle 22", "Carrera 15", "nº 8"]),
    ("Último endereço no Haiti: Rue Toussaint, nº 31, Ruelle Espoir, Gonaïves", ["Toussaint", "31"]),
    ("Informou que a avó mora no bairro San Martín, calle Sucre esquina Miranda, em Cobija.",
     ["calle Sucre esquina Miranda"]),
    ("Morava no setor Las Flores, calle principal, casa 12.", ["calle principal", "casa 12"]),
])
def test_endereco_no_exterior(anon, texto, proibidos):
    saida = anon.anonimizar(texto).texto
    for p in proibidos:
        assert p not in saida, f"vazou {p!r} em: {saida!r}"


def test_cruzamento_estrangeiro_sem_residencia_nao_e_endereco():
    assert _enderecos("A feira ocorre na calle Sucre esquina Miranda, no centro de Cobija.") == []


def test_lote_de_assentamento(anon):
    texto = ("O requerente ocupa o lote 37 do Projeto de Assentamento Santa Luzia desde 2012. Os confrontantes do "
             "lote 36 e do lote 38 confirmaram a posse.")
    saida = anon.anonimizar(texto).texto
    for lote in ("lote 37", "lote 36", "lote 38"):
        assert lote not in saida, saida


@pytest.mark.parametrize("texto", [
    "O lote 2 do pregão eletrônico foi adjudicado à empresa vencedora.",
    "Itens do lote 3: cadeiras e mesas escolares.",
])
def test_lote_de_licitacao_nao_e_endereco(texto):
    assert _enderecos(texto) == []


def test_coordenadas_da_moradia(anon):
    saida = anon.anonimizar("A família reside no sítio, nas coordenadas 3°45'10\" S, 52°20'05\" W, desde 2019.").texto
    assert "52°20'05" not in saida and "3°45'10" not in saida, saida


def test_coordenadas_de_obra_ficam_legiveis():
    assert _enderecos("A cabeceira da ponte fica nas coordenadas 3°45'10\" S, 52°20'05\" W, conforme o projeto.") == []


@pytest.mark.parametrize("texto", [
    # Uso coletivo do espaço, sem pessoa determinada.
    "A equipe observou mais pessoas pernoitando na área do antigo terminal.",
    # Comunidade atendida pela unidade pública.
    "Fica inaugurada a UBS da comunidade rural Sítio Lagoa Funda.",
    # Patrimônio e página na internet não são propriedades rurais.
    "O Sítio Histórico da Serra Velha recebeu visitantes.",
    "O edital está disponível no Sítio Eletrônico da Prefeitura.",
    # Equipamento coletivo da comunidade.
    "A Comunidade Boa Vista, casa de farinha comunitária, recebeu o forno novo.",
    # Rodovia e quilômetro de obra.
    "A ponte sobre o rio Claro, na BR-163, km 410, foi concluída.",
    # Número que integra o nome da via, em norma que denomina logradouro.
    "Fica denominada Rua Professor Ivo Lemos a atual Rua Projetada 7 do Loteamento Jardim Primavera.",
    # Expressões que não são endereço.
    "O fiscal passou na minha rua na terça-feira às 10h.",
])
def test_texto_sem_endereco_pessoal(texto):
    assert _enderecos(texto) == [], _enderecos(texto)


# ---------------------------------------------------------------------------- quase-identificadores
@pytest.mark.parametrize("texto,trecho", [
    ("a intérprete foi a única falante de pomerano entre os voluntários da paróquia, segundo o relatório",
     "única falante de pomerano entre os voluntários da paróquia"),
    ("é a única vendedora boliviana do box 2.310 da feira", "única vendedora boliviana do box 2.310"),
    ("a única professora da escola fluente em kaingang", "única professora da escola fluente em kaingang"),
    ("O cacique da Aldeia Pirajuí acompanhou a visita.", "cacique da Aldeia Pirajuí"),
    ("conforme declaração da presidente da Associação de Pescadores do Lago Azul", "presidente da Associação de "
                                                                                   "Pescadores do Lago Azul"),
    ("A agente comunitária de saúde da microárea 7 confirmou a residência.",
     "agente comunitária de saúde da microárea 7"),
    ("O carroceiro que recolhe recicláveis na Rua do Porto toda noite viu o carro.",
     "carroceiro que recolhe recicláveis na Rua do Porto toda noite"),
    ("Trabalha como guardador de carros em frente à Igreja de São Bento aos domingos.",
     "guardador de carros em frente à Igreja de São Bento aos domingos"),
    ("o mototaxista que faz a linha do porto no turno da noite", "mototaxista que faz a linha do porto no turno da noite"),
    ("o motorista da rota Barreiro–sede do turno vespertino", "motorista da rota Barreiro–sede do turno vespertino"),
    ("É o responsável pela cantina do Bloco 3 aos sábados.", "responsável pela cantina do Bloco 3"),
    ("a enfermeira que faz a sala de curativos às terças na UBS Itapoã Velha",
     "enfermeira que faz a sala de curativos às terças na UBS Itapoã Velha"),
])
def test_quase_identificador_por_funcao_lingua_ou_origem(texto, trecho):
    assert any(trecho in q for q in _quase(texto)), _quase(texto)


@pytest.mark.parametrize("texto", [
    "A presidente da Câmara abriu a sessão.",
    "O vendedor deverá emitir a nota fiscal no ato da entrega.",
    "Os carroceiros cadastrados receberão o auxílio no mês passado.",
    "Solicito o nome do responsável pelo setor de compras da Secretaria.",
])
def test_funcao_sem_individualizacao_nao_e_quase_identificador(texto):
    assert _quase(texto) == []


# ---------------------------------------------------------------------------- contatos e veículos pessoais
@pytest.mark.parametrize("texto,proibido", [
    ("A filha pode ser contatada pelo telefone (47) 99812-\n3344.", "3344"),
    ("Contatos: WeChat: rosa_lins77", "rosa_lins77"),
    ("Telegram: joaquim.prado", "joaquim.prado"),
    ("O veículo VW Gol, placa RXT-\n2B19, estava estacionado.", "2B19"),
    ("uma caminhonete de placa paraguaia AB 123 CD foi vista na saída", "AB 123 CD"),
    ("camioneta com placa boliviana 4410-KTR", "4410-KTR"),
    # RENAVAM sem a palavra-chave, na ficha de vistoria em coluna.
    ("VISTORIA\nQTR4B56\n48151623427\n9BWZZZ377VT004251\nproprietário: Joana Prado", "48151623427"),
])
def test_contato_e_veiculo_pessoal_tarjados(anon, texto, proibido):
    saida = anon.anonimizar(texto).texto
    assert proibido not in saida, saida


def test_aplicativo_sem_identificador_nao_e_perfil(anon):
    saida = anon.anonimizar("Telegram: não possui").texto
    assert "não possui" in saida


# ---------------------------------------------------------------------------- rodapé e timbre do órgão
OFICIO_COM_RODAPE = (
    "PREFEITURA MUNICIPAL DE SERRA ALTA\nSECRETARIA MUNICIPAL DE ASSISTÊNCIA SOCIAL\n\n"
    "Ofício nº 15/2026\n\nSenhora Coordenadora,\n\nEncaminhamos o relatório da família de Lúcia Nogueira.\n\n"
    "Rua das Palmeiras, 100 – Centro – Serra Alta/SC – CEP 89990-000 – Tel. (49) 3555-1000\nPágina 1 de 2\n\n"
    "PREFEITURA MUNICIPAL DE SERRA ALTA\n\nAtenciosamente,\n\nCarla Menezes\nSecretária Municipal\n\n"
    "Rua das Palmeiras, 100 – Centro – Serra Alta/SC – CEP 89990-000 – Tel. (49) 3555-1000\nPágina 2 de 2"
)


def test_rodape_do_orgao_fica_legivel(anon):
    r = anon.anonimizar(OFICIO_COM_RODAPE)
    for trecho in ("Rua das Palmeiras, 100", "Serra Alta/SC", "89990-000", "(49) 3555-1000"):
        assert r.texto.count(trecho) == 2, r.texto
    assert "Lúcia Nogueira" not in r.texto and "Carla Menezes" not in r.texto


def test_endereco_do_orgao_na_ultima_linha_apos_o_cargo(anon):
    texto = ("GOVERNO DO ESTADO DO TOCANTINS\nSECRETARIA DA CULTURA\n\nRelação de oficinas aprovadas.\n\n"
             "Paulo Rezende – Diretor de Fomento\nQuadra 102 Norte, Avenida LO-4, Lote 8 – Palmas/TO – CEP 77006-000")
    saida = anon.anonimizar(texto).texto
    assert "Lote 8" in saida and "77006-000" in saida, saida


def test_endereco_do_destinatario_no_fim_continua_tarjado(anon):
    texto = ("PREFEITURA MUNICIPAL DE SERRA ALTA\nSECRETARIA DE FAZENDA\n\nNotificamos o débito de IPTU.\n\n"
             "Ao Senhor\nRaimundo Teles\nRua dos Ipês, 44 – Centro – Serra Alta/SC")
    saida = anon.anonimizar(texto).texto
    assert "Ipês, 44" not in saida, saida


# ---------------------------------------------------------------------------- contatos do órgão e de empresa
CONTATOS_DO_ORGAO = [
    # Cabeçalho de mensagem com nome do setor ou sem nome exibido.
    ("De: Coordenação de Saúde Mental <saudemental@saude.ms.gov.br>\nData: 10/02/2026", "saudemental@saude.ms.gov.br"),
    ("Para: vigilancia.sanitaria@saude.ms.gov.br; nucleo.dst@saude.ms.gov.br\nAssunto: inspeção",
     "nucleo.dst@saude.ms.gov.br"),
    # Celular qualificado como do órgão ou anunciado entre os canais do órgão.
    ("Informações pelo WhatsApp institucional (65) 99876-1100.", "(65) 99876-1100"),
    ("Denúncias pelo Disque 181 ou pelo WhatsApp (65) 99876-1200.", "(65) 99876-1200"),
    ("Informações: (96) 99001-2233 (WhatsApp da Comissão de Contratação).", "(96) 99001-2233"),
    ("Plantão da Defesa Civil: 199 e (27) 99777-1212.", "(27) 99777-1212"),
    # E-mail da comissão hospedado em provedor gratuito, com o órgão citado.
    ("Os autos estão disponíveis na Comissão de Licitação ou pelo e-mail cpl.serraalta@gmail.com.",
     "cpl.serraalta@gmail.com"),
    # Rótulo "Contato:" com e-mail de domínio público sem nome de pessoa.
    ("Contato: (48) 3221-0000 | vigilancia.ambiental@saude.sc.gov.br", "(48) 3221-0000"),
    # Telefone logo após a designação do setor.
    ("Texto: Renata Alves – Assessoria de Imprensa da Fundação – (91) 3204-5500", "(91) 3204-5500"),
    # Canal anunciado no início do período.
    ("Atendimento presencial do SIC: Rua Quinze, 80, das 8h às 14h; telefone (31) 3333-2000.", "(31) 3333-2000"),
    # Pedido de resposta feito pelo órgão.
    ("Solicita-se resposta no prazo de dez dias pelo e-mail nucleo.defesa@defensoria.go.def.br.",
     "nucleo.defesa@defensoria.go.def.br"),
]


@pytest.mark.parametrize("texto,contato", CONTATOS_DO_ORGAO)
def test_contato_do_orgao_fica_legivel(anon, texto, contato):
    r = anon.anonimizar(TIMBRE + texto)
    assert contato in r.texto, r.texto
    assert any(e.tipo == "CONTATO_INSTITUCIONAL" and e.acao == "alertar" for e in r.entidades)


@pytest.mark.parametrize("texto,contato", [
    ("Para: Joana Pereira <joana.pereira@saude.ms.gov.br>", "joana.pereira@saude.ms.gov.br"),
    ("As fotos podem ser tiradas pelo celular do leiloeiro, (11) 98888-7766.", "(11) 98888-7766"),
    ("Contato por WhatsApp: (95) 99110-4455.", "(95) 99110-4455"),
    ("Para contato com a assistida: (34) 99100-2020.", "(34) 99100-2020"),
    ("Dúvidas: atendimento.prefeitura@gmail.com", "atendimento.prefeitura@gmail.com"),
])
def test_contato_pessoal_continua_tarjado(anon, texto, contato):
    assert contato not in anon.anonimizar(texto).texto


def test_email_de_fornecedor(anon):
    texto = TIMBRE + "As ordens de fornecimento serão enviadas ao e-mail vendas@ferragenspinheiro.com.br."
    assert ("CONTATO_EMPRESA", "alertar") in _tipos(anon, texto, "vendas@ferragenspinheiro.com.br")


# ---------------------------------------------------------------------------- endereços do órgão e de empresa
@pytest.mark.parametrize("texto,trecho,tipo", [
    ("CONTRATADA: Construtora Boa Obra Ltda., CNPJ 12.345.678/0001-95, com sede na Rua do Comércio, 45, Sala 3, "
     "Centro, Lajeado/RS.", "Rua do Comércio, 45", "ENDERECO_EMPRESA"),
    ("Local do fato: Padaria Pão de Ouro, Avenida Central, 900, loja 2", "Avenida Central, 900", "ENDERECO_EMPRESA"),
    ("EMPREGADOR\nRazão social: Laticínios Vale Verde Ltda.\nCNPJ: 12.345.678/0001-95\nEndereço: Rua da Usina, 300",
     "Rua da Usina, 300", "ENDERECO_EMPRESA"),
    ("Atendimento presencial do SIC: Rua Quinze, 80, das 8h às 14h.", "Rua Quinze, 80", "ENDERECO_INSTITUCIONAL"),
    ("Os donativos são recebidos no Galpão da Defesa Civil, na Rua do Mercado, 50, das 8h às 18h.",
     "Rua do Mercado, 50", "ENDERECO_INSTITUCIONAL"),
    ("Data: 05/03/2026     Local: Auditório da Regional de Ensino – Rua Ceará, 210, Iguatu/CE", "Rua Ceará, 210",
     "ENDERECO_INSTITUCIONAL"),
])
def test_endereco_de_empresa_ou_do_orgao_fica_legivel(anon, texto, trecho, tipo):
    r = anon.anonimizar(TIMBRE + texto)
    assert trecho in r.texto, r.texto
    assert any(e.tipo == tipo for e in r.entidades), [(e.tipo, e.valor) for e in r.entidades]


def test_endereco_do_trabalhador_no_formulario_continua_tarjado(anon):
    texto = ("EMPREGADOR\nRazão social: Laticínios Vale Verde Ltda.\nCNPJ: 12.345.678/0001-95\n"
             "Nome do trabalhador: Gilson Rocha\nEndereço: Rua das Hortas, 41")
    assert "Hortas, 41" not in anon.anonimizar(texto).texto


# ---------------------------------------------------------------------------- veículos oficiais
@pytest.mark.parametrize("texto,valores", [
    ("A viatura QWE2R34, da Delegacia Regional, foi recolhida para reparo.", ["QWE2R34"]),
    ("O caminhão basculante oficial da Secretaria de Obras, placa RTY5U67, foi cedido.", ["RTY5U67"]),
    ("A unidade móvel Van Saúde na Comunidade, placa SAQ1W23, percorreu 3 mil km.", ["SAQ1W23"]),
    ("com inclusão do ônibus placa PLM3K45 no plano de abastecimento da frota", ["PLM3K45"]),
    ("A van adaptada da Policlínica, RENAVAM 70315926482, chassi 9BD12345678901234, voltou a operar.",
     ["70315926482", "9BD12345678901234"]),
])
def test_veiculo_oficial_no_singular_fica_legivel(anon, texto, valores):
    saida = anon.anonimizar(TIMBRE + texto).texto
    for v in valores:
        assert v in saida, saida


def test_lotes_de_leilao_de_bens_da_frota(anon):
    texto = ("PREFEITURA MUNICIPAL DE SERRA ALTA\n\nEDITAL DE LEILÃO Nº 3/2026\n\nLeilão de veículos inservíveis da "
             "frota municipal.\n\nLote | Bem | Placa | RENAVAM | Lance mínimo\n"
             "01 | caminhonete, 2010 | ABC1D23 | 48151623427 | R$ 12.000,00")
    saida = anon.anonimizar(texto).texto
    assert "ABC1D23" in saida and "48151623427" in saida, saida


def test_leilao_de_veiculos_apreendidos_continua_tarjado(anon):
    texto = ("EDITAL DE LEILÃO DE VEÍCULOS APREENDIDOS E NÃO RETIRADOS\n\nLote | Placa | RENAVAM\n"
             "01 | ABC1D23 | 48151623427")
    saida = anon.anonimizar(texto).texto
    assert "ABC1D23" not in saida and "48151623427" not in saida, saida


@pytest.mark.parametrize("texto,placa", [
    ("O declarante conduzia o carro do vizinho, placa KLM4N56, quando a viatura chegou.", "KLM4N56"),
    ("A viatura colidiu com a motocicleta de placa OPQ7R89.", "OPQ7R89"),
])
def test_veiculo_particular_continua_tarjado(anon, texto, placa):
    assert placa not in anon.anonimizar(TIMBRE + texto).texto


@pytest.mark.parametrize("texto,valor", [
    # No pedido do cidadão, a placa da viatura aponta o servidor que a conduzia.
    ("Solicito informações sobre o condutor da viatura de placa QWE2R34, que me abordou ontem.", "QWE2R34"),
    # A empresa citada no pedido costuma ser a própria requerente.
    ("Represento a Construtora Boa Obra Ltda., CNPJ 12.345.678/0001-95, com sede na Rua do Comércio, 45.",
     "Comércio, 45"),
    ("Nossa empresa enviou a proposta pelo e-mail vendas@ferragenspinheiro.com.br e não teve retorno.",
     "vendas@ferragenspinheiro.com.br"),
    # O número que o cidadão cita ao lado do canal do órgão costuma ser o dele.
    ("Liguei para o 0800 do INSS e pedi retorno no (61) 99887-1122.", "(61) 99887-1122"),
    ("Dúvidas sobre o meu caso: (61) 3344-2211, falar com Joana.", "(61) 3344-2211"),
    ("Moro perto da Secretaria de Saúde e uso o e-mail saude.joana@gmail.com.", "saude.joana@gmail.com"),
])
def test_no_pedido_do_cidadao_continua_tarjado(anon, texto, valor):
    assert valor not in anon.anonimizar(texto).texto


# ---------------------------------------------------------------------------- números públicos
@pytest.mark.parametrize("texto,trecho", [
    ("Nota fiscal com chave de acesso 4219 0801 1223 3300 0199 5500 1000 0123 4510 0098 7650 anexada.",
     "4219 0801 1223 3300 0199 5500 1000 0123 4510 0098 7650"),
    ("O ginásio foi construído com recursos do Convênio nº 887766/2020.", "887766/2020"),
    ("conforme o subitem 7.2.1.4 do Termo de Referência", "7.2.1.4"),
    ("nomeado para o cargo em comissão de Assessor, símbolo CC-2, a partir de 1º de março", "CC-2"),
])
def test_numero_publico_fica_legivel(anon, texto, trecho):
    assert trecho in anon.anonimizar(TIMBRE + texto).texto


def test_perfil_maximo_tarja_contato_de_empresa():
    anon = Anonimizador(perfil="maxima")
    saida = anon.anonimizar(TIMBRE + "As ordens de fornecimento serão enviadas ao e-mail "
                                     "vendas@ferragenspinheiro.com.br.").texto
    assert "vendas@ferragenspinheiro.com.br" not in saida
