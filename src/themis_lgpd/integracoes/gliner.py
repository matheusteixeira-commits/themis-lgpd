"""Modelo neural GLiNER (opcional, experimental) via ``GLiNERRecognizer`` do Presidio.

Aumenta a cobertura de nomes incomuns e de descritores de dados sensíveis em textos livres, ao custo
de exigir PyTorch (~2 GB) e mais CPU. Uso::

    from themis_lgpd import Anonimizador
    from themis_lgpd.integracoes.gliner import reconhecedor_gliner

    anon = Anonimizador(reconhecedores_extras=[reconhecedor_gliner()])

Requer: ``pip install 'themis-lgpd[ml]'``. O modelo é baixado do Hugging Face na primeira execução e
depois roda localmente. Descritores sensíveis vindos do modelo seguem a regra de vínculo do perfil.
"""

from __future__ import annotations

from presidio_analyzer.predefined_recognizers import GLiNERRecognizer

MODELO_PADRAO = "arthrod/gliner-mmbert-small-ptbr-pii-full-3x-v1"
ROTULOS = {
    "nome de pessoa": "NOME",
    "endereço": "ENDERECO",
    "data de nascimento": "DATA_NASCIMENTO",
    "condição de saúde": "SAUDE",
    "religião": "RELIGIAO",
    "opinião política": "OPINIAO_POLITICA",
    "orientação sexual": "VIDA_SEXUAL",
    "origem étnica ou racial": "ORIGEM_RACIAL",
}


def reconhecedor_gliner(modelo: str = MODELO_PADRAO, limiar: float = 0.5,
                        rotulos: dict[str, str] | None = None) -> GLiNERRecognizer:
    mapa = rotulos or ROTULOS
    return GLiNERRecognizer(supported_entities=sorted(set(mapa.values())), name="BR_GLiNER",
                            supported_language="pt", entity_mapping=mapa, model_name=modelo, threshold=limiar)
