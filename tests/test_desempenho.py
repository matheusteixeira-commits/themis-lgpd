"""Desempenho: análise linear no tamanho do texto e PDF rasterizado compacto.

Os limites são folgados para não depender da máquina: comprovam a ausência do custo quadrático e
o modo de gravação das páginas, não um tempo absoluto.
"""

import io
import random
import sys
import time
from pathlib import Path

import pikepdf
import pytest
from presidio_analyzer.context_aware_enhancers import LemmaContextAwareEnhancer

from themis_lgpd.analisador import RealceDeContexto

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
import desempenho  # noqa: E402


def test_busca_binaria_equivale_a_busca_do_presidio():
    import spacy

    doc = spacy.blank("pt")("Requerente   Maria Souza, CPF 529.982.247-25, telefone (61) 99999-8888.\n" * 30)
    indices = [t.idx for t in doc]
    realce = RealceDeContexto()
    for inicio in sorted(random.Random(3).sample(range(len(doc.text) - 1), 300)):  # nosec B311
        esperado = LemmaContextAwareEnhancer._find_index_of_match_token("x", inicio, doc, indices)
        assert realce._find_index_of_match_token("x", inicio, doc, indices) == esperado


def _tempo(anon, texto: str) -> float:
    melhores = []
    for _ in range(2):
        inicio = time.perf_counter()
        anon.analisar(texto)
        melhores.append(time.perf_counter() - inicio)
    return min(melhores)


@pytest.mark.lento
def test_analise_cresce_linearmente(anon):
    """Cinco vezes mais texto, no máximo 7,5 vezes mais tempo (linear: 5; antes da correção: 8,7 a 25)."""
    curto, longo = desempenho.texto_longo(10_000), desempenho.texto_longo(50_000)
    anon.analisar(curto)
    assert _tempo(anon, longo) / _tempo(anon, curto) < 7.5


def _imagens(pdf: bytes) -> list[tuple[str, str]]:
    saida = []
    with pikepdf.open(io.BytesIO(pdf)) as doc:
        for pagina in doc.pages:
            for _, img in pagina.images.items():
                saida.append((str(img.get("/ColorSpace")), str(img.get("/Filter"))))
    return saida


def test_pagina_de_texto_rasterizada_em_cinza_sem_perdas(anon):
    from themis_lgpd.formatos import anonimizar_arquivo

    res = anonimizar_arquivo(desempenho.pdf_de_texto(3), "processo.pdf", anon, ocr=False)
    assert _imagens(res.dados) == [("/DeviceGray", "/FlateDecode")] * 3
    assert len(res.dados) / 3 < 130 * 1024  # 1.0.0: cerca de 171 KB por página


def test_pagina_fotografica_rasterizada_em_jpeg(anon):
    import numpy as np
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    # Como uma digitalização: tons contínuos (papel, sombra, carimbo) com ruído leve do sensor.
    y, x = np.mgrid[0:2339, 0:1654]  # A4 a 200 DPI, sem ampliação na renderização
    tons = np.stack([200 + 40 * np.sin(x / 37), 190 + 50 * np.cos(y / 53), 180 + 30 * np.sin((x + y) / 71)], axis=-1)
    tons += np.random.default_rng(7).normal(0, 6, size=tons.shape)
    ruido = np.clip(tons, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(Image.fromarray(ruido)), 0, 0, width=A4[0], height=A4[1])
    c.drawString(60, 780, "Requerente com CPF 529.982.247-25")
    c.showPage()
    c.save()
    from themis_lgpd.formatos import anonimizar_arquivo

    res = anonimizar_arquivo(buf.getvalue(), "digitalizado.pdf", anon, ocr=False)
    assert _imagens(res.dados) == [("/DeviceRGB", "/DCTDecode")]
