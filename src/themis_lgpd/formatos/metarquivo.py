"""Texto em metarquivos do Windows (EMF e WMF) incorporados em documentos Office.

Ao colar uma tabela do Excel ou um diagrama no Word como imagem, o Office grava um metarquivo: uma
sequência de comandos de desenho em que o texto de cada célula ou rótulo fica legível dentro do
arquivo, embora apareça como imagem. Este módulo localiza esse texto, para que seja analisado com o
restante do documento, e mascara os trechos tarjados **no próprio arquivo**, substituindo cada
caractere por um bloco (``█``) ou, em texto de 8 bits, por ``X``. O comprimento das cadeias não muda,
de modo que a estrutura do metarquivo permanece válida.

Registros com texto tratados:

* EMF: ``EMR_EXTTEXTOUTA``/``W``, ``EMR_POLYTEXTOUTA``/``W``, ``EMR_SMALLTEXTOUT`` e, dentro de
  comentários EMF+, ``EmfPlusDrawString`` e ``EmfPlusDrawDriverString`` com código de caracteres.
* WMF: ``META_TEXTOUT`` e ``META_EXTTEXTOUT``.

``EmfPlusDrawDriverString`` com índices de glifos (sem código de caracteres) não pode ser lido; o
metarquivo é então marcado como não analisável.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

_BLOCO_UTF16 = "█".encode("utf-16-le")
_BLOCO_8BITS = b"X"

# Tipos de registro EMF.
_EMR_HEADER, _EMR_EOF, _EMR_COMMENT = 1, 14, 70
_EMR_EXTTEXTOUTA, _EMR_EXTTEXTOUTW = 83, 84
_EMR_POLYTEXTOUTA, _EMR_POLYTEXTOUTW = 96, 97
_EMR_SMALLTEXTOUT = 108
_ETO_NO_RECT, _ETO_SMALL_CHARS = 0x100, 0x200
# Registros EMF+.
_EMFPLUS_DRAWSTRING, _EMFPLUS_DRAWDRIVERSTRING = 0x401C, 0x4036
_DRIVER_STRING_CMAP_LOOKUP = 0x1
# Registros WMF.
_META_TEXTOUT, _META_EXTTEXTOUT = 0x0521, 0x0A32
_ETO_OPAQUE, _ETO_CLIPPED = 0x0002, 0x0004


class MetarquivoInvalido(ValueError):
    """A estrutura do metarquivo não pôde ser interpretada."""


@dataclass
class Trecho:
    """Cadeia de texto dentro do metarquivo.

    Attributes:
        posicao: Posição do primeiro byte da cadeia no arquivo.
        caracteres: Quantidade de caracteres.
        largura: Bytes por caractere (2 para UTF-16, 1 para texto de 8 bits).
    """

    posicao: int
    caracteres: int
    largura: int

    def texto(self, dados: bytes | bytearray) -> str:
        bruto = bytes(dados[self.posicao:self.posicao + self.caracteres * self.largura])
        return bruto.decode("utf-16-le", errors="replace") if self.largura == 2 else bruto.decode("cp1252", "replace")


@dataclass
class Metarquivo:
    """Metarquivo com as cadeias de texto localizadas."""

    dados: bytearray
    trechos: list[Trecho] = field(default_factory=list)
    ilegivel: bool = False

    @property
    def texto(self) -> str:
        """Texto de todas as cadeias, uma por linha."""
        return "\n".join(t.texto(self.dados) for t in self.trechos)

    def mascarar(self, inicio: int, fim: int) -> None:
        """Mascara os caracteres entre ``inicio`` e ``fim`` de :attr:`texto`."""
        posicao = 0
        for trecho in self.trechos:
            a, b = max(inicio, posicao), min(fim, posicao + trecho.caracteres)
            for k in range(a - posicao, b - posicao):
                byte = trecho.posicao + k * trecho.largura
                self.dados[byte:byte + trecho.largura] = _BLOCO_UTF16 if trecho.largura == 2 else _BLOCO_8BITS
            posicao += trecho.caracteres + 1  # separador de linha


def _u16(dados, i):
    return struct.unpack_from("<H", dados, i)[0]


def _u32(dados, i):
    return struct.unpack_from("<I", dados, i)[0]


def _trecho(dados: bytes, posicao: int, caracteres: int, largura: int, limite: int) -> Trecho:
    if caracteres < 0 or posicao < 0 or posicao + caracteres * largura > limite:
        raise MetarquivoInvalido("Cadeia de texto fora do registro.")
    return Trecho(posicao, caracteres, largura)


def _emfplus(dados: bytes, inicio: int, fim: int, meta: Metarquivo) -> None:
    """Registros EMF+ contidos em um comentário EMF."""
    i = inicio
    while i + 12 <= fim:
        tipo, flags, tamanho, tamanho_dados = struct.unpack_from("<HHII", dados, i)
        if tamanho < 12 or i + tamanho > fim:
            raise MetarquivoInvalido("Registro EMF+ inválido.")
        corpo = i + 12
        if tipo == _EMFPLUS_DRAWSTRING:
            meta.trechos.append(_trecho(dados, corpo + 28, _u32(dados, corpo + 8), 2, i + tamanho))
        elif tipo == _EMFPLUS_DRAWDRIVERSTRING:
            opcoes, glifos = _u32(dados, corpo + 4), _u32(dados, corpo + 12)
            if opcoes & _DRIVER_STRING_CMAP_LOOKUP:
                meta.trechos.append(_trecho(dados, corpo + 16, glifos, 2, i + tamanho))
            elif glifos:
                meta.ilegivel = True
        i += tamanho


def _emf(dados: bytes) -> Metarquivo:
    meta = Metarquivo(bytearray(dados))
    i = 0
    while i + 8 <= len(dados):
        tipo, tamanho = struct.unpack_from("<II", dados, i)
        if tamanho < 8 or tamanho % 4 or i + tamanho > len(dados):
            raise MetarquivoInvalido("Registro EMF inválido.")
        fim = i + tamanho
        if tipo in (_EMR_EXTTEXTOUTA, _EMR_EXTTEXTOUTW):
            largura = 2 if tipo == _EMR_EXTTEXTOUTW else 1
            meta.trechos.append(_trecho(dados, i + _u32(dados, i + 48), _u32(dados, i + 44), largura, fim))
        elif tipo in (_EMR_POLYTEXTOUTA, _EMR_POLYTEXTOUTW):
            largura = 2 if tipo == _EMR_POLYTEXTOUTW else 1
            for k in range(_u32(dados, i + 36)):
                texto = i + 40 + 40 * k
                meta.trechos.append(_trecho(dados, i + _u32(dados, texto + 12), _u32(dados, texto + 8), largura, fim))
        elif tipo == _EMR_SMALLTEXTOUT:
            caracteres, opcoes = _u32(dados, i + 16), _u32(dados, i + 20)
            posicao = i + (36 if opcoes & _ETO_NO_RECT else 52)
            meta.trechos.append(_trecho(dados, posicao, caracteres, 1 if opcoes & _ETO_SMALL_CHARS else 2, fim))
        elif tipo == _EMR_COMMENT and tamanho >= 16 and dados[i + 12:i + 16] == b"EMF+":
            _emfplus(dados, i + 16, i + 12 + _u32(dados, i + 8), meta)
        i = fim
        if tipo == _EMR_EOF:
            break
    return meta


def _wmf(dados: bytes) -> Metarquivo:
    meta = Metarquivo(bytearray(dados))
    i = 22 if dados[:4] == b"\xd7\xcd\xc6\x9a" else 0  # cabeçalho "placeable" opcional
    i += _u16(dados, i + 2) * 2  # cabeçalho META_HEADER (tamanho em palavras de 16 bits)
    while i + 6 <= len(dados):
        palavras, funcao = _u32(dados, i), _u16(dados, i + 4)
        tamanho = palavras * 2
        if tamanho < 6 or i + tamanho > len(dados):
            raise MetarquivoInvalido("Registro WMF inválido.")
        fim = i + tamanho
        if funcao == 0:
            break
        if funcao == _META_TEXTOUT:
            meta.trechos.append(_trecho(dados, i + 8, _u16(dados, i + 6), 1, fim))
        elif funcao == _META_EXTTEXTOUT:
            caracteres, opcoes = _u16(dados, i + 10), _u16(dados, i + 12)
            posicao = i + 14 + (8 if opcoes & (_ETO_OPAQUE | _ETO_CLIPPED) else 0)
            meta.trechos.append(_trecho(dados, posicao, caracteres, 1, fim))
        i = fim
    return meta


def tipo_metarquivo(dados: bytes) -> str | None:
    """``emf``, ``wmf`` ou ``None``."""
    if len(dados) >= 44 and _u32(dados, 0) == _EMR_HEADER and dados[40:44] == b" EMF":
        return "emf"
    if dados[:4] == b"\xd7\xcd\xc6\x9a" or dados[:6] in (b"\x01\x00\x09\x00\x00\x03", b"\x02\x00\x09\x00\x00\x03"):
        return "wmf"
    return None


def ler(dados: bytes) -> Metarquivo:
    """Localiza as cadeias de texto de um metarquivo.

    Raises:
        MetarquivoInvalido: Estrutura inválida ou formato não reconhecido.
    """
    tipo = tipo_metarquivo(dados)
    try:
        if tipo == "emf":
            return _emf(dados)
        if tipo == "wmf":
            return _wmf(dados)
    except struct.error as erro:
        raise MetarquivoInvalido("Metarquivo truncado.") from erro
    raise MetarquivoInvalido("Formato de metarquivo não reconhecido.")
