"""Reconhecedores de endereço, CEP e localidade, com cobertura nacional.

Formatos de endereço reconhecidos:

* logradouro com nome e número, inclusive abreviado ("Av.", "Trav.", "Pça.", "Lgo.") e com número
  de milhar ("1.234"), complementos ("apto 501", "Edifício Toronto, sala 202") e cauda com bairro,
  cidade, UF e CEP;
* logradouro numerado ou com letra ("Rua 15", "Rua A", "Avenida T-9"), comum em Goiânia, Palmas,
  Manaus e em conjuntos habitacionais de todo o país, seguido de número ou de quadra e lote;
* localidades rurais e regionais, que dispensam número: sítio, fazenda, chácara, povoado,
  assentamento, aldeia, gleba, ramal, linha, loteamento, vicinal e semelhantes;
* rodovias federais e estaduais das 27 UFs com quilômetro ("PE-060, km 10");
* endereçamento de Brasília e das regiões administrativas do DF, baseado em siglas de setor e em
  quadra, conjunto e casa ("SQS 308 Bloco C Apto 602", "QNM 12 Conjunto B Casa 4").

O nome de um município (lista oficial do IBGE, em ``dados/municipios.txt``) ou de uma região
administrativa do DF é um quase-identificador (``LOCALIDADE``): por si só não identifica ninguém e,
em geral, é apenas sinalizado. Quando aparece como local de residência ("moro em Campinas"), passa a
ser tratado como endereço.
"""

from __future__ import annotations

from functools import cache
from importlib import resources

import regex as re

from ..texto import dobrar
from .base import ANTES_NUM, CONTEXTUAL, DEPOIS_NUM, Deteccao, Padrao, ReconhecedorPadroes
from .institucional import documento_do_orgao

#: Siglas das 27 unidades da federação.
UFS = ("AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
       "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO")
_UF = "(?:" + "|".join(UFS) + ")"
#: Nomes dos estados, do mais longo ao mais curto ("Mato Grosso do Sul" antes de "Mato Grosso").
ESTADOS = ("Rio Grande do Norte", "Rio Grande do Sul", "Mato Grosso do Sul", "Espírito Santo", "Rio de Janeiro",
           "Santa Catarina", "Distrito Federal", "Minas Gerais", "Mato Grosso", "Pernambuco", "São Paulo", "Tocantins",
           "Rondônia", "Maranhão", "Amazonas", "Alagoas", "Paraíba", "Roraima", "Sergipe", "Paraná", "Piauí", "Amapá",
           "Bahia", "Ceará", "Goiás", "Acre", "Pará")

#: Expressões que indicam local de residência; elevam a confiança dos endereços.
CTX_RESIDENCIA = (
    r"moro", r"resido", r"residente", r"resid[êe]ncia", r"endere[çc]o", r"domic[íi]li\w*", r"minha casa",
    r"mora(?:mos)?", r"morador[a]?", r"reside", r"residimos", r"im[óo]vel", r"localizad[oa]", r"pernoit\w*",
)

#: Rótulo de um componente de endereço cujo valor pode ser número ou letra (conjunto, casa, lote,
#: bloco, apartamento, quadra…).
_ROTULO_COMPONENTE = (
    r"\b(?:conjunto|conj\.?|cj\.?|casa|cs\.?|lote(?:\s+rural)?|lt\.?|bloco|bl\.?|apartamento|apto\.?|ap\.?|sala|loja|"
    r"quadra|qd\.?|rua|alameda|al\.|avenida|av\.|travessa|ch[áa]cara|ch\.?|m[óo]dulo|proje[çc][ãa]o|"
    r"andar|km|torre|unidade(?:\s+habitacional)?|trecho|gleba|setor|barraco|barraca|kitnet|quitinete|c[ôo]modo|"
    r"beco|quarto)"
)
#: Rótulo cujo valor só pode ser número: "nº", "número" e rodovia ("BR-020", "GO-060"). Exigir o
#: número impede que "mas" seja lido como "MA" + "s" ou "nos" como "nº" + "s".
_ROTULO_NUMERICO = r"(?:\bn[º°o]\.?|\bn[úu]mero|\b(?-i:BR|" + "|".join(UFS) + r")-?)"
_MESES = r"(?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b"
#: O dia de um logradouro com nome de data ("rua 13 de maio") não é número nem valor de componente.
_NAO_DATA = rf"(?!\s+de\s+{_MESES})"
#: Valor de um componente: número ("12", "602-A", "1.234") ou letra isolada ("B"). Nunca uma palavra
#: — o que impede que "ch" + "ão" de "chão" seja lido como "chácara ão".
_VALOR_COMP = r"(?:\d{1,3}(?:\.\d{3})+|\d[\dA-Z\-/]{0,5}|[A-Z](?:-?\d{1,4})?)(?![\wÀ-ú])" + _NAO_DATA
_VALOR_NUMERICO = r"(?:\d{1,3}(?:\.\d{3})+|\d[\dA-Z\-/]{0,5})(?![\wÀ-ú])"
#: Complemento sem valor numérico que localiza a unidade dentro do imóvel ("fundos", "sobreloja",
#: "2º andar"), a casa pelo número precedido de descrição ("casa sobre palafita nº 14") e a margem do rio
#: em comunidades ribeirinhas ("margem esquerda do rio Ariramba").
_COMPLEMENTO_ATIPICO = (r"\b(?:fundos|sobreloja|t[ée]rreo|subsolo|cobertura|ed[íi]cula)\b|\b\d{1,2}\s?[ºª°o]?\s*andar\b|"
                        r"\bcasa\s+(?:[a-zà-ú]+\s+){0,3}n[º°o]\.?\s*\d{1,5}\b|"
                        r"\bmargem\s+(?:esquerda|direita)(?:\s+d[oa]\s+(?:rio|igarap[ée]|c[óo]rrego|ribeir[ãa]o|lago|ba[íi]a|"
                        r"furo|paran[áa])\s+[\wÀ-ú'’]+(?:\s+(?-i:[A-ZÀ-Ú])[\wÀ-ú'’]+){0,2})?")
#: Componente de endereço com o seu valor ("casa 4", "Bloco C", "nº 230", "GO-060") ou "s/n".
_COMPONENTE = (rf"(?:{_ROTULO_COMPONENTE}\s*{_VALOR_COMP}|{_ROTULO_NUMERICO}\s*{_VALOR_NUMERICO}|(?<![\w/])s/n(?![\w/])|"
               rf"\bcasa\s+sem\s+n[úu]mero\b|{_COMPLEMENTO_ATIPICO})")
#: Localidade rural que integra o endereço depois da propriedade ou da linha ("Sítio Bela Vista, Córrego
#: Fundo", "Linha 18, lote 31, Gleba Santa Cruz").
_LOCALIDADE_DO_ENDERECO = r"(?:c[óo]rrego|ribeir[ãa]o|igarap[ée]|ramal|travess[ãa]o|gleba|vicinal|n[úu]cleo\s+rural)"
#: Componente cujo valor é um nome próprio ("Edifício Toronto", "Residencial Bela Vista"), a rodovia
#: em que fica o quilômetro ("km 12 da Rodovia Transamazônica", "km 8 da Rodovia LMG-800") ou a
#: localidade rural que integra o endereço. O nome do edifício admite conectores estrangeiros
#: ("Edifício Mar di Roma", "Residencial Vila del Sol").
_COMPONENTE_NOMEADO = (r"\b(?:edif[íi]cio|ed\.|residencial|condom[íi]nio|bloco)\s+(?-i:[A-ZÀ-Ú][\wÀ-ú'’]+"
                       r"(?:\s+(?:(?:d[aeoi]s?|del(?:la)?|du|von|van)\s+)?[A-ZÀ-Ú][\wÀ-ú'’]+){0,3})"
                       r"|\b(?:rodovia|estrada)\s+(?-i:[A-Z]{2,4}-?\d{2,4}(?![\w])|[A-ZÀ-Ú][\wÀ-ú'’]+"
                       r"(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ú][\wÀ-ú'’]+){0,3})"
                       rf"|\b{_LOCALIDADE_DO_ENDERECO}\s+(?-i:(?:d[aeo]s?\s+)?[A-ZÀ-Ú][\wÀ-ú'’]+"
                       r"(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ú][\wÀ-ú'’]+){0,4})")
#: Sequência de até oito componentes após o início do endereço, separados por vírgula, hífen ou
#: preposição ("Lote 12 da DF-330", "km 42 da Rodovia BR-364", "casa 3 no Bloco B").
_COMPONENTES = rf"(?:\s*[,\-–]?\s*(?:(?:n[oa]|d[ao])\s+)?(?:{_COMPONENTE}|{_COMPONENTE_NOMEADO})){{0,8}}"
#: Componente que delimita o lote ou a unidade residencial ("Lote 12", "Chácara 15", "Casa 8").
_COMPONENTE_LOTE = rf"\b(?:lote|lt\.?|ch[áa]cara|casa|cs\.?|conjunto|conj\.?|quadra|qd\.?)\s*{_VALOR_COMP}"
#: Nome do logradouro: não atravessa fim de frase; o ponto só é aceito após abreviações de títulos
#: ("Rua Dr. Fulano", "Av. Gov. Beltrano"), e a quebra de linha, só depois da sílaba separada por hífen
#: ("Rua Pedro Bor-" no fim da linha e "ges da Silva" na seguinte).
_NOME_LOGRADOURO = (r"(?:[^\n,;:()!?\d.|]|(?<=\b(?:Dr|Dra|Prof|Gov|Pres|Sen|Dep|Mal|Gal|Cel|Cap|Ten|Sto|Sta|Pe|Fr|D|S))\.|"
                    r"(?<=[A-Za-zÀ-ú]-[ \t]{0,2})\n(?=[a-zà-ú]))"
                    r"{2,60}?")
#: Casa de uso coletivo da comunidade ("casa de farinha", "casa de reza", "casa de apoio"), que não é a
#: moradia de uma família.
_CASA_COLETIVA = (r"(?!\s*,\s*casa\s+d[aeo]s?\s+(?:farinha|reza|apoio|sa[úu]de|cultura|mel|sementes|passagem|"
                  r"acolhimento|artesanato|ora[çc][ãa]o|mem[óo]ria|conselhos?|cidadania))")
#: Nome de logradouro que homenageia uma data ("15 de Novembro", "1º de Maio", "7 de Setembro").
_NOME_DATA = r"(?:[12]?\d|3[01])[º°]?\s+de\s+" + _MESES
#: Número do imóvel: com milhar ("1.234"), simples com letra ("230A") ou "s/n"; também como ponto de
#: referência ("altura do número 450"). O dia de um nome-data ("rua 13 de maio") não é número.
_NUMERO = (r"(?:(?:na\s+)?altura\s+do\s+)?(?:n[º°o]?\.?\s*|n[úu]mero\s*)?(?:\d{1,3}(?:\.\d{3})+|\d{1,6}[A-Za-z]?|s/?n)"
           r"(?![\w/])" + _NAO_DATA)
#: Cidade seguida de UF ("Joinville - SC", "Goiânia/GO", "Recife (PE)"). O pronome oblíquo colado ao
#: verbo ("…, encontra-se interditado", "reuniram-se") não é a sigla de Sergipe.
_CIDADE_UF = rf"[A-ZÀ-Ú][^\n,;.\d]{{1,35}}?\s*(?:[-/–,]\s*|\(\s*)(?!(?<=\w-)(?-i:se)\b){_UF}\)?(?![\w])"
#: Complementos opcionais do endereço: bairro (com ou sem a palavra "bairro", quando seguido de
#: cidade e UF), cidade e UF, CEP (", Bairro Vila Nova", ", Centro, Porto Alegre/RS",
#: ", Brasília/DF, CEP 70000-000").
_CAUDA = (
    r"(?:\s*,\s*(?:bairro|setor|jardim|vila|parque|residencial|condom[íi]nio)\s+[^\n,;.\d]{2,40})?"
    rf"(?:\s*,\s*[A-ZÀ-Ú][^\n,;.\d]{{1,30}}?(?=\s*,\s*{_CIDADE_UF}))?"
    rf"(?:\s*,\s*(?:(?:munic[íi]pio|cidade|zona\s+rural)\s+d[eo]\s+)?{_CIDADE_UF})?"
    r"(?:\s*,?\s*CEP\s*[:\-]?\s*\d{5}\s?-?\s?\d{3})?"
)
#: Tipos de logradouro urbano.
_LOGRADOURO = (r"(?:rua|r\.|avenida|av\.?|alameda|al\.|travessa|trav\.?|tv\.|rodovia|rod\.?|estrada|estr\.?|"
               r"pra[çc]a|p[çc]a\.?|largo|lgo\.?|viela|beco|servid[ãa]o|passagem|psg\.?|ladeira|vila|"
               r"conjunto habitacional|condom[íi]nio|setor habitacional|quadra|via|marginal|vicinal|passarela)")
#: Propriedades rurais, identificadas pelo nome, sem número: o nome designa o imóvel da família.
_PROPRIEDADE_RURAL = (r"(?:s[íi]tio|fazenda|ch[áa]cara|granja|est[âa]ncia|gleba|n[úu]cleo rural|"
                      r"col[ôo]nia(?: agr[íi]cola)?|vila rural|lote rural)")
#: Localidades coletivas (povoados, comunidades, assentamentos, estradas vicinais): também aparecem em
#: documentos de política pública, por isso só são endereço com expressão de residência por perto.
_LOCALIDADE_COLETIVA = (r"(?:povoado|(?:projeto\s+de\s+)?assentamento|aldeia|comunidade|quilombo|ramal|loteamento|"
                        r"ocupa[çc][ãa]o|favela|localidade|"
                        r"acampamento|distrito|ilha)")
#: Termos institucionais que, logo após "fazenda", "distrito" ou "comunidade", indicam órgão ou
#: conceito, não endereço ("Fazenda Pública", "Distrito Federal", "comunidade escolar"); depois de
#: "sítio", o patrimônio histórico ou natural e a página na internet ("Sítio Histórico", "Sítio Eletrônico").
_NAO_LOCALIDADE = (r"(?!(?:P[úu]blica|Nacional|Estadual|Municipal|Federal|Escolar|Acad[êe]mica|Cient[íi]fica|"
                   r"Internacional|Europeia|LGBT|Terap[êe]utica|Sanit[áa]ria|Policial|Penal|Hist[óo]ric[oa]|"
                   r"Arqueol[óo]gic[oa]|Paleontol[óo]gic[oa]|Eletr[ôo]nic[oa]|Oficial|Institucional)\b)"
                   # "Fazenda do Distrito Federal", "Fazenda do Estado de Goiás", "Fazenda da Bahia": o órgão.
                   r"(?!(?:d[aeo]s?\s+)?(?:Estado|Distrito\s+Federal|Munic[íi]pio|Uni[ãa]o|Rep[úu]blica|Prefeitura|"
                   r"Governo|Secretaria|Minist[ée]rio|" + "|".join(ESTADOS) + r")\b)")
#: Nome próprio de propriedade ou localidade: até cinco palavras iniciadas por maiúscula, com
#: conectores e hífen ("Santa Rita", "Boa Esperança", "do Cupuaçu", "Pau-Brasil").
_NOME_PROPRIO = (r"(?-i:(?:d[aeo]s?\s+)?[A-ZÀ-Ú][\wÀ-ú'’]+(?:-[A-Za-zÀ-ú][\wÀ-ú'’]*)*"
                 r"(?:\s+(?:d[aeo]s?\s+|e\s+)?[A-ZÀ-Ú0-9][\wÀ-ú'’]*(?:-[A-Za-zÀ-ú][\wÀ-ú'’]*)*){0,4})")

#: Siglas de setores de Brasília e das regiões administrativas (SQS, SHIS, QNM, EQN…).
_SIGLAS_DF = (
    r"SQ[NSWE]|SQSW|SQNW|SHI[NS]|SHCN|SHCS|SHCSW|SHCES|SHA|SHTN|SHTQ|SMPW|SMLN|SMDB|SMAS|SHVP|SHDB|SHN|SHS|"
    r"SCLN|SCLS|SCRN|SCRS|SEPN|SEPS|SGAN|SGAS|SHLN|SHLS|SRTVN|SRTVS|SAAN|SOF[NS]?|SCIA|QN[A-R]|QS|QR|QE|QI|QL|"
    r"QSE|QSD|QSF|EQN|EQS|EQNM|CLN|CLS|CLSW|CRS|CRN|AE|QMS|QNM|QNN|QNL|QNO|QNP|QNQ|QNR|QR|SHD[FSN]|SHIGS|SHCGN"
)

#: Regras de CEP e endereço.
PADROES: list[Padrao] = [
    # CEP com hífen; sem a palavra "CEP", o formato ainda é distintivo o bastante.
    Padrao("CEP", ANTES_NUM + r"\d{2}\.?\d{3}-\d{3}" + DEPOIS_NUM, 0.85, contexto=("cep",), nome="cep:hifen"),
    # Oito dígitos, com ou sem hífen, logo após a palavra "CEP".
    Padrao("CEP", r"\bCEP\s*[:\-]?\s*(?P<v>\d{5}\s?-?\s?\d{3})(?!\d)", 0.95, camada=CONTEXTUAL, grupo="v",
           nome="cep:contexto"),
    # Tipo de logradouro, nome, número ou componente, complementos e cauda.
    Padrao("ENDERECO",
           r"\b" + _LOGRADOURO + r"\s+(?:" + _NOME_DATA + r"|" + _NOME_LOGRADOURO
           # "Rua Projetada 4": o número integra o nome da via e não é o do imóvel.
           + r")\s*,?\s*(?:(?<!\bprojetad[ao]\s{1,3})" + _NUMERO + r"|" + _COMPONENTE + r")" + _COMPONENTES
           + _CAUDA, 0.85, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:logradouro"),
    # Logradouro numerado ou com letra ("Rua 15, nº 230", "Rua A, 15", "Avenida T-9, 1220", "Rua 04,
    # Lote 15"), seguido obrigatoriamente de número ou componente.
    # Em Brasília, a via pode trazer o setor cardeal ("Avenida L2 Norte, quadra 605", "W3 Sul").
    Padrao("ENDERECO",
           r"\b(?:rua|r\.|avenida|av\.?|alameda|travessa|trav\.?|tv\.)\s+(?:projetad[ao]\s+)?(?:\d{1,4}[A-Z]?|[A-Z]{1,2}(?:-?\d{1,4})?|"
           r"[IVXL]{1,6})(?![\wÀ-ú])(?:\s+(?:norte|sul|leste|oeste)\b)?\s*,?\s*(?:" + _NUMERO + r"|" + _COMPONENTE + r")"
           + _COMPONENTES + _CAUDA, 0.85, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:numerado"),
    # Logradouro sem número, quando há expressão de residência ("moro na Rua XV de Novembro, no
    # centro de Curitiba").
    Padrao("ENDERECO",
           r"\b(?:moro|resido|reside|mora|moramos|residente|domiciliad[oa]|morador(?:a)?)\s+(?:em|n[oa]s?|à|a)\s+"
           r"(?P<v>" + _LOGRADOURO + r"\s+(?:" + _NOME_DATA + r"|" + _NOME_PROPRIO + r")" + _COMPONENTES + _CAUDA
           + r")", 0.85, camada=CONTEXTUAL,
           grupo="v", nome="endereco:residencia"),
    # Propriedade rural pelo nome, sem número ("Sítio Boa Esperança, zona rural de Caruaru/PE",
    # "Fazenda Santa Rita, município de Sorriso/MT").
    Padrao("ENDERECO",
           r"\b" + _PROPRIEDADE_RURAL + r"\s+" + _NAO_LOCALIDADE + _NOME_PROPRIO + _COMPONENTES + _CAUDA,
           0.8, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:rural"),
    # A mesma propriedade escrita em minúsculas, desde que seguida do lote ("chácara santa luzia, lote 14").
    Padrao("ENDERECO",
           r"\b" + _PROPRIEDADE_RURAL + r"\s+" + _NAO_LOCALIDADE
           + r"(?-i:[a-zà-ú][\wà-ú'’]+(?:\s+(?:d[aeo]s?\s+)?[a-zà-ú][\wà-ú'’]+){0,3})\s*,\s*" + _COMPONENTE_LOTE
           + _COMPONENTES + _CAUDA, 0.8, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:rural-lote"),
    # Localidade coletiva com expressão de residência ("residente no Povoado Bela Vista", "moro no
    # Assentamento Santa Rita, lote 12", "Ramal do Cupuaçu, km 8").
    Padrao("ENDERECO",
           r"\b" + _LOCALIDADE_COLETIVA + r"\s+" + _NAO_LOCALIDADE + _NOME_PROPRIO + _COMPONENTES + _CAUDA,
           0.8, contexto=CTX_RESIDENCIA, contexto_obrigatorio=True, janela=60, nome="endereco:localidade-rural"),
    # Localidade coletiva com o lote da família ("Assentamento Santa Rita, Lote 45, Gleba B"): o lote
    # individualiza o imóvel mesmo sem expressão de residência.
    Padrao("ENDERECO",
           r"\b" + _LOCALIDADE_COLETIVA + r"\s+" + _NAO_LOCALIDADE + _NOME_PROPRIO + r"\s*,?\s*" + _COMPONENTE_LOTE
           + _COMPONENTES + _CAUDA, 0.8, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:localidade-lote"),
    # Gleba ou trecho numerado com lote, chácara ou casa ("Gleba 04, Lote 12", "Trecho 3 Lote 450"). Sem
    # o lote, "trecho 2" e "gleba 4" designam áreas, comuns em textos de obras e regularização.
    Padrao("ENDERECO",
           r"\b(?:gleba|trecho)\s+[A-Z]?\d{1,4}[A-Z]?\s*,?\s*" + _COMPONENTE_LOTE + _COMPONENTES + _CAUDA,
           0.85, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:gleba"),
    # Setor nomeado seguido de quadra, lote ou conjunto, comum no DF, em Goiás e no Tocantins ("Setor de
    # Oficinas, Lote 12, Bloco B", "Setor Sul, Quadra 4"). O nome começa por maiúscula: "setor de RH" não é.
    Padrao("ENDERECO",
           r"\bsetor\s+(?-i:(?:d[aeo]s?\s+)?[A-ZÀ-Ú][\wÀ-ú'’]*(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ú][\wÀ-ú'’]*){0,3})\s*,?\s*"
           + _COMPONENTE_LOTE + _COMPONENTES + _CAUDA, 0.85, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:setor"),
    # Conjunto identificado por letra, seguido de casa ou lote ("Conjunto B, Casa 15").
    Padrao("ENDERECO",
           r"\b(?:conjunto|conj\.|cj\.)\s+(?-i:[A-Z])\s*,?\s*(?:casa|cs\.?|lote|lt\.?)\s*\d{1,4}[A-Z]?(?![\wÀ-ú])"
           + _COMPONENTES + _CAUDA, 0.85, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:conjunto"),
    # Linha e lote (Rondônia e Norte), travessão e vicinal com número ("Linha 7, Lote 7, Gleba 11").
    Padrao("ENDERECO",
           r"\b(?:linha|travess[ãa]o|vicinal|lote\s+rural)\s+[A-Z]?\d{1,4}[A-Z]?\s*,?\s*" + _COMPONENTE
           + _COMPONENTES + _CAUDA, 0.85, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:linha"),
    # Endereçamento do DF: até duas siglas de setor seguidas de sigla, quadra ou conjunto e número.
    # A confiança é ajustada pelo número de componentes (ver ReconhecedorEndereco).
    Padrao("ENDERECO",
           rf"\b(?:(?:{_SIGLAS_DF})\s+){{0,2}}(?:{_SIGLAS_DF}|quadra|qd\.?|q\.|conjunto|conj\.?|cj\.?)\s*\d{{1,4}}[A-Z]?"
           r"(?:\s+(?:sul|norte|leste|oeste))?\b" + _COMPONENTES + _CAUDA,
           0.6, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:df"),
    # Áreas rurais: rodovia federal ou estadual (27 UFs) e quilômetro, com chácara, sítio ou lote
    # ("DF-001, km 12, Chácara 5", "PE-060, km 10").
    Padrao("ENDERECO",
           r"\b(?:BR|" + "|".join(UFS) + r")[-\s]?\d{3}\s*,?\s*(?i:km)\s*\d{1,4}(?:[.,]\d)?"
           r"(?:\s*,\s*(?i:ch[áa]cara|s[íi]tio|fazenda|lote|n[úu]cleo|condom[íi]nio)[^\n,;]{0,40})*", 0.8,
           ignorar_caixa=False, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:rodovia"),
    Padrao("ENDERECO",
           r"\bkm\s*\d{1,4}(?:[.,]\d)?\s+d[ao]\s+(?:rodovia\s+)?(?-i:BR|" + "|".join(UFS) + r")[-\s]?\d{3}"
           r"(?:\s*[,\-–]\s*(?:ch[áa]cara|s[íi]tio|fazenda|lote|n[úu]cleo(?:\s+rural)?|condom[íi]nio)[^\n,;.]{0,40})*",
           0.8, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:km-rodovia"),
    # Linha, picada ou travessão com nome, comuns nas colônias do Sul, seguidos de "s/n", quilômetro, lote
    # ou número ("Linha Santo Expedito, s/n, km 4", "Picada Café, lote 12"). O nome começa por maiúscula e o
    # componente é obrigatório: "linha de crédito" e "linha do tempo" não são endereço.
    Padrao("ENDERECO",
           r"\b(?-i:Linha|LINHA|Picada|PICADA|Travess[ãa]o|TRAVESS[ÃA]O)\s+" + _NOME_PROPRIO
           + r"\s*,?\s*(?=s/n|km\s*\d|lote\s*\d|n[º°o]\.?\s*\d)" + _COMPONENTES + _CAUDA,
           0.85, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:linha-nomeada"),
    # Localidade coletiva seguida da casa da família, com ou sem a margem do rio ("localidade Barra Funda,
    # casa de taipa", "Comunidade Santo Antônio, margem direita do rio Ariramba, casa 8"): a casa
    # individualiza a moradia mesmo sem expressão de residência.
    Padrao("ENDERECO",
           r"\b" + _LOCALIDADE_COLETIVA + r"\s+" + _NAO_LOCALIDADE + _NOME_PROPRIO
           + r"(?:\s*,\s*margem\s+(?:esquerda|direita)[^\n,;.]{0,50})?(?=\s*,\s*(?:casa|barraco|barraca)\b)"
           + _CASA_COLETIVA + _COMPONENTES, 0.8, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:localidade-casa"),
    # Unidade de abrigo ou de conjunto habitacional ("unidade habitacional 108 da ala B", no abrigo):
    # exige menção ao acolhimento ou à residência.
    Padrao("ENDERECO",
           r"\bunidade\s+habitacional\s+\d{1,4}[A-Z]?(?:\s+(?:d[oa]|n[oa])\s+(?:setor|bloco|m[óo]dulo|ala|quadra)\s+"
           r"(?-i:[A-Z0-9]{1,3})\b)?",
           0.8, contexto=CTX_RESIDENCIA + (r"abrig\w*", r"acolhid[oa]s?", r"acolhimento"), contexto_obrigatorio=True,
           janela=120, nome="endereco:unidade-habitacional"),
    # Endereço no exterior, com o tipo de via em espanhol, francês ou italiano, seguido de número,
    # componente ou cruzamento ("Calle 47 con Carrera 3, casa nº 58", "Rue Capois, nº 17", "calle
    # principal, casa 45", "calle Sarmiento esquina Belgrano"). O cruzamento sem número exige expressão de
    # residência (ver ReconhecedorEndereco).
    Padrao("ENDERECO",
           r"\b(?:calles?|carrera|cra\.|jir[óo]n|pasaje|calzada|rue|ruelle|boulevard|chemin|strada|piazza|corso)\s+"
           r"(?:\d{1,4}[A-Z]?(?![\wÀ-ú])|(?-i:[A-ZÀ-Ú][\wÀ-ú'’]+(?:\s+(?:(?:d[aeoi]s?|del|de\s+la|du|le|la)\s+)?"
           r"[A-ZÀ-Ú][\wÀ-ú'’]+){0,3})|(?-i:[a-zà-ú]{3,}))"
           r"(?:\s+(?:con|esquina(?:\s+con)?|y|entre|et|e)\s+(?:(?:calle|carrera|cra\.|avenida|av\.|rue)\s+)?"
           r"(?:\d{1,4}[A-Z]?(?![\wÀ-ú])|(?-i:[A-ZÀ-Ú][\wÀ-ú'’]+(?:\s+[A-ZÀ-Ú][\wÀ-ú'’]+){0,2})))?"
           r"(?:\s*,?\s*(?:n[º°o]\.?\s*|#\s*)\d{1,5}(?:-\d{1,3})?(?![\w/]))?" + _COMPONENTES,
           0.8, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:exterior"),
    # Coordenadas geográficas da moradia, em graus, minutos e segundos ("1°12'05" S, 48°30'44" W") ou
    # decimais após "coordenadas" ou "GPS"; só com expressão de residência por perto, pois coordenadas de
    # obras e de equipamentos públicos são informação pública.
    Padrao("ENDERECO",
           r"(?<![\d.])\d{1,3}\s?°\s?\d{1,2}\s?['’′]\s?\d{1,2}(?:[.,]\d+)?\s?(?:\"|”|″|′′|''|’’)?\s?[NS]\b\s*[,;e]?\s*"
           r"\d{1,3}\s?°\s?\d{1,2}\s?['’′]\s?\d{1,2}(?:[.,]\d+)?\s?(?:\"|”|″|′′|''|’’)?\s?[WOLE]\b"
           r"|(?<=\b(?:coordenadas|gps|lat(?:itude)?)\b[^\n\d]{0,25})-?\d{1,2}[.,]\d{4,}\s*[,;/]\s*"
           r"(?:long(?:itude)?\s*:?\s*)?-?\d{1,3}[.,]\d{4,}",
           0.8, camada=CONTEXTUAL, contexto=CTX_RESIDENCIA + (r"casa", r"fam[íi]lia", r"lote", r"propriedade",
                                                           r"s[íi]tio", r"moradia"),
           contexto_obrigatorio=True, janela=150, nome="endereco:coordenadas"),
    # Ponto de pernoite de pessoa em situação de rua, até o fim da frase ("pernoita sob o Viaduto do Chá,
    # junto à pilastra norte", "dorme debaixo da marquise do mercado"). Só no singular: "pessoas
    # pernoitando na área" descreve o uso coletivo do espaço.
    Padrao("ENDERECO",
           r"\b(?:pernoit(?:a|ava|ou)|dorm(?:e|ia)(?=\s+(?:sob|embaixo|debaixo)\b))\s+"
           r"(?:sob|embaixo\s+d[oa]s?|debaixo\s+d[oa]s?|junto\s+(?:a|à|ao)|n[oa]s?|em|à|ao)\s+(?:(?:o|a|os|as|um|uma)\s+)?"
           r"(?P<v>[^\n.;]{3,140}?)"
           r"(?=\s*(?:[.;\n]|$)|,?\s+e\s+(?!(?:o|a|os|as|d[aeo]s?|n[aeo]s?|em|um|uma)\b)(?-i:[a-zà-ú]))",
           0.8, camada=CONTEXTUAL, grupo="v", nome="endereco:pernoite"),
]

#: Componente com valor, usado para medir quão completo é um endereço do DF.
_COMP_RE = re.compile(_COMPONENTE, re.IGNORECASE)
_CTX_RESIDENCIA = re.compile(r"\b(?:" + "|".join(CTX_RESIDENCIA) + r")\b", re.IGNORECASE)
_ORGAO_ANTES = re.compile(r"\b(?:secretaria|minist[ée]rio|procuradoria|delegacia|receita|conselho|tribunal|"
                          r"superintend[êe]ncia|subsecretaria|ag[êe]ncia)\b[^.\n;]{0,40}?\bd[aeo]\s*$", re.IGNORECASE)

# Complementos que completam um endereço já reconhecido. Seguem a ordem de endereçamento dos Correios
# (logradouro, número, complemento, bairro, município, UF, CEP): o bairro, o lote e o CEP integram o
# endereço; o município e a UF no fim, sozinhos, não identificam ninguém e ficam visíveis.
_ESPACO = r"[^\S\n]"  # espaço que não atravessa linha
#: Divisão do município ou da zona rural que compõe o endereço. Em "Jardim América", "Vila Nova" e
#: "Parque das Flores", o rótulo é parte do próprio nome do bairro.
_ROTULO_BAIRRO = (rf"\b(?:bairro|setor(?:{_ESPACO}+habitacional)?|jardim|jd\.|vila|parque|residencial|"
                  rf"condom[íi]nio|loteamento|conjunto{_ESPACO}+habitacional|distrito|"
                  rf"n[úu]cleo{_ESPACO}+(?:rural|habitacional)|col[ôo]nia{_ESPACO}+agr[íi]cola)")
#: Nome do bairro: palavras com inicial maiúscula na mesma linha, com conectores ("Jardim das Flores",
#: "Setor M Norte", "Guará II").
_NOME_BAIRRO = (rf"(?-i:(?:d[aeo]s?{_ESPACO}+)?[A-ZÀ-Ú][\wÀ-ú'’]*"
                rf"(?:{_ESPACO}+(?:d[aeo]s?{_ESPACO}+|e{_ESPACO}+)?[A-ZÀ-Ú][\wÀ-ú'’]*){{0,4}})")
#: Nome do bairro escrito em minúsculas ("setor sul", "bairro jardim america"), sem começar por
#: advérbio ou pronome ("no bairro onde moro").
_NOME_BAIRRO_MINUSCULO = (rf"(?-i:(?!(?:onde|que|para|com|desde|perto|aqui|ali|mesmo|todo|toda|inteir[oa]|"
                          rf"vizinh[oa]|pr[óo]xim[oa])\b)[a-zà-ú][\wà-ú'’]{{2,}}"
                          rf"(?:{_ESPACO}+(?:d[aeo]s?{_ESPACO}+)?[a-zà-ú][\wà-ú'’]{{2,}}){{0,2}})")
#: Bairro após o endereço (", Bairro Centro", " no bairro Jardim América", " - Setor Sul", ", Zona Rural",
#: ", Centro"). "Centro" e "zona rural" seguidos de "de" nomeiam o município ("centro de Sinop", "zona
#: rural de Formosa"), que fica visível.
_BAIRRO_DEPOIS = re.compile(
    rf"{_ESPACO}*(?:[,\-–]{_ESPACO}*)?(?:(?:n[oa]|em){_ESPACO}+)?"
    rf"(?P<b>(?P<r>{_ROTULO_BAIRRO}){_ESPACO}*:?{_ESPACO}*(?P<n>{_NOME_BAIRRO}|(?P<min>{_NOME_BAIRRO_MINUSCULO}))"
    rf"|(?:zona|[áa]rea){_ESPACO}+rural(?!{_ESPACO}+d[aeo]s?\b)"
    rf"|centro(?:{_ESPACO}+(?-i:[A-ZÀ-Ú][\wÀ-ú]+))?(?!{_ESPACO}+(?:d[aeo]s?\b|(?-i:[a-zà-ú]))))(?![\wÀ-ú])",
    re.IGNORECASE,
)
#: Nome de lugar (bairro ou município) antes do CEP.
_NOME_LUGAR = rf"(?-i:[A-ZÀ-Ú][\wÀ-ú'’]+(?:{_ESPACO}+(?:d[aeo]s?{_ESPACO}+)?[A-ZÀ-Ú][\wÀ-ú'’]+){{0,4}})"
#: CEP após o endereço, precedido ou não de bairro e município (", Águas Claras, CEP 71939-000",
#: ", Icaraí, Niterói - CEP 24230-010"): seguido do CEP, o município deixa de estar isolado no fim.
_CEP_DEPOIS = re.compile(
    rf"(?:{_ESPACO}*[,\-–]{_ESPACO}*(?:{_CIDADE_UF}|{_NOME_LUGAR})){{0,2}}{_ESPACO}*[,\-–]?{_ESPACO}*"
    rf"(?:CEP{_ESPACO}*[:\-]?{_ESPACO}*\d{{2}}\.?\d{{3}}{_ESPACO}?-?{_ESPACO}?\d{{3}}|\d{{2}}\.?\d{{3}}-\d{{3}})(?!\d)",
    re.IGNORECASE,
)
#: Componentes após o bairro (", Quadra 4, Lote 12").
_COMPONENTES_DEPOIS = re.compile(
    rf"(?:{_ESPACO}*[,\-–]?{_ESPACO}*(?:(?:n[oa]|d[ao]){_ESPACO}+)?(?:{_COMPONENTE}|{_COMPONENTE_NOMEADO}))+",
    re.IGNORECASE,
)
#: Ordem da via antes do logradouro, comum no Nordeste ("2ª Travessa São Jorge", "1ª Rua do Canal").
_ORDEM_VIA = re.compile(rf"(?<![\w.])\d{{1,2}}(?:[ªº°]|a|o){_ESPACO}+\Z")
#: Ponto de referência que completa o endereço sem número ("casa sem número, atrás da capela de São
#: Benedito", "em frente à escola municipal"): até cinco palavras, sem atravessar a vírgula.
_REFERENCIA_DEPOIS = re.compile(
    rf"{_ESPACO}*,?{_ESPACO}*(?:ao{_ESPACO}+lado|em{_ESPACO}+frente|atr[áa]s|pr[óo]xim[oa]|perto|nos{_ESPACO}+fundos)"
    rf"{_ESPACO}+(?:d[aeo]s?|a[os]?|à|às){_ESPACO}+[\wÀ-ú'’-]+(?:{_ESPACO}+[\wÀ-ú'’-]+){{0,4}}?(?=[,;.\n]|$)",
    re.IGNORECASE,
)
#: Descrição que localiza a moradia sem número, em segmentos separados por vírgula: a casa ("casa de
#: taipa azul"), a posição ("quarta casa à esquerda antes da ponte", "vizinho ao depósito"), a distância
#: ("a 2 km da escola") ou a propriedade conhecida ("no sítio conhecido como Recanto").
_DESCRICAO_DEPOIS = re.compile(
    _CASA_COLETIVA + rf"{_ESPACO}*,{_ESPACO}*(?=(?:casa|barrac[oa]|palafita|(?:primeira|segunda|terceira|quarta|quinta|[úu]ltima)"
    rf"(?:{_ESPACO}+casa)?{_ESPACO}+(?:[àa]{_ESPACO}+(?:esquerda|direita)|ap[óo]s|depois|antes|do{_ESPACO}+lado)|"
    rf"a{_ESPACO}+\d+(?:[.,]\d+)?{_ESPACO}*(?:km|quil[ôo]metros?|metros|m){_ESPACO}+d[aeo]|"
    rf"ao{_ESPACO}+lado|em{_ESPACO}+frente|atr[áa]s|pr[óo]xim[oa]{_ESPACO}+(?:a|à|ao|d)|perto{_ESPACO}+d|"
    rf"depois{_ESPACO}+d|junto{_ESPACO}+(?:a|à|ao)|vizinh[oa]{_ESPACO}+(?:a|à|ao|d)|defronte|"
    rf"n[oa]{_ESPACO}+(?:s[íi]tio|ch[áa]cara|fazenda){_ESPACO}+conhecid[oa]|na{_ESPACO}+beira|"
    rf"(?:rua|beco|viela){_ESPACO}+d[aeo]s?{_ESPACO})\b)[^,;.\n]{{1,120}}(?=[,;.\n]|$)",
    re.IGNORECASE,
)
#: Lote, casa ou bairro imediatamente antes do endereço ("Lote 4, Quadra 12", "Setor M Norte QNM 14",
#: "Vila Planalto, Acampamento Tamboril"); em Marabá, a folha antes da quadra ("Folha 31, Quadra 8").
_PARTE_ANTES = re.compile(
    rf"(?:(?:{_COMPONENTE_LOTE}|\bfolha{_ESPACO}+\d{{1,3}}|(?P<b>(?P<r>{_ROTULO_BAIRRO}){_ESPACO}+(?P<n>{_NOME_BAIRRO})))"
    rf"{_ESPACO}*[,\-–]?{_ESPACO}*)+\Z",
    re.IGNORECASE,
)
#: Ligação entre duas partes do mesmo endereço ("Sítio Três Irmãos na Estrada do Capão Seco",
#: "Assentamento Pedra Branca, no km 22", "km 31 da Rodovia TO-050").
_ENTRE_PARTES = re.compile(rf"{_ESPACO}*(?:[,\-–]{_ESPACO}*)?(?:(?:n[oa]s?|em|d[aeo]s?|à|ao){_ESPACO}+)?",
                           re.IGNORECASE)
#: Órgão ou equipamento público citado antes do endereço: o endereço é institucional e, pela LAI, de
#: divulgação obrigatória; não é estendido a bairro e CEP.
_INSTITUICAO = re.compile(
    r"\b(?:secretaria|minist[ée]rio|prefeitura|c[âa]mara|assembleia|tribunal|f[óo]rum|delegacia|batalh[ãa]o|"
    r"quartel|autarquia|universidade|instituto|escola|col[ée]gio|creche|hospital|posto\s+de\s+sa[úu]de|UBS|"
    r"unidade\s+b[áa]sica|centro\s+de\s+sa[úu]de|policl[íi]nica|cart[óo]rio|defensoria|procuradoria|promotoria|"
    r"ouvidoria|conselho\s+tutelar|CRAS|CREAS|detran|administra[çc][ãa]o\s+regional|[óo]rg[ãa]o|reparti[çc][ãa]o|"
    r"superintend[êe]ncia|ger[êe]ncia\s+regional)\b",
    re.IGNORECASE,
)
#: Expressão de que o endereço é da própria pessoa, que prevalece sobre a menção a órgão público.
_RESIDENCIA_PROPRIA = re.compile(
    r"\b(?:moro|resido|reside|residente|residimos|mora(?:mos)?|morador[a]?|domicili\w*|"
    r"minha\s+(?:casa|resid[êe]ncia|propriedade|ch[áa]cara)|meu\s+(?:endere[çc]o|im[óo]vel|lote|s[íi]tio)|"
    r"nosso\s+endere[çc]o|propriet[áa]ri[oa])\b",
    re.IGNORECASE,
)
#: Fim de frase, que delimita a busca de contexto institucional.
_FIM_FRASE = re.compile(r"[.!?;\n]")
#: Regras de endereço identificado só pelo lote, sem logradouro.
_LOTE_SEM_LOGRADOURO = frozenset({"endereco:gleba", "endereco:conjunto", "endereco:localidade-lote",
                                  "endereco:rural-lote", "endereco:setor"})


def _institucional(texto: str, inicio: int) -> bool:
    """Indica se o endereço que começa em ``inicio`` é de órgão ou equipamento público: há menção a
    órgão na mesma frase, até 100 caracteres antes, e nenhuma expressão de residência própria."""
    janela = max(0, inicio - 100)
    fins = [m.end() for m in _FIM_FRASE.finditer(texto, janela, inicio)]
    janela = fins[-1] if fins else janela
    return bool(_INSTITUICAO.search(texto, janela, inicio)) and not _RESIDENCIA_PROPRIA.search(texto, janela, inicio)


def _nome_de_localidade(nome: str) -> bool:
    """Indica se o nome é de município, estado ou região administrativa do DF ("Vila Velha", "Distrito
    Federal", "Jardim Botânico")."""
    chave = " ".join(dobrar(nome).split())
    return chave in municipios() or chave in _NOMES_ESTADOS or bool(_LOCALIDADES.fullmatch(nome))


def _bairro_valido(m, depois: bool) -> bool:
    """Confere o bairro casado por :data:`_BAIRRO_DEPOIS` ou :data:`_PARTE_ANTES`.

    Rejeita o nome de município, estado ou região administrativa que começa por "Vila", "Jardim" ou
    "Distrito" ("Vila Velha", "Distrito Federal") e, depois do endereço, o "setor de" de um órgão
    ("Rua das Flores, 14, no setor de RH"); antes de quadra ou lote, "Setor de Mansões" é o setor.
    """
    if not m.group("b") or not m.group("r"):
        return True
    rotulo = dobrar(m.group("r"))
    if depois and rotulo.startswith("setor") and re.match(r"d[aeo]s?\s", m.group("n")):
        return False
    return rotulo.startswith(("bairro", "setor")) or not _nome_de_localidade(m.group("b"))


def _bairro_depois(texto: str, d: Deteccao) -> int | None:
    """Fim do bairro que segue o endereço, ou ``None``."""
    m = _BAIRRO_DEPOIS.match(texto, d.fim)
    if m is None or not _bairro_valido(m, depois=True):
        return None
    # Nome em minúsculas: só depois da palavra "bairro" ou em endereço também escrito em minúsculas.
    if (m.group("min") and not dobrar(m.group("r")).startswith("bairro")
            and any(c.isupper() for c in texto[d.inicio:d.fim])):
        return None
    return m.end()


def _completar(texto: str, d: Deteccao) -> None:
    """Estende o endereço aos complementos vizinhos: bairro, lote, componentes, CEP e ponto de referência
    depois dele e ordem da via, lote, casa ou bairro imediatamente antes. Endereços de órgãos públicos não
    são estendidos."""
    if _institucional(texto, d.inicio):
        return
    while True:
        fim = _bairro_depois(texto, d)
        if fim is None:
            m = (_CEP_DEPOIS.match(texto, d.fim) or _COMPONENTES_DEPOIS.match(texto, d.fim)
                 or _REFERENCIA_DEPOIS.match(texto, d.fim) or _DESCRICAO_DEPOIS.match(texto, d.fim))
            fim = m.end() if m else None
        if fim is None or fim <= d.fim:
            break
        d.fim = fim
    m = _ORDEM_VIA.search(texto, max(0, d.inicio - 5), d.inicio)
    if m and re.match(_LOGRADOURO, texto[d.inicio:], re.IGNORECASE):
        d.inicio = m.start()
    m = _PARTE_ANTES.search(texto, max(0, d.inicio - 80), d.inicio)
    if m and _bairro_valido(m, depois=False):
        d.inicio = m.start()


def _unir_vizinhos(texto: str, deteccoes: list[Deteccao]) -> list[Deteccao]:
    """Une os trechos de endereço contíguos ou ligados só por pontuação ou preposição, para que a
    ligação ("na", "no km", "da") não fique visível entre duas tarjas."""
    enderecos = sorted((d for d in deteccoes if d.tipo == "ENDERECO"), key=lambda d: (d.inicio, -d.fim))
    unidos: list[Deteccao] = []
    for d in enderecos:
        ult = unidos[-1] if unidos else None
        if ult is not None and (d.inicio <= ult.fim or _ENTRE_PARTES.fullmatch(texto, ult.fim, d.inicio)):
            ult.fim = max(ult.fim, d.fim)
            ult.score = max(ult.score, d.score)
            continue
        unidos.append(d)
    return [d for d in deteccoes if d.tipo != "ENDERECO"] + unidos


#: Comunidade ou unidade pública logo antes do nome da propriedade ("comunidade rural Sítio Lagoa Seca",
#: "a UBS do Sítio Boa Vista").
_COMUNIDADE_ANTES = re.compile(
    r"(?:\b(?:comunidade|localidade|povoado|distrito|regi[ãa]o|vila|lugarejo|n[úu]cleo)(?:\s+(?:rural|quilombola|"
    r"ribeirinha|ind[íi]gena|tradicional))?|" + _INSTITUICAO.pattern + r"[^.;\n,]{0,40}?\bd[aeo])\s*$",
    re.IGNORECASE,
)
#: Propriedade ou moradia junto à rodovia ("BR-020, km 12, Chácara 5", "km 851, barraca 4").
_PROPRIEDADE_NA_RODOVIA = re.compile(r"\b(?:ch[áa]cara|s[íi]tio|fazenda|lote|n[úu]cleo|condom[íi]nio|casa|barrac[oa]|"
                                     r"acampamento)\b", re.IGNORECASE)
#: Cruzamento de vias no endereço estrangeiro ("calle Sucre esquina Bolívar", "Calle 7 con Carrera 9").
_CRUZAMENTO = re.compile(r"\s(?:con|esquina|y|entre|et|e)\s", re.IGNORECASE)

#: Rótulo de campo que introduz a moradia da pessoa num formulário ou relatório ("Endereço:", "End.:",
#: "Residência:", "Local de pernoite:", "Último endereço no exterior:"). Os rótulos de endereço de
#: unidade, de obra, de empresa ou eletrônico não entram.
_ROTULO_MORADIA = re.compile(
    r"^[ \t]*(?:[-–•*][ \t]*)?(?:endere[çc]o(?:[ \t]+(?:residencial|atual|completo|domiciliar|de[ \t]+resid[êe]ncia))?|"
    r"(?-i:END|End)\.?|resid[êe]ncia(?:[ \t]+atual)?|domic[íi]lio|morada|"
    r"local[ \t]+de[ \t]+(?:pernoite|perman[êe]ncia)(?:[ \t]+habitual)?|ponto[ \t]+de[ \t]+pernoite|"
    r"localiza[çc][ãa]o[ \t]+do[ \t]+domic[íi]lio|[úu]ltimo[ \t]+endere[çc]o(?:[ \t]+[^:\n]{1,40}?)?)"
    r"[ \t]*(?::|(?<=(?-i:END))[ \t])[ \t]*",
    re.IGNORECASE | re.MULTILINE,
)
#: Fim do valor do campo: outro campo na mesma linha ("Bairro:", "CEP:", "Tel.:", "– Fone (61) …"), coluna
#: (três espaços) ou barra vertical.
_FIM_VALOR = re.compile(r"[ \t]{3,}|[ \t]\|[ \t]|[ \t]+(?:[–—-][ \t]*)?(?:bairro|cep|tel(?:efones?)?|fone|celular|whats\w*|"
                        r"e-?mail|munic[íi]pio|cidade|uf|ponto[ \t]+de[ \t]+refer[êe]ncia)\b\.?[ \t]*(?::|(?=[(+\d]))",
                        re.IGNORECASE)
#: Valor que não descreve endereço ("não informado", "situação de rua", "o mesmo").
_SEM_ENDERECO = re.compile(r"(?:n[ãa]o\s+(?:informad|possui|tem|sabe|declarad|consta)|sem\s+(?:endere|resid|domic|informa)|"
                           r"situa[çc][ãa]o\s+de\s+rua|ignorad|idem\b|o\s+mesmo|mesmo\s+d|www\.|https?:)", re.IGNORECASE)
#: Separador entre os segmentos do valor: vírgula ou travessão.
_SEPARADOR_SEGMENTO = re.compile(r",[ \t]*|[ \t][–—-][ \t]*")
#: Segmento final que não integra o endereço (convenção de anotação): zona rural, território, município,
#: estado ou país.
_FORA_DO_ENDERECO = re.compile(
    r"(?:(?:zona|[áa]rea)\s+rural|interior\b|terra\s+ind[íi]gena|territ[óo]rio|reserva\s+ind[íi]gena|"
    r"(?:munic[íi]pio|cidade|estado|departamento|prov[íi]ncia)\b|cep\b|"
    r"(?:brasil|bol[íi]via|venezuela|haiti|paraguai|argentina|uruguai|peru|col[ôo]mbia|chile|cuba|guiana|suriname|"
    r"angola|s[íi]ria|china|coreia(?:\s+do\s+sul)?|jap[ãa]o|it[áa]lia|alemanha|portugal|senegal)\s*$|" + _UF + r"\s*$)",
    re.IGNORECASE,
)


def _aparar_valor(texto: str, ini: int, fim: int) -> int:
    """Fim do valor de um campo de endereço sem os segmentos finais que não o integram (município, região
    administrativa do DF, UF, zona rural, território, país)."""
    while True:
        while fim > ini and texto[fim - 1] in " \t.;,":
            fim -= 1
        separadores = list(_SEPARADOR_SEGMENTO.finditer(texto, ini, fim))
        if not separadores:
            return fim
        m = separadores[-1]
        segmento = texto[m.end():fim]
        if not segmento or not (_FORA_DO_ENDERECO.match(segmento) or municipio_em(texto, m.end()) == fim
                                or re.fullmatch(_CIDADE_UF, segmento, re.IGNORECASE) or _LOCALIDADES.fullmatch(segmento)):
            return fim
        fim = m.start()


def _enderecos_rotulados(texto: str) -> list[Deteccao]:
    """Valor de campo de moradia ("Endereço: Aldeia Boa Vista, casa de taipa perto da escola"), do início
    ao fim da linha, sem o município, a UF, a zona rural e o território no fim. Cobre a referência
    descritiva das moradias rurais, de aldeias, de ocupações e de pessoas em situação de rua, que não
    seguem o padrão de logradouro e número."""
    saida = []
    for m in _ROTULO_MORADIA.finditer(texto):
        ini = m.end()
        fim_linha = texto.find("\n", ini)
        fim_linha = len(texto) if fim_linha < 0 else fim_linha
        corte = _FIM_VALOR.search(texto, ini, fim_linha)
        fim = _aparar_valor(texto, ini, corte.start() if corte else fim_linha)
        valor = texto[ini:fim]
        if sum(c.isalnum() for c in valor) < 4 or "@" in valor or _SEM_ENDERECO.match(valor):
            continue
        saida.append(Deteccao(ini, fim, "ENDERECO", 0.8, "endereco:rotulo", CONTEXTUAL))
    return saida


#: Lote rural citado sem a vicinal ("ocupa o lote 23", "os confrontantes do lote 58"), fora de tabela e de
#: licitação.
_LOTE = re.compile(r"\blote\s+(?:n[º°o]\.?\s*)?\d{1,4}[A-Z]?(?![\w/])(?!\s*(?:\||d[oa]\s+(?:preg[ãa]o|licita|edital|"
                   r"leil[ãa]o|contrato|ata|item)))", re.IGNORECASE)
_ITEM_ANTES = re.compile(r"\b(?:itens?|preg[ãa]o|leil[ãa]o|licita[çc][ãa]o)\b[^.\n]{0,30}$", re.IGNORECASE)
#: Regularização fundiária e reforma agrária: o lote é a parcela de uma família.
_CONTEXTO_AGRARIO = re.compile(
    r"\b(?:(?:projeto\s+de\s+)?assentamento|confrontantes?|gleba|vicinal|travess[ãa]o|regulariza[çc][ãa]o\s+fundi[áa]ria|"
    r"titula[çc][ãa]o|incra|reforma\s+agr[áa]ria|parceleir[oa]s?|posse\s+mansa|im[óo]vel\s+rural|linha\s+\d{1,4})\b",
    re.IGNORECASE,
)


def _lotes_agrarios(texto: str) -> list[Deteccao]:
    """Lotes de assentamento e de regularização fundiária, quando o trecho vizinho trata da parcela."""
    saida = []
    for m in _LOTE.finditer(texto):
        if _ITEM_ANTES.search(texto, max(0, m.start() - 40), m.start()) or _institucional(texto, m.start()):
            continue
        if _CONTEXTO_AGRARIO.search(texto, max(0, m.start() - 300), min(len(texto), m.end() + 300)):
            saida.append(Deteccao(m.start(), m.end(), "ENDERECO", 0.75, "endereco:lote-agrario", CONTEXTUAL))
    return saida


#: Regiões administrativas do Distrito Federal e bairros de Brasília.
REGIOES_DF = (
    "Plano Piloto", "Brasília", "Gama", "Taguatinga", "Brazlândia", "Sobradinho", "Sobradinho II", "Planaltina",
    "Paranoá", "Núcleo Bandeirante", "Ceilândia", "Guará", "Cruzeiro", "Samambaia", "Santa Maria",
    "São Sebastião", "Recanto das Emas", "Lago Sul", "Riacho Fundo", "Riacho Fundo II", "Lago Norte",
    "Candangolândia", "Águas Claras", "Sudoeste", "Octogonal", "Varjão", "Park Way", "SCIA", "Estrutural",
    "Jardim Botânico", "Itapoã", "SIA", "Vicente Pires", "Fercal", "Sol Nascente", "Pôr do Sol", "Arniqueira",
    "Arapoanga", "Água Quente", "Asa Norte", "Asa Sul", "Noroeste",
)


class ReconhecedorEndereco(ReconhecedorPadroes):
    """Regras de endereço, com ajuste de confiança para o endereçamento do DF.

    Uma sigla seguida de número ("QS 12") pode ser outra coisa; com componentes adicionais
    ("QS 12 Conjunto 3 Casa 8") é inequivocamente um endereço. A confiança sobe para 0,75 com um
    componente e para 0,85 com dois ou mais.
    """

    def __init__(self):
        super().__init__("localizacao", PADROES)

    def detectar(self, texto: str) -> list[Deteccao]:
        """Achados de todas as regras, com a confiança do endereçamento do DF ajustada.

        Cada endereço é estendido aos complementos vizinhos (bairro, lote, CEP) e os trechos do mesmo
        endereço ligados só por pontuação ou preposição são unidos.
        """
        saida = []
        for d in super().detectar(texto) + _enderecos_rotulados(texto) + _lotes_agrarios(texto):
            residencia = bool(_CTX_RESIDENCIA.search(texto, max(0, d.inicio - 60), d.inicio))
            # "Sítio Novo", "Fazenda Rio Grande", "Estância Velha": o nome do próprio município, citado
            # sem expressão de residência, fica a cargo do reconhecedor de localidades.
            if d.origem == "endereco:rural" and municipio_em(texto, d.inicio) == d.fim and not residencia:
                continue
            # "Secretaria de Estado de Fazenda …", "Ministério da Fazenda": órgão, não propriedade.
            if d.origem == "endereco:rural" and _ORGAO_ANTES.search(texto, max(0, d.inicio - 60), d.inicio):
                continue
            # No documento expedido pelo órgão, "a UBS do povoado Sítio Lagoa Seca" e "a escola do
            # Sítio Boa Vista" designam a comunidade atendida pela unidade pública, e rodovia e quilômetro
            # sem residência nem propriedade ("ponte na RO-010, km 87"), o local da obra.
            if (d.origem == "endereco:rural" and not residencia and documento_do_orgao(texto)
                    and _COMUNIDADE_ANTES.search(texto, max(0, d.inicio - 80), d.inicio)):
                continue
            if (d.origem in ("endereco:rodovia", "endereco:km-rodovia") and not residencia
                    and not _PROPRIEDADE_NA_RODOVIA.search(texto, d.inicio, d.fim) and documento_do_orgao(texto)):
                continue
            # Via no exterior: com número, componente ou, havendo expressão de residência, cruzamento.
            if d.origem == "endereco:exterior" and not (re.search(r"\d", texto[d.inicio:d.fim]) or (
                    residencia and _CRUZAMENTO.search(texto, d.inicio, d.fim))):
                continue
            # Gleba, trecho, conjunto ou lote de assentamento como sede de órgão ou equipamento público
            # ("a escola, localizada na Gleba 4, Lote 12"): endereço institucional.
            if d.origem in _LOTE_SEM_LOGRADOURO and _institucional(texto, d.inicio):
                continue
            if d.origem == "endereco:df":
                trecho = texto[d.inicio:d.fim]
                componentes = len(_COMP_RE.findall(trecho))
                if componentes >= 2:
                    d.score = max(d.score, 0.85)
                elif componentes == 1:
                    d.score = max(d.score, 0.75)
            if d.tipo == "ENDERECO":
                _completar(texto, d)
            saida.append(d)
        return _unir_vizinhos(texto, saida)


#: Nome de região administrativa, com qualificador opcional ("Riacho Fundo II", "Gama Leste").
#: Sensível a maiúsculas: nomes próprios, para não confundir "gama" ou "estrutural" com palavras comuns.
_LOCALIDADES = re.compile(
    r"\b(?:" + "|".join(re.escape(r).replace(r"\ ", r"\s+") for r in sorted(REGIOES_DF, key=len, reverse=True))
    + r")(?:\s+(?:Norte|Sul|Centro|Leste|Oeste|I{1,3}))?\b"
)


#: Expressão de residência imediatamente antes da localidade ("moro em", "residente no").
_RESIDE = re.compile(r"\b(?:resido|moro|reside|mora|moramos|residente|domiciliad[oa]|morador(?:a)?)"
                     r"(?:\s+(?:em|no|na|n[oa]s|d[aoe]))+\s*$", re.IGNORECASE)
#: Designação explícita de município antes do nome ("município de", "cidade de").
_MUNICIPIO_ANTES = re.compile(r"\b(?:munic[íi]pio|cidade|prefeitura\s+municipal)\s+d[eo]\s*$", re.IGNORECASE)
#: UF logo após o nome ("/GO", " - SP", " (PE)", ", MG").
_UF_DEPOIS = re.compile(rf"\s*(?:[-/–,]\s*|\(\s*)(?P<uf>{_UF})\)?(?![\w])")
#: Palavra para a busca de municípios: letras, apóstrofo e hífen ("Olho d'Água", "Embu-Guaçu").
_PALAVRA = re.compile(r"[\wÀ-ú'’-]+")
#: Municípios cujo nome é também palavra comum; isolados (sem UF nem "município de"), não são sinalizados.
_MUNICIPIOS_COMUNS = frozenset(dobrar(p) for p in (
    "Alegre", "Alvorada", "Amparo", "Aurora", "Bandeirantes", "Barra", "Belém", "Bonito", "Central", "Colorado",
    "Cruz", "Esperança", "Estrela", "Floresta", "Formosa", "Glória", "Guarani", "Jardim", "Lagoa", "Liberdade",
    "Mirante", "Natal", "Nova", "Palmas", "Palmeira", "Paraíso", "Pedra", "Planalto", "Porto", "Primavera",
    "Progresso", "Recreio", "Redenção", "Santana", "Saudade", "Serra", "Sossego", "Triunfo", "União", "Vale",
    "Vitória", "Campos", "Ouro", "Prata", "Cristal", "Fortaleza", "Itu", "Socorro", "Salvador",
))


@cache
def municipios() -> dict[str, frozenset[str]]:
    """Municípios brasileiros (lista do IBGE) pelo nome em minúsculas e sem acentos, com as UFs."""
    texto = resources.files("themis_lgpd.dados").joinpath("municipios.txt").read_text(encoding="utf-8")
    por_nome: dict[str, set[str]] = {}
    for linha in texto.splitlines():
        if linha and not linha.startswith("#"):
            nome, uf = linha.rsplit("|", 1)
            por_nome.setdefault(" ".join(dobrar(nome).split()), set()).add(uf)
    return {nome: frozenset(ufs) for nome, ufs in por_nome.items()}


@cache
def _palavras_por_inicio() -> dict[str, int]:
    """Para cada primeira palavra de nome de município, o maior número de palavras dos nomes que ela inicia."""
    indice: dict[str, int] = {}
    for nome in municipios():
        partes = nome.split()
        indice[partes[0]] = max(indice.get(partes[0], 0), len(partes))
    return indice


@cache
def _ambiguos() -> frozenset[str]:
    """Palavras isoladas que também são prenome, sobrenome ou palavra comum."""
    from .nomes import NAO_INICIAM_NOME, PALAVRAS_COMUNS, ambiguos, prenomes, sobrenomes

    return frozenset(prenomes() | sobrenomes() | ambiguos() | PALAVRAS_COMUNS | NAO_INICIAM_NOME | _MUNICIPIOS_COMUNS)


def _inicio_de_frase(texto: str, inicio: int) -> bool:
    anterior = texto[:inicio].rstrip()
    return not anterior or anterior[-1] in ".!?:;\n"


class ReconhecedorLocalidade:
    """Município brasileiro ou região administrativa do DF citado no texto.

    Isolado, é quase-identificador (``LOCALIDADE``), sinalizado para revisão e tarjado apenas no
    perfil de proteção máxima. Precedido de expressão de residência ("resido em Taguatinga", "moro em
    campinas"), é local de moradia e recebe o tipo ``ENDERECO``.

    Municípios são reconhecidos pela lista do IBGE nas formas "Cidade/UF", "Cidade - UF",
    "Cidade (UF)", "município de Cidade" e após expressão de residência (inclusive em minúsculas). A
    menção isolada só é sinalizada quando o nome começa com maiúscula, não abre a frase e não é
    ambíguo (nomes compostos, ou palavra que não seja também prenome, sobrenome ou palavra comum).
    """

    nome = "localidade"

    def detectar(self, texto: str) -> list[Deteccao]:
        """Localidades encontradas no texto, já classificadas."""
        saida = []
        for m in _LOCALIDADES.finditer(texto):
            if _RESIDE.search(texto, max(0, m.start() - 30), m.start()):
                saida.append(Deteccao(m.start(), m.end(), "ENDERECO", 0.75, "localidade:residencia"))
            else:
                saida.append(Deteccao(m.start(), m.end(), "LOCALIDADE", 0.6, self.nome))
        return saida + self._municipios(texto)

    def _municipios(self, texto: str) -> list[Deteccao]:
        palavras = list(_PALAVRA.finditer(texto))
        saida: list[Deteccao] = []
        i = 0
        while i < len(palavras):
            achado = _municipio_mais_longo(texto, palavras, i)
            if achado is None:
                i += 1
                continue
            fim, chave, n = achado
            deteccao = self._classificar(texto, palavras[i].start(), fim, chave, n, municipios()[chave])
            if deteccao is not None:
                saida.append(deteccao)
            i += n
        return saida

    @staticmethod
    def _classificar(texto: str, inicio: int, fim: int, chave: str, palavras: int,
                     ufs: frozenset[str]) -> Deteccao | None:
        janela = max(0, inicio - 40)
        uf = _UF_DEPOIS.match(texto, fim)
        fim_com_uf = uf.end() if uf else fim
        # "Paraná", "Amapá", "São Paulo", "Goiás": sem UF, pode ser o estado, que não identifica ninguém.
        estado = uf is None and chave in _NOMES_ESTADOS
        if _RESIDE.search(texto, janela, inicio):
            if estado:
                return Deteccao(inicio, fim, "LOCALIDADE", 0.6, "localidade:residencia-estado", CONTEXTUAL)
            return Deteccao(inicio, fim_com_uf, "ENDERECO", 0.75, "localidade:residencia-municipio", CONTEXTUAL)
        maiuscula = texto[inicio].isupper()
        if uf and maiuscula:
            confere = uf.group("uf") in ufs
            return Deteccao(inicio, fim_com_uf, "LOCALIDADE", 0.85 if confere else 0.65, "localidade:municipio-uf",
                            validado=confere)
        if _MUNICIPIO_ANTES.search(texto, janela, inicio):
            return Deteccao(inicio, fim_com_uf, "LOCALIDADE", 0.8, "localidade:municipio", CONTEXTUAL)
        ambiguo = estado or (palavras == 1 and (chave in _ambiguos() or len(chave) < 4))
        # Parte do nome de um logradouro ("Rua dos Andradas", "Avenida Rui Barbosa") não é menção à cidade.
        if maiuscula and not ambiguo and not _inicio_de_frase(texto, inicio) and not _LOGRADOURO_ANTES.search(
                texto, janela, inicio):
            return Deteccao(inicio, fim, "LOCALIDADE", 0.6, "localidade:municipio-isolado")
        return None


_NOMES_ESTADOS = frozenset(dobrar(e) for e in ESTADOS)
#: Tipo de logradouro imediatamente antes de um nome ("Rua dos", "Avenida").
_LOGRADOURO_ANTES = re.compile(r"\b" + _LOGRADOURO + r"(?:\s+d[aeo]s?)?\s*$", re.IGNORECASE)


def _municipio_mais_longo(texto: str, palavras: list, i: int) -> tuple[int, str, int] | None:
    """Município mais longo que começa na palavra ``i``: ``(fim, nome normalizado, nº de palavras)``."""
    tabela = municipios()
    maximo = _palavras_por_inicio().get(dobrar(palavras[i].group()), 0)
    for n in range(min(maximo, len(palavras) - i), 0, -1):
        trecho = palavras[i:i + n]
        # As palavras do nome precisam estar separadas apenas por espaços.
        if any(texto[a.end():b.start()].strip() for a, b in zip(trecho, trecho[1:])):
            continue
        chave = " ".join(dobrar(p.group()) for p in trecho)
        if chave in tabela:
            return trecho[-1].end(), chave, n
    return None


def municipio_em(texto: str, inicio: int) -> int | None:
    """Fim do nome de município que começa exatamente em ``inicio``, ou ``None``."""
    palavras = list(_PALAVRA.finditer(texto, inicio, min(len(texto), inicio + 80)))
    if not palavras or palavras[0].start() != inicio:
        return None
    achado = _municipio_mais_longo(texto, palavras, 0)
    return achado[0] if achado else None


def reconhecedores():
    """Reconhecedores deste módulo, na forma esperada por :mod:`themis_lgpd.analisador`."""
    return [ReconhecedorEndereco(), ReconhecedorLocalidade()]
