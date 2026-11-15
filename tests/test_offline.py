"""Garantia de funcionamento 100% offline: nenhuma conexão de rede durante carga e anonimização."""

import socket

import pytest


@pytest.fixture
def sem_rede(monkeypatch):
    tentativas = []

    def bloqueado(*args, **kwargs):
        tentativas.append(args)
        raise OSError("rede bloqueada pelo teste")

    monkeypatch.setattr(socket.socket, "connect", bloqueado)
    monkeypatch.setattr(socket.socket, "connect_ex", bloqueado)
    monkeypatch.setattr(socket, "create_connection", bloqueado)
    monkeypatch.setattr(socket, "getaddrinfo", bloqueado)
    return tentativas


def test_carga_e_anonimizacao_sem_rede(sem_rede):
    from themis_lgpd import Anonimizador
    from themis_lgpd.analisador import obter_analisador

    obter_analisador.cache_clear()  # recria o AnalyzerEngine (Presidio + spaCy) com a rede bloqueada
    r = Anonimizador().anonimizar(
        "Maria Souza, maria.souza@gmail.com, perfil https://instagram.com/maria.souza e site https://www.df.gov.br"
    )
    assert "maria.souza" not in r.texto and "Maria" not in r.texto
    assert sem_rede == []  # nenhuma tentativa de conexão (ex.: tldextract, download de modelo)
