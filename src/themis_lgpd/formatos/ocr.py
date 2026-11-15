"""OCR local para páginas digitalizadas e imagens.

Mecanismos, em ordem de preferência:

1. **Tesseract** com o idioma ``por``, quando instalado no sistema: melhor qualidade em português.
   A imagem é enviada pela entrada padrão do processo, sem arquivo temporário em disco.
2. **RapidOCR** (pacote ``rapidocr`` com ``onnxruntime``; modelo multilíngue PP-OCRv6 incluído no
   pacote, com suporte a português e acentuação): não requer instalação no sistema nem acesso à
   rede e fornece a caixa de cada caractere.

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
        from rapidocr import RapidOCR
    except ImportError:
        return None
    # Os modelos padrão vêm no pacote; o nível "error" evita registrar o andamento de cada imagem.
    return RapidOCR(params={"Global.log_level": "error"})


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


def _caixa(pontos) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in pontos], [p[1] for p in pontos]
    return float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))


def _palavra(chars: list[tuple[str, tuple[float, float, float, float]]]) -> Palavra:
    caixas = [c for _, c in chars]
    return Palavra("".join(t for t, _ in chars), min(c[0] for c in caixas), min(c[1] for c in caixas),
                   max(c[2] for c in caixas), max(c[3] for c in caixas), caixas)


def _separar_coladas(palavra: Palavra) -> list[Palavra]:
    """Separa palavras coladas pelo OCR na passagem de minúscula para maiúscula.

    Em digitalizações de baixa resolução, o OCR pode omitir os espaços ("formuladoporJoanaPereira"),
    o que impediria o reconhecimento do nome. Sequências longas com transições minúscula → maiúscula
    são divididas nesses pontos; siglas e nomes em caixa alta não são afetados.
    """
    texto = palavra.texto
    if len(texto) < 16 or not palavra.chars or len(palavra.chars) != len(texto):
        return [palavra]
    cortes = [i for i in range(1, len(texto)) if texto[i - 1].islower() and texto[i].isupper()]
    if not cortes:
        return [palavra]
    partes, inicio = [], 0
    for fim in [*cortes, len(texto)]:
        partes.append(_palavra(list(zip(texto[inicio:fim], palavra.chars[inicio:fim]))))
        inicio = fim
    return partes


def _via_rapidocr(imagem) -> list[Palavra]:
    """OCR pelo RapidOCR, com a caixa de cada caractere.

    O RapidOCR devolve, por linha, o texto (com espaços) e as caixas dos caracteres visíveis. As
    palavras são montadas alinhando as caixas ao texto; se a contagem não coincidir, a largura da
    linha é repartida proporcionalmente, com um caractere de margem de cada lado.
    """
    import numpy as np

    saida = _rapidocr()(np.asarray(imagem.convert("RGB")), return_word_box=True, return_single_char_box=True)
    palavras: list[Palavra] = []
    for texto, caixa_linha, caracteres in zip(saida.txts or (), saida.boxes if saida.boxes is not None else (),
                                              saida.word_results or ()):
        caixas = [_caixa(c[2]) for c in caracteres if c[2] is not None and str(c[0]).strip()]
        if len(caixas) == sum(1 for ch in texto if not ch.isspace()):
            atual: list[tuple[str, tuple[float, float, float, float]]] = []
            visiveis = iter(caixas)
            for ch in [*texto, " "]:
                if ch.isspace():
                    if atual:
                        palavras += _separar_coladas(_palavra(atual))
                    atual = []
                else:
                    atual.append((ch, next(visiveis)))
            continue
        x0, y0, x1, y1 = _caixa(caixa_linha)
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
