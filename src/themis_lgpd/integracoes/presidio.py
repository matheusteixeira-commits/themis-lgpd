"""Reconhecedores brasileiros do Themis para o seu próprio ``AnalyzerEngine`` do Presidio.

O Themis é construído sobre o Presidio; os reconhecedores brasileiros (CPF, CNPJ alfanumérico, PIS,
título, CNS, CNH, RENAVAM, processos CNJ/SEI, endereços do DF, dados sensíveis…) são
``EntityRecognizer`` do Presidio e podem ser registrados em qualquer instalação dele::

    from presidio_analyzer import AnalyzerEngine
    from themis_lgpd.integracoes.presidio import reconhecedores_brasileiros

    engine = AnalyzerEngine(supported_languages=["pt"], nlp_engine=...)   # seu motor em português
    for r in reconhecedores_brasileiros():
        engine.registry.add_recognizer(r)
    engine.analyze("CPF 529.982.247-25", language="pt")

Os tipos de entidade são os do Themis (``CPF``, ``NOME``, ``CEP``…; veja ``themis_lgpd.catalogo``).
O reconhecedor de nomes por modelo (``BR_Nomes_Modelo``) usa as entidades do ``SpacyNlpEngine``.
"""

from ..analisador import (
    MotorSpacyThemis,
    ReconhecedorNomesModelo,
    ReconhecedorThemis,
    obter_analisador,
    reconhecedores_brasileiros,
)

__all__ = ["MotorSpacyThemis", "ReconhecedorNomesModelo", "ReconhecedorThemis", "obter_analisador",
           "reconhecedores_brasileiros"]
