"""Reconhecimento de nomes de pessoas.

Três fontes se complementam:

* **Modelo de linguagem** (spaCy ``pt_core_news_lg``, via ``SpacyNlpEngine`` do Presidio): reconhece
  nomes em texto bem escrito, inclusive nomes incomuns. As entidades do modelo passam por
  :func:`filtrar_entidade_nlp`, que remove títulos, palavras comuns e nomes de lugares.
* **Lista de nomes brasileiros** (:class:`ReconhecedorNomesLista`): cobre texto todo em minúsculas
  ou em CAIXA ALTA, em que o modelo falha, a partir de prenomes e sobrenomes frequentes.
* **Gatilhos de contexto** (:class:`ReconhecedorNomesContexto`): nomes logo após expressões como
  "meu nome é", "requerente:", "Sr." ou "Atenciosamente,", inclusive quando isolados, e as formas
  próprias de documentos oficiais: rótulos de campo, atos de pessoal, nome antes da matrícula,
  bloco de assinatura, células de tabela, iniciais de crianças e apelidos.

Nomes que homenageiam pessoas em instituições, logradouros, prêmios e municípios
(:func:`contexto_nao_pessoal`) não são tratados como pessoa.

As listas de prenomes, sobrenomes e nomes ambíguos ficam em ``themis_lgpd/dados`` e são geradas por
``scripts/gerar_listas_nomes.py``.
"""

from __future__ import annotations

from bisect import bisect_right
from functools import cache, lru_cache
from importlib import resources

import regex as re

from ..texto import dobrar as _dobrar
from .base import CONTEXTUAL, NER, Deteccao

#: :func:`themis_lgpd.texto.dobrar` com memória: o reconhecimento de nomes dobra as mesmas palavras
#: muitas vezes por documento.
dobrar = lru_cache(maxsize=1 << 16)(_dobrar)

#: Palavra: letras, apóstrofos internos ("D'Ávila") e um hífen interno ("Ana-Maria").
_TOKEN = re.compile(r"\p{L}[\p{L}'’]*(?:-\p{L}[\p{L}'’]*)?")
#: Partículas que ligam partes de um nome ("Maria da Silva", "Van Dijk").
CONECTORES = frozenset({"da", "de", "do", "das", "dos", "e", "d'", "d’", "di", "del", "van", "von"})

#: Palavras que nunca iniciam nem encerram um nome de pessoa: instituições, cargos, pronomes de
#: tratamento, fórmulas de cortesia, meses, siglas de órgãos e documentos (sem acentos, minúsculas).
NAO_INICIAM_NOME = frozenset(dobrar(p) for p in [
    "secretaria", "secretario", "secretaria", "governo", "ministerio", "ministro", "departamento",
    "diretoria", "coordenacao", "gerencia", "subsecretaria", "administracao", "regional", "hospital",
    "escola", "colegio", "centro", "conselho", "tribunal", "camara", "assembleia", "policia", "corpo",
    "defensoria", "procuradoria", "controladoria", "ouvidoria", "agencia", "instituto", "fundacao",
    "universidade", "faculdade", "empresa", "companhia", "banco", "caixa", "distrito", "estado", "uniao",
    "republica", "brasil", "brasilia", "lei", "decreto", "portaria", "resolucao", "artigo", "art", "processo",
    "protocolo", "prezado", "prezada", "prezados", "senhor", "senhora", "senhores", "excelentissimo",
    "excelentissima", "ilustrissimo", "ilma", "ilmo", "atenciosamente", "cordialmente", "obrigado",
    "obrigada", "agradeco", "solicito", "venho", "gostaria", "informo", "requeiro", "declaro", "segue",
    "anexo", "assunto", "referencia", "ref", "data", "rua", "avenida", "praca", "quadra", "conjunto", "bloco",
    "setor", "lote", "casa", "edificio", "janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
    "agosto", "setembro", "outubro", "novembro", "dezembro", "segunda", "terca", "quarta", "quinta", "sexta",
    "sabado", "domingo", "hoje", "ontem", "amanha", "sim", "nao", "favor", "por", "para", "com", "sem",
    "sobre", "the", "and", "nome", "cpf", "rg", "cnh", "sei", "lai", "sus", "inss", "detran", "gdf", "cgdf",
    "seec", "ses", "sedes", "pcdf", "pmdf", "cbmdf", "adasa", "caesb", "ceb", "novacap", "terracap", "metro",
    "dftrans", "brb", "cldf", "tcdf", "stf", "stj", "tse", "tst", "trf", "tjdft", "mpdft", "mpf", "dpu",
    "agu", "cgu", "tcu", "pf", "prf", "aguardo", "fico", "grato", "grata", "reitero", "agradecemos",
    "agradeco", "permaneco", "rogo", "certo", "entao", "malgrado", "copia", "chefia", "pede", "deferimento",
    "requerente", "titular", "gestor", "gestora", "responsavel", "diretor", "diretora", "mae", "pai",
    "cidadao", "cidada", "servidor", "servidora", "vossa", "vossas", "excelencia", "senhoria", "senhorias",
    "ilustrissimos", "ilustrissimas", "inciso", "paragrafo", "alinea", "gerente", "auditor", "auditora",
    "analista", "tecnico", "tecnica", "coordenador", "coordenadora", "chefe", "presidente", "vice",
    "assessor", "assessora", "agente", "fiscal", "inspetor", "inspetora", "delegado", "delegada", "perito",
    "perita", "medico", "medica", "enfermeiro", "enfermeira", "professor", "professora", "aluno", "aluna",
    "interessado", "interessada", "solicitante", "denunciante", "segue", "seguem", "anexo", "anexos", "desde",
    "ja", "peco", "pedimos", "espero", "aguardamos", "favor", "obrigado", "obrigada", "abraco", "abracos",
    "abs", "att", "atte"
])

#: Palavras comuns que aparecem com inicial maiúscula em títulos e tabelas e nunca compõem nome de
#: pessoa; uma entidade que contenha qualquer uma delas é descartada.
PALAVRAS_COMUNS = frozenset(dobrar(p) for p in [
    "total", "totais", "geral", "gerais", "dissolvido", "dissolvida", "amoniacal", "organico", "organica",
    "informacoes", "informacao", "identificacao", "pessoa", "pessoas", "relatorio", "anexo", "item", "itens",
    "tabela", "quadro", "figura", "grafico", "resumo", "objeto", "objetivo", "objetivos", "justificativa",
    "conclusao", "introducao", "metodologia", "resultado", "resultados", "analise", "dados", "situacao",
    "status", "observacao", "observacoes", "valor", "valores", "media", "medio", "maximo", "minimo", "indice",
    "taxa", "numero", "quantidade", "unidade", "unidades", "periodo", "ano", "anos", "mes", "meses", "dia",
    "nitrogenio", "fosforo", "oxigenio", "solidos", "turbidez", "temperatura", "cor", "ph", "condutividade",
    "coliformes", "demanda", "bioquimica", "quimica", "nacional", "estadual", "municipal", "distrital",
    "federal", "publico", "publica", "social", "sociais", "urgente", "importante", "atencao", "assunto"
])

#: Cargos, profissões e papéis processuais ou administrativos ("Juiz de Direito", "Membro", "Relatora",
#: "Assistente Social", "Periciada"), siglas de registro funcional e profissional e fórmulas de
#: expediente ("Ciente", "Publique-se"). Em documentos oficiais aparecem com inicial maiúscula ao lado
#: do nome — na linha de baixo da assinatura, em colunas de tabela, em rótulos — e não o integram.
_CARGOS_E_PAPEIS = frozenset(dobrar(p) for p in [
    "juiz", "juiza", "juizo", "desembargador", "desembargadora", "magistrado", "magistrada", "promotor",
    "promotora", "procurador", "procuradora", "defensor", "defensora", "prefeito", "prefeita", "vereador",
    "vereadora", "deputado", "deputada", "senador", "senadora", "governador", "governadora", "ministra", "reitor",
    "reitora", "pro-reitor", "pro-reitora", "vice-reitor", "vice-reitora", "superintendente", "ouvidor", "ouvidora",
    "corregedor", "corregedora", "corregedor-geral", "controlador", "controladora", "conselheiro", "conselheira",
    "escrivao", "escriva", "oficial", "soldado", "sargento", "tenente", "capitao", "comandante", "investigador",
    "investigadora", "membro", "membros", "relator", "relatora", "psicologo", "psicologa", "assistente",
    "nutricionista", "farmaceutico", "farmaceutica", "fisioterapeuta", "fonoaudiologo", "fonoaudiologa",
    "dentista", "cirurgiao", "cirurgia", "cirurgia-dentista", "cirurgiao-dentista", "odontologo", "odontologa",
    "pedagogo", "pedagoga", "educador", "educadora", "orientador", "orientadora", "tesoureiro", "tesoureira",
    "contador", "contadora", "engenheiro", "engenheira", "advogado", "advogada", "estagiario", "estagiaria",
    "escriturario", "escrituraria", "motorista", "vigilante", "atendente", "recepcionista", "administrador",
    "administradora", "economista", "arquiteto", "arquiteta", "veterinario", "veterinaria", "psiquiatra",
    "pediatra", "neuropediatra", "neurologista", "cardiologista", "geriatra", "ortopedista", "clinico", "obstetra",
    "ginecologista", "oftalmologista", "infectologista", "anestesista", "radiologista", "legista",
    "medico-legista", "terapeuta", "diretor-presidente", "diretor-geral", "diretora-geral", "secretario-geral",
    "secretaria-geral", "secretario-executivo", "secretaria-executiva", "paciente", "vitima", "testemunha",
    "declarante", "depoente", "indiciado", "indiciada", "acusado", "acusada", "investigado", "investigada",
    "requerido", "requerida", "periciado", "periciada", "reeducando", "reeducanda", "apenado", "apenada",
    "sentenciado", "sentenciada", "custodiado", "custodiada", "adolescente", "crianca", "genitor", "genitora",
    "conjuge", "contribuinte", "beneficiario", "beneficiaria", "segurado", "segurada", "usuario", "usuaria",
    "proprietario", "proprietaria", "condutor", "condutora", "infrator", "infratora", "candidato", "candidata",
    "empossado", "empossada", "nomeado", "nomeada", "matricula", "mat", "matr", "siape", "masp", "crm",
    "coren", "cress", "crp", "crefito", "crfa", "cro", "crf", "crea", "oab", "nis", "pis", "pasep", "cns", "ctps",
    "cnpj", "ltda", "eireli", "epp", "ciente", "assinatura", "visto", "publique-se", "registre-se", "cumpra-se",
    "intime-se", "notifique-se", "arquive-se", "encaminhe-se", "requerente", "recorrente", "recorrido",
    "recorrida", "titular", "gestor", "gestora", "responsavel", "diretor", "diretora", "mae", "pai", "cidadao",
    "cidada", "servidor", "servidora", "gerente", "auditor", "auditora", "analista", "tecnico", "tecnica",
    "coordenador", "coordenadora", "chefe", "assessor", "assessora", "agente", "fiscal", "inspetor", "inspetora",
    "delegado", "delegada", "perito", "perita", "medico", "medica", "aluno", "aluna", "interessado", "interessada",
    "solicitante", "denunciante", "senhor", "senhora", "prezado", "prezada", "secretario", "ministro",
])
#: Órgãos e unidades que encabeçam documentos ("PREFEITURA DE …", "MUNICÍPIO DE …", "PODER JUDICIÁRIO").
NAO_INICIAM_NOME = NAO_INICIAM_NOME | _CARGOS_E_PAPEIS | frozenset(dobrar(p) for p in [
    "prefeitura", "municipio", "municipios", "superintendencia", "coordenadoria", "delegacia", "promotoria",
    "subprefeitura", "autarquia", "consorcio", "comando", "batalhao", "guarda", "juizado", "tabelionato", "junta",
    "orgao", "entidade", "poder", "judiciario", "legislativo", "executivo",
])

#: Vocabulário administrativo que aparece com inicial maiúscula em cabeçalhos, nomes de unidades e
#: tabelas de documentos oficiais ("Superintendência de Recursos Humanos", "Gerência de Vida
#: Funcional", "Norma Interna") e não compõe nome de pessoa.
PALAVRAS_COMUNS = PALAVRAS_COMUNS | frozenset(dobrar(p) for p in [
    "saude", "servico", "servicos", "pessoal", "recursos", "humanos", "gestao", "controle", "funcional",
    "pagamento", "area", "areas", "ambiental", "civil", "militar", "penal", "escolar", "basica", "basico",
    "especial", "especializado", "especializada", "juridico", "juridica", "administrativo", "administrativa",
    "financeiro", "financeira", "orcamento", "contabil", "tributario", "previdencia", "previdenciario",
    "assistencia", "vigilancia", "sanitaria", "sanitario", "epidemiologia", "epidemiologica", "urgencia",
    "emergencia", "internacao", "clinicas", "hospitalar", "ambulatorio", "ambulatorial", "farmacia",
    "laboratorio", "comissao", "comite", "nucleo", "divisao", "secao", "gabinete", "assessoria", "arquivo",
    "expediente", "cadastro", "frequencia", "licitacao", "contratos", "compras", "patrimonio", "almoxarifado",
    "transporte", "transportes", "obras", "infraestrutura", "planejamento", "cultura", "esporte",
    "esportes", "turismo", "ambiente", "agricultura", "pecuaria", "agropecuaria", "agropecuario", "defesa",
    "seguranca", "transito", "justica", "cidadania", "direitos", "direito", "mulher", "mulheres", "juventude",
    "idoso", "idosos", "familia", "familias", "desenvolvimento", "habitacao", "trabalho", "emprego",
    "comunicacao", "tecnologia", "inovacao", "ciencia", "pesquisa", "extensao", "graduacao", "reitoria", "sede",
    "norma", "normas", "interna", "interno", "instrucao", "ordem", "nota", "oficio", "memorando", "despacho",
    "parecer", "edital", "ata", "termo", "contrato", "convenio", "aditivo", "extrato", "aviso", "comunicado",
    "circular", "laudo", "atestado", "declaracao", "certidao", "requerimento", "sumario", "prontuario", "ficha",
    "notificacao", "boletim", "ocorrencia", "auto", "infracao", "exame", "avaliacao", "conduta", "carceraria",
    "educacao", "profissionais", "profissional", "consignacao", "consignacoes", "enfermagem", "medicina",
    "tropical", "geriatria", "pediatria", "psiquiatria", "maternidade", "policlinica", "componente", "estrategia",
    "atendimento", "acolhimento", "protecao", "promocao", "regulacao", "auditoria", "corregedoria", "plantao",
    "escala", "turno", "noturno", "diurno", "mensal", "anual", "vara", "comarca", "forum", "cartorio",
    "criminal", "execucao", "execucoes", "infancia", "receita", "tesouro", "construtora", "comercial",
    "comercio", "industria", "distribuidora", "panificadora", "laticinios", "transportadora", "cerealista",
    "armazens", "engenharia", "consultoria", "associacao", "cooperativa", "sindicato", "federacao", "casas",
    "programa", "projeto", "plano", "politica", "sistema", "rede", "portal", "unico", "unica", "padrao",
    "classe", "nivel", "categoria", "grau", "faixa", "simbolo", "cargo", "funcao", "equipe", "polo", "titulo",
    "eleitor", "carteira", "identidade", "documento", "habilitacao", "passaporte", "cartao", "conta",
])

#: Pronome de tratamento ou título que precede o nome; não faz parte do trecho tarjado.
TITULOS = re.compile(
    r"^(?:sr|sra|srta|dr|dra|prof|profa|profª|exmo|exma|ilmo|ilma|sr\.ª|senhor|senhora|doutor|doutora|"
    r"professor|professora|dom|dona|seu)\.?$", re.IGNORECASE)

#: Palavras que, imediatamente antes de um nome próprio, indicam lei, logradouro ou instituição
#: ("Lei Maria da Penha", "Escola Paulo Freire"): o nome homenageia alguém, não identifica o titular
#: dos dados. Entre a palavra e o nome pode haver um título ou patente do homenageado ("Rua Professora
#: Maria Clara", "Avenida Governador Valadares", "Escola Estadual Coronel Antônio Pinheiro").
_EXCECOES_ANTES = re.compile(
    r"(?:\blei|\brua|\bavenida|\bav\.|\bpra[çc]a|\balameda|\btravessa|\blargo|\bestrada|\bescola|\bcol[ée]gio|"
    r"\bhospital|\binstituto|\bfunda[çc][ãa]o|"
    r"\bedif[íi]cio|\bed\.|\bcentro|\bparque|\best[áa]dio|\bgin[áa]sio|\bviaduto|\bponte|\brodovia|\baeroporto|"
    r"\buniversidade|\bfaculdade|\bteatro|\bbiblioteca|\bmuseu|\bmemorial|\bpr[êe]mio|"
    r"\bprograma|\bprojeto|\bcondom[íi]nio|\bresidencial|\bvila|\bjardim|\bbairro|\bsetor|\bclube|"
    r"\bigreja|\bpar[óo]quia|\bcreche|\bhemocentro|\bcomplexo|\bterminal|\besta[çc][ãa]o)"
    r"(?:\s+(?:estadual|municipal|federal))?"
    r"(?:\s+(?:professora?|prof[aª]?\.?|doutora?|dra?\.|coronel|cel\.|general|marechal|major|capit[ãa]o|tenente|"
    r"almirante|brigadeiro|sargento|padre|pe\.|frei|irm[ãa]|monsenhor|c[ôo]nego|bispo|dom|dona|deputad[oa]|"
    r"senador[a]?|governador[a]?|prefeit[oa]|presidente|desembargador[a]?|ministr[oa]|vereador[a]?|"
    r"engenheir[oa]|maestro|bar[ãa]o|visconde|comendador[a]?|juiz|ju[íi]za))?\s*$",
    re.IGNORECASE,
)
#: Designação institucional de município antes do nome ("Prefeitura Municipal de", "Secretaria de
#: Obras de", "Distrito Industrial de", "Comarca de"): o nome seguinte, se for de município da lista do
#: IBGE ("Dom Eliseu", "Vitória do Jari", "Paulo Afonso"), é a cidade, não uma pessoa.
_MUNICIPIO_INSTITUCIONAL = re.compile(
    r"\b(?:prefeitura(?:\s+municipal)?|c[âa]mara\s+(?:municipal|de\s+vereadores)|munic[íi]pio|cidade|comarca|"
    r"distrito\s+industrial|secretaria(?:\s+municipal)?(?:\s+d[eao]s?\s+[\wÀ-ú]+(?:\s+e\s+[\wÀ-ú]+)?)?|"
    r"hospital(?:\s+(?:regional|municipal|geral))?|f[óo]rum|vara(?:\s+[\wÀ-ú]+){0,3}|regi[ãa]o|zona\s+rural|"
    r"aeroporto|rodovi[áa]ria|campus)\s+d[eoa]\s*$",
    re.IGNORECASE,
)
#: Título que inicia nomes de municípios ("Dom Eliseu", "Padre Bernardo", "Governador Valadares").
_TITULO_ANTES = re.compile(r"\b(?:dom|dona|padre|frei|presidente|governador|senador|deputado|professor|coronel|"
                           r"general|marechal|major|capit[ãa]o|tenente|doutor|bar[ãa]o|visconde|conde|almirante|"
                           r"ministro|monsenhor|bispo)\s+$", re.IGNORECASE)
#: "São Paulo", "Santa Maria": topônimos e santos. Sensível a maiúsculas, para não confundir com o
#: verbo "são".
_SANTOS_ANTES = re.compile(r"\b(?:São|Santa|Santo|SÃO|SANTA|SANTO)\s*$")

#: Núcleo de nome de órgão, unidade ou equipamento público, logradouro, norma, prêmio ou programa, que
#: costuma homenagear pessoas ("Unidade Básica de Saúde Doutor Fulano", "EE Professora Fulana",
#: "Penitenciária Estadual Fulano de Tal", "Prêmio Professor Fulano"). Inclui as siglas usuais de
#: unidades de saúde, de ensino e de assistência social.
_NUCLEOS_INSTITUICAO = frozenset(dobrar(p) for p in [
    "lei", "rua", "avenida", "av", "praca", "alameda", "travessa", "largo", "estrada", "rodovia", "viaduto",
    "ponte", "escola", "colegio", "creche", "hospital", "maternidade", "policlinica", "ambulatorio", "clinica",
    "posto", "pronto-socorro", "hemocentro", "unidade", "centro", "instituto", "fundacao", "universidade",
    "faculdade", "penitenciaria", "presidio", "cadeia", "colonia", "complexo", "edificio", "parque", "estadio",
    "ginasio", "aeroporto", "terminal", "estacao", "teatro", "biblioteca", "museu", "memorial", "auditorio",
    "galeria", "premio", "medalha", "comenda", "trofeu", "programa", "projeto", "patrulha", "casa",
    "condominio", "residencial", "loteamento", "vila", "jardim", "bairro", "clube", "igreja", "paroquia",
    "acude", "barragem", "ubs", "ubsf", "usf", "upa", "caps", "capsi", "capsad", "cras", "creas", "cerest",
    "ee", "eeb", "eef", "eem", "eeef", "eefm", "eeefm", "emef", "emei", "emeif", "cmei", "cei", "cef", "ced",
    "ciep", "caic", "etec", "ue", "ueb",
])
#: Qualificadores de nome de instituição escritos em minúsculas ("escola municipal", "hospital regional").
_QUALIFICADORES_INSTITUICAO = frozenset({
    "estadual", "municipal", "federal", "regional", "distrital", "publico", "publica", "geral",
})
#: Títulos e patentes que precedem o nome do homenageado ("Hospital Regional Dr. Fulano", "EEEFM
#: Presidente Fulano", "Policlínica Enfermeira Fulana", "CRAS Irmã Fulana").
_HONORIFICOS = frozenset(dobrar(p) for p in [
    "dr", "dra", "doutor", "doutora", "prof", "profa", "profª", "professor", "professora", "dom", "dona", "padre",
    "pe", "frei", "irma", "irmao", "madre", "monsenhor", "conego", "bispo", "arcebispo", "cardeal", "papa",
    "pastor", "coronel", "cel", "general", "marechal", "major", "capitao", "tenente", "sargento", "cabo",
    "soldado", "almirante", "brigadeiro", "comandante", "deputado", "deputada", "senador", "senadora",
    "governador", "governadora", "prefeito", "prefeita", "presidente", "desembargador", "desembargadora",
    "ministro", "ministra", "vereador", "vereadora", "engenheiro", "engenheira", "enfermeiro", "enfermeira",
    "maestro", "barao", "baronesa", "visconde", "viscondessa", "conde", "condessa", "comendador", "comendadora",
    "juiz", "juiza", "santo", "santa", "sao", "beato", "beata",
])

#: Palavra, sigla com pontos ("U.E.", "Dr.") ou travessão, para percorrer o nome de uma instituição.
_PALAVRA_CADEIA = re.compile(r"\p{L}[\p{L}'’ª-]*\.?(?:\p{L}\.)*|[–—]")


def _instituicao_antes(texto: str, inicio: int) -> bool:
    """Indica se o nome que começa em ``inicio`` encerra o nome de uma instituição ou logradouro.

    Percorre, na mesma linha e para a esquerda, palavras com inicial maiúscula, conectores e títulos
    até encontrar um núcleo de :data:`_NUCLEOS_INSTITUICAO`: "Unidade Básica de Saúde da Família
    Doutor", "HOSPITAL REGIONAL DR.", "Penitenciária Estadual", "Escola Municipal Professora Maria".
    Para em pontuação, em palavra minúscula ou gramatical e em cargo ou papel ("o paciente", "Médico
    Perito Dr."), que indicam menção a uma pessoa. Um travessão só é atravessado logo antes de um
    título ("Fundação de Vigilância em Saúde – Dra. Fulana").
    """
    linha = texto.rfind("\n", 0, inicio) + 1
    janela = max(linha, inicio - 120)
    palavras = list(_PALAVRA_CADEIA.finditer(texto, janela, inicio))
    pos, anterior_titulo, vistas = inicio, False, 0
    gramaticais = _palavras_gramaticais()
    for m in reversed(palavras):
        if texto[m.end():pos].strip(" \t"):
            return False
        pos = m.start()
        palavra = m.group()
        if palavra in "–—":
            if not anterior_titulo:
                return False
            anterior_titulo = False
            continue
        dob = dobrar(palavra.rstrip(".")).replace(".", "")
        if dob in _NUCLEOS_INSTITUICAO:
            return True
        vistas += 1
        anterior_titulo = dob in _HONORIFICOS
        if anterior_titulo or dob in CONECTORES or dob == "em" or dob in _QUALIFICADORES_INSTITUICAO:
            continue
        if not palavra[:1].isupper() or dob in _CARGOS_E_PAPEIS or dob in gramaticais or vistas > 9:
            return False
    return False


#: Linha de local e data que segue o município ("Teresina, 3 de março de 2025", "Itu/SP, 12/05/2024",
#: "Coari (AM), em 1º de julho"), ou só a UF ("Itu/SP", "Itu - SP", "Itu (SP)").
_UFS = r"(?-i:AC|AL|AM|AP|BA|CE|DF|ES|GO|MA|MG|MS|MT|PA|PB|PE|PI|PR|RJ|RN|RO|RR|RS|SC|SE|SP|TO)"
_DEPOIS_MUNICIPIO = re.compile(
    rf"(?:[ \t]*[/–-][ \t]*{_UFS}\b|[ \t]*\({_UFS}\))"
    r"|[ \t]*,[ \t]*(?:em[ \t]+)?(?:\d{1,2}[º°o]?[ \t]+de[ \t]+(?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|"
    r"agosto|setembro|outubro|novembro|dezembro)\b|\d{1,2}[./]\d{1,2}[./]\d{2,4})", re.IGNORECASE)
#: Preposição ou rótulo antes do município ("em Teresina", "Município: Coari", "Município de residência:
#: Coari", "Naturalidade: Coari").
_LUGAR_ANTES = re.compile(
    r"(?:\bem|\bmunic[íi]pio(?:[ \t]+de[ \t]+[\wÀ-ú]+)?[ \t]*:|\bcidade[ \t]*:|\bnaturalidade[ \t]*:|"
    r"\blocal[ \t]*:)[ \t]*$", re.IGNORECASE)
#: Unidade administrativa de abrangência municipal antes de "de" ("Superintendência Regional de Ensino
#: de", "Unidade Local de Execução de", "municípios de", "etapa regional de"): entre o núcleo e o "de"
#: só há palavras com inicial maiúscula ou conectores.
_UNIDADE_DE_MUNICIPIO = re.compile(
    r"\b(?:munic[íi]pios|regional|regionais|superintend[êe]ncias?|ger[êe]ncias?|coordenadorias?|delegacias?|"
    r"unidades?|ag[êe]ncias?|n[úu]cleos?|escrit[óo]rios?|polos?|seccional|subse[çc][ãa]o|promotorias?|"
    r"defensorias?|procuradorias?|cart[óo]rios?|diretorias?|subprefeituras?|campi)"
    r"(?:[ \t]+(?-i:[A-ZÀ-Ý][\wÀ-ú]*|d[aeo]s?|e)){0,5}[ \t]+d[eoa][ \t]*$",
    re.IGNORECASE,
)
#: Separador de itens de uma enumeração de lugares ("Coari, Tefé e de Codajás").
_ITEM_SEGUINTE = re.compile(r"[ \t]*(?:,|;|[ \t]e|[ \t]ou)[ \t]+(?:(?:de|em|a)[ \t]+)?", re.IGNORECASE)
_ITEM_ANTERIOR = re.compile(r"(?:,|;|[ \t]e|[ \t]ou)[ \t]+(?:(?:de|em|a)[ \t]+)?$", re.IGNORECASE)
#: Fim de célula de tabela após o município ("Coari | 1.234", "Coari\t1.234").
_FIM_CELULA = re.compile(r"[ \t]*(?:\t|\|)")


def _municipio_inequivoco(texto: str, inicio: int) -> int | None:
    """Fim do município que começa em ``inicio``, com inicial maiúscula, e não se confunde com nome de
    pessoa ou palavra comum ("registro", "Wanderley")."""
    from .localizacao import municipio_em

    fim = municipio_em(texto, inicio) if texto[inicio:inicio + 1].isupper() else None
    if fim is None:
        return None
    nome = dobrar(texto[inicio:fim])
    if " " not in nome and (nome in prenomes() or nome in sobrenomes() or nome in ambiguos()
                            or nome in PALAVRAS_COMUNS or len(nome) < 4):
        return None
    return fim


def _municipio_vizinho(texto: str, inicio: int, fim: int) -> bool:
    """Indica se o município em ``texto[inicio:fim]`` integra uma enumeração ou coluna de municípios."""
    m = _ITEM_SEGUINTE.match(texto, fim)
    if m and _municipio_inequivoco(texto, m.end()) is not None:
        return True
    m = _ITEM_ANTERIOR.search(texto, max(0, inicio - 12), inicio)
    if m:
        palavras = list(_TOKEN.finditer(texto, max(0, m.start() - 50), m.start()))
        for p in palavras[-5:]:
            if _municipio_inequivoco(texto, p.start()) == m.start():
                return True
    if not _FIM_CELULA.match(texto, fim):
        return False
    # Coluna de tabela: a linha anterior ou a seguinte também começa por município seguido de célula.
    ini_linha = texto.rfind("\n", 0, inicio) + 1
    if texto[ini_linha:inicio].strip(" \t|•-–"):
        return False
    vizinhas = []
    if ini_linha > 0:
        vizinhas.append(texto.rfind("\n", 0, ini_linha - 1) + 1)
    proxima = texto.find("\n", fim)
    if proxima >= 0:
        vizinhas.append(proxima + 1)
    for v in vizinhas:
        recuo = len(texto[v:v + 10]) - len(texto[v:v + 10].lstrip(" \t|•-–"))
        f = _municipio_inequivoco(texto, v + recuo)
        if f is not None and _FIM_CELULA.match(texto, f):
            return True
    return False


def _municipio_em_contexto(texto: str, inicio: int) -> bool:
    """Indica se em ``inicio`` começa o nome de um município citado como lugar.

    Vale para a linha de local e data ("João Pessoa, 3 de outubro de 2025"), o município seguido da
    UF, após "em" ou rótulo ("Município: Pedro Afonso"), após unidade administrativa ("Superintendência
    Regional de Ensino de Teófilo Otoni"), após o nome de uma instituição e um travessão ("EE Dona
    Fulana – Francisco Sá") e em enumerações ou colunas de municípios.
    """
    from .localizacao import municipio_em

    fim = municipio_em(texto, inicio)
    if fim is None:
        return False
    if _DEPOIS_MUNICIPIO.match(texto, fim):
        return True
    if texto[fim:fim + 1] == " " and texto[fim + 1:fim + 2].isupper():
        return False  # "em Marília Souza": o nome continua além do município
    janela = max(0, inicio - 80)
    if _LUGAR_ANTES.search(texto, janela, inicio) or _UNIDADE_DE_MUNICIPIO.search(texto, janela, inicio):
        return True
    travessao = _TRAVESSAO_ANTES.search(texto, max(0, inicio - 6), inicio)
    if travessao and _instituicao_antes(texto, travessao.start()):
        return True
    return _municipio_vizinho(texto, inicio, fim)


#: Travessão entre o nome de uma instituição e o do município ("Hospital Regional Fulano – Garanhuns").
_TRAVESSAO_ANTES = re.compile(r"[ \t]+[–—-][ \t]*$")


#: Expressões após as quais vem um nome de pessoa: apresentação ("meu nome é"), papéis processuais
#: ("requerente:", "réu:"), tratamento ("Sr."), fecho de mensagem ("Atenciosamente,") e parentesco
#: ("meu filho"). O nome pode estar na mesma linha ou na seguinte.
GATILHOS = re.compile(
    r"(?:\bmeu nome (?:completo )?(?:é|e)|\bme chamo|\bse chama|\bchamad[oa](?:\s+de)?|\bconhecid[oa] como|"
    r"\b(?:meus|seus|os)\s+dados(?:\s+(?:principais|pessoais|cadastrais))?\s+(?:s[ãa]o|:)|"
    r"\bdados\s+d[oa]\s+(?:requerente|titular|interessad[oa]|solicitante|servidor(?:a)?)\s+(?:s[ãa]o|:)|"
    r"\b(?:eu\s+)?sou\s+(?:o|a)\b|\beu\s+sou\b|\bem nome de|\bnomes?\s+(?:s[ãa]o|é)|"
    r"\beu,|\bnome(?:\s+completo)?(?:\s+d[oa]\s+\w+)?\s*:|\brequerente\s*:?|\binteressad[oa]\s*:?|"
    r"\bsolicitante\s*:?|\bdenunciante\s*:?|\bdenunciad[oa]\s*:?|\breclamante\s*:?|\bpaciente\s*:?|"
    r"\bservidor(?:a)?(?:\s+p[úu]blic[oa])?|\bfuncion[áa]ri[oa]|\bcolaborador(?:a)?|\bestagi[áa]ri[oa]|"
    r"\b(?:sr|sra|srta|dr|dra|prof|profa)\.|\bsenhor(?:a)?|\bdoutor(?:a)?|\bdona|\bfilh[oa] de|"
    r"\bm[ãa]e\s*:|\bpai\s*:|\bgenitor(?:a)?\s*:?|\bc[ôo]njuge\s*:?|\bassinad[oa](?:\s+eletronicamente)?\s+por|"
    r"\batenciosamente,?|\bcordialmente,?|\batt\.?,?|\batte\.?,?|\bgrat[oa],?|\bobrigad[oa],?|\bprezad[oa]s?|"
    r"\babra[çc]os?,?|\babs,?|\bbeijos?,?|\bvlw,?|\bvaleu,?|\bsauda[çc][õo]es,?|\brespeitosamente,?|"
    r"\bem nome de|\brepresentad[oa] por|\bprocurador(?:a)?\s*:?|\badvogad[oa]\s*:?|\btestemunha\s*:?|"
    r"\bv[íi]tima\s*:?|\bacusad[oa]\s*:?|\binvestigad[oa]\s*:?|\bautor(?:a)?\s*:|\br[ée]u\s*:|\bpor\s+parte\s+d[oa]|"
    r"\bmeu (?:marido|esposo|companheiro|filho|pai|irm[ãa]o|vizinho|chefe|colega)|"
    r"\bminha (?:esposa|mulher|companheira|filha|m[ãa]e|irm[ãa]|vizinha|chefe|colega)|\bsobrinh[oa]|\bnet[oa])"
    r"[ \t]*\n?[ \t]*", re.IGNORECASE)


@cache  # um item por arquivo de lista; são poucos e consultados em alternância
def _lista(nome: str) -> frozenset[str]:
    """Lista de nomes empacotada em ``themis_lgpd/dados`` (uma entrada por linha; ``#`` comenta)."""
    texto = resources.files("themis_lgpd.dados").joinpath(nome).read_text(encoding="utf-8")
    return frozenset(linha.strip() for linha in texto.splitlines() if linha.strip() and not linha.startswith("#"))


@cache
def prenomes() -> frozenset[str]:
    """Prenomes brasileiros frequentes, sem acentos e em minúsculas.

    Une a lista geral à dos prenomes mais frequentes por sexo, década e UF no Censo 2010 do IBGE
    (``prenomes_ibge.txt``, gerada por ``scripts/gerar_prenomes_ibge.py``).
    """
    return _lista("prenomes.txt") | _lista("prenomes_ibge.txt")


def sobrenomes() -> frozenset[str]:
    """Sobrenomes brasileiros frequentes, sem acentos e em minúsculas."""
    return _lista("sobrenomes.txt")


def ambiguos() -> frozenset[str]:
    """Prenomes que também são palavras comuns ("rosa", "clara", "vitoria").

    Só iniciam um nome quando escritos com inicial maiúscula e nunca são propagados isoladamente.
    """
    return _lista("nomes_ambiguos.txt")


def _capitalizado(tok: str) -> bool:
    return tok[:1].isupper()


def _tokens(texto: str) -> list[tuple[int, int, str]]:
    """Palavras do texto como ``(início, fim, palavra)``."""
    return [(m.start(), m.end(), m.group()) for m in _TOKEN.finditer(texto)]


def _so_espaco(texto: str, a: int, b: int) -> bool:
    """Indica se entre duas palavras há apenas de um a três espaços ou tabulações (sem quebra de linha)."""
    trecho = texto[a:b]
    return 0 < len(trecho) <= 3 and trecho.strip(" \t") == ""


@cache
def _palavras_gramaticais() -> frozenset[str]:
    """Palavras gramaticais do português (lista do spaCy), sem acentos."""
    from spacy.lang.pt.stop_words import STOP_WORDS

    return frozenset(dobrar(p) for p in STOP_WORDS)


#: Terminações de palavras comuns — substantivos abstratos, particípios, gerúndios, infinitivos,
#: profissões — que não completam um nome em CAIXA ALTA ("SOLICITAÇÃO", "INFORMOU", "PROCURADORA").
_SUFIXOS_NAO_NOME = ("cao", "coes", "mente", "dade", "dades", "encia", "ancia", "ismo", "agem", "avel", "ivel",
                     "dor", "dora", "dores", "doras", "ista", "istas", "ente", "entes", "ante", "antes", "ado", "ados",
                     "ada", "adas", "ido", "idos", "ida", "idas", "ando", "endo", "indo", "aram", "eram", "iram",
                     "ou", "eu", "iu", "ar", "ir")
#: Verbos e qualificações que costumam seguir o nome em requerimentos ("FULANO SOLICITA", "FULANA
#: BRASILEIRA CASADA").
_NAO_COMPLETAM_NOME = frozenset({
    "solicita", "requer", "informa", "declara", "pede", "encaminha", "reside", "brasileiro", "brasileira",
    "casado", "casada", "solteiro", "solteira", "divorciado", "divorciada", "viuvo", "viuva", "portador",
    "portadora", "inscrito", "inscrita", "nascido", "nascida", "esposa", "esposo", "marido", "conjuge",
    "companheiro", "companheira", "menor", "maior", "cpf", "rg", "oab", "matricula", "siape",
})


def _desconhecida_pode_integrar(dob: str, sufixo_ok: bool = False) -> bool:
    """Indica se uma palavra fora das listas pode integrar um nome em CAIXA ALTA.

    Com ``sufixo_ok``, ignora as terminações de :data:`_SUFIXOS_NAO_NOME`, que também ocorrem em
    sobrenomes ("RIBAMAR", "ESCOBAR", "YAMADA", "BENTES").
    """
    return (len(dob) >= 3 and dob.isalpha() and dob not in _palavras_gramaticais() and dob not in PALAVRAS_COMUNS
            and dob not in NAO_INICIAM_NOME and dob not in _NAO_COMPLETAM_NOME
            and (sufixo_ok or not dob.endswith(_SUFIXOS_NAO_NOME)))


def _desconhecida_no_nome(texto: str, toks, j: int, pn: frozenset[str], sn: frozenset[str]) -> bool:
    """Indica se a palavra ``j``, em CAIXA ALTA e fora das listas, ainda integra o nome em curso.

    Integra quando fica entre palavras de nome ("RAIMUNDA NONATA BEZERRA", "WELLINGTON JHONATAN DE
    SOUZA") ou quando, sozinha ou com até duas outras palavras desconhecidas, fecha o nome: a sequência
    vem seguida de pontuação, quebra de linha, fim do texto, palavra em minúsculas ou palavra
    gramatical ("BENEDITA FERREIRA LINS,", "MARLENE TESCH RAMLOW, matrícula", "JOSÉ DA SILVA TAVORA
    FOI"). Sobrenomes de imigrantes e indígenas raramente estão nas listas e costumam vir juntos. Não
    integra se for palavra gramatical ou comum. Palavra com terminação típica de verbo ou substantivo
    ("INFORMOU", "SOLICITAR"), que também ocorre em sobrenomes ("RIBAMAR", "YAMADA"), só integra a
    sequência que termina em pontuação, quebra de linha, cargo ou identificador — não a seguida de
    complemento ("JOSÉ SILVA INFORMOU QUE").
    """
    dob = dobrar(toks[j][2])
    if not _desconhecida_pode_integrar(dob, sufixo_ok=True):
        return False
    condicional = not _desconhecida_pode_integrar(dob)
    k, desconhecidas = j + 1, 0
    while k < len(toks) and _so_espaco(texto, toks[k - 1][1], toks[k][0]):
        tok, dob = toks[k][2], dobrar(toks[k][2])
        if dob in CONECTORES:
            k += 1
            continue
        if dob in pn or dob in sn:
            return True
        if tok.isupper() and desconhecidas < 2 and _desconhecida_pode_integrar(dob, sufixo_ok=True):
            condicional = condicional or not _desconhecida_pode_integrar(dob)
            desconhecidas += 1
            k += 1
            continue
        if condicional:
            return dob in _CARGOS_E_PAPEIS or dob in _NAO_COMPLETAM_NOME
        # A sequência de palavras desconhecidas fecha o nome se a palavra seguinte não puder continuá-lo:
        # minúscula, gramatical, cargo, documento ou qualificação ("SAMIR NAGIB CPF", "FULANO BELTRANO
        # MATRÍCULA").
        return (not tok[:1].isupper() or (dob in _palavras_gramaticais() and dob not in CONECTORES)
                or dob in NAO_INICIAM_NOME or dob in _NAO_COMPLETAM_NOME)
    return True


#: Partes finais do nome que indicam geração ou parentesco e podem ir para a linha seguinte numa
#: célula estreita ("FRANCISCO DAS CHAGAS ARAGÃO\nFILHO").
_SUFIXOS_FAMILIA = frozenset({"filho", "filha", "neto", "neta", "junior", "jr", "sobrinho", "sobrinha"})
#: Quebra de linha simples (não separa parágrafos), com espaços ou tabulações em volta.
_QUEBRA_SIMPLES = re.compile(r"[ \t]*\n[ \t]*")
#: Restante de uma célula de tabela na linha seguinte: até quatro palavras em CAIXA ALTA e o divisor.
_RESTO_DE_CELULA = re.compile(r"(?:(?:\p{Lu}[\p{L}'’-]*|d[aeo]s?|e)[ \t]+){0,3}\p{Lu}[\p{L}'’-]*[ \t]*(?:\||\t)")
#: Início de linha ou de célula antes do nome.
_INICIO_DE_CELULA = re.compile(r"(?:^|[|\t])[ \t]*$", re.MULTILINE)


def _inicial(texto: str, tok: tuple[int, int, str]) -> bool:
    """Indica se a palavra é a inicial de um nome ("B." em "Graziela B. Assunção")."""
    return len(tok[2]) == 1 and tok[2].isupper() and texto[tok[1]:tok[1] + 1] == "."


def _ligacao(texto: str, toks, i: int, j: int, pendentes: int, modo_caixa: bool) -> bool:
    """Indica se o token ``j`` pode continuar o nome que vai de ``i`` a ``j - 1``.

    Além do espaço simples, admite o ponto de uma inicial ("B. Assunção") e uma quebra de linha
    simples quando o nome continua com certeza na linha seguinte: a linha termina em conector
    ("FERRAZ DE\\nLIMA"), a linha seguinte começa por "Filho", "Neto" ou "Júnior", ou o nome ocupa a
    célula até o fim da linha e o restante dele fecha a célula na linha seguinte ("ANDREIA
    CRISTINA\\nBATALHA DE SOUZA | 864.694-5", "| Fulano Beltrano\\nde Tal | 5130749").
    """
    a, b = toks[j - 1][1], toks[j][0]
    if _so_espaco(texto, a, b):
        return True
    proximo = toks[j][2]
    if not modo_caixa or not (proximo[:1].isupper() or dobrar(proximo) in CONECTORES):
        return False
    if _inicial(texto, toks[j - 1]) and re.fullmatch(r"\.[ \t]{0,2}", texto[a:b]) and proximo[:1].isupper():
        return True
    if not _QUEBRA_SIMPLES.fullmatch(texto, a, b):
        return False
    if (pendentes or dobrar(proximo) in _SUFIXOS_FAMILIA) and proximo[:1].isupper():
        return True
    inicio_linha = texto.rfind("\n", 0, toks[i][0]) + 1
    caixa_alta = all(toks[k][2].isupper() for k in range(i, j))
    return (_INICIO_DE_CELULA.search(texto, inicio_linha, toks[i][0]) is not None
            and (caixa_alta or not proximo.isupper())
            and _RESTO_DE_CELULA.match(texto, b) is not None)


def _estender(texto: str, toks, i: int, modo_caixa: bool) -> int:
    """Estende um nome a partir do token ``i``, já aceito como início.

    Acrescenta palavras enquanto forem prenomes ou sobrenomes conhecidos — ou, com ``modo_caixa``,
    palavras capitalizadas e iniciais ("Graziela B. Assunção") — admitindo até dois conectores
    seguidos e no máximo nove palavras. Em texto todo em CAIXA ALTA, em que qualquer palavra parece
    nome próprio, uma palavra fora das listas só é aceita nas condições de :func:`_desconhecida_no_nome`.
    Prenomes que também são palavras comuns ("Dores", "Glória", "Luz") integram o nome quando
    escritos com inicial maiúscula ("MARIA DAS DORES FERREIRA"). O nome pode continuar na linha
    seguinte nas condições de :func:`_ligacao`.

    Returns:
        Índice do último token do nome.
    """
    pn, sn, amb = prenomes(), sobrenomes(), ambiguos()
    ultimo = i
    j = i + 1
    pendentes = 0  # conectores lidos e ainda não seguidos de um nome
    ultimo_conector = ""
    while j < len(toks) and _ligacao(texto, toks, i, j, pendentes, modo_caixa):
        tok = toks[j][2]
        dob = dobrar(tok)
        if dob in CONECTORES and pendentes < 2:
            pendentes += 1
            ultimo_conector = "e" if ultimo_conector == "e" else dob  # "e de" conta como "e"
            j += 1
            continue
        if ultimo_conector == "e" and (dob in pn or dob not in sn):
            # "Souza e João" e "Fulana e de João" são duas pessoas; "Silva e Souza" é um sobrenome composto.
            break
        ultimo_conector = ""
        nomeavel = dob in pn or dob in sn or (dob in amb and _capitalizado(tok))
        if modo_caixa and _inicial(texto, toks[j]):
            ok = True
        elif modo_caixa and tok.isupper() and len(tok) > 1:
            ok = (nomeavel and dob not in NAO_INICIAM_NOME) or _desconhecida_no_nome(texto, toks, j, pn, sn)
        elif modo_caixa:
            ok = (_capitalizado(tok) and dob not in NAO_INICIAM_NOME and dob not in CONECTORES) or nomeavel
        else:
            ok = nomeavel and dob not in NAO_INICIAM_NOME
        if not ok:
            break
        ultimo = j
        pendentes = 0
        j += 1
        if j - i > 8:
            break
    return ultimo


def _estender_contexto(texto: str, toks, i: int) -> int:
    """Estende, num contexto que já indica pessoa (rótulo de campo, papel), um nome com palavras fora
    das listas ("Nome: TAKESHI HAMADA OKUMURA").

    Segue enquanto as palavras mantiverem a caixa da primeira (CAIXA ALTA ou inicial maiúscula) e
    tiverem forma de nome (ver :func:`_forma_de_nome`), além de conectores e iniciais.

    Returns:
        Índice do último token do nome.
    """
    pn, sn, amb = prenomes(), sobrenomes(), ambiguos()
    caixa_alta = toks[i][2].isupper()
    ultimo, j, pendentes, conector = i, i + 1, 0, ""
    while j < len(toks) and j - i <= 8 and _ligacao(texto, toks, i, j, pendentes, True):
        tok, dob = toks[j][2], dobrar(toks[j][2])
        if dob in CONECTORES and pendentes < 2:
            pendentes, conector = pendentes + 1, "e" if conector == "e" else dob
            j += 1
            continue
        if conector == "e" and (dob in pn or dob not in sn):
            break  # "Fulana de Tal e Beltrano de Tal" são duas pessoas
        conector = ""
        if not _inicial(texto, toks[j]):
            if tok.isupper() != caixa_alta or not tok[:1].isupper():
                break
            if not (dob in pn or dob in sn or dob in amb or _forma_de_nome(dob, rigorosa=False)):
                break
        ultimo, pendentes = j, 0
        j += 1
    return ultimo


def contexto_nao_pessoal(texto: str, inicio: int) -> bool:
    """Indica se a palavra em ``inicio`` integra o nome de um lugar, instituição ou norma.

    Exemplos: "São Paulo", "Rua Paulo Freire", "Rua Professora Maria Clara", "Escola Maria Souza", "Lei
    Maria da Penha", "Prefeitura Municipal de Dom Eliseu", "Unidade Básica de Saúde Doutor Fulano",
    "João Pessoa, 3 de outubro de 2025". A regra é a mesma no reconhecimento de nomes, na propagação
    de valores tarjados e na verificação final.
    """
    janela = max(0, inicio - 45)
    if _EXCECOES_ANTES.search(texto, janela, inicio) or _SANTOS_ANTES.search(texto, janela, inicio):
        return True
    if _instituicao_antes(texto, inicio):
        return True
    from .localizacao import municipio_em

    # O nome do município pode começar por um título que o reconhecedor de nomes não inclui no
    # trecho ("Secretaria de Obras de Dom Expedito Lopes", "Prefeitura de Governador Valadares").
    titulo = _TITULO_ANTES.search(texto, max(0, inicio - 15), inicio)
    for ini in ([titulo.start()] if titulo else []) + [inicio]:
        if _MUNICIPIO_INSTITUCIONAL.search(texto, max(0, ini - 60), ini):
            fim = municipio_em(texto, ini)
            if fim is not None and fim > inicio:
                return True
        if _municipio_em_contexto(texto, ini):
            return True
    return False


class ReconhecedorNomesLista:
    """Nomes iniciados por prenome brasileiro conhecido, em qualquer caixa.

    Exige ao menos duas palavras de nome (prenome e sobrenome, por exemplo), o que evita tarjar
    prenomes soltos usados em outros sentidos. Prenomes ambíguos ("rosa", "clara") só iniciam um
    nome quando escritos com inicial maiúscula.
    """

    nome = "nomes:lista"

    def detectar(self, texto: str) -> list[Deteccao]:
        """Nomes encontrados no texto."""
        from .localizacao import municipio_em

        pn, amb = prenomes(), ambiguos()
        toks = _tokens(texto)
        saida: list[Deteccao] = []
        i = 0
        while i < len(toks):
            ini, _, tok = toks[i]
            dob = dobrar(tok)
            caixa = _capitalizado(tok)
            if dob in pn and dob not in NAO_INICIAM_NOME and (caixa or dob not in amb):
                fim_idx = _estender(texto, toks, i, caixa)
                n_nomes = sum(1 for k in range(i, fim_idx + 1) if dobrar(toks[k][2]) not in CONECTORES)
                if n_nomes >= 2:
                    empresa = _empresa_depois(texto, toks[fim_idx][1])
                    if not empresa and not contexto_nao_pessoal(texto, ini):
                        score = 0.8 if caixa else 0.7
                        saida.append(Deteccao(ini, toks[fim_idx][1], "NOME", score, self.nome, NER))
                        i = fim_idx + 1
                        continue
                    # O nome do município ou da empresa não recomeça na palavra seguinte ("Luís Eduardo
                    # Magalhães" não vira "Eduardo Magalhães").
                    fim = toks[fim_idx][1] if empresa else municipio_em(texto, ini)
                    if fim is not None:
                        while i + 1 < len(toks) and toks[i + 1][1] <= fim:
                            i += 1
            i += 1
        return saida


#: Rótulos de campo que, em documentos oficiais, antecedem o nome de uma pessoa: partes e
#: interessados, membros de comissão, profissionais responsáveis e familiares ("Membro:",
#: "Periciada:", "Reeducando:", "Contribuinte:", "Filiação:", "Responsável técnico:").
GATILHOS_ROTULO = re.compile(
    r"\b(?:membro|presidente|relator[a]?|secret[áa]ri[oa]|vogal|suplente|periciad[oa]|examinad[oa]|avaliad[oa]|"
    r"reeducand[oa]|apenad[oa]|sentenciad[oa]|custodiad[oa]|indiciad[oa]|sindicad[oa]|processad[oa]|autuad[oa]|"
    r"notificad[oa]|infrator[a]?|condutor[a]?|propriet[áa]ri[oa]|possuidor[a]?|contribuinte|declarante|depoente|"
    r"comunicante|noticiante|ofendid[oa]|agressor[a]?|envolvid[oa]|benefici[áa]ri[oa]|segurad[oa]|pensionista|"
    r"aposentad[oa]|dependentes?|titular|alun[oa]|estudante|educand[oa]|crian[çc]a|adolescente|usu[áa]ri[oa]|"
    r"assistid[oa]|atendid[oa]|acolhid[oa]|internad[oa]|alimentante|alimentand[oa]s?|exequente|executad[oa]|"
    r"requerid[oa]|impetrante|agravante|apelante|embargante|curador[a]?|curatelad[oa]|interditand[oa]|tutor[a]?|"
    r"companheir[oa]|espos[oa]|marido|filh[oa]s?|net[oa]s?|irm[ãa]os?|av[óô]|respons[áa]vel(?:[ \t]+(?:legal|"
    r"t[ée]cnic[oa]))?|m[ée]dic[oa](?:[ \t]+(?:respons[áa]vel|assistente|perit[oa]))?|perit[oa]|enfermeir[oa]|"
    r"assistente[ \t]+social|psic[óo]log[oa]|escriv[ãa]o?|delegad[oa]|agente|fiscal|conselheir[oa](?:[ \t]+tutelar)?|"
    r"nomead[oa]|empossad[oa]|exonerad[oa]|candidat[oa]|recebido[ \t]+por|elaborado[ \t]+por|assinatura|"
    r"nome[ \t]+(?:social|civil)|filia[çc][ãa]o|reclamad[oa]|representante(?:[ \t]+legal)?|servidor(?:\(a\)|a)?|"
    r"interessad[oa]|requerente|recorrente|recorrid[oa]|paciente|v[íi]tima|testemunhas?|acusad[oa]|investigad[oa]|"
    r"denunciad[oa])(?:\(?s\)?|es)?[ \t]*:[ \t]*\n?[ \t]*", re.IGNORECASE)

#: Papel ou ato que antecede o nome em despachos, portarias e relatórios ("a agente FULANA", "conduzido
#: por FULANO", "Exonerar FULANO", "Designar os servidores FULANO", "do Vereador Fulano de Tal").
GATILHOS_PAPEL = re.compile(
    r"(?:\b(?:[oa]s?|d[oa]s?|pel[oa]s?|a[os]?|à|às)[ \t]+(?:servidor(?:es|as|a)?|agentes?|policia(?:l|is)|"
    r"militar(?:es)?|soldados?|cabos?|sargentos?|investigador(?:es|as|a)?|escriv[ãa](?:o|es)?|perit[oa]s?|"
    r"professor(?:es|as|a)?|m[ée]dic[oa]s?|enfermeir[oa]s?|t[ée]cnic[oa]s?|analistas?|auditor(?:es|as|a)?|fiscal|"
    r"fiscais|testemunhas?|v[íi]timas?|acusad[oa]s?|indiciad[oa]s?|denunciad[oa]s?|investigad[oa]s?|adolescentes?|"
    r"crian[çc]as?|menor(?:es)?|alun[oa]s?|pacientes?|requerentes?|interessad[oa]s?|senhor(?:es|as|a)?|"
    r"candidat[oa]s?|conselheir[oa]s?|genitor(?:es|a)?|diretor(?:es|as|a)?|coordenador(?:es|as|a)?|chefe|gerente|"
    r"secret[áa]ri[oa]s?|membros?|contribuinte|declarante|condutor(?:es|a)?|propriet[áa]ri[oa]s?|"
    r"vereador(?:es|as|a)?|prefeit[oa]s?|deputad[oa]s?|senador(?:es|as|a)?|governador(?:es|a)?|ju[íi]z(?:es|a)?|"
    r"promotor(?:es|as|a)?|delegad[oa]s?|defensor(?:es|as|a)?|procurador(?:es|as|a)?|relator(?:es|as|a)?)"
    r"|\b(?:conduzid[oa]|praticad[oa]|cometid[oa]|subscrit[oa]|elaborad[oa]|formalizad[oa]|ajuizad[oa]|"
    r"impetrad[oa]|interpost[oa]|apresentad[oa]|lavrad[oa]|registrad[oa]|recebid[oa])[ \t]+por"
    r"|^[ \t]*(?:nomear|exonerar|designar|dispensar|aposentar|remover|ceder|lotar|readaptar|reintegrar|reconduzir|"
    r"demitir|destituir|empossar|admitir|contratar|promover|redistribuir|convocar|advertir|suspender|absolver|"
    r"conceder|autorizar|homologar|declarar)(?:,?[ \t]+a[ \t]+pedido,?)?(?:[ \t]+(?:[oa]s?|à|ao|aos|às))?"
    r"(?:[ \t]+(?:senhor(?:a)?|servidor(?:es|as|a)?))?)[ \t]+", re.IGNORECASE | re.MULTILINE)
#: Verbos que abrem os dispositivos de atos e decisões ("NOMEAR", "CONDENAR"), escritos em CAIXA ALTA
#: logo antes do nome: não o integram.
_VERBOS_DE_ATO = frozenset({
    "nomear", "exonerar", "designar", "dispensar", "aposentar", "remover", "ceder", "lotar", "readaptar", "reintegrar",
    "reconduzir", "demitir", "destituir", "empossar", "admitir", "contratar", "promover", "redistribuir", "convocar",
    "advertir", "suspender", "absolver", "conceder", "autorizar", "homologar", "declarar", "condenar", "pronunciar",
    "impronunciar", "julgar", "determinar", "aplicar", "arquivar", "instaurar", "revogar", "retificar", "prorrogar",
    "reconhecer", "deferir", "indeferir", "cessar", "tornar", "intimar", "notificar", "citar", "absolvo", "condeno",
})

#: Identificador ou qualificação que segue o nome de uma pessoa em atos e registros oficiais
#: ("FULANO DE TAL, matrícula", "Fulano de Tal – Matr.", "Fulano de Tal, RG", "Fulano de Tal, 42 anos").
_IDENTIFICADOR_APOS_NOME = re.compile(
    r"[ \t]*(?:,|[–—-]|\()[ \t]*(?:matr[íi]cula|matr?\.|mat\b|rg\b|r\.g\.|cpf\b|c\.p\.f\.|siape\b|masp\b|rf\b|cns\b|"
    r"ctps\b|n[ºo°.]?[ \t]*funcional|identidade\b|inscrit[oa][ \t]+no[ \t]+cpf|portador[a]?[ \t]+d[oa]|"
    r"brasileir[oa]|nascid[oa][ \t]+em|natural[ \t]+de|filh[oa][ \t]+de|\d{1,3}[ \t]+anos\b|"
    r"sexo[ \t]+(?:masculino|feminino)|(?:crm|coren|cress|crp|oab|crea|cro|crf|crefito|crfa)\b)", re.IGNORECASE)
#: Cargo ou função de pessoa ("Membro", "Secretário de Estado", "Assistente Social"). "Secretaria" sem
#: acento é o órgão, não a servidora.
_CARGO = (r"(?:(?:vice|sub|pr[óo])-?)?(?:secret(?:[áa]rio|ária)|diretor[a]?|superintendente|reitor[a]?|prefeit[oa]|"
          r"presidente|coordenador[a]?|gerente|chefe|assessor[a]?|assistente|psic[óo]log[oa]|m[ée]dic[oa]|"
          r"enfermeir[oa]|t[ée]cnic[oa]|perit[oa]|analista|agente|membro|relator[a]?|procurador[a]?|promotor[a]?|"
          r"defensor[a]?|ju[íi]z[a]?|desembargador[a]?|delegad[oa]|escriv[ãa]o?|conselheir[oa]|ouvidor[a]?|"
          r"auditor[a]?|fiscal|professor[a]?|pedagog[oa]|fisioterapeuta|fonoaudi[óo]log[oa]|nutricionista|"
          r"cirurgi[ãa]o?|dentista|odont[óo]log[oa]|farmac[êe]utic[oa]|terapeuta|educador[a]?|orientador[a]?|"
          r"inspetor[a]?|investigador[a]?|soldado|cabo|sargento|tenente|capit[ãa]o|major|coronel|comandante|"
          r"corregedor[a]?|controlador[a]?|tesoureir[oa]|contador[a]?|engenheir[oa]|arquitet[oa]|advogad[oa]|"
          r"servidor[a]?|estagi[áa]ri[oa]|escritur[áa]ri[oa]|oficial|respons[áa]vel|psiquiatra|pediatra|"
          r"neuropediatra|neurologista|geriatra|cardiologista|ortopedista|cl[íi]nic[oa]|obstetra|ginecologista|"
          r"legista|economista|administrador[a]?|motorista)\b")
#: Cargo ou função que segue o nome após vírgula ou travessão ("FULANO – Membro", "Fulano de Tal,
#: Secretário de Estado").
_CARGO_APOS_NOME = re.compile(r"[ \t]*(?:,|[–—-])[ \t]*" + _CARGO, re.IGNORECASE)
#: Linha de cargo, função ou registro sob o nome no bloco de assinatura.
_LINHA_DE_CARGO = re.compile(
    r"[ \t]*(?:" + _CARGO + r"|(?:matr[íi]cula|matr?\.|siape|masp|crm|coren|cress|crp|crefito|crfa|cro|crf|crea|"
    r"oab|cpf|rg)\b)", re.IGNORECASE)
#: Título antes do nome na assinatura ("Dra.", "Enf.ª", "Prof."); a normalização do texto converte "ª"
#: em "a".
_TITULO_ASSINATURA = re.compile(r"[ \t]*(?:(?:sr|sra|dr|dra|prof|profa|enf|enfa|psic|me|ma|esp)\.?[ªa]?[ \t]+)*",
                                re.IGNORECASE)

#: Célula de tabela em texto, separada por barra vertical ou tabulação.
_CELULA = re.compile(r"[^|\t]+")
#: CPF, inclusive mascarado ("***.938.044-**"), como conteúdo de uma célula.
_CPF_EM_CELULA = re.compile(r"(?:\d{3}|\*{3})\.(?:\d{3}|\*{3})\.(?:\d{3}|\*{3})-(?:\d{2}|\*{2})|\d{11}")
#: Identificador de pessoa como conteúdo de uma célula: CPF, matrícula com dígito verificador
#: ("864.694-5", "357760-1 A") ou número com seis dígitos ou mais.
_IDENTIFICADOR_EM_CELULA = re.compile(
    r"(?:\d{3}|\*{3})\.(?:\d{3}|\*{3})\.(?:\d{3}|\*{3})-(?:\d{2}|\*{2})|[\d.]*\d-[ \t]?[\dXx](?:[ \t]?[A-Z])?|\d{6,}")

#: Iniciais de pessoa ("K.C.P.", "M. E. S. C.", "J.V.S.C."): de duas a cinco letras maiúsculas, cada
#: uma seguida de ponto.
_INICIAIS = re.compile(r"(?<![\p{L}\d.])\p{Lu}\.(?:[ \t]?\p{Lu}\.){1,4}(?![\p{L}\d])")
#: Siglas que também se escrevem com pontos ("S.A.", "D.O.U.", "C.P.F.") e não são iniciais de pessoa.
_SIGLAS_PONTUADAS = frozenset({
    "sa", "ue", "ee", "em", "ce", "ps", "pps", "nb", "pm", "ar", "uf", "sos", "eua",
    "usa", "onu", "oms", "dou", "doe", "dom", "dje", "cpf", "rg", "cnh", "pis", "sus", "inss", "oab", "pad", "ltda",
    "cia", "me", "epp", "cnpj", "cep", "ctps", "nis", "cns", "tv", "rh", "ti", "qi", "cd", "dvd", "ok", "cef", "bb",
    "mp", "pf", "prf", "tj", "trt", "trf", "stf", "stj", "tcu", "cgu", "agu", "ibge", "mec", "sesi", "senai", "sesc",
    "senac", "ong", "eca", "clt", "cf", "cpc", "cpp", "ipva", "iptu", "icms", "fgts",
})
#: Palavra que, logo antes de duas iniciais, indica que são de uma pessoa ("o filho K. M.", "a
#: servidora A. P.").
_PESSOA_ANTES_DE_INICIAIS = re.compile(
    r"\b(?:filh[oa]s?|net[oa]s?|irm[ãa]os?|crian[çc]as?|adolescentes?|menor(?:es)?|alun[oa]s?|estudantes?|"
    r"servidor(?:es|as|a)?|testemunhas?|v[íi]timas?|pacientes?|genitor(?:es|a)?|dependentes?|usu[áa]ri[oa]s?|"
    r"senhor(?:es|as|a)?|sr\.?|sra\.?|requerentes?|interessad[oa]s?|acusad[oa]s?|investigad[oa]s?|"
    r"denunciad[oa]s?|declarantes?|enteadas?|enteados?|sobrinh[oa]s?|beb[êe]|rec[ée]m-nascid[oa]|"
    r"iniciais|alimentand[oa]s?|tutelad[oa]s?|acolhid[oa]s?|educand[oa]s?)[ \t]*:?[ \t]*$", re.IGNORECASE)
_IDADE_APOS_INICIAIS = re.compile(r"[ \t]*(?:,|\(|–|-)?[ \t]*(?:de[ \t]+)?\d{1,2}[ \t]+(?:anos?|meses|dias)\b",
                                  re.IGNORECASE)

#: Apelido ("vulgo “Fulano”", "conhecido apenas como Fulano"): entre aspas, ou de uma a três palavras
#: com inicial maiúscula.
_APELIDO = re.compile(
    r"\b(?:vulgo|alcunha|apelid(?:o|ad[oa])(?:[ \t]+de)?|identificad[oa][ \t]+como|"
    r"conhecid[oa][ \t]+(?:apenas[ \t]+|tamb[ée]m[ \t]+|entre[ \t]+[^\n,.;]{1,40}?[ \t]+|na[ \t]+comunidade[ \t]+|"
    r"no[ \t]+bairro[ \t]+)?(?:como|por))[ \t]*[:,]?[ \t]*"
    r"(?:[\"“«'‘]([^\"”»'’\n]{2,40})[\"”»'’]"
    r"|((?-i:\p{Lu}[\p{L}'’-]+)(?:[ \t]+(?:d[aeo]s?[ \t]+)?(?-i:\p{Lu}[\p{L}'’-]+)){0,2}))",
    re.IGNORECASE)
#: Pessoa citada logo antes de "conhecido como" ("um homem conhecido como", "FULANO, conhecido como").
_PESSOA_ANTES_DE_APELIDO = re.compile(
    r"(?:\b(?:homem|mulher|rapaz|mo[çc]a|indiv[íi]duo|sujeito|suspeit[oa]|autor[a]?|acusad[oa]|r[ée]u|pessoa|"
    r"cidad[ãa]o?|morador[a]?|usu[áa]ri[oa]|adolescente|jovem|senhor[a]?|investigad[oa]|denunciad[oa]|"
    r"traficante|interno|interna|preso|presa|vizinho|vizinha|capataz|servidor[a]?|paciente|v[íi]tima|"
    r"indiciad[oa]|agressor[a]?)\b[^\n.;]{0,12}|(?-i:\p{Lu}\p{L}+),[ \t]*)$",
    re.IGNORECASE)


def _aceitar_nome(texto: str, toks, a: int, b: int, titulo_aceito: bool) -> bool:
    """Indica se os tokens de ``a`` a ``b``, achados por contexto, formam um nome de pessoa.

    Cada palavra precisa ser prenome ou sobrenome conhecido, inicial ou palavra com inicial maiúscula e
    forma de nome (ver :func:`_forma_de_nome`); são exigidas ao menos duas. Sem nenhuma palavra das
    listas, o nome só é aceito em CAIXA ALTA — a forma usual dos nomes em atos oficiais — ou, com
    ``titulo_aceito``, também com iniciais maiúsculas (contexto inequívoco, como um rótulo de campo).
    Sigla ao lado de palavras com inicial maiúscula ("APS Caruaru", "EEB Professora") não é nome.
    """
    pn, sn, amb = prenomes(), sobrenomes(), ambiguos()
    palavras, conhecida, caixa_alta, minusculas = 0, False, True, False
    siglas = re.match(r"(?:\p{Lu}\.)+", texto[toks[a][0]:toks[b][1] + 1])
    if siglas and siglas.group().replace(".", "").lower() in _SIGLAS_PONTUADAS:
        return False  # "U.E. Professora Fulana", "S.A."
    for k in range(a, b + 1):
        tok = toks[k][2]
        dob = dobrar(tok)
        if dob in CONECTORES:
            continue
        palavras += 1
        if _inicial(texto, toks[k]):
            continue
        if not tok[:1].isupper() or dob in NAO_INICIAM_NOME or dob in PALAVRAS_COMUNS:
            return False
        if dob in _NUCLEOS_INSTITUICAO - {"vila", "jardim"} or dob in _HONORIFICOS - {"santo", "santa", "sao"}:
            return False
        if dob in pn or dob in sn:
            conhecida = True
        elif not (dob in amb or _forma_de_nome(dob, rigorosa=False)):
            return False
        caixa_alta = caixa_alta and tok.isupper()
        minusculas = minusculas or not tok.isupper()
    if palavras < 2 or not (conhecida or caixa_alta or titulo_aceito):
        return False
    if minusculas and any(len(toks[k][2]) > 1 and toks[k][2].isupper() and dobrar(toks[k][2]) not in CONECTORES
                          for k in range(a, b + 1)):
        return False
    return not contexto_nao_pessoal(texto, toks[a][0]) and not _empresa_depois(texto, toks[b][1])


def _nome_antes(texto: str, toks, fins: list[int], fim: int) -> tuple[int, int] | None:
    """Tokens do nome que termina em ``fim`` (só espaços entre o nome e ``fim``), lido para a esquerda.

    Reúne palavras com inicial maiúscula, conectores e iniciais na mesma linha, até uma palavra
    minúscula, pontuação, título, cargo ou palavra comum ("os servidores FULANO DE TAL", "Membro:
    FULANO"). ``fins`` são as posições finais dos tokens, para a busca binária.
    """
    b = bisect_right(fins, fim) - 1
    if b < 0 or texto[toks[b][1]:fim].strip(" \t"):
        return None
    a = b
    while a > 0 and b - a < 8:
        anterior = toks[a - 1]
        dob = dobrar(anterior[2])
        gap = texto[anterior[1]:toks[a][0]]
        if not (_so_espaco(texto, anterior[1], toks[a][0])
                or (_inicial(texto, anterior) and re.fullmatch(r"\.[ \t]{0,2}", gap))):
            break
        if dob not in CONECTORES and (not anterior[2][:1].isupper() or dob in NAO_INICIAM_NOME
                                      or dob in PALAVRAS_COMUNS or dob in _VERBOS_DE_ATO or dob in _HONORIFICOS
                                      or TITULOS.match(anterior[2])):
            break
        a -= 1
    while a <= b and dobrar(toks[a][2]) in CONECTORES:
        a += 1
    return (a, b) if a <= b else None


class ReconhecedorNomesContexto:
    """Nomes identificados pelo contexto em que aparecem.

    * Após um gatilho (ver :data:`GATILHOS`): o nome pode ter uma única palavra, mas precisa conter ao
      menos um prenome ou sobrenome conhecido — "Senhor Diretor" não é nome. Um título após o gatilho
      ("Sra. Dra. Ana") é ignorado.
    * Após rótulo de campo, papel ou ato de pessoal (ver :data:`GATILHOS_ROTULO` e
      :data:`GATILHOS_PAPEL`) e antes de identificador ou cargo ("FULANO, matrícula", "FULANO –
      Membro"): nomes de imigrantes e indígenas, fora das listas, são aceitos em CAIXA ALTA.
    * No bloco de assinatura: linha só com o nome, logo acima da linha do cargo ou do registro.
    * Iniciais de pessoa ("K.C.P.", "M. E. S. C."), comuns para crianças e adolescentes.
    * Apelidos ("vulgo “Fulano”", "conhecido apenas como Fulano").
    """

    nome = "nomes:gatilho"

    def detectar(self, texto: str) -> list[Deteccao]:
        """Nomes encontrados no texto."""
        toks = _tokens(texto)
        saida = self._gatilhos(texto, toks)
        saida += self._antes_de_identificador(texto, toks)
        saida += self._assinaturas(texto, toks)
        saida += self._celulas(texto, toks)
        saida += self._iniciais(texto)
        saida += self._apelidos(texto)
        return saida

    def _gatilhos(self, texto: str, toks) -> list[Deteccao]:
        """Nomes após gatilho, rótulo de campo, papel ou ato de pessoal."""
        pn, sn = prenomes(), sobrenomes()
        inicios = {t[0]: k for k, t in enumerate(toks)}
        saida: list[Deteccao] = []
        # Força do gatilho: 0, expressão geral; 1, rótulo de campo ("Nome:", "Membro:"); 2, papel ou ato
        # de pessoal.
        achados = [(m, 1 if m.group().rstrip().endswith(":") else 0) for m in GATILHOS.finditer(texto)]
        achados += [(m, 1) for m in GATILHOS_ROTULO.finditer(texto)]
        achados += [(m, 2) for m in GATILHOS_PAPEL.finditer(texto)]
        for m, forca in achados:
            k = inicios.get(m.end())
            if k is None:
                continue
            tok = toks[k][2]
            dob = dobrar(tok)
            if TITULOS.match(tok) and k + 1 < len(toks):
                k += 1
                tok, dob = toks[k][2], dobrar(toks[k][2])
            # Sigla de corporação ou unidade entre o papel e o nome ("o Sargento PM Fulano de Tal").
            if forca and 1 < len(tok) <= 5 and tok.isupper() and dob not in pn and dob not in sn \
                    and k + 1 < len(toks) and toks[k + 1][2][:1].isupper() and not toks[k + 1][2].isupper() \
                    and _so_espaco(texto, toks[k][1], toks[k + 1][0]):
                k += 1
                tok, dob = toks[k][2], dobrar(toks[k][2])
            if dob in NAO_INICIAM_NOME or dob in CONECTORES or dob in _VERBOS_DE_ATO or len(dob) < 2:
                continue
            caixa = _capitalizado(tok)
            if not (caixa or dob in pn or dob in sn):
                continue
            fim_idx = _estender(texto, toks, k, caixa)
            if forca and caixa:
                fim_idx = max(fim_idx, _estender_contexto(texto, toks, k))
            palavras = [dobrar(toks[x][2]) for x in range(k, fim_idx + 1)]
            if any(p in PALAVRAS_COMUNS for p in palavras) or (len(palavras) == 1 and palavras[0] in ambiguos()):
                continue
            if any(p in pn or p in sn for p in palavras):
                if forca == 2 and not tok.isupper() and sum(p not in CONECTORES for p in palavras) < 2:
                    continue  # após papel, nome isolado só em CAIXA ALTA ("o servidor SAMIR")
                if contexto_nao_pessoal(texto, toks[k][0]) or _empresa_depois(texto, toks[fim_idx][1]):
                    continue
            elif forca == 0 or not _aceitar_nome(texto, toks, k, fim_idx, titulo_aceito=forca == 1):
                continue
            saida.append(Deteccao(toks[k][0], toks[fim_idx][1], "NOME", 0.85, self.nome, CONTEXTUAL))
            if forca:
                saida += self._coordenado(texto, toks, fim_idx, titulo_aceito=forca == 1)
        return saida

    def _coordenado(self, texto: str, toks, fim_idx: int, titulo_aceito: bool) -> list[Deteccao]:
        """Segundo nome ligado por "e" a um nome achado por rótulo ou papel ("Requeridos: FULANA DE TAL e
        BELTRANO DE TAL", "os servidores FULANO e BELTRANO")."""
        k = fim_idx + 2
        if k >= len(toks) or dobrar(toks[fim_idx + 1][2]) != "e" or not toks[k][2][:1].isupper() \
                or not _so_espaco(texto, toks[fim_idx][1], toks[fim_idx + 1][0]) \
                or not _so_espaco(texto, toks[fim_idx + 1][1], toks[k][0]) \
                or toks[k][2].isupper() != toks[fim_idx][2].isupper():
            return []
        fim = max(_estender(texto, toks, k, True), _estender_contexto(texto, toks, k))
        if not _aceitar_nome(texto, toks, k, fim, titulo_aceito):
            return []
        return [Deteccao(toks[k][0], toks[fim][1], "NOME", 0.85, self.nome, CONTEXTUAL)]

    def _antes_de_identificador(self, texto: str, toks) -> list[Deteccao]:
        """Nome seguido de identificador funcional ou pessoal, idade ou cargo ("FULANO, matrícula")."""
        saida: list[Deteccao] = []
        fins = [t[1] for t in toks]
        for padrao, titulo_aceito in ((_IDENTIFICADOR_APOS_NOME, True), (_CARGO_APOS_NOME, False)):
            for m in padrao.finditer(texto):
                faixa = _nome_antes(texto, toks, fins, m.start())
                if faixa is not None and _aceitar_nome(texto, toks, faixa[0], faixa[1], titulo_aceito):
                    saida.append(Deteccao(toks[faixa[0]][0], toks[faixa[1]][1], "NOME", 0.85, "nomes:identificador",
                                          CONTEXTUAL))
        return saida

    def _assinaturas(self, texto: str, toks) -> list[Deteccao]:
        """Linha só com o nome, entre uma linha em branco (ou de traços) e a linha do cargo ou registro."""
        saida: list[Deteccao] = []
        inicios = {t[0]: k for k, t in enumerate(toks)}
        anterior, pos, corpo = "", 0, False
        for linha in texto.split("\n"):
            ini, pos = pos, pos + len(linha) + 1
            anterior, em_branco, apos_corpo = linha, not anterior.strip(" \t_-–—"), corpo
            corpo = corpo or bool(linha.strip())
            # O cabeçalho do documento (antes de qualquer outra linha) não é bloco de assinatura.
            if not linha.strip() or pos >= len(texto) or not em_branco or not apos_corpo:
                continue
            if not _LINHA_DE_CARGO.match(texto, pos):
                continue
            k = inicios.get(_TITULO_ASSINATURA.match(texto, ini).end())
            if k is None:
                continue
            b = k
            while b + 1 < len(toks) and toks[b + 1][1] <= ini + len(linha):
                b += 1
            if b - k > 7 or texto[toks[b][1]:ini + len(linha)].strip(" \t."):
                continue
            ligados = all(_so_espaco(texto, toks[x][1], toks[x + 1][0])
                          or (_inicial(texto, toks[x]) and re.fullmatch(r"\.[ \t]{0,2}", texto[toks[x][1]:toks[x + 1][0]]))
                          for x in range(k, b))
            if ligados and _aceitar_nome(texto, toks, k, b, titulo_aceito=False):
                saida.append(Deteccao(toks[k][0], toks[b][1], "NOME", 0.85, "nomes:assinatura", CONTEXTUAL))
        return saida

    def _celulas(self, texto: str, toks) -> list[Deteccao]:
        """Célula de tabela só com o nome, em linha que traz um identificador da pessoa.

        Em listas de nomeação, escalas e relações de servidores ("15º | FULANO DE TAL | ***.938.044-**",
        "10254601 | FULANO DE TAL | Agente Administrativo"), a linha com CPF ou matrícula indica que a
        célula ao lado é o nome do titular. Com CPF na linha, nomes com iniciais maiúsculas também são
        aceitos.
        """
        saida: list[Deteccao] = []
        inicios = {t[0]: k for k, t in enumerate(toks)}
        fins = {t[1]: k for k, t in enumerate(toks)}
        pos = 0
        for linha in texto.split("\n"):
            ini, pos = pos, pos + len(linha) + 1
            if "|" not in linha and "\t" not in linha:
                continue
            celulas = [(ini + m.start(), ini + m.end()) for m in _CELULA.finditer(linha)]
            ids = [c for c in celulas if _IDENTIFICADOR_EM_CELULA.fullmatch(texto[c[0]:c[1]].strip())]
            if not ids:
                continue
            cpf = any(_CPF_EM_CELULA.fullmatch(texto[a:b].strip()) for a, b in ids)
            for a, b in celulas:
                trecho = texto[a:b]
                inicio = a + len(trecho) - len(trecho.lstrip())
                fim = a + len(trecho.rstrip())
                k, f = inicios.get(inicio), fins.get(fim)
                if k is None or f is None or f - k > 7:
                    continue
                ligados = all(_so_espaco(texto, toks[x][1], toks[x + 1][0])
                              or (_inicial(texto, toks[x])
                                  and re.fullmatch(r"\.[ \t]{0,2}", texto[toks[x][1]:toks[x + 1][0]]))
                              for x in range(k, f))
                if ligados and _aceitar_nome(texto, toks, k, f, titulo_aceito=cpf):
                    saida.append(Deteccao(toks[k][0], toks[f][1], "NOME", 0.85, "nomes:tabela", CONTEXTUAL))
        return saida

    def _iniciais(self, texto: str) -> list[Deteccao]:
        """Iniciais de pessoa: três ou mais letras, ou duas em contexto pessoal ou junto de outras iniciais."""
        achados = [m for m in _INICIAIS.finditer(texto)
                   if "".join(ch for ch in m.group() if ch.isalpha()).lower() not in _SIGLAS_PONTUADAS]
        saida: list[Deteccao] = []
        for n, m in enumerate(achados):
            if sum(ch.isalpha() for ch in m.group()) < 3:
                vizinhas = [o for o in achados[max(0, n - 1):n + 2] if o is not m]
                junto = any(abs(o.start() - m.end()) <= 4 or abs(m.start() - o.end()) <= 4 for o in vizinhas)
                antes = _PESSOA_ANTES_DE_INICIAIS.search(texto, max(0, m.start() - 40), m.start())
                if not (junto or antes or _IDADE_APOS_INICIAIS.match(texto, m.end())):
                    continue
            # O ponto final fica fora do trecho, como nas demais anotações de nome.
            saida.append(Deteccao(m.start(), m.end() - 1, "NOME", 0.8, "nomes:iniciais", CONTEXTUAL))
        return saida

    def _apelidos(self, texto: str) -> list[Deteccao]:
        """Apelido de pessoa após "vulgo", "alcunha" ou "conhecido como"."""
        saida: list[Deteccao] = []
        for m in _APELIDO.finditer(texto):
            if dobrar(m.group()).startswith(("conhecid", "identificad")) and not _PESSOA_ANTES_DE_APELIDO.search(
                    texto, max(0, m.start() - 60), m.start()):
                continue
            grupo = 1 if m.group(1) else 2
            valor = dobrar(m.group(grupo)).split()
            if not valor or valor[0] in NAO_INICIAM_NOME or any(v in PALAVRAS_COMUNS for v in valor):
                continue
            saida.append(Deteccao(m.start(grupo), m.end(grupo), "NOME", 0.85, "nomes:apelido", CONTEXTUAL))
        return saida


@lru_cache(maxsize=4)
def carregar_spacy(modelo: str | None):
    """Carrega o modelo spaCy usado pelo ``SpacyNlpEngine`` do Presidio.

    O analisador sintático e o segmentador de frases são excluídos: não são usados e respondem por
    cerca de 30% do tempo de processamento. O lematizador é mantido, pois alimenta o reforço de
    confiança por palavras de contexto do Presidio. O modelo nunca é baixado automaticamente, para
    preservar a operação offline.

    Args:
        modelo: Nome do pacote do modelo (ex.: ``pt_core_news_lg``), ou ``None`` para usar apenas
            tokenização e lematização simplificada, sem reconhecimento de entidades.

    Raises:
        RuntimeError: O modelo não está instalado.
    """
    import spacy

    if modelo is None:
        nlp = spacy.blank("pt")
        if "themis_lema" not in nlp.pipe_names:
            nlp.add_pipe("themis_lema")
        return nlp
    try:
        return spacy.load(modelo, exclude=["parser", "senter"])
    except OSError as erro:
        raise RuntimeError(
            f"Modelo spaCy '{modelo}' não encontrado. Instale com:  python -m spacy download {modelo}. "
            "Ou use usar_ner=False (menor cobertura de nomes)."
        ) from erro


def _registrar_lema_simples() -> None:
    """Registra o componente ``themis_lema``, usado quando nenhum modelo spaCy é carregado.

    O lema passa a ser a própria palavra em minúsculas: suficiente para que o reforço de confiança
    por contexto do Presidio encontre palavras como "cpf" ou "telefone".
    """
    from spacy.language import Language

    if "themis_lema" in Language.factories:
        return

    @Language.component("themis_lema")
    def _lema(doc):
        for token in doc:
            token.lemma_ = token.lower_
        return doc


_registrar_lema_simples()


def partes(texto: str, limite: int = 100_000, sobreposicao: int = 2_000):
    """Divide textos grandes em blocos para análise, preferindo cortar em quebras de linha.

    Blocos consecutivos compartilham ``sobreposicao`` caracteres, de modo que um dado que cruze o
    ponto de corte seja visto inteiro em pelo menos um dos blocos. Achados repetidos na faixa
    compartilhada são unificados na consolidação.

    Yields:
        Pares ``(deslocamento, bloco)``; ``deslocamento`` é a posição do bloco no texto.
    """
    if len(texto) <= limite:
        yield 0, texto
        return
    quebra = chr(10)
    inicio = 0
    while inicio < len(texto):
        fim = min(len(texto), inicio + limite)
        if fim < len(texto):
            corte = texto.rfind(quebra, inicio + limite // 2, fim)
            fim = corte + 1 if corte > 0 else fim
        yield inicio, texto[inicio:fim]
        if fim >= len(texto):
            return
        # O próximo bloco começa na primeira quebra de linha da faixa de sobreposição ou, sem quebra,
        # no início da faixa.
        recuo = texto.find(quebra, fim - sobreposicao, fim - 1)
        inicio = recuo + 1 if recuo > inicio else max(inicio + 1, fim - sobreposicao)


#: Razão social logo após o nome ("Panificadora Paulo Afonso Ltda.", "Comercial Fulano S/A"): o nome
#: integra o de uma empresa.
_RAZAO_SOCIAL_DEPOIS = re.compile(r"[ \t]*(?:(?i:ltda|eireli|epp)\b|(?-i:S\.?[ \t]?A\.?|S/A)(?!\w))")


def _empresa_depois(texto: str, fim: int) -> bool:
    """Indica se o nome que termina em ``fim`` é seguido de designação de empresa ("Ltda.", "S/A")."""
    return _RAZAO_SOCIAL_DEPOIS.match(texto, fim) is not None


#: Terminações de substantivos abstratos, advérbios e gerúndios, que não ocorrem em nomes de pessoa.
_SUFIXOS_ABSTRATOS = ("cao", "coes", "mente", "dade", "dades", "encia", "ancia", "ismo", "agem", "avel", "ivel",
                      "ando", "endo", "indo", "aram", "eram", "iram")


def _forma_de_nome(dob: str, rigorosa: bool = True) -> bool:
    """Indica se uma palavra fora das listas de nomes pode ser nome: não é gramatical, comum, cargo,
    numeral romano nem tem terminação típica de substantivo, adjetivo ou verbo.

    Sem ``rigorosa`` — quando o contexto já indica uma pessoa —, só as terminações de
    :data:`_SUFIXOS_ABSTRATOS` são recusadas, pois as demais ocorrem em sobrenomes ("Bittar",
    "Yamada", "Bentes").
    """
    limpa = dob.replace("'", "").replace("’", "").replace("-", "")
    sufixos = _SUFIXOS_NAO_NOME if rigorosa else _SUFIXOS_ABSTRATOS
    return (len(limpa) >= 2 and limpa.isalpha() and dob not in _palavras_gramaticais() and dob not in PALAVRAS_COMUNS
            and dob not in NAO_INICIAM_NOME and dob not in _NAO_COMPLETAM_NOME and not dob.endswith(sufixos)
            and not re.fullmatch(r"[ivxlc]+", dob))


def _separador(token) -> bool:
    """Pontuação ou símbolo que nunca ocorre dentro de um nome ("–", "|", ",", "(", ":")."""
    return not any(ch.isalnum() for ch in token.text) and token.text not in ("'", "’")


def _segmentos(texto: str, ent) -> list[list]:
    """Divide os tokens de uma entidade do modelo nos trechos que podem conter um nome.

    O modelo junta ao nome o que vem na linha seguinte ("Fulano de Tal\nMédico da Estratégia Saúde
    da Família"), depois de travessão ou barra vertical ("Fulano de Tal – Enfermeira") e em colunas
    alinhadas por espaços ("Fulano de Tal          Idade"). Uma quebra de linha simples não separa
    quando a linha termina em conector ou a seguinte começa por "Filho", "Neto" ou "Júnior".
    """
    segmentos: list[list] = []
    atual: list = []
    for t in ent:
        if t.is_space:
            continue
        if _separador(t):
            if atual:
                segmentos.append(atual)
                atual = []
            continue
        if atual:
            entre = texto[atual[-1].idx + len(atual[-1].text):t.idx]
            if "\n" in entre or "\t" in entre or "   " in entre:
                continua = entre.count("\n") == 1 and (dobrar(atual[-1].text) in CONECTORES
                                                       or dobrar(t.text) in _SUFIXOS_FAMILIA)
                if not continua:
                    segmentos.append(atual)
                    atual = []
        atual.append(t)
    if atual:
        segmentos.append(atual)
    return segmentos


def _nome_do_segmento(texto: str, tokens: list, pessoa: bool, score: float) -> Deteccao | None:
    """Valida um trecho de entidade do modelo como nome de pessoa (ver :func:`filtrar_entidade_nlp`)."""
    pn, sn = prenomes(), sobrenomes()
    # Títulos, cargos e marcadores de lista antes do nome ("Dr.", "Vereador", "I.") ficam fora do trecho.
    while tokens and (TITULOS.match(tokens[0].text) or len(tokens[0].text) == 1
                      or re.fullmatch(r"[IVXLC]+", tokens[0].text)
                      or dobrar(tokens[0].text) in _CARGOS_E_PAPEIS):
        tokens = tokens[1:]
    while tokens and (dobrar(tokens[-1].text) in NAO_INICIAM_NOME or dobrar(tokens[-1].text) in CONECTORES):
        tokens = tokens[:-1]
    if any(dobrar(t.text) in PALAVRAS_COMUNS for t in tokens):
        return None
    # Núcleo de instituição no trecho ("EE Professor Fulano", "Centro de Referência Fulana") ou sigla ao
    # lado de palavras com inicial maiúscula ("UBS Fulano", "Soldado PM"): não é nome de pessoa.
    if any(dobrar(t.text).replace(".", "") in _NUCLEOS_INSTITUICAO - {"vila", "jardim"} for t in tokens):
        return None
    if any(len(t.text.rstrip(".")) > 1 and t.text.isupper() for t in tokens) and any(
            t.text[:1].isupper() and not t.text.isupper() for t in tokens):
        return None
    if tokens and all(t.text.isupper() for t in tokens):
        # Em CAIXA ALTA, o nome vai até a primeira palavra que não pode integrá-lo; palavras fora das
        # listas ("EDGARD TOURINHO VIANA") só valem ao lado de um prenome ou sobrenome conhecido.
        corte, conhecidas = 0, 0
        for k, t in enumerate(tokens):
            d = dobrar(t.text)
            if d in CONECTORES:
                continue
            if d in pn or d in sn:
                conhecidas += 1
            elif not _desconhecida_pode_integrar(d):
                break
            corte = k + 1
        tokens = tokens[:corte] if conhecidas else []
    if not tokens:
        return None
    palavras = [dobrar(t.text) for t in tokens]
    if not pessoa and not (palavras[0] in pn and len([p for p in palavras if p not in CONECTORES]) >= 2):
        return None
    if palavras[0] in NAO_INICIAM_NOME or palavras[0] in CONECTORES or palavras[0] in {"sao", "santo", "santa"}:
        return None
    if any(any(ch.isdigit() for ch in t.text) for t in tokens):
        return None
    texto_ent = texto[tokens[0].idx:tokens[-1].idx + len(tokens[-1].text)]
    if len(texto_ent) < 3 or (texto_ent.isupper() and len(texto_ent) <= 4):
        return None
    conhecido = any(p in pn or p in sn for p in palavras)
    if not any(t.text[:1].isupper() for t in tokens) and not conhecido:
        return None
    if not conhecido:
        nucleo = [(t, p) for t, p in zip(tokens, palavras) if p not in CONECTORES]
        if len(nucleo) < 2 or any(not t.text[:1].isupper() or not _forma_de_nome(p, rigorosa=False) for t, p in nucleo):
            return None
    inicio = tokens[0].idx
    fim = inicio + len(texto_ent)
    if contexto_nao_pessoal(texto, inicio) or _empresa_depois(texto, fim):
        return None
    return Deteccao(inicio, fim, "NOME", score, "nomes:modelo", NER)


def filtrar_entidade_nlp(doc, ent, rotulo_pessoa: str = "PERSON", score: float = 0.85,
                         texto: str | None = None) -> Deteccao | None:
    """Valida uma entidade do modelo de linguagem como nome de pessoa e ajusta seus limites.

    O modelo comete erros previsíveis, corrigidos aqui:

    * estende o nome sobre a linha seguinte, um travessão ou uma coluna vizinha ("Maria Souza\nMédica
      Perita", "Maria Souza – Enfermeira") — a entidade é dividida nesses pontos (ver
      :func:`_segmentos`) e vale o primeiro trecho aceito;
    * inclui títulos e marcadores de lista no início ("Sr.", "I.", "a)") e cargos no fim — são cortados;
    * em CAIXA ALTA, junta palavras comuns ao nome — o nome termina na primeira palavra que não pode
      integrá-lo, e palavras fora das listas só são aceitas ao lado de prenome ou sobrenome conhecido;
    * rotula como pessoa termos de tabelas, títulos e nomes de empresas ("Oxigênio Dissolvido",
      "Soldado PM", "Cerealista Vale Verde") — sem nome conhecido, só são aceitas duas ou mais
      palavras capitalizadas com forma de nome;
    * rotula pessoas como ``MISC`` ou ``LOC`` — aceitas quando começam por prenome conhecido;
    * rotula nomes de lugares, instituições e empresas ("Escola Paulo Freire", "Panificadora Paulo
      Afonso Ltda.") — descartados.

    Args:
        doc: Documento spaCy.
        ent: Entidade do documento.
        rotulo_pessoa: Rótulo de pessoa no esquema em uso (``PERSON`` no Presidio).
        score: Confiança atribuída ao achado aceito.
        texto: Texto do documento. ``doc.text`` remonta o texto a cada acesso; quem filtra várias
            entidades do mesmo documento deve informá-lo, para não tornar a análise quadrática.

    Returns:
        O achado, ou ``None`` se a entidade não for aceita como nome de pessoa.
    """
    texto = doc.text if texto is None else texto
    pessoa = ent.label_ == rotulo_pessoa
    for tokens in _segmentos(texto, ent):
        achado = _nome_do_segmento(texto, tokens, pessoa, score)
        if achado is not None:
            return achado
    return None
