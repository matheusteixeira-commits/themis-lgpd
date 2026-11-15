"""Normalização de texto para detecção, com mapa de posições até o texto original.

A detecção é feita sobre uma versão normalizada do texto, que neutraliza variações de escrita
usadas — intencionalmente ou não — para escapar de reconhecedores:

* forma de compatibilidade Unicode (NFKC): dígitos de largura total, ligaduras, sobrescritos;
* remoção de caracteres invisíveis (espaço de largura zero, marcas de direção de texto);
* espaços especiais convertidos em espaço comum;
* homóglifos: letras cirílicas e gregas idênticas às latinas ("Мaria" com M cirílico);
* hifenização de fim de linha desfeita ("Apa-\\nrecida" → "Aparecida");
* letras confundidas com dígitos pelo OCR, apenas em trechos majoritariamente numéricos.

A substituição, porém, é sempre aplicada sobre o texto **original**: o mapa de posições traduz cada
achado de volta, e o documento publicado só muda nos trechos tarjados.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

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
    i = 0
    while i < n:
        c = original[i]
        j = i + 1
        while j < n and unicodedata.combining(original[j]):
            j += 1
        # Hifenização de fim de linha entre letras: só é desfeita quando a linha seguinte continua
        # em minúscula, o que preserva hífens legítimos em fim de linha ("Rio-\nGrande").
        if c == "-" and j < n and original[j] == "\n" and saida and _eh_letra(saida[-1]):
            k = j + 1
            while k < n and original[k] in " \t":
                k += 1
            if k < n and original[k].islower():
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
        i = j
    return TextoNormalizado(original, _corrigir_ocr_numerico("".join(saida)), ini, fim, corrigido)


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
