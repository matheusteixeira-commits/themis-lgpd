"""Reconhecedores de endereço, CEP e localidade.

Além do formato "logradouro, número", o módulo reconhece o endereçamento próprio de Brasília e das
regiões administrativas do Distrito Federal, baseado em siglas de setor e em quadra, conjunto e
casa ("SQS 308 Bloco C Apto 602", "QNM 12 Conjunto B Casa 4"), que não contém logradouro nem
número no sentido usual.

O nome de uma cidade ou região administrativa isolado é um quase-identificador
(``LOCALIDADE``): por si só não identifica ninguém e, em geral, é apenas sinalizado. Quando aparece
como local de residência ("moro em Taguatinga"), passa a ser tratado como endereço.
"""

from __future__ import annotations

import regex as re

from .base import ANTES_NUM, CONTEXTUAL, DEPOIS_NUM, Deteccao, Padrao, ReconhecedorPadroes

#: Expressões que indicam local de residência; elevam a confiança dos endereços.
CTX_RESIDENCIA = (
    r"moro", r"resido", r"residente", r"resid[êe]ncia", r"endere[çc]o", r"domicili\w*", r"minha casa",
    r"mora(?:mos)?", r"morador[a]?", r"reside", r"residimos", r"im[óo]vel", r"localizad[oa]",
)

#: Rótulo de um componente de endereço (conjunto, casa, lote, bloco, apartamento, quadra…).
_COMPONENTE = (
    r"\b(?:conjunto|conj\.?|cj\.?|casa|cs\.?|lote|lt\.?|bloco|bl\.?|apartamento|apto\.?|ap\.?|sala|loja|"
    r"quadra|qd\.?|rua|alameda|al\.|avenida|av\.|travessa|ch[áa]cara|ch\.?|m[óo]dulo|proje[çc][ãa]o|edif[íi]cio|"
    r"ed\.|andar|km|torre|unidade|trecho|(?:BR|DF|GO|MG)-?|n[º°o]\.?|n[úu]mero)"
)
#: Valor de um componente: número ("12", "602-A") ou letra isolada ("B"). Nunca uma palavra — o que
#: impede que "ch" + "ão" de "chão" seja lido como "chácara ão".
_VALOR_COMP = r"(?:\d[\dA-Z\-/]{0,5}|[A-Z](?:-?\d{1,4})?)(?![\wÀ-ú])"
#: Sequência de até oito componentes após o início do endereço.
_COMPONENTES = rf"(?:\s*[,\-–]?\s*{_COMPONENTE}\s*{_VALOR_COMP}){{0,8}}"
#: Nome do logradouro: não atravessa fim de frase; o ponto só é aceito após abreviações de títulos
#: ("Rua Dr. Fulano", "Av. Gov. Beltrano").
_NOME_LOGRADOURO = (r"(?:[^\n,;:()!?\d.]|(?<=\b(?:Dr|Dra|Prof|Gov|Pres|Sen|Dep|Mal|Gal|Cel|Cap|Ten|Sto|Sta|Pe|Fr|D|S))\.)"
                    r"{2,60}?")
#: Complementos opcionais do endereço: bairro, cidade e UF, CEP (", Bairro Vila Nova",
#: ", Joinville - SC", ", Brasília/DF, CEP 70000-000").
_CAUDA = (
    r"(?:\s*,\s*(?:bairro|setor|jardim|vila|parque|residencial|condom[íi]nio)\s+[^\n,;.\d]{2,40})?"
    r"(?:\s*,\s*[A-ZÀ-Ú][^\n,;.\d]{1,35}?\s*[-/–,]\s*(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|"
    r"RS|RO|RR|SC|SP|SE|TO)(?![\w]))?"
    r"(?:\s*,?\s*CEP\s*[:\-]?\s*\d{5}\s?-?\s?\d{3})?"
)

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
           r"\b(?:rua|r\.|avenida|av\.?|alameda|al\.|travessa|tv\.|rodovia|rod\.|estrada|estr\.|pra[çc]a|largo|"
           r"viela|beco|servid[ãa]o|vila|conjunto habitacional|condom[íi]nio|ch[áa]cara|"
           r"s[íi]tio|fazenda|n[úu]cleo rural|col[ôo]nia agr[íi]cola|setor habitacional|acampamento)\s+"
           + _NOME_LOGRADOURO + r"\s*,?\s*(?:(?:n[º°o]?\.?\s*|n[úu]mero\s*)?(?:\d{1,6}[A-Za-z]?|s/?n)(?![\w/])|"
           + _COMPONENTE + r"\s*" + _VALOR_COMP + r")" + _COMPONENTES + _CAUDA,
           0.85, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:logradouro"),
    # Endereçamento do DF: até duas siglas de setor seguidas de sigla, quadra ou conjunto e número.
    # A confiança é ajustada pelo número de componentes (ver ReconhecedorEndereco).
    Padrao("ENDERECO",
           rf"\b(?:(?:{_SIGLAS_DF})\s+){{0,2}}(?:{_SIGLAS_DF}|quadra|qd\.?|q\.|conjunto|conj\.?|cj\.?)\s*\d{{1,4}}[A-Z]?"
           r"(?:\s+(?:sul|norte|leste|oeste))?\b" + _COMPONENTES + _CAUDA,
           0.6, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:df"),
    # Áreas rurais: rodovia e quilômetro, com chácara, sítio ou lote ("DF-001, km 12, Chácara 5").
    Padrao("ENDERECO",
           r"\b(?:BR|DF|GO|MG|SP|RJ|BA|PR|SC|RS|MT|MS|TO)[-\s]?\d{3}\s*,?\s*km\s*\d{1,4}(?:[.,]\d)?"
           r"(?:\s*,\s*(?:ch[áa]cara|s[íi]tio|fazenda|lote|n[úu]cleo|condom[íi]nio)[^\n,;]{0,40})*", 0.8,
           contexto=CTX_RESIDENCIA, janela=60, nome="endereco:rodovia"),
    Padrao("ENDERECO",
           r"\bkm\s*\d{1,4}(?:[.,]\d)?\s+d[ao]\s+(?:rodovia\s+)?(?:BR|DF|GO|MG|SP|RJ|BA)[-\s]?\d{3}"
           r"(?:\s*[,\-–]\s*(?:ch[áa]cara|s[íi]tio|fazenda|lote|n[úu]cleo(?:\s+rural)?|condom[íi]nio)[^\n,;.]{0,40})*",
           0.8, contexto=CTX_RESIDENCIA, janela=60, nome="endereco:km-rodovia"),
]

#: Componente com valor, usado para medir quão completo é um endereço do DF.
_COMP_RE = re.compile(_COMPONENTE + r"\s*" + _VALOR_COMP, re.IGNORECASE)

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
        """Achados de todas as regras, com a confiança do endereçamento do DF ajustada."""
        saida = []
        for d in super().detectar(texto):
            if d.origem == "endereco:df":
                trecho = texto[d.inicio:d.fim]
                componentes = len(_COMP_RE.findall(trecho))
                if componentes >= 2:
                    d.score = max(d.score, 0.85)
                elif componentes == 1:
                    d.score = max(d.score, 0.75)
            saida.append(d)
        return saida


#: Nome de região administrativa, com qualificador opcional ("Riacho Fundo II", "Gama Leste").
#: Sensível a maiúsculas: nomes próprios, para não confundir "gama" ou "estrutural" com palavras comuns.
_LOCALIDADES = re.compile(
    r"\b(?:" + "|".join(re.escape(r).replace(r"\ ", r"\s+") for r in sorted(REGIOES_DF, key=len, reverse=True))
    + r")(?:\s+(?:Norte|Sul|Centro|Leste|Oeste|I{1,3}))?\b"
)


class ReconhecedorLocalidade:
    """Cidade ou região administrativa citada no texto.

    Isolada, é quase-identificador (``LOCALIDADE``), sinalizado para revisão e tarjado apenas no
    perfil de proteção máxima. Precedida de expressão de residência ("resido em Taguatinga"), é
    local de moradia e recebe o tipo ``ENDERECO``.
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
        return saida


#: Expressão de residência imediatamente antes da localidade ("moro em", "residente no").
_RESIDE = re.compile(r"\b(?:resido|moro|reside|mora|moramos|residente|domiciliad[oa]|morador(?:a)?)"
                     r"(?:\s+(?:em|no|na|n[oa]s|d[aoe]))+\s*$", re.IGNORECASE)


def reconhecedores():
    """Reconhecedores deste módulo, na forma esperada por :mod:`themis_lgpd.analisador`."""
    return [ReconhecedorEndereco(), ReconhecedorLocalidade()]
