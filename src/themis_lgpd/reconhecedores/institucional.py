"""Contatos, endereços e veículos de órgãos, de entidades públicas e de empresas.

Telefone e e-mail de setor, endereço de sede ou de unidade de atendimento e placa, RENAVAM e chassi de
veículo da frota oficial não são dados pessoais: a LAI manda divulgá-los (art. 8º, § 1º, I) e a LGPD
protege apenas dados de pessoa natural (art. 5º, I). Documentos oficiais os trazem no cabeçalho e no
rodapé, nos canais de atendimento ("Dúvidas pelo telefone…", "Informações: setor@orgao.gov.br") e nos
endereços das unidades ("na sede da Secretaria, situada na Rua…"). Pela mesma razão, o endereço e o
contato de pessoa jurídica citados em contratos, licitações e registros (sede da contratada, e-mail de
vendas do fornecedor, endereço de estabelecimento comercial) não são dados pessoais.

Este módulo reclassifica, depois de todos os reconhecedores, os achados de telefone, e-mail, endereço,
CEP, placa, RENAVAM e chassi que o contexto mostra serem do órgão ou de empresa. Os novos tipos
(``CONTATO_INSTITUCIONAL``, ``ENDERECO_INSTITUCIONAL``, ``PLACA_OFICIAL``, ``VEICULO_OFICIAL``,
``CONTATO_EMPRESA`` e ``ENDERECO_EMPRESA``) pertencem à categoria ``INSTITUCIONAL``, que o perfil LAI
mantém legível e sinaliza para revisão. Na dúvida, o achado continua pessoal:

* celular só é do órgão quando qualificado como tal ("WhatsApp institucional", "WhatsApp da Ouvidoria")
  ou anunciado entre os canais do órgão, ao lado de número de serviço ou de e-mail do órgão, sem pessoa
  designada na frase;
* e-mail de provedor pessoal ou com nome de pessoa só é do órgão quando a parte local começa pela sigla
  do setor ("cpl.municipio@…") e o órgão é citado por perto; e-mail de empresa, só ao lado de menção ao
  fornecedor ou à contratada;
* a placa da viatura citada no singular, o endereço e o contato de empresa e os canais do órgão
  reconhecidos pelas regras mais amplas (celular, provedor gratuito, designação do setor, rótulo de
  atendimento) só são reclassificados em documento expedido pelo órgão (com timbre): no pedido ou na
  manifestação do cidadão, a placa aponta o servidor que conduzia o veículo, a empresa costuma ser a
  própria requerente e o número citado ao lado do órgão costuma ser o da própria pessoa;
* expressão de vínculo pessoal ("meu telefone", "residente na", "telefone da genitora") prevalece
  sobre a menção ao órgão;
* o mesmo valor citado em outro ponto do documento recebe a mesma classificação.
"""

from __future__ import annotations

from collections import Counter
from functools import cache, lru_cache

import regex as re

from ..texto import dobrar
from .base import Deteccao

# --------------------------------------------------------------------------- Órgãos e unidades
#: Designações de órgão, entidade ou unidade pública, inclusive as unidades de atendimento de saúde e
#: de assistência social pelas siglas (UBS, UPA, CAPS, CRAS…), o Serviço de Informação ao Cidadão e os
#: equipamentos municipais ("Garagem Municipal", "Mercado Público").
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
    r"posto\s+de\s+\w+|servi[çc]o\s+de\s+informa[çc][ãa]o\s+ao\s+cidad[ãa]o|"
    r"(?:garagem|almoxarifado|p[áa]tio|galp[ãa]o|dep[óo]sito|mercado|terminal|cemit[ée]rio|est[áa]dio|gin[áa]sio|"
    r"teatro|biblioteca|museu|parque)\s+(?:municipal|estadual|p[úu]blic[oa])|"
    r"(?-i:UBSF?|USF|UPA|CAPS\w*|CRAS|CREAS|CEO|CIEVS|SAMU|HEMOCENTRO|SINE|e-?SIC|SIC))"
)
_ORGAO_RE = re.compile(r"\b" + _ORGAO + r"\b", re.IGNORECASE)
#: Linha que começa pela designação de um órgão ou unidade (cabeçalho, rodapé, linha de contato).
_LINHA_ORGAO = re.compile(r"^\s*(?:[-–•*]\s*)?" + _ORGAO + r"\b", re.IGNORECASE)

#: Meios de contato que, citados antes do número, sugerem contato pessoal ("celular", "WhatsApp",
#: "recado"); o órgão também os usa, por isso são examinados à parte (ver :func:`_movel_do_orgao`).
_MEIO_MOVEL = r"celular|whats\w*|zap|recados?"
#: Expressões de vínculo pessoal antes do contato ou do endereço: primeira pessoa, possessivo, papel
#: da pessoa no documento ou qualificação do meio de contato como pessoal.
_VINCULO_PESSOAL = (
    r"eu|meus?|minhas?|me|mim|comigo|estou|estarei|fico|ficarei|posso|sou|tenho|moro|resido|seus?|suas?|dele|dela|"
    r"residente|domiciliad[oa]|morador[a]?|requerente|manifestante|solicitante|interessad[oa]|paciente|"
    r"usu[áa]ri[oa]|respons[áa]vel|acompanhante|genitor[a]?|m[ãa]e|pai|filh[oa]|espos[oa]|marido|companheir[oa]|"
    r"vizinh[oa]|assistid[oa]|autor[a]?|r[ée]u|testemunha|denunciante|v[íi]tima|declarante|candidat[oa]|"
    r"servidor[a]?|pessoal|particular|residencial|resid[êe]ncia|familiar|parente|"
    r"irm[ãa]o?|av[óô]|net[oa]|sobrinh[oa]|ti[oa]|propriet[áa]ri[oa]|contratad[oa]|empregad[oa]"
)
_PESSOAL = re.compile(r"\b(?:" + _VINCULO_PESSOAL + "|" + _MEIO_MOVEL + r")\b", re.IGNORECASE)
_PESSOAL_SEM_MEIO = re.compile(r"\b(?:" + _VINCULO_PESSOAL + r")\b", re.IGNORECASE)
_MEIO_MOVEL_RE = re.compile(r"\b(?:" + _MEIO_MOVEL + r")\b", re.IGNORECASE)
#: Campos de qualificação de pessoa num formulário ("Nome:", "CPF:", "Endereço:"): o telefone na linha
#: seguinte é o da pessoa qualificada.
_CAMPO_PESSOAL = re.compile(
    r"^\s*(?:nome|paciente|usu[áa]ri[oa]|requerente|interessad[oa]|manifestante|solicitante|cpf|rg|cns|nis|"
    r"endere[çc]o(?:\s+residencial)?|resid[êe]ncia|domic[íi]lio|respons[áa]vel|m[ãa]e|pai|genitor[a]?|"
    r"data\s+de\s+nascimento|idade|e-?mail(?:\s+pessoal)?)\b[^:\n]{0,30}:",
    re.IGNORECASE | re.MULTILINE,
)

# --------------------------------------------------------------------------- Timbre e rodapé
#: Primeiras linhas de documento oficial: designação do ente ou do veículo de publicação ("GOVERNO DO
#: ESTADO…", "ESTADO DE GOIÁS", "PODER JUDICIÁRIO", "DIÁRIO OFICIAL…", "CONSÓRCIO INTERMUNICIPAL…").
_TIMBRE = re.compile(r"^\s*(?:governo|estado\s+d[eoa]|rep[úu]blica|munic[íi]pio\s+d[eoa]|poder\s+(?:judici|legislat|"
                     r"execut)|di[áa]rio\s+oficial|cons[óo]rcio\s+(?:p[úu]blico|intermunicipal))", re.IGNORECASE)
#: Paginação ("Página 1 de 2", "fl. 2/3", "Pág. 3").
_PAGINACAO = re.compile(r"\b(?:p[áa]g(?:ina)?\.?|fls?\.?|folha)\s*\d{1,4}(?:\s*(?:/|de)\s*\d{1,4})?(?![\w/])",
                        re.IGNORECASE)
#: Linha de endereço e contatos: começa pelo tipo de logradouro, pelo CEP ou por um meio de contato.
_LINHA_ENDERECO = re.compile(
    r"^\s*(?:rua|r\.|avenida|av\.|alameda|travessa|trav\.|rodovia|rod\.|estrada|pra[çc]a|p[çc]a\.|largo|quadra|setor|"
    r"esplanada|cep|tel(?:efones?)?\.?|fones?|e-?mail|pabx|(?-i:S[A-Z]{2,4})\s+(?:\d|quadra))(?![\wÀ-ú])",
    re.IGNORECASE)
#: Partes da linha de rodapé separadas por travessão, barra vertical ou ponto médio.
_PARTES_RODAPE = re.compile(r"\s[–—|•·-]\s")
_CEP_RE = re.compile(r"\b\d{2}\.?\d{3}-\d{3}\b")
#: Cargo no bloco de assinatura que precede o endereço do órgão no fim do documento.
_CARGO = re.compile(r"\b(?:secret[áa]ri[oa]|diretor[a]?|coordenador[a]?|presidente|prefeit[oa]|(?:sub)?comandante|"
                    r"delegad[oa]|gerente|chefe|superintendente|(?:pr[óo]-)?reitor[a]?|procurador[a]?|promotor[a]?|"
                    r"defensor[a]?|ju[íi]z[a]?|ouvidor[a]?|assessor[a]?|titular|vereador[a]?|governador[a]?|"
                    r"ministr[oa])\b", re.IGNORECASE)
#: Fórmula de endereçamento ("Ao Senhor", "À Senhora", "Ilmo."): o endereço que a segue é do destinatário.
_DESTINATARIO = re.compile(r"\b(?:a[o]?\s+(?:senhor|senhora|sr\.?|sra\.?)|à\s+(?:senhora|sra\.?)|ilm[oa]\.?|exm[oa]\.?|"
                           r"sua\s+senhoria|destinat[áa]ri[oa]|prezad[oa])\b", re.IGNORECASE)


@lru_cache(maxsize=16)
def _documento_do_orgao(texto: str) -> bool:
    """Indica se o documento foi expedido pelo órgão: uma das três primeiras linhas é o timbre ou a
    designação de órgão ou unidade. Pedidos e manifestações de cidadãos não têm timbre."""
    linhas = [m.group() for m in re.finditer(r"[^\n]*\S[^\n]*", texto[:1500])][:3]
    return any(_LINHA_ORGAO.match(linha) or _TIMBRE.match(linha) for linha in linhas)


@lru_cache(maxsize=16)
def _rodapes(texto: str) -> tuple[tuple[int, int], ...]:
    """Linhas de endereço e contatos do órgão no rodapé de documento oficial.

    O documento começa pelo timbre do órgão, e a linha começa pelo logradouro, pelo CEP ou pelo meio
    de contato, sem vínculo pessoal, e reúne várias partes (endereço, bairro, cidade, CEP, telefone).
    É rodapé a linha repetida em outra página, a que vem ao lado da paginação e a última linha do
    documento logo depois do cargo do signatário, fora de bloco de endereçamento a destinatário.
    """
    if not _documento_do_orgao(texto):
        return ()
    linhas = [(m.start(), m.end()) for m in re.finditer(r"[^\n]*\S[^\n]*", texto)]
    conteudo = [" ".join(_PAGINACAO.sub("", texto[a:b]).split()) for a, b in linhas]
    repeticoes = Counter(conteudo)
    saida = []
    for k, (a, b) in enumerate(linhas):
        linha = texto[a:b]
        if (not _LINHA_ENDERECO.match(linha) or _PESSOAL.search(linha) or _CAMPO_PESSOAL.match(linha)
                or not (_PARTES_RODAPE.search(linha) or _CEP_RE.search(linha))):
            continue
        anterior = texto[linhas[k - 1][0]:linhas[k - 1][1]] if k else ""
        seguinte = texto[linhas[k + 1][0]:linhas[k + 1][1]] if k + 1 < len(linhas) else ""
        paginada = any(_PAGINACAO.match(x.strip()) for x in (anterior, seguinte)) or bool(_PAGINACAO.search(linha))
        final = (k == len(linhas) - 1 and bool(_CARGO.search(anterior))
                 and not any(_DESTINATARIO.search(texto, x, y) for x, y in linhas[max(0, k - 4):k]))
        if repeticoes[conteudo[k]] >= 2 or paginada or final:
            saida.append((a, b))
    return tuple(saida)


def _em_rodape(texto: str, pos: int) -> bool:
    return any(a <= pos < b for a, b in _rodapes(texto))


# --------------------------------------------------------------------------- Contatos
#: Indicação de que o meio de contato é do órgão: canal de atendimento ao público, contato da unidade
#: ou do setor, ramal, pedido de resposta feito pelo órgão ("Solicita-se resposta pelo e-mail…").
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
#: Pedido de resposta feito pelo órgão ("Solicita-se resposta pelo e-mail…").
_PEDIDO_DE_RESPOSTA = re.compile(r"\b(?:solicita|requisita|aguarda)-se\s+(?:a\s+)?resposta\b", re.IGNORECASE)
#: Rótulo de campo de contato no início da linha ("Telefone:", "Fone:", "Contato:").
_ROTULO_CONTATO = re.compile(r"^\s*(?:telefones?|fones?|tel\.?|contatos?|e-?mails?)\s*:", re.IGNORECASE)
#: Rótulo que anuncia um canal de atendimento do órgão no período do contato ("Atendimento presencial do
#: SIC: …; telefone …", "Plantão da Defesa Civil: …"). O atendimento domiciliar é prestado na casa da
#: pessoa e não entra.
_ROTULO_CANAL = re.compile(r"\b(?:atendimento(?!\s+domiciliar)|plant[ãa]o|informa[çc][õo]es|d[úu]vidas|ouvidoria|"
                           r"fale\s+conosco|central\s+de\s+atendimento|(?-i:e-?SIC|SIC))\b[^:\n]{0,50}:", re.IGNORECASE)
#: Segmento da linha, separado por travessão ou barra, que designa o órgão logo antes do número
#: ("Fulana – Assessoria de Comunicação da Agência – (91) 3204-0000").
_SEGMENTO_ORGAO = re.compile(r"(?:^|[–—|]\s*)" + _ORGAO + r"\b[^–—|:\n]{0,70}[–—|:]\s*$", re.IGNORECASE)
#: Cabeçalho de mensagem eletrônica ("De:", "Para:", "Cc:").
_CAMPO_MENSAGEM = re.compile(r"^\s*(?:de|para|cc|cco|bcc|from|to|responder\s+para)\s*:", re.IGNORECASE)
#: Números de serviço, que nunca são de pessoa (0800, 0300, 4004…).
_SERVICO = re.compile(r"0[3589]00\d{6,7}|400\d{5}")
#: Número de serviço ou de emergência citado na frase ("0800 091 3434", "Disque-Denúncia 181", "Plantão:
#: 199 e …").
_SERVICO_NA_FRASE = re.compile(r"\b0[3589]00[\s.\-]?\d{3}[\s.\-]?\d{3,4}\b|\b400\d[\s.\-]?\d{4}\b|"
                               r"(?:disque[\w\-]*|ligue|telefones?|plant[ãa]o[^:\n]{0,20}:|:)\s*1\d{2}(?![\d)\-])",
                               re.IGNORECASE)
#: Pessoa designada na frase do contato ("com o fiscal do contrato pelo celular…", "pelo celular do
#: leiloeiro"): o celular é dela.
_PESSOA_DESIGNADA = re.compile(
    r"\b(?:fiscal|leiloeir[oa]|t[ée]cnic[oa]|agente|engenheir[oa]|m[ée]dic[oa]|enfermeir[oa]|professor[a]?|"
    r"motorista|gestor[a]?|pregoeir[oa]|coordenador[a]?|diretor[a]?|secret[áa]ri[oa]|presidente|assessor[a]?|"
    r"analista|assistente|conselheir[oa]|advogad[oa]|corretor[a]?|despachante|sr|sra|senhor[a]?|dr|dra)\b",
    re.IGNORECASE)
#: Qualificação do celular como do órgão, antes do número ("WhatsApp institucional", "celular funcional",
#: "WhatsApp da Ouvidoria") ou depois dele ("(WhatsApp da Comissão de Contratação)").
_MOVEL_QUALIFICADO_ANTES = re.compile(r"\b(?:whats\w*|celular|telefone)\s+(?:institucional|funcional|corporativ[oa]|oficial|"
                                      r"d[aoe]s?\s+" + _ORGAO + r"\b[^,;.\n]{0,40}?)\s*:?\s*$", re.IGNORECASE)
_MOVEL_QUALIFICADO_DEPOIS = re.compile(r"\s*\(?\s*(?:whats\w*\s+)?(?:institucional|funcional|corporativ[oa]|"
                                       r"d[aoe]s?\s+" + _ORGAO + r")\b", re.IGNORECASE)
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
#: Sigla ou nome de setor no início da parte local do e-mail de órgão hospedado em provedor gratuito
#: ("cpl.municipio@…", "licitacao.pm@…", "pss.saude@…", "premio.cultura@…").
_SETOR_NO_EMAIL = re.compile(
    r"(?:cpl|cpel|licita\w*|preg[aã]o|compras|contratos?|contratacao|comissao|prefeitura|pref|pm|camara|"
    r"secretaria|ouvidoria|e?sic|protocolo|gabinete|gab|conselho|cmdca|cmas|cras|creas|caps|ubs|pss|selecao|"
    r"seletivo|concurso|procuradoria|controladoria|ascom|imprensa|"
    r"defesacivil|vigilancia|epidemiologia|regulacao|tfd|samu|premio|editais?|sms|semed|semsa|seduc|sesau|"
    r"saude|educacao|assistencia|tributos|fiscalizacao|obras|agricultura|cultura|esportes?|turismo|transito)"
    r"(?=[._\-\d]|$)", re.IGNORECASE)
#: Setor comercial no início da parte local do e-mail de empresa ("vendas@…", "comercial@…").
_SETOR_EMPRESA_NO_EMAIL = re.compile(r"(?:vendas|comercial|licitac\w*|contato|atendimento|sac|financeiro|faturamento|"
                                     r"orcamentos?|pedidos|suporte|administrativo|adm|juridico)", re.IGNORECASE)
#: Fornecedor, contratada ou empresa citados na frase do contato ou do endereço.
_PESSOA_JURIDICA = re.compile(
    r"\b(?:fornec\w*|contratad[oa]s?|empresas?|licitantes?|adjudicat[áa]ri\w*|arrematantes?|ordens?\s+de\s+"
    r"(?:fornecimento|servi[çc]o)|raz[ãa]o\s+social|ltda|eireli|epp|cnpj|(?-i:S/?A|ME))\b", re.IGNORECASE)


@cache
def _listas_nomes() -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """Prenomes (sem os ambíguos), prenomes ambíguos e sobrenomes, sem acentos e em minúsculas."""
    from .nomes import ambiguos, prenomes, sobrenomes

    return frozenset(prenomes() - ambiguos()), frozenset(ambiguos()), frozenset(sobrenomes())


def _tem_nome(local: str) -> bool:
    """Indica se a parte local de um e-mail contém nome de pessoa ("maria.souza", "clara.lima", "jsilva",
    "carlamendes82"): um prenome inteiro ou no início de uma parte, sobrenome ou prenome ambíguo ao lado
    de outra parte, ou sobrenome precedido de iniciais. Um sobrenome sozinho ("frota@") não basta: também
    é palavra comum que nomeia o setor."""
    prenomes, ambiguos, sobrenomes = _listas_nomes()
    partes = _PARTES_LOCAL.findall(dobrar(local))
    if any(p in prenomes for p in partes):
        return True
    if len(partes) >= 2 and any(p in sobrenomes or p in ambiguos for p in partes):
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
    """Fim do cabeçalho do documento (timbre): o primeiro bloco de duas a oito linhas curtas, separado do
    corpo por uma linha em branco, quando uma das três primeiras linhas designa órgão ou unidade. Zero se
    não houver cabeçalho; um texto de parágrafo único ("Secretaria de Saúde, solicito…") não tem."""
    inicio = len(texto) - len(texto.lstrip())
    fim = texto.find("\n\n", inicio)
    if fim < 0 or not texto[fim:].strip():
        return 0
    linhas = texto[inicio:fim].split("\n")
    if not 2 <= len(linhas) <= 8 or any(len(linha) > 100 for linha in linhas):
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


def _periodo_antes(texto: str, inicio: int, limite: int = 200) -> str:
    """Como :func:`_frase_antes`, mas sem cortar no ponto e vírgula: o período inteiro que antecede a
    posição ("Atendimento do SIC: Rua…, das 9h às 17h; telefone …")."""
    a = max(0, inicio - limite)
    trecho = texto[a:inicio]
    cortes = [m.end() - 1 for m in _FIM_FRASE.finditer(trecho) if m.group() != ";"]
    return trecho[max(trecho.rfind("\n"), *cortes, -1) + 1:]


def _frase(texto: str, inicio: int, fim: int) -> tuple[int, int]:
    """Limites da frase que contém o trecho, sem atravessar linhas."""
    la, lb = _linha(texto, inicio)
    antes = [m.end() for m in _FIM_FRASE.finditer(texto, la, inicio)]
    a = antes[-1] if antes else la
    m = _FIM_FRASE.search(texto, fim, lb)
    return a, (m.start() if m else lb)


def _sem(texto: str, a: int, b: int, trechos: list[tuple[int, int]]) -> str:
    """Texto de ``a`` a ``b`` com os trechos indicados apagados (substituídos por espaço)."""
    partes = list(texto[a:b])
    for x, y in trechos:
        for k in range(max(a, x), min(b, y)):
            partes[k - a] = " "
    return "".join(partes)


def _movel_do_orgao(texto: str, d: Deteccao, contatos: list[Deteccao]) -> bool:
    """Indica se o celular ou WhatsApp é canal do órgão: qualificado como institucional ou do órgão,
    junto ao número ("WhatsApp institucional", "(WhatsApp da Comissão)"), ou anunciado numa frase de
    canais do órgão que traz também número de serviço ("0800…", "Disque 181", "Plantão: 199") ou e-mail do
    órgão, sem pessoa designada nem vínculo pessoal na frase."""
    la, _ = _linha(texto, d.inicio)
    if _MOVEL_QUALIFICADO_ANTES.search(texto[max(la, d.inicio - 80):d.inicio]):
        return True
    if _MOVEL_QUALIFICADO_DEPOIS.match(texto, d.fim):
        return True
    a, b = _frase(texto, d.inicio, d.fim)
    # Os próprios contatos são apagados da frase: um e-mail como "fiscal.obras@…" não designa pessoa.
    frase = _sem(texto, a, b, [(c.inicio, c.fim) for c in contatos])
    if _PESSOAL_SEM_MEIO.search(frase) or _PESSOA_DESIGNADA.search(frase):
        return False
    if _SERVICO_NA_FRASE.search(frase):
        return True
    return any(c.tipo == "EMAIL" and a <= c.inicio < b and email_institucional(texto[c.inicio:c.fim])
               for c in contatos)


def _email_de_setor(texto: str, d: Deteccao) -> bool:
    """E-mail do órgão em provedor gratuito ou com nome próprio na parte local ("cpl.joaopessoa@…",
    "premio.anaclara@municipio.gov.br"): a parte local começa pela sigla ou pelo nome do setor, o domínio
    é público ou de provedor gratuito (o de empresa é o canal da própria empresa) e o órgão é citado na
    mesma frase ou nos 200 caracteres anteriores."""
    valor = texto[d.inicio:d.fim]
    local, _, dominio = valor.lower().rpartition("@")
    if not _SETOR_NO_EMAIL.match(dobrar(local)):
        return False
    if not (_DOMINIO_PUBLICO.search(dominio) or _PROVEDORES_PESSOAIS.search(dominio)):
        return False
    a, b = _frase(texto, d.inicio, d.fim)
    return bool(_ORGAO_RE.search(_sem(texto, max(0, min(a, d.inicio - 200)), b, [(d.inicio, d.fim)])))


def _email_de_empresa(texto: str, d: Deteccao) -> bool:
    """E-mail comercial de fornecedor ou contratada ("vendas@empresa.com.br" nas ordens de fornecimento
    de uma ata de registro de preços), em documento expedido pelo órgão: setor comercial na parte local,
    domínio que não é de órgão e menção ao fornecedor, à contratada ou à empresa na frase. Num pedido, o
    e-mail da empresa é o canal pelo qual a própria requerente recebe a resposta."""
    valor = texto[d.inicio:d.fim]
    local, _, dominio = valor.lower().rpartition("@")
    if not _documento_do_orgao(texto) or _DOMINIO_PUBLICO.search(dominio):
        return False
    if not _SETOR_EMPRESA_NO_EMAIL.match(dobrar(local)):
        return False
    a, b = _frase(texto, d.inicio, d.fim)
    return bool(_PESSOA_JURIDICA.search(_sem(texto, a, b, [(d.inicio, d.fim)])))


def _cabecalho_de_mensagem(texto: str, d: Deteccao, la: int) -> bool:
    """E-mail do setor no cabeçalho de mensagem ("Para: Núcleo de Saúde <saude@orgao.gov.br>", "De:
    setor@orgao.gov.br"): sem nome exibido ou com o nome de órgão ou unidade."""
    linha_antes = texto[la:d.inicio]
    if not _CAMPO_MENSAGEM.match(linha_antes):
        return False
    exibido = re.split(r"[:;,>]", linha_antes)[-1].strip(" \t<\"'")
    return not exibido or bool(_LINHA_ORGAO.match(exibido))


def _contexto_contato(texto: str, d: Deteccao, anterior: int, contatos: list[Deteccao]) -> str:
    """Classifica uma ocorrência de telefone ou e-mail: ``orgao``, ``empresa``, ``pessoal`` ou ``neutro``.

    Args:
        texto: Texto analisado.
        d: Achado de telefone ou e-mail.
        anterior: Fim do contato anterior; o vínculo pessoal é procurado só depois dele, para que o
            celular de uma pessoa não contamine o e-mail do setor citado em seguida.
        contatos: Todos os achados de telefone e e-mail do texto.
    """
    valor = texto[d.inicio:d.fim]
    if d.tipo == "TELEFONE" and _SERVICO.fullmatch(_digitos(valor)):
        return "orgao"
    antes = _frase_antes(texto, d.inicio)
    la, _ = _linha(texto, d.inicio)
    linha_antes = texto[la:d.inicio]
    perto = texto[max(la, anterior, d.inicio - 60):d.inicio]
    if _em_rodape(texto, d.inicio):
        return "orgao"
    if d.tipo == "EMAIL" and email_institucional(valor) and _cabecalho_de_mensagem(texto, d, la):
        return "orgao"
    if _PESSOAL_SEM_MEIO.search(perto):
        return "pessoal"
    # As regras seguintes de canal do órgão (celular, provedor gratuito, designação do setor, rótulo de
    # atendimento) só valem no documento expedido pelo órgão: no pedido do cidadão, o número citado ao
    # lado do órgão costuma ser o da própria pessoa.
    doc_orgao = _documento_do_orgao(texto)
    if d.tipo == "TELEFONE" and (celular(valor) or _MEIO_MOVEL_RE.search(perto)):
        return "orgao" if doc_orgao and _movel_do_orgao(texto, d, contatos) else "pessoal"
    if _MEIO_MOVEL_RE.search(perto):
        return "pessoal"
    if d.tipo == "EMAIL" and not email_institucional(valor):
        if doc_orgao and _email_de_setor(texto, d):
            return "orgao"
        return "empresa" if _email_de_empresa(texto, d) else "pessoal"
    if d.inicio < _fim_cabecalho(texto):
        return "orgao"
    if _CANAL_ORGAO.search(antes) or _LINHA_ORGAO.match(linha_antes):
        return "orgao"
    if doc_orgao and (_SEGMENTO_ORGAO.search(linha_antes) or _PEDIDO_DE_RESPOSTA.search(antes)):
        return "orgao"
    periodo = _periodo_antes(texto, d.inicio)
    rotulo = _ROTULO_CANAL.search(periodo) if doc_orgao else None
    if rotulo and not _PESSOAL.search(periodo, rotulo.start()):
        return "orgao"
    # Rótulo "Telefone:" no início da linha: vale a linha anterior (o nome do órgão no cabeçalho ou o
    # campo de qualificação da pessoa). Sob o rótulo "Contato:", o e-mail de domínio público e sem nome de
    # pessoa é o do setor que publica o documento.
    if _ROTULO_CONTATO.match(linha_antes):
        acima = _linha_anterior(texto, la)
        if _LINHA_ORGAO.match(acima) and not _CAMPO_PESSOAL.match(acima) and not _PESSOAL.search(acima):
            return "orgao"
        if doc_orgao and d.tipo == "EMAIL" and re.match(r"\s*contatos?\s*:", linha_antes, re.IGNORECASE) \
                and not _CAMPO_PESSOAL.match(acima):
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
        situacao.append(_contexto_contato(texto, d, anterior, contatos))
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
        if "pessoal" in c:
            continue
        if "orgao" in c:
            d.tipo, d.origem = "CONTATO_INSTITUCIONAL", d.origem + ":institucional"
        elif "empresa" in c:
            d.tipo, d.origem = "CONTATO_EMPRESA", d.origem + ":empresa"


# --------------------------------------------------------------------------- Endereços
_FIM_ENDERECO_ORGAO = r"(?:(?:n[oa]|à|em|:)\s*)?[-–:,]?\s*$"
#: Local público ou de serviço onde fica a unidade ("no Galpão da Defesa Civil, na Rua…", "no pátio da
#: Garagem Municipal, Rua…").
_LOCAL_DE_SERVICO = (r"(?:audit[óo]rio|plen[áa]rio|sal[ãa]o\s+(?:nobre|de\s+(?:eventos|reuni[õo]es|atos))|"
                     r"sala\s+de\s+(?:reuni[õo]es|sess[õo]es|confer[êe]ncias|treinamento)|gin[áa]sio|est[áa]dio|"
                     r"quadra\s+(?:poliesportiva|de\s+esportes)|teatro|centro\s+de\s+(?:conven[çc][õo]es|eventos)|"
                     r"centro\s+cultural|gal?p[ãa]o|garagem|p[áa]tio|almoxarifado|dep[óo]sito|terminal|rodovi[áa]ria|"
                     r"biblioteca|museu)")
#: Endereço introduzido pela sede ou pela unidade: "na sede da …", "a Diretoria …, situada na", "na UBS
#: X, na Rua", "no Galpão da Defesa Civil, na Rua". Num pedido, a mesma construção costuma descrever o
#: lugar que a própria pessoa frequenta; por isso só vale no anúncio do serviço (ver :data:`_ANUNCIO`).
_ENDERECO_SEDE = re.compile(
    r"(?:(?:\b(?:n[ao]|à|a)\s+|^\s*)sede\b[^.;\n]{0,90}?"
    r"|\b" + _ORGAO + r"\b[^.;\n]{0,90}?(?:,\s*)?\b(?:situad|sediad|instalad)[oa]s?\s+"
    r"|\b(?:n[oa]|à|ao)\s+(?:" + _LOCAL_DE_SERVICO + r"\s+(?:d[aeo]s?\s+)?)?" + _ORGAO + r"\b[^.;\n,]{0,70},\s*)"
    + _FIM_ENDERECO_ORGAO,
    re.IGNORECASE,
)
#: Rótulo do endereço da unidade ("Endereço da unidade:"), canal de atendimento ("Atendimento presencial
#: do SIC:") e edifício-sede do governo ("Palácio …", "Centro Administrativo …"), que bastam por si.
_ENDERECO_ORGAO = re.compile(
    r"(?:\bendere[çc]o\s+d[ao]\s+(?:unidade|[óo]rg[ãa]o)\s*:\s*"
    r"|\batendimento(?!\s+domiciliar)(?:\s+(?:presencial|ao\s+p[úu]blico))?(?:\s+d[aoe]s?\s+[^:\n]{1,50})?\s*:\s*"
    r"|\b(?:pal[áa]cio|pa[çc]o\s+municipal|centro\s+administrativo|edif[íi]cio[-\s]sede)\b[^.;\n]{0,60}?)"
    + _FIM_ENDERECO_ORGAO,
    re.IGNORECASE,
)
#: Local público de evento ou de serviço logo antes do endereço ("Local: Auditório da Regional – Rua…",
#: "no Plenário …, Rua…"): ninguém mora em auditório, galpão ou pátio.
_LOCAL_ANTES = re.compile(r"\b" + _LOCAL_DE_SERVICO + r"\b[^.;\n]{0,70}?[,–\-]\s*(?:(?:n[oa]|à|em)\s+)?$",
                          re.IGNORECASE)
#: Anúncio do serviço pelo órgão, na mesma frase do endereço: horário de atendimento ("de segunda a
#: sexta-feira, das 8h às 17h"), hora do ato ("às 10 horas, … compareceu") ou providência a cargo do
#: público ou do órgão ("poderão ser retirados", "deverá ser protocolada", "fica assegurada vista").
_ANUNCIO = re.compile(
    r"\b(?:das?\s+\d{1,2}\s*(?:h|:\d{2}|horas)|de\s+segunda\s+a\s+(?:sexta|s[áa]bado)|em\s+dias\s+[úu]teis|"
    r"no\s+hor[áa]rio|[àa]s\s+\d{1,2}\s*(?:h|:\d{2}|horas)|"
    r"compareceu|compareceram|reuni(?:u|ram)-se|assegurad[oa]|"
    r"(?:poder[áã]o?|dever[áã]o?|ser[áã]o?)\s+(?:ser\s+)?(?:retirad|entregue|protocolad|apresentad|recebid|"
    r"realizad|prestad|atendid|mantid)\w*)",
    re.IGNORECASE,
)
#: Expressão de residência ou propriedade da própria pessoa, que prevalece sobre a menção a órgão.
_RESIDENCIA = re.compile(
    r"\b(?:moro|resido|reside|residente|residimos|mora(?:mos)?|morador[a]?|domicili\w*|minh[ao]s?|meus?|"
    r"nossa|nosso|propriet[áa]ri[oa]|endere[çc]o\s+residencial)\b",
    re.IGNORECASE,
)
#: Sede de pessoa jurídica na linguagem dos contratos e registros: "com sede na", "estabelecida na",
#: "sediada em".
_SEDE_DE_EMPRESA = re.compile(r"\b(?:com\s+sede|sediad[oa]|estabelecid[oa])\s*"
                              r"(?:n[oa]|à|em)?\s*[,:]?\s*$", re.IGNORECASE)
#: Estabelecimento comercial logo antes do endereço ("Pastelaria Boa Massa, Rua…", "na Mercearia São
#: Jorge, Avenida…").
_ESTABELECIMENTO = re.compile(
    r"\b(?:loja|pastelaria|padaria|panificadora|mercearia|mercadinho|supermercado|restaurante|lanchonete|bar|"
    r"farm[áa]cia|drogaria|oficina|borracharia|posto\s+de\s+combust[íi]vel|hotel|pousada|academia|escrit[óo]rio|"
    r"f[áa]brica|ind[úu]stria|armaz[ée]m|distribuidora|transportadora|construtora|imobili[áa]ria|barbearia|"
    r"sal[ãa]o\s+de\s+beleza|a[çc]ougue|sorveteria|pizzaria|churrascaria|lot[ée]rica|empresa)\b"
    r"(?-i:\s+(?:d[aeo]s?\s+|&\s+|e\s+)?[A-ZÀ-Ú0-9][\wÀ-ú'’&.]*){1,6}\s*[,–\-]\s*(?:(?:n[oa]|à|em)\s+)?$",
    re.IGNORECASE)
#: Bloco de formulário que qualifica pessoa jurídica ("Razão social:", "CNPJ:", "Empregador:") ou pessoa
#: natural ("Nome:", "CPF:").
_CAMPO_EMPRESA = re.compile(r"^\s*(?:raz[ãa]o\s+social|cnpj|cnae|empregador|empresa|estabelecimento|contratada|"
                            r"fornecedor[a]?|nome\s+(?:empresarial|fantasia))\b[^:\n]{0,30}:", re.IGNORECASE)
_CAMPO_PESSOA = re.compile(r"^\s*(?:nome|cpf|rg|nis|cns|data\s+de\s+nascimento|trabalhador[a]?|requerente|"
                           r"paciente|v[íi]tima|interessad[oa])\b[^:\n]{0,30}:", re.IGNORECASE)


def endereco_institucional(texto: str, inicio: int) -> bool:
    """Indica se o endereço que começa em ``inicio`` é de sede ou unidade de órgão público, sem expressão
    de residência própria na frase: está no cabeçalho ou no rodapé do documento, segue o rótulo do
    endereço da unidade, o canal de atendimento, o edifício-sede ou um local público de serviço
    (auditório, galpão, pátio), ou é introduzido pela sede ou pela unidade numa frase que anuncia o
    serviço."""
    antes = _frase_antes(texto, inicio, 140)
    if _RESIDENCIA.search(antes):
        return False
    if inicio < _fim_cabecalho(texto) or _em_rodape(texto, inicio) or _ENDERECO_ORGAO.search(antes):
        return True
    if _LOCAL_ANTES.search(antes):
        return True
    if not _ENDERECO_SEDE.search(antes):
        return False
    a, b = _frase(texto, inicio, inicio)
    return bool(_ANUNCIO.search(texto, max(0, a - 1), min(len(texto), b + 200)))


def _bloco_de_empresa(texto: str, inicio: int) -> bool:
    """O endereço é campo de um bloco de formulário que qualifica pessoa jurídica: entre a linha em branco
    anterior e o endereço há campo de empresa ("Razão social:", "CNPJ:") e nenhum campo de pessoa."""
    la, _ = _linha(texto, inicio)
    bloco_ini = texto.rfind("\n\n", 0, la)
    bloco = texto[bloco_ini + 1 if bloco_ini >= 0 else 0:la]
    linhas = bloco.split("\n")
    return any(_CAMPO_EMPRESA.match(x) for x in linhas) and not any(_CAMPO_PESSOA.match(x) for x in linhas)


def endereco_de_empresa(texto: str, inicio: int) -> bool:
    """Indica se o endereço que começa em ``inicio`` é de pessoa jurídica: campo de endereço de bloco que
    qualifica a empresa ou, em documento expedido pelo órgão, sede de empresa citada na frase ("…Ltda.,
    CNPJ…, com sede na Rua…") e estabelecimento comercial logo antes ("Pastelaria Boa Massa, Avenida…").
    Num pedido, o endereço da empresa costuma ser o da própria requerente."""
    antes = _frase_antes(texto, inicio, 200)
    if _RESIDENCIA.search(antes):
        return False
    if _bloco_de_empresa(texto, inicio):
        return True
    if not _documento_do_orgao(texto):
        return False
    return bool(_SEDE_DE_EMPRESA.search(antes) and _PESSOA_JURIDICA.search(antes)) or bool(_ESTABELECIMENTO.search(antes))


def _reclassificar_enderecos(texto: str, deteccoes: list[Deteccao]) -> None:
    orgaos = []
    for d in deteccoes:
        if d.tipo != "ENDERECO" or not d.origem.startswith("endereco:"):
            continue
        if endereco_institucional(texto, d.inicio):
            d.tipo, d.origem = "ENDERECO_INSTITUCIONAL", d.origem + ":institucional"
            orgaos.append(d)
        elif endereco_de_empresa(texto, d.inicio):
            d.tipo, d.origem = "ENDERECO_EMPRESA", d.origem + ":empresa"
            orgaos.append(d)
    # CEP do mesmo endereço, separado dele só por bairro, município e UF, e CEP do rodapé.
    for d in deteccoes:
        if d.tipo != "CEP":
            continue
        dono = next((o for o in orgaos if o.inicio <= d.inicio
                     and (d.fim <= o.fim or _so_complemento(texto[o.fim:d.inicio]))), None)
        if dono is not None or _em_rodape(texto, d.inicio):
            tipo = dono.tipo if dono is not None else "ENDERECO_INSTITUCIONAL"
            d.tipo, d.origem = tipo, d.origem + (":empresa" if tipo == "ENDERECO_EMPRESA" else ":institucional")
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
#: Documento que trata da frota oficial ou da alienação de bens públicos: a tabela que associa unidades
#: ou lotes a placas lista veículos do órgão. Leilão de veículos apreendidos ou removidos não entra: os
#: veículos são de particulares.
_DOC_FROTA = re.compile(r"\b(?:frota|ve[íi]culos\s+(?:oficiais|pr[óo]prios)|viaturas|bens\s+(?:m[óo]veis\s+)?"
                        r"inserv[íi]veis|aliena[çc][ãa]o\s+de\s+(?:bens|ve[íi]culos))\b", re.IGNORECASE)
_DOC_APREENSAO = re.compile(r"\b(?:apreendid|removid|recolhid|retid|abandonad|n[ãa]o\s+retirad|custodiad)[oa]s\b",
                            re.IGNORECASE)
#: Veículo que, pela própria designação, é de serviço público ("a viatura", "a ambulância", "a unidade
#: móvel").
_VEICULO_DE_SERVICO = r"(?:viaturas?|ambul[âa]ncias?|unidades?\s+m[óo]ve(?:l|is))"
#: Veículo citado pelo tipo ou pela marca.
_VEICULO = (r"(?:ve[íi]culos?|carros?|autom[óo]ve(?:l|is)|caminh(?:[ãa]o|[õo]es)|caminhonetes?|camionetes?|[ôo]nibus|"
            r"micro-?[ôo]nibus|vans?|motos?|motocicletas?|lanchas?|barcos?|tratores?|retroescavadeiras?|"
            r"motoniveladoras?|utilit[áa]rios?|furg(?:[ãa]o|[õo]es)|picapes?|(?-i:Fiat|VW|Volkswagen|Chevrolet|GM|Ford|"
            r"Renault|Toyota|Mercedes(?:-Benz)?|M\.\s?Benz|Iveco|Hyundai|Honda|Yamaha|Nissan|Peugeot|Citro[ëe]n|"
            r"Mitsubishi|Jeep|Kia|Volvo|Scania|Agrale|Marcopolo|JAC|BYD|Caterpillar))")
_VEICULO_RE = re.compile(r"\b(?:" + _VEICULO_DE_SERVICO + "|" + _VEICULO + r")\b", re.IGNORECASE)
_VEICULO_DE_SERVICO_RE = re.compile(r"\b" + _VEICULO_DE_SERVICO + r"\b", re.IGNORECASE)
#: Qualificação que mostra ser o veículo do órgão: "oficial", "da frota", "do Município", "da Secretaria",
#: "adaptada da Policlínica".
_QUALIFICA_OFICIAL = re.compile(r"\b(?:oficia(?:l|is)|da\s+frota|institucional|d[aoe]s?\s+(?:munic[íi]pio|prefeitura|"
                                r"estado|uni[ãa]o|" + _ORGAO + r"))\b", re.IGNORECASE)
#: Posse por pessoa natural ou condução em relato policial: o veículo é particular.
_VEICULO_PARTICULAR = re.compile(
    r"\b(?:particular(?:es)?|pr[óo]pri[oa]s?|propriedade|em\s+nome\s+d|registrad[oa]\s+em|indiciad[oa]|suspeit[oa]s?|"
    r"infrator(?:a)?|conduzid[oa]\s+p|d[oa]s?\s+(?:requerente|manifestante|solicitante|interessad[oa]|paciente|"
    r"usu[áa]ri[oa]|acompanhante|genitor[a]?|m[ãa]e|pai|filh[oa]|espos[oa]|marido|companheir[oa]|vizinh[oa]|"
    r"assistid[oa]|autor[a]?|r[ée]u|testemunha|denunciante|v[íi]tima|declarante|candidat[oa]|servidor[a]?|"
    r"irm[ãa]o?|av[óô]|net[oa]|sobrinh[oa]|ti[oa]|propriet[áa]ri[oa]|empregad[oa]|condutor[a]?|acusad[oa]|"
    r"investigad[oa]|cidad[ãa]o?))\b", re.IGNORECASE)
_FROTA_RE = re.compile(r"\bfrota\b", re.IGNORECASE)
#: Até duas palavras entre duas designações do mesmo veículo, sem pontuação.
_APOSTO_VEICULO = re.compile(r"\s+(?:[\wÀ-ú/.\-]+\s+){0,2}")
_IDENTIFICADORES_VEICULO = ("PLACA", "RENAVAM", "CHASSI")


def _veiculo_do_orgao(texto: str, d: Deteccao) -> bool:
    """Indica se a placa, o RENAVAM ou o chassi citados no singular são de veículo do órgão.

    Vale a designação do veículo mais próxima antes do identificador, na mesma frase: veículo de serviço
    público ("a viatura QKM5E21", "a ambulância de placa…") ou qualificado como do órgão ("o veículo oficial
    do Escritório", "a Fiat Doblò adaptada da Policlínica, RENAVAM…"), sem marca de posse particular entre a
    designação e o identificador; ou, sem designação qualificada, a frase trata da frota ("…no plano de
    abastecimento da frota"), sem vínculo pessoal.
    """
    a, b = _frase(texto, d.inicio, d.fim)
    mencoes = list(_VEICULO_RE.finditer(texto, a, d.inicio))
    if mencoes:
        # Designações contíguas formam uma só ("a unidade móvel Van da Cidadania", "a ambulância Fiat
        # Ducato"): vale a primeira.
        k = len(mencoes) - 1
        while k > 0 and _APOSTO_VEICULO.fullmatch(texto, mencoes[k - 1].end(), mencoes[k].start()):
            k -= 1
        m = mencoes[k]
        trecho = texto[m.start():d.inicio]
        if _VEICULO_PARTICULAR.search(trecho):
            return False
        if _VEICULO_DE_SERVICO_RE.match(trecho) or _QUALIFICA_OFICIAL.search(trecho):
            return True
    frase = texto[a:b]
    return bool(_FROTA_RE.search(frase)) and not _PESSOAL.search(frase) and not _VEICULO_PARTICULAR.search(frase)


def _reclassificar_veiculos(texto: str, deteccoes: list[Deteccao]) -> None:
    """Placa, RENAVAM e chassi de veículo do órgão: enumeração após a frota no plural, citação no
    singular com designação de veículo do órgão em documento expedido pelo órgão, e linhas de tabela de
    documento sobre a frota ou sobre a alienação de bens públicos. A linha de tabela com placa oficial leva
    junto o RENAVAM e o chassi, e o mesmo identificador recebe a mesma classificação em todo o documento."""
    veiculos = sorted((d for d in deteccoes if d.tipo in _IDENTIFICADORES_VEICULO), key=lambda d: d.inicio)
    if not veiculos:
        return
    nomes = [(d.inicio, d.fim) for d in deteccoes if d.tipo == "NOME"]
    doc_frota = bool(_DOC_FROTA.search(texto)) and not _DOC_APREENSAO.search(texto)
    # A citação no singular só vale em documento expedido pelo órgão: no pedido ou na manifestação do
    # cidadão, a placa da viatura costuma apontar o servidor que a conduzia.
    doc_orgao = _documento_do_orgao(texto)
    oficiais: set[str] = set()
    linhas_oficiais: set[tuple[int, int]] = set()
    anterior: Deteccao | None = None
    marcados: list[Deteccao] = []
    for d in veiculos:
        la, lb = _linha(texto, d.inicio)
        oficial = d.tipo == "PLACA" and bool(_FROTA_ANTES.search(texto[max(0, d.inicio - 120):d.inicio]))
        if not oficial and d.tipo == "PLACA" and anterior is not None and anterior in marcados:
            oficial = bool(_ENUMERACAO_PLACA.match(texto[anterior.fim:d.inicio]))
        linha = texto[la:lb]
        if not oficial and "|" in linha:
            # Linha de tabela que associa unidade do órgão ou lote de alienação a placas, sem nome de pessoa.
            sem_pessoa = not any(la <= x < lb for x, _ in nomes) and not _PESSOAL.search(linha)
            oficial = sem_pessoa and (doc_frota or (d.tipo == "PLACA" and bool(_DOC_FROTA.search(texto))
                                                    and bool(_ORGAO_RE.search(linha))))
        if not oficial and "|" not in linha and doc_orgao:
            oficial = _veiculo_do_orgao(texto, d)
        if oficial:
            marcados.append(d)
            oficiais.add(_chave_veiculo(texto, d))
            if "|" in linha:
                linhas_oficiais.add((la, lb))
        anterior = d
    for d in veiculos:
        if d in marcados or _chave_veiculo(texto, d) in oficiais or _linha(texto, d.inicio) in linhas_oficiais:
            if d.tipo == "PLACA":
                d.tipo, d.origem = "PLACA_OFICIAL", d.origem + ":frota"
            else:
                d.tipo, d.origem = "VEICULO_OFICIAL", d.origem + ":frota"


def _chave_veiculo(texto: str, d: Deteccao) -> str:
    return re.sub(r"[\W_]", "", texto[d.inicio:d.fim]).upper()


# --------------------------------------------------------------------------- Números públicos
#: Natureza de despesa (Portaria Interministerial STN/SOF nº 163/2001: categoria, grupo, modalidade e
#: elemento, "3.3.90.39"), que tem a forma de endereço IP.
_NATUREZA_DESPESA = re.compile(r"[34]\.[1-9]\.\d{2}\.\d{2}(?:\.\d{2})?")
_CONTEXTO_DESPESA = re.compile(r"\b(?:despesas?|natureza|elemento|dota[çc][ãa]o|or[çc]ament\w*|programa\s+de\s+trabalho)\b",
                               re.IGNORECASE)
#: Subitem de edital ou contrato e código de classificação pública com a forma de endereço IP ("subitem
#: 8.3.1.2", "COBRADE 1.3.2.1.4").
_NUMERACAO_ANTES = re.compile(r"\b(?:(?:sub)?ite(?:m|ns)|cl[áa]usulas?|se[çc][ãa]o|cap[íi]tulo|anexo|par[áa]grafo|"
                              r"(?-i:COBRADE|CNAE|NCM|CBO|CATMAT|CATSER))\s*(?:n[º°o]\.?\s*)?$", re.IGNORECASE)
#: Chave de acesso de nota fiscal eletrônica: 44 dígitos, em geral em grupos de quatro, com dígito
#: verificador.
_CHAVE_NFE = re.compile(r"(?<![\d])(?:\d{4}[ .]?){10}\d{4}(?![\d])")
#: Designação de ato público logo antes de número tomado por telefone ("Convênio nº 912345/2021"). Processo,
#: recurso e certidão ficam de fora: o número pode ser de procedimento sobre a pessoa.
_ATO_ANTES = re.compile(r"\b(?:conv[êe]nio|contrato|lei|decreto|portaria|edital|resolu[çc][ãa]o|of[íi]cio|empenho|"
                        r"preg[ãa]o|licita[çc][ãa]o|termo\s+de\s+(?:fomento|colabora[çc][ãa]o|coopera[çc][ãa]o))\b"
                        r"[^\n\d]{0,25}n[º°o]\.?\s*$", re.IGNORECASE)


#: Símbolo de cargo em comissão ou de função gratificada ("símbolo CC-3", "símbolo DAS-4").
_SIMBOLO_CARGO = re.compile(r"\bs[íi]mbolo\s+(?-i:[A-Z]{1,5})[-\s]?$", re.IGNORECASE)


def _codigo_orcamentario(texto: str, d: Deteccao) -> bool:
    return (d.tipo == "IP" and bool(_NATUREZA_DESPESA.fullmatch(texto[d.inicio:d.fim]))
            and bool(_CONTEXTO_DESPESA.search(_frase_antes(texto, d.inicio, 80))))


def _numeracao_de_item(texto: str, d: Deteccao) -> bool:
    return d.tipo == "IP" and bool(_NUMERACAO_ANTES.search(texto, max(0, d.inicio - 40), d.inicio))


def _nfe_dv_valido(digitos: str) -> bool:
    """Dígito verificador da chave de acesso da NF-e (módulo 11, pesos de 2 a 9 da direita para a esquerda)."""
    soma = sum(int(c) * (2 + k % 8) for k, c in enumerate(reversed(digitos[:43])))
    dv = 11 - soma % 11
    return int(digitos[43]) == (0 if dv >= 10 else dv)


def _chaves_nfe(texto: str) -> list[tuple[int, int]]:
    saida = []
    for m in _CHAVE_NFE.finditer(texto):
        digitos = re.sub(r"\D", "", m.group())
        if len(digitos) == 44 and _nfe_dv_valido(digitos):
            saida.append(m.span())
    return saida


def _numero_publico(texto: str, d: Deteccao, chaves: list[tuple[int, int]], veiculos: list[Deteccao]) -> bool:
    """Número público lido como telefone, cartão ou conta: dentro da chave de acesso de nota fiscal, logo
    após a designação de um ato ("Convênio nº"), RENAVAM lido como telefone e símbolo de cargo em comissão
    lido como conta ("símbolo CC-3")."""
    if any(a <= d.inicio and d.fim <= b for a, b in chaves):
        return d.tipo in ("TELEFONE", "CARTAO", "CONTA_BANCARIA", "PROTOCOLO", "DOCUMENTO", "CPF", "CNS", "PIS")
    if d.tipo == "CONTA_BANCARIA":
        return bool(_SIMBOLO_CARGO.search(texto, max(0, d.inicio - 30), d.inicio))
    if d.tipo != "TELEFONE":
        return False
    if any(v.inicio <= d.inicio and d.fim <= v.fim for v in veiculos):
        return True
    # Num pedido, o número que segue "Convênio nº" pode ser referência do próprio requerente.
    return _documento_do_orgao(texto) and bool(_ATO_ANTES.search(texto, max(0, d.inicio - 40), d.inicio))


def reclassificar(texto: str, deteccoes: list[Deteccao]) -> list[Deteccao]:
    """Reclassifica os achados de contato, endereço, CEP, placa, RENAVAM e chassi que o contexto mostra
    serem do órgão ou de empresa e descarta os números públicos lidos como dado pessoal: códigos de
    natureza de despesa e subitens lidos como endereço IP, chave de acesso de nota fiscal e número de ato
    lidos como telefone ou cartão.

    Args:
        texto: Texto completo analisado (normalizado).
        deteccoes: Achados de todos os reconhecedores, em coordenadas de ``texto``; alterados no lugar.

    Returns:
        A própria lista ``deteccoes``.
    """
    _reclassificar_contatos(texto, deteccoes)
    _reclassificar_enderecos(texto, deteccoes)
    _reclassificar_veiculos(texto, deteccoes)
    chaves = _chaves_nfe(texto)
    veiculos = [d for d in deteccoes if d.tipo in ("RENAVAM", "CHASSI", "VEICULO_OFICIAL")]
    deteccoes[:] = [d for d in deteccoes if not (_codigo_orcamentario(texto, d) or _numeracao_de_item(texto, d)
                                                 or _numero_publico(texto, d, chaves, veiculos))]
    return deteccoes
