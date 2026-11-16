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
#: Partículas que ligam partes de um nome ("Maria da Silva", "Van Dijk"), inclusive as de sobrenomes
#: espanhóis, italianos, franceses, alemães, holandeses e árabes ("FULANA DEL CAMPO", "FULANO DE LOS
#: SANTOS", "FULANO DE' BELTRANI DELLA COSTA", "FULANA VON DER BERG", "FULANO AL BELTRANI", "GARCÍA Y LÓPEZ").
CONECTORES = frozenset({
    "da", "de", "do", "das", "dos", "e", "d'", "d’", "di", "del", "van", "von", "de'", "de’", "della", "dello", "delle",
    "dei", "degli", "dalla", "dal", "du", "des", "la", "las", "los", "el", "al", "y", "der", "den", "ter", "ten", "zu",
    "vom", "zum", "bin", "ibn", "bint",
})

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
    r"professor|professora|dom|dona|seu|enf|enfa|enfo|enfª|enfº|enf\.ª|enf\.a)\.?$", re.IGNORECASE)

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
    r"\bigreja|\bpar[óo]quia|\bcreche|\bhemocentro|\bcomplexo|\bterminal|\besta[çc][ãa]o|"
    # Embarcações ("B/M Comandante Fulano", "lancha-ambulância Enfermeira Fulana", "N/M Dona Fulana") e
    # nomes próprios de equipamentos, honrarias, bolsas, operações policiais e políticas públicas.
    r"\b[BNLMR]/[MBVT]|\blancha(?:-ambul[âa]ncia)?|\bambulancha|\bbarco(?:-hospital|\s+escolar|\s+hospital|"
    r"\s+de\s+(?:sa[úu]de|apoio|linha))?|\bbalsa|\bferry(?:-boat)?|\bnavio(?:-hospital)?|\bembarca[çc][ãa]o"
    r"(?:\s+de\s+apoio)?|\brebocador|\bcatamar[ãa]|\bvoadeira|\bplen[áa]rio|\bsal[ãa]o|\borquestra|\bcoral|"
    r"\bmedalha|\bcomenda|\btrof[ée]u|\bopera[çc][ãa]o|\bpol[íi]tica\s+(?:nacional|estadual|municipal)|"
    r"\bconjunto\s+habitacional|\bmercado(?:\s+p[úu]blico)?|\bronda)"
    r"(?:\s+(?:estadual|municipal|federal|p[úu]blic[oa]))?"
    r"(?:\s+(?:professora?|prof[aª]?\.?[aª]?|doutora?|dra?\.|coronel|cel\.|general|marechal|major|capit[ãa]o|"
    r"tenente|almirante|brigadeiro|sargento|padre|pe\.|frei|irm[ãa]o?|monsenhor|c[ôo]nego|bispo|dom|dona|deputad[oa]|"
    r"senador[a]?|governador[a]?|prefeit[oa]|presidente|desembargador[a]?|ministr[oa]|vereador[a]?|"
    r"engenheir[oa]|maestro|bar[ãa]o|visconde|comendador[a]?|juiz|ju[íi]za|enfermeir[oa]|comandante|pastor[a]?|"
    r"ti[oa]|mestre|seu|madre|delegad[oa]|infante|m[ée]dic[oa]|pr[áa]tico))?\s*$",
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
#: Título que inicia nomes de municípios ("Dom Eliseu", "Padre Bernardo", "Governador Valadares",
#: "Comendador Levy Gasparian", "Desembargador Otoni").
_TITULO_ANTES = re.compile(r"\b(?:dom|dona|padre|frei|presidente|governador|senador|deputado|professor|coronel|"
                           r"general|marechal|major|capit[ãa]o|tenente|doutor|bar[ãa]o|visconde|conde|almirante|"
                           r"ministro|monsenhor|bispo|engenheiro|comendador|desembargador|conselheiro|prefeito|"
                           r"vereador|pastor|sargento|cabo|soldado|brigadeiro|juiz|irm[ãa]o?|madre|abade|"
                           r"cardeal|arcebispo|c[ôo]nego)\s+$", re.IGNORECASE)
#: "São Paulo", "Santa Maria", "Nossa Senhora da Glória": topônimos, santos e invocações religiosas.
#: Sensível a maiúsculas, para não confundir com o verbo "são".
_SANTOS_ANTES = re.compile(r"\b(?:São|Santa|Santo|SÃO|SANTA|SANTO|Nossa[ \t]+Senhora(?:[ \t]+d[aeo]s?)?|"
                           r"NOSSA[ \t]+SENHORA(?:[ \t]+D[AEO]S?)?)\s*$")

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
    # Abreviaturas de escola ("ESC. MUN. DR. FULANO") e prefixos de embarcação ("B/M", "N/M").
    "esc", "b/m", "n/m", "l/m", "m/v", "r/m", "n/t",
])
#: Núcleos que só designam uma entidade com inicial maiúscula ("Mercado Seu Fulano", "Plenário Vereador
#: Fulano", "Coral Fulano de Tal", "Associação Beneficente Doutor Fulano", "Operação Fulana", "Bolsa
#: Talento Fulano"); em minúsculas são palavras comuns ("a bolsa de Fulana").
_NUCLEOS_PROPRIOS = frozenset(dobrar(p) for p in [
    "mercado", "plenario", "salao", "orquestra", "coral", "coro", "banda", "operacao", "bolsa", "conjunto",
    "ronda", "politica", "associacao", "sociedade", "irmandade", "cemiterio", "capela", "santuario", "arena",
    "lancha", "barco", "balsa", "navio", "embarcacao", "rebocador", "catamara", "voadeira", "ambulancha", "trilha",
    "turma", "catedra", "cadeira", "galeria",
])
#: Embarcações, cujo nome próprio segue o substantivo comum em minúsculas ("a lancha Comandante Fulano").
_EMBARCACOES = frozenset(dobrar(p) for p in [
    "lancha", "barco", "balsa", "navio", "embarcacao", "rebocador", "catamara", "voadeira", "ambulancha",
])
#: Qualificadores de nome de instituição escritos em minúsculas ("escola municipal", "hospital regional").
_QUALIFICADORES_INSTITUICAO = frozenset({
    "estadual", "municipal", "federal", "regional", "distrital", "publico", "publica", "geral", "mun",
})
#: Abreviaturas que terminam em ponto dentro do nome de uma instituição ("Av.", "Esc.", "Hosp."). Fora
#: delas, um núcleo seguido de ponto encerra a frase ("ficou em casa. Fulana voltou").
_ABREVIATURAS_NUCLEO = frozenset({"av", "esc", "pca", "trav", "rod", "est", "col", "ed", "cond", "res", "conj"})
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
#: Tratamentos e títulos que só iniciam o nome do homenageado com inicial maiúscula ("Mercado Público Seu
#: Fulano", "B/M Tia Fulana", "Instituto Delegado Fulano"); em minúsculas, a menção é a uma pessoa ("do
#: programa da tia Fulana").
_HONORIFICOS_MAIUSCULOS = frozenset({
    "tia", "tio", "mestre", "seu", "delegado", "delegada", "infante", "rainha", "rei", "princesa", "principe",
    "imperador", "imperatriz", "pastora", "vovo",
})
_HONORIFICOS = _HONORIFICOS | _HONORIFICOS_MAIUSCULOS

#: Palavra, sigla com pontos ("U.E.", "Dr."), título com ordinal ("Prof.ª", que a normalização torna
#: "Prof.a"), prefixo de embarcação ("B/M") ou travessão, para percorrer o nome de uma instituição.
_PALAVRA_CADEIA = re.compile(r"\p{Lu}/\p{Lu}(?!\p{L})|\p{L}[\p{L}'’ª-]*(?:\.[ªºao](?!\p{L}))?\.?(?:\p{L}\.)*|[–—]")


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
    pos, anterior_titulo, vistas, conector, proprias = inicio, False, 0, False, 0
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
        if palavra.endswith(".") and "." not in palavra[:-1] and dob not in _ABREVIATURAS_NUCLEO \
                and (dob in _NUCLEOS_INSTITUICAO or dob in _NUCLEOS_PROPRIOS) and len(dob) > 2:
            return False  # "ficou em casa. Fulana voltou": o ponto encerra a frase
        if dob in _NUCLEOS_INSTITUICAO or dob in _NUCLEOS_PROPRIOS:
            # Núcleo em minúsculas seguido só de "de" indica posse, não nome próprio ("a escola de Fulano",
            # "a lancha de Fulano"); as embarcações e entidades de :data:`_NUCLEOS_PROPRIOS` em minúsculas
            # valem só imediatamente antes do nome ("a lancha Comandante Fulano").
            if palavra[:1].isupper():
                return True
            if dob in _NUCLEOS_PROPRIOS:
                return not conector and dob in _EMBARCACOES
            return not (conector and not proprias)
        vistas += 1
        conector = conector or dob in CONECTORES
        proprias += palavra[:1].isupper() and dob not in CONECTORES
        anterior_titulo = dob in _HONORIFICOS and (palavra[:1].isupper() or dob not in _HONORIFICOS_MAIUSCULOS)
        if anterior_titulo or dob in CONECTORES or dob in ("em", "por") or dob in _QUALIFICADORES_INSTITUICAO:
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
    r"\blocal[ \t]*:|\bnatura(?:l|is)[ \t]+d[eoa]|\bprocedentes?[ \t]+d[eoa]|\boriund[oa]s?[ \t]+d[eoa])[ \t]*$",
    re.IGNORECASE)
#: Designação de lugar que não é município da lista do IBGE e antecede seu nome próprio ("distrito de
#: Fulano", "povoado Fulano", "Região Administrativa de Fulano", "Município Fulano", de outro país).
_LUGAR_PROPRIO_ANTES = re.compile(
    r"\b(?:distritos?|povoados?|localidades?|lugarejos?|vilarejos?|regi(?:[ãa]o|[õo]es)[ \t]+administrativas?|"
    r"munic[íi]pio|subdistritos?|n[úu]cleos?[ \t]+rura(?:l|is)|vilas?)(?:[ \t]+d[eoa]s?)?[ \t]+$",
    re.IGNORECASE)
#: Unidade administrativa de abrangência municipal antes de "de" ("Superintendência Regional de Ensino
#: de", "Unidade Local de Execução de", "municípios de", "etapa regional de"): entre o núcleo e o "de"
#: só há palavras com inicial maiúscula ou conectores.
_UNIDADE_DE_MUNICIPIO = re.compile(
    r"\b(?:munic[íi]pios|regional|regionais|superintend[êe]ncias?|ger[êe]ncias?|coordenadorias?|delegacias?|"
    r"unidades?|ag[êe]ncias?|n[úu]cleos?|escrit[óo]rios?|polos?|seccional|subse[çc][ãa]o|promotorias?|"
    r"defensorias?|procuradorias?|cart[óo]rios?|diretorias?|subprefeituras?|campi|"
    # Órgão, colegiado ou cargo de abrangência municipal ("CONSELHO TUTELAR DE", "Conselho Municipal do
    # Idoso de", "Prefeito Municipal de", "Câmara Municipal de").
    r"conselhos?|secretarias?|prefeit[oa]s?|c[âa]maras?|f[óo]runs?|varas?|juizados?|comarcas?|batalh(?:[ãa]o|[õo]es)|"
    r"companhias?|comandos?|guardas?|institutos?|funda[çc](?:[ãa]o|[õo]es)|autarquias?|cons[óo]rcios?|"
    r"hospita(?:l|is)|policl[íi]nicas?|escolas?|col[ée]gios?|creches?|centros?|postos?)"
    r"(?:[ \t]+(?-i:[A-ZÀ-Ý][\wÀ-ú]*|d[aeo]s?|e|DE|D[AO]S?|E)){0,6}[ \t]+d[eoa][ \t]*$",
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

    Vale para a linha de local e data ("João Pessoa, 27 de fevereiro de 2026"), o município seguido da
    UF, após "em" ou rótulo ("Município: Pedro Afonso"), após unidade administrativa ("Superintendência
    Regional de Ensino de Carlos Chagas"), após o nome de uma instituição e um travessão ("EE Dona
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


def _municipio_registravel(texto: str, inicio: int, fim: int) -> bool:
    """Indica se o município em ``texto[inicio:fim]`` é citado como lugar em contexto inequívoco.

    Vale o mesmo que em :func:`_municipio_em_contexto`, exceto a preposição "em" antes de nome de uma
    só palavra ("em Vitória"), insuficiente para tratar como lugar as demais menções do documento.
    """
    if _DEPOIS_MUNICIPIO.match(texto, fim):
        return True
    if texto[fim:fim + 1] == " " and texto[fim + 1:fim + 2].isupper():
        return False
    janela = max(0, inicio - 80)
    lugar = _LUGAR_ANTES.search(texto, janela, inicio)
    if lugar and (" " in texto[inicio:fim].strip() or lugar.group().strip().lower() != "em"):
        return True
    if _UNIDADE_DE_MUNICIPIO.search(texto, janela, inicio) or _MUNICIPIO_INSTITUCIONAL.search(texto, janela, inicio):
        return True
    travessao = _TRAVESSAO_ANTES.search(texto, max(0, inicio - 6), inicio)
    if travessao and _instituicao_antes(texto, travessao.start()):
        return True
    return _municipio_vizinho(texto, inicio, fim)


#: Designação de lugar ou de logradouro seguida do nome próprio, para o registro dos nomes de lugar do
#: documento. No plural, o nome é o primeiro de uma enumeração ("distritos de Fulano, Beltrano e
#: Sicrano", "ruas Fulano de Tal, Beltrano e Sicrano").
_LUGAR_OU_LOGRADOURO = re.compile(
    r"\b(?:(?P<plural>distritos|povoados|localidades|vilas|ruas|avenidas|travessas|alamedas|pra[çc]as|vielas|"
    r"becos|estradas|logradouros)|distrito|povoado|localidade|lugarejo|vilarejo|vila|subdistrito|"
    r"regi[ãa]o[ \t]+administrativa|rua|avenida|av\.|travessa|alameda|pra[çc]a|largo|viela|beco|estrada)"
    r"(?:[ \t]+d[eoa]s?)?[ \t]+", re.IGNORECASE)
#: Nome próprio de lugar: palavras com inicial maiúscula, ligadas por "de", "da", "do"… ("Pedro do Rio").
_NOME_PROPRIO = re.compile(r"\p{Lu}[\p{L}'’-]*(?:[ \t]+(?:(?:d[aeo]s?|D[AEO]S?)[ \t]+)?\p{Lu}[\p{L}'’-]*){0,5}")
#: Separador de itens numa enumeração de nomes de lugar.
_SEPARADOR_ENUMERACAO = re.compile(r"[ \t]*[,;][ \t]*(?:e[ \t]+)?|[ \t]+e[ \t]+")
#: Título do homenageado no início do nome de logradouro ("Rua Professora Fulana").
_TITULO_LOGRADOURO = re.compile(
    r"(?:(?:professora?|prof[aª]?\.?|doutora?|dra?\.|coronel|cel\.|general|marechal|major|capit[ãa]o|tenente|"
    r"padre|pe\.|frei|irm[ãa]|monsenhor|dom|dona|deputad[oa]|senador[a]?|governador[a]?|prefeit[oa]|presidente|"
    r"vereador[a]?|engenheir[oa]|comendador[a]?|desembargador[a]?|ministr[oa]|bar[ãa]o|visconde)[ \t]+)+",
    re.IGNORECASE)


@cache
def _regioes_df():
    """Regiões administrativas do Distrito Federal (ver :data:`themis_lgpd.reconhecedores.localizacao.REGIOES_DF`)."""
    from .localizacao import REGIOES_DF

    return re.compile(r"(?<![\w])(?:" + "|".join(
        re.escape(r).replace(r"\ ", r"[ \t]+") for r in sorted(REGIOES_DF, key=len, reverse=True)) + r")(?!\w)")


def _lugar_em(texto: str, inicio: int) -> int | None:
    """Fim do município ou da região administrativa do DF que começa em ``inicio``, ou ``None``."""
    from .localizacao import municipio_em

    fim = municipio_em(texto, inicio)
    if fim is None and (m := _regioes_df().match(texto, inicio)):
        fim = m.end()
    return fim


def _regiao_registravel(texto: str, inicio: int, fim: int) -> bool:
    """Indica se a região administrativa do DF em ``texto[inicio:fim]`` é citada como lugar: com a UF,
    após "em", rótulo ou "Região Administrativa", em linha de endereço ou numa enumeração de lugares."""
    if _DEPOIS_MUNICIPIO.match(texto, fim) or _linha_de_endereco(texto, inicio):
        return True
    if texto[fim:fim + 1] == " " and texto[fim + 1:fim + 2].isupper():
        return False
    janela = max(0, inicio - 60)
    if _LUGAR_ANTES.search(texto, janela, inicio) or _LUGAR_PROPRIO_ANTES.search(texto, janela, inicio):
        return True
    seguinte = _ITEM_SEGUINTE.match(texto, fim)
    if seguinte and _lugar_em(texto, seguinte.end()) is not None:
        return True
    anterior = _ITEM_ANTERIOR.search(texto, max(0, inicio - 12), inicio)
    if anterior:
        for p in list(_TOKEN.finditer(texto, max(0, anterior.start() - 50), anterior.start()))[-5:]:
            if _lugar_em(texto, p.start()) == anterior.start():
                return True
    return False


@cache
def _primeiras_palavras_de_municipio() -> frozenset[str]:
    """Primeiras palavras dos nomes de município, para descartar depressa as que não iniciam nenhum."""
    from .localizacao import municipios

    return frozenset(nome.split()[0] for nome in municipios())


def _chave_lugar(nome: str) -> str:
    return " ".join(dobrar(nome).split())


@lru_cache(maxsize=8)
def _lugares_do_documento(texto: str):
    """Padrão dos nomes de lugar e de logradouro que o próprio documento identifica, ou ``None``.

    Um município citado em contexto inequívoco ("PREFEITURA MUNICIPAL DE FULANO DE TAL", "Fulano de
    Tal/UF", "Fulano de Tal, 07/04/2027", coluna ou enumeração de municípios), um distrito,
    povoado ou região administrativa ("distrito de Fulano") e um logradouro ("Rua Fulano de Tal", "ruas
    Fulano, Beltrano e Sicrano") continuam sendo o lugar nas demais menções do documento, inclusive como
    sujeito de oração ("Fulano de Tal ampliou o atendimento", "a Beltrano já está concluída").

    Returns:
        Os nomes registrados e as palavras que os compõem, dobrados (sem acentos, em minúsculas), ou
        ``None``.
    """
    from .localizacao import municipio_em

    chaves: set[str] = set()
    iniciais = _primeiras_palavras_de_municipio()
    for m in _TOKEN.finditer(texto):
        if not m.group()[:1].isupper() or dobrar(m.group()) not in iniciais:
            continue
        fim = municipio_em(texto, m.start())
        if fim is not None and _municipio_registravel(texto, m.start(), fim):
            chaves.add(_chave_lugar(texto[m.start():fim]))
    for m in _regioes_df().finditer(texto):
        if _regiao_registravel(texto, m.start(), m.end()):
            chaves.add(_chave_lugar(m.group()))
    for m in _LUGAR_OU_LOGRADOURO.finditer(texto):
        pos = m.end()
        while (titulo := _TITULO_LOGRADOURO.match(texto, pos)) is not None:
            pos = titulo.end()
        while (item := _NOME_PROPRIO.match(texto, pos)) is not None:
            if dobrar(item.group().split()[0]) not in NAO_INICIAM_NOME:
                chaves.add(_chave_lugar(item.group()))
            sep = _SEPARADOR_ENUMERACAO.match(texto, item.end())
            if not m.group("plural") or sep is None:
                break
            pos = sep.end()
    chaves = {c for c in chaves if len(c) >= 4}
    if not chaves:
        return None
    return frozenset(chaves), frozenset(p for c in chaves for p in c.split())


@lru_cache(maxsize=32)
def _padrao_de_lugares(chaves: frozenset[str]):
    """Padrão que encontra no texto original, sem distinção de caixa e acentos, os nomes registrados."""
    return re.compile(r"(?<![\w])(?:" + "|".join(
        "".join(_SEM_ACENTO.get(ch) or (r"\s+" if ch == " " else re.escape(ch)) for ch in c)
        for c in sorted(chaves, key=len, reverse=True)) + r")(?!\w)", re.IGNORECASE)


#: Letra sem acento → classe com as variantes acentuadas, para buscar no texto original os nomes
#: registrados na forma dobrada.
_SEM_ACENTO = {"a": "[aáàâãä]", "e": "[eéèêë]", "i": "[iíìîï]", "o": "[oóòôõö]", "u": "[uúùûü]", "c": "[cç]",
               "n": "[nñ]"}


#: Pronome de tratamento ou parentesco logo antes de um nome ("Dona Fulana", "a filha Fulana"): a
#: menção é de pessoa, ainda que o nome coincida com o de um lugar do documento.
_PESSOA_LOGO_ANTES = re.compile(
    r"(?:\b(?:sr|sra|srta|dr|dra|prof|profa|enf)\.|\b(?:senhor|senhora|dona|seu|doutor|doutora)|"
    r"\b(?:filh[oa]s?|net[oa]s?|irm[ãa]o?s?|espos[oa]|marido|companheir[oa]|m[ãa]e|pai|av[óô]|ti[oa]|sobrinh[oa]|"
    r"prim[oa]|genitor[a]?|entead[oa]|cunhad[oa]|sogr[oa]))[ \t]*,?[ \t]*$", re.IGNORECASE)


def _pessoa_antes(texto: str, inicio: int) -> bool:
    """Indica se o nome que começa em ``inicio`` vem logo após tratamento, parentesco, rótulo ou papel."""
    janela = max(0, inicio - 60)
    if _PESSOA_LOGO_ANTES.search(texto, janela, inicio):
        return True
    return any(m.end() == inicio for padrao in (GATILHOS_ROTULO, GATILHOS_PAPEL)
               for m in padrao.finditer(texto, janela, inicio))


def _lugar_do_documento(texto: str, inicio: int) -> bool:
    """Indica se a palavra em ``inicio`` integra uma menção a lugar ou logradouro identificado no próprio
    documento (ver :func:`_lugares_do_documento`).

    Não vale quando o nome continua além do lugar ("Fulano de Tal Souza") nem quando é precedido de
    tratamento, parentesco, rótulo ou papel ("a filha Fulana", "Dona Fulana").
    """
    registro = _lugares_do_documento(texto)
    palavra = _TOKEN.match(texto, inicio)
    if registro is None or palavra is None or dobrar(palavra.group()) not in registro[1]:
        return False
    # Busca local: os nomes registrados têm no máximo algumas palavras.
    for m in _padrao_de_lugares(registro[0]).finditer(texto, max(0, inicio - 80), inicio + 80):
        a, b = m.span()
        if a <= inicio < b:
            continua = texto[b:b + 1] == " " and texto[b + 1:b + 2].isupper()
            if not continua and not _pessoa_antes(texto, a):
                return True
    return False


#: Designação de pessoa jurídica ao fim da razão social ("Ltda.", "S.A.", "EIRELI", "& Cia.").
_DESIGNACAO_EMPRESA = r"(?:(?i:ltda|eireli|epp)\.?(?!\w)|(?-i:S\.[ \t]?A\.?|S/A)(?!\w)|&[ \t]*(?i:cia)\b)"
#: Razão social a partir da palavra: palavras com inicial maiúscula, iniciais, conectivos e "&" até a
#: designação de empresa ("F. B. Fulano Comércio de Ferragens Ltda.", "Fulano & Beltrano Engenharia
#: Ltda."), ou sobrenomes ligados por "&" ("Fulano & Beltrano").
_RAZAO_SOCIAL = re.compile(
    r"(?:(?:\p{Lu}[\p{L}'’-]*\.?|d[aeo]s?|e|&)[ \t]+){0,9}" + _DESIGNACAO_EMPRESA
    + r"|\p{Lu}[\p{L}'’-]*(?:[ \t]+\p{Lu}[\p{L}'’-]*){0,2}[ \t]*&[ \t]*\p{Lu}")


def _razao_social(texto: str, inicio: int) -> bool:
    """Indica se a palavra em ``inicio`` integra a razão social de uma empresa (ver :data:`_RAZAO_SOCIAL`)."""
    if _RAZAO_SOCIAL.match(texto, inicio):
        return True
    antes = texto[max(0, inicio - 4):inicio]
    return antes.rstrip(" \t").endswith("&")


#: Sigla de escola ("EEF", "EEIEF", "EMEIEF", "EEM"): "E", "E" ou "M" e letras de etapa ou modalidade.
_SIGLA_ESCOLA = re.compile(r"E[EM][EIFMBPTAJ]{0,4}[FMBPTI]")


def _nucleo(palavra: str) -> bool:
    """Indica se a palavra designa instituição, unidade, logradouro ou outra entidade (ver
    :data:`_NUCLEOS_INSTITUICAO` e :data:`_NUCLEOS_PROPRIOS`)."""
    dob = dobrar(palavra.rstrip(".")).replace(".", "")
    return (dob in _NUCLEOS_INSTITUICAO or (palavra[:1].isupper() and dob in _NUCLEOS_PROPRIOS)
            or _SIGLA_ESCOLA.fullmatch(palavra) is not None)


def _continua_celula_de_instituicao(texto: str, inicio: int) -> bool:
    """Indica se a palavra em ``inicio`` continua, na linha de baixo, o nome de instituição da célula
    acima, em tabela alinhada por espaços ("EEF VEREADOR FULANO" / "DE TAL", na mesma coluna)."""
    ini_linha = texto.rfind("\n", 0, inicio) + 1
    antes = texto[ini_linha:inicio]
    if ini_linha == 0:
        return False
    # A palavra pode estar no meio da célula ("DE TAL"): vale a coluna em que a célula começa.
    corte = antes.rfind("  ")
    celula = antes[corte + 2:] if corte >= 0 else antes
    coluna = len(antes) - len(celula.lstrip(" \t"))
    if not re.fullmatch(r"[ \t]*(?:(?:\p{Lu}[\p{L}'’-]*|d[aeo]s?)[ \t]+)*", celula):
        return False
    ini_acima = texto.rfind("\n", 0, ini_linha - 1) + 1
    acima = texto[ini_acima:ini_linha - 1]
    if len(acima) <= coluna or acima[coluna].isspace() or (coluna and not acima[coluna - 1].isspace()) \
            or "  " not in acima.strip():
        return False
    palavra = _PALAVRA_CADEIA.match(acima, coluna)
    return palavra is not None and _nucleo(palavra.group())


#: Linha de endereço rotulada ("Endereço:", "END.:", "Residência:"): após vírgula ou travessão vêm
#: complemento, bairro, cidade e UF, não pessoas ("END.: Rua Fulano, 10 – Bairro Beltrano – Cidade/UF").
_LINHA_DE_ENDERECO = re.compile(
    r"^[ \t]*(?:endere[çc]o(?:[ \t]+(?:residencial|completo|atual))?|end\.?|resid[êe]ncia|domic[íi]lio|logradouro)"
    r"[ \t]*:[^\n]*?\d[^\n]*(?:,|[ \t][–—-])[ \t]*$", re.IGNORECASE)


def _linha_de_endereco(texto: str, inicio: int) -> bool:
    """Indica se a palavra em ``inicio`` está numa linha de endereço, após vírgula ou travessão."""
    ini_linha = texto.rfind("\n", 0, inicio) + 1
    return _LINHA_DE_ENDERECO.match(texto[ini_linha:inicio]) is not None


#: Expressões após as quais vem um nome de pessoa: apresentação ("meu nome é"), papéis processuais
#: ("requerente:", "réu:"), tratamento ("Sr."), fecho de mensagem ("Atenciosamente,") e parentesco
#: ("meu filho"). O nome pode estar na mesma linha ou na seguinte.
GATILHOS = re.compile(
    r"(?:\bmeu nome (?:completo )?(?:é|e)|\bme chamo|\bse chama|\bchamad[oa](?:\s+de)?|\bconhecid[oa] como|"
    r"\b(?:meus|seus|os)\s+dados(?:\s+(?:principais|pessoais|cadastrais))?\s+(?:s[ãa]o|:)|"
    r"\bdados\s+d[oa]\s+(?:requerente|titular|interessad[oa]|solicitante|servidor(?:a)?)\s+(?:s[ãa]o|:)|"
    r"\b(?:eu\s+)?sou\s+(?:o|a)\b|\beu\s+sou\b|\bem nome de|\bnomes?\s+(?:s[ãa]o|é)|"
    r"\beu,|\bnome(?:[ \t]+(?:completo|civil|social|adotad[oa]|de[ \t]+registro|de[ \t]+guerra|religios[oa]|"
    r"ind[íi]gena|art[íi]stico|de[ \t]+batismo))*(?:\s+d[oa]\s+\w+)?(?:[ \t]+(?:no|na|em)[ \t]+[\wÀ-ú]+)?"
    r"(?:[ \t]*\([^()\n]{1,40}\))?\s*:|\brequerente\s*:?|\binteressad[oa]\s*:?|"
    r"\bsolicitante\s*:?|\bdenunciante\s*:?|\bdenunciad[oa]\s*:?|\breclamante\s*:?|\bpaciente\s*:?|"
    r"\bservidor(?:a)?(?:\s+p[úu]blic[oa])?|\bfuncion[áa]ri[oa]|\bcolaborador(?:a)?|\bestagi[áa]ri[oa]|"
    r"\b(?:sr|sra|srta|dr|dra|prof|profa)\.|\bsenhor(?:a)?|\bdoutor(?:a)?|\bdona|(?-i:\bSeu)|\bfilh[oa]s? de|"
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
    gramatical ("SEBASTIANA ROCHA LEDO,", "ROSANE TESSMANN BRAATZ, matrícula", "JOSÉ DA SILVA TAVORA
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
#: célula estreita ("RAIMUNDO DOS ANJOS PAIVA\nFILHO").
_SUFIXOS_FAMILIA = frozenset({"filho", "filha", "neto", "neta", "junior", "jr", "sobrinho", "sobrinha"})
#: Quebra de linha simples (não separa parágrafos), com espaços ou tabulações em volta.
_QUEBRA_SIMPLES = re.compile(r"[ \t]*\n[ \t]*")
#: Restante de uma célula de tabela na linha seguinte: até quatro palavras em CAIXA ALTA e o divisor.
_RESTO_DE_CELULA = re.compile(r"(?:(?:\p{Lu}[\p{L}'’-]*|d[aeo]s?|e)[ \t]+){0,3}\p{Lu}[\p{L}'’-]*[ \t]*(?:\||\t)")
#: Início de linha ou de célula antes do nome.
_INICIO_DE_CELULA = re.compile(r"(?:^|[|\t])[ \t]*$", re.MULTILINE)


def _inicial(texto: str, tok: tuple[int, int, str]) -> bool:
    """Indica se a palavra é a inicial de um nome ("T." em "Rosângela T. Medeiros")."""
    return len(tok[2]) == 1 and tok[2].isupper() and texto[tok[1]:tok[1] + 1] == "."


def _ligacao(texto: str, toks, i: int, j: int, pendentes: int, modo_caixa: bool) -> bool:
    """Indica se o token ``j`` pode continuar o nome que vai de ``i`` a ``j - 1``.

    Além do espaço simples, admite o ponto de uma inicial ("T. Medeiros") e uma quebra de linha
    simples quando o nome continua com certeza na linha seguinte: a linha termina em conector
    ("FERRAZ DE\\nLIMA"), a linha seguinte começa por "Filho", "Neto" ou "Júnior", ou o nome ocupa a
    célula até o fim da linha e o restante dele fecha a célula na linha seguinte ("ANDREIA
    CRISTINA\\nBATALHA DE SOUZA | 864.694-5", "| Fulano Beltrano\\nde Tal | 6283517").
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
    palavras capitalizadas e iniciais ("Rosângela T. Medeiros") — admitindo até dois conectores
    seguidos e no máximo nove palavras. Em texto todo em CAIXA ALTA, em que qualquer palavra parece
    nome próprio, uma palavra fora das listas só é aceita nas condições de :func:`_desconhecida_no_nome`.
    Prenomes que também são palavras comuns ("Dores", "Glória", "Luz") integram o nome quando
    escritos com inicial maiúscula ("MARIA DA GLÓRIA BASTOS"). O nome pode continuar na linha
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
    das listas ("Nome: KENJI MORISHITA ODAGIRI").

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
    "João Pessoa, 27 de fevereiro de 2026". A regra é a mesma no reconhecimento de nomes, na propagação
    de valores tarjados e na verificação final.

    Também integram nome de lugar ou entidade: a palavra que é ela própria o núcleo ("Praça Vereador
    Fulano", "EEF PROFESSORA FULANA"); o nome de embarcação, equipamento, honraria ou operação ("B/M
    Comandante Fulano", "Operação Fulana"); o nome após "distrito de", "povoado", "Região Administrativa
    de"; a razão social ("Fulano & Beltrano Engenharia Ltda."); a continuação, na linha de baixo, do nome
    de instituição de uma célula de tabela; e as demais menções a município, distrito ou logradouro que
    o documento identifica (ver :func:`_lugares_do_documento`).
    """
    palavra = _PALAVRA_CADEIA.match(texto, inicio)
    if palavra is not None and _nucleo(palavra.group()) and re.match(r"[ \t]+\p{Lu}", texto[palavra.end():]):
        return True
    janela = max(0, inicio - 45)
    if _EXCECOES_ANTES.search(texto, janela, inicio) or _SANTOS_ANTES.search(texto, janela, inicio):
        return True
    if _instituicao_antes(texto, inicio) or _LUGAR_PROPRIO_ANTES.search(texto, janela, inicio):
        return True
    if _razao_social(texto, inicio) or _continua_celula_de_instituicao(texto, inicio) \
            or _linha_de_endereco(texto, inicio):
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
    return _lugar_do_documento(texto, inicio)


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
    r"denunciad[oa]|int[ée]rprete|manifestante|acompanhante|cuidador[a]?|respons[áa]vel[ \t]+familiar)"
    r"(?:\(?s\)?|es|\((?:[oa]|[oa]s|es)\))?(?:[ \t]*\([^()\n]{1,40}\))?[ \t]*:[ \t]*\n?[ \t]*", re.IGNORECASE)

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
    r"promotor(?:es|as|a)?|delegad[oa]s?|defensor(?:es|as|a)?|procurador(?:es|as|a)?|relator(?:es|as|a)?|"
    r"autor(?:es|as|a)?[ \t]+d[oa][ \t]+fato|comunicantes?|noticiantes?|ofendid[oa]s?)"
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

#: Apresentação explícita ("meu nome é", "me chamo", "se chama"): vale como rótulo de campo, e o nome
#: pode estar fora das listas.
_APRESENTACAO = re.compile(r"(?:meu nome|me chamo|se chama)", re.IGNORECASE)
#: Pronome de tratamento como gatilho ("Sr.", "Dona", "Senhora"): a palavra seguinte com inicial
#: maiúscula é nome, ainda que fora das listas ("Sr. Fulano") ou coincidente com palavra comum ("Dona
#: Fulana", com prenome que é também substantivo).
_TRATAMENTO = re.compile(r"(?:(?:sr|sra|srta|dr|dra|prof|profa)\.|(?:senhor|senhora|doutor|doutora|dona)\b|(?-i:Seu))",
                         re.IGNORECASE)
#: Parentesco ou convivência antes do nome, com ou sem vírgula ("a esposa, FULANA DE TAL", "o
#: companheiro FULANO", "seu marido, Fulano", "a filha Fulana").
GATILHOS_PARENTESCO = re.compile(
    r"\b(?:[oa]s?|seus?|suas?|meus?|minhas?|d[oa]s?|pel[oa]s?|ao|à|com[ \t]+[oa])[ \t]+"
    r"(?-i:companheir[oa]|espos[oa]|marido|filh[oa]s?|irm[ãa]o?s?|pai|m[ãa]e|av[óô]s?|bisav[óô]|net[oa]s?|"
    r"bisnet[oa]s?|sobrinh[oa]s?|genitor[a]?|entead[oa]s?|cunhad[oa]s?|sogr[oa]|genro|nora|ti[oa]s?|prim[oa]s?|"
    r"namorad[oa]|ex-companheir[oa]|ex-marido|ex-espos[oa]|padrasto|madrasta|afilhad[oa]|padrinho|madrinha)"
    r"(?:[ \t]+(?:mais[ \t]+(?:velh[oa]|nov[oa])|ca[çc]ula|d[oa][ \t]+(?:casal|requerente|titular|v[íi]tima|"
    r"declarante|assistid[oa]|paciente|usu[áa]ri[oa]|respons[áa]vel|entrevistad[oa])))?[ \t]*,?[ \t]+",
    re.IGNORECASE)
#: Papel em linha própria, como título de seção, com o nome na linha seguinte ("VÍTIMA⏎FULANA DE TAL",
#: "TESTEMUNHAS⏎FULANO", "VÍTIMA/COMUNICANTE⏎FULANA").
_PAPEIS_CABECALHO = (r"V[ÍI]TIMAS?|AUTOR(?:A|ES|AS)?|TESTEMUNHAS?|COMUNICANTES?|MANIFESTANTES?|REQUERENTES?|"
                     r"DECLARANTES?|ASSISTID[OA]S?|INTERESSAD[OA]S?|DENUNCIANTES?|DENUNCIAD[OA]S?|INVESTIGAD[OA]S?|"
                     r"NOTICIANTES?|OFENDID[OA]S?|ENVOLVID[OA]S?|CONDUTOR(?:A|ES)?|PROPRIET[ÁA]RI[OA]S?|"
                     r"RECLAMANTES?|USU[ÁA]RI[OA]S?|PACIENTES?|CRIAN[ÇC]AS?|ADOLESCENTES?|GENITOR(?:A|ES)?|"
                     r"RESPONS[ÁA]VE(?:L|IS)(?:[ \t]+LEGA(?:L|IS))?|SUSPEIT[OA]S?|AGRESSOR(?:A|ES)?|PARTES?|"
                     r"REPRESENTANTES?(?:[ \t]+LEGA(?:L|IS))?")
_CABECALHO_PAPEL = re.compile(
    rf"^[ \t]*(?:{_PAPEIS_CABECALHO})(?:[ \t]*/[ \t]*(?:{_PAPEIS_CABECALHO}))*[ \t]*\n[ \t]*", re.MULTILINE)
#: Outra grafia do mesmo nome ("também grafado FULANO", "registrada como FULANA").
_OUTRA_GRAFIA = re.compile(r"\b(?:tamb[ée]m[ \t]+)?(?:grafad[oa]|registrad[oa][ \t]+como)(?:[ \t]+como)?[ \t]*:?[ \t]+",
                           re.IGNORECASE)
#: Posto ou graduação militar abreviado, com a corporação ou o quadro e, às vezes, a matrícula, antes do
#: nome de guerra em escalas e boletins ("3º SGT PM 100.000-0 FULANO", "SD PM FULANO", "1º TEN QOPM
#: 000.000-0 F. BELTRANO").
_POSTO_GRADUACAO = re.compile(
    r"(?<![\p{L}\d])(?:[1-3][ºo°ª]?[ \t]*)?(?:SD|CB|SGT|TEN|CAP|MAJ|TC|CEL|ST|SUBTEN|ASP)"
    r"[ \t]+(?:PM|BM|PC|GCM|QOPM|QPPM|QOBM|QPBM|QOEM|QOS|QOA|QPE|PM[A-Z]{2}|BM[A-Z]{2})"
    r"(?:[ \t]+(?:n[º°o]?[ \t]*)?\d{1,3}(?:\.\d{3})*-?[\dXx])?[ \t]+")
#: Gentílicos de nacionalidade, que em registros de migrantes seguem o nome em aposto ("FULANO,
#: venezuelano, …"). Não compõem nome de pessoa.
_GENTILICOS = (r"(?:(?:brasileir|venezuelan|bolivian|haitian|paraguai|peruan|colombian|argentin|chilen|uruguai|"
               r"equatorian|cuban|mexican|dominican|surinam|italian|iranian|iraquian|angolan|nigerian|cabo-verdian|"
               r"mo[çc]ambican|russ|ucranian|indian|paquistan|filipin|vietnamit|s[íi]ri|palestin|eg[íi]pci|"
               r"marroquin|turc|greg|argelin|corean|japones|chines|portugues|taiwanes|libanes|congoles|senegales|"
               r"poloneses|frances|ingles|holandes|guianens)[oa]s?"
               r"|(?:chin|japon|portugu|taiwan|liban|congol|senegal|gan|polon|franc|ingl|holand|irland|guian)[eê]s"
               r"|alem[ãa](?:o|es|s)?|afeg[ãa](?:o|os|s)?|espanh(?:ol|ola|óis|ois|olas)|[áa]rabes?)")

#: Identificador ou qualificação que segue o nome de uma pessoa em atos e registros oficiais
#: ("FULANO DE TAL, matrícula", "Fulano de Tal – Matr.", "Fulano de Tal, RG", "Fulano de Tal, 42 anos",
#: "FULANO DE TAL, venezuelano").
_IDENTIFICADOR_APOS_NOME = re.compile(
    r"[ \t]*(?:,|[–—-]|\()[ \t]*(?:matr[íi]cula|matr?\.|mat\b|rg\b|r\.g\.|cpf\b|c\.p\.f\.|siape\b|masp\b|rf\b|cns\b|"
    r"ctps\b|n[ºo°.]?[ \t]*funcional|identidade\b|inscrit[oa][ \t]+no[ \t]+cpf|portador[a]?[ \t]+d[oa]|"
    r"brasileir[oa]|nascid[oa][ \t]+em|natural[ \t]+de|filh[oa][ \t]+de|\d{1,3}[ \t]+anos\b|"
    r"sexo[ \t]+(?:masculino|feminino)|(?:crm|coren|cress|crp|oab|crea|cro|crf|crefito|crfa)\b|"
    r"(?:m[ãa]e|pai|filh[oa]|companheir[oa]|espos[oa]|marido|irm[ãa]o?|av[óô]|net[oa]|sobrinh[oa]|genitor[a]?|"
    r"entead[oa]|cunhad[oa]|sogr[oa]|respons[áa]vel[ \t]+familiar|chefe[ \t]+d[ae][ \t]+fam[íi]lia)\b|"
    rf"{_GENTILICOS}(?:[ \t]+naturalizad[oa])?\b)", re.IGNORECASE)
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
#: Célula de tabela alinhada por espaços: palavras separadas por um espaço; dois ou mais separam células.
_CELULA_ALINHADA = re.compile(r"\S+(?: \S+)*")
#: CPF, inclusive mascarado ("***.471.629-**"), como conteúdo de uma célula.
_CPF_EM_CELULA = re.compile(r"(?:\d{3}|\*{3})\.(?:\d{3}|\*{3})\.(?:\d{3}|\*{3})-(?:\d{2}|\*{2})|\d{11}"
                            r"|\d{3}\.\d{5}\.\d{2}-\d|[12789]\d{14}|[12789]\d{2}[ \t]\d{4}[ \t]\d{4}[ \t]\d{4}")
#: Identificador de pessoa como conteúdo de uma célula: CPF, matrícula com dígito verificador
#: ("864.694-5", "482915-3 A") ou número com seis dígitos ou mais.
_IDENTIFICADOR_EM_CELULA = re.compile(
    r"(?:\d{3}|\*{3})\.(?:\d{3}|\*{3})\.(?:\d{3}|\*{3})-(?:\d{2}|\*{2})|[\d.]*\d-[ \t]?[\dXx](?:[ \t]?[A-Z])?|\d{6,}")

#: Iniciais de pessoa ("K.C.P.", "R. A. T. L.", "J.V.S.C."): de duas a cinco letras maiúsculas, cada
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
#: Parentesco ou papel em aposto logo após as iniciais ("F.B., neta da requerente", "B.T., enteado").
_PARENTESCO_APOS_INICIAIS = re.compile(
    r"[ \t]*,[ \t]*(?:filh[oa]|net[oa]|sobrinh[oa]|irm[ãa]o?|entead[oa]|prim[oa]|bisnet[oa]|crian[çc]a|"
    r"adolescente|beb[êe]|rec[ée]m-nascid[oa]|v[íi]tima|testemunha|aluno|aluna|estudante)\b", re.IGNORECASE)

#: Apelido ("vulgo “Fulano”", "conhecido apenas como Fulano"): entre aspas, ou de uma a três palavras
#: com inicial maiúscula.
_APELIDO = re.compile(
    r"\b(?:(?P<livre>vulgo|alcunha|apelid(?:o|ad[oa])(?:[ \t]+de)?|"
    r"(?:prefere|pede[ \t]+para|pediu[ \t]+para|gosta[ \t]+de|quer)[ \t]+ser[ \t]+chamad[oa](?:[ \t]+de)?|"
    r"(?:nome|apelido)[ \t]+pelo[ \t]+qual[^:\n]{0,40}:|a[ \t]+quem[^\n.;:]{0,30}?chama(?:m|va|vam)?[ \t]+de)|"
    r"identificad[oa][ \t]+como|conhecid[oa]s?[ \t]+(?:[^\n,.;:\"“]{1,40}?[ \t]+)?(?:como|por)|"
    r"chamad[oa]s?[ \t]+(?:[^\n,.;:\"“]{1,40}?[ \t]+)?de)[ \t]*[:,]?[ \t]*"
    r"(?:(?:el|la|o|a)[ \t]+)?(?P<titulo>(?:dona|seu|sr\.?|sra\.?|dr\.?|dra\.?|tia|tio)[ \t]+)?"
    r"(?:[\"“«'‘](?P<aspas>[^\"”»'’\n]{2,40})[\"”»'’]"
    r"|(?P<nome>(?-i:\p{Lu}[\p{L}'’-]+)(?:[ \t]+(?:d[aeo]s?[ \t]+)?(?-i:\p{Lu}[\p{L}'’-]+)){0,2}))",
    re.IGNORECASE)
#: Segundo apelido coordenado ao primeiro ("conhecidos como el Fulano e la Fulana").
_APELIDO_COORDENADO = re.compile(r"[ \t]+e[ \t]+(?:(?:el|la|o|a)[ \t]+)?(\p{Lu}[\p{L}'’-]+)")
#: Apelido ou nome social entre aspas seguido da indicação entre parênteses ("“Fulana” (nome social)").
_APELIDO_INDICADO = re.compile(r"[\"“]([^\"”\n]{2,40})[\"”][ \t]*\((?:nome[ \t]+social|apelido|alcunha)\)",
                               re.IGNORECASE)
#: Pessoa citada logo antes de "conhecido como" ou "chamado de" ("um rapaz conhecido como", "FULANO,
#: conhecido como", "a sobrinha era chamada de", "três argentinos conhecidos como").
_PESSOA_ANTES_DE_APELIDO = re.compile(
    r"(?:\b(?:homem|homens|mulher|mulheres|rapaz|mo[çc]a|indiv[íi]duos?|sujeitos?|suspeit[oa]s?|autor[a]?|"
    r"acusad[oa]|r[ée]u|pessoa|cidad[ãa]o?|morador[a]?|usu[áa]ri[oa]|adolescente|jovem|senhor[a]?|investigad[oa]|"
    r"denunciad[oa]|traficante|interno|interna|preso|presa|vizinho|vizinha|capataz|servidor[a]?|paciente|"
    r"v[íi]tima|indiciad[oa]|agressor[a]?|ele|ela|deles|delas|filh[oa]|irm[ãa]o?|net[oa]|sobrinh[oa]|"
    r"companheir[oa]|marido|espos[oa]|pai|m[ãa]e|av[óô]|gerente|dono|dona|comerciante|vendedor[a]?|"
    rf"criança|menin[oa]|{_GENTILICOS})\b[^\n.;]{{0,25}}|(?-i:\p{{Lu}}\p{{L}}+)[,)][ \t]*)$",
    re.IGNORECASE)


#: Sigla de corporação ou quadro entre o papel e o nome ("PM", "BM", "GCM", "QOPM"): sem vogais ou
#: iniciada pelas siglas usuais. Sobrenomes do Leste Asiático em CAIXA ALTA têm vogais ("FULANO Beltrano").
_SIGLA_CORPORACAO = re.compile(r"[B-DF-HJ-NP-TV-Z]{2,5}|(?:PM|BM|PC|CBM|GCM|QO|QP)[A-Z]{0,3}")
#: Pontuação, "e" ou idade logo após um nome isolado em aposto ("a filha Fulana, de 15 anos", "o neto
#: Fulano (8 anos)", "a irmã Fulana e o cunhado").
_APOSTO_APOS_NOME = re.compile(r"[ \t]*(?:[,;:(]|\.(?:\s|$)|$)|[ \t]+e[ \t]+", re.MULTILINE)


def _isolado_aceito(dob: str, tratamento: bool) -> bool:
    """Indica se uma palavra fora das listas pode ser, sozinha, o nome de uma pessoa já indicada pelo
    contexto. Após pronome de tratamento ("Dona Fulana"), aceitam-se também terminações de substantivo
    abstrato, comuns em prenomes de devoção."""
    base = dob.split("-")[0]  # "controlador-geral", "coordenadora-adjunta"
    if len(dob) < 3 or not dob.replace("-", "").isalpha() or base in _CARGOS_E_PAPEIS or base in NAO_INICIAM_NOME:
        return False
    return (dob not in _palavras_gramaticais() and dob not in PALAVRAS_COMUNS and dob not in NAO_INICIAM_NOME
            and dob not in _NAO_COMPLETAM_NOME) if tratamento else _forma_de_nome(dob, rigorosa=False)


def _leste_asiatico(toks, a: int, b: int) -> bool:
    """Indica se os tokens de ``a`` a ``b`` têm a forma de nome do Leste Asiático com o sobrenome em
    CAIXA ALTA à frente ("FULANO Beltrano", "FULANO Bel-trano", "FULANO Bel Trano"): sobrenome curto,
    sem conectores, e prenome com inicial maiúscula, às vezes hifenizado."""
    palavras = [toks[k][2] for k in range(a, b + 1)]
    return (2 <= len(palavras) <= 4 and palavras[0].isupper() and 2 <= len(palavras[0]) <= 5
            and re.search(r"[AEIOUY]", palavras[0]) is not None and "-" not in palavras[0]
            and all(p[:1].isupper() and not p.isupper() and dobrar(p) not in CONECTORES
                    and dobrar(p) not in _PONTOS_CARDEAIS for p in palavras[1:]))


#: Pontos cardeais e designações de área que seguem siglas de unidades ("CRAS Leste", "DRE Centro").
_PONTOS_CARDEAIS = frozenset({"norte", "sul", "leste", "oeste", "centro", "nordeste", "noroeste", "sudeste", "sudoeste",
                              "central", "metropolitana", "regional", "capital", "interior", "litoral", "agreste",
                              "sertao", "serra", "vale"})


#: Forma de sigla de órgão ou unidade, distinta de nome em CAIXA ALTA: sem acentos, com até
#: três letras ou terminada em consoante que não encerra nomes ("SME", "SEMED", "SEDUC").
_SIGLA = re.compile(r"[A-Z]{2,3}|[A-Z]{3,7}[BCDFGJKPQTVWXY]")


def _aceitar_nome(texto: str, toks, a: int, b: int, titulo_aceito: bool) -> bool:
    """Indica se os tokens de ``a`` a ``b``, achados por contexto, formam um nome de pessoa.

    Cada palavra precisa ser prenome ou sobrenome conhecido, inicial ou palavra com inicial maiúscula e
    forma de nome (ver :func:`_forma_de_nome`); são exigidas ao menos duas. Sem nenhuma palavra das
    listas, o nome só é aceito em CAIXA ALTA — a forma usual dos nomes em atos oficiais — ou, com
    ``titulo_aceito``, também com iniciais maiúsculas (contexto inequívoco, como um rótulo de campo).
    Sigla ao lado de palavras com inicial maiúscula ("APS Caruaru", "EEB Professora") não é nome, mas o
    sobrenome do Leste Asiático em CAIXA ALTA antes do prenome é (ver :func:`_leste_asiatico`). Uma
    palavra com terminação de substantivo abstrato só é aceita num nome de três palavras ou mais com
    prenome ou sobrenome conhecido (prenomes de devoção, como "FULANA NATIVIDADE DE JESUS").
    """
    pn, sn, amb = prenomes(), sobrenomes(), ambiguos()
    palavras, conhecida, caixa_alta, minusculas, abstratas = 0, False, True, False, 0
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
        elif dob.endswith(_SUFIXOS_ABSTRATOS) and dob.isalpha() and dob not in _palavras_gramaticais()                 and dob not in _NAO_COMPLETAM_NOME:
            abstratas += 1
        elif not (dob in amb or _forma_de_nome(dob, rigorosa=False)):
            return False
        caixa_alta = caixa_alta and tok.isupper()
        minusculas = minusculas or not tok.isupper()
    primeira = toks[a][2]
    if b > a and _SIGLA.fullmatch(primeira) and dobrar(primeira) not in pn and dobrar(primeira) not in sn:
        from .localizacao import municipio_em

        if municipio_em(texto, toks[a + 1][0]) == toks[b][1]:
            return False  # sigla de órgão e município ("SME FULANÓPOLIS", "APS Fulanópolis")
    leste = _leste_asiatico(toks, a, b)
    if palavras < 2 or not (conhecida or caixa_alta or titulo_aceito or leste):
        return False
    if abstratas and not (abstratas == 1 and conhecida and palavras >= 3):
        return False
    if minusculas and not leste and any(len(toks[k][2]) > 1 and toks[k][2].isupper()
                                        and dobrar(toks[k][2]) not in CONECTORES for k in range(a, b + 1)):
        return False
    if not (conhecida or caixa_alta or leste) and any(dobrar(toks[k][2]).endswith(_SUFIXOS_OFICIO)
                                                      for k in range(a, b + 1)):
        return False  # "Operador de Máquinas, matrícula": nome de cargo, não de pessoa
    return not contexto_nao_pessoal(texto, toks[a][0]) and not _empresa_depois(texto, toks[b][1])


#: Terminações de nomes de ofício ("Operador", "Eletricista", "Cozinheira", "Servente").
_SUFIXOS_OFICIO = ("dor", "dora", "dores", "doras", "ista", "istas", "eiro", "eira", "eiros", "eiras", "ente", "entes")


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


#: Nome invertido, como em listas e tabelas: sobrenome em CAIXA ALTA, vírgula e prenomes ou iniciais
#: ("SOBRENOME, Fulana de Tal", "SOBRENOME, F. B.", "SOBRENOME, FULANA DE TAL").
_NOME_INVERTIDO = re.compile(
    r"(?<![\p{L}\d.])(?P<sobrenome>\p{Lu}[\p{Lu}'’-]+(?: (?:(?:D[AEO]S?|DEL|VON|VAN) )?\p{Lu}[\p{Lu}'’-]+){0,2})"
    r",[ \t]?(?P<prenomes>(?:\p{Lu}\.[ \t]?){1,4}(?![\p{L}])|\p{Lu}[\p{L}'’-]+"
    r"(?: (?:d[aeo]s?|D[AEO]S?|\p{Lu}[\p{L}'’-]+|\p{Lu}\.(?![\p{L}]))){0,5})")
#: Início de célula, de linha ou de item de lista antes do nome invertido.
_INICIO_DE_ITEM = re.compile(r"(?:^[ \t]*|[\"“;|\t][ \t]*|  [ \t]*|^[ \t]*(?:\d{1,4}[.)º°-]?|[–—•-])[ \t]+)$")
#: Identificador da pessoa na linha: CPF (inclusive mascarado), RG ou matrícula com dígito, número longo.
_IDENTIFICADOR_NA_LINHA = re.compile(
    r"(?:\d{3}|\*{3})\.(?:\d{3}|\*{3})\.(?:\d{3}|\*{3})-(?:\d{2}|\*{2})|\b\d{1,3}(?:\.\d{3}){1,2}-[\dXx]\b|\b\d{6,}\b")
#: Idade em aposto a um prenome ("Fulana, de 15 anos", "Fulano, 8 anos", "Fulana (4 anos)").
_EXTENSO = (r"(?:um|uma|dois|duas|tr[êe]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|quatorze|catorze|"
            r"quinze|dezesseis|dezessete|dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|"
            r"noventa)(?:[ \t]+e[ \t]+(?:um|uma|dois|duas|tr[êe]s|quatro|cinco|seis|sete|oito|nove))?")
_PRENOME_COM_IDADE = re.compile(
    rf"(?<![\p{{L}}\d])((?-i:\p{{Lu}}\p{{Ll}}[\p{{L}}'’-]*))(?:[ \t]*,[ \t]*(?:de|com)?[ \t]*|[ \t]*\([ \t]*)"
    rf"(?:\d{{1,3}}|{_EXTENSO})[ \t]+(?:anos?|meses)\b", re.IGNORECASE)
#: Última palavra antes de uma posição, na mesma linha, separada só por espaços.
_TOKEN_ANTERIOR = re.compile(r"(\p{L}[\p{L}'’-]*)[ \t]+$")
#: Antes de um prenome em enumeração de pessoas: "e", vírgula ou ponto e vírgula ("…, e Fulana, de 4 anos").
_ANTES_DE_PRENOME_EM_LISTA = re.compile(r"(?:,|[ \t]e|;)[ \t]+$")
#: Linha só com um nome em CAIXA ALTA, em lista ("FULANA DE TAL⏎BELTRANO DE TAL⏎…").
_LINHA_SO_NOME = re.compile(r"[ \t]*(?:\d{1,3}[.)º°-]?[ \t]+)?(\p{Lu}[\p{Lu}'’-]+(?:[ \t](?:D[AEO]S?[ \t]|E[ \t])?"
                            r"\p{Lu}[\p{Lu}'’-]+){1,6})[ \t]*")


class ReconhecedorNomesContexto:
    """Nomes identificados pelo contexto em que aparecem.

    * Após um gatilho (ver :data:`GATILHOS`): o nome pode ter uma única palavra, mas precisa conter ao
      menos um prenome ou sobrenome conhecido — "Senhor Diretor" não é nome. Um título após o gatilho
      ("Sra. Dra. Ana") é ignorado.
    * Após rótulo de campo, papel ou ato de pessoal (ver :data:`GATILHOS_ROTULO` e
      :data:`GATILHOS_PAPEL`) e antes de identificador ou cargo ("FULANO, matrícula", "FULANO –
      Membro"): nomes de imigrantes e indígenas, fora das listas, são aceitos em CAIXA ALTA.
    * No bloco de assinatura: linha só com o nome, logo acima da linha do cargo ou do registro.
    * Iniciais de pessoa ("K.C.P.", "R. A. T. L."), comuns para crianças e adolescentes.
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
        saida += self._postos(texto, toks)
        saida += self._invertidos(texto)
        saida += self._prenomes_com_idade(texto)
        saida += self._linhas_de_nomes(texto, toks)
        saida += self._continuacoes(texto, toks, saida)
        return saida + self._mesmo_nome_no_documento(texto, saida)

    def _mesmo_nome_no_documento(self, texto: str, achados: list[Deteccao]) -> list[Deteccao]:
        """Demais menções, no documento, a palavra de um nome reconhecido que coincide com município ("o
        neto Fulano, de 9 anos, … a matrícula de Fulano").

        A propagação de valores tarjados não alcança essas menções, sinalizadas como localidade. Não vale
        quando o contexto indica o lugar ("em Fulano", "Fulano/UF") nem quando outro nome segue a palavra.
        """
        from .localizacao import municipio_em

        excluidas = CONECTORES | NAO_INICIAM_NOME | PALAVRAS_COMUNS | ambiguos()
        partes: set[str] = set()
        for d in achados:
            for m in _TOKEN.finditer(texto, d.inicio, d.fim):
                p = m.group()
                if len(p) >= 4 and p[:1].isupper() and not p.isupper() and dobrar(p) not in excluidas \
                        and municipio_em(texto, m.start()) == m.end():
                    partes.add(p)
        saida: list[Deteccao] = []
        for p in partes:
            for m in re.finditer(r"(?<![\w-])" + re.escape(p) + r"(?![\w-])", texto):
                a, b = m.span()
                if any(d.inicio <= a and b <= d.fim for d in achados):
                    continue
                if texto[b:b + 1] == " " and texto[b + 1:b + 2].isupper():
                    continue
                if not contexto_nao_pessoal(texto, a):
                    saida.append(Deteccao(a, b, "NOME", 0.8, "nomes:mesmo-nome", CONTEXTUAL))
        return saida

    def _gatilhos(self, texto: str, toks) -> list[Deteccao]:
        """Nomes após gatilho, rótulo de campo, papel ou ato de pessoal."""
        pn, sn = prenomes(), sobrenomes()
        inicios = {t[0]: k for k, t in enumerate(toks)}
        saida: list[Deteccao] = []
        # Força do gatilho: 0, expressão geral; 1, rótulo de campo ("Nome:", "Membro:"), apresentação
        # explícita, papel em linha de título ou outra grafia do nome; 2, papel ou ato de pessoal; 3,
        # parentesco.
        achados = [(m, 1 if m.group().rstrip().endswith(":") or _APRESENTACAO.match(m.group()) else 0)
                   for m in GATILHOS.finditer(texto)]
        achados += [(m, 1) for padrao in (GATILHOS_ROTULO, _CABECALHO_PAPEL, _OUTRA_GRAFIA) for m in padrao.finditer(texto)]
        achados += [(m, 2) for m in GATILHOS_PAPEL.finditer(texto)]
        achados += [(m, 3) for m in GATILHOS_PARENTESCO.finditer(texto)]
        for m, forca in achados:
            k = inicios.get(m.end())
            if k is None:
                continue
            tok = toks[k][2]
            dob = dobrar(tok)
            tratamento = forca == 0 and _TRATAMENTO.fullmatch(m.group().strip()) is not None
            if TITULOS.match(tok) and k + 1 < len(toks):
                k += 1
                tok, dob = toks[k][2], dobrar(toks[k][2])
                tratamento = True
            # Sigla de corporação ou unidade entre o papel e o nome ("o Sargento PM Fulano de Tal"); um
            # sobrenome do Leste Asiático em CAIXA ALTA antes do prenome ("Nome: FULANO Beltrano") não é sigla.
            if forca and 1 < len(tok) <= 5 and tok.isupper() and dob not in pn and dob not in sn \
                    and _SIGLA_CORPORACAO.fullmatch(tok) \
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
            if (forca or tratamento) and caixa:
                fim_idx = max(fim_idx, _estender_contexto(texto, toks, k))
            palavras = [dobrar(toks[x][2]) for x in range(k, fim_idx + 1)]
            if any(p in PALAVRAS_COMUNS for p in palavras):
                continue
            isolado = sum(p not in CONECTORES for p in palavras) == 1
            if isolado and palavras[0] in ambiguos() and not (tratamento or forca == 3):
                continue
            if isolado and (tratamento or forca == 3) and not (palavras[0] in pn or palavras[0] in sn):
                # Nome isolado após tratamento ("Sr. Fulano", "Dona Fulana") ou em aposto a parentesco ("a
                # filha Fulana, de 15 anos"), ainda que fora das listas ou coincidente com palavra comum.
                if not (caixa and _isolado_aceito(palavras[0], tratamento)
                        and (tratamento or _APOSTO_APOS_NOME.match(texto, toks[fim_idx][1]))):
                    continue
                if contexto_nao_pessoal(texto, toks[k][0]):
                    continue
            elif any(p in pn or p in sn for p in palavras):
                if forca == 2 and not tok.isupper() and isolado:
                    continue  # após papel, nome isolado só em CAIXA ALTA ("o servidor SAMIR")
                if forca == 3 and isolado and not tok.isupper() and palavras[0] in ambiguos() \
                        and not _APOSTO_APOS_NOME.match(texto, toks[fim_idx][1]):
                    continue
                if contexto_nao_pessoal(texto, toks[k][0]) or _empresa_depois(texto, toks[fim_idx][1]):
                    continue
            elif (forca == 0 and not tratamento) or not _aceitar_nome(
                    texto, toks, k, fim_idx, titulo_aceito=forca == 1 or tratamento):
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

        Em listas de nomeação, escalas e relações de servidores ("15º | FULANO DE TAL | ***.471.629-**",
        "30718264 | FULANO DE TAL | Agente Administrativo"), a linha com CPF ou matrícula indica que a
        célula ao lado é o nome do titular. Com CPF na linha, nomes com iniciais maiúsculas também são
        aceitos. Sem barra vertical nem tabulação, as células de tabela alinhada por espaços são separadas
        por dois espaços ou mais ("01   FULANO DE TAL      000.000.000-00   0000000-0").
        """
        pn, sn = prenomes(), sobrenomes()
        saida: list[Deteccao] = []
        inicios = {t[0]: k for k, t in enumerate(toks)}
        fins = {t[1]: k for k, t in enumerate(toks)}
        pos = 0
        for linha in texto.split("\n"):
            ini, pos = pos, pos + len(linha) + 1
            if "|" in linha or "\t" in linha:
                celulas = [(ini + m.start(), ini + m.end()) for m in _CELULA.finditer(linha)]
            elif "  " in linha.strip():
                celulas = [(ini + m.start(), ini + m.end()) for m in _CELULA_ALINHADA.finditer(linha)]
            else:
                continue
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
                # Sem CPF na linha, o código pode ser de material ou serviço ("FEIJÃO CARIOCA | 456789"):
                # exige-se prenome ou sobrenome conhecido.
                conhecida = cpf or any(dobrar(toks[x][2]) in pn or dobrar(toks[x][2]) in sn for x in range(k, f + 1))
                if ligados and conhecida and _aceitar_nome(texto, toks, k, f, titulo_aceito=cpf):
                    saida.append(Deteccao(toks[k][0], toks[f][1], "NOME", 0.85, "nomes:tabela", CONTEXTUAL))
        return saida

    def _continuacoes(self, texto: str, toks, achados: list[Deteccao]) -> list[Deteccao]:
        """Restante do nome na linha de baixo, na mesma coluna, em tabela alinhada por espaços.

        Numa célula estreita, o nome continua abaixo do início ("01   FULANA DE TAL     000.000.000-00" /
        "     DE SOUZA"; "SOBRENOME, Fulana de" / "Tal"). A linha do nome precisa ter outras células; a de
        baixo, estar em branco até a coluna do nome; e o trecho, ter forma de nome e a mesma caixa.
        """
        pn, sn = prenomes(), sobrenomes()
        inicios = {t[0]: k for k, t in enumerate(toks)}
        saida: list[Deteccao] = []
        vistos: set[int] = set()
        for d in achados:
            ini_linha = texto.rfind("\n", 0, d.inicio) + 1
            fim_linha = texto.find("\n", d.fim)
            if fim_linha < 0 or d.inicio in vistos or "\n" in texto[d.inicio:d.fim]:
                continue
            antes, depois = texto[ini_linha:d.inicio], texto[d.fim:fim_linha]
            if (antes.strip() and not antes.endswith("  ")) or (depois.strip() and not depois.startswith("  ")) \
                    or not (antes.strip() or depois.strip()):
                continue
            vistos.add(d.inicio)
            coluna = d.inicio - ini_linha
            proxima = texto[fim_linha + 1:texto.find("\n", fim_linha + 1) if "\n" in texto[fim_linha + 1:] else None]
            if len(proxima) <= coluna or proxima[:coluna].strip() or proxima[coluna].isspace():
                continue
            celula = _CELULA_ALINHADA.match(proxima, coluna)
            a = fim_linha + 1 + coluna
            k = inicios.get(a)
            if celula is None or k is None:
                continue
            caixa_alta = texto[d.inicio:d.fim].replace(",", "").split()[0].isupper() \
                and texto[d.inicio:d.fim].upper() == texto[d.inicio:d.fim]
            f, ok = k, True
            while f < len(toks) and toks[f][1] <= a + celula.end() - coluna:
                tok, dob = toks[f][2], dobrar(toks[f][2])
                if dob not in CONECTORES and not (
                        tok[:1].isupper() and (tok.isupper() or not caixa_alta) and len(dob) >= 2
                        and dob not in NAO_INICIAM_NOME and dob not in PALAVRAS_COMUNS and not _nucleo(tok)
                        and dob.split("-")[0] not in NAO_INICIAM_NOME
                        and (dob in pn or dob in sn or _forma_de_nome(dob, rigorosa=False))):
                    ok = False
                    break
                f += 1
            f -= 1
            if ok and k <= f <= k + 3 and dobrar(toks[f][2]) not in CONECTORES \
                    and not contexto_nao_pessoal(texto, toks[k][0]):
                saida.append(Deteccao(toks[k][0], toks[f][1], "NOME", 0.8, "nomes:continuacao", CONTEXTUAL))
        return saida

    def _iniciais(self, texto: str) -> list[Deteccao]:
        """Iniciais de pessoa: três ou mais letras, ou duas em contexto pessoal ou junto de outras iniciais.

        Siglas de unidade escritas com pontos ("E.E.E.F.", "E.M.E.B.") não são iniciais. Iniciais de duas
        letras aceitas pelo contexto valem também nas demais menções do documento ("a criança F.B., 6
        anos, … a frequência de F.B."), que a propagação não alcança por serem curtas demais.
        """
        def letras(m) -> str:
            return "".join(ch for ch in m.group() if ch.isalpha())

        achados = [m for m in _INICIAIS.finditer(texto)
                   if letras(m).lower() not in _SIGLAS_PONTUADAS and letras(m).lower() not in _NUCLEOS_INSTITUICAO
                   and not _SIGLA_ESCOLA.fullmatch(letras(m))]
        aceitas, pendentes = [], []
        for n, m in enumerate(achados):
            if len(letras(m)) < 3:
                vizinhas = [o for o in achados[max(0, n - 1):n + 2] if o is not m]
                junto = any(abs(o.start() - m.end()) <= 4 or abs(m.start() - o.end()) <= 4 for o in vizinhas)
                antes = _PESSOA_ANTES_DE_INICIAIS.search(texto, max(0, m.start() - 40), m.start())
                if not (junto or antes or _IDADE_APOS_INICIAIS.match(texto, m.end())
                        or _PARENTESCO_APOS_INICIAIS.match(texto, m.end())):
                    pendentes.append(m)
                    continue
            aceitas.append(m)
        confirmadas = {letras(m) for m in aceitas}
        aceitas += [m for m in pendentes if letras(m) in confirmadas]
        # O ponto final fica fora do trecho, como nas demais anotações de nome.
        return [Deteccao(m.start(), m.end() - 1, "NOME", 0.8, "nomes:iniciais", CONTEXTUAL) for m in aceitas]

    def _apelidos(self, texto: str) -> list[Deteccao]:
        """Apelido ou nome pelo qual a pessoa é chamada: após "vulgo", "alcunha", "conhecido como",
        "chamado de", "prefere ser chamada de", "nome pelo qual é conhecida:", ou entre aspas seguido de "(nome
        social)".

        "Conhecido como" e "chamado de" exigem uma pessoa citada logo antes, pois também designam lugares
        e programas. O apelido entre aspas vale mesmo se for palavra comum ("Professor"); sem aspas, não. O
        pronome de tratamento fica fora do trecho ("conhecida como Dona Fulana" → "Fulana").
        """
        saida: list[Deteccao] = []
        for m in _APELIDO.finditer(texto):
            if not m.group("livre") and not m.group("titulo") and not _PESSOA_ANTES_DE_APELIDO.search(
                    texto, max(0, m.start() - 60), m.start()):
                continue
            grupo = "aspas" if m.group("aspas") else "nome"
            valor = dobrar(m.group(grupo)).split()
            if not valor or (grupo == "nome" and (valor[0] in NAO_INICIAM_NOME or valor[0] in _palavras_gramaticais()
                                                  or any(v in PALAVRAS_COMUNS for v in valor))):
                continue
            saida.append(Deteccao(m.start(grupo), m.end(grupo), "NOME", 0.85, "nomes:apelido", CONTEXTUAL))
            seguinte = _APELIDO_COORDENADO.match(texto, m.end())
            if seguinte and dobrar(seguinte.group(1)) not in NAO_INICIAM_NOME | PALAVRAS_COMUNS:
                saida.append(Deteccao(seguinte.start(1), seguinte.end(1), "NOME", 0.85, "nomes:apelido", CONTEXTUAL))
        for m in _APELIDO_INDICADO.finditer(texto):
            saida.append(Deteccao(m.start(1), m.end(1), "NOME", 0.85, "nomes:apelido", CONTEXTUAL))
        return saida

    def _postos(self, texto: str, toks) -> list[Deteccao]:
        """Nome de guerra após posto ou graduação, corporação e matrícula em escalas e boletins
        ("3º SGT PM 100.000-0 FULANO", "SD PM FULANO", "1º TEN QOPM 000.000-0 F. BELTRANO")."""
        pn, sn = prenomes(), sobrenomes()
        inicios = {t[0]: k for k, t in enumerate(toks)}
        saida: list[Deteccao] = []
        for m in _POSTO_GRADUACAO.finditer(texto):
            k = inicios.get(m.end())
            if k is None:
                continue
            fim = None
            for x in range(k, min(k + 4, len(toks))):
                tok, dob = toks[x][2], dobrar(toks[x][2])
                if x > k and not (_so_espaco(texto, toks[x - 1][1], toks[x][0])
                                  or (_inicial(texto, toks[x - 1])
                                      and re.fullmatch(r"\.[ \t]{0,2}", texto[toks[x - 1][1]:toks[x][0]]))):
                    break
                if _inicial(texto, toks[x]) or (dob in CONECTORES and dob != "e" and tok.isupper()):
                    continue
                if not tok.isupper() or len(tok) < 2 or dob in NAO_INICIAM_NOME or dob in PALAVRAS_COMUNS \
                        or not (dob in pn or dob in sn or _forma_de_nome(dob, rigorosa=False)):
                    break
                fim = x
            if fim is not None and not contexto_nao_pessoal(texto, toks[k][0]):
                saida.append(Deteccao(toks[k][0], toks[fim][1], "NOME", 0.85, "nomes:posto", CONTEXTUAL))
        return saida

    def _invertidos(self, texto: str) -> list[Deteccao]:
        """Nome invertido ("SOBRENOME, Fulana de Tal", "SOBRENOME, F. B."), usual em listas, escalas e
        relações nominais.

        Só vale no início de célula, de linha ou de item (após aspas, ponto e vírgula, barra vertical,
        tabulação, dois espaços ou número de ordem), o que exclui "diretor da SIGLA, Fulano de Tal". O
        sobrenome, em CAIXA ALTA, precisa ter forma de nome; os prenomes, ser só iniciais ou ter ao menos uma
        palavra das listas (em CAIXA ALTA, o primeiro prenome) — exigência dispensada na linha que traz
        identificador da pessoa (CPF, RG, matrícula). Recusa cabeçalhos e lugares ("BRASÍLIA, Distrito
        Federal", "MANAUS, AMAZONAS").
        """
        pn, sn = prenomes(), sobrenomes()
        saida: list[Deteccao] = []
        for m in _NOME_INVERTIDO.finditer(texto):
            ini_linha = texto.rfind("\n", 0, m.start()) + 1
            if not _INICIO_DE_ITEM.search(texto[ini_linha:m.start()]):
                continue
            sobrenomes_ = [dobrar(p) for p in m.group("sobrenome").split() if dobrar(p) not in CONECTORES]
            if any(len(p) < 3 or p in NAO_INICIAM_NOME or p in PALAVRAS_COMUNS or p in _NUCLEOS_INSTITUICAO
                   or not (p in pn or p in sn or _forma_de_nome(p, rigorosa=False)) for p in sobrenomes_):
                continue
            prenomes_ = m.group("prenomes").rstrip()
            palavras = [p for p in prenomes_.split() if dobrar(p) not in CONECTORES]
            if re.fullmatch(r"(?:\p{Lu}\.[ \t]?)+", prenomes_):
                if "".join(ch for ch in prenomes_ if ch.isalpha()).lower() in _SIGLAS_PONTUADAS:
                    continue
            else:
                dobradas = [dobrar(p.rstrip(".")) for p in palavras]
                if any(d in NAO_INICIAM_NOME or d in PALAVRAS_COMUNS
                       or not (d in pn or d in sn or _forma_de_nome(d, rigorosa=False)) for d in dobradas):
                    continue
                fim_linha = texto.find("\n", m.end())
                linha = texto[ini_linha:fim_linha if fim_linha >= 0 else None]
                if not _IDENTIFICADOR_NA_LINHA.search(linha):
                    if prenomes_.split()[0].isupper() and dobradas[0] not in pn:
                        continue
                    if not any(d in pn or d in sn for d in dobradas):
                        continue
            if contexto_nao_pessoal(texto, m.start()):
                continue
            saida.append(Deteccao(m.start(), m.start("prenomes") + len(prenomes_), "NOME", 0.85, "nomes:invertido",
                                  CONTEXTUAL))
        return saida

    def _prenomes_com_idade(self, texto: str) -> list[Deteccao]:
        """Prenome isolado com a idade em aposto ("Fulana, de 15 anos"; "…, e Fulano (8 anos)").

        Vale para prenome das listas, não ambíguo, ou, em enumeração de pessoas (após vírgula ou "e"), para
        palavra com forma de nome que não seja município. Prenome precedido de outra palavra com inicial
        maiúscula é parte de um nome mais longo, tratado pelos demais reconhecedores.
        """
        from .localizacao import municipio_em

        pn, amb = prenomes(), ambiguos()
        saida: list[Deteccao] = []
        for m in _PRENOME_COM_IDADE.finditer(texto):
            a, b = m.span(1)
            anterior = _TOKEN_ANTERIOR.search(texto, max(0, a - 40), a)
            if anterior and anterior.group(1)[:1].isupper():
                continue
            dob = dobrar(m.group(1))
            if dob in NAO_INICIAM_NOME or dob in PALAVRAS_COMUNS or dob in amb:
                continue
            if dob not in pn:
                em_lista = _ANTES_DE_PRENOME_EM_LISTA.search(texto, max(0, a - 6), a)
                if not (em_lista and _forma_de_nome(dob) and municipio_em(texto, a) is None):
                    continue
            if contexto_nao_pessoal(texto, a):
                continue
            saida.append(Deteccao(a, b, "NOME", 0.8, "nomes:idade", CONTEXTUAL))
        return saida

    def _linhas_de_nomes(self, texto: str, toks) -> list[Deteccao]:
        """Nomes em CAIXA ALTA, um por linha, em lista de três linhas ou mais (relação de beneficiários,
        lista de presença sem colunas). Cada linha precisa ter forma de nome e uma palavra das listas."""
        pn, sn = prenomes(), sobrenomes()
        inicios = {t[0]: k for k, t in enumerate(toks)}
        fins = {t[1]: k for k, t in enumerate(toks)}
        candidatas: list[tuple[int, int] | None] = []
        pos = 0
        for linha in texto.split("\n"):
            ini, pos = pos, pos + len(linha) + 1
            m = _LINHA_SO_NOME.fullmatch(linha)
            achado = None
            if m:
                k, f = inicios.get(ini + m.start(1)), fins.get(ini + m.end(1))
                if k is not None and f is not None and any(dobrar(toks[x][2]) in pn or dobrar(toks[x][2]) in sn
                                                           for x in range(k, f + 1)) \
                        and _aceitar_nome(texto, toks, k, f, titulo_aceito=False):
                    achado = (k, f)
            candidatas.append(achado)
        saida: list[Deteccao] = []
        n = 0
        while n < len(candidatas):
            if candidatas[n] is None:
                n += 1
                continue
            fim_bloco = n
            while fim_bloco + 1 < len(candidatas) and candidatas[fim_bloco + 1] is not None:
                fim_bloco += 1
            if fim_bloco - n >= 2:
                for k, f in candidatas[n:fim_bloco + 1]:
                    saida.append(Deteccao(toks[k][0], toks[f][1], "NOME", 0.8, "nomes:lista-de-nomes", CONTEXTUAL))
            n = fim_bloco + 1
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


#: Razão social logo após o nome ("Panificadora Fulano de Tal Ltda.", "Comercial Fulano S/A"), também
#: com o ramo de atividade entre o nome e a designação ("Fulano de Tal Comércio de Ferragens Ltda.") ou
#: com outro sócio após "&" ("Fulano & Beltrano"): o nome integra o de uma empresa.
_RAZAO_SOCIAL_DEPOIS = re.compile(
    r"[ \t]*(?:(?i:ltda|eireli|epp)\b|(?-i:S\.?[ \t]?A\.?|S/A)(?!\w))"
    r"|(?:[ \t]+(?:\p{Lu}[\p{L}'’-]*\.?|d[aeo]s?|e|&)){1,6}[ \t]*(?:(?i:ltda|eireli|epp)\b|(?-i:S\.[ \t]?A\.?|S/A)(?!\w))"
    r"|[ \t]*&[ \t]*\p{Lu}")


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


#: Pronome de tratamento abreviado ("V. Sa.", "V. S.ª", "V. Exa.", "V. Ex.ª", "V. Ema.", "V. M.").
_PRONOME_DE_TRATAMENTO = re.compile(r"V\.?[ 	]*(?:S|Sa|Sas|S\.a|Ex|Exa|Exas|Ex\.a|Ema|Emas|M|Mag\.a|Maga|A)\.?",
                                    re.IGNORECASE)


def _nome_do_segmento(texto: str, tokens: list, pessoa: bool, score: float) -> Deteccao | None:
    """Valida um trecho de entidade do modelo como nome de pessoa (ver :func:`filtrar_entidade_nlp`)."""
    pn, sn = prenomes(), sobrenomes()
    if tokens and _PRONOME_DE_TRATAMENTO.fullmatch(texto[tokens[0].idx:tokens[-1].idx + len(tokens[-1].text)]):
        return None  # "V. Sa.", "V. Exa.": pronome de tratamento abreviado
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
    # lado de palavras com inicial maiúscula ("UBS Fulano", "Soldado PM"): não é nome de pessoa. Depois de um
    # prenome conhecido, a palavra só indica instituição seguida de preposição ("Maria Casa de Cultura"); sem
    # ela, é parte de um sobrenome ("Augusto Casa Grande", "Lourenço da Ponte").
    nucleos = [k for k, t in enumerate(tokens) if dobrar(t.text).replace(".", "") in _NUCLEOS_INSTITUICAO - {"vila", "jardim"}]
    if nucleos and not (dobrar(tokens[0].text) in pn and all(
            k > 0 and (k + 1 == len(tokens) or dobrar(tokens[k + 1].text) not in CONECTORES) for k in nucleos)):
        return None
    if any(len(t.text.rstrip(".")) > 1 and t.text.isupper() for t in tokens) and any(
            t.text[:1].isupper() and not t.text.isupper() for t in tokens):
        return None
    if tokens and all(t.text.isupper() for t in tokens):
        # Em CAIXA ALTA, o nome vai até a primeira palavra que não pode integrá-lo; palavras fora das
        # listas ("ODILON TAVEIRA LUCENA") só valem ao lado de um prenome ou sobrenome conhecido.
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
    # O modelo cortou o nome de um município ("por Fulano Beltrano em …" → "Fulano").
    fim_lugar = _lugar_em(texto, inicio)
    if fim_lugar is not None and fim_lugar > fim and not (
            texto[fim_lugar:fim_lugar + 1] == " " and texto[fim_lugar + 1:fim_lugar + 2].isupper()):
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
