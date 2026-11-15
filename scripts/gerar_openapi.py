"""Gera (ou verifica) ``docs/openapi.json``, a especificação versionada da API HTTP.

A especificação é gerada com a configuração padrão, sem nenhuma variável ``THEMIS_*`` do ambiente,
para que o arquivo não dependa da máquina em que foi gerado. Integrações podem usá-la para gerar
clientes; o teste ``tests/test_api_tarefas.py`` falha se a API mudar sem que o arquivo seja
atualizado.

Uso::

    python scripts/gerar_openapi.py              # grava docs/openapi.json
    python scripts/gerar_openapi.py --verificar  # código 1 se o arquivo estiver desatualizado
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DESTINO = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"


def gerar() -> str:
    """Especificação OpenAPI da API, em JSON formatado e com chaves ordenadas."""
    for chave in [k for k in os.environ if k.startswith("THEMIS_")]:
        del os.environ[chave]
    os.environ["THEMIS_USAR_NER"] = "0"  # a especificação não depende do modelo de linguagem
    from themis_lgpd.api.app import app

    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    texto = gerar()
    if "--verificar" in sys.argv:
        atual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if atual != texto:
            print(f"{DESTINO} está desatualizado: execute python scripts/gerar_openapi.py", file=sys.stderr)
            return 1
        return 0
    DESTINO.write_text(texto, encoding="utf-8", newline="\n")
    print(f"especificação gravada em {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
