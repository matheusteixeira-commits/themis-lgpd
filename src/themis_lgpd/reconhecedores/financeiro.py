"""Reconhecedores de dados financeiros, veículos e números de processo e protocolo.

Números de processo e de protocolo não identificam a pessoa diretamente, mas permitem consultar
autos e atendimentos que contêm os dados do interessado; por isso são tratados como identificadores
indiretos. Números de normas, editais, contratos e empenhos, ao contrário, são informação pública e
não são reconhecidos (ver :data:`_NAO_NORMA`).

As expressões são compiladas pela biblioteca ``regex`` (ver :class:`~themis_lgpd.reconhecedores.base.Padrao`),
que admite *lookbehind* de comprimento variável.
"""

from __future__ import annotations

import re

from .. import validadores as v
from .base import ANTES_NUM, CONTEXTUAL, DEPOIS_NUM, Padrao, ReconhecedorPadroes

#: Indicação opcional de número: "nº", "n.", "número", "de número".
_NUM = r"(?:(?:de\s+)?n(?:[º°o]|úm(?:ero)?|um(?:ero)?)?\.?\s*)?"
#: O número não pode vir logo após a designação de norma, edital ou contrato: números de atos
#: públicos ("Lei nº 12.527/2011", "Edital 85/2009") devem permanecer visíveis.
_NAO_NORMA = (r"(?<!\b(?:lei|decreto|portaria|resolu[çc][ãa]o|instru[çc][ãa]o\s+normativa|edital|termo(?:\s+de\s+\w+)*|"
              r"of[íi]cio|memorando|nota\s+fiscal|empenho|contrato|conv[êe]nio|preg[ãa]o|licita[çc][ãa]o)"
              r"\s{1,3}(?:n[º°o.]*\s*)?)")
#: Separador opcional entre a palavra-chave e o valor: "agência: 1234", "a conta é 5678", "o processo
#: é o 123", "registrado sob o nº 123".
_SEP = r"\s*(?:[:\-–]|\b(?:é|e|era|sendo)\b(?:\s+(?:o|a)\b)?|\bsob\s+o\b)?\s*"

#: Regras de dados bancários, cartões e chaves PIX.
FINANCEIRO: list[Padrao] = [
    Padrao("CONTA_BANCARIA",
           r"(?:\bag[êe]ncia|\bag\.)" + _SEP + _NUM + r"(?P<v>\d{3,5}(?:\s?-\s?[\dXx])?)(?!\d)", 0.85,
           camada=CONTEXTUAL, grupo="v", nome="banco:agencia"),
    Padrao("CONTA_BANCARIA",
           r"(?:\bconta(?:[\s-]+(?:corrente|poupan[çc]a|sal[áa]rio|de pagamento|banc[áa]ria))?|\bc/c|\bc\.c\.|\bcc\b)"
           + _SEP + _NUM + r"(?P<v>(?:\d{1,3}(?:\.\d{3})+|\d{1,13})(?:\s?[-.]\s?[\dXx])?)(?!\d)", 0.85,
           camada=CONTEXTUAL, grupo="v", nome="banco:conta"),
    # Número com dígito após hífen ("12345-6", "0012345-6") em contexto bancário próximo, mas não imediato.
    Padrao("CONTA_BANCARIA", ANTES_NUM + r"\d{4,12}-[\dXx]" + DEPOIS_NUM, 0.7,
           contexto=("conta", "ag[êe]ncia", "banco", r"banc[áa]ri[oa]s?", "dep[óo]sito", r"deposit(?:ad[oa]s?|ar|em)",
                     "transfer[êe]ncia", "pix", "ted", "doc", "creditad[oa]", "ressarcimento", "reembolso"),
           contexto_obrigatorio=True, janela=60, nome="banco:conta-contexto"),
    # Cartão de pagamento: 13 a 19 dígitos com verificação de Luhn.
    Padrao("CARTAO", ANTES_NUM + r"\d{4}[\s.\-]?\d{4}[\s.\-]?\d{4}[\s.\-]?\d{1,7}" + DEPOIS_NUM, 0.85,
           validador=v.luhn_valido, contexto=("cart[ãa]o", "cr[ée]dito", "d[ée]bito", "visa", "master(?:card)?",
                                              "elo", "amex", "hipercard"), score_invalido=0.8, nome="cartao"),
    # Chave PIX aleatória (UUID): exige a menção a PIX, pois UUIDs são comuns em sistemas.
    Padrao("CHAVE_PIX",
           r"(?P<v>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", 0.9, grupo="v",
           contexto=("pix", "chave"), contexto_obrigatorio=True, janela=60, nome="pix:aleatoria"),
    # Chave PIX numérica (CPF, CNPJ ou telefone sem pontuação) logo após "PIX".
    Padrao("CHAVE_PIX", r"\bpix\b(?:\s+(?:[ée]|:|para|na chave|chave))*\s*[:\-]?\s*(?P<v>\d{11,14})(?!\d)", 0.85,
           camada=CONTEXTUAL, grupo="v", nome="pix:numerica"),
]

#: Regras de identificação de veículos.
VEICULOS: list[Padrao] = [
    # Placa Mercosul (AAA0A00): formato distintivo, reconhecido sem contexto, em maiúsculas.
    Padrao("PLACA", r"(?<![\w-])[A-Z]{3}-?\d[A-Z]\d{2}(?![\w])", 0.85, ignorar_caixa=False, nome="placa:mercosul"),
    # Placa antiga (AAA-0000): o formato coincide com siglas seguidas de número ("ISO-9001",
    # "LEI-1234"), excluídas explicitamente.
    Padrao("PLACA",
           r"(?<![\w-])(?!(?:ISO|NBR|IEC|ABNT|LAI|OUV|SEI|SIC|LEI|ART|CEP|CPF|CID|PEC|ADI|RES|DEC|INC|PAR|COD|REF|"
           r"TEL|CEL|FAX|NUM|ANO|DOC|ATA|OAB|CRM|SUS|CNH|CNS|PIS|INSS|MEC|STF|STJ|TST|TSE|TCU|TCDF|CLDF|GDF|SES|SEE|"
           r"BRB|NOV|DEZ|JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT)-)[A-Z]{3}-\d{4}(?![\w])",
           0.8, ignorar_caixa=False, contexto=("placa", "ve[íi]culo", "carro", "moto(?:cicleta)?", "autom[óo]vel",
                                               "caminh[ãa]o", "[ôo]nibus", "renavam"), nome="placa:antiga"),
    # Qualquer dos dois formatos, em minúsculas ou sem hífen, quando há menção a veículo.
    Padrao("PLACA", r"(?<![\w-])[A-Za-z]{3}[-\s]?\d[A-Za-z0-9]\d{2}(?![\w])", 0.85,
           contexto=("placa", "ve[íi]culo", "carro", "moto(?:cicleta)?", "autom[óo]vel", "caminh[ãa]o"),
           contexto_obrigatorio=True, nome="placa:contexto"),
    # RENAVAM: também com a grafia "renavan" e com pontuação ("2914.1777638"); o dígito verificador
    # eleva a confiança, mas um número com dígito inválido ao lado da palavra-chave é tarjado assim mesmo.
    Padrao("RENAVAM", r"\brenava[mn]\s*[:\-]?\s*" + _NUM + r"(?P<v>\d[\d.\-\s]{7,13}\d)(?![\d])", 0.9,
           camada=CONTEXTUAL, grupo="v", validador=v.renavam_valido, score_invalido=0.85,
           contexto=("renavam", "renavan"), nome="renavam"),
    # Chassi (VIN, ISO 3779): 17 caracteres sem I, O e Q. Com a palavra-chave, qualquer fabricante;
    # sem ela, apenas identificadores de fabricantes no Brasil (prefixo 9), com letras e dígitos.
    Padrao("CHASSI", r"\b(?:chassis?|VIN)\s*[:\-]?\s*" + _NUM + r"(?P<v>[A-HJ-NPR-Z0-9]{17})(?![\w])", 0.95,
           camada=CONTEXTUAL, grupo="v", nome="chassi:contexto"),
    Padrao("CHASSI", r"(?<![\w-])9[A-HJ-NPR-Z0-9]{16}(?![\w])", 0.85, ignorar_caixa=False,
           validador=lambda valor: _vin_plausivel(valor), nome="chassi:brasil"),
    # Recibo de inscrição no Cadastro Ambiental Rural: UF, código IBGE do município e 32 caracteres
    # hexadecimais em grupos de quatro ("MT-5107925-ABCD.1234.…").
    Padrao("CAR", r"(?<![\w-])[A-Z]{2}-\d{7}-[0-9A-F]{4}(?:\.[0-9A-F]{4}){7}(?!\w|\.[0-9A-F])", 0.95,
           nome="car:recibo"),
]


def _vin_plausivel(valor: str) -> bool:
    """Chassi com mistura de letras e dígitos (descarta sequências só de dígitos ou só de letras)."""
    return sum(c.isdigit() for c in valor) >= 4 and sum(c.isalpha() for c in valor) >= 3

#: Sigla de unidade, órgão ou UF colada ao fim da numeração ("12345/2023-SP", "0042/2023-SEC",
#: "2023.08.ABC.0442"), em maiúsculas e seguida opcionalmente de mais dígitos.
_SUFIXO_SIGLA = r"(?:[./\-](?-i:[A-Z]{1,8}(?![A-Za-z]))(?:[./\-]?\d+)?)*"
#: Designações de atos e documentos públicos — normas, editais, licitações, contratos, acórdãos,
#: ofícios — e o CNPJ: números que os acompanham não são referência a processo de uma pessoa.
_ATOS_PUBLICOS = (r"leis?|decretos?|portarias?|resolu[çc](?:[ãa]o|[õo]es)|instru[çc](?:[ãa]o|[õo]es)|edita(?:l|is)|"
                  r"contratos?|conv[êe]nios?|acordos?\s+de|empenhos?|notas?\s+fisca(?:l|is)|notas?\s+t[ée]cnicas?|"
                  r"preg(?:[ãa]o|[õo]es)|licita[çc](?:[ãa]o|[õo]es)|licitat[óo]ri[oa]s?|seletiv[oa]s?|concursos?|"
                  r"chamamentos?|credenciamentos?|ac[óo]rd(?:[ãa]o|[ãa]os)|pareceres|parecer|emendas?|s[úu]mulas?|"
                  r"delibera[çc](?:[ãa]o|[õo]es)|medidas?\s+provis[óo]rias?|of[íi]cios?|memorandos?|despachos?|atas?|"
                  r"pre[çc]os|parcerias?|fomento|colabora[çc][ãa]o|coopera[çc][ãa]o|termos?\s+de\s+refer[êe]ncia|"
                  r"cnpj")
#: A designação não pode estar logo após o nome de um ato público ("Lei número 12.527/2011").
_NAO_ATO = r"(?<!\b(?:" + _ATOS_PUBLICOS + r")\s{1,3})"
#: Designações de processo, pedido ou atendimento da própria pessoa, no singular ("os pedidos foram
#: 12345" é contagem). "Boletim" fica de fora: o boletim de ocorrência é coberto por "ocorrência", e
#: boletins epidemiológicos, de serviço e oficiais são publicações.
_REFERENCIAS = (r"processo|protocolo|registro|pedido|chamado|requerimento|solicita[çc][ãa]o|ocorr[êe]ncia|"
                r"manifesta[çc][ãa]o|reclama[çc][ãa]o|den[úu]ncia|atendimento|alvar[áa]|rastreio|rastreamento|ticket|"
                r"auto\s+de\s+infra[çc][ãa]o")
#: Indicação de número: "nº", "n.", "número", "de número".
_MARCA_NUM = r"(?:(?:de\s+)?(?:n[úu]mero|n[º°o]\.?|n\.))"
#: Trecho entre a designação e o número, na mesma frase, sem dígitos e sem nome de ato público.
_INTERVALO = r"(?:(?!\b(?:" + _ATOS_PUBLICOS + r")\b)[^\d\n.;!?:]){0,70}?"
#: Ligação entre a designação e o número. Após o trecho intermediário, é preciso um verbo de
#: identificação ("é o", "foi", "consta como"), uma preposição seguida de indicação de número ("sob o
#: nº", "com o número"), a própria indicação ou dois-pontos. Sem trecho intermediário, a designação
#: pode vir seguida de complemento curto ("processo de pagamento 123/2024") ou do número.
_LIGACAO_REF = (r"(?:" + _INTERVALO + r"\s*(?:\b(?:[ée]|eh|foi|era|seria|ser[áa]|sendo|consta(?:va)?)\b"
                r"(?:\s+(?:o|a|como))?\s*" + _MARCA_NUM + r"?|\b(?:sob|com|tem|possui|recebeu|gerou)\b(?:\s+(?:o|a))?\s*"
                + _MARCA_NUM + r"|" + _MARCA_NUM + r"|:)|\s+(?:de|do|da)(?:\s+(?!(?:" + _ATOS_PUBLICOS +
                r")\b)[^\W\d_]+){1,3})?\s*[:\-–]?\s*")
#: Número de registro: dígitos, separadores e siglas em maiúsculas, com prefixo opcional ("BR123…",
#: "AB-123") e dígito verificador "X". Não pode continuar em vírgula decimal (valor monetário).
_VALOR_REF = (r"(?P<v>(?-i:[A-Z]{1,4}-?)?\d(?:[\d./\-]|(?-i:[A-Z]))*(?-i:[\dA-Z])(?:-x)?)"
              r"(?![\w])(?![.\-/]\d)(?!,\d)")
#: CNPJ com a pontuação oficial: tem reconhecedor próprio e, em regra, é informação pública.
_CNPJ_FORMATADO = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
#: Formas numéricas que não são número de registro: datas, períodos ("2023/2024"), quantidades com
#: separador de milhar, CNPJ e documentos de execução da despesa no SIAFI (nota de empenho, ordem
#: bancária, nota de lançamento: "2023NE000123"), que são informação pública de gasto.
_NAO_REFERENCIA = re.compile(
    r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|(?:19|20)\d{2}[/.\-]\d{1,2}[/.\-]\d{1,2}|(?:19|20)\d{2}[/\-](?:19|20)?\d{2}|"
    r"\d{1,3}(?:\.\d{3})+|(?:19|20)\d{2}(?:NE|OB|NL|NS|PF|RP|GR|DF|DR)\d{3,}|" + _CNPJ_FORMATADO)

#: Regras de números de processo judicial, processo administrativo e protocolo.
PROCESSOS: list[Padrao] = [
    # Processo judicial: numeração única da Resolução CNJ nº 65/2008 (NNNNNNN-DD.AAAA.J.TR.OOOO).
    Padrao("PROCESSO_JUDICIAL", ANTES_NUM + r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}" + DEPOIS_NUM, 0.85,
           nome="cnj:formatado"),
    Padrao("PROCESSO_JUDICIAL", ANTES_NUM + r"\d{7}[-.]?\d{2}[.]?\d{4}[.]?\d[.]?\d{2}[.]?\d{4}" + DEPOIS_NUM, 0.9,
           validador=v.processo_cnj_valido, contexto=("processo", "autos", "a[çc][ãa]o", "proc\\."),
           score_invalido=0.8, nome="cnj:validado"),
    # Processo administrativo SEI/NUP ("00410.002123/2024-11", "00060-00123456/2023-10"); o ano de
    # autuação precisa ser plausível.
    Padrao("PROCESSO_ADMINISTRATIVO",
           ANTES_NUM + r"\d{3,5}[.\-]\d{5,9}/\d{4}[-.]?\d{2}" + DEPOIS_NUM, 0.85,
           validador=v.ano_plausivel, nome="sei:nup"),
    Padrao("PROCESSO_ADMINISTRATIVO", ANTES_NUM + r"\d{3}\.\d{3}\.\d{3}/\d{4}-\d{2}" + DEPOIS_NUM, 0.8,
           validador=v.ano_plausivel, nome="sei:pontuado"),
    # Numerações de processo eletrônico de outros entes, reconhecidas pelo formato:
    # NUP de 21 dígitos ("0000123.00012345/2024-11"), SEI de MG ("1500.01.0012345/2024-12"),
    # de PE ("3900000017.000123/2023-45"), da BA ("019.1234.2024.0001234-56") e do RJ
    # ("120001/001234/2024").
    Padrao("PROCESSO_ADMINISTRATIVO",
           ANTES_NUM + r"(?:\d{7}\.\d{8}/\d{4}-\d{2}|\d{4}\.\d{2}\.\d{7}/\d{4}-\d{2}|\d{10}\.\d{6}/\d{4}-\d{2}|"
           r"\d{3}\.\d{4}\.\d{4}\.\d{7}-\d{2}|\d{6}/\d{6}/\d{4})" + DEPOIS_NUM, 0.85, validador=v.ano_plausivel,
           nome="processo:estadual"),
    # Qualquer número após a designação de processo, sindicância ou inquérito, inclusive dos sistemas
    # de protocolo estaduais (PROA no RS, eProtocolo no PR, SGPe em SC). A sigla da unidade ou da UF
    # colada ao número ("12345/2023-SP", "2023.08.ABC.0442") faz parte da numeração e é incluída.
    Padrao("PROCESSO_ADMINISTRATIVO",
           r"(?:\bprocesso(?:\s+(?:administrativo|disciplinar|sei|judicial|eletr[ôo]nico))*|\bautos|"
           r"\bproc\.(?:\s*adm(?:inistrativo)?\.?)?|\bPAD\b|\bsindic[âa]ncia|\binqu[ée]rito(?:\s+policial)?|\bNUP|"
           r"\bSEI|(?-i:\bPROA\b)|\be-?protocolo|(?-i:\bSGPe?\b)(?:\s+[A-Z]{2,5})?)" + _SEP + _NUM + _SEP +
           r"(?P<v>\d[\d./\-]{0,24}\d" + _SUFIXO_SIGLA + r"|\d)(?![\d])(?![.\-/]\d)(?!,\d)", 0.75,
           camada=CONTEXTUAL, grupo="v", nome="processo:contexto"),
    # Protocolos de ouvidoria e de pedidos de acesso. O prefixo alfabético ("OUV-") só é aceito em
    # maiúsculas, para não incorporar uma palavra da frase ao número.
    Padrao("PROTOCOLO",
           r"(?:\bprotocolo|\bLAI|\bOUV|\be-?SIC|\bouvidoria|\brequerimento|\bchamado|\bticket|\bmanifesta[çc][ãa]o|"
           r"\bdemanda|\bsolicita[çc][ãa]o)[^\d\n;]{0,30}?"
           + _NAO_NORMA + r"(?P<v>(?-i:[A-Z]{2,4}-?)?\d[\dA-Z./\-]{2,24}[\dA-Z])(?![\w])(?!,\d)", 0.8,
           camada=CONTEXTUAL, grupo="v", validador=lambda valor: _id_plausivel(valor), nome="protocolo:contexto"),
    # Ocorrências, boletins, códigos de atendimento, certidões de dívida ativa e registros de imóveis,
    # com até 40 caracteres entre a palavra-chave e o número ("a ocorrência é a 2023-88741"). Boletins
    # que são publicações (epidemiológico, informativo, de serviço, oficial) não entram.
    Padrao("PROTOCOLO",
           r"(?:\bocorr[êe]ncias?|\bboletim(?!\s+(?:epidemiol[óo]gico|informativo|oficial|interno|t[ée]cnico|"
           r"estat[íi]stico|de\s+servi[çc]o|de\s+pessoal))|\bB\.O\.|\bc[óo]digo(?:\s+num[ée]rico)?|\bidentificador|\bexpediente|"
           r"\bregistro\s+(?:de\s+atendimento|policial|da\s+ocorr[êe]ncia)|\batendimento|\bpedido|\bchamado|"
           r"\bmatr[íi]cula|\binscri[çc][ãa]o|\bn[úu]mero\s+que\s+me\s+passaram|\bcertid(?:[ãa]o|[õo]es)|\bCDAs?\b|"
           r"\bd[íi]vida\s+ativa|\bauto\s+de\s+infra[çc][ãa]o|\bnotifica[çc][ãa]o|\bmulta|\bIPTU|\bIPVA|"
           r"\brefer[êe]ncia(?:\s+interna)?|\bguia|\bboleto)"
           # O prefixo de letras ("AB-12345") não pode ser a sigla de outro documento ("pedido - CPF 529…"),
           # que tem reconhecedor próprio e cuja sigla deve continuar visível.
           r"[^\d\n;]{0,40}?" + _NAO_NORMA + r"(?P<v>(?<![\wÀ-ú])(?!(?-i:CPF|CNPJ|RG|CNH|PIS|NIS|CEP|NB|CNS|OAB|CRM|SIAPE)\b)"
           r"(?-i:[A-Z]{1,4})(?:[-\s])?\d[\dA-Z./\-]{2,22}[\dA-Z]|\d[\dA-Z./\-]{2,22}[\dA-Z])(?![\w])(?!,\d)",
           0.8,
           camada=CONTEXTUAL,
           grupo="v", validador=lambda valor: _id_plausivel(valor), nome="protocolo:ocorrencia"),
    # Número ligado à designação por um verbo ou expressão de identificação, mesmo distante dela na
    # frase: "o processo que abri na regional é o 12345/2024", "o protocolo de atendimento foi
    # 2024.0315-12", "registrado no sistema sob o número 2024.03.0012", "Número do processo: …".
    Padrao("PROTOCOLO", _NAO_ATO + r"\b(?:" + _REFERENCIAS + r")\b" + _LIGACAO_REF + _VALOR_REF, 0.8,
           camada=CONTEXTUAL, grupo="v", validador=lambda valor: _referencia_plausivel(valor),
           nome="protocolo:referencia"),
    # O mesmo com "número" ou "caso", que também designam quantidades ("o número de vagas é 12345"):
    # o valor precisa ter forma de registro — separador, letra ou ao menos oito dígitos.
    Padrao("PROTOCOLO", _NAO_ATO + r"\b(?:n[úu]mero|caso)\b" + _LIGACAO_REF + _VALOR_REF, 0.75,
           camada=CONTEXTUAL, grupo="v", validador=lambda valor: _referencia_plausivel(valor, exigir_forma=True),
           nome="protocolo:numero"),
]


def _id_plausivel(valor: str) -> bool:
    """Indica se ``valor`` tem a forma de um número de registro.

    Exige pelo menos cinco dígitos, ou quatro com separador, e rejeita anos isolados, datas e
    valores iniciados por letra minúscula (palavra da frase, não prefixo de protocolo).
    """
    n = sum(c.isdigit() for c in valor)
    if re.fullmatch(r"(?:19|20)\d{2}", valor) or valor[:1].islower():
        return False
    if re.fullmatch(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}", valor) or re.fullmatch(_CNPJ_FORMATADO, valor):
        return False
    return n >= 5 or (n >= 4 and bool(re.search(r"[./\-]", valor)))


def _referencia_plausivel(valor: str, exigir_forma: bool = False) -> bool:
    """Indica se ``valor``, ligado a uma designação de processo ou pedido, é um número de registro.

    Exige pelo menos cinco dígitos e no máximo 30 caracteres, e rejeita datas, períodos, quantidades
    com separador de milhar e CNPJ (ver :data:`_NAO_REFERENCIA`).

    Args:
        valor: Valor candidato.
        exigir_forma: Rejeita também números sem separador nem letra com menos de oito dígitos, para
            designações que também indicam quantidade ("número", "caso").
    """
    digitos = sum(c.isdigit() for c in valor)
    if len(valor) > 30 or digitos < 5 or _NAO_REFERENCIA.fullmatch(valor):
        return False
    return not (exigir_forma and valor.isdigit() and digitos < 8)


def reconhecedores():
    """Reconhecedores deste módulo, na forma esperada por :mod:`themis_lgpd.analisador`."""
    return [
        ReconhecedorPadroes("financeiro", FINANCEIRO),
        ReconhecedorPadroes("veiculos", VEICULOS),
        ReconhecedorPadroes("processos", PROCESSOS),
    ]
