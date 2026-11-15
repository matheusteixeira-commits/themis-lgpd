"""OCR local para páginas digitalizadas e imagens.

Mecanismos, em ordem de preferência:

1. **Tesseract** com o idioma ``por``, quando instalado no sistema: melhor qualidade em português.
   A imagem é enviada pela entrada padrão do processo, sem arquivo temporário em disco.
2. **RapidOCR** (pacote ``rapidocr-onnxruntime``, modelos ONNX incluídos no pacote): não requer
   instalação no sistema e fornece a caixa de cada caractere.

Nenhuma imagem sai da máquina. Uma falha do mecanismo de OCR interrompe o processamento: tratar a
falha como "página sem texto" entregaria a página sem tarja.
"""

from __future__ import annotations

import io
import shutil
import subprocess  # noqa: S404 - executa o binário local do Tesseract, sem shell  # nosec B404
from dataclasses import dataclass
from functools import lru_cache

from . import FalhaOCR

#: Tempo máximo de OCR de uma página pelo Tesseract, em segundos.
TEMPO_MAXIMO_S = 300


@dataclass
class Palavra:
    """Palavra reconhecida, com a caixa em pixels da imagem.

    Attributes:
        texto: Texto da palavra.
        x0: Borda esquerda.
        topo: Borda superior.
        x1: Borda direita.
        base: Borda inferior.
        chars: Caixa de cada caractere, quando o mecanismo de OCR a fornece.
    """

    texto: str
    x0: float
    topo: float
    x1: float
    base: float
    chars: list[tuple[float, float, float, float]] | None = None


@lru_cache(maxsize=1)
def _tesseract() -> str | None:
    """Caminho do Tesseract, se instalado com o idioma ``por``."""
    caminho = shutil.which("tesseract")
    if not caminho:
        return None
    try:
        idiomas = subprocess.run([caminho, "--list-langs"], capture_output=True, text=True, timeout=20,  # noqa: S603  # nosec B603
                                 check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    return caminho if "por" in idiomas.split() else None


@lru_cache(maxsize=1)
def _rapidocr():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None
    return RapidOCR()


def ocr_disponivel() -> bool:
    """Indica se algum mecanismo de OCR está disponível."""
    return bool(_tesseract() or _rapidocr())


def _via_tesseract(imagem) -> list[Palavra]:
    """OCR pelo Tesseract, com saída em TSV (uma linha por palavra, nível 5)."""
    png = io.BytesIO()
    imagem.save(png, format="PNG")
    try:
        processo = subprocess.run(  # noqa: S603 - argumentos fixos, sem shell  # nosec B603
            [_tesseract(), "stdin", "stdout", "-l", "por", "--psm", "3", "tsv"],
            input=png.getvalue(), capture_output=True, timeout=TEMPO_MAXIMO_S, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise FalhaOCR("O OCR (Tesseract) não pôde ser executado.") from erro
    if processo.returncode != 0:
        raise FalhaOCR("O OCR (Tesseract) falhou ao processar a imagem.")
    palavras = []
    for linha in processo.stdout.decode("utf-8", errors="replace").splitlines()[1:]:
        campos = linha.split("\t")
        if len(campos) < 12 or not campos[11].strip() or campos[0] != "5":
            continue
        x, y, w, h = (float(c) for c in campos[6:10])
        palavras.append(Palavra(campos[11], x, y, x + w, y + h))
    return palavras


def _via_rapidocr(imagem) -> list[Palavra]:
    """OCR pelo RapidOCR, com a caixa de cada caractere quando a versão instalada a fornece."""
    import numpy as np

    resultado, _ = _rapidocr()(np.asarray(imagem.convert("RGB")), return_word_box=True)
    palavras = []
    for item in resultado or []:
        caixa, texto = item[0], item[1]
        if len(item) >= 5 and len(item[3]) == len(item[4]):
            # Caixas por caractere: as palavras são montadas com precisão de pixel.
            atual: list = []
            for ch, cx in [*zip(item[4], item[3]), (" ", None)]:
                if ch.strip() and cx is not None:
                    xs, ys = [p[0] for p in cx], [p[1] for p in cx]
                    atual.append((ch, (min(xs), min(ys), max(xs), max(ys))))
                elif atual:
                    cs = [c for _, c in atual]
                    palavras.append(Palavra("".join(c for c, _ in atual), min(c[0] for c in cs), min(c[1] for c in cs),
                                            max(c[2] for c in cs), max(c[3] for c in cs), cs))
                    atual = []
            continue
        # Versões que devolvem apenas a caixa da linha: a largura é repartida proporcionalmente entre
        # as palavras, com um caractere de margem de cada lado para compensar a estimativa.
        xs, ys = [p[0] for p in caixa], [p[1] for p in caixa]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        partes = texto.split()
        total = sum(len(p) for p in partes) + max(0, len(partes) - 1)
        largura_char = (x1 - x0) / max(1, total)
        cursor = x0
        for p in partes:
            largura = largura_char * len(p)
            palavras.append(Palavra(p, max(x0, cursor - largura_char), y0, min(x1, cursor + largura + largura_char), y1))
            cursor += largura + largura_char
    return palavras


def reconhecer(imagem) -> list[Palavra]:
    """Reconhece as palavras de uma imagem.

    Args:
        imagem: Imagem do Pillow.

    Returns:
        Palavras com caixas em pixels da imagem.

    Raises:
        FalhaOCR: Nenhum mecanismo disponível ou falha na execução.
    """
    if _tesseract():
        return _via_tesseract(imagem)
    if _rapidocr():
        return _via_rapidocr(imagem)
    raise FalhaOCR("OCR indisponível: instale o Tesseract com o idioma 'por' ou 'pip install themis-lgpd[ocr]'.")
