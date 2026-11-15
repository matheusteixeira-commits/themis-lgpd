"""Construção de metarquivos EMF e WMF mínimos, com texto, para os testes."""

import struct


def _registro(tipo: int, corpo: bytes) -> bytes:
    corpo += b"\x00" * (-len(corpo) % 4)
    return struct.pack("<II", tipo, 8 + len(corpo)) + corpo


def emf(textos: list[str], emfplus: str | None = None) -> bytes:
    """EMF com um ``EMR_EXTTEXTOUTW`` por texto e, opcionalmente, um ``EmfPlusDrawString``."""
    registros = []
    for k, texto in enumerate(textos):
        cadeia = texto.encode("utf-16-le")
        cabecalho = struct.pack("<4i", 0, 0, 100, 20) + struct.pack("<Iff", 1, 1.0, 1.0)
        emrtext = struct.pack("<iiIII4iI", 10, 10 + 20 * k, len(texto), 0, 0, 0, 0, 100, 20, 0)
        posicao = 8 + len(cabecalho) + len(emrtext)
        emrtext = struct.pack("<iiIII4iI", 10, 10 + 20 * k, len(texto), posicao, 0, 0, 0, 100, 20, 0)
        registros.append(_registro(84, cabecalho + emrtext + cadeia))
    if emfplus is not None:
        cadeia = emfplus.encode("utf-16-le")
        dados = struct.pack("<III4f", 0, 0, len(emfplus), 0, 0, 100, 20) + cadeia
        dados += b"\x00" * (-len(dados) % 4)
        registro_plus = struct.pack("<HHII", 0x401C, 0, 12 + len(dados), len(dados)) + dados
        corpo = struct.pack("<I", 4 + len(registro_plus)) + b"EMF+" + registro_plus
        registros.append(_registro(70, corpo))
    eof = _registro(14, struct.pack("<III", 0, 16, 20))
    corpo_cabecalho = (struct.pack("<4i4i", 0, 0, 100, 100, 0, 0, 2000, 2000) + b" EMF" +
                       struct.pack("<IIHHIII", 0x10000, 0, 0, 0, 0, 0, 0) + struct.pack("<ii", 1024, 768) +
                       struct.pack("<ii", 320, 240))
    cabecalho = _registro(1, corpo_cabecalho)
    tamanho_total = len(cabecalho) + sum(len(r) for r in registros) + len(eof)
    quantidade = 2 + len(registros)
    corpo_cabecalho = corpo_cabecalho[:36] + struct.pack("<II", 0x10000, tamanho_total) + \
        struct.pack("<I", quantidade) + corpo_cabecalho[48:]
    return _registro(1, corpo_cabecalho) + b"".join(registros) + eof


def wmf(textos: list[str]) -> bytes:
    """WMF com um ``META_TEXTOUT`` por texto (em Windows-1252)."""
    registros = []
    for k, texto in enumerate(textos):
        cadeia = texto.encode("cp1252")
        cadeia += b"\x00" * (len(cadeia) % 2)
        corpo = struct.pack("<H", len(texto)) + cadeia + struct.pack("<hh", 10 + 20 * k, 10)
        registros.append(struct.pack("<IH", (6 + len(corpo)) // 2, 0x0521) + corpo)
    fim = struct.pack("<IH", 3, 0)
    tamanho = 9 + sum(len(r) for r in registros) // 2 + 3
    cabecalho = struct.pack("<HHHIHIH", 1, 9, 0x0300, tamanho, 0, 10, 0)
    return cabecalho + b"".join(registros) + fim
