"""Gera ``dados/prenomes_ibge.txt`` com os prenomes mais frequentes do Censo Demográfico 2010.

A API de Nomes do IBGE (https://servicodados.ibge.gov.br/api/docs/nomes) devolve os 20 prenomes
mais frequentes de cada recorte. O script percorre os recortes por sexo, década de nascimento e
unidade da federação, o que reúne os nomes comuns em cada região e geração — inclusive os
regionais (Raimunda, Francisca, Iracema) e os de gerações recentes (Kauã, Ryan, Yasmin) — que as
listas genéricas não trazem.

Os dados são públicos e podem ser reproduzidos com citação da fonte (IBGE, Censo Demográfico
2010). O arquivo gerado é versionado: a anonimização nunca acessa a rede.

Uso::

    python scripts/gerar_prenomes_ibge.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from themis_lgpd.texto import dobrar  # noqa: E402

URL = "https://servicodados.ibge.gov.br/api/v2/censos/nomes/ranking?sexo={sexo}&decada={decada}&localidade={uf}"
#: Códigos IBGE das 27 unidades da federação.
UFS = (11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 32, 33, 35, 41, 42, 43, 50, 51, 52, 53)
DECADAS = (1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000)
#: Prenomes frequentes que também são palavras comuns; ficam fora da lista para não iniciar nomes
#: em textos comuns (já são tratados como ambíguos pelas listas principais quando necessário).
EXCLUIR = {"gloria", "luz", "paz", "sol", "flor", "rosa", "clara", "vitoria", "aurora", "graca", "ida", "domingo",
           "divina", "divino", "amara"}
DESTINO = Path(__file__).resolve().parents[1] / "src" / "themis_lgpd" / "dados" / "prenomes_ibge.txt"


def consultar(sexo: str, decada: int, uf: int) -> list[str]:
    """Os 20 prenomes mais frequentes do recorte."""
    url = URL.format(sexo=sexo, decada=decada, uf=uf)
    for tentativa in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 - URL fixa do IBGE
                return [item["nome"] for item in json.load(r)[0]["res"]]
        except (OSError, ValueError, IndexError, KeyError):
            time.sleep(2 * (tentativa + 1))
    raise RuntimeError(f"falha ao consultar {url}")


def main() -> int:
    recortes = [(s, d, u) for s in ("f", "m") for d in DECADAS for u in UFS]
    with ThreadPoolExecutor(max_workers=6) as pool:
        resultados = list(pool.map(lambda r: consultar(*r), recortes))
    nomes = sorted({dobrar(n) for lista in resultados for n in lista} - EXCLUIR)
    cabecalho = [
        "# Prenomes mais frequentes no Censo Demográfico 2010 (IBGE, API de Nomes), por sexo, década de",
        "# nascimento e unidade da federação: os 20 primeiros de cada um dos "
        f"{len(recortes)} recortes. Fonte: IBGE.",
        "# Gerado por scripts/gerar_prenomes_ibge.py; minúsculas e sem acentos.",
    ]
    DESTINO.write_text("\n".join(cabecalho + nomes) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(nomes)} prenomes gravados em {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
