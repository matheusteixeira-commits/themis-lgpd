"""Localização e decodificação de QR codes em páginas e imagens.

Um QR code é texto legível por qualquer celular, mesmo depois de o texto ao redor ser tarjado. O
BR Code do PIX (padrão EMV, usado em boletos, GRU e cobranças) contém o nome do recebedor e a chave
PIX, que pode ser CPF, e-mail ou telefone; crachás e etiquetas costumam codificar nome e matrícula.

Política de tarja (aplicada pelos formatos):

* BR Code PIX: sempre tarjado.
* QR code decodificado: o conteúdo é analisado como o restante do documento e o código é tarjado se
  contiver dado a tarjar. QR codes com conteúdo público (ex.: endereço de conferência de autenticidade
  de documentos) permanecem.
* QR code localizado, mas não decodificado: tarjado, pois o conteúdo não pode ser verificado.

A detecção usa o OpenCV (``QRCodeDetectorAruco``, mais sensível a códigos pequenos, com o detector
padrão como alternativa).
"""

from __future__ import annotations

from dataclasses import dataclass

#: Margem, em fração do lado do código, acrescentada à tarja (inclui a zona de silêncio).
MARGEM = 0.12


@dataclass
class CodigoQR:
    """QR code localizado.

    Attributes:
        caixa: Caixa em pixels da imagem, com margem: (x0, topo, x1, base).
        conteudo: Texto decodificado, ou ``None`` quando não foi possível decodificar.
    """

    caixa: tuple[float, float, float, float]
    conteudo: str | None

    @property
    def pix(self) -> bool:
        """Indica se o conteúdo é um BR Code do PIX."""
        return bool(self.conteudo) and self.conteudo.startswith("000201") and "BR.GOV.BCB.PIX" in self.conteudo.upper()


def disponivel() -> bool:
    """Indica se o OpenCV está instalado."""
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False
    return True


def localizar(imagem) -> list[CodigoQR]:
    """Localiza e decodifica os QR codes de uma imagem do Pillow."""
    import cv2
    import numpy as np

    cinza = np.asarray(imagem.convert("L"))
    detectores = [d for d in (getattr(cv2, "QRCodeDetectorAruco", None), cv2.QRCodeDetector) if d is not None]
    for detector in detectores:
        encontrou, textos, pontos, _ = detector().detectAndDecodeMulti(cinza)
        if encontrou and pontos is not None and len(pontos):
            codigos = []
            for texto, quadrilatero in zip(textos, pontos):
                xs, ys = quadrilatero[:, 0], quadrilatero[:, 1]
                lado = max(float(xs.max() - xs.min()), float(ys.max() - ys.min()))
                folga = lado * MARGEM
                caixa = (max(0.0, float(xs.min()) - folga), max(0.0, float(ys.min()) - folga),
                         min(float(imagem.width), float(xs.max()) + folga),
                         min(float(imagem.height), float(ys.max()) + folga))
                codigos.append(CodigoQR(caixa, texto or None))
            return codigos
    return []
