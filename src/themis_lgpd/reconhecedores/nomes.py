"""Reconhecimento de nomes de pessoas.

Três fontes se complementam:

* **Modelo de linguagem** (spaCy ``pt_core_news_lg``, via ``SpacyNlpEngine`` do Presidio): reconhece
  nomes em texto bem escrito, inclusive nomes incomuns. As entidades do modelo passam por
  :func:`filtrar_entidade_nlp`, que remove títulos, palavras comuns e nomes de lugares.
* **Lista de nomes brasileiros** (:class:`ReconhecedorNomesLista`): cobre texto todo em minúsculas
  ou em CAIXA ALTA, em que o modelo falha, a partir de prenomes e sobrenomes frequentes.
* **Gatilhos de contexto** (:class:`ReconhecedorNomesContexto`): nomes logo após expressões como
  "meu nome é", "requerente:", "Sr." ou "Atenciosamente,", inclusive quando isolados.

As listas de prenomes, sobrenomes e nomes ambíguos ficam em ``themis_lgpd/dados`` e são geradas por
``scripts/gerar_listas_nomes.py``.
"""

from __future__ import annotations

from functools import cache, lru_cache
from importlib import resources

import regex as re

from ..texto import dobrar
from .base import CONTEXTUAL, NER, Deteccao

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
                     "ou", "ar", "ir")
#: Verbos e qualificações que costumam seguir o nome em requerimentos ("FULANO SOLICITA", "FULANA
#: BRASILEIRA CASADA").
_NAO_COMPLETAM_NOME = frozenset({
    "solicita", "requer", "informa", "declara", "pede", "encaminha", "reside", "brasileiro", "brasileira",
    "casado", "casada", "solteiro", "solteira", "divorciado", "divorciada", "viuvo", "viuva", "portador",
    "portadora", "inscrito", "inscrita", "nascido", "nascida", "esposa", "esposo", "marido", "conjuge",
    "companheiro", "companheira", "menor", "maior", "cpf", "rg", "oab", "matricula", "siape",
})


def _desconhecida_pode_integrar(dob: str) -> bool:
    return (len(dob) >= 3 and dob.isalpha() and dob not in _palavras_gramaticais() and dob not in PALAVRAS_COMUNS
            and dob not in NAO_INICIAM_NOME and dob not in _NAO_COMPLETAM_NOME and not dob.endswith(_SUFIXOS_NAO_NOME))


def _desconhecida_no_nome(texto: str, toks, j: int, pn: frozenset[str], sn: frozenset[str]) -> bool:
    """Indica se a palavra ``j``, em CAIXA ALTA e fora das listas, ainda integra o nome em curso.

    Integra quando fica entre palavras de nome ("RAIMUNDA NONATA BEZERRA", "WELLINGTON JHONATAN DE
    SOUZA") ou quando o fecha: vem seguida de pontuação, quebra de linha, fim do texto, palavra em
    minúsculas ou palavra gramatical ("BENEDITA FERREIRA LINS,", "JOSÉ DA SILVA TAVORA FOI"). Não
    integra se for palavra gramatical, comum ou com terminação típica de substantivo ou verbo.
    """
    if not _desconhecida_pode_integrar(dobrar(toks[j][2])):
        return False
    k, desconhecidas = j + 1, 0
    while k < len(toks) and k - j <= 4 and _so_espaco(texto, toks[k - 1][1], toks[k][0]):
        tok, dob = toks[k][2], dobrar(toks[k][2])
        if dob in CONECTORES:
            k += 1
            continue
        if dob in pn or dob in sn:
            return True
        if not (tok.isupper() and desconhecidas == 0 and _desconhecida_pode_integrar(dob)):
            break
        desconhecidas += 1
        k += 1
    if j + 1 >= len(toks) or not _so_espaco(texto, toks[j][1], toks[j + 1][0]):
        return True
    seguinte = toks[j + 1][2]
    return not seguinte[:1].isupper() or (dobrar(seguinte) in _palavras_gramaticais()
                                          and dobrar(seguinte) not in CONECTORES)


def _estender(texto: str, toks, i: int, modo_caixa: bool) -> int:
    """Estende um nome a partir do token ``i``, já aceito como início.

    Acrescenta palavras enquanto forem prenomes ou sobrenomes conhecidos — ou, com ``modo_caixa``,
    palavras capitalizadas — admitindo até dois conectores seguidos e no máximo nove palavras.
    Em texto todo em CAIXA ALTA, em que qualquer palavra parece nome próprio, uma palavra fora das
    listas só é aceita nas condições de :func:`_desconhecida_no_nome`.

    Returns:
        Índice do último token do nome.
    """
    pn, sn = prenomes(), sobrenomes()
    ultimo = i
    j = i + 1
    pendentes = 0  # conectores lidos e ainda não seguidos de um nome
    ultimo_conector = ""
    while j < len(toks) and _so_espaco(texto, toks[j - 1][1], toks[j][0]):
        tok = toks[j][2]
        dob = dobrar(tok)
        if dob in CONECTORES and pendentes < 2:
            pendentes += 1
            ultimo_conector = dob
            j += 1
            continue
        if ultimo_conector == "e" and (dob in pn or dob not in sn):
            break  # "Souza e João" são duas pessoas; "Silva e Souza" é um sobrenome composto
        ultimo_conector = ""
        nomeavel = dob in pn or dob in sn
        if modo_caixa and tok.isupper() and len(tok) > 1:
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


def contexto_nao_pessoal(texto: str, inicio: int) -> bool:
    """Indica se a palavra em ``inicio`` integra o nome de um lugar, instituição ou norma.

    Exemplos: "São Paulo", "Rua Paulo Freire", "Rua Professora Maria Clara", "Escola Maria Souza", "Lei
    Maria da Penha", "Prefeitura Municipal de Dom Eliseu". A regra é a mesma no reconhecimento de
    nomes, na propagação de valores tarjados e na verificação final.
    """
    janela = max(0, inicio - 45)
    if _EXCECOES_ANTES.search(texto, janela, inicio) or _SANTOS_ANTES.search(texto, janela, inicio):
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
                if n_nomes >= 2 and not contexto_nao_pessoal(texto, ini):
                    score = 0.8 if caixa else 0.7
                    saida.append(Deteccao(ini, toks[fim_idx][1], "NOME", score, self.nome, NER))
                    i = fim_idx + 1
                    continue
            i += 1
        return saida


class ReconhecedorNomesContexto:
    """Nomes logo após um gatilho de contexto (ver :data:`GATILHOS`).

    O nome pode ter uma única palavra, mas precisa conter ao menos um prenome ou sobrenome
    conhecido: "Senhor Diretor" não é nome. Um título após o gatilho ("Sra. Dra. Ana") é ignorado.
    """

    nome = "nomes:gatilho"

    def detectar(self, texto: str) -> list[Deteccao]:
        """Nomes encontrados no texto."""
        pn, sn = prenomes(), sobrenomes()
        toks = _tokens(texto)
        inicios = {t[0]: k for k, t in enumerate(toks)}
        saida: list[Deteccao] = []
        for m in GATILHOS.finditer(texto):
            k = inicios.get(m.end())
            if k is None:
                continue
            tok = toks[k][2]
            dob = dobrar(tok)
            if TITULOS.match(tok) and k + 1 < len(toks):
                k += 1
                tok, dob = toks[k][2], dobrar(toks[k][2])
            if dob in NAO_INICIAM_NOME or dob in CONECTORES or len(dob) < 2:
                continue
            caixa = _capitalizado(tok)
            if not (caixa or dob in pn or dob in sn):
                continue
            fim_idx = _estender(texto, toks, k, caixa)
            palavras = [dobrar(toks[x][2]) for x in range(k, fim_idx + 1)]
            if not any(p in pn or p in sn for p in palavras) or contexto_nao_pessoal(texto, toks[k][0]):
                continue
            if any(p in PALAVRAS_COMUNS for p in palavras) or (len(palavras) == 1 and palavras[0] in ambiguos()):
                continue
            saida.append(Deteccao(toks[k][0], toks[fim_idx][1], "NOME", 0.85, self.nome, CONTEXTUAL))
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


def filtrar_entidade_nlp(doc, ent, rotulo_pessoa: str = "PERSON", score: float = 0.85) -> Deteccao | None:
    """Valida uma entidade do modelo de linguagem como nome de pessoa e ajusta seus limites.

    O modelo comete erros previsíveis, corrigidos aqui:

    * inclui títulos e marcadores de lista no início ("Sr.", "I.", "a)") e palavras de outra linha
      no fim ("Maria Souza\\nCPF") — são cortados;
    * em CAIXA ALTA, junta palavras comuns ao nome — o nome termina na primeira palavra que não é
      prenome nem sobrenome conhecido;
    * rotula como pessoa termos de tabelas e títulos ("Oxigênio Dissolvido") — sem nome conhecido, só
      são aceitas duas ou mais palavras capitalizadas;
    * rotula pessoas como ``MISC`` ou ``LOC`` — aceitas quando começam por prenome conhecido;
    * rotula nomes de lugares e instituições ("Escola Paulo Freire") — descartados.

    Args:
        doc: Documento spaCy.
        ent: Entidade do documento.
        rotulo_pessoa: Rótulo de pessoa no esquema em uso (``PERSON`` no Presidio).
        score: Confiança atribuída ao achado aceito.

    Returns:
        O achado, ou ``None`` se a entidade não for aceita como nome de pessoa.
    """
    pn, sn = prenomes(), sobrenomes()
    tokens = [t for t in ent if not t.is_punct and not t.is_space]
    while tokens and (TITULOS.match(tokens[0].text) or len(tokens[0].text) == 1
                      or re.fullmatch(r"[IVXLC]+", tokens[0].text)):
        tokens = tokens[1:]
    while tokens and (dobrar(tokens[-1].text) in NAO_INICIAM_NOME or dobrar(tokens[-1].text) in CONECTORES):
        tokens = tokens[:-1]
    if any(dobrar(t.text) in PALAVRAS_COMUNS for t in tokens):
        return None
    if tokens and all(t.text.isupper() for t in tokens):
        corte = 0
        for k, t in enumerate(tokens):
            d = dobrar(t.text)
            if d in CONECTORES:
                continue
            if d not in pn and d not in sn:
                break
            corte = k + 1
        tokens = tokens[:corte]
    if not tokens:
        return None
    palavras = [dobrar(t.text) for t in tokens]
    if ent.label_ != rotulo_pessoa and not (palavras[0] in pn and len([p for p in palavras if p not in CONECTORES]) >= 2):
        return None
    if palavras[0] in NAO_INICIAM_NOME or palavras[0] in CONECTORES:
        return None
    if any(any(ch.isdigit() for ch in t.text) for t in tokens):
        return None
    texto_ent = doc.text[tokens[0].idx:tokens[-1].idx + len(tokens[-1].text)]
    if len(texto_ent) < 3 or (texto_ent.isupper() and len(texto_ent) <= 4):
        return None
    conhecido = any(p in pn or p in sn for p in palavras)
    if not any(t.text[:1].isupper() for t in tokens) and not conhecido:
        return None
    if not conhecido:
        nucleo = [t for t, p in zip(tokens, palavras) if p not in CONECTORES]
        if len(nucleo) < 2 or any(not t.text[:1].isupper() for t in nucleo):
            return None
        if any(p in NAO_INICIAM_NOME for p in palavras):
            return None
    inicio = tokens[0].idx
    if contexto_nao_pessoal(doc.text, inicio):
        return None
    return Deteccao(inicio, inicio + len(texto_ent), "NOME", score, "nomes:modelo", NER)
