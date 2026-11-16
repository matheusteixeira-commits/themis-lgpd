"""Dados pessoais em tabelas, listas e formulários, reconhecidos pela estrutura do texto.

Relações de servidores, folhas de pagamento e de bolsas, editais de resultado, escalas, listas de
presença, relações de beneficiários e de diárias e fichas cadastrais trazem o dado pessoal numa
célula cujo rótulo está só no cabeçalho da coluna ou num bloco separado dos valores: a matrícula, o
registro profissional, a data de nascimento, a agência e a conta e o valor pago não têm a
palavra-chave ao lado. Este módulo reconhece a estrutura do texto, tipifica cada coluna pelo
cabeçalho e confere a forma de cada valor antes de atribuir o tipo.

Formas reconhecidas:

Tabela com separador
    Colunas separadas por barra vertical, tabulação ou ponto e vírgula (arquivo CSV), com linha de
    cabeçalho.
Tabela alinhada por espaços
    Colunas alinhadas por espaços, como nos relatórios emitidos por sistemas de folha, de protocolo
    e de cadastro. Cada coluna começa no seu rótulo e se estende para a esquerda até a faixa em
    branco comum a todas as linhas (valores alinhados à direita). A célula partida em duas linhas
    continua na linha seguinte, sem conteúdo na primeira coluna; o registro em duas linhas, com dois
    cabeçalhos, é separado pelo recuo de cada linha.
Formulário em grade
    Rótulos numa linha e valores na linha de baixo, na mesma ordem ("CPF   DATA DE NASCIMENTO" sobre
    o CPF e a data), inclusive com um rótulo por linha.
Colunas em bloco
    Texto extraído coluna a coluna: o cabeçalho de cada coluna seguido dos seus valores, um por
    linha, com o mesmo número de valores em todas as colunas.
Formulário em bloco
    Rótulos de campo ("Nome:", "CPF:") em sequência e, adiante, os valores na mesma ordem e em igual
    número, como na extração de texto de formulários eletrônicos.

Só são examinadas tabelas de pessoas: com coluna de identificador pessoal (CPF, RG, matrícula,
registro profissional, NIS, CNS, inscrição, data de nascimento) ou com coluna de nome em que ao menos
uma célula traga um nome completo ("Profissional" e "Beneficiário" também encabeçam categorias e
contagens). Tabelas de itens, de empresas, de unidades e de orçamento não têm essas colunas e ficam
como estão; numa tabela de pessoas, as linhas de pessoa jurídica (CNPJ, razão social) e as de totais
são ignoradas. Colunas de valor, de conta bancária, de contato, de endereço de residência e de saúde
só são tipificadas em tabela de pessoas.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from functools import cache

import regex as re

from ..texto import dobrar
from . import nomes
from .base import CONTEXTUAL, Deteccao

# =========================================================================== rótulos de coluna
#: Flexão de gênero ou número no rótulo: "SERVIDOR(A)", "ALUNO/A", "BENEFICIÁRIOS(AS)".
_FLEXAO = r"(?:\s*\((?:a|o|as|os|es)\)|/as?|/os?)?"
#: Papéis de pessoa natural que, como rótulo de coluna, indicam uma tabela de pessoas.
_PAPEIS_FORTES = (
    r"servidor(?:es|as?)?|benefici[áa]ri[oa]s?|bolsistas?|alun[oa]s?|estudantes?|candidat[oa]s?|atletas?|"
    r"pacientes?|requerentes?|interessad[oa]s?|contribuintes?|segurad[oa]s?|pensionistas?|aposentad[oa]s?|"
    r"profissional|empregad[oa]s?|funcion[áa]ri[oa]s?|militar(?:es)?|policia(?:l|is)|professor(?:es|as?)?|"
    r"docentes?|estagi[áa]ri[oa]s?|vacinad[oa]s?|credor(?:es|as?)?|devedor(?:es|as?)?|titular(?:es)?|"
    r"inscrit[oa]s?|nomead[oa]s?|aprovad[oa]s?|classificad[oa]s?|selecionad[oa]s?|propriet[áa]ri[oa]s?|"
    r"condutor(?:es|as?)?|infrator(?:es|as?)?|autuad[oa]s?|declarantes?|usu[áa]ri[oa]s?|morador(?:es|as?)?|"
    r"agricultor(?:es|as?)?|pescador(?:es|as?)?|trabalhador(?:es|as?)?|eleitor(?:es|as?)?|homenagead[oa]s?|"
    r"premiad[oa]s?|falecid[oa]s?|apenad[oa]s?|investigad[oa]s?|denunciad[oa]s?|indiciad[oa]s?|v[íi]timas?"
)
#: Papéis que só designam pessoas numa tabela que já é de pessoas ("MÃE/RESPONSÁVEL",
#: "ORIENTADOR(A)"): numa tabela de ações, "Responsável" costuma ser uma unidade.
_PAPEIS_FRACOS = (
    r"respons[áa]vel(?:\s+legal)?|m[ãa]e|pai|filia[çc][ãa]o|c[ôo]njuge|companheir[oa]|dependentes?|filh[oa]s?|"
    r"testemunhas?|orientador(?:es|as?)?|supervisor(?:es|as?)?|preceptor(?:es|as?)?|tutor(?:es|as?)?|"
    r"chefia(?:\s+imediata)?|membros?|conselheir[oa]s?|m[ée]dic[oa]s?|enfermeir[oa]s?|vacinador(?:es|as?)?|"
    r"examinador(?:es|as?)?|avaliador(?:es|as?)?|fiscal|substitut[oa]|acompanhante|representante(?:\s+legal)?|"
    r"m[ãa]e\s*/\s*respons[áa]vel|pai\s*/\s*m[ãa]e|respons[áa]vel\s*/\s*m[ãa]e"
)
_NUMERO = r"(?:n[º°o]\.?|n\.|n[úu]mero|num\.?)"
#: Expressão de valor em reais no rótulo: "(R$)", "R$", "em R$".
_EM_REAIS = r"(?:\s*(?:\(\s*r\$\s*\)|em\s+r\$|r\$))?"

#: Rótulos de coluna: tipo do catálogo atribuído às células, se o rótulo indica uma tabela de pessoas
#: (forte) e a expressão, comparada com a célula inteira do cabeçalho.
_ROTULOS: list[tuple[str, bool, str]] = [
    ("NOME", True, r"nomes?(?:\s+(?:completo|civil|social|e\s+sobrenome))?|nome\s+d[oa]s?" + _FLEXAO + r"\s+(?:"
     + _PAPEIS_FORTES + r"|" + _PAPEIS_FRACOS + r")" + _FLEXAO + r"(?:\s+\w+)?|(?:" + _PAPEIS_FORTES + r")" + _FLEXAO),
    ("NOME", False, r"(?:" + _PAPEIS_FRACOS + r")" + _FLEXAO + r"|nome\s+d[ao]\s+(?:m[ãa]e|pai)"),
    ("CPF", True, r"cpf(?:\s*/\s*cnpj)?|c\.p\.f\.?|" + _NUMERO + r"\s+(?:do\s+)?cpf"),
    ("RG", True, r"rg|r\.g\.?|identidade|c[ée]dula\s+de\s+identidade|carteira\s+de\s+identidade|"
                 r"doc(?:umento|\.)?\s+(?:de\s+)?identidade|rg\s*/\s*(?:uf|[óo]rg[ãa]o(?:\s+(?:emissor|expedidor))?)|"
                 r"rg\s+e\s+[óo]rg[ãa]o\s+(?:emissor|expedidor)|" + _NUMERO + r"\s+(?:do\s+)?rg"),
    ("MATRICULA", True, r"matr[íi]cula(?:\s+(?:funcional|siape|masp|n[º°o]\.?))?|matr?\.|mat\.?|siape|masp|"
                        r"" + _NUMERO + r"\s+(?:de\s+)?matr[íi]cula|" + _NUMERO + r"\s+funcional|id\.?\s*funcional|"
                        r"identidade\s+funcional|registro\s+funcional|r\.\s?f\.?"),
    ("REGISTRO_PROFISSIONAL", True,
     r"(?:oab|crm|cro|crp|coren|crea|cau|crf|crn|crefito|crmv|crc|cress|cref|crfa|crq|creci|crbm|cra|crb)"
     r"(?:\s*[-/]\s*[a-z]{2})?(?:\s+" + _NUMERO + r")?|registro\s+(?:profissional|no\s+conselho|de\s+classe)|"
     r"" + _NUMERO + r"\s+(?:do\s+)?(?:registro|conselho)(?:\s+(?:profissional|de\s+classe))?|"
     r"conselho\s*/\s*n[º°o]\.?"),
    ("PIS", True, r"pis(?:\s*/\s*pasep)?|pasep|nis|nit|pis\s*/\s*nis|nis\s*/\s*pis|" + _NUMERO + r"\s+(?:do\s+)?nis"),
    ("CNS", True, r"cns|cart[ãa]o\s+(?:do\s+)?sus|cart[ãa]o\s+nacional\s+de\s+sa[úu]de|" + _NUMERO
     + r"\s+(?:do\s+)?(?:cns|cart[ãa]o\s+sus)"),
    ("TITULO_ELEITOR", True, r"t[íi]t(?:ulo|\.)\s*(?:de\s+)?eleit(?:or|oral|\.)?"),
    ("CNH", True, r"cnh|" + _NUMERO + r"\s+(?:da\s+)?cnh"),
    ("PASSAPORTE", True, r"passaporte"),
    ("CTPS", True, r"ctps"),
    ("BENEFICIO", True, r"nb|" + _NUMERO + r"\s+(?:do\s+)?benef[íi]cio"),
    ("REGISTRO_SAUDE", True, r"prontu[áa]rio|" + _NUMERO + r"\s+(?:do\s+)?prontu[áa]rio|dnv|aih"),
    ("MATRICULA_ESCOLAR", True, r"r\.?a\.?|matr[íi]cula\s+(?:escolar|acad[êe]mica)|registro\s+acad[êe]mico|"
                                r"c[óo]digo\s+do\s+alun[oa]"),
    ("DOCUMENTO", True, r"(?:" + _NUMERO + r"\s+(?:de\s+|da\s+)?)?inscri[çc][ãa]o(?:\s+" + _NUMERO + r")?"),
    ("DATA_NASCIMENTO", True, r"(?:data|dt\.?)\s*(?:de\s+)?nasc(?:imento|\.)?|nascimento|nasc\.?|d\.\s?n\.?|dn"),
    ("PROTOCOLO", False, r"protocolo|processo(?:\s+sei)?|requerimento|ait|auto(?:\s+de\s+infra[çc][ãa]o)?|"
                         r"" + _NUMERO + r"\s+(?:do\s+|da\s+)?(?:protocolo|processo|requerimento|ait|auto|"
                         r"notifica[çc][ãa]o)"),
    ("IDADE", False, r"idade"),
    ("CONTA_BANCARIA", False, r"ag(?:[êe]ncia|\.)?|ag[êe]ncia\s+banc[áa]ria|conta(?:\s+(?:corrente|banc[áa]ria|"
                              r"poupan[çc]a|sal[áa]rio))?|c/c|c\.c\.|cc|" + _NUMERO + r"\s+da\s+conta|"
                              r"ag(?:[êe]ncia|\.)?\s*/\s*conta"),
    ("VALOR_PESSOAL", False,
     r"(?:valor|vlr\.?)(?:\s+(?!unit|global|estimad|de\s+refer|or[çc]ad|contrat)[\w()/.]+){0,3}" + _EM_REAIS + r"|r\$|"
     r"(?:sal[áa]rio|remunera[çc][ãa]o|vencimentos?|proventos?|rendimentos?)"
     r"(?:\s+(?:b[áa]sic[oa]|bruto|l[íi]quido|mensal|total|base))?" + _EM_REAIS + r"|"
     r"venc\.?(?:\s+base)?|vantag(?:ens|\.)?|bruto|l[íi]quido|"
     r"desc(?:ontos?|\.)|bolsa|di[áa]rias?|multa|benef[íi]cio(?:\s+mensal)?|aux[íi]lio(?:\s+\w+)?|"
     r"renda(?:\s+(?:mensal|familiar|per\s+capita|bruta|l[íi]quida))?|pens[ãa]o|gratifica[çc](?:[ãa]o|[õo]es)|"
     r"adicional|indeniza[çc][ãa]o|ajuda\s+de\s+custo|abono|subs[íi]dio|honor[áa]rios|cach[êe]|"
     # "Total" sozinho também soma pontos ou horas; exige-se a indicação do valor em dinheiro.
     r"total(?:\s+(?:bruto|l[íi]quido|recebido|a\s+receber|pago|devido))" + _EM_REAIS + r"|"
     r"total\s*(?:\(\s*r\$\s*\)|em\s+r\$|r\$)"),
    ("TELEFONE", False, r"tel(?:efone|\.)?(?:\s*/\s*cel(?:ular|\.)?)?|fone|celular|cel\.|whats(?:app)?|"
                        r"telefone\s+(?:de\s+)?contato|contato"),
    ("EMAIL", False, r"e-?mail|correio\s+eletr[ôo]nico"),
    # Numa tabela, "Endereço" sozinho também é o da unidade de lotação; vale o de residência (ver
    # _ROTULO_ENDERECO_CAMPO para os formulários).
    ("ENDERECO", False, r"endere[çc]o\s+(?:residencial|de\s+resid[êe]ncia|d[oa]\s+(?:" + _PAPEIS_FORTES + r")"
                        + _FLEXAO + r")|resid[êe]ncia|domic[íi]lio"),
    ("CEP", False, r"cep"),
    ("PLACA", False, r"placa"),
    ("RENAVAM", False, r"renavam"),
    ("CHASSI", False, r"chassi"),
    ("SAUDE", False, r"diagn[óo]stico|cid(?:-?10)?|cid\s*/\s*diagn[óo]stico|doen[çc]as?|agravo|comorbidades?|"
                     r"defici[êe]ncia|tipo\s+de\s+defici[êe]ncia|patologia|enfermidade|morbidade|alergias?|"
                     r"imunobiol[óo]gico(?:\s*/\s*dose)?|vacinas?(?:\s*/\s*dose)?|medicamentos?|medica[çc][ãa]o|"
                     r"motivo\s+d[oa]\s+(?:afastamento|licen[çc]a)|condi[çc][ãa]o\s+de\s+sa[úu]de"),
    # "Cor" sozinho é também a cor do veículo; exige-se a raça no rótulo.
    ("ORIGEM_RACIAL", False, r"ra[çc]a(?:\s*/\s*cor)?|cor\s*/\s*ra[çc]a|cor\s+ou\s+ra[çc]a|etnia|"
                             r"autodeclara[çc][ãa]o(?:\s+[ée]tnico-racial)?"),
    ("RELIGIAO", False, r"religi[ãa]o|credo|confiss[ãa]o\s+religiosa"),
]
_ROTULOS_RE = [(tipo, forte, re.compile(expr, re.IGNORECASE)) for tipo, forte, expr in _ROTULOS]
#: Rótulos de coluna de pessoa jurídica: sem coluna de CPF, a tabela não é de pessoas naturais.
_ROTULO_EMPRESA = re.compile(r"cnpj|empresas?|raz[ãa]o\s+social|fornecedor(?:es|a)?|licitantes?|nome\s+fantasia|"
                             r"entidades?|institui[çc](?:[ãa]o|[õo]es)|organiza[çc](?:[ãa]o|[õo]es)|osc",
                             re.IGNORECASE)
#: Complemento do rótulo de unidade ou lugar: "Unidade de saúde", "Órgão de origem", "ESCOLA / LOTAÇÃO",
#: "DESTINO / PERÍODO".
_COMPLEMENTO = r"(?:\s+[\w.]+){0,3}(?:\s*/\s*[\w.]+(?:\s+[\w.]+){0,2})?"
#: Rótulos de coluna de lugar: o nome de pessoa na célula é o nome do município ou da localidade ("Sousa").
_ROTULO_LUGAR = re.compile(r"(?:munic[íi]pios?|cidades?|naturalidade|localidades?|bairros?|distritos?|comunidades?|"
                           r"origem|destino|local)" + _COMPLEMENTO, re.IGNORECASE)
#: Rótulos de coluna de órgão, unidade, estabelecimento ou empresa: o nome de pessoa na célula integra o nome
#: da unidade ("EE Professora Fulana de Tal", "UBS Doutor Fulano") e permanece legível.
_ROTULO_UNIDADE = re.compile(
    r"(?:nome\s+d[oa]\s+)?(?:escolas?|unidades?|lota[çc](?:[ãa]o|[õo]es)|[óo]rg[ãa]os?|setor(?:es)?|secretarias?|"
    r"polos?|campus|institui[çc][ãa]o|estabelecimentos?|hospita(?:l|is)|maternidade|creches?|regional|"
    r"diretorias?|ger[êe]ncias?|departamentos?|programas?|cursos?|projetos?|empresas?|raz[ãa]o\s+social|"
    r"fornecedor(?:es|a)?|entidades?|reservat[óo]rio|esta[çc][ãa]o|ponto\s+de\s+coleta|servi[çc]o)" + _COMPLEMENTO,
    re.IGNORECASE)


@dataclass(frozen=True)
class _Coluna:
    """Coluna tipificada pelo cabeçalho.

    Attributes:
        tipo: Código do tipo de dado das células ("" para coluna sem dado pessoal reconhecido).
        forte: O rótulo indica, por si, uma tabela de pessoas.
        empresa: O rótulo designa pessoa jurídica (CNPJ, razão social).
        unidade: Tipo atribuído ao nome de pessoa reconhecido numa célula de coluna de lugar
            (``LOCALIDADE``) ou de órgão, unidade, estabelecimento ou empresa (``UNIDADE_INSTITUCIONAL``);
            vazio nas demais colunas.
    """

    tipo: str = ""
    forte: bool = False
    empresa: bool = False
    unidade: str = ""


_SEM_TIPO = _Coluna()


def _limpar_rotulo(rotulo: str) -> str:
    return " ".join(rotulo.replace("*", " ").split()).strip(" :.-–").strip()


def tipificar(rotulo: str) -> _Coluna:
    """Tipo de dado de uma coluna, pelo texto do cabeçalho (a célula inteira).

    Example:
        >>> tipificar("DATA NASC.").tipo
        'DATA_NASCIMENTO'
        >>> tipificar("Unidade escolar").tipo
        ''
    """
    s = _limpar_rotulo(rotulo)
    if not s or len(s) > 45:
        return _SEM_TIPO
    for tipo, forte, expr in _ROTULOS_RE:
        if expr.fullmatch(s) or expr.fullmatch(rotulo.strip(" :")):
            return _Coluna(tipo, forte)
    empresa = _ROTULO_EMPRESA.fullmatch(s) is not None
    if _ROTULO_LUGAR.fullmatch(s):
        return _Coluna(empresa=empresa, unidade="LOCALIDADE")
    if empresa or _ROTULO_UNIDADE.fullmatch(s):
        return _Coluna(empresa=empresa, unidade="" if s.lower() == "cnpj" else "UNIDADE_INSTITUCIONAL")
    return _SEM_TIPO


#: Rótulo de endereço sem indicação de residência: no formulário de uma pessoa, é o endereço dela.
_ROTULO_ENDERECO_CAMPO = re.compile(r"endere[çc]o(?:\s+completo)?|end\.?|logradouro(?:\s+e\s+n[úu]mero)?",
                                    re.IGNORECASE)


def _tipificar_campo(rotulo: str) -> _Coluna:
    """Tipo de um campo de formulário (ver :func:`tipificar`), inclusive o endereço sem indicação de
    residência."""
    col = tipificar(rotulo)
    if not col.tipo and _ROTULO_ENDERECO_CAMPO.fullmatch(_limpar_rotulo(rotulo)):
        return _Coluna("ENDERECO")
    return col


def _tipificar_composto(rotulo: str) -> _Coluna:
    """Tipo de um rótulo que pode reunir dois cabeçalhos separados por um espaço ("CLASS. INSCRIÇÃO"):
    vale o rótulo inteiro ou, na falta dele, o rótulo reconhecido no início ou no fim, desde que o
    restante seja um rótulo curto (uma abreviatura ou uma palavra em caixa alta)."""
    col = tipificar(rotulo)
    if col.tipo or col.empresa or col.unidade:
        return col
    palavras = rotulo.split()
    for k in range(len(palavras) - 1, 0, -1):
        for parte, resto in ((palavras[k:], palavras[:k]), (palavras[:k], palavras[k:])):
            if len(resto) > 1 or not re.fullmatch(r"\p{Lu}[\p{Lu}.º°/]{0,11}", resto[0]):
                continue
            col = tipificar(" ".join(parte))
            if col.tipo or col.empresa:
                return col
    return _SEM_TIPO


# =========================================================================== forma dos valores
#: Valor monetário: "R$ 1.234,56", "1.234,56", "1200,00".
_DINHEIRO = re.compile(r"(?<![\d.,])(?:R\$\s?)?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}(?![\d,])")
#: Data: "12/03/1987", "12.03.87", "12 03 1987" e "12031987".
_DATA = re.compile(r"(?<![\d/.\-])(?P<d>\d{1,2})(?P<s>[/.\-]| ?)(?P<m>\d{1,2})(?P=s)(?P<a>(?:19|20)\d{2}|\d{2})"
                   r"(?![\d/.\-])")
#: Idade numa célula: "45", "45 anos", "7 meses".
_IDADE = re.compile(r"\d{1,3}(?:\s*(?:anos?|a|m[êe]s|meses|m))?", re.IGNORECASE)
#: Palavra de identificador: dígitos (ou máscara) com pontuação de documento e, no máximo, sigla ou dígito
#: verificador em letra ("140.496-ENF", "29.063/D", "52526-X", "***.306.237-**", "L0771838").
_PALAVRA_ID = re.compile(r"(?:[A-Z]{1,4}[-/]?)?[\d*•#][\d*•#.\-/]*(?:[\dXx*•#]|[-/][A-Z]{1,4})|"
                         r"[A-Z]{1,3}\d[\dA-Z]{3,}|\d+[A-Z]{1,3}\d+")
#: Formas que ocupam colunas de identificador sem serem identificadores: datas, horas e valores.
_NAO_ID = re.compile(r"\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{1,2}:\d{2}|.*,\d{2}|(?:19|20)\d{2}")
#: CNPJ, com ou sem pontuação.
_CNPJ = re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/\d{4}-?\d{2}(?!\d)")
_TELEFONE = re.compile(r"(?:\+?55\s?)?(?:\(?\d{2}\)?[\s.]?)?9?\s?\d{4}[\s.\-]?\d{4}")
_CEP = re.compile(r"\d{5}-?\d{3}|\d{2}\.\d{3}-\d{3}")
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_PLACA = re.compile(r"[A-Z]{3}-?\d[A-Z0-9]\d{2}", re.IGNORECASE)
_CHASSI = re.compile(r"[A-HJ-NPR-Z0-9]{17}", re.IGNORECASE)
#: Cor, raça ou etnia numa célula (classificação do IBGE e autodeclarações usuais).
_RACA = re.compile(r"\b(?:branc|pret|pard|amarel|ind[íi]gen|negr|quilombol|cafuz|mesti[çc]|mulat|etnia|povo)\w*",
                   re.IGNORECASE)
#: Endereço numa célula: começa por tipo de logradouro ou traz número ou "s/n".
_ENDERECO = re.compile(r"(?:rua|r\.|av(?:enida|\.)?|travessa|tv\.?|alameda|al\.|estrada|est\.|rodovia|rod\.|"
                       r"pra[çc]a|p[çc]\.|quadra|qd\.?|setor|s[íi]tio|fazenda|ch[áa]cara|povoado|linha|vila|beco|"
                       r"conjunto|q[nrs]\w?)\b.*|.*\b(?:\d+|s/n)\b.*", re.IGNORECASE)

#: Títulos, tratamentos e postos que antecedem o nome numa célula ("Prof. Dr.", "Enfª", "TÉC. ENF.",
#: "SD PM"); a normalização converte "ª" e "º" em "a" e "o". "MA." fica de fora: abrevia "Maria".
_TITULO = re.compile(
    r"(?:(?:prof|profa|profo|dr|dra|me|msc|esp|sr|sra|srta|enf|enfa|enfo|t[ée]c|aux|eng|agr|arq|adv|psic|nutr|"
    r"fisio|farm|odont|biom|cel|ten|cap|maj|sgt|sd|cb|subten|asp|pm|bm|gcm|qopm|cmt|esc|insp)\b\.?[ªºao]?\s*|"
    r"\d{1,2}[ºo°]\s+)+",
    re.IGNORECASE)
#: Palavras que, numa célula de nome, indicam pessoa jurídica, unidade ou ausência de nome.
_NAO_NOME = frozenset({
    "ltda", "eireli", "epp", "me", "s/a", "cia", "companhia", "empresa", "comercio", "comercial", "industria",
    "transportadora", "construtora", "distribuidora", "servicos", "associacao", "fundacao", "instituto",
    "cooperativa", "sindicato", "condominio", "consorcio", "secretaria", "prefeitura", "municipio", "estado",
    "governo", "ministerio", "departamento", "diretoria", "coordenacao", "gerencia", "divisao", "setor", "nucleo",
    "unidade", "escola", "colegio", "creche", "hospital", "clinica", "posto", "ubs", "usf", "caps", "cras", "creas",
    "universidade", "faculdade", "camara", "tribunal", "comarca", "vara", "delegacia", "batalhao", "conselho",
    "comissao", "programa", "vago", "vaga", "nenhum", "nenhuma", "outros", "outras", "idem", "total", "subtotal",
    "soma", "declarado", "declarada", "informado", "informada", "nao", "sim", "falecido", "ignorado", "consta"
})
_CONECTORES = frozenset({"de", "da", "do", "das", "dos", "e", "d'", "di", "del", "van", "von"})
#: Palavra de nome: inicial maiúscula (ou caixa alta), com acento, apóstrofo ou hífen interno, ou abreviada
#: ("Jr."); conectivo; inicial ("K.", "K.R.").
_PALAVRA_NOME = re.compile(r"(?:\p{Lu}[\p{L}'’\-]*\.?|d[aeo]s?|e|d['’]\p{Lu}[\p{L}]*)(?:,)?|"
                           r"\p{Lu}\.(?:\p{Lu}\.)*,?")
#: Numeração no início da célula ("01", "1º", "3.", "a)").
_NUMERACAO = re.compile(r"[\s\-–•]*(?:(?:\d{1,3}(?:[ºo°]|\.(?!\d)|\))?|[a-z]\))[\s\-–•]+)?")
#: Marca de célula sem valor.
_VAZIO = re.compile(r"[\s\-–—_.*x/]*|n/?[ad]|s/?[id]|n[ãa]o(?:\s+\w+)?|nenhum[a]?|sem\s+\w+|ignorad[oa]",
                    re.IGNORECASE)


@cache
def _nomes_conhecidos() -> frozenset[str]:
    """Prenomes e sobrenomes das listas do reconhecimento de nomes."""
    return nomes.prenomes() | nomes.sobrenomes()


@cache
def _nao_nomes() -> frozenset[str]:
    """Palavras que não compõem nome de pessoa: cargos, papéis e palavras comuns e administrativas das
    listas do reconhecimento de nomes ("Enfermeiro", "Famílias", "Assinatura") e as deste módulo, sem os
    prenomes e sobrenomes que coincidem com elas ("Câmara", "Pessoa")."""
    return (nomes.NAO_INICIAM_NOME | nomes.PALAVRAS_COMUNS | _NAO_NOME) - _nomes_conhecidos()


def _nome(texto: str, a: int, b: int, fragmento: bool = False) -> tuple[int, int] | None:
    """Trecho do nome de pessoa numa célula, sem título, posto ou numeração; ``None`` se a célula não
    tem a forma de um nome ("SÃO JOSÉ LTDA", "—", "Secretaria de Saúde", "Enfermeiro", "CPF").

    Uma só palavra (fora as iniciais) só é nome se constar das listas de prenomes e sobrenomes ou se
    for o ``fragmento`` de um nome partido entre duas linhas da célula ("FULANO DE" / "TAL").
    """
    m = _NUMERACAO.match(texto, a, b)
    if m:
        a = m.end()
    t = _TITULO.match(texto, a, b)
    if t:
        a = t.end()
    while b > a and texto[b - 1] in " ,;.–-":
        # O ponto da inicial final ("SOUZA, M. R.") pertence ao nome.
        if texto[b - 1] == "." and b - 2 >= a and texto[b - 2].isupper() and (b - 3 < a or not texto[b - 3].isalpha()):
            break
        b -= 1
    if b - a < 2:
        return None
    palavras = texto[a:b].split()
    if not 1 <= len(palavras) <= 10:
        return None
    # Rótulo de formulário ou cabeçalho repetido ("CPF", "NOME", "Servidor"); na continuação de um nome,
    # o sobrenome pode coincidir com um rótulo ("NASCIMENTO").
    col = _tipificar_campo(texto[a:b])
    if not fragmento and (col.tipo or col.unidade or col.empresa):
        return None
    significativas = []
    iniciais = 0
    for p in palavras:
        if not _PALAVRA_NOME.fullmatch(p):
            return None
        base = dobrar(p.strip(",.")).replace("’", "'")
        if base in _nao_nomes():
            return None
        if re.fullmatch(r"\p{Lu}\.(?:\p{Lu}\.)*,?", p):
            iniciais += 1
        elif base not in _CONECTORES and len(base) >= 2:
            significativas.append(base)
    if not significativas:
        # Só iniciais ("A. B."): exige ao menos duas.
        return (a, b) if iniciais >= 2 else None
    if len(significativas) == 1 and not iniciais and not fragmento and significativas[0] not in _nomes_conhecidos():
        return None
    return a, b


def _nome_confirmado(texto: str, a: int, b: int) -> bool:
    """Nome completo na célula: duas palavras ou mais, ou uma palavra com iniciais ("SOUZA, M. R."), com
    um prenome ou sobrenome das listas."""
    trecho = _nome(texto, a, b)
    if trecho is None:
        return False
    partes = [dobrar(p.strip(",.")) for p in texto[trecho[0]:trecho[1]].split()]
    significativas = [p for p in partes if p not in _CONECTORES and len(p) >= 2]
    iniciais = len(partes) - len(significativas) - sum(p in _CONECTORES for p in partes)
    return (len(significativas) >= 2 or (significativas and iniciais > 0)) and \
        any(p in _nomes_conhecidos() for p in significativas)


def _palavras(texto: str, tokens: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Identificadores entre as palavras de uma célula; palavras de identificador vizinhas, separadas
    por um espaço, formam um só valor ("013 524608-3", "4345 0201 2747")."""
    achados: list[tuple[int, int]] = []
    atual: tuple[int, int] | None = None
    for a, b in tokens:
        p = texto[a:b].strip(",;")
        ok = _PALAVRA_ID.fullmatch(p) is not None and not _NAO_ID.fullmatch(p) and \
            sum(c.isdigit() or c in "*•#" for c in p) >= 3
        if ok and atual is not None and a - atual[1] == 1:
            atual = (atual[0], a + len(p))
            continue
        if atual is not None:
            achados.append(atual)
        atual = (a, a + len(p)) if ok else None
    if atual is not None:
        achados.append(atual)
    return [(a, b) for a, b in achados if sum(c.isdigit() or c in "*•#" for c in texto[a:b]) >= 4]


def _data_valida(m: re.Match) -> bool:
    d, mes = int(m.group("d")), int(m.group("m"))
    if not (1 <= d <= 31 and 1 <= mes <= 12):
        return False
    # Sem separador, só a forma completa (ddmmaaaa) é uma data.
    return m.group("s") != "" or (len(m.group("d")) == 2 and len(m.group("m")) == 2 and len(m.group("a")) == 4)


def _valores(tipo: str, texto: str, tokens: list[tuple[int, int]],
             trecho: tuple[int, int] | None, fragmento: bool = False) -> list[tuple[int, int]]:
    """Valores com a forma do tipo numa célula.

    Args:
        tipo: Tipo da coluna.
        texto: Texto analisado.
        tokens: Palavras da célula, em posições do texto.
        trecho: Primeiro trecho da célula (palavras separadas por um espaço), usado nos tipos de texto
            livre — nome, endereço, saúde —, que não se estendem a uma coluna vizinha sem rótulo.
        fragmento: A célula continua, na linha de baixo, o nome da linha anterior (ver :func:`_nome`).
    """
    if not tokens:
        return []
    a, b = tokens[0][0], tokens[-1][1]
    celula = texto[a:b]
    if tipo == "NOME":
        if trecho is None:
            return []
        nome = _nome(texto, *trecho, fragmento=fragmento)
        return [nome] if nome else []
    if tipo == "VALOR_PESSOAL":
        return [(a + m.start(), a + m.end()) for m in _DINHEIRO.finditer(celula)]
    if tipo == "DATA_NASCIMENTO":
        return [(a + m.start(), a + m.end()) for m in _DATA.finditer(celula) if _data_valida(m)]
    if tipo == "IDADE":
        x, y = trecho or (a, b)
        return [(x, y)] if _IDADE.fullmatch(texto[x:y]) else []
    if tipo == "TELEFONE":
        return [(a + m.start(), a + m.end()) for m in _TELEFONE.finditer(celula)
                if sum(c.isdigit() for c in m.group()) >= 8]
    if tipo == "EMAIL":
        return [(a + m.start(), a + m.end()) for m in _EMAIL.finditer(celula)]
    if tipo == "CEP":
        return [(a + m.start(), a + m.end()) for m in _CEP.finditer(celula)]
    if tipo == "PLACA":
        return [(x, y) for x, y in tokens if _PLACA.fullmatch(texto[x:y])]
    if tipo == "CHASSI":
        return [(x, y) for x, y in tokens if _CHASSI.fullmatch(texto[x:y])]
    if tipo in ("ENDERECO", "SAUDE", "ORIGEM_RACIAL", "RELIGIAO"):
        if trecho is None:
            return []
        x, y = trecho
        valor = texto[x:y]
        if _VAZIO.fullmatch(valor) or not any(c.isalpha() for c in valor):
            return []
        if tipo == "ENDERECO" and not _ENDERECO.fullmatch(valor):
            return []
        if tipo == "ORIGEM_RACIAL" and not _RACA.search(valor):
            return []
        return [(x, y)]
    if tipo == "RENAVAM":
        return [(x, y) for x, y in tokens if re.fullmatch(r"\d{9,11}", texto[x:y])]
    return _palavras(texto, tokens)


#: Linha de totais, que soma valores de várias pessoas.
_TOTAL = re.compile(r"\b(?:sub)?tota(?:l|is)\b|\bsoma\b", re.IGNORECASE)
#: Palavras de pessoa jurídica numa linha de tabela de pessoas.
_PJ = re.compile(r"\b(?:ltda|eireli|s/a|s\.a\.|cia)\b|\s(?-i:ME|EPP)\s*$|"
                 r"\b(?:empresa|com[ée]rcio|comercial|ind[úu]stria|"
                 r"transportadora|construtora|distribuidora|associa[çc][ãa]o|funda[çc][ãa]o|instituto|cooperativa|"
                 r"sindicato|condom[íi]nio|cons[óo]rcio)\b", re.IGNORECASE)


# =========================================================================== estrutura do texto
def _linhas(texto: str) -> list[tuple[int, int]]:
    """Posições de início e fim (sem a quebra) de cada linha."""
    saida, pos = [], 0
    for linha in texto.split("\n"):
        fim = pos + len(linha)
        saida.append((pos, fim - 1 if linha.endswith("\r") else fim))
        pos = fim + 1
    return saida


_TRECHO = re.compile(r"\S+(?: \S+)*")
_TOKEN = re.compile(r"\S+")
#: Algarismos de dado numa linha de cabeçalho: número com três dígitos ou mais, data, valor, e-mail.
#: Números curtos ("01 02 03", dias de escala) e "(R$)" são admitidos.
_DADO_NO_CABECALHO = re.compile(r"\d{3,}|\d[.,/:]\d|@")


def _trechos(texto: str, a: int, b: int) -> list[tuple[int, int]]:
    """Trechos da linha separados por dois espaços ou mais."""
    return [m.span() for m in _TRECHO.finditer(texto, a, b)]


def _tokens(texto: str, a: int, b: int) -> list[tuple[int, int]]:
    return [m.span() for m in _TOKEN.finditer(texto, a, b)]


def _rotulo_plausivel(s: str) -> bool:
    """Indica se o trecho pode ser um rótulo de coluna: curto, sem dois-pontos seguidos de valor e sem
    algarismos de dado (admitidos números curtos, como os dias de uma escala)."""
    if re.fullmatch(r"\d{1,2}(?: \d{1,2})*", s):
        return True
    # Caixa de marcação ("( ) SERVIDOR  (X) PENSIONISTA") é opção de formulário, não rótulo de coluna.
    if len(s) > 45 or len(s.split()) > 6 or re.search(r":\s*\S|\(\s*[xX]?\s*\)", s):
        return False
    return s[:1].isupper() or s[:1] in "(Nº#" or s[:1].isdigit() and len(s) <= 3


@dataclass
class _Cabecalho:
    """Linha de cabeçalho de uma tabela alinhada por espaços.

    Attributes:
        inicio: Posição do início da linha no texto.
        trechos: Rótulos, como posições relativas ao início da linha.
        colunas: Tipo de cada rótulo.
    """

    inicio: int
    trechos: list[tuple[int, int]]
    colunas: list[_Coluna]

    @property
    def tipificadas(self) -> int:
        return sum(1 for c in self.colunas if c.tipo)

    @property
    def de_pessoas(self) -> bool:
        """Tabela de pessoas: coluna forte, sem coluna de pessoa jurídica (salvo havendo CPF)."""
        if not any(c.forte for c in self.colunas):
            return False
        return not any(c.empresa for c in self.colunas) or any(c.tipo == "CPF" for c in self.colunas)

    @property
    def identificada(self) -> bool:
        """Tabela com coluna de identificador pessoal (CPF, matrícula, data de nascimento…). Sem ela, o
        rótulo de nome ("Profissional", "Beneficiário") também encabeça categorias e contagens, e a
        tabela só é de pessoas se alguma célula trouxer um nome completo (ver :func:`_nome_confirmado`)."""
        return any(c.forte and c.tipo != "NOME" for c in self.colunas)


def _cabecalho_alinhado(texto: str, a: int, b: int) -> _Cabecalho | None:
    """Cabeçalho de tabela alinhada por espaços na linha ``texto[a:b]``, ou ``None``."""
    linha = texto[a:b]
    if "|" in linha or "\t" in linha or linha.count(";") >= 2 or _DADO_NO_CABECALHO.search(linha.replace("(R$)", "")):
        return None
    trechos = _trechos(texto, a, b)
    if len(trechos) < 2 or not all(_rotulo_plausivel(texto[x:y]) for x, y in trechos):
        return None
    colunas = [_tipificar_composto(texto[x:y]) for x, y in trechos]
    if not any(c.tipo for c in colunas):
        return None
    return _Cabecalho(a, [(x - a, y - a) for x, y in trechos], colunas)


def _prosa(texto: str, a: int, b: int) -> bool:
    """Linha de texto corrido, que encerra a tabela: um só trecho, sem recuo, com seis palavras ou mais."""
    trechos = _trechos(texto, a, b)
    return len(trechos) == 1 and trechos[0][0] == a and len(texto[a:b].split()) >= 6


@dataclass
class _Linha:
    """Linha de dados de uma tabela.

    Attributes:
        tokens: Palavras de cada coluna.
        trechos: Primeiro trecho de cada coluna.
        continuacao: A linha continua as células da linha anterior: não tem conteúdo na primeira coluna
            ou só tem conteúdo numa coluna, recuado em relação ao início dela.
    """

    tokens: list[list[tuple[int, int]]]
    trechos: list[tuple[int, int] | None]
    continuacao: bool


def _primeiros_trechos(texto: str, tokens: list[list[tuple[int, int]]]) -> list[tuple[int, int] | None]:
    """Primeiro trecho (palavras separadas por um espaço) das palavras de cada coluna."""
    saida: list[tuple[int, int] | None] = []
    for toks in tokens:
        if not toks:
            saida.append(None)
            continue
        x, y = toks[0]
        for p, q in toks[1:]:
            if p - y > 1:
                break
            y = q
        saida.append((x, y))
    return saida


class _Alinhada:
    """Tabela alinhada por espaços, com um ou dois cabeçalhos (registro em duas linhas)."""

    def __init__(self, texto: str, cabecalhos: list[_Cabecalho], linhas: list[tuple[int, int]]):
        self.texto = texto
        self.cabecalhos = cabecalhos
        self.linhas = linhas

    def _cabecalho_da_linha(self, a: int, b: int) -> int:
        """Índice do cabeçalho cujo recuo é o da linha (o mais próximo; o primeiro, no empate)."""
        if len(self.cabecalhos) == 1:
            return 0
        toks = _tokens(self.texto, a, b)
        recuo = toks[0][0] - a if toks else 0
        return min(range(len(self.cabecalhos)), key=lambda i: (abs(self.cabecalhos[i].trechos[0][0] - recuo), i))

    def _fronteiras(self, cab: _Cabecalho, linhas: list[tuple[int, int]]) -> list[int]:
        """Início de cada coluna (relativo ao início da linha).

        A coluna começa no rótulo ou, se os valores vierem alinhados à direita e começarem antes dele,
        logo depois da faixa em branco comum a todas as linhas que antecede o rótulo.
        """
        largura = max([cab.trechos[-1][1]] + [b - a for a, b in linhas])
        branco = [True] * (largura + 1)
        for a, b in [(cab.inicio, cab.inicio + cab.trechos[-1][1]), *linhas]:
            for p, ch in enumerate(self.texto[a:b]):
                if ch != " ":
                    branco[p] = False
        fronteiras = [0]
        for j in range(1, len(cab.trechos)):
            s, fim_anterior = cab.trechos[j][0], cab.trechos[j - 1][1]
            p = s
            while p - 1 >= fim_anterior and not branco[p - 1]:
                p -= 1
            fronteiras.append(p if p - 1 >= fim_anterior else s)
        return fronteiras

    def _linha(self, cab: _Cabecalho, fronteiras: list[int], a: int, b: int) -> _Linha:
        """Distribui as palavras da linha pelas colunas.

        Pela posição, cada palavra fica na coluna em que começa. Quando a linha tem um trecho por
        coluna, mas a posição reúne dois trechos numa só coluna (alinhamento perdido, como depois de
        reunir os caracteres de um campo em quadrícula), vale a ordem dos trechos.
        """
        n = len(cab.trechos)
        tokens: list[list[tuple[int, int]]] = [[] for _ in range(n)]
        for x, y in _tokens(self.texto, a, b):
            tokens[bisect_right(fronteiras, x - a) - 1].append((x, y))
        trechos = _trechos(self.texto, a, b)
        if len(trechos) == n:
            por_coluna = [sum(1 for x, _ in trechos if any(t[0] == x for t in toks)) for toks in tokens]
            if any(c > 1 for c in por_coluna):
                tokens = [_tokens(self.texto, x, y) for x, y in trechos]
        cheias = [i for i, toks in enumerate(tokens) if toks]
        continuacao = not tokens[0] or (n > 1 and len(cheias) == 1
                                        and tokens[cheias[0]][0][0] - a >= fronteiras[cheias[0]] + 2)
        return _Linha(tokens, _primeiros_trechos(self.texto, tokens), continuacao)

    def examinar(self, achados: _Achados) -> None:
        """Registra os valores das colunas tipificadas e as células das colunas de unidade."""
        texto = self.texto
        grupos: list[list[tuple[int, int]]] = [[] for _ in self.cabecalhos]
        for a, b in self.linhas:
            grupos[self._cabecalho_da_linha(a, b)].append((a, b))
        if not any(c.de_pessoas for c in self.cabecalhos):
            return
        tabela: list[tuple[_Cabecalho, list[tuple[int, int, _Linha]]]] = []
        for cab, linhas in zip(self.cabecalhos, grupos):
            if linhas and cab.tipificadas:
                fronteiras = self._fronteiras(cab, linhas)
                tabela.append((cab, [(a, b, self._linha(cab, fronteiras, a, b)) for a, b in linhas]))
        if not any(c.identificada for c in self.cabecalhos) and not any(
                _nome_confirmado(texto, *linha.trechos[i])
                for cab, linhas in tabela for _, _, linha in linhas
                for i, col in enumerate(cab.colunas) if col.tipo == "NOME" and linha.trechos[i]):
            return
        for cab, linhas in tabela:
            visto = ignorar = False
            nomes_anteriores: set[int] = set()
            for a, b, linha in linhas:
                if not linha.continuacao:
                    visto = True
                    ignorar = _linha_de_pj(texto, a, b, cab.colunas, linha.trechos)
                elif not visto:
                    # Antes do primeiro registro, a linha sem a primeira coluna e sem algarismos continua os
                    # rótulos ("VENC." / "BASE"), e não as células.
                    if not any(c.isdigit() for c in texto[a:b]):
                        continue
                    ignorar = _linha_de_pj(texto, a, b, cab.colunas, linha.trechos)
                if ignorar:
                    continue
                fragmentos = nomes_anteriores if linha.continuacao else set()
                nomes_da_linha = achados.linha(texto, cab.colunas, linha.tokens, linha.trechos, "tabela:alinhada",
                                               fragmentos=fragmentos)
                if not linha.continuacao:
                    nomes_anteriores = nomes_da_linha


def _linha_de_pj(texto: str, a: int, b: int, colunas: list[_Coluna],
                 trechos: list[tuple[int, int] | None]) -> bool:
    """Linha de pessoa jurídica numa tabela de pessoas: CNPJ na linha ou razão social na coluna de nome."""
    if _CNPJ.search(texto, a, b):
        return True
    for col, trecho in zip(colunas, trechos):
        if col.tipo == "NOME" and trecho is not None and _PJ.search(texto, *trecho):
            return True
    return False


@dataclass
class _Achados:
    """Resultado do exame da estrutura de um texto.

    Attributes:
        deteccoes: Valores das colunas e campos tipificados.
        unidades: Células das colunas de órgão, unidade, empresa ou lugar, com o tipo atribuído ao nome
            de pessoa reconhecido nelas (ver :attr:`_Coluna.unidade`).
    """

    deteccoes: list[Deteccao] = field(default_factory=list)
    unidades: list[tuple[int, int, str]] = field(default_factory=list)

    def valor(self, x: int, y: int, tipo: str, origem: str) -> None:
        origem = f"{origem}:{tipo.lower()}"
        if tipo == "ENDERECO":
            # O endereço passa pela mesma verificação de endereço do órgão que os demais reconhecedores
            # de endereço (ver themis_lgpd.reconhecedores.institucional).
            origem = "endereco:" + origem
        self.deteccoes.append(Deteccao(x, y, tipo, 0.85, origem, CONTEXTUAL, None, True))

    def linha(self, texto: str, colunas: list[_Coluna], tokens: list[list[tuple[int, int]]],
              trechos: list[tuple[int, int] | None], origem: str, valores: bool = True,
              fragmentos: set[int] = frozenset()) -> set[int]:
        """Registra uma linha de tabela: os valores das colunas tipificadas (se ``valores``) e as células
        das colunas de unidade.

        Args:
            fragmentos: Colunas cuja célula continua o nome reconhecido na linha anterior.

        Returns:
            As colunas em que um nome foi reconhecido.
        """
        com_nome: set[int] = set()
        for i, (col, toks, trecho) in enumerate(zip(colunas, tokens, trechos)):
            if col.unidade and toks:
                self.unidades.append((toks[0][0], toks[-1][1], col.unidade))
            if col.tipo and valores:
                for x, y in _valores(col.tipo, texto, toks, trecho, fragmento=i in fragmentos):
                    self.valor(x, y, col.tipo, origem)
                    if col.tipo == "NOME":
                        com_nome.add(i)
        return com_nome


def _tabelas_alinhadas(texto: str, linhas: list[tuple[int, int]], achados: _Achados) -> None:
    """Tabelas com colunas alinhadas por espaços (ver :class:`_Alinhada`)."""
    k = 0
    while k < len(linhas):
        cab = _cabecalho_alinhado(texto, *linhas[k])
        if cab is None:
            k += 1
            continue
        cabecalhos = [cab]
        rotulos = {" ".join(texto[slice(*linhas[k])].split())}
        k += 1
        # Registro em duas linhas: um segundo cabeçalho, com outro recuo, logo abaixo do primeiro.
        if k < len(linhas):
            segundo = _cabecalho_alinhado(texto, *linhas[k])
            if segundo is not None and segundo.trechos[0][0] != cab.trechos[0][0]:
                cabecalhos.append(segundo)
                rotulos.add(" ".join(texto[slice(*linhas[k])].split()))
                k += 1
        corpo: list[tuple[int, int]] = []
        while k < len(linhas):
            a, b = linhas[k]
            if not texto[a:b].strip() or _TOTAL.search(texto, a, b) or _prosa(texto, a, b):
                break
            # Cabeçalho repetido (nova página) ou de outra tabela. Uma linha de dados pode coincidir com
            # um rótulo ("Servidor"), mas não com dois.
            novo = _cabecalho_alinhado(texto, a, b)
            if novo is not None and (novo.tipificadas >= 2 or " ".join(texto[a:b].split()) in rotulos):
                break
            corpo.append((a, b))
            k += 1
        if corpo:
            _Alinhada(texto, cabecalhos, corpo).examinar(achados)


# =========================================================================== tabelas com separador
def _separador(linha: str) -> str:
    """Separador de colunas da linha: barra vertical, tabulação, ponto e vírgula ou nenhum."""
    if linha.count("|") >= 1 and linha.count("|") >= linha.count("\t"):
        return "|"
    if "\t" in linha:
        return "\t"
    return ";" if linha.count(";") >= 2 else ""


def _celulas(texto: str, a: int, b: int, sep: str) -> list[tuple[int, int]]:
    """Células da linha, sem espaços e aspas nas bordas; bordas vazias de "| a | b |" descartadas."""
    celulas, x = [], a
    for k in range(a, b + 1):
        if k == b or texto[k] == sep:
            p, q = x, k
            while p < q and texto[p] in " \t\"":
                p += 1
            while q > p and texto[q - 1] in " \t\"":
                q -= 1
            celulas.append((p, q))
            x = k + 1
    if sep == "|":
        if celulas and celulas[0][0] == celulas[0][1]:
            celulas.pop(0)
        if celulas and celulas[-1][0] == celulas[-1][1]:
            celulas.pop()
    return celulas


def _tabelas_com_separador(texto: str, linhas: list[tuple[int, int]], achados: _Achados) -> None:
    """Tabelas com colunas separadas por barra vertical, tabulação ou ponto e vírgula."""
    if "|" not in texto and "\t" not in texto and ";" not in texto:
        return
    cab: _Cabecalho | None = None
    sep_tabela = ""
    corpo: list[tuple[int, int, list[tuple[int, int]]]] = []
    for a, b in linhas:
        linha = texto[a:b]
        sep = _separador(linha)
        if cab is not None and sep != sep_tabela:
            _linhas_com_separador(texto, cab, corpo, achados)
            cab, corpo = None, []
        if not sep:
            continue
        celulas = _celulas(texto, a, b, sep)
        rotulos = [texto[x:y] for x, y in celulas]
        if len(celulas) >= 2 and not _DADO_NO_CABECALHO.search(linha.replace("(R$)", "")) \
                and all(_rotulo_plausivel(r) or not r for r in rotulos):
            novo = _Cabecalho(a, [], [tipificar(r) for r in rotulos])
            # Dentro de uma tabela, uma linha só é novo cabeçalho com dois rótulos tipificados: uma
            # célula de dados pode coincidir com um rótulo ("Servidor", "Titular").
            if novo.tipificadas >= (2 if cab is not None else 1):
                if cab is not None:
                    _linhas_com_separador(texto, cab, corpo, achados)
                cab, sep_tabela, corpo = (novo, sep, []) if novo.de_pessoas else (None, "", [])
                continue
        if cab is not None and not _TOTAL.search(linha):
            corpo.append((a, b, celulas))
    if cab is not None:
        _linhas_com_separador(texto, cab, corpo, achados)


def _linhas_com_separador(texto: str, cab: _Cabecalho, corpo: list[tuple[int, int, list[tuple[int, int]]]],
                          achados: _Achados) -> None:
    """Registra as linhas de uma tabela com separador (ver :func:`_tabelas_com_separador`)."""
    colunas = cab.colunas
    registros = []
    for a, b, celulas in corpo:
        # Linhas com colunas vazias no fim ("a;b;;;") são completadas; as de outra largura, ignoradas.
        celulas = celulas + [(b, b)] * (len(colunas) - len(celulas))
        if len(celulas) != len(colunas) and any(x < y for x, y in celulas[len(colunas):]):
            continue
        celulas = celulas[:len(colunas)]
        tokens = [_tokens(texto, x, y) for x, y in celulas]
        registros.append((a, b, tokens, [(x, y) if x < y else None for x, y in celulas]))
    if not cab.identificada and not any(_nome_confirmado(texto, *trechos[i])
                                        for _, _, _, trechos in registros
                                        for i, col in enumerate(colunas) if col.tipo == "NOME" and trechos[i]):
        return
    ignorar = False
    nomes_anteriores: set[int] = set()
    for a, b, tokens, trechos in registros:
        continuacao = not tokens[0] and any(tokens)
        if not continuacao:
            ignorar = _linha_de_pj(texto, a, b, colunas, trechos)
        nomes_da_linha = achados.linha(texto, colunas, tokens, trechos, "tabela:separador", valores=not ignorar,
                                       fragmentos=nomes_anteriores if continuacao else set())
        if not continuacao:
            nomes_anteriores = nomes_da_linha


# =========================================================================== formulários
def _formulario_vertical(texto: str, linhas: list[tuple[int, int]], achados: _Achados) -> None:
    """Rótulo sozinho numa linha e o valor na linha de baixo ("NOME COMPLETO" / "FULANO DE TAL").

    Vale para rótulos fortes; os demais (endereço, telefone, valor) só num formulário de pessoa, com
    um rótulo forte a até oito linhas.
    """
    candidatos: list[tuple[int, _Coluna, tuple[int, int]]] = []
    for k in range(len(linhas) - 1):
        a, b = linhas[k]
        s = texto[a:b].strip()
        if not s or len(s) > 45 or any(c.isdigit() for c in s) or len(_trechos(texto, a, b)) != 1:
            continue
        col = _tipificar_campo(s)
        if not col.tipo:
            continue
        x, y = linhas[k + 1]
        trechos = _trechos(texto, x, y)
        if len(trechos) != 1 or len(texto[x:y].strip()) > 80:
            continue
        candidatos.append((k, col, trechos[0]))
    fortes = [k for k, col, _ in candidatos if col.forte]
    for k, col, (x, y) in candidatos:
        if not col.forte and not any(abs(k - f) <= 8 for f in fortes):
            continue
        for p, q in _valores(col.tipo, texto, _tokens(texto, x, y), (x, y)):
            # Sob o rótulo de nome, o nome completo: uma só palavra pode ser outro rótulo do formulário.
            if col.tipo == "NOME" and len([w for w in texto[p:q].split() if len(w) > 2]) < 2:
                continue
            achados.valor(p, q, col.tipo, "tabela:formulario")


def _colunas_em_bloco(texto: str, linhas: list[tuple[int, int]], achados: _Achados) -> None:
    """Colunas extraídas uma depois da outra: o rótulo de cada coluna seguido dos seus N valores.

    Num trecho sem linhas em branco, os rótulos tipificados, todos distintos, devem estar a intervalos
    de N + 1 linhas (ou múltiplos, quando há colunas sem rótulo reconhecido entre eles), com N de dois
    ou mais. Pares de rótulo e valor repetidos ("NOME" / nome / "CARGO" / cargo / "NOME" / …) não são
    colunas: o mesmo rótulo aparece mais de uma vez.
    """
    k = 0
    while k < len(linhas):
        # Trecho de linhas não vazias.
        f = k
        while f < len(linhas) and texto[linhas[f][0]:linhas[f][1]].strip():
            f += 1
        if f - k >= 5:
            _bloco_de_colunas(texto, linhas[k:f], achados)
        k = f + 1


def _bloco_de_colunas(texto: str, linhas: list[tuple[int, int]], achados: _Achados) -> None:
    rotulos: list[tuple[int, _Coluna]] = []
    for i, (a, b) in enumerate(linhas):
        s = texto[a:b].strip()
        if len(s) <= 45 and not any(c.isdigit() for c in s) and len(_trechos(texto, a, b)) == 1:
            col = tipificar(s)
            if col.tipo:
                rotulos.append((i, col))
    if len(rotulos) < 2 or not any(col.forte for _, col in rotulos):
        return
    textos_dos_rotulos = [dobrar(" ".join(texto[slice(*linhas[i])].split())) for i, _ in rotulos]
    if len(set(textos_dos_rotulos)) < len(textos_dos_rotulos):
        return
    intervalos = [j - i - 1 for (i, _), (j, _) in zip(rotulos, rotulos[1:])]
    n = min(intervalos)
    if n < 2 or any((g + 1) % (n + 1) for g in intervalos) or rotulos[-1][0] + n >= len(linhas):
        return
    valores = [linhas[i + 1:i + 1 + n] for i, _ in rotulos]
    if any(len(texto[a:b].strip()) > 80 for grupo in valores for a, b in grupo):
        return
    # Coluna de nomes sem nenhum nome completo: a estrutura não é uma relação de pessoas.
    if any(col.tipo == "NOME" and not any(_nome_confirmado(texto, a, b) for a, b in grupo)
           for (_, col), grupo in zip(rotulos, valores)):
        return
    achados_bloco: list[tuple[int, int, str]] = []
    for (_, col), grupo in zip(rotulos, valores):
        da_coluna = []
        for a, b in grupo:
            trechos = _trechos(texto, a, b)
            if len(trechos) != 1 or (col.tipo == "NOME" and _PJ.search(texto, a, b)):
                continue
            da_coluna += [(p, q, col.tipo) for p, q in _valores(col.tipo, texto, _tokens(texto, a, b), trechos[0])]
        # Em cada coluna, ao menos dois terços dos valores têm a forma do tipo; senão, os "valores" são
        # outros rótulos e campos de um formulário.
        if len(da_coluna) * 3 < n * 2:
            return
        achados_bloco += da_coluna
    for p, q, tipo in achados_bloco:
        achados.valor(p, q, tipo, "tabela:bloco")


#: Rótulo de campo sem valor na mesma linha: "Nome:", "CPF/CNPJ:", "Valor da venda (R$):".
_ROTULO_CAMPO = re.compile(r"\s*(?P<r>[^\W\d][^:\n]{0,44}):\s*")
#: Título de seção entre os rótulos de um formulário: "2. DADOS DO VENDEDOR".
_TITULO_SECAO = re.compile(r"\s*(?:\d{1,2}[.)]\s*)?[^\W\d][^:\n]{2,60}")


def _formulario_em_bloco(texto: str, linhas: list[tuple[int, int]], achados: _Achados) -> None:
    """Rótulos de campo em sequência e, adiante, os valores na mesma ordem e em igual número.

    A extração de texto de formulários eletrônicos põe os rótulos impressos de um lado e o conteúdo
    dos campos de outro. Pelo menos três rótulos, um deles forte; o bloco de valores é o primeiro
    trecho de linhas não vazias, até 40 linhas adiante, com exatamente o mesmo número de linhas, e ao
    menos dois terços dos campos tipificados têm, na posição correspondente, um valor com a forma do
    tipo (um bloco qualquer de mesmo tamanho, como uma assinatura, não serve).
    """
    k = 0
    while k < len(linhas):
        rotulos: list[_Coluna] = []
        j = k
        while j < len(linhas):
            a, b = linhas[j]
            m = _ROTULO_CAMPO.fullmatch(texto, a, b)
            if m:
                rotulos.append(_tipificar_campo(m.group("r")))
            elif not (rotulos and _TITULO_SECAO.fullmatch(texto, a, b)):
                break
            j += 1
        if len(rotulos) < 3 or not any(c.forte for c in rotulos):
            k = j + 1 if j > k else k + 1
            continue
        valores = _bloco_de_valores(texto, linhas, j, len(rotulos))
        encontrados: list[tuple[int, int, str]] = []
        for col, (a, b) in zip(rotulos, valores):
            if not col.tipo or (col.tipo == "NOME" and _PJ.search(texto, a, b)):
                continue
            trechos = _trechos(texto, a, b)
            encontrados += [(p, q, col.tipo) for p, q in
                            _valores(col.tipo, texto, _tokens(texto, a, b), trechos[0] if trechos else None)]
        if len({p for p, _, _ in encontrados}) * 3 >= sum(1 for c in rotulos if c.tipo) * 2:
            for p, q, tipo in encontrados:
                achados.valor(p, q, tipo, "tabela:campos")
        k = j


def _bloco_de_valores(texto: str, linhas: list[tuple[int, int]], inicio: int, n: int) -> list[tuple[int, int]]:
    """Primeiro trecho de linhas não vazias com exatamente ``n`` linhas curtas, sem rótulo de campo."""
    k = inicio
    limite = min(len(linhas), inicio + 40)
    while k < limite:
        a, b = linhas[k]
        if not texto[a:b].strip():
            k += 1
            continue
        f = k
        while f < len(linhas) and texto[linhas[f][0]:linhas[f][1]].strip():
            f += 1
        bloco = linhas[k:f]
        if any(_ROTULO_CAMPO.fullmatch(texto, a, b) for a, b in bloco):
            return []
        if f - k == n and all(len(texto[a:b].strip()) <= 100 for a, b in bloco):
            return bloco
        k = f
    return []


# =========================================================================== reconhecedor
#: Tipos produzidos pelo reconhecedor.
TIPOS = sorted({tipo for tipo, _, _ in _ROTULOS})


#: Último texto examinado e o resultado: o reconhecedor e :func:`preservar_unidades` examinam o mesmo
#: texto em seguida; a atribuição única da tupla é segura entre threads.
_ULTIMO: tuple[str, _Achados] = ("", _Achados())


def examinar(texto: str) -> _Achados:
    """Valores das colunas e campos tipificados e células das colunas de unidade do texto."""
    global _ULTIMO
    ultimo = _ULTIMO
    if ultimo[0] == texto:
        return ultimo[1]
    achados = _Achados()
    if "\n" in texto:
        linhas = _linhas(texto)
        _tabelas_com_separador(texto, linhas, achados)
        if "  " in texto:
            _tabelas_alinhadas(texto, linhas, achados)
        _formulario_vertical(texto, linhas, achados)
        _colunas_em_bloco(texto, linhas, achados)
        if ":" in texto:
            _formulario_em_bloco(texto, linhas, achados)
    _ULTIMO = (texto, achados)
    return achados


def preservar_unidades(texto: str, deteccoes: list[Deteccao]) -> None:
    """Reclassifica os nomes de pessoa reconhecidos dentro de células de colunas de órgão, unidade,
    empresa ou lugar ("EE Professora Fulana de Tal" na coluna "Lotação", "Sousa" na coluna "Destino").

    O nome de pessoa que integra o nome de uma instituição, unidade ou lugar permanece legível; a
    coluna da tabela informa que a célula é uma unidade, e não uma pessoa. O achado passa a
    ``UNIDADE_INSTITUCIONAL`` ou ``LOCALIDADE``, que o perfil LAI sinaliza para revisão e que impede a
    propagação, para dentro da célula, do sobrenome de uma pessoa tarjada em outro ponto. A lista é
    alterada no lugar.

    Args:
        texto: Texto analisado (normalizado).
        deteccoes: Achados de todos os reconhecedores no texto.
    """
    unidades = sorted(examinar(texto).unidades)
    if not unidades:
        return
    inicios = [a for a, _, _ in unidades]
    for k, d in enumerate(deteccoes):
        if d.tipo != "NOME":
            continue
        i = bisect_right(inicios, d.inicio) - 1
        if i >= 0 and d.fim <= unidades[i][1]:
            deteccoes[k] = Deteccao(d.inicio, d.fim, unidades[i][2], d.score, d.origem + "+tabela:unidade", d.camada,
                                    d.validado, True)


class ReconhecedorTabelas:
    """Dados pessoais em tabelas, listas e formulários, tipificados pelo rótulo da coluna ou do campo."""

    nome = "tabelas"

    def detectar(self, texto: str) -> list[Deteccao]:
        return list(examinar(texto).deteccoes)
