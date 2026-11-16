"""Contatos, endereços e veículos do órgão; endereços residuais e quase-identificadores em documentos oficiais.

Telefone e e-mail de setor, endereço de sede ou de unidade e placa da frota oficial não são dados
pessoais: ficam legíveis no perfil LAI e são sinalizados para revisão (tipos da categoria
``INSTITUCIONAL``). Celular, e-mail com nome de pessoa e contato em qualificação de pessoa continuam
tarjados. Os exemplos são fictícios.
"""

import pytest

from themis_lgpd import Anonimizador
from themis_lgpd.reconhecedores import institucional
from themis_lgpd.reconhecedores.base import ReconhecedorPadroes
from themis_lgpd.reconhecedores.financeiro import VEICULOS
from themis_lgpd.reconhecedores.localizacao import ReconhecedorEndereco
from themis_lgpd.reconhecedores.sensiveis import QUASE_IDENTIFICADORES


def _tipos(anon, texto, trecho):
    """Tipos e ações das entidades que cobrem ``trecho``."""
    i = texto.index(trecho)
    return {(e.tipo, e.acao) for e in anon.analisar(texto) if e.inicio <= i and i + len(trecho) <= e.fim}


# ---------------------------------------------------------------------------- contatos do órgão
CONTATOS_DO_ORGAO = [
    ("Dúvidas poderão ser esclarecidas pelo telefone (64) 3218-4400 ou pelo e-mail protocolo.geral@itaguara.go.gov.br.",
     ["(64) 3218-4400", "protocolo.geral@itaguara.go.gov.br"]),
    ("Informações: Coordenação de Vigilância Sanitária – (75) 3602-1188 – visa.municipal@saude.ba.gov.br",
     ["(75) 3602-1188", "visa.municipal@saude.ba.gov.br"]),
    ("A equipe permanece à disposição pelo telefone institucional (51) 3288-9010.", ["(51) 3288-9010"]),
    ("3. Telefone da unidade: (98) 3221-5070.", ["(98) 3221-5070"]),
    ("Atendimento ao contribuinte: 0800 642 1199 ou sac.tributos@fazenda.pi.gov.br.",
     ["0800 642 1199", "sac.tributos@fazenda.pi.gov.br"]),
    ("Núcleo de Endemias – (69) 3216-7742", ["(69) 3216-7742"]),
    ("Sugestões de pauta podem ser enviadas ao e-mail conselho.saude@vilanova.rs.gov.br.",
     ["conselho.saude@vilanova.rs.gov.br"]),
    ("Emergências devem ser comunicadas pelo telefone 193 ou pelo número (48) 3254-6100.", ["(48) 3254-6100"]),
]


@pytest.mark.parametrize("texto,contatos", CONTATOS_DO_ORGAO)
def test_contato_do_orgao_fica_legivel(anon, texto, contatos):
    r = anon.anonimizar(texto)
    for c in contatos:
        assert c in r.texto, f"tarjou contato do órgão {c!r}: {r.texto!r}"
    assert any(e.tipo == "CONTATO_INSTITUCIONAL" and e.acao == "alertar" for e in r.entidades)


def test_cabecalho_do_orgao_com_telefone_e_endereco(anon):
    texto = ("PREFEITURA MUNICIPAL DE SANTA LUZIA DO NORTE\nSECRETARIA MUNICIPAL DE ASSISTÊNCIA SOCIAL\n"
             "Rua Projetada Dois, 115 – Fone (82) 3264-7012\n\nOFÍCIO Nº 41/2026\n\nSenhora Coordenadora,")
    saida = anon.anonimizar(texto).texto
    assert "(82) 3264-7012" in saida and "Rua Projetada Dois, 115" in saida, saida


def test_telefone_do_orgao_na_linha_seguinte_ao_nome_do_orgao(anon):
    texto = "CONSELHO TUTELAR DE SERRA DOURADA – REGIÃO NORTE\nTelefone: (73) 3288-4120\n\nREQUISIÇÃO Nº 12/2026"
    assert "(73) 3288-4120" in anon.anonimizar(texto).texto


CONTATOS_PESSOAIS = [
    # Celular nunca é do órgão, mesmo ao lado de e-mail institucional.
    ("Dúvidas com o fiscal do contrato pelo celular (63) 99214-7781 ou pelo e-mail fiscal.obras@palmeiras.to.gov.br.",
     "(63) 99214-7781"),
    # Telefone fixo em campo de qualificação da pessoa.
    ("Nome: Rosalina Pereira Bastos\nEndereço: Rua das Paineiras, 312, casa 2\nTelefone: (31) 3471-2290",
     "(31) 3471-2290"),
    # Vínculo pessoal prevalece sobre a menção ao canal de atendimento.
    ("Para informações, meu telefone é (61) 3346-0912.", "(61) 3346-0912"),
    # E-mail com nome de pessoa, ainda que no domínio do órgão.
    ("Dúvidas pelo e-mail marcia.teixeira@educacao.sp.gov.br.", "marcia.teixeira@educacao.sp.gov.br"),
    # Iniciais coladas ao sobrenome.
    ("Informações pelo e-mail jcarvalho@ufpi.edu.br.", "jcarvalho@ufpi.edu.br"),
    # Provedor de uso pessoal.
    ("Dúvidas: atendimento.prefeitura@gmail.com", "atendimento.prefeitura@gmail.com"),
    # E-mail de empresa: pode ser o canal pelo qual a própria pessoa recebe a resposta.
    ("Para esclarecimentos, disponibilizamos o e-mail contato@pereiraconsultoria.com.br.",
     "contato@pereiraconsultoria.com.br"),
    # Telefone da genitora em requisição do conselho tutelar.
    ("Genitora: Valdirene Souza – telefone (73) 3288-9041", "(73) 3288-9041"),
]


@pytest.mark.parametrize("texto,contato", CONTATOS_PESSOAIS)
def test_contato_pessoal_continua_tarjado(anon, texto, contato):
    saida = anon.anonimizar(texto).texto
    assert contato not in saida, f"vazou {contato!r}: {saida!r}"


def test_mesmo_numero_recebe_a_mesma_classificacao(anon):
    texto = ("Informações: (27) 3132-8800.\n\nO pedido foi protocolado e o andamento pode ser consultado "
             "no (27) 3132-8800.")
    saida = anon.anonimizar(texto).texto
    assert saida.count("(27) 3132-8800") == 2, saida


@pytest.mark.parametrize("valor,esperado", [
    ("ouvidoria@saude.go.gov.br", True), ("cpl.licitacoes@tjpi.jus.br", True), ("frota@itaberai.go.gov.br", True),
    ("ana.lima@saude.go.gov.br", False), ("rsantos@mpf.mp.br", False), ("contato@empresa.com.br", False),
    ("clara.mendes@educacao.ba.gov.br", False), ("bezerra.coelho@tce.pe.gov.br", False),
    ("ouvidoria@hotmail.com", False),
])
def test_email_institucional(valor, esperado):
    assert institucional.email_institucional(valor) is esperado


@pytest.mark.parametrize("valor,esperado", [
    ("(61) 99876-5432", True), ("61 9 8765-4321", True), ("(61) 3344-5566", False), ("3344-5566", False),
    ("+55 11 98765-4321", True),
])
def test_celular(valor, esperado):
    assert institucional.celular(valor) is esperado


# ---------------------------------------------------------------------------- endereços do órgão
ENDERECOS_DO_ORGAO = [
    "A vista dos autos será assegurada na sede da Controladoria-Geral, situada na Avenida das Nações, nº 1.200.",
    "O atendimento será prestado no Centro de Referência da Mulher, na Rua Treze de Maio, 455, das 8h às 17h.",
    "Os documentos poderão ser entregues na Central de Atendimento ao Cidadão, situada na Rua Goiás, 77, Centro.",
    "Unidade: Policlínica Regional\nEndereço da unidade: Rua Pará, 410, Setor Sul",
]


@pytest.mark.parametrize("texto", ENDERECOS_DO_ORGAO)
def test_endereco_de_orgao_fica_legivel(anon, texto):
    r = anon.anonimizar(texto)
    assert "[ENDEREÇO]" not in r.texto, r.texto
    assert any(e.tipo == "ENDERECO_INSTITUCIONAL" for e in r.entidades)


@pytest.mark.parametrize("texto,proibido", [
    # Residência própria prevalece sobre a menção à sede.
    ("Sou servidora da Secretaria de Educação e moro na Rua Tupis, 88, perto da sede.", "Tupis, 88"),
    # Rótulo de endereço de escola num pedido: a pessoa frequenta o endereço.
    ("- Endereço da escola: Rua das Seringueiras, 240, Setor Norte", "Seringueiras, 240"),
    # Escola citada antes do endereço da família.
    ("Minha filha estuda na Escola Estadual Rio Claro, na Rua Pedro Lessa, 19, onde moramos.", "Pedro Lessa, 19"),
])
def test_endereco_pessoal_perto_de_orgao_continua_tarjado(anon, texto, proibido):
    assert proibido not in anon.anonimizar(texto).texto


def test_tabela_nao_forma_endereco():
    texto = "Logradouro | Vistorias | Interdições\nRua das Hortênsias | 7 | 2\nEstrada do Morro Alto | 11 | 4"
    assert [d for d in ReconhecedorEndereco().detectar(texto) if d.tipo == "ENDERECO"] == []


def test_codigo_de_natureza_de_despesa_nao_e_ip(anon):
    saida = anon.anonimizar("DOTAÇÃO: 12.361.0150.2010 – natureza de despesa 3.3.90.30 – fonte 1500.").texto
    assert "3.3.90.30" in saida, saida


# ---------------------------------------------------------------------------- veículos
def test_placas_da_frota_oficial_ficam_legiveis(anon):
    texto = "O transporte será feito pelos veículos oficiais de placas RTE4F12 e QMA7B30."
    saida = anon.anonimizar(texto).texto
    assert "RTE4F12" in saida and "QMA7B30" in saida, saida


def test_tabela_da_frota_oficial(anon):
    texto = ("Assunto: recadastramento da frota oficial\n\nData | Unidade | Placas\n"
             "02/03/2026 | Secretaria Municipal de Obras | PQD2C81, OKT4H09\n"
             "03/03/2026 | Guarda Civil Municipal | RRB6J55")
    saida = anon.anonimizar(texto).texto
    for placa in ("PQD2C81", "OKT4H09", "RRB6J55"):
        assert placa in saida, saida


@pytest.mark.parametrize("texto,placa", [
    ("O indiciado conduzia o automóvel Fiat Argo, placa SFG3D27, pela avenida.", "SFG3D27"),
    ("Bens declarados: motocicleta Honda Biz, ano 2018, placa PRT-4417.", "PRT-4417"),
    # Viatura e veículo particular na mesma frase: a placa do particular continua tarjada.
    ("A viatura colidiu com o carro de placa JKW8E44, conduzido pelo declarante.", "JKW8E44"),
])
def test_placa_de_veiculo_particular_continua_tarjada(anon, texto, placa):
    assert placa not in anon.anonimizar(texto).texto


@pytest.mark.parametrize("texto", [
    "Motocicleta Honda CG 160, ano 2019, placa QWE1R23, avaliada em R$ 9.000,00.",
    "Equipamento: radar fixo nº RDF-0412, aferido em 10/01/2026, local da infração próximo ao veículo.",
    "Conforme o Contrato nº 88/SEJ-2025, o veículo foi cedido.",
])
def test_sigla_e_numero_nao_sao_placa(texto):
    achados = [texto[d.inicio:d.fim] for d in ReconhecedorPadroes("v", VEICULOS).detectar(texto) if d.tipo == "PLACA"]
    assert not any(a.lower().startswith(("ano", "rdf", "sej")) for a in achados), achados


# ---------------------------------------------------------------------------- endereços residuais
def _enderecos(texto):
    return [texto[d.inicio:d.fim] for d in ReconhecedorEndereco().detectar(texto) if d.tipo == "ENDERECO"]


@pytest.mark.parametrize("texto,trecho", [
    ("Endereço: 3ª Travessa do Sossego, 52, casa A, Liberdade.", "Travessa do Sossego, 52, casa A"),
    ("residente no Povoado Lagoa Seca, casa sem número, ao lado da igreja de Santo Antônio, zona rural.",
     "Povoado Lagoa Seca, casa sem número, ao lado da igreja de Santo Antônio"),
    ("Endereço: Ocupação Vila Esperança, Rua 3, barraco 17, região norte", "Ocupação Vila Esperança, Rua 3, barraco 17"),
    ("vive com os filhos na Passarela Beija-Flor, casa 58, área de ressaca do bairro", "Passarela Beija-Flor, casa 58"),
])
def test_endereco_residual(texto, trecho):
    assert any(trecho in e for e in _enderecos(texto)), _enderecos(texto)


def test_ordem_da_via_tarjada(anon):
    saida = anon.anonimizar("Endereço: 2ª Travessa São Caetano, 14, casa B, Pernambués").texto
    assert "2ª" not in saida and "14" not in saida, saida


@pytest.mark.parametrize("texto,visivel", [
    ("O imóvel da Rua das Palmeiras, 12, encontra-se interditado.", "encontra-se"),
    ("na sala da Casa dos Conselhos, na Avenida Sete, 220, bairro Centro, reuniram-se os conselheiros", "reuniram-se"),
])
def test_pronome_obliquo_nao_e_sigla_de_uf(texto, visivel):
    assert not any(visivel in e for e in _enderecos(texto)), _enderecos(texto)


def test_colonia_penal_nao_e_endereco():
    assert _enderecos("A reeducanda cumpre pena na Colônia Penal Feminina de Abreu e Lima.") == []


# ---------------------------------------------------------------------------- quase-identificadores
def _quase(texto):
    return [texto[d.inicio:d.fim] for d in ReconhecedorPadroes("q", QUASE_IDENTIFICADORES).detectar(texto)]


QUASE = [
    # "Único" determina a pessoa mesmo sem artigo.
    ("a noticiante, única professora cega lotada na Escola Municipal Rui Barbosa, relata",
     "única professora cega lotada na Escola Municipal Rui Barbosa"),
    ("É o único apenado do bloco que atua como monitor da oficina de marcenaria da unidade.",
     "único apenado do bloco que atua como monitor da oficina de marcenaria da unidade"),
    # Aposto com "único" depois da vírgula.
    ("conforme relatado pela merendeira da escola rural da comunidade, única funcionária do local, que",
     "merendeira da escola rural da comunidade, única funcionária do local"),
    # Aposto que descreve a pessoa e oração relativa com clítico.
    ("O plantonista da delegacia naquela noite, um senhor careca de óculos que se identificou como chefe do "
     "turno, recusou o registro.",
     "plantonista da delegacia naquela noite, um senhor careca de óculos que se identificou como chefe do turno"),
    # Posto militar com unidade numerada.
    ("A soldado que dirigia a viatura do 3º Batalhão naquela madrugada chegou depressa.",
     "soldado que dirigia a viatura do 3º Batalhão naquela madrugada"),
    # Relativa com preposição.
    ("segundo a orientadora educacional do turno vespertino da escola em que a criança estuda, houve faltas",
     "orientadora educacional do turno vespertino da escola em que a criança estuda"),
    # Vizinhança.
    ("A vizinha do apartamento 41, única pessoa que visita o idoso, relatou o abandono.",
     "vizinha do apartamento 41, única pessoa que visita o idoso"),
    # Trabalho rural e aposto com "responsável".
    ("Presenciou o ato o caseiro da Chácara Recanto Verde, responsável pela guarda do gado.",
     "caseiro da Chácara Recanto Verde, responsável pela guarda do gado"),
    # Campo de formulário no início da linha.
    ("TESTEMUNHA\nVigia do turno da noite do armazém, identificado apenas pelo apelido.",
     "Vigia do turno da noite do armazém"),
    # Dias da semana enumerados.
    ("pela técnica de enfermagem do setor de hemodiálise que atende o paciente nas sessões de terça, quinta e sábado",
     "técnica de enfermagem do setor de hemodiálise que atende o paciente nas sessões de terça, quinta e sábado"),
    # Marca física distintiva.
    ("QUE o mais baixo, com cicatriz no queixo e que gaguejava ao falar, pegou o celular",
     "mais baixo, com cicatriz no queixo e que gaguejava ao falar"),
    # Candidato e caixa (no masculino, a pessoa) com sala, guichê, data e horário.
    ("sou o candidato que fez a prova prática na sala 7 do bloco C no dia 04/02/2026", "candidato que fez a prova"),
    ("Fui mal atendida pelo caixa do guichê 5 no dia 10/03/2026 às 15h20.", "caixa do guichê 5 no dia 10/03/2026"),
]


@pytest.mark.parametrize("texto,trecho", QUASE)
def test_quase_identificador_em_documento_oficial(texto, trecho):
    assert any(trecho in q for q in _quase(texto)), _quase(texto)


@pytest.mark.parametrize("texto", [
    "O servidor do plantão noturno deverá registrar as ocorrências no sistema.",
    "Compete ao diretor da escola organizar a escala do turno vespertino.",
    "A única forma de recurso é o protocolo eletrônico.",
    "Um homem de camisa azul entrou na fila às 10h.",
    "O saque foi feito no caixa eletrônico da agência no dia 10/03/2026 às 15h20.",
])
def test_descricao_generica_nao_e_quase_identificador(texto):
    assert _quase(texto) == []


def test_quase_identificador_e_sinalizado_no_perfil_lai(anon):
    texto = "A vítima, única professora surda do corpo docente do colégio, relatou o ocorrido."
    assert ("QUASE_IDENTIFICADOR", "alertar") in _tipos(anon, texto, "única professora surda do corpo docente do colégio")


def test_perfil_maximo_tarja_contato_do_orgao():
    anon = Anonimizador(perfil="maxima")
    saida = anon.anonimizar("Dúvidas pelo telefone (64) 3218-4400.").texto
    assert "(64) 3218-4400" not in saida
