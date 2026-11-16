"""Normalização de texto para detecção, com mapa de posições até o texto original.

A detecção é feita sobre uma versão normalizada do texto, que neutraliza variações de escrita
usadas — intencionalmente ou não — para escapar de reconhecedores:

* forma de compatibilidade Unicode (NFKC): dígitos de largura total, ligaduras, sobrescritos;
* remoção de caracteres invisíveis (espaço de largura zero, marcas de direção de texto);
* espaços especiais convertidos em espaço comum;
* homóglifos: letras cirílicas e gregas idênticas às latinas ("Мaria" com M cirílico);
* hifenização de fim de linha desfeita ("Apa-\\nrecida" → "Aparecida"), também em caixa alta
  ("PE-\\nREIRA"), com "¬" ou hífen condicional e com espaço depois do hífen ("Bor- \\nges");
* número partido depois do hífen reunido, com o hífen ("027-\\n09" → "027-09");
* campos de formulário em quadrícula, com um caractere por casa ("M A R I A   D E" → "MARIA DE");
* espaço depois de rótulo colado ao valor ("Nome:FULANO" → "Nome: FULANO");
* letras confundidas com dígitos pelo OCR, apenas em trechos majoritariamente numéricos; o zero no
  lugar da letra O dentro de palavra ("C0STA"); "rn" lido no lugar de "m" em nomes e rótulos de campo
  ("Sarnuel", "norne").

A substituição, porém, é sempre aplicada sobre o texto **original**: o mapa de posições traduz cada
achado de volta, e o documento publicado só muda nos trechos tarjados.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

try:  # dependência declarada; a importação opcional mantém o motor funcional sem ela
    import ftfy
    from ftfy.badness import is_bad as _mojibake
except ImportError:  # pragma: no cover
    ftfy = None

#: Caracteres sem representação visual removidos antes da detecção: hífen condicional, marcas de
#: direção de texto, junções de largura zero, BOM. Definidos por código, e não como caracteres
#: literais, para que o código-fonte não contenha caracteres invisíveis.
INVISIVEIS = frozenset(chr(c) for c in (
    0x00AD, 0x034F, 0x061C, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180B, 0x180C, 0x180D, 0x180E,
    0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
    0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF,
))

#: Espaços tipográficos (não separável, fino, ideográfico…) tratados como espaço comum.
ESPACOS = frozenset(chr(c) for c in (
    0x00A0, 0x1680, *range(0x2000, 0x200B), 0x202F, 0x205F, 0x3000,
))

#: Letras cirílicas e gregas visualmente idênticas às latinas, convertidas para o equivalente latino.
HOMOGLIFOS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j",
    "ѕ": "s", "ԁ": "d", "һ": "h", "ӏ": "l", "ԛ": "q", "ԝ": "w", "ɡ": "g",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "Х": "X", "У": "Y", "І": "I", "Ј": "J", "Ѕ": "S",
    "α": "a", "ο": "o", "ν": "v", "ρ": "p", "τ": "t", "ι": "i", "κ": "k",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M",
    "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
})


@dataclass
class TextoNormalizado:
    """Texto normalizado e o mapa de cada caractere para o intervalo correspondente no original.

    Attributes:
        original: Texto de entrada, com a codificação corrigida quando necessário. É sobre ele que a
            anonimização é aplicada.
        texto: Texto normalizado, usado na detecção.
        encoding_corrigido: Indica que o texto de entrada tinha mojibake e foi corrigido.
    """

    original: str
    texto: str
    _ini: list[int] = field(repr=False)
    _fim: list[int] = field(repr=False)
    encoding_corrigido: bool = False

    def para_original(self, inicio: int, fim: int) -> tuple[int, int]:
        """Converte um intervalo do texto normalizado para o texto original.

        O intervalo devolvido cobre integralmente os caracteres originais que deram origem ao trecho,
        inclusive caracteres removidos na normalização que estejam entre eles.
        """
        if not self.texto:
            return 0, 0
        inicio = max(0, min(inicio, len(self.texto) - 1))
        fim = max(inicio + 1, min(fim, len(self.texto)))
        return self._ini[inicio], self._fim[fim - 1]


def corrigir_encoding(texto: str) -> tuple[str, bool]:
    """Corrige mojibake (ex.: "Ã©" → "é") apenas quando há sinais claros do problema.

    Returns:
        ``(texto, corrigido)``: o texto, corrigido ou não, e se houve correção.
    """
    if ftfy is None or not texto:
        return texto, False
    try:
        if _mojibake(texto):
            corrigido = ftfy.fix_encoding(texto)
            return corrigido, corrigido != texto
    except Exception:  # pragma: no cover - falha na heurística não deve interromper a anonimização
        return texto, False
    return texto, False


def _eh_letra(c: str) -> bool:
    return c.isalpha()


#: Marcas de hifenização explícitas: "¬" (comum em textos extraídos de PDF e de OCR) e hífen
#: condicional. Entre letras, no fim da linha, sempre indicam palavra partida.
_MARCAS_HIFENIZACAO = frozenset({"\u00ac", "\u00ad"})
#: Hífens tipográficos que, no fim da linha, podem partir uma palavra ou um número.
_HIFENS = frozenset({"-", "\u2010"})

#: Siglas das unidades da federação: depois do hífen no fim da linha, completam um registro
#: ("COREN-\nAM", "SES-\nDF") e não continuam uma palavra.
_UFS = frozenset({
    "ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi",
    "rj", "rn", "rs", "ro", "rr", "sc", "sp", "se", "to"
})
#: Primeiros elementos de palavras compostas e prefixos que se ligam por hífen ("VICE-\nPREFEITO",
#: "SEGUNDA-\nFEIRA"): em caixa alta, o hífen no fim da linha é mantido.
_PRIMEIROS_ELEMENTOS = frozenset({
    "ex", "vice", "vizo", "pre", "pro", "pos", "recem", "sem", "alem", "aquem", "bem", "mal", "auto", "anti",
    "contra", "extra", "infra", "intra", "neo", "proto", "pseudo", "semi", "supra", "ultra", "sub", "super",
    "hiper", "inter", "circum", "pan", "mega", "micro", "mini", "multi", "co", "guarda", "porta", "segunda",
    "terca", "quarta", "quinta", "sexta", "meio", "meia", "norte", "sul", "nordeste", "noroeste", "sudeste",
    "sudoeste", "leste", "oeste", "centro", "luso", "afro", "latino", "franco", "anglo", "italo", "nipo", "sino",
    "teuto", "greco", "euro", "ibero", "indo", "socio", "medico", "tecnico", "politico", "economico", "juridico",
    "fisico", "quimico", "psico", "agro", "sao", "santa", "santo"
})
#: Segundos elementos frequentes de palavras compostas ("DIRETOR-\nGERAL", "TÉCNICO-\nADMINISTRATIVO").
_SEGUNDOS_ELEMENTOS = frozenset({
    "feira", "geral", "gerais", "chefe", "chefes", "adjunto", "adjunta", "executivo", "executiva", "presidente",
    "mor", "mirim", "acu", "guacu", "assistente", "substituto", "substituta", "relator", "relatora", "membro",
    "membros", "administrativo", "administrativa", "pedagogico", "pedagogica", "cientifico", "cientifica",
    "financeiro", "financeira", "social", "sociais", "legista"
})


def _fragmento_anterior(saida: list[str], fim: int | None = None) -> str:
    """Letras já emitidas que terminam em ``fim`` (padrão: o fim da saída), até o primeiro caractere
    que não é letra."""
    k = f = len(saida) if fim is None else fim
    while k > 0 and saida[k - 1].isalpha():
        k -= 1
    return "".join(saida[k:f])


def _fragmento_seguinte(texto: str, k: int) -> str:
    """Letras do texto a partir da posição ``k``, até o primeiro caractere que não é letra."""
    f = k
    while f < len(texto) and texto[f].isalpha():
        f += 1
    return texto[k:f]


def _sem_acento(palavra: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", palavra.lower()) if not unicodedata.combining(c))


def _continuacao_de_linha(texto: str, j: int) -> int:
    """Posição do primeiro caractere da linha seguinte quando ``j`` está no fim da linha (admitidos
    espaços antes da quebra); -1 se houver outro conteúdo antes da quebra ou se a linha seguinte
    estiver vazia."""
    n = len(texto)
    k = j
    while k < n and texto[k] in " \t":
        k += 1
    if k < n and texto[k] == "\r":
        k += 1
    if k >= n or texto[k] != "\n":
        return -1
    k += 1
    while k < n and texto[k] in " \t":
        k += 1
    return k if k < n and not texto[k].isspace() else -1


def _hifenizacao(saida: list[str], texto: str, c: str, k: int) -> str:
    """Decide o tratamento de um hífen no fim da linha.

    Args:
        saida: Caracteres já emitidos (o último precede o hífen).
        texto: Texto original.
        c: O hífen ou a marca de hifenização.
        k: Início da linha seguinte (ver :func:`_continuacao_de_linha`).

    Returns:
        ``"palavra"`` quando o hífen parte uma palavra e deve sair junto com a quebra de linha,
        ``"numero"`` quando parte um número (só a quebra sai: "027-\\n09" → "027-09") e ``""``
        quando o hífen é legítimo e a linha permanece como está.
    """
    anterior, seguinte = saida[-1], texto[k]
    if c in _MARCAS_HIFENIZACAO:
        return "palavra" if anterior.isalpha() and seguinte.isalpha() else ""
    if anterior.isalpha() and seguinte.islower():
        return "palavra"
    if anterior.isalnum() and seguinte.isdigit():
        return "numero"
    if anterior.isalpha() and anterior.isupper() and seguinte.isupper():
        # Palavra em caixa alta partida pela translineação ("PE-\nREIRA"). Não há minúscula que
        # distinga a sílaba de um composto; preservam-se os compostos e prefixos usuais, as siglas
        # de UF e os fragmentos de uma só letra.
        esquerda, direita = _fragmento_anterior(saida), _fragmento_seguinte(texto, k)
        if len(esquerda) < 2 or len(direita) < 2 or not esquerda.isupper() or not direita.isupper():
            return ""
        e, d = _sem_acento(esquerda), _sem_acento(direita)
        if (len(d) == 2 and d in _UFS) or e in _PRIMEIROS_ELEMENTOS or d in _SEGUNDOS_ELEMENTOS:
            return ""
        return "palavra"
    return ""


#: Campo em quadrícula: caracteres isolados separados por um a três espaços ("M A R I A   D E"). Os
#: separadores de tabela e as operações ("|", ";", "+") não ocupam casas de formulário.
_QUADRICULA = re.compile(r"(?<!\S)[^\s|;+](?!\S)(?: {1,3}[^\s|;+](?!\S))+")
#: Quatro casas seguidas, separadas por espaço simples, com letras maiúsculas ou algarismos.
_CASAS = re.compile(r"(?<!\S)[^\W_a-zà-ÿ](?: [^\W_a-zà-ÿ]){3}(?!\S)")


def _espacos_de_quadricula(texto: str) -> set[int]:
    """Posições de espaços a descartar nos campos em quadrícula.

    Formulários impressos com uma casa por caractere chegam ao texto com cada letra separada por
    espaço e cada palavra por casas vazias. Num campo com ao menos quatro letras maiúsculas ou
    algarismos seguidos, separados por espaço simples, e sem letras minúsculas (o texto corrido tem
    palavras de uma letra: "B e é o"), o espaço entre caracteres é descartado e o intervalo entre
    palavras (dois ou três espaços) é reduzido a um espaço. Intervalos maiores separam colunas e são
    mantidos.
    """
    if not _CASAS.search(texto):
        return set()
    descartar: set[int] = set()
    for m in _QUADRICULA.finditer(texto):
        trecho = m.group()
        if not _CASAS.search(trecho) or any(ch.islower() for ch in trecho):
            continue
        caracteres = [ch for ch in trecho if not ch.isspace()]
        if sum(ch.isalnum() for ch in caracteres) * 4 < len(caracteres) * 3:
            continue
        p = m.start()
        while p < m.end():
            if texto[p] != " ":
                p += 1
                continue
            q = p
            while q < m.end() and texto[q] == " ":
                q += 1
            # Espaço simples: entre caracteres da mesma palavra; dois ou três: entre palavras.
            descartar.update(range(p, q) if q - p == 1 else range(p + 1, q))
            p = q
    return descartar


#: Rótulos de campo que o OCR costuma ler com "rn" no lugar de "m" ("norne", "rnãe").
_ROTULOS_OCR = frozenset({
    "matricula", "nome", "numero", "mae", "mes", "municipio", "nascimento", "nascido", "nascida", "menor",
    "medico", "medica",
})
#: Palavra com "rn".
_PALAVRA_RN = re.compile(r"(?<![\w])[^\W\d_]*[rR][nN][^\W\d_]*(?![\w])")


@lru_cache(maxsize=1)
def _lexico_ocr() -> frozenset[str]:
    """Prenomes, sobrenomes e rótulos de campo, sem acentos e em minúsculas."""
    # Importação tardia: o módulo de nomes depende deste.
    from .reconhecedores.nomes import prenomes, sobrenomes

    return prenomes() | sobrenomes() | _ROTULOS_OCR


def _rn_lido_como_m(texto: str) -> dict[int, str]:
    """Posições de "rn" que o OCR leu no lugar de "m" e a letra correspondente.

    A troca só é feita quando a palavra não existe nas listas de prenomes, sobrenomes e rótulos de
    campo e passa a existir com "m" ("Sarnuel" → "Samuel", "norne" → "nome"). Palavras com
    "rn" legítimo ("Bernardo", "governo", "turno") não mudam.
    """
    if "rn" not in texto and "RN" not in texto and "rN" not in texto and "Rn" not in texto:
        return {}
    lexico = _lexico_ocr()
    trocas: dict[int, str] = {}
    for m in _PALAVRA_RN.finditer(texto):
        palavra = m.group()
        base = _sem_acento(palavra)
        if base in lexico:
            continue
        corrigida = base.replace("rn", "m")
        if len(corrigida) < 3 or corrigida not in lexico:
            continue
        for k in range(len(palavra) - 1):
            if palavra[k] in "rR" and palavra[k + 1] in "nN":
                trocas[m.start() + k] = "M" if palavra[k].isupper() else "m"
    return trocas


#: Esquemas de endereço de internet, cujos dois-pontos não separam rótulo e valor.
_ESQUEMAS = frozenset({"http", "https", "ftp", "mailto", "file", "urn", "data", "sip"})


def _rotulo_colado(saida: list[str], texto: str, j: int) -> bool:
    """Indica se os dois-pontos recém-emitidos separam um rótulo do valor colado a ele.

    Em "Aluno(a):FULANO" e "Dt.Nasc.:19/08/2015", o espaço que falta depois dos dois-pontos impede
    que reconhecedores baseados em rótulo e no início da palavra encontrem o valor. Não se aplica a
    horas, endereços de internet e sequências com vários dois-pontos (IPv6, endereço MAC).
    """
    if len(saida) < 2 or j >= len(texto):
        return False
    antes, depois = saida[-2], texto[j]
    if not (antes.isalpha() or antes in ").") or not (depois.isalnum() or depois == "("):
        return False
    if ":" in texto[max(0, j - 7):j - 1] or ":" in texto[j:j + 6]:
        return False
    return _sem_acento(_fragmento_anterior(saida, len(saida) - 1)) not in _ESQUEMAS


def normalizar(texto: str) -> TextoNormalizado:
    """Gera o texto de detecção e o mapa de posições.

    Args:
        texto: Texto de entrada.

    Returns:
        O texto normalizado e o mapa até o original. O ``original`` do resultado já vem com a
        codificação corrigida, quando necessário.
    """
    original, corrigido = corrigir_encoding(texto)
    saida: list[str] = []
    ini: list[int] = []
    fim: list[int] = []
    n = len(original)
    descartar = _espacos_de_quadricula(original)
    rn_m = _rn_lido_como_m(original)
    i = 0
    while i < n:
        c = original[i]
        if i in descartar:
            i += 1
            continue
        if i in rn_m:
            saida.append(rn_m[i])
            ini.append(i)
            fim.append(i + 2)
            i += 2
            continue
        j = i + 1
        while j < n and unicodedata.combining(original[j]):
            j += 1
        # Hifenização de fim de linha: em caixa mista, só é desfeita quando a linha seguinte continua
        # em minúscula, o que preserva hífens legítimos em fim de linha ("Rio-\nGrande").
        if (c in _HIFENS or c in _MARCAS_HIFENIZACAO) and saida and saida[-1].isalnum():
            k = _continuacao_de_linha(original, j)
            tratamento = _hifenizacao(saida, original, c, k) if k > 0 else ""
            if tratamento == "palavra":
                i = k
                continue
            if tratamento == "numero":
                saida.append("-")
                ini.append(i)
                fim.append(j)
                i = k
                continue
        if c in INVISIVEIS:
            i = j
            continue
        if c in ESPACOS:
            norm = " "
        elif unicodedata.category(c) == "Cc" and c not in "\n\r\t":
            i = j
            continue
        else:
            norm = unicodedata.normalize("NFKC", original[i:j]).translate(HOMOGLIFOS)
        for ch in norm:
            saida.append(ch)
            ini.append(i)
            fim.append(j)
        if c == ":" and _rotulo_colado(saida, original, j):
            saida.append(" ")
            ini.append(i)
            fim.append(j)
        i = j
    texto_norm = _corrigir_ocr_palavras(_corrigir_ocr_numerico("".join(saida)))
    return TextoNormalizado(original, texto_norm, ini, fim, corrigido)


#: Letras que o OCR costuma confundir com dígitos ("1Z3.456.789-OO") e o dígito correspondente.
_CONFUSAS = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "i": "1", "|": "1", "Z": "2", "z": "2",
                           "S": "5", "B": "8"})
#: Sequência de dígitos e letras confundíveis, com pontuação de documento, não colada a outras letras.
_RUN_NUMERICO = re.compile(r"(?<![A-Za-zÀ-ÿ])[0-9OoIli|ZzSB][0-9OoIli|ZzSB.\-/]{0,24}[0-9OoIli|ZzSB](?![A-Za-zÀ-ÿ])")


def _corrigir_ocr_numerico(texto: str) -> str:
    """Troca letras confundíveis por dígitos em trechos majoritariamente numéricos.

    A troca preserva o comprimento do texto, mantendo válido o mapa de posições. Códigos com uma
    única letra inicial — códigos da CID ("S10") e nomes como "vitamina B12" — são preservados.
    """

    def troca(m: re.Match) -> str:
        s = m.group()
        digitos = sum(c.isdigit() for c in s)
        letras = sum(c.isalpha() or c == "|" for c in s)
        if s[0].isalpha() and letras == 1:
            return s
        if digitos >= 1 and 0 < letras <= 2 * digitos + 3:
            return s.translate(_CONFUSAS)
        return s

    return _RUN_NUMERICO.sub(troca, texto)


#: Palavra com o algarismo zero entre letras ("C0STA", "WELLINGT0N").
_ZERO_EM_PALAVRA = re.compile(r"(?<![\w])[^\W\d_]+(?:0[^\W\d_]+){1,2}(?![\w])")


def _corrigir_ocr_palavras(texto: str) -> str:
    """Troca o zero confundido com a letra O dentro de palavras, preservando o comprimento.

    Só se aplica a palavras de caixa uniforme, com ao menos quatro letras, em que o zero está entre
    letras e é o único algarismo: códigos alfanuméricos (placas, lotes, protocolos) têm outros
    algarismos ou o zero na borda.
    """
    if "0" not in texto:
        return texto

    def troca(m: re.Match) -> str:
        s = m.group()
        letras = s.replace("0", "")
        if len(letras) < 4 or not (letras.isupper() or letras.islower()):
            return s
        return s.replace("0", "O" if letras.isupper() else "o")

    return _ZERO_EM_PALAVRA.sub(troca, texto)


def dobrar(texto: str) -> str:
    """Converte para minúsculas e remove acentos, preservando o comprimento.

    Cada caractere de entrada produz exatamente um caractere de saída, o que permite usar as
    posições do texto dobrado no texto original.

    Example:
        >>> dobrar("São PAULO")
        'sao paulo'
    """
    out = []
    for c in texto:
        minus = c.lower()
        if len(minus) != 1:
            minus = c
        base = unicodedata.normalize("NFD", minus)[:1]
        out.append(base if base else minus)
    return "".join(out)
