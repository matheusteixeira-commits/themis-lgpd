"""Contatos, endereços e veículos de órgãos e entidades públicas.

Telefone e e-mail de setor, endereço de sede ou de unidade de atendimento e placa de veículo da frota
oficial não são dados pessoais: a LAI manda divulgá-los (art. 8º, § 1º, I) e a LGPD protege apenas
dados de pessoa natural (art. 5º, I). Documentos oficiais os trazem no cabeçalho e no rodapé, nos
canais de atendimento ("Dúvidas pelo telefone…", "Informações: setor@orgao.gov.br") e nos endereços
das unidades ("na sede da Secretaria, situada na Rua…").

Este módulo reclassifica, depois de todos os reconhecedores, os achados de telefone, e-mail, endereço,
CEP e placa que o contexto mostra serem do órgão. Os novos tipos (``CONTATO_INSTITUCIONAL``,
``ENDERECO_INSTITUCIONAL`` e ``PLACA_OFICIAL``) pertencem à categoria ``INSTITUCIONAL``, que o perfil
LAI mantém legível e sinaliza para revisão. Na dúvida, o achado continua pessoal:

* celular nunca é institucional; e-mail de provedor pessoal ou com nome de pessoa também não;
* expressão de vínculo pessoal ("meu telefone", "residente na", "telefone da genitora") prevalece
  sobre a menção ao órgão;
* o mesmo valor citado em outro ponto do documento recebe a mesma classificação.
"""

from __future__ import annotations

from functools import cache, lru_cache

import regex as re

from ..texto import dobrar
from .base import Deteccao

# --------------------------------------------------------------------------- Órgãos e unidades
#: Designações de órgão, entidade ou unidade pública, inclusive as unidades de atendimento de saúde e
#: de assistência social pelas siglas (UBS, UPA, CAPS, CRAS…).
_ORGAO = (
    r"(?:secretaria|subsecretaria|minist[ée]rio|prefeitura|governo|c[âa]mara|assembleia|tribunal|f[óo]rum|"
    r"delegacia|batalh[ãa]o|quartel|autarquia|funda[çc][ãa]o|universidade|instituto|escola|col[ée]gio|creche|"
    r"hospital|policl[íi]nica|cart[óo]rio|defensoria|procuradoria|promotoria|ouvidoria|corregedoria|"
    r"controladoria|conselhos?|superintend[êe]ncia|ger[êe]ncia|diretoria|coordena[çc][ãa]o|coordenadoria|"
    r"departamento|divis[ãa]o|n[úu]cleo|se[çc][ãa]o|assessoria|gabinete|reitoria|pr[óo]-reitoria|campus|"
    r"ag[êe]ncia|[óo]rg[ãa]o|reparti[çc][ãa]o|comiss[ãa]o|comit[êe]|junta|vara|guarda\s+(?:civil|municipal)|"
    r"pol[íi]cia|corpo\s+de\s+bombeiros|defesa\s+civil|detran|pal[áa]cio|pa[çc]o\s+municipal|"
    r"centro\s+(?:administrativo|de\s+\w+|municipal|estadual|regional|especializado)|"
    r"central\s+de\s+\w+|unidade\s+(?:de\s+\w+|b[áa]sica|municipal|estadual|regional|descentralizada)|"
    r"posto\s+de\s+\w+|(?-i:UBSF?|USF|UPA|CAPS\w*|CRAS|CREAS|CEO|CIEVS|SAMU|HEMOCENTRO|SINE))"
)
_ORGAO_RE = re.compile(r"\b" + _ORGAO + r"\b", re.IGNORECASE)
#: Linha que começa pela designação de um órgão ou unidade (cabeçalho, rodapé, linha de contato).
_LINHA_ORGAO = re.compile(r"^\s*(?:[-–•*]\s*)?" + _ORGAO + r"\b", re.IGNORECASE)

#: Expressões de vínculo pessoal antes do contato ou do endereço: primeira pessoa, possessivo, papel
#: da pessoa no documento ou qualificação do meio de contato como pessoal.
_PESSOAL = re.compile(
    r"\b(?:eu|meus?|minhas?|me|mim|comigo|estou|estarei|fico|ficarei|posso|sou|tenho|moro|resido|seus?|suas?|dele|dela|"
    r"residente|domiciliad[oa]|morador[a]?|requerente|manifestante|solicitante|interessad[oa]|paciente|"
    r"usu[áa]ri[oa]|respons[áa]vel|acompanhante|genitor[a]?|m[ãa]e|pai|filh[oa]|espos[oa]|marido|companheir[oa]|"
    r"vizinh[oa]|assistid[oa]|autor[a]?|r[ée]u|testemunha|denunciante|v[íi]tima|declarante|candidat[oa]|"
    r"servidor[a]?|celular|whats\w*|zap|recados?|pessoal|particular|residencial|resid[êe]ncia|familiar|parente|"
    r"irm[ãa]o?|av[óô]|net[oa]|sobrinh[oa]|ti[oa]|propriet[áa]ri[oa]|contratad[oa]|empregad[oa])\b",
    re.IGNORECASE,
)
#: Campos de qualificação de pessoa num formulário ("Nome:", "CPF:", "Endereço:"): o telefone na linha
#: seguinte é o da pessoa qualificada.
_CAMPO_PESSOAL = re.compile(
    r"^\s*(?:nome|paciente|usu[áa]ri[oa]|requerente|interessad[oa]|manifestante|solicitante|cpf|rg|cns|nis|"
    r"endere[çc]o(?:\s+residencial)?|resid[êe]ncia|domic[íi]lio|respons[áa]vel|m[ãa]e|pai|genitor[a]?|"
    r"data\s+de\s+nascimento|idade|e-?mail(?:\s+pessoal)?)\b[^:\n]{0,30}:",
    re.IGNORECASE | re.MULTILINE,
)

# --------------------------------------------------------------------------- Contatos
#: Indicação de que o meio de contato é do órgão: canal de atendimento ao público, contato da unidade
#: ou do setor, ramal.
_CANAL_ORGAO = re.compile(
    r"\b(?:institucional|ramal|pabx|sac|fale\s+conosco|disque|d[úu]vidas|informa[çc](?:[õo]es|[ãa]o)|"
    r"esclarecimentos?|atendimento|agendamento|[àa]\s+disposi[çc][ãa]o|canais|"
    r"(?:esclarecid|dirimid|sanad|obtid|solicitad|agendad|emitid|prestad|enviad|encaminhad)[oa]s?|"
    r"(?:telefones?|n[úu]meros?|ligue|ligar|disque)\s+(?:para\s+(?:o\s+)?)?1\d{2}(?!\d)|"
    r"(?:poder[áã]o?|pode(?:m|r[áã]o?)?)\s+(?:\w+\s+){0,2}?(?:acompanhar|consultar|obter|solicitar|agendar|"
    r"esclarecer|tirar|registrar|entrar\s+em\s+contato)|"
    r"(?:pel[oa]|n[oa]|à|ao|junto\s+(?:a|à|ao))\s+" + _ORGAO + r"\b[^.;\n]{0,70}?"
    r"\b(?:telefones?|fones?|n[úu]meros?|e-?mails?|endere[çc]os?\s+eletr[ôo]nicos?)|"
    r"(?:telefones?|fones?|tel\.?|e-?mails?|contatos?|endere[çc]os?(?:\s+eletr[ôo]nicos?)?)\s+"
    r"(?:d[aoe]s?\s+)?(?:unidade|[óo]rg[ãa]o|setor|institui[çc][ãa]o|sede|equipe|" + _ORGAO + r"))\b",
    re.IGNORECASE,
)
#: Rótulo de campo de contato no início da linha ("Telefone:", "Fone:", "Contato:").
_ROTULO_CONTATO = re.compile(r"^\s*(?:telefones?|fones?|tel\.?|contatos?|e-?mails?)\s*:", re.IGNORECASE)
#: Números de serviço, que nunca são de pessoa (0800, 0300, 4004…).
_SERVICO = re.compile(r"0[3589]00\d{6,7}|400\d{5}")
#: Provedores de e-mail de uso pessoal.
_PROVEDORES_PESSOAIS = re.compile(
    r"(?:^|\.)(?:gmail|googlemail|hotmail|outlook|live|msn|yahoo|ymail|icloud|me|mac|uol|bol|terra|ig|globo|"
    r"globomail|r7|zipmail|oi|protonmail|proton|aol|gmx|zoho|tutanota|yandex|mail)\.",
    re.IGNORECASE,
)
#: Domínios de órgãos públicos, instituições de ensino e entidades sem fins lucrativos. E-mail de empresa
#: (".com.br") não é considerado: costuma ser o canal pelo qual a própria pessoa recebe a resposta.
_DOMINIO_PUBLICO = re.compile(r"\.(?:gov|jus|mp|leg|def|mil|edu|org)\.br$|\.(?:gov|edu|int)$", re.IGNORECASE)
_PARTES_LOCAL = re.compile(r"[a-z]+")


@cache
def _listas_nomes() -> tuple[frozenset[str], frozenset[str]]:
    """Prenomes (sem os ambíguos) e sobrenomes, sem acentos e em minúsculas."""
    from .nomes import ambiguos, prenomes, sobrenomes

    return frozenset(prenomes() - ambiguos()), frozenset(sobrenomes())


def _tem_nome(local: str) -> bool:
    """Indica se a parte local de um e-mail contém nome de pessoa ("maria.souza", "jsilva",
    "carlamendes82"): um prenome inteiro ou no início da parte, sobrenome precedido de iniciais ou dois
    sobrenomes."""
    prenomes, sobrenomes = _listas_nomes()
    partes = _PARTES_LOCAL.findall(dobrar(local))
    if any(p in prenomes for p in partes):
        return True
    if sum(p in sobrenomes for p in partes) >= 2 or (len(partes) >= 2 and any(len(p) <= 2 for p in partes)
                                                       and any(p in sobrenomes for p in partes)):
        return True
    for p in partes:
        # Iniciais coladas ao sobrenome ("jsilva", "mcarvalho") ou prenome colado a outra parte ("anabia").
        if any(p[k:] in sobrenomes for k in (1, 2, 3) if len(p) - k >= 4):
            return True
        if any(p[:k] in prenomes for k in range(4, len(p) - 2)):
            return True
    return False


def email_institucional(valor: str) -> bool:
    """Indica se o e-mail pode ser de órgão ou setor: domínio público, sem nome de pessoa na parte local
    e fora dos provedores de uso pessoal. A classificação final depende também do contexto."""
    local, _, dominio = valor.strip().lower().rpartition("@")
    if not local or not dominio or _PROVEDORES_PESSOAIS.search(dominio) or _tem_nome(local):
        return False
    return bool(_DOMINIO_PUBLICO.search(dominio))


def _digitos(valor: str) -> str:
    """Dígitos do telefone, sem o código do país."""
    d = re.sub(r"\D", "", valor)
    return d[2:] if len(d) >= 12 and d.startswith("55") else d


def celular(valor: str) -> bool:
    """Indica se o número é de celular (nono dígito ou, sem DDD, iniciado por 6 a 9)."""
    d = _digitos(valor).lstrip("0")
    if len(d) == 11:
        return d[2] == "9"
    if len(d) == 9:
        return d[0] == "9"
    if len(d) == 10:
        return d[2] not in "2345"
    return len(d) == 8 and d[0] not in "2345"


def _linha(texto: str, pos: int) -> tuple[int, int]:
    """Limites da linha que contém ``pos``."""
    a = texto.rfind("\n", 0, pos) + 1
    b = texto.find("\n", pos)
    return a, (len(texto) if b < 0 else b)


def _linha_anterior(texto: str, inicio_linha: int) -> str:
    """Linha não vazia imediatamente anterior."""
    fim = inicio_linha - 1
    while fim > 0 and texto[fim - 1] in " \t\r\n":
        fim -= 1
    if fim <= 0:
        return ""
    a, b = _linha(texto, fim - 1)
    return texto[a:b]


@lru_cache(maxsize=16)
def _fim_cabecalho(texto: str) -> int:
    """Fim do cabeçalho do documento (timbre): o primeiro bloco de linhas, até a primeira linha em branco,
    quando uma das três primeiras linhas designa órgão ou unidade. Zero se não houver cabeçalho."""
    inicio = len(texto) - len(texto.lstrip())
    fim = texto.find("\n\n", inicio)
    fim = len(texto) if fim < 0 else fim
    bloco = texto[inicio:fim]
    linhas = bloco.split("\n")
    if fim - inicio > 600 or len(linhas) > 8:
        return 0
    if not any(_LINHA_ORGAO.match(linha) for linha in linhas[:3]):
        return 0
    if any(_CAMPO_PESSOAL.match(linha) for linha in linhas):
        return 0
    return fim


#: Fim de frase: pontuação final seguida de espaço, exceto o ponto de abreviatura ("Qd.", "Dr.", "nº.").
_FIM_FRASE = re.compile(r"(?<!\b[A-Za-zÀ-ú]{1,3})[.!?;](?=\s|$)")


def _frase_antes(texto: str, inicio: int, limite: int = 160) -> str:
    """Trecho da frase (ou da linha) que antecede a posição, até ``limite`` caracteres."""
    a = max(0, inicio - limite)
    trecho = texto[a:inicio]
    corte = max(trecho.rfind("\n"), *(m.end() - 1 for m in _FIM_FRASE.finditer(trecho)), -1)
    return trecho[corte + 1:]


def _frase(texto: str, inicio: int, fim: int) -> tuple[int, int]:
    """Limites da frase que contém o trecho, sem atravessar linhas."""
    la, lb = _linha(texto, inicio)
    antes = [m.end() for m in _FIM_FRASE.finditer(texto, la, inicio)]
    a = antes[-1] if antes else la
    m = _FIM_FRASE.search(texto, fim, lb)
    return a, (m.start() if m else lb)


def _contexto_contato(texto: str, d: Deteccao, anterior: int) -> str:
    """Classifica uma ocorrência de telefone ou e-mail: ``orgao``, ``pessoal`` ou ``neutro``.

    Args:
        texto: Texto analisado.
        d: Achado de telefone ou e-mail.
        anterior: Fim do contato anterior; o vínculo pessoal é procurado só depois dele, para que o
            celular de uma pessoa não contamine o e-mail do setor citado em seguida.
    """
    valor = texto[d.inicio:d.fim]
    if d.tipo == "TELEFONE" and _SERVICO.fullmatch(_digitos(valor)):
        return "orgao"
    antes = _frase_antes(texto, d.inicio)
    la, _ = _linha(texto, d.inicio)
    linha_antes = texto[la:d.inicio]
    perto = texto[max(la, anterior, d.inicio - 60):d.inicio]
    if _PESSOAL.search(perto):
        return "pessoal"
    if d.tipo == "TELEFONE" and celular(valor):
        return "pessoal"
    if d.tipo == "EMAIL" and not email_institucional(valor):
        return "pessoal"
    if d.inicio < _fim_cabecalho(texto):
        return "orgao"
    if _CANAL_ORGAO.search(antes) or _LINHA_ORGAO.match(linha_antes):
        return "orgao"
    # Rótulo "Telefone:" no início da linha: vale a linha anterior (o nome do órgão no cabeçalho ou o
    # campo de qualificação da pessoa).
    if _ROTULO_CONTATO.match(linha_antes):
        acima = _linha_anterior(texto, la)
        if _LINHA_ORGAO.match(acima) and not _CAMPO_PESSOAL.match(acima) and not _PESSOAL.search(acima):
            return "orgao"
        return "neutro"
    return "neutro"


def _chave_contato(texto: str, d: Deteccao) -> str:
    valor = texto[d.inicio:d.fim]
    return _digitos(valor)[-8:] if d.tipo == "TELEFONE" else valor.strip().lower()


def _reclassificar_contatos(texto: str, deteccoes: list[Deteccao]) -> None:
    contatos = [d for d in deteccoes if d.tipo in ("TELEFONE", "EMAIL")]
    if not contatos:
        return
    contatos.sort(key=lambda d: d.inicio)
    situacao: list[str] = []
    anterior = 0
    for d in contatos:
        situacao.append(_contexto_contato(texto, d, anterior))
        anterior = max(anterior, d.fim)
    # Contato sem indicação própria na mesma frase de um contato do órgão ("pelo telefone … ou pelo
    # e-mail setor@orgao.gov.br"): os dois são canais do mesmo setor.
    frases = [_frase(texto, d.inicio, d.fim) for d in contatos]
    orgao = {f for f, s in zip(frases, situacao) if s == "orgao"}
    situacao = ["orgao" if s == "neutro" and f in orgao else s for f, s in zip(frases, situacao)]
    classes: dict[str, set[str]] = {}
    for d, s in zip(contatos, situacao):
        classes.setdefault(_chave_contato(texto, d), set()).add(s)
    for d in contatos:
        c = classes[_chave_contato(texto, d)]
        if "orgao" in c and "pessoal" not in c:
            d.tipo, d.origem = "CONTATO_INSTITUCIONAL", d.origem + ":institucional"


# --------------------------------------------------------------------------- Endereços
#: Endereço de sede ou unidade: "na sede da …", "a Diretoria …, situada na", "na UBS X, na Rua". O
#: rótulo "Endereço da escola:" não basta: em pedidos, costuma ser o endereço que a pessoa frequenta.
_ENDERECO_ORGAO = re.compile(
    r"(?:(?:\b(?:n[ao]|à|a)\s+|^\s*)sede\b[^.;\n]{0,90}?"
    r"|\b" + _ORGAO + r"\b[^.;\n]{0,90}?(?:,\s*)?\b(?:situad|sediad|instalad)[oa]s?\s+"
    r"|\bendere[çc]o\s+d[ao]\s+(?:unidade|[óo]rg[ãa]o)\s*:\s*"
    r"|\b(?:n[oa]|à|ao)\s+" + _ORGAO + r"\b[^.;\n,]{0,70},\s*"
    r"|\b(?:pal[áa]cio|pa[çc]o\s+municipal|centro\s+administrativo|edif[íi]cio[-\s]sede)\b[^.;\n]{0,60}?)"
    r"(?:(?:n[oa]|à|em|:)\s*)?[-–:,]?\s*$",
    re.IGNORECASE,
)
#: Expressão de residência ou propriedade da própria pessoa, que prevalece sobre a menção a órgão.
_RESIDENCIA = re.compile(
    r"\b(?:moro|resido|reside|residente|residimos|mora(?:mos)?|morador[a]?|domicili\w*|minh[ao]s?|meus?|"
    r"nossa|nosso|propriet[áa]ri[oa]|endere[çc]o\s+residencial)\b",
    re.IGNORECASE,
)


def endereco_institucional(texto: str, inicio: int) -> bool:
    """Indica se o endereço que começa em ``inicio`` é de sede ou unidade de órgão público: está no
    cabeçalho do documento ou é introduzido pela sede ou pela unidade, sem expressão de residência
    própria na frase."""
    antes = _frase_antes(texto, inicio, 140)
    if _RESIDENCIA.search(antes):
        return False
    return inicio < _fim_cabecalho(texto) or bool(_ENDERECO_ORGAO.search(antes))


def _reclassificar_enderecos(texto: str, deteccoes: list[Deteccao]) -> None:
    orgaos = []
    for d in deteccoes:
        if d.tipo == "ENDERECO" and d.origem.startswith("endereco:") and endereco_institucional(texto, d.inicio):
            d.tipo, d.origem = "ENDERECO_INSTITUCIONAL", d.origem + ":institucional"
            orgaos.append(d)
    # CEP do mesmo endereço, separado dele só por bairro, município e UF.
    for d in deteccoes:
        if d.tipo == "CEP" and any(o.inicio <= d.inicio and (d.fim <= o.fim or _so_complemento(texto[o.fim:d.inicio]))
                                   for o in orgaos):
            d.tipo, d.origem = "ENDERECO_INSTITUCIONAL", d.origem + ":institucional"
    # Nome de pessoa dentro do endereço do órgão é o nome do logradouro ("Rua Doutor Fulano de Tal, 360").
    if orgaos:
        deteccoes[:] = [d for d in deteccoes
                        if not (d.tipo == "NOME" and any(o.inicio <= d.inicio and d.fim <= o.fim for o in orgaos))]


def _so_complemento(trecho: str) -> bool:
    """Trecho curto, sem fim de frase, entre o endereço e o CEP (bairro, município, UF)."""
    return len(trecho) <= 80 and not re.search(r"[.;!?\n]", trecho)


# --------------------------------------------------------------------------- Veículos
#: Frota oficial no plural antes da enumeração de placas ("veículos oficiais de placas …", "as viaturas
#: de placas …"): lista de veículos do órgão, informação de gestão da frota.
_FROTA_ANTES = re.compile(
    r"\b(?:ve[íi]culos\s+oficiais|viaturas|ambul[âa]ncias|ve[íi]culos\s+d[ae]\s+frota|frota\s+(?:oficial|pr[óo]pria|"
    r"municipal|estadual|federal))\b(?:(?!\b(?:carros?|motos?|motocicletas?|caminh[õo]es|caminh[ãa]o|autom[óo]veis|"
    r"particulares?|propriedade|conduzid[oa]s?)\b)[^.;\n]){0,60}?\bplacas\s*:?\s*$",
    re.IGNORECASE,
)
_ENUMERACAO_PLACA = re.compile(r"^\s*(?:,|;|\be\b)\s*$", re.IGNORECASE)
#: Documento que trata da frota oficial: a tabela que associa unidades a placas lista veículos do órgão.
_DOC_FROTA = re.compile(r"\b(?:frota\s+(?:oficial|pr[óo]pria|municipal|estadual)|ve[íi]culos\s+oficiais|viaturas)\b",
                        re.IGNORECASE)


def _reclassificar_placas(texto: str, deteccoes: list[Deteccao]) -> None:
    placas = sorted((d for d in deteccoes if d.tipo == "PLACA"), key=lambda d: d.inicio)
    if not placas:
        return
    nomes = [(d.inicio, d.fim) for d in deteccoes if d.tipo == "NOME"]
    doc_frota = bool(_DOC_FROTA.search(texto))
    anterior: Deteccao | None = None
    for d in placas:
        oficial = bool(_FROTA_ANTES.search(texto[max(0, d.inicio - 120):d.inicio]))
        if not oficial and anterior is not None and anterior.tipo == "PLACA_OFICIAL":
            oficial = bool(_ENUMERACAO_PLACA.match(texto[anterior.fim:d.inicio]))
        if not oficial and doc_frota:
            la, lb = _linha(texto, d.inicio)
            linha = texto[la:lb]
            # Linha de tabela que associa unidade do órgão a placas, sem nome de pessoa.
            oficial = ("|" in linha and bool(_ORGAO_RE.search(linha))
                       and not any(la <= a < lb for a, _ in nomes) and not _PESSOAL.search(linha))
        if oficial:
            d.tipo, d.origem = "PLACA_OFICIAL", d.origem + ":frota"
        anterior = d


# --------------------------------------------------------------------------- Códigos orçamentários
#: Natureza de despesa (Portaria Interministerial STN/SOF nº 163/2001: categoria, grupo, modalidade e
#: elemento, "3.3.90.39"), que tem a forma de endereço IP.
_NATUREZA_DESPESA = re.compile(r"[34]\.[1-9]\.\d{2}\.\d{2}(?:\.\d{2})?")
_CONTEXTO_DESPESA = re.compile(r"\b(?:despesas?|natureza|elemento|dota[çc][ãa]o|or[çc]ament\w*|programa\s+de\s+trabalho)\b",
                               re.IGNORECASE)


def _codigo_orcamentario(texto: str, d: Deteccao) -> bool:
    return (d.tipo == "IP" and bool(_NATUREZA_DESPESA.fullmatch(texto[d.inicio:d.fim]))
            and bool(_CONTEXTO_DESPESA.search(_frase_antes(texto, d.inicio, 80))))


def reclassificar(texto: str, deteccoes: list[Deteccao]) -> list[Deteccao]:
    """Reclassifica os achados de contato, endereço, CEP e placa que o contexto mostra serem do órgão e
    descarta os códigos de natureza de despesa lidos como endereço IP.

    Args:
        texto: Texto completo analisado (normalizado).
        deteccoes: Achados de todos os reconhecedores, em coordenadas de ``texto``; alterados no lugar.

    Returns:
        A própria lista ``deteccoes``.
    """
    _reclassificar_contatos(texto, deteccoes)
    _reclassificar_enderecos(texto, deteccoes)
    _reclassificar_placas(texto, deteccoes)
    deteccoes[:] = [d for d in deteccoes if not _codigo_orcamentario(texto, d)]
    return deteccoes
