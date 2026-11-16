"""Tarja manual por região em PDFs e imagens.

Assinaturas manuscritas, fotos de rosto, carimbos e impressões digitais não são texto e escapam à
análise automática. O revisor marca a região e ela é coberta como as demais tarjas: nos PDFs, a
página é convertida em imagem e as palavras sob a região deixam de existir na camada de texto; nas
imagens, os pixels são cobertos.

Uma região é dada em frações da página (de 0 a 1, com origem no canto superior esquerdo), na
orientação em que a página é exibida. A mesma marcação vale para qualquer tamanho de página e
resolução — inclusive a da pré-visualização da interface. Na linha de comando e na API, a região é
escrita em porcentagens: ``1:10,70,45,85`` é a página 1, de 10% a 45% da largura e de 70% a 85% da
altura.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from . import ArquivoInvalido

_FORMATO = re.compile(r"^\s*(\d+)\s*:\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*$")


@dataclass(frozen=True)
class Regiao:
    """Região retangular de uma página, em frações da largura e da altura exibidas.

    Attributes:
        pagina: Número da página, a partir de 1 (imagens têm uma página; TIFF, uma por quadro).
        x0, y0, x1, y1: Cantos superior esquerdo e inferior direito, de 0 a 1.

    Raises:
        ValueError: Página menor que 1 ou coordenadas fora do intervalo ou invertidas.
    """

    pagina: int
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self):
        if self.pagina < 1:
            raise ValueError("a página da região começa em 1")
        if not (0 <= self.x0 < self.x1 <= 1 and 0 <= self.y0 < self.y1 <= 1):
            raise ValueError("a região deve ter início antes do fim, dentro da página (de 0% a 100%)")

    def caixa(self, largura: float, altura: float) -> tuple[float, float, float, float]:
        """Caixa da região na página exibida com a largura e a altura indicadas (pontos ou pixels)."""
        return self.x0 * largura, self.y0 * altura, self.x1 * largura, self.y1 * altura

    def __str__(self) -> str:
        return f"{self.pagina}:" + ",".join(f"{v * 100:g}" for v in (self.x0, self.y0, self.x1, self.y1))


def interpretar(texto: str) -> Regiao:
    """Lê uma região escrita como ``página:x0,y0,x1,y1``, com as coordenadas em porcentagem.

    Raises:
        ValueError: Texto fora do formato ou região inválida (mensagem destinada ao usuário).
    """
    achado = _FORMATO.match(texto or "")
    if not achado:
        raise ValueError(f"região '{texto}' fora do formato página:x0,y0,x1,y1 (porcentagens, ex.: 1:10,70,45,85)")
    pagina, *valores = achado.groups()
    return Regiao(int(pagina), *(float(v) / 100 for v in valores))


def interpretar_lista(texto: str) -> list[Regiao]:
    """Lê várias regiões separadas por ponto e vírgula ou por linha.

    Raises:
        ValueError: Alguma região inválida.
    """
    return [interpretar(parte) for parte in re.split(r"[;\n]", texto or "") if parte.strip()]


def por_pagina(regioes: Iterable[Regiao], paginas: int) -> dict[int, list[Regiao]]:
    """Regiões agrupadas pelo índice da página (a partir de 0).

    Raises:
        ArquivoInvalido: Região numa página que o documento não tem.
    """
    grupos: dict[int, list[Regiao]] = {}
    for regiao in regioes:
        if regiao.pagina > paginas:
            raise ArquivoInvalido(f"Região indicada na página {regiao.pagina}, mas o documento tem {paginas} "
                                  "página(s).")
        grupos.setdefault(regiao.pagina - 1, []).append(regiao)
    return grupos


def aviso(regioes: list[Regiao]) -> list[str]:
    """Aviso ao usuário sobre as regiões tarjadas manualmente."""
    if not regioes:
        return []
    paginas = sorted({r.pagina for r in regioes})
    return [f"{len(regioes)} região(ões) tarjada(s) manualmente na(s) página(s) {', '.join(map(str, paginas))}."]
