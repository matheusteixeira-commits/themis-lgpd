"""Gera a lista de municípios brasileiros usada pelo reconhecimento de localidades.

A lista é obtida da API pública de localidades do IBGE (dados abertos, reutilização permitida com
citação da fonte) e gravada em ``src/themis_lgpd/dados/municipios.txt``, um município por linha, no
formato ``Nome|UF``, em ordem alfabética. O arquivo é versionado no repositório: o Themis não acessa a
rede em execução, e o script só precisa ser rodado de novo quando o IBGE criar ou renomear municípios.

Fonte: IBGE, API de Localidades — https://servicodados.ibge.gov.br/api/docs/localidades

Uso::

    python scripts/gerar_municipios.py
"""

from __future__ import annotations

import gzip
import json
import urllib.request
from pathlib import Path

#: Endereço da lista completa de municípios na API de localidades do IBGE.
URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
DESTINO = Path(__file__).resolve().parents[1] / "src" / "themis_lgpd" / "dados" / "municipios.txt"


def _uf(municipio: dict) -> str:
    """Sigla da UF; alguns municípios novos vêm sem microrregião na resposta da API."""
    if municipio.get("microrregiao"):
        return municipio["microrregiao"]["mesorregiao"]["UF"]["sigla"]
    return municipio["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]


def main() -> None:
    with urllib.request.urlopen(URL, timeout=60) as resposta:  # noqa: S310 - endereço fixo do IBGE  # nosec B310
        corpo = resposta.read()
    if corpo[:2] == b"\x1f\x8b":  # a API responde comprimida em gzip mesmo sem o cabeçalho Accept-Encoding
        corpo = gzip.decompress(corpo)
    municipios = json.loads(corpo)
    linhas = sorted({f"{m['nome']}|{_uf(m)}" for m in municipios})
    cabecalho = ("# Municípios brasileiros (nome|UF). Fonte: IBGE, API de Localidades "
                 "(servicodados.ibge.gov.br). Gerado por scripts/gerar_municipios.py.\n")
    DESTINO.write_text(cabecalho + "\n".join(linhas) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(linhas)} municípios gravados em {DESTINO}")


if __name__ == "__main__":
    main()
