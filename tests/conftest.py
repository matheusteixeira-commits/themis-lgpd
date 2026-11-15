"""Instâncias do anonimizador compartilhadas pelos testes (o modelo de linguagem é carregado uma vez)."""

import pytest

from themis_lgpd import Anonimizador


@pytest.fixture(scope="session")
def anon() -> Anonimizador:
    return Anonimizador()


@pytest.fixture(scope="session")
def anon_maxima() -> Anonimizador:
    return Anonimizador("maxima")


@pytest.fixture(scope="session")
def anon_sem_ner() -> Anonimizador:
    return Anonimizador(usar_ner=False)
