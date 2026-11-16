"""Reconhecedores de idade, de data de nascimento em tabelas e de valores monetários de pessoa natural.

Idade e valor recebido ou devido por alguém só são dado pessoal quando se referem a uma pessoa
identificável; os mesmos números em normas, editais, estatísticas e contratos com empresas são
informação pública (LAI, arts. 3º e 8º). Por isso as regras deste módulo dependem do contexto:

Idade (tipo ``IDADE``)
    Campo de formulário ("Idade: 63 anos", "Idade: 47 a"), aposto junto ao nome, às iniciais ou ao
    papel da pessoa ("Fulano, 45 anos, CPF…", "a filha, A. B. C., de 6 anos", "um sobrinho de 10
    anos"), idade com verbo ("hoje com 2 anos", "contava 19 anos", "tem 9 anos"), "60 (sessenta) anos
    de idade", idade ao lado da data de nascimento e coluna "Idade" de tabelas de pessoas. Ficam
    legíveis faixas e requisitos ("de 11 a 14 anos", "idade mínima de 18 anos", "maiores de 60
    anos"), durações ("há 14 anos", "pena de 5 anos", "36 anos de contribuição"), grupos ("pessoas
    com 60 anos") e a idade em que algo ocorreu ("aos 15 anos").
Data de nascimento em tabela (tipo ``DATA_NASCIMENTO``)
    Datas na coluna "Nascimento" ou "Data de nascimento" de tabelas com colunas separadas por barra
    vertical ou tabulação. A data precedida de "nascido em", "Data de nascimento:" etc. é reconhecida
    em :mod:`themis_lgpd.reconhecedores.documentos`.
Valor monetário de pessoa natural (tipo ``VALOR_PESSOAL``)
    Valor que a expressão mais próxima vincula a uma pessoa — remuneração, salário, renda, benefício,
    pensão, aluguel, dívida, desconto em folha, multa, prejuízo alegado, bem subtraído ou avaliado —,
    valores em tabelas de pessoas (com coluna de nome, parentesco, CPF ou matrícula) e valores em
    declarações de bens e em extratos de contrato ou termo de outorga com pessoa física. Quando a
    expressão mais próxima é de valor público — contrato, licitação, orçamento, dotação, repasse,
    empresa, erário, valor estimado, tabela ou valor fixado em norma —, o valor permanece legível.
"""

from __future__ import annotations

from collections.abc import Iterator

import regex as re

from .base import CONTEXTUAL, Deteccao

# =========================================================================== idade
#: Número de anos com extenso opcional entre parênteses: "60 (sessenta)".
_NUMERO = r"\d{1,3}(?:\s*\([^()\d\n]{2,40}\))?"
#: Idade: "45 anos", "1 ano", "7 meses", "5 anos e 9 meses", "60 (sessenta) anos".
_IDADE = (r"(?:" + _NUMERO + r"\s+(?:anos?|m[êe]s(?:es)?)\b"
          r"(?:\s*(?:,|e)\s*\d{1,2}(?:\s*\([^()\d\n]{2,30}\))?\s+(?:m[êe]s(?:es)?|dias?)\b)?)")

#: Continuações que fazem do número uma faixa, um requisito ou uma duração, e não a idade de alguém:
#: "60 anos ou mais", "6 a 14 anos", "36 anos de contribuição", "2 anos depois".
_NAO_IDADE_DEPOIS = (
    r"(?!\s*(?:ou\s+(?:mais|menos)|completos|incompletos|(?:a|à|ao|e|at[ée])\s+\d|"
    r"de\s+(?:contribui|servi[çc]o|reclus|deten|pris|carreira|exerc[íi]cio|atividade|experi[êe]ncia|efetivo|casa|"
    r"empresa|fun[çc]|mandato|vig[êe]ncia|dura[çc]|hist[óo]ria|exist[êe]ncia|funcionamento|tradi[çc]|estudo|"
    r"escolaridade|car[êe]ncia|prescri|pena|trabalho|profiss|uso|tratamento|acompanhamento|doen[çc]a|evolu[çc]|"
    r"diagn[óo]stico|casad|uni[ãa]o|resid|moradia|perman[êe]ncia|licen[çc]a|f[ée]rias|afastamento|gozo|"
    r"aus[êe]ncia|atraso|espera|idade\s+(?:m[íi]nima|m[áa]xima))|"
    r"atr[áa]s|depois|antes|ap[óo]s|seguidos|consecutivos|ininterruptos))")

#: Palavras que, pouco antes do número, indicam faixa, requisito, estimativa ou grupo de pessoas:
#: "idade mínima de", "maiores de", "a partir de", "pessoas com", "quem tem", "cerca de".
_NAO_IDADE_ANTES = re.compile(
    r"\b(?:m[íi]nim[oa]|m[áa]xim[oa]|limite|superior|inferior|acima|abaixo|maiores|menores|mais|menos|at[ée]|"
    r"partir|entre|faixa|cerca|aproximadamente|aparentando|aparenta|igual|quem|"
    r"pessoas|idos[oa]s|crian[çc]as|adolescentes|jovens|mulheres|homens|candidat[oa]s|servidor(?:es|as)|alun[oa]s|"
    r"estudantes|pacientes|benefici[áa]ri[oa]s|segurad[oa]s|aposentad[oa]s|trabalhador(?:es|as)|indiv[íi]duos|"
    r"cidad[ãa]os|popula[çc][ãa]o|grupos?|p[úu]blico|usu[áa]ri[oa]s|filhos|netos|dependentes)\b[^.;\n]{0,12}$",
    re.IGNORECASE)

#: Iniciais de pessoa: "K.C.P.", "K. M. P.", "A.F.L.".
_INICIAIS = r"(?:\b[A-ZÀ-Ú]\.\s?){2,}(?:[A-ZÀ-Ú]\b\.?)?"
#: Nome próprio de duas palavras ou mais, em caixa normal ou alta, com conectores.
_NOME = (r"(?:\b[A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:(?:d[aeo]s?|e)\s+)?[A-ZÀ-Ú][a-zà-ú]+)+|"
         r"\b[A-ZÀ-Ú]{2,}(?:\s+(?:(?:D[AEO]S?|E)\s+)?[A-ZÀ-Ú]{2,})+)")
#: Papéis, parentescos e qualificações que designam uma pessoa determinada.
_PAPEL = (r"(?i:filh[oa]|irm[ãa]o?|m[ãa]e|pai|genitor[a]?|av[ôóo]|bisav[ôó]|net[oa]|bisnet[oa]|sobrinh[oa]|"
          r"ti[oa]|prim[oa]|entead[oa]|padrasto|madrasta|sogr[oa]|cunhad[oa]|genro|nora|companheir[oa]|espos[oa]|"
          r"marido|c[ôo]njuge|crian[çc]a|adolescente|beb[êe]|rec[ée]m-nascid[oa]|menor|menina|menino|garot[oa]|"
          r"jovem|rapaz|mo[çc]a|senhor[a]?|homem|mulher|indiv[íi]duo|paciente|v[íi]tima|autor[a]?|autuad[oa]|"
          r"r[ée]u|acusad[oa]|denunciad[oa]|indiciad[oa]|investigad[oa]|apenad[oa]|custodiad[oa]|requerente|requerid[oa]|"
          r"interessad[oa]|assistid[oa]|usu[áa]ri[oa]|idos[oa]|servidor[a]?|declarante|testemunha|"
          r"benefici[áa]ri[oa]|segurad[oa]|pensionista|aposentad[oa]|titular|respons[áa]vel|curatelad[oa]|"
          r"interditad[oa]|tutelad[oa]|alun[oa]|estudante|sexo\s+(?:masculino|feminino)|brasileir[oa]|"
          r"estrangeir[oa]|solteir[oa]|casad[oa]|divorciad[oa]|separad[oa]|vi[úu]v[oa]|"
          r"natural\s+de\s+[^\W\d_][\w\s/-]{1,30})")
#: Fim de trecho que designa uma pessoa: iniciais, nome, ou papel seguido opcionalmente do nome.
_PESSOA_FIM = re.compile(r"(?:" + _INICIAIS + r"|" + _NOME + r"|\b" + _PAPEL + r"(?:\s+(?:" + _INICIAIS +
                         r"|[A-ZÀ-Ú][\wà-ú]+))*)[\s.]*$")
#: Papel no singular imediatamente antes de "de N anos": "um sobrinho de 10 anos", "meu filho Caio de 6 anos".
_PAPEL_ANTES_DE = re.compile(r"\b(?i:filh[oa]|irm[ãa]o?|net[oa]|bisnet[oa]|sobrinh[oa]|entead[oa]|crian[çc]a|"
                             r"adolescente|beb[êe]|menina|menino|garot[oa]|rapaz|mo[çc]a|senhor[a]?|idos[oa]|"
                             r"homem|mulher|indiv[íi]duo|"
                             r"paciente|v[íi]tima|requerente|assistid[oa]|usu[áa]ri[oa]|genitor[a]?|"
                             r"companheir[oa]|espos[oa]|marido|m[ãa]e|pai|av[ôóo])"
                             r"(?:\s+(?:" + _INICIAIS + r"|[A-ZÀ-Ú][\wà-ú]+))*\s*$")
#: Separadores entre os segmentos de uma enumeração ou de um formulário.
_SEGMENTO = re.compile(r"[,;:(\n|\t–—]|\s-\s")

#: Rótulo de formulário: "Idade: 63 anos", "IDADE: 34", "Idade: 47 a". A abreviatura "a" só vale
#: logo após o rótulo.
_ROTULO_IDADE = re.compile(
    r"\bidade(?:\s+(?:atual|declarada))?\s*(?:\(\s*anos\s*\))?\s*[:=]\s*"
    r"(?P<v>\d{1,3}(?:\s*(?:anos?\b|a\b\.?(?!\s*\d)|m[êe]s(?:es)?\b)"
    r"(?:\s*(?:,|e)\s*\d{1,2}\s*(?:m[êe]s(?:es)?|dias?)\b)?)?)(?![\d/.,])(?!\s*(?:a|à|e|ou)\s+\d)",
    re.IGNORECASE)
#: Idade em aposto, após vírgula, travessão ou parêntese: "Fulano, 38 anos, CPF…", "K.C.P., 9 anos;".
_APOSTO = re.compile(r"(?:(?<=[,;(]\s{0,3})|(?<=[–—]\s{0,3})|(?<=\s-\s))(?P<v>" + _IDADE + r")" + _NAO_IDADE_DEPOIS +
                     r"(?=\s*(?:[,;.)|\t\n]|$|e\s+\S|de\s+idade|\(\s*nascid))", re.IGNORECASE)
#: Idade com "de": "a filha, A.F.L., de 3 anos", "um sobrinho de 10 anos".
_DE_IDADE = re.compile(r"\bde\s+(?P<v>" + _IDADE + r")" + _NAO_IDADE_DEPOIS, re.IGNORECASE)
#: Idade com "com": "hoje com 2 anos", "então com 16 anos", "…, com 52 anos, empresário".
_COM_IDADE = re.compile(r"(?:(?<=,\s{0,3})|\b(?:hoje|ent[ãa]o|atualmente|agora|j[áa])\s+)com\s+(?P<v>" + _IDADE + r")" +
                        _NAO_IDADE_DEPOIS + r"(?=\s*(?:de\s+idade|[,;.)\n]|$|e\s+\S))", re.IGNORECASE)
#: Idade com verbo: "contava 19 anos", "tem 9 anos", "possuindo 60 (sessenta) anos de idade".
_VERBO_IDADE = re.compile(
    r"\b(?:tem|tinha|completou|completa|completar[áa]|completando|contava(?:\s+com)?|possui|"
    r"possu[íi]a|possuindo|fez|far[áa])\s+(?P<v>" + _IDADE + r")" + _NAO_IDADE_DEPOIS, re.IGNORECASE)
#: "N anos de idade" em qualquer construção: "61 (sessenta e um) anos de idade".
_ANOS_DE_IDADE = re.compile(r"(?<![\d,.])(?P<v>" + _IDADE + r")(?=\s+de\s+idade\b)(?!\s+de\s+idade\s+ou\s+(?:mais|menos))",
                            re.IGNORECASE)
#: Idade logo depois da data de nascimento: "Data de nascimento: 17/02/2019 (6 anos)", "… – 28 anos".
_DEPOIS_DA_DATA = re.compile(
    r"(?:\bnasc\w*\.?|\bD\.?N\.?)[^\d\n]{0,25}\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*\d{2,4}"
    r"\s*(?:\(\s*|[,–—]\s*|-\s+)(?P<v>" + _IDADE + r")", re.IGNORECASE)
#: Idade logo antes da data de nascimento: "23 anos, nascido em…", "11 anos (nascido em…)".
_ANTES_DA_DATA = re.compile(r"(?<![\d,.])(?P<v>" + _IDADE + r")(?:\s+de\s+idade)?\s*[,(]\s*nascid[oa]", re.IGNORECASE)


def _antes_generico(texto: str, inicio: int) -> bool:
    """Indica se as palavras logo antes da idade a tornam faixa, requisito, estimativa ou grupo."""
    return bool(_NAO_IDADE_ANTES.search(texto, max(0, inicio - 40), inicio))


def _segmento_anterior(texto: str, fim: int) -> str:
    """Trecho entre o separador anterior (vírgula, dois-pontos, parêntese, linha) e ``fim``."""
    ini = max(0, fim - 90)
    ultimo = None
    for m in _SEGMENTO.finditer(texto, ini, fim):
        ultimo = m
    return texto[ultimo.end() if ultimo else ini:fim]


#: Disposição normativa: artigo ou parágrafo de norma, ou verbo no futuro que prescreve ("o servidor
#: com 70 anos de idade será aposentado…").
_NORMA = re.compile(r"\b(?:Art\.|§|ser[áa]o?|dever[áa]o?|poder[áa]o?|far[áa]o?\s+jus|ter[áa]o?\s+direito)(?!\w)")
#: Pessoa identificada na frase: nome, iniciais ou CPF.
_IDENTIFICADA = re.compile(_NOME + r"|" + _INICIAIS + r"|\bCPF\b")


def _norma_generica(texto: str, ini: int, fim: int) -> bool:
    """Indica se a idade está numa disposição normativa sem pessoa identificada na frase."""
    a = max((m.end() for m in re.finditer(r"[.;:!?]\s|\n", texto[max(0, ini - 200):ini])), default=0)
    a += max(0, ini - 200)
    m = re.search(r"[.;!?](?:\s|$)|\n", texto[fim:fim + 200])
    b = fim + (m.start() if m else min(200, len(texto) - fim))
    return bool(_NORMA.search(texto, a, b)) and not _IDENTIFICADA.search(texto, a, b)


def _anterior_nao_espaco(texto: str, pos: int) -> int:
    """Posição do último caractere que não é espaço antes de ``pos`` (-1 se não houver)."""
    pos -= 1
    while pos >= 0 and texto[pos].isspace():
        pos -= 1
    return pos


def _designa_pessoa(trecho: str) -> bool:
    """Indica se o trecho termina com nome, iniciais ou papel de uma pessoa determinada."""
    trecho = trecho.strip()
    return bool(trecho) and _PESSOA_FIM.search(trecho) is not None


class ReconhecedorIdades:
    """Idade exata de pessoa identificável e datas de nascimento em colunas de tabela."""

    nome = "idades"

    def detectar(self, texto: str) -> list[Deteccao]:
        achados: list[Deteccao] = []

        def novo(ini: int, fim: int, origem: str, score: float = 0.85, tipo: str = "IDADE") -> None:
            achados.append(Deteccao(ini, fim, tipo, score, origem, CONTEXTUAL, None, True))

        if not re.search(r"\d\s*(?:\([^()\d\n]{2,40}\)\s*)?(?:anos?|m[êe]s|meses|a\b)|nasc", texto, re.IGNORECASE):
            return achados
        for m in _ROTULO_IDADE.finditer(texto):
            novo(*m.span("v"), "idade:rotulo", 0.9)
        for m in _DEPOIS_DA_DATA.finditer(texto):
            novo(*m.span("v"), "idade:data-nascimento", 0.9)
        for m in _ANTES_DA_DATA.finditer(texto):
            novo(*m.span("v"), "idade:data-nascimento", 0.9)
        for m in _APOSTO.finditer(texto):
            # O separador (vírgula, parêntese, travessão) precede a idade; o segmento anterior a ele
            # precisa designar a pessoa.
            sep = _anterior_nao_espaco(texto, m.start("v"))
            if _designa_pessoa(_segmento_anterior(texto, sep)):
                novo(*m.span("v"), "idade:aposto")
        for m in _DE_IDADE.finditer(texto):
            ini = m.start()
            if _antes_generico(texto, ini):
                continue
            sep = _anterior_nao_espaco(texto, ini)
            if sep >= 0 and texto[sep] == ",":
                pessoa = _designa_pessoa(_segmento_anterior(texto, sep))
            else:
                pessoa = _PAPEL_ANTES_DE.search(texto, max(0, ini - 90), ini) is not None
            if pessoa:
                novo(*m.span("v"), "idade:de")
        for rx, origem in ((_COM_IDADE, "idade:com"), (_VERBO_IDADE, "idade:verbo"), (_ANOS_DE_IDADE, "idade:de-idade")):
            for m in rx.finditer(texto):
                if not _antes_generico(texto, m.start()) and not _norma_generica(texto, m.start(), m.end()):
                    novo(*m.span("v"), origem)
        for tabela in _tabelas(texto):
            achados.extend(tabela.idades_e_nascimentos())
        return achados


# =========================================================================== tabelas
#: Cabeçalho de coluna de data de nascimento.
_COL_NASCIMENTO = re.compile(r"nasc|^\s*d\.?\s?n\.?\s*$|\bdt\.?\s*nasc", re.IGNORECASE)
#: Cabeçalho de coluna de idade.
_COL_IDADE = re.compile(r"^\s*idade\b", re.IGNORECASE)
#: Cabeçalhos que indicam uma tabela de pessoas naturais (uma linha por pessoa ou por rubrica do
#: contracheque de uma pessoa).
_COL_PESSOA = re.compile(
    r"\bnome\b|parentesco|v[íi]nculo|\bcpf\b|siape|\bmasp\b|matr[íi]cula|rubrica|"
    # No singular (ou com a flexão "(a)"): no plural, o cabeçalho costuma ser contagem ("Beneficiários").
    r"\b(?:servidor|benefici[áa]ri[oa]|contribuinte|integrante|membro|dependente|requerente|interessad[oa]|"
    r"alun[oa]|paciente|professor|segurad[oa]|pensionista|titular|declarante|credor|devedor|respons[áa]vel)"
    r"(?:\s*\(a\)|a)?(?![\wà-ú])", re.IGNORECASE)
#: Cabeçalhos de tabela de pessoas jurídicas, cujos valores são públicos.
_COL_EMPRESA = re.compile(r"\bcnpj\b|empresa|raz[ãa]o\s+social|fornecedor|licitante|contratad", re.IGNORECASE)
#: Cabeçalho de coluna de valor em dinheiro (e não de nota, índice ou percentual).
_COL_VALOR = re.compile(r"valor|renda|remunera|sal[áa]rio|vencimento|provento|benef[íi]cio|R\$|rendimento|d[ée]bito|"
                        r"devid|pag[oa]|bruto|l[íi]quido|desconto|cr[ée]dito|saldo|parcela|aluguel|pens[ãa]o|bolsa|"
                        r"aux[íi]lio|di[áa]ria|multa", re.IGNORECASE)
#: Cabeçalho de coluna de duração ("Tempo de serviço", "Período"), cujos "N anos" não são idade.
_COL_DURACAO = re.compile(r"tempo|per[íi]odo|prazo|dura[çc]|perman|car[êe]ncia|servi[çc]o|contribui|pena|exerc",
                          re.IGNORECASE)
#: Data numérica.
_DATA = re.compile(r"(?<![\d/.\-])\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*(?:19|20)?\d{2}(?![\d/.\-])")
#: Célula que é uma idade ("31 anos", "7 meses") ou só o número de anos.
_CELULA_IDADE = re.compile(r"^\s*(?P<v>" + _IDADE + r"|\d{1,3})\s*$", re.IGNORECASE)
#: Valor monetário no início de uma célula, com ou sem "R$": "R$ 600,00 (Bolsa Família)", "8.412,57".
_CELULA_VALOR = re.compile(r"\s*(?P<v>(?:R\$\s?)?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2})(?![\d])")


class _Tabela:
    """Bloco de linhas consecutivas com colunas separadas por barra vertical ou tabulação.

    Attributes:
        texto: Texto completo.
        cabecalho: Células do cabeçalho (sem posições), ou lista vazia se o bloco não tiver um.
        linhas: Para cada linha de dados, a lista de células como ``(início, fim)`` no texto.
    """

    def __init__(self, texto: str, cabecalho: list[str], linhas: list[list[tuple[int, int]]]):
        self.texto = texto
        self.cabecalho = cabecalho
        self.linhas = linhas
        cab = " | ".join(cabecalho)
        self.de_pessoas = bool(_COL_PESSOA.search(cab)) and not _COL_EMPRESA.search(cab)

    def _coluna(self, rx: re.Pattern) -> int | None:
        return next((i for i, c in enumerate(self.cabecalho) if rx.search(c)), None)

    def idades_e_nascimentos(self) -> list[Deteccao]:
        """Datas da coluna de nascimento e idades da coluna de idade (ou de células "N anos")."""
        saida: list[Deteccao] = []
        col_nasc, col_idade = self._coluna(_COL_NASCIMENTO), self._coluna(_COL_IDADE)
        if col_nasc is None and not self.de_pessoas:
            return saida
        for celulas in self.linhas:
            for i, (a, b) in enumerate(celulas):
                valor = self.texto[a:b]
                if col_nasc is not None and (i == col_nasc or len(celulas) != len(self.cabecalho)):
                    for m in _DATA.finditer(valor):
                        saida.append(Deteccao(a + m.start(), a + m.end(), "DATA_NASCIMENTO", 0.85, "nascimento:tabela",
                                              CONTEXTUAL, None, True))
                if self.de_pessoas:
                    m = _CELULA_IDADE.match(valor)
                    duracao = i < len(self.cabecalho) and _COL_DURACAO.search(self.cabecalho[i])
                    if m and (i == col_idade or (col_idade is None and not duracao and not m.group("v").isdigit())):
                        saida.append(Deteccao(a + m.start("v"), a + m.end("v"), "IDADE", 0.85, "idade:tabela",
                                              CONTEXTUAL, None, True))
        return saida

    def valores(self, todos: bool = False) -> list[Deteccao]:
        """Valores monetários das células, se a tabela for de pessoas (ou se ``todos``).

        A célula precisa trazer "R$" ou estar numa coluna de valor em dinheiro: numa tabela de pessoas,
        "72,50" também pode ser nota de concurso. Sem cabeçalho (só com ``todos``), vale qualquer valor.
        """
        if not (self.de_pessoas or todos):
            return []
        colunas = {i for i, c in enumerate(self.cabecalho) if _COL_VALOR.search(c)}
        saida = []
        for celulas in self.linhas:
            alinhada = len(celulas) == len(self.cabecalho)
            for i, (a, b) in enumerate(celulas):
                m = _CELULA_VALOR.match(self.texto, a, b)
                if m is None:
                    continue
                if ("R$" in m.group("v") or not self.cabecalho or (i in colunas if alinhada else bool(colunas))):
                    saida.append(Deteccao(m.start("v"), m.end("v"), "VALOR_PESSOAL", 0.85, "valor:tabela",
                                          CONTEXTUAL, None, True))
        return saida


def _celulas(texto: str, ini: int, fim: int, sep: str) -> list[tuple[int, int]]:
    """Células de uma linha, como posições sem os espaços das bordas."""
    saida = []
    a = ini
    partes = texto[ini:fim].split(sep)
    if sep == "|" and partes and not partes[0].strip():
        a += len(partes[0]) + 1
        partes = partes[1:]
    for p in partes:
        x, y = a, a + len(p)
        while x < y and texto[x].isspace():
            x += 1
        while y > x and texto[y - 1].isspace():
            y -= 1
        saida.append((x, y))
        a += len(p) + 1
    if saida and saida[-1][0] == saida[-1][1]:
        saida.pop()
    return saida


def _separador(linha: str) -> str:
    """Separador de colunas da linha: "|", tabulação ou nenhum."""
    if "|" in linha and linha.count("|") >= linha.count("\t"):
        return "|"
    return "\t" if "\t" in linha else ""


def _tabelas(texto: str) -> Iterator[_Tabela]:
    """Blocos de linhas consecutivas com colunas separadas por "|" ou por tabulação."""
    if "|" not in texto and "\t" not in texto:
        return
    bloco: list[tuple[int, int]] = []
    sep_bloco = ""
    pos = 0
    for linha in texto.split("\n"):
        ini, fim = pos, pos + len(linha)
        pos = fim + 1
        sep = _separador(linha)
        if sep and sep == sep_bloco:
            bloco.append((ini, fim))
            continue
        if bloco:
            yield _montar(texto, bloco, sep_bloco)
        bloco, sep_bloco = ([(ini, fim)], sep) if sep else ([], "")
    if bloco:
        yield _montar(texto, bloco, sep_bloco)


def _montar(texto: str, bloco: list[tuple[int, int]], sep: str) -> _Tabela:
    """Separa o cabeçalho (primeira linha sem algarismos) das linhas de dados."""
    primeira = texto[bloco[0][0]:bloco[0][1]]
    if not any(c.isdigit() for c in primeira.replace("(R$)", "")):
        cab = [texto[a:b] for a, b in _celulas(texto, *bloco[0], sep)]
        dados = bloco[1:]
    else:
        cab, dados = [], bloco
    return _Tabela(texto, cab, [_celulas(texto, a, b, sep) for a, b in dados])


# =========================================================================== valores
#: Valor em reais: "R$ 1.234,56", "R$ 600", "R$ 2 mil", com o extenso entre parênteses, se houver.
_REAIS = (r"R\$\s?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?(?:\s+(?:mil|milh(?:[ãa]o|[õo]es))\b)?(?![\d])"
          r"(?:\s*\((?=[^()\n]{0,200}?\b(?:reais|real|centavos?)\b)[^()\n]{3,200}\))?")
#: Valor expresso em salários mínimos: "um salário mínimo", "dois salários mínimos".
_SALARIOS = (r"\b(?:meio|um|dois|tr[êe]s|quatro|cinco|seis|sete|oito|nove|dez|\d{1,2}(?:,\d{1,2})?)\s+"
             r"sal[áa]rios?[\s-]+m[íi]nimos?\b")
#: Percentual dos rendimentos de alguém: "25% (vinte e cinco por cento) dos rendimentos brutos".
_PERCENTUAL = (r"\b\d{1,3}(?:,\d{1,2})?\s?%(?:\s*\([^()\n]{3,60}\))?(?=\s+d[oa]s?\s+(?:rendimentos|sal[áa]rios?|"
               r"remunera[çc](?:[ãa]o|[õo]es)|proventos|vencimentos)\b(?!\s+(?:inicial|iniciais|base|b[áa]sico)\b))")
_VALOR = re.compile(r"(?P<reais>" + _REAIS + r")|(?P<salarios>" + _SALARIOS + r")|(?P<percentual>" + _PERCENTUAL + r")",
                    re.IGNORECASE)

#: Expressões que vinculam o valor a uma pessoa: o que ela recebe, paga, deve ou perdeu.
_FORTE = (
    r"rendas?|rendimentos?|ganhos|sal[áa]rios?|remunera[çc](?:[ãa]o|[õo]es)|vencimento\s+b[áa]sico|proventos|"
    r"pr[óo]-?labore|cach[êe]s?|aposentadoria|pens(?:[ãa]o|[õo]es)|pensionista|seguro[\s-](?:defeso|desemprego)|"
    r"benef[íi]cio\s+de\s+presta[çc][ãa]o\s+continuada|BPC|alimentos|alimentante|alugu(?:el|[ée]is)|d[íi]vidas?|"
    r"saldo\s+devedor|d[ée]bitos?|parcelas?|financiamentos?|empr[ée]stimos?|faturas?|consigna(?:[çc][ãa]o|d[oa]s?)|"
    r"descontos?|descontad[oa]s?|contribui[çc][ãa]o\s+(?:previdenci[áa]ria|ao|à|para\s+o)|IRRF|imposto\s+de\s+renda|"
    r"margem|multas?|preju[íi]zos?|avaliad[oa]s?\s+em|quantias?|di[áa]rias|ajuda\s+de\s+custo|indeniza[çc](?:[ãa]o|[õo]es)|"
    r"restitui[çc][ãa]o|restituir|ressarcimento|ressarcir|reembolso|transfer[êe]ncias|dep[óo]sitos|saques|"
    r"presta[çc][ãa]o\s+pecuni[áa]ria|gratifica[çc](?:[ãa]o|[õo]es)|adicional\s+(?:por|de|noturno)(?!\s+R\$)|abono|"
    r"saldos?\s+(?:em|na|no|da|de)\s+(?:conta|caderneta|poupan[çc]a|aplica)|despesas\s+pessoais|"
    r"pertencentes?|subtra[íi]\w*|furt\w+|roubad[oa]s?|repara[çc][ãa]o\s+(?:d[oa]s?\s+)?danos?|"
    r"danos\s+(?:morais|materiais)|ter[çc]o\s+(?:constitucional|de\s+f[ée]rias)|verbas?\s+rescis[óo]rias?|FGTS|"
    r"fian[çc]a|aufer\w+|heran[çc]a|mensalidades?|condenad[oa]\s+ao\s+pagamento|penhor\w+|bloquead[oa]s?|"
    r"apreendid[oa]s?|propinas?|vantagem\s+indevida"
)
#: Expressões que podem se referir a uma pessoa ou a um programa ou norma: valem quando a frase
#: designa uma pessoa (ver :data:`_ANCORA`).
_FRACO = (
    r"bolsa\s+fam[íi]lia|bolsas?|benef[íi]cios?|aux[íi]lios?[\w-]*|subs[íi]dios?|honor[áa]rios|di[áa]ria|"
    r"rece(?:be|beu|bia|ber[áa]|bido|bida|bidos|bimento)|perceb\w+|creditad[oa]|pag[oa]u?|pagos|pagas|"
    r"custear|custeio|sustent\w+|sobreviv\w+|estim(?:a|ou|ad[oa])|adquiri\w*|compr(?:ou|ad[oa])|vend(?:eu|id[oa])|"
    r"exigi\w*|cobr(?:ou|ad[oa]|ava)|somam|somaram|soma|totaliz\w+|apurad[oa]s?\s+em|corresponde\w*|"
    r"deve|devia|devendo|ganha|ganhava|ganhou"
)
#: Expressões de valor público: contratos e licitações, orçamento, repasses, pessoa jurídica,
#: dinheiro público, valores fixados em norma e tabelas de valores.
_PUBLICO = (
    r"(?:remunera[çc][ãa]o|vencimento|sal[áa]rio|subs[íi]dio)\s+(?:inicial|base)|"
    # Dívida, débito ou despesa do próprio ente público ("o débito do Município com o INSS").
    r"(?:d[íi]vidas?|d[ée]bitos?|saldo\s+devedor|multas?|preju[íi]zos?|parcelas?|financiamentos?|"
    r"empr[ée]stimos?|despesas?|receitas?)\s+(?:d[oa]|ao|à)\s+(?:munic[íi]pio|estado|uni[ãa]o|prefeitura|"
    r"secretaria|[óo]rg[ãa]o|ente|governo|tesouro|distrito\s+federal|c[âa]mara|autarquia)|"
    r"contratos?|contratual|contratante|(?:a|à|da|pela|empresa)\s+contratada|licita\w+|preg[ãa]o|edital|"
    r"or[çc]ament\w+|dota[çc]\w+|empenh\w+|repasses?|contrapartida|conv[êe]nios?|recursos|investimentos?|obras?|"
    r"faturamento|empresas?|Ltda|EIRELI|CNPJ|er[áa]rio|cofres\s+p[úu]blicos|propostas?|pre[çc]os?|"
    r"unit[áa]ri[oa]|global|glosa|medi[çc][ãa]o|tarifas?|arrecada\w*|taxas?|causa|teto|piso|tabela|"
    r"fixa(?:d[oa]s?)?|fixando|categorias?|vagas|programa(?!\s+bolsa)|projetos?|caixa\s+da\s+empresa|"
    r"valor(?:es)?\s+(?:estimad[oa]s?|contratua(?:l|is)|global|globais|de\s+refer[êe]ncia)|custo\s+estimado|"
    r"total\s+(?:executado|estimado|geral|do\s+edital|do\s+programa)|aquisi[çc](?:[ãa]o|[õo]es)\s+de"
)
#: "Salário mínimo" é unidade de valor e não decide por si se o valor é de uma pessoa.
_NEUTRO = r"sal[áa]rios?[\s-]+m[íi]nimos?(?:\s+(?:vigente|nacional|atual))?"
_GATILHO = re.compile(r"\b(?:(?P<neutro>" + _NEUTRO + r")|(?P<publico>" + _PUBLICO + r")|(?P<forte>" + _FORTE +
                      r")|(?P<fraco>" + _FRACO + r"))\b", re.IGNORECASE)
#: Expressões logo após o valor que o vinculam a uma pessoa ("R$ 1.518,00 mensais de pensão",
#: "R$ 455,40 para despesas pessoais") ou o tornam público ("do caixa da empresa", "ao erário").
_DEPOIS_PESSOAL = re.compile(
    r"^[\s,)]*(?:mensais\s+)?(?:\(?\s*(?:bolsa\s+fam[íi]lia|BPC|benef[íi]cio|aposentadoria|pens[ãa]o|aux[íi]lio)|"
    r"(?:de|a\s+t[íi]tulo\s+de)\s+(?:pens[ãa]o|aposentadoria|renda|sal[áa]rio|benef[íi]cio|aluguel|alimentos)|"
    r"para\s+despesas\s+pessoais|pertencentes?\s+a)", re.IGNORECASE)
_DEPOIS_PUBLICO = re.compile(
    r"^[^.;\n]{0,25}?\b(?:da\s+empresa|do\s+caixa|ao\s+er[áa]rio|aos\s+cofres|do\s+contrato|da\s+contratada|"
    r"(?:ao|do|pelo|para\s+o)\s+(?:munic[íi]pio|estado|distrito\s+federal|governo)|(?:à|da|pela)\s+(?:uni[ãa]o|prefeitura|secretaria)|"
    r"por\s+(?:fam[íi]lia|benefici[áa]ri[oa]|alun[oa]|vaga|cargo|candidat[oa])|para\s+quem|aos?\s+infrator)", re.IGNORECASE)
#: Faixa de valores ou limite ("de R$ 500,00 a R$ 5.000,00", "até R$ 218,00"): referência normativa.
_LIMITE_ANTES = re.compile(r"\b(?:at[ée]|inferior\s+a|superior\s+a|m[áa]ximo\s+de|m[íi]nimo\s+de|limite\s+de|"
                           r"teto\s+de|acima\s+de|abaixo\s+de|entre(?:\s+\S+){0,2}\s+e|"
                           r"(?:exced|ultrapass|supera|n[ãa]o\s+(?:pode|deve)\s+passar)\w*(?:\s+(?:[oa]s?|de))?)\s*$",
                           re.IGNORECASE)
_FAIXA_DEPOIS = re.compile(r"\s*(?:a|à|e|até)\s+R\$", re.IGNORECASE)
#: Marcas de que a frase se refere a uma pessoa determinada: CPF, iniciais, tratamento e primeira
#: pessoa (fortes) ou papel com artigo ou possessivo (que, numa norma, também pode ser genérico:
#: "o servidor fará jus a…").
_ANCORA_FORTE = re.compile(
    r"\bCPF\b|\d{3}\.\d{3}\.\d{3}-\d{2}|\*{3}\.\d{3}\.\d{3}-\*{2}|" + _INICIAIS + r"|\bSr[a]?\.|"
    r"\b(?i:recebo|ganho|pago|devo|tenho|minha\s+renda|meu\s+sal[áa]rio)\b")
_ANCORA = re.compile(
    r"\b(?i:(?:o|a|do|da|ao|à|pelo|pela|seu|sua|meu|minha|nosso|nossa)\s+(?:filh[oa]|m[ãa]e|pai|fam[íi]lia|"
    r"respons[áa]vel|requerente|requerid[oa]|interessad[oa]|assistid[oa]|usu[áa]ri[oa]|idos[oa]|servidor[a]?|"
    r"benefici[áa]ri[oa]|segurad[oa]|pensionista|aposentad[oa]|titular|crian[çc]a|adolescente|v[íi]tima|autor[a]?|"
    r"r[ée]u|acusad[oa]|indiciad[oa]|apenad[oa]|declarante|companheir[oa]|genitor[a]?|av[óôo]|net[oa]|sobrinh[oa]|"
    r"militar|contratad[oa]|outorgad[oa]|bolsista|autuad[oa]|condutor[a]?|propriet[áa]ri[oa]|locat[áa]ri[oa]|"
    r"reclamante|reclamad[oa]|exequente|executad[oa]|impetrante|sentenciad[oa]|condenad[oa]|pres[oa]|"
    r"detent[oa]|internad[oa]|paciente|empregad[oa]|trabalhador[a]?))\b")
#: Grupo ou média entre a expressão e o valor ("a renda média das famílias atendidas é de…", "R$ X por
#: aluno"): dado agregado, não de uma pessoa.
_COLETIVO = re.compile(
    r"\b(?:d[oa]s|pel[oa]s|entre\s+[oa]s|aos|às|para\s+[oa]s)\s+(?:fam[íi]lias|servidor(?:es|as)|benefici[áa]ri[oa]s|"
    r"segurad[oa]s|aposentad[oa]s|pensionistas|alun[oa]s|estudantes|bolsistas|trabalhador(?:es|as)|professor(?:es|as)|"
    r"profissionais|empregad[oa]s|usu[áa]ri[oa]s|cidad[ãa]os|moradores|pacientes|idos[oa]s|contribuintes|"
    r"candidat[oa]s|participantes|inscrit[oa]s|selecionad[oa]s|munic[íi]pios|unidades|cargos|categorias)\b|"
    r"\bpor\s+(?:fam[íi]lia|pessoa|benefici[áa]ri[oa]|alun[oa]|estudante|servidor|bolsista|participante|"
    r"candidat[oa]|vaga|cargo)\b", re.IGNORECASE)
#: Pessoa jurídica na frase: multa, parcela, desconto ou débito são da empresa, não de uma pessoa.
_PESSOA_JURIDICA = re.compile(r"\bCNPJ\b|\bLtda\b|\bS\.\s?A\.|\bEIRELI\b|\b(?i:empresa|contratada|licitante|fornecedor[a]?|"
                              r"concession[áa]ria|cons[óo]rcio|cooperativa|associa[çc][ãa]o|funda[çc][ãa]o)\b")
#: Início de frase que retoma uma pessoa já mencionada: possessivo ("Sua participação…") ou verbo de
#: relato na terceira pessoa ("Afirmou ter comprado…", "Declarou receber…"), típico de depoimentos.
_ANCORA_INICIAL = re.compile(
    r"\s*(?:\d+(?:\.\d+)*\.?\s+)?(?:QUE\s+)?(?:Sua|Seu|Suas|Seus|Afirmou|Declarou|Informou|Relatou|Alegou|Disse|"
    r"Esclareceu|Acrescentou|Narrou|Confessou|Admitiu|Reconheceu|Contou|Mencionou)\b")
#: Marcas normativas na oração: o valor é fixado por norma ou edital para um cargo ou categoria.
_NORMATIVO = re.compile(r"\b(?:fica(?:m)?\s+(?:fixad|estabelecid|institu[íi]d)\w*|fixa(?:d[oa]s?|r)?|estabelece\w*|"
                        r"institui\w*|sujeit\w+|far[áa]\s+jus|far[ãa]o\s+jus|perceber[áa]|receber[áa]|receber[ãa]o|"
                        r"ser[áa]\s+(?:de|pag[oa]|concedid[oa]|devid[oa])|o\s+valor\s+d[ae]\s+cada)\b", re.IGNORECASE)
#: Fronteira de frase (exceto abreviaturas comuns) ou de linha.
_FIM_FRASE = re.compile(r"(?<!\b(?:Sr|Sra|Dr|Dra|art|arts|inc|n|fls|fl|p|pp|Av|Prof|Profa|Exmo|Exma|Ilmo|Ilma|nº|cf|"
                        r"Ag|ag|Cia|Ltda|S\.A|Me|Ma|Esp|Rod|Trav|Al|al|tel|Tel|ref|Ref|aprox|R))"
                        r"[.!?](?=\s+[A-ZÀ-Ú(\d\"“])|\n")
#: Declaração de bens (Lei nº 8.429/1992, art. 13): todos os valores são patrimônio do declarante.
_DECLARACAO_BENS = re.compile(r"^[^\S\n]*declara[çc][ãa]o\s+(?:de\s+bens|patrimonial)", re.IGNORECASE | re.MULTILINE)
#: Extrato de contrato, termo de outorga ou de concessão cuja contraparte é pessoa física: o rótulo
#: da parte é seguido do CPF na mesma linha, sem CNPJ.
_CONTRAPARTE_PF = re.compile(
    r"^[^\n]{0,20}\b(?:contratad[oa]|outorgad[oa]|bolsista|benefici[áa]ri[oa]|credenciad[oa]|premiad[oa]|"
    r"favorecid[oa]|permission[áa]ri[oa]|cession[áa]ri[oa]|locador[a]?|prestador[a]?)\s*:(?![^\n]*\bCNPJ\b)[^\n]*"
    r"\bCPF\b", re.IGNORECASE | re.MULTILINE)
_CNPJ = re.compile(r"\bCNPJ\b|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")
_CPF = re.compile(r"\bCPF\b|\d{3}\.\d{3}\.\d{3}-\d{2}|\*{3}\.\d{3}\.\d{3}-\*{2}")


def _inicio_frase(texto: str, pos: int, alcance: int = 160) -> int:
    ini = max(0, pos - alcance)
    ultimo = None
    for m in _FIM_FRASE.finditer(texto, ini, pos):
        ultimo = m
    return ultimo.end() if ultimo else ini


def _fim_frase(texto: str, pos: int, alcance: int = 160) -> int:
    m = _FIM_FRASE.search(texto, pos, min(len(texto), pos + alcance))
    return m.start() if m else min(len(texto), pos + alcance)


def classificar_valor(texto: str, ini: int, fim: int) -> str | None:
    """Classifica um valor monetário pelo contexto da frase em que está.

    Decide a última expressão decisiva antes do valor: de valor público, o valor fica legível; de
    vínculo pessoal (renda, dívida, multa…), é dado pessoal, salvo em oração normativa sem pessoa
    determinada ("fica fixada a remuneração do cargo em…"). Sem expressão decisiva, uma expressão de
    vínculo fraco (benefício, recebeu, auxílio…) basta se a frase designa uma pessoa (ver
    :data:`_ANCORA`) e não é normativa.

    Returns:
        ``"pessoal"``, ``"publico"`` ou ``None`` (contexto insuficiente).
    """
    a, b = _inicio_frase(texto, ini), _fim_frase(texto, fim)
    antes = texto[a:ini]
    depois = texto[fim:min(len(texto), fim + 60)]
    if _LIMITE_ANTES.search(antes) or _FAIXA_DEPOIS.match(texto, fim) or _DEPOIS_PUBLICO.match(depois):
        return "publico"
    decisivo = fraco = None
    for m in _GATILHO.finditer(antes):
        if m.group("publico") or m.group("forte"):
            decisivo = m
        elif m.group("fraco"):
            fraco = m
    gatilho = decisivo or fraco
    if gatilho is not None and gatilho.group("publico"):
        return "publico"
    forte = _ANCORA_FORTE.search(texto, a, b) is not None or _ANCORA_INICIAL.match(texto, a) is not None
    if gatilho is not None and not _COLETIVO.search(antes, gatilho.end()):
        oracao = antes[antes.rfind(",", 0, gatilho.start()) + 1:]
        # Valor fixado em norma ou atribuído a pessoa jurídica na mesma oração ("multa de R$ X por dia
        # de atraso, aplicada à contratada"): só é pessoal se a frase identifica uma pessoa.
        ressalva = _NORMATIVO.search(oracao) or _PESSOA_JURIDICA.search(oracao) or \
            _PESSOA_JURIDICA.search(texto, fim, min(b, fim + 60))
        pessoa = forte or (not ressalva and _ANCORA.search(texto, a, b) is not None)
        if pessoa or (gatilho.group("forte") and not ressalva):
            return "pessoal"
    return "pessoal" if _DEPOIS_PESSOAL.match(depois) else None


def _quantia(valor: str) -> str:
    """Algarismos de um valor em reais, para comparar repetições do mesmo valor no documento."""
    return "".join(c for c in valor.split("(")[0] if c.isdigit())


#: Indício barato de valor monetário no texto, para evitar o trabalho nos demais.
_TEM_VALOR = re.compile(r"R\$|\d,\d{2}\b|\d\s?%|sal[áa]rios?[\s-]+m[íi]nimo", re.IGNORECASE)


class ReconhecedorValores:
    """Valores monetários recebidos, pagos ou devidos por pessoa natural."""

    nome = "valores"

    def detectar(self, texto: str) -> list[Deteccao]:
        achados: list[Deteccao] = []
        if not _TEM_VALOR.search(texto):
            return achados
        declaracao = _DECLARACAO_BENS.search(texto) is not None
        contraparte_pf = _CONTRAPARTE_PF.search(texto) is not None
        em_tabela: list[tuple[int, int]] = []
        for t in _tabelas(texto):
            for d in t.valores(todos=declaracao):
                achados.append(d)
                em_tabela.append((d.inicio, d.fim))

        def novo(ini: int, fim: int, score: float, origem: str) -> None:
            achados.append(Deteccao(ini, fim, "VALOR_PESSOAL", score, origem, CONTEXTUAL, None, True))

        indefinidos = []
        for m in _VALOR.finditer(texto):
            ini, fim = m.span()
            if any(x <= ini < y for x, y in em_tabela):
                continue
            if declaracao:
                # Declaração de bens (Lei nº 8.429/1992, art. 13): todo valor é patrimônio do declarante.
                novo(ini, fim, 0.8, "valor:declaracao-bens")
                continue
            classe = classificar_valor(texto, ini, fim)
            if classe == "pessoal":
                novo(ini, fim, 0.85, "valor:contexto")
            elif classe is None and m.group("reais"):
                # Sem contexto decisivo na frase: o extrato com pessoa física é inteiramente sobre a
                # pessoa; na frase com CPF (e sem CNPJ), o valor é dela.
                a, b = _inicio_frase(texto, ini, 400), _fim_frase(texto, fim, 400)
                if contraparte_pf:
                    novo(ini, fim, 0.75, "valor:documento")
                elif _CPF.search(texto, a, b) and not _CNPJ.search(texto, a, b):
                    novo(ini, fim, 0.7, "valor:frase-cpf")
                else:
                    indefinidos.append(m)
        # O mesmo valor repetido no documento sem contexto decisivo ("fixo o valor mínimo para
        # reparação em R$ X", depois de "subtraiu a quantia de R$ X") é o mesmo dado pessoal.
        pessoais = {_quantia(texto[d.inicio:d.fim]) for d in achados}
        for m in indefinidos:
            if m.group("reais") and _quantia(m.group()) in pessoais:
                novo(*m.span(), 0.7, "valor:repeticao")
        return achados


def reconhecedores():
    """Reconhecedores deste módulo, na forma esperada por :mod:`themis_lgpd.analisador`."""
    return [ReconhecedorIdades(), ReconhecedorValores()]
