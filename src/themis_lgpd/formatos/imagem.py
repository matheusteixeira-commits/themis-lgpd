"""Anonimização de imagens (PNG e JPEG) por OCR local.

O texto da imagem é reconhecido por OCR, analisado, e as regiões dos trechos tarjados são cobertas
diretamente nos pixels. A imagem resultante é gravada como um PNG novo: nenhum metadado do arquivo
original (EXIF, GPS, perfil de cor com nome do equipamento, miniatura incorporada) é copiado.

Após a tarja, a imagem gerada passa por novo OCR e o resultado é comparado com os valores tarjados;
qualquer valor ainda legível interrompe a operação.

Limitações: rostos, assinaturas manuscritas e texto que o OCR não reconhece não são detectados.
O aviso devolvido ao usuário registra essa limitação.
"""

from __future__ import annotations

import io

from ..motor import Anonimizador
from . import ArquivoInvalido, FalhaOCR, ResultadoArquivo, VazamentoDetectado
from .pdf import Pagina, _desenhar, _montar_segmento, _uniao_por_linha
from .verificacao import valores_protegidos, valores_tarjados, verificar_ausencia

#: Limite de pixels aceito; protege contra imagens construídas para esgotar a memória ao descompactar.
MAX_PIXELS = 60_000_000

#: Margem, em pixels, acrescentada a cada tarja: as caixas do OCR são estimadas e podem cortar a borda
#: dos caracteres.
FOLGA_PIXELS = 4


def anonimizar_imagem(dados: bytes, anon: Anonimizador, nome: str, *, ocr: bool = True,
                      verificar: bool = True) -> ResultadoArquivo:
    """Anonimiza uma imagem.

    Args:
        dados: Conteúdo do arquivo (PNG ou JPEG).
        anon: Anonimizador configurado.
        nome: Nome do arquivo de saída.
        ocr: Deve ser verdadeiro; imagens não têm outra fonte de texto.
        verificar: Executa novo OCR na imagem gerada para confirmar que nada tarjado continua legível.

    Returns:
        A imagem anonimizada em PNG, os resultados da análise e os avisos ao usuário.

    Raises:
        ArquivoInvalido: Imagem corrompida, grande demais ou OCR desativado.
        FalhaOCR: Nenhum mecanismo de OCR disponível, ou falha na execução do OCR.
        VazamentoDetectado: A verificação encontrou valor tarjado legível na imagem gerada.
    """
    from PIL import Image

    from . import ocr as mod_ocr

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        img = Image.open(io.BytesIO(dados))
        img.load()
    except Exception as erro:
        raise ArquivoInvalido("Imagem inválida ou grande demais.") from erro
    img = img.convert("RGB")
    if not ocr:
        raise ArquivoInvalido("Imagens só podem ser anonimizadas com o OCR ativado.")
    if not mod_ocr.ocr_disponivel():
        raise FalhaOCR("Imagens exigem OCR: instale o Tesseract (idioma 'por') ou 'pip install themis-lgpd[ocr]'.")
    palavras = [(p.texto, (p.x0, p.topo, p.x1, p.base), p.chars) for p in mod_ocr.reconhecer(img)]
    pag = Pagina(0, float(img.width), float(img.height), 0)
    resultados = []
    if palavras:
        seg = _montar_segmento(palavras, "ocr")
        pag.segmentos.append(seg)
        resultados = anon.anonimizar_lote([seg.texto], mesmo_documento=True)
        for s in resultados[0].substituicoes:
            caixas = [seg.caixas[k] for k in range(s["inicio"], min(s["fim"], len(seg.caixas))) if seg.caixas[k]]
            for caixa in _uniao_por_linha(caixas, folga=FOLGA_PIXELS):
                pag.tarjas.append(caixa)
                if anon.modo != "tarja":
                    pag.rotulos.append((caixa, s["substituto"]))
    _desenhar(img, pag, 1.0)
    if verificar and pag.tarjas:
        relido = " ".join(p.texto for p in mod_ocr.reconhecer(img))
        if verificar_ausencia(relido, valores_tarjados(resultados), valores_protegidos(resultados, anon.permitir)):
            raise VazamentoDetectado("Trecho tarjado ainda legível na imagem gerada.")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    avisos = ["Texto reconhecido por OCR: confira se todos os dados foram tarjados (manuscritos, carimbos e "
              "fotos de rosto não são detectados)."]
    if not palavras:
        avisos.append("O OCR não reconheceu nenhum texto na imagem: revise-a manualmente.")
    return ResultadoArquivo(buf.getvalue(), "png", nome, resultados, avisos)
