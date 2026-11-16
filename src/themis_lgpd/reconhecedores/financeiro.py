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
from .documentos import ColunasIdentificadoras

#: Indicação opcional de número: "nº", "n.", "número", "de número".
_NUM = r"(?:(?:de\s+)?n(?:[º°o]|úm(?:ero)?|um(?:ero)?)?\.?\s*)?"
#: O número não pode vir logo após a designação de norma, edital ou contrato: números de atos
#: públicos ("Lei nº 12.527/2011", "Edital 85/2009") devem permanecer visíveis, inclusive com a
#: sigla do órgão emissor entre a designação e o número ("Resolução CONTRAN nº 619/2016",
#: "Portaria GM/MS nº 2.436/2017").
_NAO_NORMA = (r"(?<!\b(?:lei|decreto|portaria|resolu[çc][ãa]o|instru[çc][ãa]o\s+normativa|edital|termo(?:\s+de\s+\w+)*|"
              r"of[íi]cio|memorando|nota\s+fiscal|nota\s+t[ée]cnica|empenho|contrato|conv[êe]nio|preg[ãa]o|"
              r"licita[çc][ãa]o)"
              r"(?:\s+(?-i:[A-Z][A-Za-z]*(?:/[A-Z][A-Za-z]*)*)){0,2}\s{1,3}(?:n[º°o.]*\s*)?)")
#: Separador opcional entre a palavra-chave e o valor: "agência: 1234", "a conta é 5678", "o processo
#: é o 123", "registrado sob o nº 123".
_SEP = r"\s*(?:[:\-–]|\b(?:é|e|era|sendo)\b(?:\s+(?:o|a)\b)?|\bsob\s+o\b)?\s*"

#: Conta de ente público ou de entidade que recebe recursos públicos, publicada por dever de
#: transparência: conta específica de convênio, parceria ou termo de fomento, conta de fundo, para
#: doações, do órgão ou da entidade parceira.
_CONTA_COLETIVA = re.compile(
    r"\b(?:conta\s+(?:espec[íi]fica|[úu]nica|d[aoe]\s+(?:munic[íi]pio|prefeitura|secretaria|[óo]rg[ãa]o|estado|"
    r"uni[ãa]o|fundo|entidade|parceria|conv[êe]nio))|parcerias?|conv[êe]nios?|termos?\s+de\s+(?:fomento|colabora[çc][ãa]o)|"
    r"fundos?|doa[çc](?:[ãa]o|[õo]es)|donativos?|OSC)\b", re.IGNORECASE)
#: Indício de que a conta é de pessoa natural, que prevalece sobre o de conta coletiva.
_CONTA_PESSOAL = re.compile(
    r"\bCPF\b|\b(?:benefici[áa]ri[oa]|servidor(?:a)?|titular|requerente|interessad[oa]|segurad[oa]|bolsista|candidat[oa]|"
    r"alun[oa]|estudante|pensionista|credor(?:a)?|minhas?|meus?|del[ea]s?|suas?|seus?|pessoa\s+f[íi]sica)\b",
    re.IGNORECASE)


#: Fim de frase ou de parágrafo.
_FIM_DE_FRASE = re.compile(r"\n\s*\n|[.;!?](?=\s+[A-ZÀ-Ú])")


def _conta_coletiva(texto: str, inicio: int) -> bool:
    """Indica se o trecho da frase e da linha que precede a conta bancária em ``inicio`` a atribui a
    pessoa jurídica ou ente público, sem menção a pessoa natural (ver :data:`_CONTA_COLETIVA`)."""
    a = max(0, inicio - 200, texto.rfind("\n", 0, inicio) + 1)
    for m in _FIM_DE_FRASE.finditer(texto, a, inicio):
        a = m.end()
    trecho = texto[a:inicio]
    return bool(_CONTA_COLETIVA.search(trecho)) and not _CONTA_PESSOAL.search(trecho)


class PadraoBancario(Padrao):
    """:class:`Padrao` de agência e conta que descarta as contas de pessoa jurídica e de ente público.

    A conta específica de um convênio, a conta de um fundo para doações e a conta de uma entidade
    parceira são publicadas por dever de transparência e não são dado pessoal (ver
    :func:`_conta_coletiva`).
    """

    def detectar(self, texto: str) -> list[Deteccao]:
        return [d for d in super().detectar(texto) if not _conta_coletiva(texto, d.inicio)]


#: Regras de dados bancários, cartões e chaves PIX.
FINANCEIRO: list[Padrao | ColunasIdentificadoras] = [
    PadraoBancario("CONTA_BANCARIA",
                   r"(?:\bag[êe]ncia|\bag\.)" + _SEP + _NUM + r"(?P<v>\d{3,5}(?:\s?-\s?[\dXx])?)(?!\d)", 0.85,
                   camada=CONTEXTUAL, grupo="v", nome="banco:agencia"),
    # A conta tem ao menos três dígitos, em grupos separados por pontos ("12.345-6", "35.123456.0-7"):
    # "símbolo CC-3" é cargo em comissão, e uma célula com o número da linha sob o cabeçalho "CONTA" não
    # é conta.
    PadraoBancario("CONTA_BANCARIA",
                   r"(?:\bconta(?:[\s-]+(?:corrente|poupan[çc]a|sal[áa]rio|de pagamento|banc[áa]ria))?|\bc/c|\bc\.c\.|\bcc\b)"
                   + _SEP + _NUM + r"(?P<v>\d(?:[\d.]{0,15}\d)?(?:\s?[-.]\s?[\dXx])?)(?!\d)", 0.85,
                   camada=CONTEXTUAL, grupo="v", validador=lambda valor: sum(c.isdigit() for c in valor) >= 3,
                   nome="banco:conta"),
    # Número com dígito após hífen ("52817-4", "0052817-4") em contexto bancário próximo, mas não imediato.
    PadraoBancario("CONTA_BANCARIA", ANTES_NUM + r"\d{4,12}-[\dXx]" + DEPOIS_NUM, 0.7,
                   contexto=("conta", "ag[êe]ncia", "banco", r"banc[áa]ri[oa]s?", "dep[óo]sito",
                             r"deposit(?:ad[oa]s?|ar|em)", "transfer[êe]ncia", "pix", "ted", "doc", "creditad[oa]",
                             "ressarcimento", "reembolso"),
                   contexto_obrigatorio=True, janela=60, nome="banco:conta-contexto"),
    # Cartão de pagamento: 13 a 19 dígitos com verificação de Luhn, que não continuam uma sequência maior
    # de grupos de dígitos (chave de acesso de nota fiscal, código de barras).
    Padrao("CARTAO", ANTES_NUM + r"(?<!\d{4}[\s.\-])\d{4}[\s.\-]?\d{4}[\s.\-]?\d{4}[\s.\-]?\d{1,7}" + DEPOIS_NUM +
           r"(?![\s.\-]\d{4})", 0.85,
           validador=v.luhn_valido, contexto=("cart[ãa]o", "cr[ée]dito", "d[ée]bito", "visa", "master(?:card)?",
                                              "elo", "amex", "hipercard"), score_invalido=0.8, nome="cartao"),
    # Chave PIX aleatória (UUID): exige a menção a PIX, pois UUIDs são comuns em sistemas.
    Padrao("CHAVE_PIX",
           r"(?P<v>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", 0.9, grupo="v",
           contexto=("pix", "chave"), contexto_obrigatorio=True, janela=60, nome="pix:aleatoria"),
    # Chave PIX numérica (CPF, CNPJ ou telefone sem pontuação) logo após "PIX".
    Padrao("CHAVE_PIX", r"\bpix\b(?:\s+(?:[ée]|:|para|na chave|chave))*\s*[:\-]?\s*(?P<v>\d{11,14})(?!\d)", 0.85,
           camada=CONTEXTUAL, grupo="v", nome="pix:numerica"),
    # Agência e conta em colunas de tabelas de pagamento a pessoas (folhas de bolsas, relações de
    # beneficiários), reconhecidas pelo cabeçalho da coluna.
    ColunasIdentificadoras([("CONTA_BANCARIA", r"ag(?:[êe]ncia)?\.?|ag[êe]ncia\s+banc[áa]ria|"
                                               r"conta(?:\s+(?:corrente|banc[áa]ria|poupan[çc]a))?|c/c|c\.c\.")],
                           tipo="CONTA_BANCARIA", nome="tabela:banco"),
]

#: Siglas e abreviaturas que, seguidas de número, têm a forma de placa antiga ("ISO-9001", "LEI-1234",
#: "ano 2019"). Também valem em minúsculas na regra que depende de menção a veículo.
_NAO_PLACA = (r"ISO|NBR|IEC|ABNT|LAI|OUV|SEI|SIC|LEI|ART|CEP|CPF|CID|PEC|ADI|RES|DEC|INC|PAR|COD|REF|"
              r"TEL|CEL|FAX|NUM|ANO|DOC|ATA|OAB|CRM|SUS|CNH|CNS|PIS|INSS|MEC|STF|STJ|TST|TSE|TCU|TCDF|CLDF|GDF|SES|SEE|"
              r"BRB|NOV|DEZ|JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT")
#: A placa não continua a numeração de um ato ("Contrato nº 214/PGE-2024") nem é o número de série de
#: um equipamento ("medidor nº MVF-0137", "lacre nº QRT-5082"): o número de placa não é precedido de "nº".
_ANTES_PLACA = (r"(?<![\w-])(?=[A-Za-z]{3}(?:-[ \t]*\n[ \t]*|[-\s])?\d)(?<!\d/)(?<!\bn[º°o]\.?\s{0,2})"
                r"(?<!\bn[úu]mero\s{1,2})")

#: Placa estrangeira, citada com o país ("placa boliviana 3409-GHN", "placa argentina AB 123 CD"): cada
#: país tem formato próprio, por isso vale qualquer combinação de duas a quatro letras e dígitos por bloco.
_PLACA_ESTRANGEIRA = (r"\bplacas?\s+(?:estrangeira|boliviana|paraguaia|argentina|uruguaia|venezuelana|peruana|chilena|"
                      r"colombiana|guianense|surinamesa|(?:do|da)\s+(?:Bol[íi]via|Paraguai|Argentina|Uruguai|Venezuela|"
                      r"Peru|Chile|Col[ôo]mbia|Guiana|Suriname|exterior))\s*(?:n[º°o]\.?\s*)?[:\-]?\s*"
                      r"(?P<v>(?-i:[A-Z0-9]{2,4}(?:[ \-][A-Z0-9]{2,4}){0,2}))(?![\w\-])")


def _placa_estrangeira_plausivel(valor: str) -> bool:
    """Placa estrangeira: cinco a oito caracteres, com letras e ao menos dois dígitos."""
    chars = [c for c in valor if c.isalnum()]
    return 5 <= len(chars) <= 8 and sum(c.isdigit() for c in chars) >= 2 and any(c.isalpha() for c in chars)


#: Placa ou chassi, que denunciam o registro de um veículo na vizinhança de um número de onze dígitos.
_PLACA_OU_CHASSI = re.compile(r"(?<![\w-])(?:[A-Z]{3}-?\d[A-Z0-9]\d{2}|(?=[A-HJ-NPR-Z0-9]{0,16}[A-Z])[A-HJ-NPR-Z0-9]{17})"
                              r"(?![\w])")


class _PadraoVizinhoDeVeiculo(Padrao):
    """:class:`Padrao` cujo achado só é aceito ao lado de placa ou chassi: na mesma linha (célula de
    tabela da frota ou do leilão) ou na linha vizinha (ficha de vistoria em coluna)."""

    def detectar(self, texto: str) -> list[Deteccao]:
        saida = []
        for d in super().detectar(texto):
            a = texto.rfind("\n", 0, max(0, texto.rfind("\n", 0, d.inicio))) + 1
            fim_linha = texto.find("\n", d.fim)
            b = len(texto) if fim_linha < 0 else texto.find("\n", fim_linha + 1)
            if _PLACA_OU_CHASSI.search(texto, a, len(texto) if b < 0 else b):
                saida.append(d)
        return saida


#: Regras de identificação de veículos.
VEICULOS: list[Padrao] = [
    # Placa Mercosul (AAA0A00): formato distintivo, reconhecido sem contexto, em maiúsculas. O hífen pode
    # encerrar a linha, com o restante da placa na seguinte.
    Padrao("PLACA", r"(?<![\w-])[A-Z]{3}(?:-[ \t]*\n[ \t]*|-)?\d[A-Z]\d{2}(?![\w])", 0.85, ignorar_caixa=False,
           nome="placa:mercosul"),
    # Placa antiga (AAA-0000): o formato coincide com siglas seguidas de número ("ISO-9001",
    # "LEI-1234"), excluídas explicitamente.
    Padrao("PLACA",
           _ANTES_PLACA + r"(?!(?:" + _NAO_PLACA + r")-)[A-Z]{3}-(?:[ \t]*\n[ \t]*)?\d{4}(?![\w])",
           0.8, ignorar_caixa=False, contexto=("placa", "ve[íi]culo", "carro", "moto(?:cicleta)?", "autom[óo]vel",
                                               "caminh[ãa]o", "[ôo]nibus", "renavam"), nome="placa:antiga"),
    Padrao("PLACA", _PLACA_ESTRANGEIRA, 0.85, camada=CONTEXTUAL, grupo="v", validador=_placa_estrangeira_plausivel,
           nome="placa:estrangeira"),
    # RENAVAM sem a palavra-chave, com dígito verificador válido, na coluna da tabela ou na linha vizinha
    # de placa ou chassi.
    _PadraoVizinhoDeVeiculo("RENAVAM", ANTES_NUM + r"\d{11}" + DEPOIS_NUM, 0.85, validador=v.renavam_valido,
                            nome="renavam:vizinho"),
    # Qualquer dos dois formatos, em minúsculas ou sem hífen, quando há menção a veículo.
    Padrao("PLACA", _ANTES_PLACA + r"(?!(?:" + _NAO_PLACA + r")[-\s])[A-Za-z]{3}[-\s]?\d[A-Za-z0-9]\d{2}(?![\w])", 0.85,
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
    r"laudos?(?![^\n\d]{0,40}?\b(?:im[óo]ve|vistoria|ambienta|estrutura|engenharia|obras?\b|predia|edifica|ensaio|"
    r"compress|concreto|pavimenta|asfalt|sondage|[áa]gua\b|potabilidade|efluente))|"
    r"parecer(?:es)?\s+(?:m[ée]dic|pericia|psicol[óo]gic|psicossocia|biopsicossocia|socia|t[ée]cnico[-\s]pericia|"
    r"d[ae]\s+junta\s+m[ée]dica|cl[íi]nic|individual|criminol[óo]gic|psiqui[áa]tric|d[ae]\s+acompanhamento|"
    r"d[ae]\s+acolhimento)\w*(?:[-\s]pericia\w*)?|"
    r"relat[óo]rios?(?![^\n\d]{0,90}?(?:" + _RELATORIO_COLETIVO + r"))|"
    r"investiga[çc][ãa]o|declara[çc][ãa]o\s+de\s+[óo]bito|comunica[çc][ãa]o\s+de\s+acidente\s+d[eo]\s+trabalho|"
    r"(?-i:CAT)|procedimento(?![^\n\d]{0,40}?(?:licitat|contrata|preg[ãa]o|chamamento|credenciamento|"
    r"manifesta[çc][ãa]o\s+de\s+interesse))|sindic[âa]ncia|termo\s+circunstanciado(?:\s+de\s+ocorr[êe]ncia)?|"
    r"auto\s+de\s+(?:pris[ãa]o\s+em\s+flagrante|infra[çc][ãa]o|apreens[ãa]o|exibi[çc][ãa]o\s+e\s+apreens[ãa]o|"
    r"constata[çc][ãa]o|interdi[çc][ãa]o|embargo)|"
    r"termo\s+de\s+(?:embargo|apreens[ãa]o|interdi[çc][ãa]o|dep[óo]sito|recolhimento|reten[çc][ãa]o|constata[çc][ãa]o|"
    r"declara[çc](?:[ãa]o|[õo]es)|depoimento|oitiva|inquiri[çc][ãa]o|indicia[çc][ãa]o|acolhimento|guarda|advert[êe]ncia)|"
    # Fichas são registros de uma pessoa (de inscrição, de matrícula, de acolhimento, de abordagem),
    # salvo a ficha técnica de um produto ou obra e a ficha catalográfica.
    r"ficha(?!\s+(?:t[ée]cnica|catalogr[áa]fica|limpa))|"
    # Instrumentos individuais da proteção à criança e ao adolescente: ficha de comunicação de aluno
    # infrequente (FICAI), plano individual de atendimento (PIA, ECA e Lei nº 12.594/2012) e
    # comunicado da escola a uma família.
    r"(?-i:FICAI|PIA)|plano\s+individual\s+de\s+atendimento|comunicado\s+[àa]\s+fam[íi]lia|"
    r"guia\s+de\s+(?:acolhimento|encaminhamento|execu[çc][ãa]o|recolhimento)|mandado"
)
#: Qualificativos entre a designação e o número, na mesma linha: palavras sem dígitos que não nomeiam
#: ato público, siglas entre parênteses ("Comunicação de Acidente de Trabalho (CAT) nº"), travessões
#: e o ano a que o documento se refere ("FICHA DE MATRÍCULA – ANO LETIVO 2026 – Nº").
_QUALIFICATIVOS = (r"(?:[ \t]+(?:\((?-i:[A-Z]{2,8})\)|[–—\-]|(?:19|20)\d{2}(?![\w/.\-])|"
                   r"(?!(?:" + _ATOS_PUBLICOS + r")\b)[^\W\d_][\w\-]*)){0,8}?\s*")
#: Indicação obrigatória de número após a designação e seus qualificativos: "nº", "n.º", "No.",
#: "número" ou "nr."; na detecção, a forma de compatibilidade Unicode converte "º" em "o" (ver
#: :mod:`themis_lgpd.texto`). Os dois-pontos de um campo de formulário ("Laudo: …") também indicam o
#: número, mas exigem valor com forma de registro, pois também introduzem quantidades.
_MARCA_REGISTRO = r"(?:n[º°o]\b\.?|n\.\s*[º°o]?|n[úu]mero|nr\b\.?)\s*[:.]?"
#: Número do documento: sigla opcional da unidade emissora antes ("ABC-0123/2025", "XY-AB 027/2026")
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
#: SESSÃO – CONCORRÊNCIA ELETRÔNICA Nº 6/2024", "EXTRATO DO CONTRATO Nº 12/2025", "TERMO DE
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


#: Designação de ato de contratação ou de transferência de recursos públicos.
_ATO_CONTRATACAO = (r"(?:contrato|conv[êe]nio|termo\s+(?:de\s+)?(?:fomento|colabora[çc][ãa]o|aditivo|coopera[çc][ãa]o)|"
                    r"proposta|edital|leil[ãa]o|preg[ãa]o|concorr[êe]ncia|tomada\s+de\s+pre[çc]os|"
                    r"ata\s+de\s+registro\s+de\s+pre[çc]os|inexigibilidade|dispensa|chamamento\s+p[úu]blico|"
                    r"credenciamento|licita[çc][ãa]o)")
_DESIGNACOES_PROCESSO = (r"(?:(?:processo|proc\.)(?:\s+(?:administrativo|adm\.|sei|eletr[ôo]nico|licitat[óo]rio))*|"
                         r"NUP|SEI)")
#: Número de ato de contratação logo antes do processo, separado só por travessão ou quebra de linha:
#: "Contrato nº 12/2025 – Processo SEI nº …", "TERMO DE COLABORAÇÃO Nº 3/2025⏎Processo nº …".
_ATO_ANTES_DO_PROCESSO = re.compile(
    r"\b" + _ATO_CONTRATACAO + r"\b[^\n\d]{0,40}?(?:n[º°o]\.?|n[úu]mero)\s*[\w./\-]*\d[\w./\-]*\s*"
    r"(?:[–—\-]\s*|\n\s*)" + _DESIGNACOES_PROCESSO + r"\s*[:\-]?\s*(?:n[º°o]\.?|n[úu]mero)?\s*[:\-]?\s*$", re.IGNORECASE)
#: Número precedido diretamente da designação de proposta de transferência de recursos ("Proposta FNS
#: nº …"), e não da designação de processo.
_ATO_ANTES_DO_NUMERO = re.compile(r"\bproposta(?:\s+(?-i:[A-Z]{2,10}))?\s*(?:n[º°o]\.?|n[úu]mero)?\s*[:\-]?\s*$",
                                  re.IGNORECASE)
#: Número de ato de contratação logo depois do processo, após travessão ("Processo nº … – Pregão
#: Eletrônico nº 9/2025").
_ATO_DEPOIS = re.compile(r"\s*[–—\-]\s*" + _ATO_CONTRATACAO + r"\b[^\n\d]{0,40}?(?:n[º°o]\.?|n[úu]mero)", re.IGNORECASE)
#: Ação coletiva ou de controle abstrato: o número da ação civil pública, da ação popular e da ação
#: direta não se refere a uma pessoa natural.
_ACAO_COLETIVA = re.compile(r"\b(?:a[çc][ãa]o\s+civil\s+p[úu]blica|(?-i:ACP)|a[çc][ãa]o\s+popular|"
                            r"a[çc][ãa]o\s+direta(?:\s+de\s+inconstitucionalidade)?|(?-i:ADI|ADPF|ADC|ADO)|"
                            r"habeas\s+corpus\s+coletivo|mandado\s+de\s+seguran[çc]a\s+coletivo)\s*(?:n[º°o]\.?)?\s*[:\-]?\s*$",
                            re.IGNORECASE)
#: Registro de pessoa jurídica ("comprovante de registro da pessoa jurídica no conselho nº …").
_REGISTRO_PJ = re.compile(r"\bpessoa\s+jur[íi]dica\b[^\n\d.;]{0,30}$", re.IGNORECASE)


#: Campo que qualifica a parte contratada, outorgada ou beneficiária de um ato ("CONTRATADA: …"), até
#: o fim da linha ou o ponto e vírgula.
_CAMPO_PARTE = re.compile(r"\b(?:contratad[oa]s?|outorgad[oa]s?|benefici[áa]ri[oa]s?|credenciad[oa]s?|favorecid[oa]s?|"
                          r"premiad[oa]s?|bolsistas?|proponentes?)\s*:[^\n;]{0,200}", re.IGNORECASE)
#: Pessoa jurídica no campo da parte: o CPF que o acompanhe é do representante.
_PARTE_JURIDICA = re.compile(r"\bCNPJ\b|\bLtda\b|\bEIRELI\b|\bS\.?/A\b", re.IGNORECASE)


@lru_cache(maxsize=32)
def _parte_pessoa_natural(texto: str) -> bool:
    """Indica se a parte contratada, outorgada ou beneficiária do ato é pessoa natural (CPF, inteiro ou
    mascarado, ou "pessoa física" no campo que a qualifica, sem CNPJ): o processo do ato é então dado
    pessoal."""
    return any(_PESSOA_NATURAL.search(m.group()) and not _PARTE_JURIDICA.search(m.group())
               for m in _CAMPO_PARTE.finditer(texto))


#: Marcas de texto redigido em primeira pessoa, como pedidos de acesso, requerimentos e manifestações.
_PRIMEIRA_PESSOA = re.compile(
    r"\b(?:eu|me|mim|comigo|meus?|minhas?|nós|nossos?|nossas?|sou|somos|estou|estamos|quero|queria|desejo|"
    r"gostaria|gostar[íi]amos|solicito|solicitamos|venho|vimos|vem\s+(?:,\s*respeitosamente,\s*)?requerer|requeiro|"
    r"requeremos|preciso|precisamos|pe[çc]o|pedimos|sirvo-me|reporto-me|apresento|apresentamos|submeto|represento|"
    r"aguardo|agrade[çc]o)\b", re.IGNORECASE)


@lru_cache(maxsize=32)
def _primeira_pessoa(texto: str) -> bool:
    """Indica se o texto é redigido em primeira pessoa (pedido de acesso, requerimento, manifestação).

    Nesses textos, os números de processo, auto ou notificação citados pelo autor se referem, em regra,
    a assuntos dele, ainda que envolvam empresa ou contrato: os descartes por alvo coletivo e por
    contratação vizinha (ver :func:`_processo_de_contratacao` e :func:`_registro_coletivo`) só se
    aplicam a documentos institucionais.
    """
    return bool(_PRIMEIRA_PESSOA.search(texto))


def _processo_de_contratacao(texto: str, inicio: int, fim: int) -> bool:
    """Indica se o processo citado em ``texto[inicio:fim]`` é o de uma contratação, de uma
    transferência de recursos ou de uma ação coletiva, pela designação vizinha (ver
    :data:`_ATO_ANTES_DO_PROCESSO`, :data:`_ATO_ANTES_DO_NUMERO`, :data:`_ATO_DEPOIS` e
    :data:`_ACAO_COLETIVA`). Não se aplica quando a parte contratada ou beneficiária é pessoa natural
    (ver :func:`_parte_pessoa_natural`) nem a textos em primeira pessoa (ver :func:`_primeira_pessoa`)."""
    if _primeira_pessoa(texto):
        return False
    antes = texto[max(0, inicio - 160):inicio]
    if _ACAO_COLETIVA.search(antes[-80:]) or _REGISTRO_PJ.search(antes[-60:]):
        return True
    return bool((_ATO_ANTES_DO_PROCESSO.search(antes) or _ATO_ANTES_DO_NUMERO.search(antes[-60:])
                 or _ATO_DEPOIS.match(texto, fim, fim + 80)) and not _parte_pessoa_natural(texto))


class PadraoProcesso(Padrao):
    """:class:`Padrao` de número de processo que não se aplica a documentos de contratação pública.

    Em avisos de licitação, atas de pregão, termos de referência e extratos de contrato com pessoa
    jurídica (ver :func:`_contratacao_publica`), os números precedidos da designação de processo
    são descartados; os demais achados da regra são mantidos. Em qualquer documento, também é
    descartado o processo citado junto ao número de um contrato, convênio ou procedimento
    licitatório, o de uma ação coletiva (ver :func:`_processo_de_contratacao`) e o auto ou a
    notificação dirigidos a pessoa jurídica (ver :func:`_registro_coletivo`).
    """

    def detectar(self, texto: str) -> list[Deteccao]:
        achados = [d for d in super().detectar(texto)
                   if not _processo_de_contratacao(texto, d.inicio, d.fim) and not _registro_coletivo(texto, d)]
        if not achados or not _contratacao_publica(texto):
            return achados
        return [d for d in achados if not _DESIGNACAO_PROCESSO.search(texto, max(0, d.inicio - 40), d.inicio)]


#: Pessoa jurídica ou objeto coletivo como destinatário ou assunto do documento: a contratada, a
#: empresa, a obra, o ensaio de material ou a análise de água ("Notificação nº 3/2025 à contratada",
#: "Laudo de Ensaio nº 8/2025 do concreto").
_ALVO_COLETIVO = re.compile(
    r"\b(?:contratad[ao]|empresa|construtora|concession[áa]ria|cons[óo]rcio|cooperativa|Ltda|EIRELI|S\.?/A|CNPJ|"
    r"obras?|concreto|MPa|ensaios?|compress[ãa]o|pavimenta\w*|asfalt\w*|sondage[mn]s?|[áa]gua|esgoto|potabilidade|"
    r"efluentes?)\b", re.IGNORECASE)
#: Indício de pessoa natural na mesma frase, que prevalece sobre o de alvo coletivo.
_ALVO_PESSOAL = re.compile(
    r"\bCPF\b|\bSra?\.|\b(?:servidor(?:a)?|propriet[áa]ri[oa]|condutor(?:a)?|motorista|paciente|requerente|"
    r"interessad[oa]|periciad[oa]|v[íi]tima|crian[çc]a|adolescente|alun[oa]|nascid[oa]|pessoa\s+f[íi]sica|senhor(?:a)?|"
    r"cidad[ãa]o|mun[íi]cipe|morador(?:a)?|residente|usu[áa]ri[oa]|titular|benefici[áa]ri[oa]|meus?|minhas?|eu)\b",
    re.IGNORECASE)
#: Designação de documento sobre um destinatário que rege o número, sem outra designação de pedido
#: ou processo entre ela e o número: nesses documentos, o alvo coletivo afasta o dado pessoal.
_DOCUMENTO_DIRIGIDO = re.compile(r"\b(?:notifica[çc][ãa]o|auto\s+de|laudo|multa|termo\s+de|relat[óo]rio|procedimento|"
                                 r"parecer)(?:(?!protocolo|processo|requerimento|pedido|solicita)[^\n\d]){0,45}$",
                                 re.IGNORECASE)
#: Quantidade com separador de milhar seguida de substantivo no plural ("1.032 partos", "2.318 pessoas").
_QUANTIDADE = re.compile(r"\d{1,3}(?:\.\d{3})+")
#: Designação de item, cláusula ou dispositivo logo antes do número ("subitem 8.3.1", "cláusula 12.4").
_ITEM_ANTES = re.compile(r"\b(?:sub)?(?:ite(?:m|ns)|cl[áa]usulas?|incisos?|al[íi]neas?|art(?:igo)?s?\.?|§)\s*"
                         r"(?:n[º°o]\.?\s*)?$", re.IGNORECASE)
#: Código de autenticação do documento eletrônico ("código verificador 1234567", "código CRC 1A2B3C4D").
_AUTENTICACAO = re.compile(r"\bc[óo]digo\s+(?:CRC|verificador|de\s+(?:verifica[çc][ãa]o|autenticidade|autentica[çc][ãa]o))"
                           r"\s*[:=]?\s*$", re.IGNORECASE)
#: Documento publicado em diário oficial: o título do jornal no cabeçalho.
_DIARIO_OFICIAL = re.compile(r"\bDI[ÁA]RIO\s+OFICIAL\b", re.IGNORECASE)


def _frase(texto: str, inicio: int, fim: int) -> tuple[int, int]:
    """Limites da frase de ``texto[inicio:fim]``. Quando o trecho encerra a frase, a seguinte também
    é incluída: costuma nomear o destinatário ("… a Notificação nº 3/2025. A contratada…")."""
    a = max(0, inicio - 200)
    for m in _FIM_DE_FRASE.finditer(texto, a, inicio):
        a = m.end()
    m = _FIM_DE_FRASE.search(texto, fim, fim + 200)
    if m and m.start() - fim <= 1:
        m = _FIM_DE_FRASE.search(texto, m.end(), m.end() + 200)
    return a, (m.start() if m else min(len(texto), fim + 200))


def _registro_coletivo(texto: str, d: Deteccao) -> bool:
    """Indica se o número em ``d`` não é de documento sobre pessoa natural.

    É o caso de notificação, auto, laudo ou relatório dirigido a pessoa jurídica ou sobre obra ou
    análise de água, sem menção a pessoa natural na mesma frase, e do código verificador ou CRC de
    autenticação, em documento institucional (ver :func:`_primeira_pessoa`); de quantidade com
    separador de milhar seguida de substantivo, sem indicação de número ("41.870 atendimentos e 1.032
    partos"); da numeração de item, cláusula ou artigo ("cláusula 12.4.1"); e do protocolo de
    publicação no diário oficial ("Protocolo 1234567" ao fim da matéria).
    """
    antes = texto[max(0, d.inicio - 60):d.inicio]
    if _ITEM_ANTES.search(antes):
        return True
    if _AUTENTICACAO.search(antes) and not _primeira_pessoa(texto):
        return True
    if _DOCUMENTO_DIRIGIDO.search(antes) and not _primeira_pessoa(texto):
        a, b = _frase(texto, d.inicio, d.fim)
        trecho = texto[a:b]
        if _ALVO_COLETIVO.search(trecho) and not _ALVO_PESSOAL.search(trecho):
            return True
    valor = texto[d.inicio:d.fim]
    if (_QUANTIDADE.fullmatch(valor) and re.match(r"\s+[a-zà-ú]{2,}s\b", texto[d.fim:d.fim + 30])
            and not re.search(r"(?:n[º°o]\.?|n[úu]mero|:)\s*$", antes, re.IGNORECASE)):
        return True
    return bool(valor.isdigit() and re.search(r"(?:^|\s)(?-i:Protocolo|PROTOCOLO)\s$", antes)
                and re.match(r"\s*$|\s*\n| {2}", texto[d.fim:d.fim + 2]) and _DIARIO_OFICIAL.search(texto[:400]))


class PadraoRegistro(Padrao):
    """:class:`Padrao` de número de documento ou protocolo que descarta os que não se referem a pessoa
    natural (ver :func:`_registro_coletivo`)."""

    def detectar(self, texto: str) -> list[Deteccao]:
        return [d for d in super().detectar(texto) if not _registro_coletivo(texto, d)]


#: Regras de números de processo judicial, processo administrativo e protocolo.
PROCESSOS: list[Padrao] = [
    # Processo judicial: numeração única da Resolução CNJ nº 65/2008 (NNNNNNN-DD.AAAA.J.TR.OOOO). O
    # número de uma ação coletiva (ação civil pública, ação popular) não se refere a pessoa natural.
    PadraoProcesso("PROCESSO_JUDICIAL", ANTES_NUM + r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}" + DEPOIS_NUM, 0.85,
                   nome="cnj:formatado"),
    PadraoProcesso("PROCESSO_JUDICIAL", ANTES_NUM + r"\d{7}[-.]?\d{2}[.]?\d{4}[.]?\d[.]?\d{2}[.]?\d{4}" + DEPOIS_NUM,
                   0.9, validador=v.processo_cnj_valido, contexto=("processo", "autos", "a[çc][ãa]o", "proc\\."),
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
    # de protocolo estaduais (PROA no RS, eProtocolo no PR, SGPe em SC) e do processo de assistência
    # jurídica da Defensoria Pública (PAJ). A sigla da unidade ou da UF colada ao número
    # ("12345/2023-SP", "2023.08.ABC.0442") faz parte da numeração e é incluída.
    PadraoProcesso("PROCESSO_ADMINISTRATIVO",
                   r"(?:\bprocesso(?:\s+(?:administrativo|disciplinar|sei|judicial|eletr[ôo]nico))*|\bautos|"
                   r"\bproc\.(?:\s*adm(?:inistrativo)?\.?)?|\bPAD\b|\bsindic[âa]ncia|\binqu[ée]rito(?:\s+policial)?|\bNUP|"
                   r"\bSEI|(?-i:\bPROA\b)|(?-i:\bPAJ\b)|\be-?protocolo|(?-i:\bSGPe?\b)(?:\s+[A-Z]{2,5})?)" + _SEP + _NUM +
                   _SEP +
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
    PadraoRegistro("PROTOCOLO",
                   r"(?<![\w])(?:" + _REGISTROS_DE_PESSOA + r")(?![\w])" + _QUALIFICATIVOS + _MARCA_REGISTRO + r"\s*" +
                   _VALOR_REGISTRO, 0.8, camada=CONTEXTUAL, grupo="v",
                   validador=lambda valor: _registro_plausivel(valor), nome="protocolo:registro-pessoal"),
    PadraoRegistro("PROTOCOLO",
                   r"(?<![\w])(?:" + _REGISTROS_DE_PESSOA + r")(?![\w])" + _QUALIFICATIVOS + r":\s*" + _VALOR_REGISTRO,
                   0.8, camada=CONTEXTUAL, grupo="v", validador=lambda valor: _registro_plausivel(valor, campo=True),
                   nome="protocolo:registro-pessoal-campo"),
    # Parecer técnico da comissão de classificação na execução penal, reconhecido pela finalidade que o
    # segue: progressão de regime, livramento condicional, remição, exame criminológico, indulto.
    PadraoRegistro("PROTOCOLO",
                   r"(?<![\w])parecer(?:\s+t[ée]cnico)?\s*" + _MARCA_REGISTRO + r"\s*" + _VALOR_REGISTRO +
                   r"(?=[^\d]{0,120}?\b(?:progress[ãa]o|livramento\s+condicional|remi[çc][ãa]o|criminol[óo]gic|"
                   r"regime\s+(?:semi)?aberto|indulto|comuta[çc][ãa]o))", 0.8, camada=CONTEXTUAL, grupo="v",
                   validador=lambda valor: _registro_plausivel(valor), nome="protocolo:parecer-execucao-penal"),
    # Registros policiais pela sigla usada em cada UF, com o número logo em seguida ("REDS 2026-…").
    Padrao("PROTOCOLO",
           r"(?-i:(?<![\w])(?:B\.?O\.?(?:U|PM)?|REDS|RAI|TCO|APF)(?![\w]))\s*(?:" + _MARCA_REGISTRO + r"|:)?\s*"
           + _VALOR_REGISTRO, 0.8, camada=CONTEXTUAL, grupo="v", validador=lambda valor: _registro_plausivel(valor),
           nome="protocolo:registro-policial"),
    # Protocolos de ouvidoria e de pedidos de acesso, inclusive com a palavra abreviada em formulários
    # ("PROTOC 2026/001234"). O prefixo alfabético ("OUV-") só é aceito em maiúsculas, para não
    # incorporar uma palavra da frase ao número. O protocolo de publicação no diário oficial não é
    # pedido de ninguém (ver :func:`_registro_coletivo`).
    PadraoRegistro("PROTOCOLO",
           r"(?:\bprotocolo|(?-i:\bPROTOC\b)\.?|\bLAI|\bOUV|\be-?SIC|\bouvidoria|\brequerimento|\bchamado|\bticket|\bmanifesta[çc][ãa]o|"
           r"\bdemanda|\bsolicita[çc][ãa]o)[^\d\n;]{0,30}?"
           + _NAO_NORMA + r"(?P<v>(?-i:[A-Z]{2,4}-?)?\d[\dA-Z./\-]{2,24}[\dA-Z])(?![\w])(?!,\d)", 0.8,
           camada=CONTEXTUAL, grupo="v", validador=lambda valor: _id_plausivel(valor), nome="protocolo:contexto"),
    # Ocorrências, boletins, códigos de atendimento, certidões de dívida ativa e registros de imóveis,
    # com até 40 caracteres entre a palavra-chave e o número ("a ocorrência é a 2023-88741"). Boletins
    # que são publicações (epidemiológico, informativo, de serviço, oficial, "Boletim da Polícia Militar")
    # não entram, nem o título de um edital publicado ("EDITAL DE NOTIFICAÇÃO Nº 12/2024"), nem
    # códigos de tabelas públicas: código IBGE do município, CNAE, CBO, CID e o código de
    # enquadramento de uma infração seguido da descrição ("Código: 545-21 – Estacionar…").
    PadraoRegistro("PROTOCOLO",
           r"(?<!(?-i:\bEDITA(?:L|IS)\s+DE)\s+)"
           r"(?:\bocorr[êe]ncias?|\bboletim(?!\s+(?:epidemiol[óo]gico|informativo|oficial|interno|t[ée]cnico|"
           r"estat[íi]stico|de\s+servi[çc]o|de\s+pessoal|d[oa]\s+(?-i:[A-Z])))|\bB\.O\.|"
           r"\bc[óo]digo(?!\s+(?:d[oa]\s+)?(?-i:IBGE|CNAE|CBO|CID|NCM|SIAFI)\b|\s+d[oa]\s+munic[íi]pio)(?:\s+num[ée]rico)?"
           r"(?![^\d\n;]{0,12}\d{3,4}-\d{1,2}(?:/\d{2})?\s+[–—-]\s)|\bidentificador|"
           r"\bexpediente(?=\s*(?:n[º°o]|n[úu]mero|:|\d))|"
           r"\bregistro\s+(?:de\s+atendimento|policial|da\s+ocorr[êe]ncia)|\batendimento|\bpedido|\bchamado|"
           r"\bmatr[íi]cula|\binscri[çc][ãa]o|\bn[úu]mero\s+que\s+me\s+passaram|\bcertid(?:[ãa]o|[õo]es)|\bCDAs?\b|"
           r"\bd[íi]vida\s+ativa|\bauto\s+de\s+infra[çc][ãa]o|\bnotifica[çc][ãa]o|\bmulta|\bIPTU|\bIPVA|"
           r"(?<!termos?\s+de\s+)\brefer[êe]ncia(?:\s+interna)?|\bguia|\bboleto)"
           # O prefixo de letras ("AB-12345") não pode ser a sigla de outro documento ("pedido - CPF 529…"),
           # que tem reconhecedor próprio e cuja sigla deve continuar visível.
           r"[^\d\n;]{0,40}?" + _NAO_NORMA + _NAO_CODIGO_PUBLICO + r"(?P<v>(?<![\wÀ-ú])(?!(?-i:CPF|CNPJ|RG|CNH|PIS|NIS|CEP|NB|CNS|OAB|CRM|SIAPE)\b)"
           r"(?-i:[A-Z]{1,4})(?:[-\s])?\d[\dA-Z./\-]{2,22}[\dA-Z]|\d[\dA-Z./\-]{2,22}[\dA-Z])(?![\w])(?!,\d)",
           0.8,
           camada=CONTEXTUAL,
           grupo="v", validador=lambda valor: _id_plausivel(valor), nome="protocolo:ocorrencia"),
    # Número ligado à designação por um verbo ou expressão de identificação, mesmo distante dela na
    # frase: "o processo que abri na regional é o 12345/2024", "o protocolo de atendimento foi
    # 2024.0315-12", "a solicitação aberta no portal sob o número 2025.07.0031", "Número do processo: …".
    PadraoProcesso("PROTOCOLO", _NAO_ATO + r"(?<!c[óo]digo\s+de\s+)\b(?:" + _REFERENCIAS + r")\b" + _LIGACAO_REF +
                   _VALOR_REF, 0.8,
                   camada=CONTEXTUAL, grupo="v", validador=lambda valor: _referencia_plausivel(valor),
                   nome="protocolo:referencia"),
    # O mesmo com "número" ou "caso", que também designam quantidades ("o número de vagas é 12345"):
    # o valor precisa ter forma de registro — separador, letra ou ao menos oito dígitos.
    PadraoProcesso("PROTOCOLO", _NAO_ATO + r"\b(?:n[úu]mero|caso)\b" + _LIGACAO_REF + _VALOR_REF, 0.75,
                   camada=CONTEXTUAL, grupo="v",
                   validador=lambda valor: _referencia_plausivel(valor, exigir_forma=True), nome="protocolo:numero"),
    # Número e ano separados por espaço, sem a barra, como em formulários datilografados ou lidos por OCR
    # ("PROCESSO ADMINISTRATIVO N 1234 2026", "TERMO CIRCUNSTANCIADO DE OCORRENCIA N 56 2026").
    Padrao("PROTOCOLO",
           r"(?:\bprocesso(?:\s+administrativo)?|\bproc\.?|\bcertid[ãa]o(?:\s+de\s+[^\W\d_]+){0,4}|"
           r"\btermo\s+circunstanciado(?:\s+de\s+ocorr[êe]ncia)?|(?-i:\bTCO\b)|\bboletim\s+de\s+ocorr[êe]ncia|"
           r"\binqu[ée]rito(?:\s+policial)?|\bprotocolo|\brequerimento|\bocorr[êe]ncia)\s+(?:n[º°o]?\.?|n[úu]mero)\s+"
           r"(?P<v>\d{1,7}\s(?:19|20)\d{2})(?![\d/.\-])", 0.8, camada=CONTEXTUAL, grupo="v",
           validador=v.ano_plausivel, nome="protocolo:numero-ano"),
]


def _id_plausivel(valor: str) -> bool:
    """Indica se ``valor`` tem a forma de um número de registro.

    Exige pelo menos cinco dígitos, ou quatro com separador, e rejeita anos isolados, datas (inclusive
    só o dia e o mês, "25/11") e valores iniciados por letra minúscula (palavra da frase, não prefixo
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
