"""Funções de análise executadas pela API, na própria thread ou num processo de trabalho.

Com ``THEMIS_PROCESSOS`` maior que 1, a API distribui as análises entre processos (cada um com o
seu modelo de linguagem), contornando o limite de uma CPU por processo do Python. As funções deste
módulo recebem apenas valores simples, que atravessam a fronteira entre processos, e montam o
anonimizador no processo que executa a análise, com a configuração do órgão (``THEMIS_CONFIG``).
"""

from __future__ import annotations

from functools import cache

from ..configuracao import ConfiguracaoOrgao, carregar
from ..formatos import ResultadoArquivo
from ..formatos import anonimizar_arquivo as _anonimizar_arquivo
from ..motor import Anonimizador, Entidade, Resultado


@cache
def orgao() -> ConfiguracaoOrgao:
    """Configuração do órgão deste processo (lida uma vez de ``THEMIS_CONFIG``)."""
    return carregar()


def anonimizador(sobrepor: dict) -> Anonimizador:
    """Anonimizador com a configuração do órgão e as opções da requisição."""
    return Anonimizador(**orgao().argumentos(**sobrepor))


def anonimizar_texto(sobrepor: dict, texto: str) -> Resultado:
    return anonimizador(sobrepor).anonimizar(texto)


def analisar_texto(sobrepor: dict, texto: str) -> list[Entidade]:
    return anonimizador(sobrepor).analisar(texto)


def anonimizar_arquivo(sobrepor: dict, dados: bytes, nome: str, opcoes: dict) -> ResultadoArquivo:
    return _anonimizar_arquivo(dados, nome, anonimizador(sobrepor), **opcoes)
