"""Gera PDFs anonimizados no modo PDF/A-2b para validação pelo veraPDF.

Produz, na pasta indicada, a versão anonimizada em PDF/A de documentos com características
diferentes: texto com fontes não incorporadas (as 14 fontes padrão), página digitalizada (só imagem,
com OCR), página com cor CMYK e o exemplo fictício de ``exemplos/``. O CI executa em seguida o veraPDF
(imagem oficial ``verapdf/cli``) sobre a pasta e falha se algum arquivo não estiver conforme.

Uso::

    python scripts/validar_pdfa.py <pasta de saída>
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _texto_fontes_padrao() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Times-Roman", 12)
    c.drawString(60, 790, "Requerente: Maria Aparecida Souza, CPF 529.982.247-25 — ação, função, coração.")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, 760, "Endereço: Rua das Acácias, 45, Goiânia/GO.")
    c.showPage()
    c.drawString(60, 790, "Segunda página sem dado pessoal: relatório anual de gestão.")
    c.showPage()
    c.save()
    return buf.getvalue()


def _digitalizada() -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    img = Image.new("RGB", (1654, 2339), "white")
    desenho = ImageDraw.Draw(img)
    try:
        fonte = ImageFont.truetype("DejaVuSans.ttf", 40)
    except OSError:
        import reportlab

        fonte = ImageFont.truetype(str(Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"), 40)
    desenho.text((140, 200), "Requerente: Maria Souza, CPF 529.982.247-25", fill="black", font=fonte)
    desenho.text((140, 300), "Pedido de acesso a informacao.", fill="black", font=fonte)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(img), 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()
    return buf.getvalue()


def _cmyk() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFillColorCMYK(0.1, 0.8, 0.2, 0.0)
    c.rect(50, 600, 300, 100, fill=1, stroke=0)
    c.setFillColorCMYK(0, 0, 0, 1)
    c.drawString(60, 790, "Contato do requerente: joao.silva@exemplo.com.br")
    c.showPage()
    c.save()
    return buf.getvalue()


def main() -> int:
    from themis_lgpd import Anonimizador
    from themis_lgpd.formatos import anonimizar_arquivo

    saida = Path(sys.argv[1])
    saida.mkdir(parents=True, exist_ok=True)
    anon = Anonimizador("lai")
    entradas = {
        "texto_fontes_padrao.pdf": _texto_fontes_padrao(),
        "digitalizada.pdf": _digitalizada(),
        "cmyk.pdf": _cmyk(),
        "despacho_ficticio.pdf": (RAIZ / "exemplos" / "despacho_ficticio.pdf").read_bytes(),
    }
    for nome, dados in entradas.items():
        res = anonimizar_arquivo(dados, nome, anon, pdfa=True)
        (saida / nome).write_bytes(res.dados)
        print(f"{nome}: {sum(len(r.tarjadas) for r in res.resultados)} tarja(s), {len(res.dados) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
