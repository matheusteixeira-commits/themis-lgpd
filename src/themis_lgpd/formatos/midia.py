"""Remoção de metadados de imagens incorporadas em documentos.

Fotos coladas em documentos Word, planilhas e PDFs carregam metadados que nenhuma revisão visual
enxerga: coordenadas GPS do local da foto, nome do autor, modelo do aparelho, data, miniaturas da
imagem original (que podem mostrar o que foi recortado) e até vídeos anexados por celulares ao fim
do arquivo JPEG. Este módulo remove esses dados **sem recomprimir** a imagem, operando diretamente
na estrutura de cada formato:

* **JPEG:** mantém apenas os segmentos necessários à decodificação. APP1 (EXIF, XMP), APP3–APP13,
  APP15, comentários e dados após o marcador de fim são removidos; o APP0 (JFIF) é regravado sem
  miniatura; APP2 só é mantido quando é perfil de cor ICC; APP14 (Adobe) é mantido por indicar a
  transformação de cor.
* **PNG:** remove blocos de texto, EXIF e data de modificação, e dados após o fim da imagem.
* **GIF:** remove comentários e extensões de aplicativo (inclusive XMP), mantendo a de animação.
* **WebP:** remove os blocos EXIF e XMP.
* **TIFF:** regrava cada página apenas com os pixels.
* **JPEG 2000 (PDF):** mantém apenas a assinatura, o cabeçalho e o fluxo codificado.

:func:`metadados_restantes` examina uma imagem e lista os metadados encontrados; é usada na
verificação final de cada formato.
"""

from __future__ import annotations

import io
import struct
import zlib
from collections.abc import Iterable, Mapping

#: Blocos PNG mantidos: os necessários à exibição correta (cor, transparência, animação).
_PNG_MANTER = frozenset({b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM", b"sRGB", b"iCCP", b"sBIT",
                         b"pHYs", b"bKGD", b"hIST", b"acTL", b"fcTL", b"fdAT", b"cICP", b"mDCv", b"cLLi"})
_ASSINATURA_PNG = b"\x89PNG\r\n\x1a\n"
#: Extensões de aplicativo do GIF que controlam a animação.
_GIF_ANIMACAO = (b"NETSCAPE2.0", b"ANIMEXTS1.0")
#: Etiquetas TIFF com informação sobre autor, equipamento, data, local ou descrição.
_TIFF_PESSOAIS = frozenset({269, 270, 271, 272, 305, 306, 315, 316, 700, 33432, 33723, 34665, 34853, 37510, 40091,
                            40092, 40093, 40094, 40095})


class ImagemInvalida(ValueError):
    """A estrutura da imagem não pôde ser interpretada."""


# ---------------------------------------------------------------------------- JPEG
def _segmentos_jpeg(dados: bytes):
    """Percorre os segmentos de um JPEG.

    Gera ``(marcador, bytes do segmento)``. Os dados codificados que seguem cada SOS são devolvidos
    com marcador ``None``; o que vier depois do marcador de fim (EOI) é devolvido com marcador ``-1``.
    """
    if dados[:2] != b"\xff\xd8":
        raise ImagemInvalida("JPEG sem marcador de início.")
    yield 0xD8, dados[:2]
    i, n = 2, len(dados)
    while i < n:
        if dados[i] != 0xFF:
            raise ImagemInvalida("Estrutura de segmentos do JPEG inválida.")
        while i + 1 < n and dados[i + 1] == 0xFF:  # bytes de preenchimento
            i += 1
        if i + 1 >= n:
            break
        marcador = dados[i + 1]
        if marcador == 0xD9:
            yield 0xD9, dados[i:i + 2]
            if i + 2 < n:
                yield -1, dados[i + 2:]
            return
        if 0xD0 <= marcador <= 0xD7 or marcador == 0x01:
            yield marcador, dados[i:i + 2]
            i += 2
            continue
        if i + 4 > n:
            raise ImagemInvalida("Segmento JPEG truncado.")
        tamanho = struct.unpack(">H", dados[i + 2:i + 4])[0]
        fim = i + 2 + tamanho
        yield marcador, dados[i:fim]
        i = fim
        if marcador == 0xDA:
            # Dados codificados: vão até o próximo marcador que não seja preenchimento (FF00) nem RSTn.
            j = i
            while j + 1 < n and not (dados[j] == 0xFF and dados[j + 1] not in (0x00, 0xFF) and
                                     not 0xD0 <= dados[j + 1] <= 0xD7):
                j += 1
            if j + 1 >= n:
                j = n
            yield None, dados[i:j]
            i = j


def _jfif_sem_miniatura(segmento: bytes) -> bytes | None:
    """APP0 JFIF regravado sem miniatura; ``None`` para APP0 que não seja JFIF (ex.: JFXX)."""
    corpo = segmento[4:]
    if not corpo.startswith(b"JFIF\x00") or len(corpo) < 14:
        return None
    novo = corpo[:12] + b"\x00\x00"  # versão, unidade e densidades; miniatura de 0 × 0
    return b"\xff\xe0" + struct.pack(">H", len(novo) + 2) + novo


def _manter_jpeg(marcador: int | None, segmento: bytes) -> bytes | None:
    if marcador is None or marcador in (0xD8, 0xD9) or not 0xE0 <= marcador <= 0xEF and marcador not in (0xFE, -1):
        return segmento
    if marcador == 0xE0:
        return _jfif_sem_miniatura(segmento)
    if marcador == 0xE2 and segmento[4:16] == b"ICC_PROFILE\x00":
        return segmento
    if marcador == 0xEE and segmento[4:9] == b"Adobe":
        return segmento
    return None


def limpar_jpeg(dados: bytes) -> bytes:
    """JPEG sem metadados, com os dados da imagem copiados byte a byte."""
    mantidos = (_manter_jpeg(marcador, segmento) for marcador, segmento in _segmentos_jpeg(dados))
    return b"".join(s for s in mantidos if s is not None)


def _restantes_jpeg(dados: bytes) -> list[str]:
    achados = []
    for marcador, segmento in _segmentos_jpeg(dados):
        if marcador == -1:
            achados.append("dados após o fim da imagem")
        elif marcador == 0xE0 and _jfif_sem_miniatura(segmento) != segmento:
            achados.append("APP0 com miniatura ou extensão")
        elif marcador is not None and (0xE1 <= marcador <= 0xEF or marcador == 0xFE) and \
                _manter_jpeg(marcador, segmento) is None:
            achados.append("EXIF/XMP/comentário" if marcador != 0xFE else "comentário")
    return achados


# ---------------------------------------------------------------------------- PNG
def _blocos_png(dados: bytes):
    if not dados.startswith(_ASSINATURA_PNG):
        raise ImagemInvalida("PNG sem assinatura.")
    i = len(_ASSINATURA_PNG)
    while i + 8 <= len(dados):
        tamanho = struct.unpack(">I", dados[i:i + 4])[0]
        tipo = dados[i + 4:i + 8]
        fim = i + 12 + tamanho
        if fim > len(dados):
            raise ImagemInvalida("Bloco PNG truncado.")
        yield tipo, dados[i:fim]
        i = fim
        if tipo == b"IEND":
            if i < len(dados):
                yield b"", dados[i:]
            return


def _bloco_png(tipo: bytes, conteudo: bytes) -> bytes:
    return struct.pack(">I", len(conteudo)) + tipo + conteudo + struct.pack(">I", zlib.crc32(tipo + conteudo))


def limpar_png(dados: bytes) -> bytes:
    """PNG apenas com os blocos de imagem; o nome do perfil de cor é neutralizado."""
    partes = [_ASSINATURA_PNG]
    for tipo, bloco in _blocos_png(dados):
        if tipo == b"iCCP":
            conteudo = bloco[8:-4]
            separador = conteudo.find(b"\x00")
            partes.append(_bloco_png(b"iCCP", b"ICC Profile" + conteudo[separador:]))
        elif tipo in _PNG_MANTER:
            partes.append(bloco)
    return b"".join(partes)


def _restantes_png(dados: bytes) -> list[str]:
    achados = []
    for tipo, bloco in _blocos_png(dados):
        if tipo == b"":
            achados.append("dados após o fim da imagem")
        elif tipo == b"iCCP" and not bloco[8:].startswith(b"ICC Profile\x00"):
            achados.append("nome do perfil de cor")
        elif tipo not in _PNG_MANTER:
            achados.append(f"bloco {tipo.decode('latin-1')}")
    return achados


# ---------------------------------------------------------------------------- GIF
def _blocos_gif(dados: bytes):
    """Gera ``(tipo, bytes)``: ``cabecalho``, ``extensao:<rótulo>:<aplicativo>``, ``imagem``, ``fim``."""
    if dados[:6] not in (b"GIF87a", b"GIF89a"):
        raise ImagemInvalida("GIF sem assinatura.")
    flags = dados[10]
    i = 13 + (3 * (2 << (flags & 7)) if flags & 0x80 else 0)
    yield "cabecalho", dados[:i]

    def sub_blocos(j: int) -> int:
        while j < len(dados) and dados[j] != 0:
            j += dados[j] + 1
        return j + 1

    while i < len(dados):
        introdutor = dados[i]
        if introdutor == 0x3B:
            yield "fim", dados[i:i + 1]
            return
        if introdutor == 0x21:
            rotulo = dados[i + 1]
            aplicativo = dados[i + 3:i + 14] if rotulo == 0xFF else b""
            fim = sub_blocos(i + 2)
            yield f"extensao:{rotulo:02x}:{aplicativo.decode('latin-1')}", dados[i:fim]
            i = fim
        elif introdutor == 0x2C:
            local = dados[i + 9]
            j = i + 10 + (3 * (2 << (local & 7)) if local & 0x80 else 0) + 1  # + tamanho mínimo do LZW
            fim = sub_blocos(j)
            yield "imagem", dados[i:fim]
            i = fim
        else:
            raise ImagemInvalida("Bloco GIF desconhecido.")


def _manter_gif(tipo: str) -> bool:
    if not tipo.startswith("extensao:"):
        return True
    _, rotulo, aplicativo = tipo.split(":", 2)
    if rotulo == "fe":
        return False
    return rotulo != "ff" or aplicativo.encode("latin-1") in _GIF_ANIMACAO


def limpar_gif(dados: bytes) -> bytes:
    """GIF sem comentários e sem extensões de aplicativo além da de animação."""
    return b"".join(bloco for tipo, bloco in _blocos_gif(dados) if _manter_gif(tipo))


# ---------------------------------------------------------------------------- WebP
def _blocos_webp(dados: bytes):
    if dados[:4] != b"RIFF" or dados[8:12] != b"WEBP":
        raise ImagemInvalida("WebP sem assinatura.")
    i = 12
    while i + 8 <= len(dados):
        tamanho = struct.unpack("<I", dados[i + 4:i + 8])[0]
        fim = i + 8 + tamanho + (tamanho & 1)  # blocos de tamanho ímpar têm um byte de preenchimento
        yield dados[i:i + 4], dados[i:fim]
        i = fim


def limpar_webp(dados: bytes) -> bytes:
    """WebP sem os blocos EXIF e XMP, com o cabeçalho VP8X atualizado."""
    blocos = []
    for tipo, bloco in _blocos_webp(dados):
        if tipo == b"VP8X":
            bloco = bloco[:8] + bytes([bloco[8] & ~0x0C]) + bloco[9:]  # sem as indicações de EXIF (0x08) e XMP (0x04)
        if tipo not in (b"EXIF", b"XMP "):
            blocos.append(bloco)
    corpo = b"WEBP" + b"".join(blocos)
    return b"RIFF" + struct.pack("<I", len(corpo)) + corpo


# ---------------------------------------------------------------------------- TIFF
def limpar_tiff(dados: bytes) -> bytes:
    """TIFF regravado apenas com os pixels de cada página (compressão sem perdas)."""
    from PIL import Image, ImageSequence

    with Image.open(io.BytesIO(dados)) as original:
        paginas = []
        for quadro in ImageSequence.Iterator(original):
            modo = quadro.mode if quadro.mode in ("1", "L", "RGB", "RGBA", "CMYK") else "RGB"
            pixels = quadro.convert(modo)
            paginas.append(Image.frombytes(modo, pixels.size, pixels.tobytes()))
    saida = io.BytesIO()
    paginas[0].save(saida, format="TIFF", save_all=True, append_images=paginas[1:], compression="tiff_deflate")
    return saida.getvalue()


def _restantes_tiff(dados: bytes) -> list[str]:
    from PIL import Image, ImageSequence

    with Image.open(io.BytesIO(dados)) as imagem:
        etiquetas = set()
        for quadro in ImageSequence.Iterator(imagem):
            etiquetas |= set(quadro.tag_v2) & _TIFF_PESSOAIS
    return [f"etiqueta TIFF {e}" for e in sorted(etiquetas)]


# ---------------------------------------------------------------------------- JPEG 2000
def limpar_jp2(dados: bytes) -> bytes:
    """JPEG 2000 apenas com assinatura, tipo, cabeçalho e fluxo codificado (sem XML, UUID/XMP)."""
    if not dados.startswith(b"\x00\x00\x00\x0cjP  "):
        return dados  # fluxo J2K puro, sem caixas de metadados
    manter, saida, i = (b"jP  ", b"ftyp", b"jp2h", b"jp2c"), [], 0
    while i + 8 <= len(dados):
        tamanho = struct.unpack(">I", dados[i:i + 4])[0]
        tipo = dados[i + 4:i + 8]
        if tamanho == 1:
            tamanho = struct.unpack(">Q", dados[i + 8:i + 16])[0]
        elif tamanho == 0:
            tamanho = len(dados) - i
        if tipo in manter:
            saida.append(dados[i:i + tamanho])
        i += tamanho
    return b"".join(saida)


# ---------------------------------------------------------------------------- interface
def formato_imagem(dados: bytes) -> str | None:
    """Formato da imagem pela assinatura, ou ``None`` se não for imagem rasterizada reconhecida."""
    if dados[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if dados.startswith(_ASSINATURA_PNG):
        return "png"
    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "webp"
    if dados[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if dados[:2] == b"BM":
        return "bmp"
    return None


def limpar_imagem(dados: bytes) -> bytes:
    """Imagem sem metadados; formatos não reconhecidos ou sem metadados são devolvidos sem alteração.

    Raises:
        ImagemInvalida: A estrutura da imagem é inválida.
    """
    formato = formato_imagem(dados)
    limpadores = {"jpeg": limpar_jpeg, "png": limpar_png, "gif": limpar_gif, "webp": limpar_webp,
                  "tiff": limpar_tiff}
    return limpadores[formato](dados) if formato in limpadores else dados


def limpar_imagens(partes: Mapping[str, bytes], nomes: Iterable[str]) -> dict[str, bytes]:
    """Versões sem metadados das imagens de um pacote.

    Args:
        partes: Conteúdo das partes do pacote, pelo nome.
        nomes: Partes a examinar; as que não forem imagens são ignoradas.

    Returns:
        Conteúdo novo de cada imagem, pelo nome da parte.

    Raises:
        ArquivoInvalido: Uma imagem tem estrutura inválida e não pode ser limpa com segurança.
    """
    from . import ArquivoInvalido

    novas = {}
    for nome in nomes:
        if formato_imagem(partes[nome]):
            try:
                novas[nome] = limpar_imagem(partes[nome])
            except (ImagemInvalida, OSError, struct.error, IndexError) as erro:
                raise ArquivoInvalido("O documento contém uma imagem corrompida.") from erro
    return novas


def metadados_restantes(dados: bytes) -> list[str]:
    """Metadados ainda presentes em uma imagem; lista vazia quando não há nenhum."""
    formato = formato_imagem(dados)
    if formato == "jpeg":
        return _restantes_jpeg(dados)
    if formato == "png":
        return _restantes_png(dados)
    if formato == "gif":
        return [t for t, _ in _blocos_gif(dados) if not _manter_gif(t)]
    if formato == "webp":
        return [f"bloco {t.decode('latin-1').strip()}" for t, _ in _blocos_webp(dados) if t in (b"EXIF", b"XMP ")]
    if formato == "tiff":
        return _restantes_tiff(dados)
    return []
