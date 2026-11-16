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
from functools import lru_cache

from .. import validadores as v
from .base import ANTES_NUM, CONTEXTUAL, DEPOIS_NUM, Deteccao, Padrao, ReconhecedorPadroes

#: Indicação opcional de número: "nº", "n.", "número", "de número".
_NUM = r"(?:(?:de\s+)?n(?:[º°o]|úm(?:ero)?|um(?:ero)?)?\.?\s*)?"
#: O número não pode vir logo após a designação de norma, edital ou contrato: números de atos
#: públicos ("Lei nº 12.527/2011", "Edital 85/2009") devem permanecer visíveis, inclusive com a
#: sigla do órgão emissor entre a designação e o número ("Resolução CONTRAN nº 619/2016",
#: "Portaria GM/MS nº 2.436/2017").
_NAO_NORMA = (r"(?<!\b(?:lei|decreto|portaria|resolu[çc][ãa]o|instru[çc][ãa]o\s+normativa|edital|termo(?:\s+de\s+\w+)*|"
              r"of[íi]cio|memorando|nota\s+fiscal|empenho|contrato|conv[êe]nio|preg[ãa]o|licita[çc][ãa]o)"
              r"(?:\s+(?-i:[A-Z][A-Za-z]*(?:/[A-Z][A-Za-z]*)*)){0,2}\s{1,3}(?:n[º°o.]*\s*)?)")
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

#: Designações de documentos e procedimentos sobre uma pessoa determinada, cujo número permite chegar
#: ao documento e, por ele, à pessoa (convenção de anotação 8): laudos, pareceres médicos e
#: psicossociais, relatórios sociais e técnicos de atendimento, investigações de caso, declarações de
#: óbito, comunicações de acidente de trabalho, procedimentos de conselho tutelar e de Ministério
#: Público, sindicâncias, autos e termos lavrados contra o autuado e fichas individuais. Relatórios e
#: laudos sobre a gestão, obras, imóveis ou o meio ambiente são informação pública e ficam de fora.
_RELATORIO_COLETIVO = (r"auditoria|fiscaliza|gest[ãa]o|inspe[çc][ãa]o|monitoramento|anual|mensal|bimestral|trimestral|"
                       r"quadrimestral|semestral|consolidad|or[çc]ament|financeir|estat[íi]stic|epidemiol[óo]gico|"
                       r"obras?\b|engenharia|ambienta|impacto|contrat|conv[êe]nio|licita|preg[ãa]o|correi[çc][ãa]o|"
                       r"governan|transpar[êe]ncia|viage[mn]")
_REGISTROS_DE_PESSOA = (
    r"laudos?(?![^\n\d]{0,40}?\b(?:im[óo]ve|vistoria|ambienta|estrutura|engenharia|obras?\b|predia|edifica))|"
    r"parecer(?:es)?\s+(?:m[ée]dic|pericia|psicol[óo]gic|psicossocia|biopsicossocia|socia|t[ée]cnico[-\s]pericia|"
    r"d[ae]\s+junta\s+m[ée]dica)\w*(?:[-\s]pericia\w*)?|"
    r"relat[óo]rios?(?![^\n\d]{0,90}?(?:" + _RELATORIO_COLETIVO + r"))|"
    r"investiga[çc][ãa]o|declara[çc][ãa]o\s+de\s+[óo]bito|comunica[çc][ãa]o\s+de\s+acidente\s+d[eo]\s+trabalho|"
    r"(?-i:CAT)|procedimento(?![^\n\d]{0,40}?(?:licitat|contrata|preg[ãa]o|chamamento|credenciamento|"
    r"manifesta[çc][ãa]o\s+de\s+interesse))|sindic[âa]ncia|termo\s+circunstanciado(?:\s+de\s+ocorr[êe]ncia)?|"
    r"auto\s+de\s+(?:pris[ãa]o\s+em\s+flagrante|infra[çc][ãa]o|apreens[ãa]o|exibi[çc][ãa]o\s+e\s+apreens[ãa]o|"
    r"constata[çc][ãa]o|interdi[çc][ãa]o|embargo)|"
    r"termo\s+de\s+(?:embargo|apreens[ãa]o|interdi[çc][ãa]o|dep[óo]sito|recolhimento|reten[çc][ãa]o|constata[çc][ãa]o|"
    r"declara[çc](?:[ãa]o|[õo]es)|depoimento|oitiva|inquiri[çc][ãa]o|indicia[çc][ãa]o|acolhimento|guarda|advert[êe]ncia)|"
    r"ficha\s+(?:de\s+)?(?:inscri[çc][ãa]o|notifica[çc][ãa]o|investiga[çc][ãa]o|atendimento|cadastr\w*)|"
    r"guia\s+de\s+(?:acolhimento|encaminhamento|execu[çc][ãa]o|recolhimento)|mandado"
)
#: Qualificativos entre a designação e o número, na mesma linha: palavras sem dígitos que não nomeiam
#: ato público e siglas entre parênteses ("Comunicação de Acidente de Trabalho (CAT) nº").
_QUALIFICATIVOS = (r"(?:[ \t]+(?:\((?-i:[A-Z]{2,8})\)|(?!(?:" + _ATOS_PUBLICOS + r")\b)[^\W\d_][\w\-]*)){0,8}?\s*")
#: Indicação obrigatória de número após a designação e seus qualificativos: "nº", "n.º", "No.",
#: "número" ou "nr."; na detecção, a forma de compatibilidade Unicode converte "º" em "o" (ver
#: :mod:`themis_lgpd.texto`). Os dois-pontos de um campo de formulário ("Laudo: …") também indicam o
#: número, mas exigem valor com forma de registro, pois também introduzem quantidades.
_MARCA_REGISTRO = r"(?:n[º°o]\b\.?|n\.\s*[º°o]?|n[úu]mero|nr\b\.?)\s*[:.]?"
#: Número do documento: sigla opcional da unidade emissora antes ("ABC-0123/2025", "XY-AB 019/2026")
#: ou depois ("0123/2025-PTC", "0451/2026-ABC/DEF"), ou código alfanumérico em maiúsculas com ao menos
#: três dígitos ("7D3K5M2P").
_VALOR_REGISTRO = (r"(?P<v>(?:(?-i:(?!(?:CPF|CNPJ|RG|CNH|PIS|NIS|CEP|CNS|OAB|CRM|SIAPE)\b)[A-Z][A-Z0-9]{0,7}"
                   r"(?:-[A-Z0-9]{1,6}){0,2})[\s\-]?)?\d[\d./\-]*\d" + _SUFIXO_SIGLA +
                   r"|(?-i:(?=[A-Z0-9]{6,12}(?![\w]))(?=(?:[A-Z]*\d){3})(?=\d*[A-Z])[A-Z0-9]{6,12}))"
                   r"(?![\w])(?![.\-/]\d)(?!,\d)")
#: Número precedido do nome de uma tabela pública de códigos ("Código IBGE: 5300108", "CNAE 8411-6/00"):
#: não é registro de pessoa, mesmo que uma designação de registro apareça antes na mesma linha.
_NAO_CODIGO_PUBLICO = r"(?<!\b(?-i:IBGE|CNAE|CBO|CID|NCM|CATMAT|CATSER|UASG)\s{0,3}[:\-]?\s{0,3})"

#: Título de documento de licitação ou de contratação pública: linha curta, em maiúsculas, iniciada
#: pela espécie do documento e com a designação do procedimento ("AVISO DE LICITAÇÃO", "ATA DA
#: SESSÃO – CONCORRÊNCIA ELETRÔNICA Nº 4/2025", "EXTRATO DO CONTRATO Nº 12/2025", "TERMO DE
#: REFERÊNCIA").
_TITULO_CONTRATACAO = re.compile(
    r"\s*(?=(?:AVISO|EXTRATO|ATA|EDITAL|TERMO|RESULTADO|HOMOLOGA[ÇC][ÃA]O|ADJUDICA[ÇC][ÃA]O|PREG[ÃA]O|CONCORR[ÊE]NCIA|"
    r"TOMADA|DISPENSA|INEXIGIBILIDADE)\b).{0,60}?(?:PREG[ÃA]O|LICITA[ÇC][ÃA]O|TERMO\s+DE\s+REFER[ÊE]NCIA|"
    r"REGISTRO\s+DE\s+PRE[ÇC]OS|CONCORR[ÊE]NCIA|TOMADA\s+DE\s+PRE[ÇC]OS|DISPENSA\s+(?:ELETR[ÔO]NICA|DE\s+LICITA)|"
    r"INEXIGIBILIDADE|EXTRATO\s+D[OE]\s+(?:[A-ZÀ-Ú]+\s+)?(?:CONTRATO|CONV[ÊE]NIO|TERMO\s+ADITIVO|ADITIVO))")
#: Indício de que o documento trata de pessoa natural: CPF, inteiro ou mascarado, ou a expressão
#: "pessoa física".
_PESSOA_NATURAL = re.compile(r"\bCPF\b|\bc\.p\.f\b|pessoa\s+f[íi]sica|(?<![\w*])(?:\d{3}|[*Xx•#]{3})\.(?:\d{3}|"
                             r"[*Xx•#]{3})\.(?:\d{3}|[*Xx•#]{3})-(?:\d{2}|[*Xx•#]{2})", re.IGNORECASE)
#: Designação de processo logo antes do número ("Processo nº", "PROCESSO:", "Proc. SEI").
_DESIGNACAO_PROCESSO = re.compile(r"\b(?:processo|proc\.|NUP|SEI)\b[^\n\d]{0,30}$", re.IGNORECASE)


@lru_cache(maxsize=32)
def _contratacao_publica(texto: str) -> bool:
    """Indica se o texto é documento de licitação ou contratação sem pessoa natural identificada.

    O número do processo de uma licitação ou de um contrato com pessoa jurídica é informação de
    divulgação obrigatória (LAI, art. 8º, § 1º, IV; Lei nº 14.133/2021, art. 94) e não identifica
    ninguém. O documento é reconhecido pelo título em maiúsculas e pela ausência de CPF.
    """
    if _PESSOA_NATURAL.search(texto):
        return False
    for linha in texto.splitlines():
        if len(linha) <= 100 and _TITULO_CONTRATACAO.match(linha) and \
                not any(c.islower() for c in re.sub(r"\bN[oº°]\b", "", linha)):
            return True
    return False


class PadraoProcesso(Padrao):
    """:class:`Padrao` de número de processo que não se aplica a documentos de contratação pública.

    Em avisos de licitação, atas de pregão, termos de referência e extratos de contrato com pessoa
    jurídica (ver :func:`_contratacao_publica`), os números precedidos da designação de processo
    são descartados; os demais achados da regra são mantidos.
    """

    def detectar(self, texto: str) -> list[Deteccao]:
        achados = super().detectar(texto)
        if not achados or not _contratacao_publica(texto):
            return achados
        return [d for d in achados if not _DESIGNACAO_PROCESSO.search(texto, max(0, d.inicio - 40), d.inicio)]


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
    PadraoProcesso("PROCESSO_ADMINISTRATIVO",
                   ANTES_NUM + r"\d{3,5}[.\-]\d{5,9}/\d{4}[-.]?\d{2}" + DEPOIS_NUM, 0.85,
                   validador=v.ano_plausivel, nome="sei:nup"),
    PadraoProcesso("PROCESSO_ADMINISTRATIVO", ANTES_NUM + r"\d{3}\.\d{3}\.\d{3}/\d{4}-\d{2}" + DEPOIS_NUM, 0.8,
                   validador=v.ano_plausivel, nome="sei:pontuado"),
    # Numerações de processo eletrônico de outros entes, reconhecidas pelo formato:
    # NUP de 21 dígitos ("0000123.00012345/2024-11"), SEI de MG ("1500.01.0012345/2024-12"),
    # de PE ("3900000017.000123/2023-45"), da BA ("019.1234.2024.0001234-56") e do RJ
    # ("120001/001234/2024").
    PadraoProcesso("PROCESSO_ADMINISTRATIVO",
                   ANTES_NUM + r"(?:\d{7}\.\d{8}/\d{4}-\d{2}|\d{4}\.\d{2}\.\d{7}/\d{4}-\d{2}|\d{10}\.\d{6}/\d{4}-\d{2}|"
                   r"\d{3}\.\d{4}\.\d{4}\.\d{7}-\d{2}|\d{6}/\d{6}/\d{4})" + DEPOIS_NUM, 0.85, validador=v.ano_plausivel,
                   nome="processo:estadual"),
    # Qualquer número após a designação de processo, sindicância ou inquérito, inclusive dos sistemas
    # de protocolo estaduais (PROA no RS, eProtocolo no PR, SGPe em SC). A sigla da unidade ou da UF
    # colada ao número ("12345/2023-SP", "2023.08.ABC.0442") faz parte da numeração e é incluída.
    PadraoProcesso("PROCESSO_ADMINISTRATIVO",
                   r"(?:\bprocesso(?:\s+(?:administrativo|disciplinar|sei|judicial|eletr[ôo]nico))*|\bautos|"
                   r"\bproc\.(?:\s*adm(?:inistrativo)?\.?)?|\bPAD\b|\bsindic[âa]ncia|\binqu[ée]rito(?:\s+policial)?|\bNUP|"
                   r"\bSEI|(?-i:\bPROA\b)|\be-?protocolo|(?-i:\bSGPe?\b)(?:\s+[A-Z]{2,5})?)" + _SEP + _NUM + _SEP +
                   r"(?P<v>\d[\d./\-]{0,24}\d" + _SUFIXO_SIGLA + r"|\d)(?![\d])(?![.\-/]\d)(?!,\d)", 0.75,
                   camada=CONTEXTUAL, grupo="v", nome="processo:contexto"),
    # Processo identificado pelo sistema de origem em sigla ("Processo SIGLA: ABC-DEF-2025/01234") ou
    # com a sigla do órgão autuador antes do número ("Processo: XYZ 00012345/2025").
    PadraoProcesso("PROCESSO_ADMINISTRATIVO",
                   r"\bprocesso(?:\s+(?-i:(?!SEI\b|SELETIVO\b|LICITAT)[A-Z][A-Z\-]{1,11}[a-z]?))?\s*(?:" +
                   _MARCA_REGISTRO + r"|:)\s*" + _VALOR_REGISTRO, 0.8, camada=CONTEXTUAL, grupo="v",
                   validador=lambda valor: _registro_plausivel(valor, campo=True), nome="processo:sistema"),
    # Documento ou procedimento sobre uma pessoa, com qualificativos entre a designação e o número
    # ("Relatório de Acompanhamento Psicossocial nº 0123/2026-ABC", "Laudo nº 4410/2025-PTC",
    # "Sindicância Administrativa Punitiva nº 977/2026", "Termo de Apreensão nº AB12C3D4") ou, em
    # campo de formulário, com dois-pontos ("Investigação: AB-123/2025").
    Padrao("PROTOCOLO",
           r"(?<![\w])(?:" + _REGISTROS_DE_PESSOA + r")(?![\w])" + _QUALIFICATIVOS + _MARCA_REGISTRO + r"\s*" +
           _VALOR_REGISTRO, 0.8, camada=CONTEXTUAL, grupo="v", validador=lambda valor: _registro_plausivel(valor),
           nome="protocolo:registro-pessoal"),
    Padrao("PROTOCOLO",
           r"(?<![\w])(?:" + _REGISTROS_DE_PESSOA + r")(?![\w])" + _QUALIFICATIVOS + r":\s*" + _VALOR_REGISTRO, 0.8,
           camada=CONTEXTUAL, grupo="v", validador=lambda valor: _registro_plausivel(valor, campo=True),
           nome="protocolo:registro-pessoal-campo"),
    # Registros policiais pela sigla usada em cada UF, com o número logo em seguida ("REDS 2026-…").
    Padrao("PROTOCOLO",
           r"(?-i:(?<![\w])(?:B\.?O\.?(?:U|PM)?|REDS|RAI|TCO|APF)(?![\w]))\s*(?:" + _MARCA_REGISTRO + r"|:)?\s*"
           + _VALOR_REGISTRO, 0.8, camada=CONTEXTUAL, grupo="v", validador=lambda valor: _registro_plausivel(valor),
           nome="protocolo:registro-policial"),
    # Protocolos de ouvidoria e de pedidos de acesso. O prefixo alfabético ("OUV-") só é aceito em
    # maiúsculas, para não incorporar uma palavra da frase ao número.
    Padrao("PROTOCOLO",
           r"(?:\bprotocolo|\bLAI|\bOUV|\be-?SIC|\bouvidoria|\brequerimento|\bchamado|\bticket|\bmanifesta[çc][ãa]o|"
           r"\bdemanda|\bsolicita[çc][ãa]o)[^\d\n;]{0,30}?"
           + _NAO_NORMA + r"(?P<v>(?-i:[A-Z]{2,4}-?)?\d[\dA-Z./\-]{2,24}[\dA-Z])(?![\w])(?!,\d)", 0.8,
           camada=CONTEXTUAL, grupo="v", validador=lambda valor: _id_plausivel(valor), nome="protocolo:contexto"),
    # Ocorrências, boletins, códigos de atendimento, certidões de dívida ativa e registros de imóveis,
    # com até 40 caracteres entre a palavra-chave e o número ("a ocorrência é a 2023-88741"). Boletins
    # que são publicações (epidemiológico, informativo, de serviço, oficial, "Boletim da Polícia Militar")
    # não entram, nem o título de um edital publicado ("EDITAL DE NOTIFICAÇÃO Nº 12/2024"), nem
    # códigos de tabelas públicas: código IBGE do município, CNAE, CBO, CID e o código de
    # enquadramento de uma infração seguido da descrição ("Código: 545-21 – Estacionar…").
    Padrao("PROTOCOLO",
           r"(?<!(?-i:\bEDITA(?:L|IS)\s+DE)\s+)"
           r"(?:\bocorr[êe]ncias?|\bboletim(?!\s+(?:epidemiol[óo]gico|informativo|oficial|interno|t[ée]cnico|"
           r"estat[íi]stico|de\s+servi[çc]o|de\s+pessoal|d[oa]\s+(?-i:[A-Z])))|\bB\.O\.|"
           r"\bc[óo]digo(?!\s+(?:d[oa]\s+)?(?-i:IBGE|CNAE|CBO|CID|NCM|SIAFI)\b|\s+d[oa]\s+munic[íi]pio)(?:\s+num[ée]rico)?"
           r"(?![^\d\n;]{0,12}\d{3,4}-\d{1,2}(?:/\d{2})?\s+[–—-]\s)|\bidentificador|\bexpediente|"
           r"\bregistro\s+(?:de\s+atendimento|policial|da\s+ocorr[êe]ncia)|\batendimento|\bpedido|\bchamado|"
           r"\bmatr[íi]cula|\binscri[çc][ãa]o|\bn[úu]mero\s+que\s+me\s+passaram|\bcertid(?:[ãa]o|[õo]es)|\bCDAs?\b|"
           r"\bd[íi]vida\s+ativa|\bauto\s+de\s+infra[çc][ãa]o|\bnotifica[çc][ãa]o|\bmulta|\bIPTU|\bIPVA|"
           r"\brefer[êe]ncia(?:\s+interna)?|\bguia|\bboleto)"
           # O prefixo de letras ("AB-12345") não pode ser a sigla de outro documento ("pedido - CPF 529…"),
           # que tem reconhecedor próprio e cuja sigla deve continuar visível.
           r"[^\d\n;]{0,40}?" + _NAO_NORMA + _NAO_CODIGO_PUBLICO + r"(?P<v>(?<![\wÀ-ú])(?!(?-i:CPF|CNPJ|RG|CNH|PIS|NIS|CEP|NB|CNS|OAB|CRM|SIAPE)\b)"
           r"(?-i:[A-Z]{1,4})(?:[-\s])?\d[\dA-Z./\-]{2,22}[\dA-Z]|\d[\dA-Z./\-]{2,22}[\dA-Z])(?![\w])(?!,\d)",
           0.8,
           camada=CONTEXTUAL,
           grupo="v", validador=lambda valor: _id_plausivel(valor), nome="protocolo:ocorrencia"),
    # Número ligado à designação por um verbo ou expressão de identificação, mesmo distante dela na
    # frase: "o processo que abri na regional é o 12345/2024", "o protocolo de atendimento foi
    # 2024.0315-12", "registrado no sistema sob o número 2024.03.0012", "Número do processo: …".
    PadraoProcesso("PROTOCOLO", _NAO_ATO + r"\b(?:" + _REFERENCIAS + r")\b" + _LIGACAO_REF + _VALOR_REF, 0.8,
                   camada=CONTEXTUAL, grupo="v", validador=lambda valor: _referencia_plausivel(valor),
                   nome="protocolo:referencia"),
    # O mesmo com "número" ou "caso", que também designam quantidades ("o número de vagas é 12345"):
    # o valor precisa ter forma de registro — separador, letra ou ao menos oito dígitos.
    PadraoProcesso("PROTOCOLO", _NAO_ATO + r"\b(?:n[úu]mero|caso)\b" + _LIGACAO_REF + _VALOR_REF, 0.75,
                   camada=CONTEXTUAL, grupo="v",
                   validador=lambda valor: _referencia_plausivel(valor, exigir_forma=True), nome="protocolo:numero"),
]


def _id_plausivel(valor: str) -> bool:
    """Indica se ``valor`` tem a forma de um número de registro.

    Exige pelo menos cinco dígitos, ou quatro com separador, e rejeita anos isolados, datas (inclusive
    só o dia e o mês, "02/06") e valores iniciados por letra minúscula (palavra da frase, não prefixo
    de protocolo).
    """
    n = sum(c.isdigit() for c in valor)
    if re.fullmatch(r"(?:19|20)\d{2}", valor) or valor[:1].islower():
        return False
    if re.fullmatch(r"\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?", valor) or re.fullmatch(_CNPJ_FORMATADO, valor):
        return False
    return n >= 5 or (n >= 4 and bool(re.search(r"[./\-]", valor)))


def _registro_plausivel(valor: str, campo: bool = False) -> bool:
    """Indica se ``valor``, após a designação de um documento sobre pessoa, é o número do documento.

    Exige pelo menos três dígitos (quatro, se o valor for só de dígitos) e rejeita anos isolados,
    datas, dia e mês e CNPJ.

    Args:
        valor: Valor candidato.
        campo: O valor vem após dois-pontos, que também introduzem quantidades ("Relatório: 1.500
            atendimentos"): rejeita ainda períodos e números com separador de milhar (ver
            :data:`_NAO_REFERENCIA`) e números só de dígitos com menos de oito.
    """
    digitos = sum(c.isdigit() for c in valor)
    if digitos < 3 or (valor.isdigit() and digitos < 4):
        return False
    if re.fullmatch(r"(?:19|20)\d{2}|\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?", valor) or re.fullmatch(_CNPJ_FORMATADO, valor):
        return False
    return not (campo and (_NAO_REFERENCIA.fullmatch(valor) or (valor.isdigit() and digitos < 8)))


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
