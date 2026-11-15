"""Themis LGPD: anonimização de documentos brasileiros para publicação (LGPD e LAI), com execução local.

Uso básico::

    from themis_lgpd import Anonimizador

    resultado = Anonimizador(perfil="lai").anonimizar("Requerente: Maria Souza, CPF 529.982.247-25.")
    resultado.texto  # 'Requerente: [NOME], CPF [CPF].'

Arquivos (PDF, DOCX, XLSX, CSV, TXT e imagens) são tratados por :mod:`themis_lgpd.formatos`.
"""

from .motor import Anonimizador, Entidade, Resultado, anonimizar
from .operadores import MODOS
from .perfis import PERFIS, Perfil, obter_perfil

__version__ = "1.0.0"

__all__ = ["Anonimizador", "Entidade", "Resultado", "anonimizar", "MODOS", "PERFIS", "Perfil", "obter_perfil",
           "__version__"]
