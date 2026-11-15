"""Reconhecedores de documentos de pessoas naturais e jurídicas.

Para os documentos que têm dígito verificador (CPF, CNPJ, PIS, título de eleitor, CNS, CNH), a
validação é o principal critério: número válido é reconhecido mesmo sem contexto. Número com dígito
inválido só é reconhecido quando acompanhado da palavra que o identifica ("CPF", "título de
eleitor"); nesse caso é tarjado mesmo assim — política de *falhar fechado*, que cobre erros de
digitação e de OCR.

Documentos sem dígito verificador (RG, passaporte, CTPS, matrícula, registro profissional) exigem a
palavra-chave, pois o número sozinho não se distingue de outros números.
"""

from __future__ import annotations

from .. import validadores as v
from .base import ANTES_NUM, CONTEXTUAL, DEPOIS_NUM, Padrao

#: Indicação opcional de número entre a palavra-chave e o valor: "nº", "n.", "número", "de número".
_NUM = r"(?:(?:de\s+)?n(?:[º°o]|úm(?:ero)?|um(?:ero)?)?\.?\s*)?"
#: Separador opcional entre a palavra-chave e o valor: "RG: 123", "RG - 123", "meu RG é 123".
_SEP = r"\s*(?:[:\-–]|\b(?:é|e|era|sendo|seria)\b)?\s*"

#: Contexto do CPF; "CIC" é a denominação antiga do documento.
CTX_CPF = ("cpf", r"c\.p\.f\.?", "cadastro de pessoas? f[íi]sicas?", r"inscrit[oa] no", "cic")
#: Contexto do PIS/PASEP/NIS/NIT (mesma numeração).
CTX_PIS = ("pis", "pasep", "nis", "nit", r"pis/pasep", "inscri[çc][ãa]o do trabalhador")
#: Contexto do título de eleitor.
CTX_TITULO = (r"t[íi]tulo(?: de)? eleitor(?:al)?", "inscri[çc][ãa]o eleitoral", "t[íi]tulo eleitoral", r"t[íi]tulo")
#: Contexto do Cartão Nacional de Saúde.
CTX_CNS = ("cns", r"cart[ãa]o (?:do )?sus", r"cart[ãa]o nacional de sa[úu]de", "sus")
#: Contexto da CNH.
CTX_CNH = ("cnh", r"habilita[çc][ãa]o", r"carteira (?:nacional )?de (?:habilita[çc][ãa]o|motorista)",
           r"registro (?:da )?cnh", r"carteira de motorista")
#: Contexto do CNPJ.
CTX_CNPJ = ("cnpj", r"c\.n\.p\.j\.?", "pessoa jur[íi]dica", "empresa", "inscrita no")

#: Regras de documentos de identificação.
PADROES: list[Padrao] = [
    # ---------------- CPF
    Padrao("CPF", ANTES_NUM + r"\d{3}\.\d{3}\.\d{3}-\d{2}" + DEPOIS_NUM, 0.8, nome="cpf:formatado"),
    # Pontuação parcial, espaços e separadores trocados ("529 982 247 25", "529.982.247/25").
    Padrao("CPF", ANTES_NUM + r"\d{3}[.\s]{0,2}\d{3}[.\s]{0,2}\d{3}\s{0,2}[-.\s/]?\s{0,2}\d{2}" + DEPOIS_NUM,
           0.9, validador=v.cpf_valido, contexto=CTX_CPF, score_invalido=0.85, nome="cpf:flexivel"),
    # Número colado à sigla, comum em texto extraído por OCR ("CPF529.982.247-25"). A sigla é
    # exigida em maiúsculas para não casar com o interior de palavras.
    Padrao("CPF", r"(?-i:CPF|C\.P\.F\.?)(?P<v>\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s/]?\d{2})" + DEPOIS_NUM, 0.9,
           grupo="v", nome="cpf:colado"),
    Padrao("CNPJ", r"(?-i:CNPJ)(?P<v>[0-9A-Z]{2}\.?[0-9A-Z]{3}\.?[0-9A-Z]{3}/?[0-9A-Z]{4}-?\d{2})" + DEPOIS_NUM, 0.9,
           grupo="v", nome="cnpj:colado"),
    Padrao("DOCUMENTO", r"(?-i:RG|CNH|PIS|NIS|CNS|SIAPE)(?P<v>\d[\d.\-]{5,14}\d)" + DEPOIS_NUM, 0.85, grupo="v",
           nome="documento:colado"),
    # ---------------- CNPJ (numérico e alfanumérico, IN RFB nº 2.229/2024)
    Padrao("CNPJ", ANTES_NUM + r"[0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-\d{2}" + DEPOIS_NUM, 0.8,
           nome="cnpj:formatado"),
    Padrao("CNPJ", ANTES_NUM + r"[0-9A-Z]{2}\.?[0-9A-Z]{3}\.?[0-9A-Z]{3}/?[0-9A-Z]{4}-?\d{2}" + DEPOIS_NUM, 0.9,
           validador=v.cnpj_valido, contexto=CTX_CNPJ, score_invalido=0.8,
           nome="cnpj:flexivel"),
    # ---------------- PIS/PASEP/NIS/NIT
    Padrao("PIS", ANTES_NUM + r"\d{3}\.\d{5}\.\d{2}-\d" + DEPOIS_NUM, 0.8, nome="pis:formatado"),
    # Sem a pontuação característica, onze dígitos válidos como PIS também podem ser CPF ou CNH: a
    # regra exige contexto.
    Padrao("PIS", ANTES_NUM + r"\d{3}[.\s]?\d{4,5}[.\s]?\d{2,3}[-.\s]?\d" + DEPOIS_NUM, 0.9,
           validador=v.pis_valido, contexto=CTX_PIS, contexto_obrigatorio=True, score_invalido=0.85,
           nome="pis:contexto"),
    # ---------------- Título de eleitor
    Padrao("TITULO_ELEITOR", ANTES_NUM + r"\d{4}\s?\d{4}\s?\d{4}" + DEPOIS_NUM, 0.9,
           validador=v.titulo_eleitor_valido, contexto=CTX_TITULO, score_invalido=0.85,
           nome="titulo:validado"),
    # ---------------- CNS (Cartão SUS): primeiro dígito 1 ou 2 (definitivo) ou 7, 8 ou 9 (provisório)
    Padrao("CNS", ANTES_NUM + r"[12789]\d{2}\s?\d{4}\s?\d{4}\s?\d{4}" + DEPOIS_NUM, 0.9,
           validador=v.cns_valido, contexto=CTX_CNS, score_invalido=0.85, nome="cns:validado"),
    # ---------------- CNH: o contexto é obrigatório porque o registro tem onze dígitos, como o CPF
    Padrao("CNH", ANTES_NUM + r"\d{9,11}" + DEPOIS_NUM, 0.9, validador=v.cnh_valida, contexto=CTX_CNH,
           contexto_obrigatorio=True, score_invalido=0.85, nome="cnh:contexto"),
    # ---------------- RG: o formato varia por estado; exige a palavra-chave e inclui o órgão emissor
    # e a UF ("1.234.567 SSP/DF"), que também identificam a pessoa quando combinados ao número.
    Padrao("RG",
           r"(?:\bRG|\bR\.G\.|\bidentidade|carteira de identidade|c[ée]dula de identidade|\bCIN\b|"
           r"registro geral|\bdoc(?:umento)?\.? de identidade)" + _SEP + _NUM + _SEP +
           r"(?P<v>(?:[A-Z]{2}[-\s]?)?\d{1,3}(?:\.?\d{3}){1,3}(?:\s?-\s?[\dXx])?"
           r"(?:\s*[-/]?\s*(?:SSP|SESP|SDS|PC|PCDF|SSPDF|DETRAN|IFP|IIRGD|SJS|SSPDS|DGPC|IGP|SEJUSP|SPTC|DIC|ITEP)"
           r"(?:\s*[-/]\s*[A-Z]{2})?)?)", 0.9, camada=CONTEXTUAL, grupo="v", nome="rg:contexto"),
    # ---------------- Passaporte brasileiro: duas letras e seis dígitos (formatos antigos variam)
    Padrao("PASSAPORTE", r"passaporte" + _SEP + _NUM + _SEP + r"(?P<v>[A-Z]{1,2}\s?\d{6,8})\b", 0.9,
           camada=CONTEXTUAL, grupo="v"),
    # ---------------- CTPS: número e, opcionalmente, série e UF
    Padrao("CTPS",
           r"(?:\bctps|carteira de trabalho(?: e previd[êe]ncia social)?)" + _SEP + _NUM + _SEP +
           r"(?P<v>\d{3,8}(?:\s*[,/-]?\s*s[ée]rie\s*\d{3,5}(?:\s*[-/]\s*[A-Z]{2})?)?)", 0.9,
           camada=CONTEXTUAL, grupo="v"),
    # ---------------- Certidão civil: matrícula nacional de 32 dígitos (Provimento CNJ nº 3/2009)
    Padrao("CERTIDAO", ANTES_NUM + r"\d{6}\s?\d{2}\s?\d{2}\s?\d{4}\s?\d\s?\d{5}\s?\d{3}\s?\d{7}[-\s]?\d{2}" + DEPOIS_NUM,
           0.9),
    # ---------------- Matrícula funcional / SIAPE
    Padrao("MATRICULA",
           r"(?:matr[íi]cula(?:\s+(?:funcional|gdf|siape|do servidor|da servidora))?|\bmat\.|\bsiape)" + _SEP + _NUM +
           _SEP + r"(?P<v>[A-Z]?\d{1,3}(?:\.\d{3}){1,2}(?:\s?-\s?[\dXx])?|[A-Z]?\d{4,10}(?:\s?-\s?[\dXx]|[A-Z])?)"
           + DEPOIS_NUM,
           0.9, camada=CONTEXTUAL, grupo="v"),
    # ---------------- Registro em conselho profissional (OAB, CRM, CREA, CAU…): sigla e número, em
    # qualquer ordem. Siglas em maiúsculas, para não casar com palavras comuns.
    Padrao("REGISTRO_PROFISSIONAL",
           r"(?P<v>\b(?:OAB|CRM|CRO|CRP|COREN|CREA|CAU|CRF|CRN|CREFITO|CRMV|CRC|CRBio|CRESS|CREF|CRFa|CRQ|"
           r"CORECON|CRA|CRECI|CRTR|CRBM)\s*[-/]?\s*(?:[A-Z]{2}\s*)?" + _NUM + r"[:\-]?\s*[A-Z]?\d{1,3}(?:\.?\d{3})*"
           r"(?:\s*[-/]\s*[A-Z0-9]{1,2}\b)?)", 0.9, ignorar_caixa=False, nome="registro:sigla-numero"),
    Padrao("REGISTRO_PROFISSIONAL",
           r"(?P<v>\b\d{1,3}(?:\.?\d{3})*\s*[-/]?\s*(?:OAB|CRM|CREA|CRO|CRP|COREN|CAU)\s*[-/]\s*[A-Z]{2}\b)", 0.9,
           ignorar_caixa=False, nome="registro:numero-sigla"),
    # ---------------- Data de nascimento: só a data precedida de expressão de nascimento; datas
    # isoladas são frequentes em documentos públicos e não são dado pessoal por si.
    Padrao("DATA_NASCIMENTO",
           r"(?:\bnascid[oa]s?|\bnascimento|\bnasc\b\.?|\bD\.?N\.?(?=\s*[:\-]|\s+\d)|\bdata de nasc\.?|\bnasceu|\bnasci|"
           r"\bnaci|\bnascida|\banivers[áa]rio|\bniver|\bdt\.?\s*nasc\.?)"
           r"[^\d\n]{0,30}?(?P<v>\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*(?:19|20)?\d{2}(?!\d)|"
           r"\d{1,2}\s+de\s+(?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|"
           r"novembro|dezembro)\s+de\s+\d{4})", 0.9, camada=CONTEXTUAL, grupo="v"),
    # ---------------- Identificadores de cliente ou contribuinte (água, energia, IPTU, inscrições):
    # número com dígito após hífen, perto de uma expressão que indica o cadastro.
    Padrao("DOCUMENTO", ANTES_NUM + r"\d{3,12}-[\dXx]" + DEPOIS_NUM, 0.8,
           contexto=(r"unidades?\s+consumidoras?", r"inscri[çc](?:[ãa]o|[õo]es)", r"hidr[ôo]metros?",
                     r"conta[\s-]contrato", r"c[óo]digo\s+do\s+cliente", r"instala[çc][ãa]o", r"matr[íi]culas?",
                     r"cadastro", r"contratos?", r"im[óo]vel", r"iptu", r"cliente", r"benef[íi]cio"),
           contexto_obrigatorio=True, janela=50, nome="documento:cliente"),
    # ---------------- Qualquer número após palavra que designa documento (falhar fechado): cobre
    # documentos de estrangeiros (RNE, RNM, CRNM), inscrições estaduais e municipais e registros.
    Padrao("DOCUMENTO",
           r"(?:\bdocumento|\binscri[çc][ãa]o(?: estadual| municipal)?|\bRNE|\bRNM|\bCRNM|\bNIRF|\bCAEPF|"
           r"\bregistro(?: civil)?)\s*(?:de identifica[çc][ãa]o\s*)?" + _SEP + _NUM + _SEP +
           r"(?P<v>[A-Z]{0,3}\d[\d.\-/]{5,20}\d)", 0.75, camada=CONTEXTUAL, grupo="v", nome="documento:contexto"),
]
