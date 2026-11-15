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
           + _SEP + _NUM + r"(?P<v>\d{1,13}(?:\s?[-.]\s?[\dXx])?)(?!\d)", 0.85, camada=CONTEXTUAL, grupo="v",
           nome="banco:conta"),
    # Número com dígito após hífen ("12345-6") em contexto bancário próximo, mas não imediato.
    Padrao("CONTA_BANCARIA", ANTES_NUM + r"\d{4,6}-[\dXx]" + DEPOIS_NUM, 0.7,
           contexto=("conta", "ag[êe]ncia", "banco", "dep[óo]sito", "transfer[êe]ncia", "pix", "ted", "doc",
                     "creditad[oa]", "ressarcimento", "reembolso"), contexto_obrigatorio=True, janela=60,
           nome="banco:conta-contexto"),
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
    Padrao("RENAVAM", r"\brenavam\s*[:\-]?\s*" + _NUM + r"(?P<v>\d{9,11})(?!\d)", 0.9, camada=CONTEXTUAL,
           grupo="v", nome="renavam"),
]

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
    # Qualquer número após a designação de processo, sindicância ou inquérito.
    Padrao("PROCESSO_ADMINISTRATIVO",
           r"(?:\bprocesso(?:\s+(?:administrativo|disciplinar|sei|judicial|eletr[ôo]nico))*|\bautos|\bproc\.|"
           r"\bPAD\b|\bsindic[âa]ncia|\binqu[ée]rito(?:\s+policial)?|\bNUP|\bSEI)" + _SEP + _NUM + _SEP +
           r"(?P<v>\d[\d./\-]{0,24}\d|\d)(?![\d])", 0.75, camada=CONTEXTUAL, grupo="v", nome="processo:contexto"),
    # Protocolos de ouvidoria e de pedidos de acesso. O prefixo alfabético ("OUV-") só é aceito em
    # maiúsculas, para não incorporar uma palavra da frase ao número.
    Padrao("PROTOCOLO",
           r"(?:\bprotocolo|\bLAI|\bOUV|\be-?SIC|\bouvidoria|\brequerimento|\bchamado|\bticket|\bmanifesta[çc][ãa]o|"
           r"\bdemanda|\bsolicita[çc][ãa]o)[^\d\n;]{0,30}?"
           + _NAO_NORMA + r"(?P<v>(?-i:[A-Z]{2,4}-?)?\d[\dA-Z./\-]{2,24}[\dA-Z])(?![\w])", 0.8, camada=CONTEXTUAL, grupo="v",
           validador=lambda valor: _id_plausivel(valor), nome="protocolo:contexto"),
    # Ocorrências, boletins, códigos de atendimento, certidões de dívida ativa e registros de imóveis,
    # com até 40 caracteres entre a palavra-chave e o número ("a ocorrência é a 2023-88741").
    Padrao("PROTOCOLO",
           r"(?:\bocorr[êe]ncias?|\bboletim|\bB\.O\.|\bc[óo]digo(?:\s+num[ée]rico)?|\bidentificador|\bexpediente|"
           r"\bregistro\s+(?:de\s+atendimento|policial|da\s+ocorr[êe]ncia)|\batendimento|\bpedido|\bchamado|"
           r"\bmatr[íi]cula|\binscri[çc][ãa]o|\bn[úu]mero\s+que\s+me\s+passaram|\bcertid(?:[ãa]o|[õo]es)|\bCDAs?\b|"
           r"\bd[íi]vida\s+ativa|\bauto\s+de\s+infra[çc][ãa]o|\bnotifica[çc][ãa]o|\bmulta|\bIPTU|\bIPVA|"
           r"\brefer[êe]ncia(?:\s+interna)?|\bguia|\bboleto)"
           r"[^\d\n;]{0,40}?" + _NAO_NORMA + r"(?P<v>(?-i:[A-Z]{1,4})(?:[-\s])?\d[\dA-Z./\-]{2,22}[\dA-Z]|\d[\dA-Z./\-]{2,22}[\dA-Z])(?![\w])",
           0.8,
           camada=CONTEXTUAL,
           grupo="v", validador=lambda valor: _id_plausivel(valor), nome="protocolo:ocorrencia"),
]


def _id_plausivel(valor: str) -> bool:
    """Indica se ``valor`` tem a forma de um número de registro.

    Exige pelo menos cinco dígitos, ou quatro com separador, e rejeita anos isolados, datas e
    valores iniciados por letra minúscula (palavra da frase, não prefixo de protocolo).
    """
    n = sum(c.isdigit() for c in valor)
    if re.fullmatch(r"(?:19|20)\d{2}", valor) or valor[:1].islower():
        return False
    if re.fullmatch(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}", valor):
        return False
    return n >= 5 or (n >= 4 and bool(re.search(r"[./\-]", valor)))


def reconhecedores():
    """Reconhecedores deste módulo, na forma esperada por :mod:`themis_lgpd.analisador`."""
    return [
        ReconhecedorPadroes("financeiro", FINANCEIRO),
        ReconhecedorPadroes("veiculos", VEICULOS),
        ReconhecedorPadroes("processos", PROCESSOS),
    ]
