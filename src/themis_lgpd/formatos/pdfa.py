"""Acessibilidade e arquivamento do PDF gerado: camada de texto Unicode, idioma e PDF/A-2b.

* **Camada de texto invisível** com fonte incorporada (Bitstream Vera, distribuída com o ReportLab,
  licença livre): torna pesquisáveis e selecionáveis as páginas convertidas em imagem e as páginas
  digitalizadas — inclusive as sem tarja, que recebem o texto do OCR já realizado. Cada tarja recebe
  o rótulo ("[CPF]") como texto alternativo (``/ActualText``), lido por leitores de tela no lugar do
  conteúdo removido.
* **Idioma** do documento (``/Lang pt-BR``), usado por leitores de tela para a pronúncia.
* **PDF/A-2b** (ISO 19005-2, nível B): perfil de cor sRGB como *OutputIntent*, metadados XMP com a
  identificação PDF/A e mais nada — nenhum autor, título ou dado do documento original —, versão
  1.7 do formato. As páginas são todas convertidas em imagem com camada de texto, o que garante
  fontes incorporadas e espaços de cor compatíveis qualquer que seja o PDF de entrada. A conformidade
  é validada no CI com o veraPDF.
"""

from __future__ import annotations

import io
from functools import cache
from pathlib import Path

FONTE = "ThemisVera"
IDIOMA = "pt-BR"


@cache
def registrar_fonte() -> str:
    """Registra no ReportLab a fonte Unicode incorporada da camada de texto e devolve o nome."""
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    caminho = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    pdfmetrics.registerFont(TTFont(FONTE, str(caminho)))
    return FONTE


def texto_alternativo(rotulo: str) -> str:
    """Operador de conteúdo marcado com ``/ActualText`` (cadeia UTF-16BE em hexadecimal)."""
    hexa = "FEFF" + rotulo.encode("utf-16-be").hex().upper()
    return f"/Span <</ActualText <{hexa}>>> BDC"


def perfil_srgb() -> bytes:
    """Perfil ICC sRGB, gerado pelo LittleCMS do Pillow (sem arquivo externo)."""
    from PIL import ImageCms

    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def aplicar_pdfa(pdf) -> None:
    """Acrescenta ao documento (pikepdf) o *OutputIntent* sRGB e os metadados de identificação PDF/A-2b.

    Os metadados XMP contêm apenas a identificação da norma e a ferramenta: o saneamento já removeu
    os metadados do documento original, que podem conter dados pessoais.
    """
    import pikepdf

    icc = pikepdf.Stream(pdf, perfil_srgb())
    icc["/N"] = 3
    intento = pikepdf.Dictionary(
        Type=pikepdf.Name.OutputIntent, S=pikepdf.Name.GTS_PDFA1,
        OutputConditionIdentifier=pikepdf.String("sRGB IEC61966-2.1"),
        Info=pikepdf.String("sRGB IEC61966-2.1"), DestOutputProfile=icc,
    )
    pdf.Root["/OutputIntents"] = pikepdf.Array([pdf.make_indirect(intento)])
    with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
        meta["pdfaid:part"] = "2"
        meta["pdfaid:conformance"] = "B"
        meta["xmp:CreatorTool"] = "Themis LGPD"


def aplicar_idioma(pdf) -> None:
    """Declara o idioma do documento no catálogo."""
    import pikepdf

    pdf.Root["/Lang"] = pikepdf.String(IDIOMA)


def camada_de_texto(largura: float, altura: float, palavras, tarjas=()) -> bytes:
    """Página PDF transparente só com texto invisível, para sobrepor a uma página digitalizada.

    Args:
        largura: Largura da página, em pontos.
        altura: Altura da página, em pontos.
        palavras: Pares ``(palavra, caixa)`` em coordenadas com origem no canto superior esquerdo.
        tarjas: Pares ``(caixa, rótulo)`` das tarjas, escritos como texto alternativo.
    """
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(largura, altura), invariant=True, pageCompression=1,
                      initialFontName=registrar_fonte(), initialFontSize=10)
    escrever_texto(c, altura, palavras, tarjas)
    c.showPage()
    c.save()
    return buf.getvalue()


def escrever_texto(c, altura: float, palavras, tarjas=()) -> None:
    """Escreve no ``canvas`` do ReportLab a camada de texto invisível e os rótulos das tarjas.

    O ``canvas`` deve ser criado com ``initialFontName=registrar_fonte()``: a fonte inicial é
    declarada no início da página, e a padrão do ReportLab (Helvetica, não incorporada) não é
    admitida no PDF/A.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth

    fonte = registrar_fonte()
    texto = c.beginText()
    texto.setTextRenderMode(3)  # texto invisível: serve à busca, à seleção e a leitores de tela

    def escrever(conteudo: str, caixa) -> None:
        tam = max(1.0, (caixa[3] - caixa[1]) * 0.85)
        largura = stringWidth(conteudo, fonte, tam) or 1.0
        texto.setFont(fonte, tam)
        texto.setHorizScale(max(10.0, min(400.0, 100.0 * (caixa[2] - caixa[0]) / largura)))
        texto.setTextOrigin(caixa[0], altura - caixa[3] + (caixa[3] - caixa[1]) * 0.2)
        texto.textOut(conteudo)

    for palavra, caixa in palavras:
        escrever(palavra, caixa)
    for caixa, rotulo in tarjas:
        texto._code.append(texto_alternativo(rotulo))  # noqa: SLF001 - operador de conteúdo marcado
        escrever(rotulo, caixa)
        texto._code.append("EMC")  # noqa: SLF001
    c.drawText(texto)
