"""Themis LGPD: anonimização de documentos brasileiros para publicação (LGPD e LAI), com execução local.

Uso básico::

    from themis_lgpd import Anonimizador

    resultado = Anonimizador(perfil="lai").anonimizar("Requerente: Maria Souza, CPF 529.982.247-25.")
    resultado.texto  # 'Requerente: [NOME], CPF [CPF].'

Arquivos (PDF, Office, ODF, HTML, e-mail, imagens e ZIP) são tratados por :mod:`themis_lgpd.formatos`.
"""

from ._versao import __version__
from .motor import Anonimizador, Entidade, Resultado, anonimizar
from .operadores import MODOS
from .perfis import PERFIS, Perfil, obter_perfil

__all__ = ["Anonimizador", "Entidade", "Resultado", "anonimizar", "MODOS", "PERFIS", "Perfil", "obter_perfil",
           "__version__"]
