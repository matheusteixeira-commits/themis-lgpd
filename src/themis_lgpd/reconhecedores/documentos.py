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

import regex as re

from .. import validadores as v
from .base import ANTES_NUM, CONTEXTUAL, DEPOIS_NUM, Deteccao, Padrao
from .pessoais import DATA_POR_EXTENSO, MES_ROMANO, MESES, NASCEU_SEM_PESSOA

#: Indicação opcional de número entre a palavra-chave e o valor: "nº", "n.", "número", "de número".
_NUM = r"(?:(?:de\s+)?n(?:[º°o]|úm(?:ero)?|um(?:ero)?)?\.?\s*)?"
#: Separador opcional entre a palavra-chave e o valor: "RG: 123", "RG - 123", "meu RG é 123",
#: "meu RG é o 123", "inscrito sob o nº 123", "o RG dele é 123".
_SEP = r"\s*(?:\b(?:dele|dela|deles|delas)\b\s*)?(?:[:\-–]|\b(?:é|e|era|sendo|seria)\b(?:\s+(?:o|a)\b)?|\bsob\s+o\b)?\s*"

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
#: Siglas das unidades da Federação, que acompanham o registro em conselho ("CRM-PB", "OAB/SC").
_UF = r"(?:A[CLMP]|BA|CE|DF|ES|GO|M[AGST]|P[ABEIR]|R[JNORS]|S[CEP]|TO)"
#: Caractere de máscara em documentos parcialmente ocultados ("***.123.456-**", "123.XXX.XXX-45").
_MASCARA = r"[*Xx•#]"
#: País ou nacionalidade entre a designação de um documento estrangeiro e o número: até quatro
#: palavras sem dígitos ("haitiano", "de la République d'Haïti"), que não podem ser a indicação de
#: número nem uma conjunção.
_ORIGEM = r"(?:\s+(?!(?:e|ou|n[º°o]|n[úu]mero|nr|sob)\b)(?-i:[a-zà-ÿA-ZÀ-Ý][\w'’\-]*)){0,4}?"
#: Postos e graduações militares abreviados, como aparecem em escalas e boletins ("SD", "3º SGT",
#: "1º TEN", "TEN CEL"); o ordinal chega à detecção como "o" (forma de compatibilidade Unicode).
_POSTO = (r"(?:SD|CB|[123][º°o]?\s?SGT|SGT|SUBTEN|ST|ASP(?:\s+OF)?|[12][º°o]?\s?TEN|TEN(?:[\s\-]CEL)?|CAP|MAJ|CEL|"
          r"Sd|Cb|[123][º°o]?\s?Sgt|Sgt|Subten|[12][º°o]?\s?Ten|Cap|Maj|Cel)")
#: Quadro ou corporação que segue o posto: Polícia Militar e Corpo de Bombeiros e seus quadros.
_CORPORACAO = r"(?:PM|BM|QOPM|QPPM|QOBM|QPBM|QOEM|QOE|QOA|QOS|QPE|QPMP|QOC|CBM)"
#: Componentes do assento de registro civil ou de ato notarial no formato antigo: livro, folha e
#: termo, em qualquer ordem ("termo 1.234, livro A-12, folha 56", "Livro 214, fls. 88", "acta nº 3,
#: tomo 2, folio 15").
_C_LIVRO = r"(?:livro|liv\.|tomo|libro|registre)\s*(?:n[º°o]\.?\s*)?(?-i:[A-Z]{1,2}-?)?\d(?:[\d.]*\d)?"
_C_FOLHA = r"(?:folhas?|fls?\.|fls|folio|f[óo]lio|foja|feuillet)\s*(?:n[º°o]\.?\s*)?\d+(?:\s?v(?:erso)?\b)?"
_C_TERMO = r"(?:termo|assento|acta|acte)\s*(?:n[º°o]\.?\s*)?\d(?:[\d.]*\d)?"
#: Expressões que indicam registro civil ou ato de notas: certidões e assentos de nascimento,
#: casamento e óbito, registros de nascimento de outros países e de indígenas (RANI), pactos e
#: escrituras.
_CTX_ASSENTO = (r"certid[ãa]o", r"cert\.", r"nasc\w*", r"casament\w*", r"[óo]bito", r"RANI", r"registro\s+civil",
                r"assento", r"partida", r"acta", r"acte", r"naissance", r"nacimiento", r"matrimonio", r"antenupcial",
                r"escritura", r"tabeli\w+", r"cart[óo]rio", r"serventia", r"notas")
#: A sigla de conselho profissional não pode vir logo após a designação de um ato ("Ofício OAB/UF nº",
#: "Parecer Técnico CREA-UF nº") nem perto da menção a pessoa jurídica ("registro de pessoa jurídica
#: no CREA-UF nº"): o número é do ato ou da empresa.
_NAO_ATO_CONSELHO = (r"(?<!(?i:\b(?:of[íi]cio|of\.|parecer(?:\s+t[ée]cnico)?|resolu[çc][ãa]o|portaria|nota(?:\s+t[ée]cnica)?|"
                     r"delibera[çc][ãa]o|ac[óo]rd[ãa]o|edital|instru[çc][ãa]o\s+normativa|ato|circular|memorando|despacho|"
                     r"decis[ãa]o|provimento|recomenda[çc][ãa]o|conv[êe]nio|termo\s+de\s+\w+)\s{1,3}))"
                     r"(?<!(?i:pessoa\s+jur[íi]dica|empresa|\bPJ)\b[^\n.;]{0,20})")
#: Número do registro em conselho, com a letra inicial e o sufixo de categoria ou de dígito opcionais
#: ("A12345-6", "123.456-ENF" até o hífen, "12345-P"), inclusive com o código do estado antes do ponto
#: ("52.12345-6").
_NUM_CONSELHO = r"[A-Z]?(?:\d{1,3}(?:\.\d{3})+|\d{1,2}\.\d{4,6}|\d{3,})(?:\s*[-/]\s*[A-Z0-9]{1,2}\b){0,2}"
#: Data numérica completa ("12/05/2025", "12.05.25").
_DATA = re.compile(r"\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*\d{2,4}")

#: Regras de documentos de identificação.
PADROES: list[Padrao | ColunasIdentificadoras] = [
    # ---------------- CPF
    Padrao("CPF", ANTES_NUM + r"\d{3}\.\d{3}\.\d{3}-\d{2}" + DEPOIS_NUM, 0.8, nome="cpf:formatado"),
    # Pontuação parcial, espaços e separadores trocados ("529 982 247 25", "529.982.247/25").
    Padrao("CPF", ANTES_NUM + r"\d{3}[.\s]{0,2}\d{3}[.\s]{0,2}\d{3}\s{0,2}[-.\s/]?\s{0,2}\d{2}" + DEPOIS_NUM,
           0.9, validador=v.cpf_valido, contexto=CTX_CPF, score_invalido=0.85, nome="cpf:flexivel"),
    # Número colado à sigla, comum em texto extraído por OCR ("CPF529.982.247-25"). A sigla é
    # exigida em maiúsculas para não casar com o interior de palavras.
    Padrao("CPF", r"(?-i:CPF|C\.P\.F\.?)(?P<v>\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s/]?\d{2})" + DEPOIS_NUM, 0.9,
           grupo="v", nome="cpf:colado"),
    # CPF parcialmente mascarado, como publicam os órgãos ao divulgar atos com o nome do servidor ou
    # do candidato ("***.123.456-**", "123.XXX.XXX-45"): os dígitos visíveis, somados ao nome,
    # ainda identificam a pessoa. Exige ao menos um grupo mascarado e um grupo de dígitos; tolera a
    # quebra de linha após um separador.
    Padrao("CPF", r"(?<![\w*•#.])(?:\d{3}|" + _MASCARA + r"{3})\.\s?(?:\d{3}|" + _MASCARA + r"{3})\.\s?(?:\d{3}|" +
           _MASCARA + r"{3})\s?-\s?(?:\d{2}|" + _MASCARA + r"{2})(?![\w*•#])", 0.9,
           validador=lambda valor: _cpf_mascarado(valor), nome="cpf:mascarado"),
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
    # ---------------- CNS (Cartão SUS): primeiro dígito 1 ou 2 (definitivo) ou 7, 8 ou 9 (provisório),
    # em grupos de 3-4-4-4 separados por espaço ou ponto.
    Padrao("CNS", ANTES_NUM + r"[12789]\d{2}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4}" + DEPOIS_NUM, 0.9,
           validador=v.cns_valido, contexto=CTX_CNS, score_invalido=0.85, nome="cns:validado"),
    # ---------------- CNH: o contexto é obrigatório porque o registro tem onze dígitos, como o CPF
    Padrao("CNH", ANTES_NUM + r"\d{9,11}" + DEPOIS_NUM, 0.9, validador=v.cnh_valida, contexto=CTX_CNH,
           contexto_obrigatorio=True, score_invalido=0.85, nome="cnh:contexto"),
    # ---------------- RG: o formato varia por estado; exige a palavra-chave. O órgão emissor e a UF
    # ("1.234.567 SSP/DF") ficam fora da tarja: são informação pública e, sem o número, não
    # identificam ninguém.
    Padrao("RG",
           r"(?:\bRG|\bR\.G\.|\bidentidade(?:\s+(?:civil|militar))?|carteira de identidade|c[ée]dula de identidade|"
           r"\bCIN\b|registro geral|\bdoc(?:umento)?\.? de identidade)" + _SEP + _NUM + _SEP +
           r"(?P<v>(?:[A-Z]{2}[-\s]?)?\d{1,3}(?:\.?\d{3}){1,3}(?:\s?-\s?[\dXx])?)(?![\w])(?!\.\d)", 0.9,
           camada=CONTEXTUAL, grupo="v", nome="rg:contexto"),
    # ---------------- Passaporte brasileiro: duas letras e seis dígitos (formatos antigos variam).
    # Passaportes estrangeiros têm de seis a dez caracteres, com letras e dígitos em qualquer posição
    # ("C01X00T47"): aceitos em maiúsculas e com ao menos três dígitos. A designação pode vir em
    # outra língua e seguida do país emissor ("passaporte peruano nº", "passeport de la République de
    # X nº").
    Padrao("PASSAPORTE", r"\b(?:passaporte|passeport|pasaporte|passport|passaporto)" + _ORIGEM + _SEP + _NUM + _SEP +
           r"(?P<v>[A-Z]{1,2}\s?\d{6,8}\b|(?-i:(?=[A-Z0-9]{6,10}(?![\w]))(?=(?:[A-Z]*\d){3})[A-Z0-9]{6,10}))", 0.9,
           camada=CONTEXTUAL, grupo="v"),
    # ---------------- Documentos de identidade estrangeiros (migrantes e refugiados): cédula de
    # identidad ("V-12.345.678", "6.123.456 LP"), carta d'identità, carte d'identité, DNI e
    # identificadores fiscais nacionais (NIF, CUIL, RUT…), com o país ou a nacionalidade entre a
    # designação e o número. A sigla do departamento emissor que segue o número fica visível.
    Padrao("DOCUMENTO",
           r"(?:\bc[ée]dula\s+de\s+identi(?:dad|ficaci[óo]n)|\bcarta\s+d['’]\s?identit[àa](?:\s+elettronica)?|"
           r"\bcarte\s+(?:nationale\s+)?d['’]\s?identit[ée]|\bdocumento\s+nacional\s+de\s+identidad|"
           r"(?-i:\b(?:DNI|NIF|NIE|CUIL|CUIT|RUT|RUN|CURP)\b))" + _ORIGEM + _SEP + _NUM + _SEP +
           r"(?P<v>(?-i:[VE])-?\d{1,3}(?:\.\d{3}){1,3}|\d{1,3}(?:\.\d{3}){1,3}(?:-[\dK])?|"
           r"\d[\d\-]{4,16}[\dK]|(?-i:(?=[A-Z0-9]{7,18}(?![\w]))(?=(?:[A-Z]*\d){3})[A-Z0-9]{7,18}))(?![\w])(?![.\-/]\d)",
           0.9, camada=CONTEXTUAL, grupo="v", validador=lambda valor: not _DATA.fullmatch(valor) and
           not re.fullmatch(r"(?:19|20)\d{2}-\d{1,2}-\d{1,2}", valor), nome="documento:estrangeiro"),
    # Cédula venezuelana pela letra de nacionalidade ("cédula V-12.345.678"), mesmo sem "de identidad".
    Padrao("DOCUMENTO", r"\bc[ée]dula" + _SEP + _NUM + _SEP + r"(?P<v>(?-i:[VE])-\d{1,3}(?:\.\d{3}){1,3}|(?-i:[VE])-\d{6,9})"
           r"(?![\w])(?![.\-/]\d)", 0.9, camada=CONTEXTUAL, grupo="v", nome="documento:cedula"),
    # Codice fiscale italiano: seis letras do nome, data e município de nascimento codificados e um
    # caractere de controle; reconhecido pela forma e pelo caractere de controle.
    Padrao("DOCUMENTO", r"(?<![\w])[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-EHLMPR-T][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]"
           r"(?![\w])", 0.9, ignorar_caixa=False, validador=v.codice_fiscale_valido, nome="documento:codice-fiscale"),
    # Número de identidade chinês (GB 11643): dezoito caracteres com data de nascimento e dígito de
    # controle ISO 7064; exige menção a identidade ou documento por perto.
    Padrao("DOCUMENTO", ANTES_NUM + r"\d{17}[\dXx]" + DEPOIS_NUM, 0.9, validador=v.identidade_chinesa_valida,
           contexto=(r"identidade", r"identity", r"chin[êe]s[ae]?", r"documento", r"ID"), contexto_obrigatorio=True,
           janela=60, nome="documento:identidade-chinesa"),
    # ---------------- CTPS: número e, opcionalmente, série e UF
    Padrao("CTPS",
           r"(?:\bctps|carteira de trabalho(?: e previd[êe]ncia social)?)" + _SEP + _NUM + _SEP +
           r"(?P<v>\d{3,8}(?:\s*[,/-]?\s*s[ée]rie\s*\d{3,5}(?:\s*[-/]\s*[A-Z]{2})?)?)", 0.9,
           camada=CONTEXTUAL, grupo="v"),
    # ---------------- Certidão civil: matrícula nacional de 32 dígitos (Provimento CNJ nº 3/2009)
    Padrao("CERTIDAO", ANTES_NUM + r"\d{6}\s?\d{2}\s?\d{2}\s?\d{4}\s?\d\s?\d{5}\s?\d{3}\s?\d{7}[-\s]?\d{2}" + DEPOIS_NUM,
           0.9),
    # ---------------- Assento de registro civil ou ato de notas no formato antigo, citado por livro,
    # folha e termo ("termo 1.234, livro A-12, folha 56", "Livro 214, fls. 88"), inclusive em
    # registros de outros países ("acta nº 3, tomo 2, folio 15") e de nascimento indígena (RANI). A
    # citação inteira identifica o assento; exige ao menos dois componentes, um deles livro ou folha, e
    # menção a certidão, nascimento, casamento, óbito ou cartório por perto.
    Padrao("CERTIDAO",
           r"(?<![\w])(?P<v>(?:(?<=(?:\bn[º°o]\.?|:)\s{0,2})\d(?:[\d.]*\d)?|" + _C_LIVRO + "|" + _C_TERMO + r")"
           r"(?:\s*[,;]?\s*(?:" + _C_LIVRO + "|" + _C_FOLHA + "|" + _C_TERMO + r")){1,3})(?![\w])",
           0.85, camada=CONTEXTUAL, grupo="v", validador=lambda valor: _assento(valor), contexto=_CTX_ASSENTO,
           contexto_obrigatorio=True, janela=80, nome="certidao:livro-folha"),
    # ---------------- Matrícula funcional: SIAPE (União), MASP (MG), ID funcional (RJ, RS), registro
    # funcional (RF, município de São Paulo: "123.456.7/1"), número, registro e identidade funcional
    # dos demais entes, inclusive com a abreviatura sem ponto, em maiúsculas, de formulários ("MATR
    # 12345", "MAT 12.345"). A sigla do órgão pode preceder o número ("ABC-12345-X"), e o número do
    # vínculo pode segui-lo ("1234567/01"). Um ano isolado não é matrícula ("matrícula 2025" é o
    # cabeçalho de uma contagem).
    Padrao("MATRICULA",
           r"(?:matr[íi]cula(?:\s+(?:funcional|gdf|siape|do servidor|da servidora))?|\bmatr?\.|(?-i:\bMATR?\b)|\bsiape|"
           r"\bMASP\b|\bID\.?\s*funcional|\b(?:registro|identidade|identifica[çc][ãa]o|n[úu]mero)\s+funcional|"
           r"\bn[º°o]\.?\s*funcional)" + _SEP + _NUM +
           _SEP + r"(?P<v>(?:(?-i:[A-Z]{2,4})-)?(?:[A-Z]?\d{1,3}(?:\.\d{3}){1,2}(?:\.\d)?(?:\s?-\s?[\dXx])?|"
           r"[A-Z]?\d{4,10}(?:\s?-\s?[\dXx]|[A-Z])?)(?:/\d{1,2})?)" + DEPOIS_NUM,
           0.9, camada=CONTEXTUAL, grupo="v", validador=lambda valor: not _ano(valor)),
    # Militar estadual identificado pelo posto ou graduação, pelo quadro e pelo número, como nas
    # escalas e boletins das polícias e dos corpos de bombeiros ("SD PM 100.000-0 FULANO", "2º TEN
    # QOPM 120.000-1"): o número é a matrícula do militar.
    Padrao("MATRICULA", r"(?<![\w])" + _POSTO + r"\s+" + _CORPORACAO + r"\s+(?P<v>\d{1,3}(?:\.\d{3}){1,2}(?:\s?-\s?\d)?|"
           r"\d{4,9}(?:-\d)?)" + DEPOIS_NUM, 0.85, camada=CONTEXTUAL, grupo="v", ignorar_caixa=False,
           nome="matricula:posto"),
    # A sigla "RF" é ambígua; só é aceita com o formato do registro funcional ("RF 123.456.7/1").
    Padrao("MATRICULA", r"(?-i:\bR\.?F\.?)\s*[:\-]?\s*" + _NUM + r"(?P<v>\d{3}\.\d{3}\.\d(?:\s*/\s*\d{1,2})?)" + DEPOIS_NUM,
           0.9, camada=CONTEXTUAL, grupo="v", nome="matricula:rf"),
    # ---------------- Número de benefício do INSS (NB), com dez dígitos.
    Padrao("BENEFICIO",
           r"(?:(?-i:\bNB\b)|\bn[úu]mero\s+do\s+benef[íi]cio|\bbenef[íi]cio(?:\s+(?:previdenci[áa]rio|assistencial|"
           r"do\s+INSS|de\s+presta[çc][ãa]o\s+continuada))?(?=\s*(?:NB|n[º°o]|n[úu]mero|[:\-]|\d)))" + _SEP + _NUM +
           _SEP + r"(?P<v>\d{3}\.?\d{3}\.?\d{3}-?\d)(?!\d)", 0.9, camada=CONTEXTUAL, grupo="v", nome="beneficio:nb"),
    # ---------------- Registros de saúde: prontuário, declaração de nascido vivo (DNV), autorização de
    # internação hospitalar (AIH) e cartão de vacinação. O prontuário pode trazer a sigla do serviço
    # ou do sistema ("Prontuário CER:", "Prontuário SIGLA nº") ou uma qualificação ("prontuário
    # familiar", "prontuário prisional"), e o número pode começar pela sigla da unidade que o emitiu
    # ("ABC-0123/2024", "XYZ-UN 0371").
    Padrao("REGISTRO_SAUDE",
           r"(?:\bprontu[áa]rio(?:\s+(?:m[ée]dico|familiar|prisional|eletr[ôo]nico|hospitalar|ambulatorial|"
           r"odontol[óo]gico|cl[íi]nico|social|(?-i:[A-Z]{2,8})))?(?:\s+(?:n[ao]|d[ao])\s+(?:unidade|servi[çc]o|hospital|"
           r"institui[çc][ãa]o|paciente|usu[áa]ri[oa]))?|(?-i:\bDNV\b)|declara[çc][ãa]o\s+de\s+nascido\s+vivo|"
           r"(?-i:\bAIH\b)|autoriza[çc][ãa]o\s+de\s+interna[çc][ãa]o(?:\s+hospitalar)?|cart[ãa]o\s+de\s+vacina(?:[çc][ãa]o)?)"
           + _SEP + _NUM + _SEP + r"(?P<v>(?:(?-i:(?!(?:CPF|RG|CNS|CNH|NIS|PIS|SUS)\b)[A-Z][A-Z0-9]{1,7}"
           r"(?:-[A-Z0-9]{1,6})?)[\s\-]?)?\d[\d.\-/]{2,20}\d)(?!\d)",
           0.9, camada=CONTEXTUAL, grupo="v", nome="saude:registro"),
    # Registro da pessoa nos sistemas nacionais de informação em saúde que identificam o usuário ou o
    # caso: atenção à saúde indígena (SIASI), agravos de notificação (SINAN), regulação (SISREG),
    # nascidos vivos (SINASC), imunização (SIPNI) e câncer (SISCAN).
    Padrao("REGISTRO_SAUDE",
           r"(?-i:\b(?:SIASI|SINAN|SISREG|SINASC|SIPNI|SISCAN|SISPRENATAL)\b)\s*[:\-]?\s*" + _NUM + r"[:\-]?\s*"
           r"(?P<v>\d[\d.\-/]{3,18}\d)(?![\w])(?![.\-/]\d)", 0.85, camada=CONTEXTUAL, grupo="v",
           validador=lambda valor: _numero_de_registro(valor), nome="saude:sistema"),
    # ---------------- Matrícula escolar e registro acadêmico (RA), inclusive com os grupos de dígitos
    # separados por pontos ("R.A.: 000.123.456-7").
    Padrao("MATRICULA_ESCOLAR",
           r"(?:(?-i:\bR\.?A\.?)(?=\s*(?:n[º°o]|[:\-]|\d))|\bregistro\s+acad[êe]mico|\bmatr[íi]cula\s+(?:escolar|do\s+alun[oa]|"
           r"da\s+alun[oa]|acad[êe]mica|do\s+estudante)|\bc[óo]digo\s+do\s+alun[oa])" + _SEP + _NUM + _SEP +
           r"(?P<v>[A-Z]?(?:\d{1,3}(?:\.\d{3}){2,4}|\d{4,14})(?:-?[\dX])?)(?!\d)", 0.9, camada=CONTEXTUAL, grupo="v",
           nome="escolar:ra"),
    # ---------------- Inscrição imobiliária (IPTU), índice cadastral e cadastro de contribuinte municipal.
    Padrao("INSCRICAO_IMOVEL",
           r"(?:\binscri[çc][ãa]o\s+(?:imobili[áa]ria|cadastral|do\s+im[óo]vel)|\b[íi]ndice\s+cadastral|(?-i:\bCCM\b)|"
           r"\bn[úu]mero\s+de\s+contribuinte|\bcadastro\s+imobili[áa]rio|(?-i:\bIPTU\b))[^\d\n;]{0,25}?"
           r"(?P<v>\d[\d.\-/]{4,24}\d)(?!\d)", 0.85, camada=CONTEXTUAL, grupo="v", nome="imovel:inscricao"),
    # ---------------- Inscrição estadual abreviada ("IE 110.042.490.114"); por extenso, ver
    # "documento:contexto".
    Padrao("DOCUMENTO", r"(?-i:\bI\.?E\.?)" + _SEP + _NUM + _SEP + r"(?P<v>\d[\d.\-/]{6,18}\d)(?!\d)", 0.85,
           camada=CONTEXTUAL, grupo="v", nome="documento:ie"),
    # ---------------- RG com a palavra-chave depois do número ("12.345.678-9 (identidade)").
    Padrao("RG", ANTES_NUM + r"\d{1,2}\.\d{3}\.\d{3}\s?-\s?[\dXx]" + DEPOIS_NUM, 0.85,
           contexto=(r"rg", r"identidade", r"ssp", r"c[ée]dula"), contexto_obrigatorio=True, nome="rg:contexto-depois"),
    # ---------------- Registro em cadastros profissionais não vinculados a conselho: transportadores
    # (RNTRC), turismo (CADASTUR), pesca (Registro Geral da Atividade Pesqueira, RGP, com a UF antes do
    # número: "RGP AB-00012345") e registro profissional no Ministério do Trabalho ("registro MTE
    # UF/001234.5").
    Padrao("REGISTRO_PROFISSIONAL", r"(?-i:\b(?:RNTRC|CADASTUR))" + _SEP + _NUM + _SEP + r"(?P<v>\d[\d.\-/]{4,16}\d)",
           0.9, camada=CONTEXTUAL, grupo="v", nome="registro:cadastro"),
    Padrao("REGISTRO_PROFISSIONAL",
           r"(?:(?-i:\bRGP\b)|\bregistro\s+geral\s+d[ae]\s+(?:atividade\s+)?pesc\w+|\bregistro\s+(?:n[oa]\s+)?(?-i:MTE|SRTE)\b)"
           + _SEP + _NUM + _SEP + r"(?P<v>(?:(?-i:[A-Z]{2})\s*[-/]\s*)?\d[\d.\-/]{3,16}\d)(?![\w])(?![.\-/]\d)", 0.9,
           camada=CONTEXTUAL, grupo="v", nome="registro:pesca-trabalho"),
    # ---------------- Carteiras de identificação de categorias de pessoas, sem formato nacional: da
    # pessoa com transtorno do espectro autista (CIPTEA, Lei nº 13.977/2020), da pessoa com
    # deficiência, do idoso, funcional, estudantil e outras ("Carteira de Identificação X nº …").
    Padrao("DOCUMENTO",
           r"(?:(?-i:\bCIPTEA\b)|\bcarteira(?:\s+(?!(?:de\s+(?:trabalho|motorista|habilita[çc][ãa]o|vacina\w*|identidade)|"
           r"nacional\s+de\s+habilita)\b)(?:d[aeo]s?\s+|com\s+)?[^\W\d_][\w\-]*){1,7}?(?=\s*(?:n[º°o]\b|n[úu]mero\b|:)))"
           + _SEP + _NUM + _SEP + r"(?P<v>(?:(?-i:[A-Z]{1,4})-?)?\d[\dA-Z.\-/]{2,24}[\dA-Z])(?![\w])(?![.\-/]\d)", 0.85,
           camada=CONTEXTUAL, grupo="v", validador=lambda valor: _numero_de_registro(valor), nome="documento:carteira"),
    # ---------------- "Registro profissional" seguido do registro em qualquer formato: sigla do conselho
    # ou do órgão, com UF ou região ("ABC/SP 12345/RJ", "XYZ-12345"), ou o número seguido da UF ou de
    # letra de categoria ("012345-DF", "12345-P"). O registro inteiro identifica o profissional.
    Padrao("REGISTRO_PROFISSIONAL",
           r"\b(?:registro|inscri[çc][ãa]o)\s+(?:profissional|de\s+classe|no\s+conselho)"
           r"(?:\s+(?:provis[óo]ri[oa]|definitiv[oa]|secund[áa]ri[oa]))?" + _SEP + _NUM + _SEP +
           r"(?P<v>(?:(?-i:[A-Z]{2,7})(?:\s*[-/]\s*(?:(?-i:[A-Z]{2})|\d{1,2}))?\s*[-:]?\s*)?"
           r"(?:\d{1,3}(?:\.\d{3})+|\d{3,12})(?:\s*[-/]\s*(?:(?-i:[A-Z]{1,4})|\d{1,2})(?![\w]))?)" + DEPOIS_NUM,
           0.9, camada=CONTEXTUAL, grupo="v", nome="registro:profissional"),
    # ---------------- Certidão no formato antigo: número do termo, com livro e folha por perto.
    Padrao("CERTIDAO", r"\btermo\s*(?:n[º°o]?\.?\s*)?(?P<v>\d[\d.]{1,9}\d|\d)(?![\d])", 0.85,
           contexto=(r"livro", r"folhas?", r"fls?\."), contexto_obrigatorio=True, janela=60, camada=CONTEXTUAL,
           grupo="v", nome="certidao:termo"),
    # ---------------- Registro em conselho profissional (OAB, CRM, CREA, CAU…): sigla e número, em
    # qualquer ordem. Siglas em maiúsculas, para não casar com palavras comuns. A região do conselho
    # ("CRN-3", "CRP-06", "CRESS 6ª Região") integra o número e fica sob a tarja; a sigla e a UF
    # ("OAB/SP", "COREN-AM") ficam visíveis, pois sem o número não identificam ninguém. O Registro de
    # Qualificação de Especialista (RQE) segue a mesma forma. A sigla do conselho seguida do número
    # de um ato ("Ofício OAB/UF nº 12/2025", "Parecer Técnico CREA-UF nº 3/2025") ou do registro de
    # pessoa jurídica não é registro profissional.
    Padrao("REGISTRO_PROFISSIONAL",
           _NAO_ATO_CONSELHO + r"\b(?:OAB|CRM|CRO|CRP|COREN|CREA|CAU|CRF|CRN|CREFITO|CRMV|CRC|CRBio|CRESS|CREF|CRFa|CRQ|"
           r"CORECON|CRA|CRECI|CRTR|CRBM|CRB|CRT|MTB|MTb|DRT|RQE)(?:\s*[-/]?\s*" + _UF + r"\b)?\s*[-/]?\s*"
           # O ordinal da região chega à detecção como "a" (forma de compatibilidade Unicode).
           r"(?:(?P<v>(?:\d{1,2}[ªa](?:\s*(?:Regi[ãa]o|REGI[ÃA]O|R(?:eg)?\.)|(?![\w]))|\d{1,2}\b)\s*[-/]?\s*"
           r"(?:sob\s+o\s+)?" + _NUM + r"[:\-]?\s*" + _NUM_CONSELHO + r")|(?:sob\s+o\s+)?" + _NUM + r"[:\-]?\s*"
           r"(?P<v>" + _NUM_CONSELHO + r"))(?![\w])", 0.9, ignorar_caixa=False, grupo="v", nome="registro:sigla-numero"),
    # Em minúsculas ("oab/sp 123456", "crm-df 12345"), só com a UF e um número de três dígitos ou mais.
    Padrao("REGISTRO_PROFISSIONAL",
           _NAO_ATO_CONSELHO + r"\b(?:oab|crm|cro|crp|coren|crea|cau|crf|crn|crefito|crmv|crc|cress|cref|crq|creci)\s*[-/]\s*"
           r"[a-z]{2}\b\s*(?:sob\s+o\s+)?" + _NUM + r"[:\-]?\s*(?P<v>(?:\d{1,3}(?:\.\d{3})+|\d{3,})"
           r"(?:\s*[-/]\s*[a-z0-9]{1,2}\b)?)", 0.9, grupo="v", nome="registro:minusculas"),
    Padrao("REGISTRO_PROFISSIONAL",
           r"(?P<v>\b\d{1,3}(?:\.?\d{3})*)\s*[-/]?\s*(?:OAB|CRM|CREA|CRO|CRP|COREN|CAU)\s*[-/]\s*[A-Z]{2}\b", 0.9,
           ignorar_caixa=False, grupo="v", nome="registro:numero-sigla"),
    # ---------------- Data de nascimento: só a data precedida de expressão de nascimento; datas
    # isoladas são frequentes em documentos públicos e não são dado pessoal por si. Formatos: numérico
    # ("12/03/1987", "12.03.87", "1987-03-12", "1987.03.12", "12 03 1987"), com o mês em algarismos
    # romanos ("12/III/1987") ou abreviado ("12/mar/1987"), por extenso ("1º de março de 1987", "12 de
    # mar. de 1987", "12 de marzo de 1987", "12 marzo 1987"), a fórmula de registro civil ("aos 12 dias
    # do mês de março de 1987") e a data toda por extenso dos proclamas e assentos. As expressões de
    # nascimento incluem as de documentos de estrangeiros ("nacida el", "nato a … il", "née le"); "nasceu"
    # com sujeito que é programa, entidade ou lugar indica data de criação. A idade da pessoa é
    # reconhecida em :mod:`themis_lgpd.reconhecedores.pessoais`.
    Padrao("DATA_NASCIMENTO",
           r"(?:\bnascid[oa]s?|\bnascimento|\bnasc\b\.?|\bD\.?N\.?(?=\s*[:\-]|\s+\d)|\bdata de nasc\.?|"
           r"\bnasce(?:u|ram)\b(?<!" + NASCEU_SEM_PESSOA + r"nasce(?:u|ram))|\bnasci|"
           r"\bnaci|\bnascida|\bnascit[ao]\b|\bnat[oa]\b(?=[^\d\n]{1,30}?\bil\s+\d)|\bn[ée]e?\s+le\b|"
           r"\banivers[áa]rio|\bniver|\bdt\.?\s*nasc\.?)"
           r"[^\d\n]{0,30}?(?P<v>\d{1,2}\s*[/.\-]\s*(?:\d{1,2}|" + MES_ROMANO + r")\s*[/.\-]\s*(?:19|20)?\d{2}(?!\d)|"
           r"(?:19|20)\d{2}[-./]\d{2}[-./]\d{2}(?!\d)|\d{2}\s\d{2}\s(?:19|20)\d{2}(?!\d)|"
           r"\d{1,2}[/.\-\s](?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[a-zç]*\.?[/.\-\s](?:19|20)?\d{2}(?!\d)|"
           r"\d{1,2}[º°]?\s+(?:dias\s+do\s+m[êe]s\s+)?(?:de\s+)?" + MESES + r"\.?\s+(?:(?:do\s+ano\s+)?de\s+|del\s+)?\d{4}|" +
           DATA_POR_EXTENSO + r")", 0.9, camada=CONTEXTUAL, grupo="v"),
    # Só o ano, logo após "nascido em" ou "ano de nascimento" (no singular: "nascidos em 2023" é
    # contagem de registros), inclusive o ano presumido de quem não tem registro.
    Padrao("DATA_NASCIMENTO",
           r"(?:\bnascid[oa]\s+em|\bano\s+de\s+nascimento(?:\s+(?:presumido|prov[áa]vel|declarado|informado|"
           r"aproximado|estimado))?\s*[:\-]?)\s*(?P<v>(?:19|20)\d{2})(?![\d/.\-])",
           0.85, camada=CONTEXTUAL, grupo="v", nome="nascimento:ano"),
    # ---------------- Identificadores de cliente ou contribuinte (água, energia, IPTU, inscrições):
    # número com dígito após hífen, perto de uma expressão que indica o cadastro.
    Padrao("DOCUMENTO", ANTES_NUM + r"\d{3,12}-[\dXx]" + DEPOIS_NUM, 0.8,
           contexto=(r"unidades?\s+consumidoras?", r"inscri[çc](?:[ãa]o|[õo]es)", r"hidr[ôo]metros?",
                     r"conta[\s-]contrato", r"c[óo]digo\s+do\s+cliente", r"instala[çc][ãa]o", r"matr[íi]culas?",
                     r"cadastro", r"contratos?", r"im[óo]vel", r"iptu", r"cliente", r"benef[íi]cio"),
           contexto_obrigatorio=True, janela=50, nome="documento:cliente"),
    # ---------------- Qualquer número após palavra que designa documento (falhar fechado): cobre
    # documentos de estrangeiros (RNE, RNM, CRNM e o documento provisório, DPRNM), inscrições estaduais
    # e municipais e registros. O RNE e o RNM têm uma letra, seis dígitos e o dígito verificador, que
    # pode ser letra ("V123456-K"); o dígito "X" também ocorre no RG ("12.345.678-X"). Uma data após
    # "registro" ("Data do registro: 12/05/2025") é a data do próprio ato, não um número de documento.
    Padrao("DOCUMENTO",
           r"(?:\bdocumento|\binscri[çc][ãa]o(?: estadual| municipal)?|\bRNE|\bRNM|\bCRNM|\bDPRNM|\bNIRF|\bCAEPF|"
           r"\bregistro(?: civil)?)\s*(?:de identifica[çc][ãa]o\s*)?" + _SEP + _NUM + _SEP +
           r"(?P<v>(?:[A-Z]{0,3}\d[\d.\-/]{5,20}\d|(?-i:[A-Z]{1,3})\d{5,6})(?:-(?-i:[0-9A-Z])(?![\w])|-x(?![\w]))?)",
           0.75, camada=CONTEXTUAL, grupo="v", validador=lambda valor: not _DATA.fullmatch(valor),
           nome="documento:contexto"),
]


def _cpf_mascarado(valor: str) -> bool:
    """CPF com ao menos um grupo mascarado e ao menos um grupo de dígitos visível."""
    grupos = [g.strip() for g in re.split(r"[.\-]", valor)]
    return any(g.isdigit() for g in grupos) and not all(g.isdigit() for g in grupos)


def _ano(valor: str) -> bool:
    """Indica se ``valor`` é só um ano (1900 a 2099), que não é número de documento."""
    return bool(re.fullmatch(r"(?:19|20)\d{2}", valor))


def _assento(valor: str) -> bool:
    """Citação de assento com ao menos um livro ou uma folha (ver :data:`_C_LIVRO` e :data:`_C_FOLHA`)."""
    return bool(re.search(r"(?i)\b(?:livro|liv\.|tomo|libro|registre|folhas?|fls?\b|folio|f[óo]lio|foja|feuillet)",
                          valor))


def _numero_de_registro(valor: str) -> bool:
    """Número com forma de registro: ao menos quatro dígitos, sem ser ano, data ou período ("2023/2024")."""
    if sum(c.isdigit() for c in valor) < 4 or _ano(valor):
        return False
    return not re.fullmatch(r"\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?|(?:19|20)\d{2}[/\-](?:19|20)?\d{2}", valor)


#: Cabeçalhos de coluna que designam identificadores de pessoa e o tipo atribuído às células da
#: coluna. O cabeçalho precisa ocupar a célula inteira ("MATRÍCULA", "SIAPE", "COREN-SP", "Nº de
#: inscrição"); os tipos são os deste módulo. O auto de infração de trânsito (AIT) de cada
#: proprietário notificado também é número de procedimento sobre a pessoa.
_COLUNAS: list[tuple[str, str]] = [
    ("CPF", r"cpf"),
    ("RG", r"rg|identidade|c[ée]dula\s+de\s+identidade"),
    ("CNH", r"cnh"),
    ("PIS", r"pis(?:/pasep)?|pasep|nis|nit"),
    ("CNS", r"cns|cart[ãa]o\s+(?:do\s+)?sus"),
    ("TITULO_ELEITOR", r"t[íi]tulo(?:\s+de)?\s+eleitor(?:al)?"),
    ("BENEFICIO", r"nb|benef[íi]cio"),
    ("MATRICULA", r"matr[íi]cula(?:\s+(?:funcional|siape|masp|do\s+servidor|da\s+servidora))?|matr?\.?|siape|masp|"
                  r"r\.?f\.?|id\.?\s*funcional|(?:registro|identidade|n[úu]mero|n[º°]\.?)\s+funcional"),
    ("REGISTRO_PROFISSIONAL", r"(?:oab|crm|cro|crp|coren|crea|cau|crf|crn|crefito|crmv|crc|cress|cref|crfa|crq|creci|"
                              r"rqe)(?:\s*[-/]\s*" + _UF + r")?|registro\s+(?:profissional|no\s+conselho|de\s+classe)"),
    ("REGISTRO_SAUDE", r"prontu[áa]rio"),
    ("DOCUMENTO", r"inscri[çc][ãa]o(?:\s+(?:municipal|estadual|imobili[áa]ria))?|protocolo|requerimento|ait"),
]
#: Indicação de número que pode acompanhar o cabeçalho ("Nº de inscrição", "Matrícula nº").
_NUM_COLUNA = r"(?:n[º°o]\.?|n\.|n[úu]mero)"


def _cabecalhos(colunas: list[tuple[str, str]]) -> list[tuple[str, re.Pattern]]:
    """Expressões dos cabeçalhos, com a indicação de número opcional antes ou depois."""
    return [(tipo, re.compile(r"(?:" + _NUM_COLUNA + r"\s*(?:d[eoa]\s+)?)?(?:" + expr + r")(?:\s*" + _NUM_COLUNA +
                              r")?", re.IGNORECASE)) for tipo, expr in colunas]


_CABECALHOS = _cabecalhos(_COLUNAS)
#: Valor de uma célula com forma de identificador: dígitos, separadores e siglas em maiúsculas, ou
#: um CPF mascarado; ao menos quatro dígitos.
_CELULA_ID = re.compile(r"(?=(?:[^\d]*\d){4})(?:(?-i:[A-Z]{1,6})[\s\-]?)?[\d*Xx•#][\d*Xx•#.\-/ ]{2,22}"
                        r"(?:[\s\-/]?(?-i:[A-Z]{1,4}))?")
#: Formas que ocupam colunas de tabelas sem ser identificadores: datas, horas e valores monetários.
_CELULA_NAO_ID = re.compile(r"\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{1,2}:\d{2}|.*,\d{2}|(?:19|20)\d{2}")
#: Linha de pessoa jurídica numa tabela de pessoas ("TRANSPORTADORA X LTDA"): os números da linha não
#: são de pessoa natural.
_LINHA_PJ = re.compile(r"\b(?:LTDA|EIRELI|EPP|S\.?/?A|CNPJ)\b\.?", re.IGNORECASE)
#: Célula de tabela alinhada por espaços: palavras separadas por um espaço; as células são separadas
#: por dois ou mais.
_CELULA_ALINHADA = re.compile(r"\S+(?: \S+)*")
#: Cabeçalho numérico de colunas de dias, comum em escalas ("01 02 03 … 31").
_DIAS = re.compile(r"\d{1,2}(?: \d{1,2})+")
#: Complemento numérico separado por um espaço dentro da mesma célula ("013 524608-3").
_COMPLEMENTO = re.compile(r" [\d.\-/]*\d[\d.\-/]*(?=\s|$)")


class ColunasIdentificadoras:
    """Identificadores em colunas de tabelas, reconhecidos pelo cabeçalho da coluna.

    Anexos de portarias, editais de resultado, escalas e relações de beneficiários listam pessoas em
    tabelas ("NOME | MATRÍCULA | LOTAÇÃO", "SIAPE | SERVIDOR | FUNÇÃO"): o número da célula não traz a
    palavra-chave ao lado, que está só no cabeçalho. São reconhecidas tabelas com separadores de
    coluna (barra vertical, tabulação ou ponto e vírgula, como nas planilhas exportadas em CSV) e
    tabelas alinhadas por espaços, como as que a extração de texto de PDF produz.

    Com separadores, uma linha sem dígitos em que uma célula inteira designa um documento é tomada
    como cabeçalho; nas linhas seguintes com o mesmo número de colunas, a célula dessa coluna é
    reconhecida quando tem forma de identificador (ver :data:`_CELULA_ID`). Linhas quebradas pela
    extração do texto ("FULANO DE | TAL | 1234567") são unidas quando as duas partes somam o número
    de colunas do cabeçalho.

    Alinhada por espaços, a tabela tem um cabeçalho com ao menos três células separadas por dois ou
    mais espaços, curtas e sem dígitos (salvo a numeração de dias de uma escala); a coluna do
    documento pode ser a célula inteira ou uma palavra dela ("CLASS. INSCRIÇÃO"). Nas linhas
    seguintes, até uma linha de texto corrido ou duas linhas em branco, é reconhecido o valor que
    começa sob o cabeçalho da coluna; as linhas de pessoa jurídica (com "LTDA", "S/A", CNPJ) são
    ignoradas.

    Os tipos produzidos são os dos cabeçalhos; o objeto pode integrar uma lista de
    :class:`~themis_lgpd.reconhecedores.base.Padrao`.

    Args:
        colunas: Tipo e expressão de cada cabeçalho reconhecido; padrão, :data:`_COLUNAS`.
        tipo: Tipo que representa o reconhecedor na lista de padrões.
        nome: Origem atribuída aos achados.
    """

    #: Linhas sem separador de coluna toleradas dentro de uma tabela (nomes quebrados em duas linhas).
    TOLERANCIA = 2
    #: Distância máxima, em caracteres, entre o início do valor e o início do cabeçalho da coluna.
    DESVIO = 2

    def __init__(self, colunas: list[tuple[str, str]] | None = None, tipo: str = "DOCUMENTO",
                 nome: str = "tabela:coluna"):
        self.tipo, self.nome = tipo, nome
        self._expr = _CABECALHOS if colunas is None else _cabecalhos(colunas)

    def _tipo_cabecalho(self, texto: str, a: int, b: int) -> str | None:
        """Tipo do cabeçalho que ocupa ``texto[a:b]`` inteiro, ou ``None``."""
        for tipo, expr in self._expr:
            if expr.fullmatch(texto, a, b):
                return tipo
        return None

    @staticmethod
    def _celulas(texto: str, ini: int, fim: int, sep: str) -> list[tuple[int, int]]:
        """Posições das células de uma linha, sem os espaços das bordas; bordas vazias são descartadas."""
        celulas, a = [], ini
        for k in range(ini, fim + 1):
            if k == fim or texto[k] == sep:
                x, y = a, k
                while x < y and texto[x].isspace():
                    x += 1
                while y > x and texto[y - 1].isspace():
                    y -= 1
                celulas.append((x, y))
                a = k + 1
        if celulas and celulas[0][0] == celulas[0][1]:
            celulas.pop(0)
        if celulas and celulas[-1][0] == celulas[-1][1]:
            celulas.pop()
        return celulas

    def _colunas(self, texto: str, celulas: list[tuple[int, int]]) -> dict[int, str]:
        """Colunas de identificador num cabeçalho, com o tipo de cada uma; vazio se não for cabeçalho."""
        if len(celulas) < 2 or any(c.isdigit() for a, b in celulas for c in texto[a:b]):
            return {}
        colunas = {}
        for i, (a, b) in enumerate(celulas):
            tipo = self._tipo_cabecalho(texto, a, b)
            if tipo:
                colunas[i] = tipo
        return colunas if len(colunas) < len(celulas) else {}

    def _separadas(self, texto: str, sep: str) -> list[Deteccao]:
        """Achados nas tabelas com separador de coluna ``sep``."""
        achados: list[Deteccao] = []
        colunas: dict[int, str] = {}
        largura = fora = 0
        pendente: list[tuple[int, int]] | None = None
        fim = -1
        for conteudo in texto.split("\n"):
            ini, fim = fim + 1, fim + 1 + len(conteudo)
            if sep not in conteudo:
                fora += 1
                if fora > self.TOLERANCIA:
                    colunas, pendente = {}, None
                continue
            fora = 0
            celulas = self._celulas(texto, ini, fim, sep)
            novas = self._colunas(texto, celulas)
            if novas:
                colunas, largura, pendente = novas, len(celulas), None
                continue
            if not colunas:
                continue
            if len(celulas) < largura:
                if pendente is None or len(pendente) + len(celulas) - 1 != largura:
                    pendente = celulas
                    continue
                celulas = pendente[:-1] + [(pendente[-1][0], celulas[0][1])] + celulas[1:]
            pendente = None
            if len(celulas) != largura:
                continue
            for i, tipo in colunas.items():
                a, b = celulas[i]
                valor = texto[a:b]
                if _CELULA_ID.fullmatch(valor) and not _CELULA_NAO_ID.fullmatch(valor):
                    achados.append(Deteccao(a, b, tipo, 0.85, self.nome, CONTEXTUAL, None, True))
        return achados

    def _cabecalho_alinhado(self, linha: str) -> list[tuple[int, int, str]]:
        """Colunas de identificador de um cabeçalho alinhado por espaços: início e fim na linha e tipo."""
        celulas = [(m.start(), m.end()) for m in _CELULA_ALINHADA.finditer(linha)]
        if len(celulas) < 3:
            return []
        colunas = []
        for a, b in celulas:
            celula = linha[a:b]
            if any(c.isdigit() for c in celula):
                if _DIAS.fullmatch(celula):
                    continue
                return []
            palavras = [(m.start() + a, m.end() + a) for m in re.finditer(r"\S+", celula)]
            if b - a > 40 or len(palavras) > 4:
                return []
            # A célula inteira ou uma sequência de até três palavras dela.
            trechos = [(0, len(palavras) - 1)] + [(p, q) for p in range(len(palavras))
                                                  for q in range(p, min(len(palavras), p + 3))]
            for p, q in trechos:
                tipo = self._tipo_cabecalho(linha, palavras[p][0], palavras[q][1])
                if tipo:
                    colunas.append((palavras[p][0], palavras[q][1], tipo))
                    break
        return colunas if 0 < len(colunas) < len(celulas) else []

    def _alinhadas(self, texto: str) -> list[Deteccao]:
        """Achados nas tabelas alinhadas por espaços."""
        achados: list[Deteccao] = []
        colunas: list[tuple[int, int, str]] = []
        brancas = 0
        fim = -1
        for linha in texto.split("\n"):
            ini, fim = fim + 1, fim + 1 + len(linha)
            if not linha.strip():
                brancas += 1
                if brancas >= 2:
                    colunas = []
                continue
            brancas = 0
            if "  " not in linha.strip() or "|" in linha or "\t" in linha:
                # Linha de texto corrido encerra a tabela; linhas curtas (continuação de célula) não.
                if len(linha.strip()) >= 60:
                    colunas = []
                continue
            novas = self._cabecalho_alinhado(linha)
            if novas:
                colunas = novas
                continue
            if not colunas or _LINHA_PJ.search(linha):
                continue
            for a, b, tipo in colunas:
                for m in re.finditer(r"\S+", linha):
                    if m.start() >= b:
                        break
                    if m.start() < a - self.DESVIO:
                        continue
                    x, y = m.span()
                    comp = _COMPLEMENTO.match(linha, y)
                    if comp and _CELULA_ID.fullmatch(linha, x, comp.end()):
                        y = comp.end()
                    valor = linha[x:y]
                    if _CELULA_ID.fullmatch(valor) and not _CELULA_NAO_ID.fullmatch(valor):
                        achados.append(Deteccao(ini + x, ini + y, tipo, 0.85, self.nome, CONTEXTUAL, None, True))
                    break
        return achados

    def detectar(self, texto: str) -> list[Deteccao]:
        """Achados nas colunas de identificador das tabelas do texto."""
        achados: list[Deteccao] = []
        for sep in ("|", "\t", ";"):
            if sep in texto:
                achados.extend(self._separadas(texto, sep))
        if "   " in texto:
            achados.extend(self._alinhadas(texto))
        return achados


PADROES.append(ColunasIdentificadoras())
