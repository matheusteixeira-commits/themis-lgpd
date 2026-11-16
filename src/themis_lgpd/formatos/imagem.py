"""Anonimização de imagens: arquivos PNG, JPEG e TIFF (uma ou várias páginas) e imagens incorporadas.

O texto da imagem é reconhecido por OCR e os QR codes são localizados e decodificados (ver
:mod:`themis_lgpd.formatos.qr`). O texto e o conteúdo dos QR codes são analisados — no caso de
imagens incorporadas, no mesmo lote do documento, com propagação — e as regiões a tarjar são cobertas
diretamente nos pixels. A imagem resultante é gravada sem nenhum metadado do arquivo original (EXIF,
GPS, perfil de cor, miniatura); a orientação registrada no EXIF é aplicada antes do OCR.

Após a tarja, a imagem gerada passa por novo OCR e nova leitura de QR codes; qualquer valor tarjado
ainda legível interrompe a operação.

Limitações: rostos, assinaturas manuscritas e texto que o OCR não reconhece não são detectados.
"""

from __future__ import annotations

import io

from ..motor import Anonimizador, Resultado
from . import ArquivoInvalido, FalhaOCR, ResultadoArquivo, VazamentoDetectado
from . import qr as mod_qr
from . import xml_office as X
from .pdf import Pagina, _desenhar, _montar_segmento, _uniao_por_linha
from .verificacao import valores_protegidos, valores_tarjados, verificar_ausencia

#: Limite de pixels aceito; protege contra imagens construídas para esgotar a memória ao descompactar.
MAX_PIXELS = 60_000_000

#: Margem, em pixels, acrescentada a cada tarja: as caixas do OCR são estimadas e podem cortar a borda
#: dos caracteres.
FOLGA_PIXELS = 4

#: Imagens com o menor lado abaixo deste valor (ícones, marcadores) não passam por OCR nem pela busca
#: de QR codes: não comportam texto legível.
MENOR_LADO_ANALISADO = 48

#: Formatos do Pillow usados para regravar cada tipo de imagem incorporada.
_FORMATOS_PILLOW = {"jpeg": "JPEG", "png": "PNG", "gif": "GIF", "bmp": "BMP", "tiff": "TIFF", "webp": "WEBP"}


def abrir(dados: bytes):
    """Abre a imagem, aplica a orientação do EXIF e converte para RGB.

    Raises:
        ArquivoInvalido: Imagem inválida ou acima do limite de pixels.
    """
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        img = Image.open(io.BytesIO(dados))
        img.load()
        img = ImageOps.exif_transpose(img)
    except Exception as erro:
        raise ArquivoInvalido("Imagem inválida ou grande demais.") from erro
    return img.convert("RGB")


class ImagemAnalisada:
    """OCR, QR codes e tarjas de uma imagem.

    O texto reconhecido e o conteúdo dos QR codes viram unidades de análise (ver
    :mod:`themis_lgpd.formatos.xml_office`), que podem ser analisadas sozinhas ou junto com o restante
    de um documento. As tarjas decorrentes da análise são acumuladas e aplicadas por :meth:`desenhar`.

    Args:
        img: Imagem RGB.
        modo: Modo de saída do anonimizador; fora do modo ``tarja``, o substituto é escrito na tarja.
        ocr: Executa o OCR (pode ser desligado quando só os QR codes interessam).
    """

    def __init__(self, img, modo: str, *, ocr: bool = True):
        from . import ocr as mod_ocr

        self.img = img
        self.modo = modo
        self.pagina = Pagina(0, float(img.width), float(img.height), 0)
        self.analisavel = min(img.size) >= MENOR_LADO_ANALISADO
        palavras = []
        if ocr and self.analisavel:
            palavras = [(p.texto, (p.x0, p.topo, p.x1, p.base), p.chars) for p in mod_ocr.reconhecer(img)]
        self.segmento = _montar_segmento(palavras, "ocr") if palavras else None
        if self.segmento:
            self.pagina.segmentos.append(self.segmento)
        self.codigos = mod_qr.localizar(img) if self.analisavel and mod_qr.disponivel() else []
        self.qr_tarjados = 0

    @property
    def tarjada(self) -> bool:
        """Indica se alguma região será tarjada."""
        return bool(self.pagina.tarjas)

    def unidades(self) -> list[X.Unidade]:
        """Unidades de análise: o texto do OCR e o conteúdo de cada QR code decodificado.

        BR Codes do PIX e QR codes não decodificados são marcados para tarja de imediato.
        """
        lista = []
        if self.segmento:
            lista.append(X.Unidade(self.segmento.texto, self._aplicar_texto))
        for codigo in self.codigos:
            if codigo.pix or codigo.conteudo is None:
                self._tarjar_qr(codigo)
            else:
                lista.append(X.Unidade(codigo.conteudo, self._aplicador_qr(codigo)))
        return lista

    def _aplicar_texto(self, r: Resultado) -> list[Resultado]:
        seg = self.segmento
        if r.original != seg.texto and r.tarjadas:
            # Posições não correspondem ao texto reconhecido (codificação corrigida): tarja todo o texto.
            intervalos = [(0, len(seg.texto), r.substituicoes[0]["substituto"] if r.substituicoes else "")]
        else:
            intervalos = [(s["inicio"], s["fim"], s["substituto"]) for s in r.substituicoes]
        for inicio, fim, substituto in intervalos:
            caixas = [seg.caixas[k] for k in range(inicio, min(fim, len(seg.caixas))) if seg.caixas[k]]
            for caixa in _uniao_por_linha(caixas, folga=FOLGA_PIXELS):
                self.pagina.tarjas.append(caixa)
                if self.modo != "tarja":
                    self.pagina.rotulos.append((caixa, substituto))
        return []

    def _aplicador_qr(self, codigo: mod_qr.CodigoQR):
        def aplicar(r: Resultado) -> list[Resultado]:
            if r.tarjadas:
                self._tarjar_qr(codigo)
            return []
        return aplicar

    def _tarjar_qr(self, codigo: mod_qr.CodigoQR) -> None:
        self.pagina.tarjas.append(codigo.caixa)
        self.qr_tarjados += 1

    def desenhar(self):
        """Aplica as tarjas sobre os pixels e devolve a imagem."""
        _desenhar(self.img, self.pagina, 1.0)
        return self.img

    def verificar(self, resultados: list[Resultado], permitir) -> None:
        """Relê a imagem tarjada (OCR e QR codes) e confirma que nada tarjado continua legível.

        Raises:
            VazamentoDetectado: Valor tarjado ainda legível no texto ou em um QR code.
        """
        from . import ocr as mod_ocr

        relido = " ".join(p.texto for p in mod_ocr.reconhecer(self.img)) if self.segmento else ""
        codigos = mod_qr.localizar(self.img) if self.codigos else []
        if any(c.pix for c in codigos):
            raise VazamentoDetectado("QR code PIX ainda legível na imagem gerada.")
        relido += "\n" + "\n".join(c.conteudo for c in codigos if c.conteudo)
        if verificar_ausencia(relido, valores_tarjados(resultados), valores_protegidos(resultados, permitir)):
            raise VazamentoDetectado("Trecho tarjado ainda legível na imagem gerada.")

    def codificar(self, formato: str) -> bytes:
        """Imagem tarjada no formato indicado (``png``, ``jpeg``…), sem metadados."""
        from PIL import Image

        saida = io.BytesIO()
        img = self.img
        img.info = {}
        if formato == "gif":
            img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
        opcoes = {"quality": 92} if formato in ("jpeg", "webp") else {"optimize": True} if formato == "png" else {}
        img.save(saida, format=_FORMATOS_PILLOW.get(formato, "PNG"), **opcoes)
        return saida.getvalue()


def analisar_incorporadas(partes: dict[str, bytes], nomes, modo: str, *, ocr: bool) -> dict[str, tuple]:
    """Prepara a análise das imagens rasterizadas incorporadas em um documento.

    Args:
        partes: Conteúdo das partes do pacote, pelo nome.
        nomes: Partes a examinar; as que não forem imagens rasterizadas são ignoradas.
        modo: Modo de saída do anonimizador.
        ocr: Executa o OCR. Sem ele, apenas os QR codes são examinados.

    Returns:
        ``{parte: (ImagemAnalisada, formato)}`` para as imagens grandes o bastante para conter texto.

    Raises:
        FalhaOCR: Há imagens a analisar, o OCR foi pedido e nenhum mecanismo está disponível.
        ArquivoInvalido: Imagem corrompida.
    """
    from . import ocr as mod_ocr
    from .midia import formato_imagem

    analisadas: dict[str, tuple] = {}
    for nome in nomes:
        formato = formato_imagem(partes[nome])
        if formato is None:
            continue
        img = abrir(partes[nome])
        if min(img.size) < MENOR_LADO_ANALISADO:
            continue
        if ocr and not mod_ocr.ocr_disponivel():
            raise FalhaOCR("O documento tem imagens, que exigem OCR: instale o Tesseract (idioma 'por') ou "
                           "'pip install themis-lgpd[ocr]', ou desative o OCR para processar sem analisá-las.")
        analisadas[nome] = (ImagemAnalisada(img, modo, ocr=ocr), formato)
    return analisadas


def aviso_imagens(analisadas: int, tarjadas: int, ocr: bool) -> list[str]:
    """Aviso ao usuário sobre as imagens incorporadas em um documento."""
    if not analisadas:
        return []
    if not ocr:
        return [f"{analisadas} imagem(ns) não analisada(s) por OCR (OCR desativado); apenas QR codes foram "
                "examinados. Revise-as manualmente."]
    aviso = f"{analisadas} imagem(ns) analisada(s) por OCR"
    aviso += f", {tarjadas} com tarja aplicada nos pixels" if tarjadas else ""
    return [aviso + ". Manuscritos, assinaturas e rostos não são detectados: revise as imagens."]


def anonimizar_imagem(dados: bytes, anon: Anonimizador, nome: str, *, ocr: bool = True,
                      verificar: bool = True) -> ResultadoArquivo:
    """Anonimiza uma imagem.

    Args:
        dados: Conteúdo do arquivo (PNG ou JPEG).
        anon: Anonimizador configurado.
        nome: Nome do arquivo de saída.
        ocr: Deve ser verdadeiro; imagens não têm outra fonte de texto.
        verificar: Relê a imagem gerada (OCR e QR codes) para confirmar que nada tarjado continua legível.

    Returns:
        A imagem anonimizada em PNG, os resultados da análise e os avisos ao usuário.

    Raises:
        ArquivoInvalido: Imagem corrompida, grande demais ou OCR desativado.
        FalhaOCR: Nenhum mecanismo de OCR disponível, ou falha na execução do OCR.
        VazamentoDetectado: A verificação encontrou valor tarjado legível na imagem gerada.
    """
    from . import ocr as mod_ocr

    img = abrir(dados)
    if not ocr:
        raise ArquivoInvalido("Imagens só podem ser anonimizadas com o OCR ativado.")
    if not mod_ocr.ocr_disponivel():
        raise FalhaOCR("Imagens exigem OCR: instale o Tesseract (idioma 'por') ou 'pip install themis-lgpd[ocr]'.")
    analise = ImagemAnalisada(img, anon.modo)
    unidades = analise.unidades()
    resultados = X.analisar(unidades, anon) if unidades else []
    analise.desenhar()
    if verificar and analise.tarjada:
        analise.verificar(resultados, anon.permitir)
    avisos = ["Texto reconhecido por OCR: confira se todos os dados foram tarjados (manuscritos, carimbos e "
              "fotos de rosto não são detectados)."]
    if analise.segmento is None:
        avisos.append("O OCR não reconheceu nenhum texto na imagem: revise-a manualmente.")
    if analise.qr_tarjados:
        avisos.append(f"{analise.qr_tarjados} QR code(s) tarjado(s) (PIX, conteúdo com dado pessoal ou não legível).")
    return ResultadoArquivo(analise.codificar("png"), "png", nome, resultados, avisos)


def _paginas_tiff(dados: bytes, limite_paginas: int) -> tuple[list, str, tuple | None]:
    """Páginas do TIFF em RGB, o modo de cor a usar na gravação e a resolução da primeira página.

    Raises:
        ArquivoInvalido: TIFF inválido, grande demais ou com páginas além do limite.
    """
    from PIL import Image, ImageOps, ImageSequence

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        original = Image.open(io.BytesIO(dados))
        total = getattr(original, "n_frames", 1)
    except Exception as erro:
        raise ArquivoInvalido("Imagem TIFF inválida.") from erro
    if total > limite_paginas:
        raise ArquivoInvalido(f"TIFF com {total} páginas, acima do limite de {limite_paginas}.")
    paginas, modos, dpi = [], set(), None
    try:
        for quadro in ImageSequence.Iterator(original):
            quadro.load()
            dpi = dpi or quadro.info.get("dpi")
            modos.add(quadro.mode)
            paginas.append(ImageOps.exif_transpose(quadro).convert("RGB"))
    except Exception as erro:
        raise ArquivoInvalido("Imagem TIFF inválida ou grande demais.") from erro
    finally:
        original.close()
    # Páginas em preto e branco (o padrão das digitalizadoras de documentos) continuam em 1 bit, com
    # compressão CCITT G4; páginas em tons de cinza, em 8 bits.
    modo = "1" if modos == {"1"} else "L" if modos <= {"1", "L", "LA", "I;16", "I;16B"} else "RGB"
    return paginas, modo, dpi


def anonimizar_tiff(dados: bytes, anon: Anonimizador, nome: str, *, ocr: bool = True, verificar: bool = True,
                    limite_paginas: int = 500) -> ResultadoArquivo:
    """Anonimiza um TIFF de uma ou várias páginas, como os gerados por digitalizadoras.

    O texto de todas as páginas é analisado no mesmo lote (um nome tarjado numa página é tarjado em
    todas). O arquivo gerado é um TIFF novo, com as mesmas páginas, resolução e profundidade de cor,
    sem nenhuma etiqueta de metadados do original (autor, programa, datas, EXIF, GPS, XMP).

    Raises:
        ArquivoInvalido: TIFF inválido, acima dos limites ou OCR desativado.
        FalhaOCR: Nenhum mecanismo de OCR disponível, ou falha na execução do OCR.
        VazamentoDetectado: A verificação encontrou valor tarjado legível em alguma página.
    """
    from PIL import Image

    from . import ocr as mod_ocr

    if not ocr:
        raise ArquivoInvalido("Imagens só podem ser anonimizadas com o OCR ativado.")
    if not mod_ocr.ocr_disponivel():
        raise FalhaOCR("Imagens exigem OCR: instale o Tesseract (idioma 'por') ou 'pip install themis-lgpd[ocr]'.")
    paginas, modo, dpi = _paginas_tiff(dados, limite_paginas)
    analises = [ImagemAnalisada(img, anon.modo) for img in paginas]
    unidades = [u for a in analises for u in a.unidades()]
    resultados = X.analisar(unidades, anon) if unidades else []
    for analise in analises:
        analise.desenhar()
        if verificar and analise.tarjada:
            analise.verificar(resultados, anon.permitir)

    if modo == "1":
        gravadas = [a.img.convert("L").point(lambda v: 255 if v >= 128 else 0, mode="1") for a in analises]
    else:
        gravadas = [a.img.convert(modo) for a in analises]
    gravadas = [Image.frombytes(img.mode, img.size, img.tobytes()) for img in gravadas]  # sem etiquetas
    saida = io.BytesIO()
    opcoes = {"dpi": tuple(round(float(v)) for v in dpi)} if dpi else {}
    gravadas[0].save(saida, format="TIFF", save_all=True, append_images=gravadas[1:],
                     compression="group4" if modo == "1" else "tiff_deflate", **opcoes)

    avisos = [f"Texto de {len(paginas)} página(s) reconhecido por OCR: confira se todos os dados foram tarjados "
              "(manuscritos, carimbos e fotos de rosto não são detectados)."]
    sem_texto = sum(1 for a in analises if a.segmento is None)
    if sem_texto:
        avisos.append(f"O OCR não reconheceu texto em {sem_texto} página(s): revise-a(s) manualmente.")
    qr = sum(a.qr_tarjados for a in analises)
    if qr:
        avisos.append(f"{qr} QR code(s) tarjado(s) (PIX, conteúdo com dado pessoal ou não legível).")
    return ResultadoArquivo(saida.getvalue(), "tiff", nome, resultados, avisos)
