"""Configuração da API e da interface web por variáveis de ambiente (prefixo ``THEMIS_``).

Os valores padrão são os seguros. Com ``THEMIS_DEMO=1``, os limites são reduzidos para uma
instalação pública de demonstração e a documentação interativa da API é desligada.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(nome: str, padrao: bool) -> bool:
    v = os.environ.get(nome)
    return padrao if v is None else v.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _int(nome: str, padrao: int) -> int:
    """Lê um inteiro; valores inválidos são ignorados em favor do padrão seguro."""
    try:
        return int(os.environ.get(nome, padrao))
    except ValueError:
        return padrao


def _lista(nome: str) -> list[str]:
    return [x.strip() for x in os.environ.get(nome, "").split(",") if x.strip()]


@dataclass(frozen=True)
class Config:
    """Configuração efetiva.

    Attributes:
        demo: Modo de demonstração pública (``THEMIS_DEMO``).
        max_caracteres: Tamanho máximo de texto por requisição (``THEMIS_MAX_CARACTERES``).
        max_mb: Tamanho máximo de arquivo, em MB (``THEMIS_MAX_MB``).
        max_paginas: Número máximo de páginas de PDF (``THEMIS_MAX_PAGINAS``).
        limite_req_minuto: Requisições por minuto por cliente (``THEMIS_LIMITE_REQ_MINUTO``).
        concorrencia: Análises simultâneas (``THEMIS_CONCORRENCIA``).
        timeout_s: Tempo máximo de processamento por requisição, em segundos (``THEMIS_TIMEOUT_S``).
        chaves_api: Chaves aceitas no cabeçalho ``X-API-Key``; vazio desativa a autenticação
            (``THEMIS_CHAVES_API``, separadas por vírgula).
        cors_origens: Origens autorizadas a chamar a API pelo navegador (``THEMIS_CORS_ORIGENS``).
        docs: Publica a documentação interativa em ``/docs`` (``THEMIS_DOCS``).
        confiar_proxy: Usa o cabeçalho ``X-Forwarded-For`` para identificar o cliente; só deve ser
            ativado atrás de um proxy reverso confiável (``THEMIS_CONFIAR_PROXY``).
        usar_ner: Usa o modelo de linguagem no reconhecimento de nomes (``THEMIS_USAR_NER``).
        modelo_spacy: Pacote do modelo spaCy (``THEMIS_MODELO_SPACY``).
    """

    demo: bool
    max_caracteres: int
    max_mb: int
    max_paginas: int
    limite_req_minuto: int
    concorrencia: int
    timeout_s: int
    chaves_api: tuple[str, ...]
    cors_origens: tuple[str, ...]
    docs: bool
    confiar_proxy: bool
    usar_ner: bool
    modelo_spacy: str


def carregar() -> Config:
    """Lê a configuração do ambiente."""
    demo = _bool("THEMIS_DEMO", False)
    return Config(
        demo=demo,
        max_caracteres=_int("THEMIS_MAX_CARACTERES", 20_000 if demo else 500_000),
        max_mb=_int("THEMIS_MAX_MB", 5 if demo else 50),
        max_paginas=_int("THEMIS_MAX_PAGINAS", 10 if demo else 500),
        limite_req_minuto=_int("THEMIS_LIMITE_REQ_MINUTO", 10 if demo else 120),
        concorrencia=_int("THEMIS_CONCORRENCIA", 2),
        timeout_s=_int("THEMIS_TIMEOUT_S", 60 if demo else 300),
        chaves_api=tuple(_lista("THEMIS_CHAVES_API")),
        cors_origens=tuple(_lista("THEMIS_CORS_ORIGENS")),
        docs=_bool("THEMIS_DOCS", not demo),
        confiar_proxy=_bool("THEMIS_CONFIAR_PROXY", False),
        usar_ner=_bool("THEMIS_USAR_NER", True),
        modelo_spacy=os.environ.get("THEMIS_MODELO_SPACY", "pt_core_news_lg"),
    )
