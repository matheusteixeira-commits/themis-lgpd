"""Perfis de anonimização: o que tarjar, o que sinalizar para revisão e o que manter.

Um perfil associa a cada categoria de dado (ver :data:`themis_lgpd.catalogo.CATEGORIAS`) uma regra:

``tarjar``
    O dado é substituído.
``alertar``
    O dado permanece no texto e é listado para revisão humana.
``manter``
    O dado é ignorado.
``vinculado``
    Frases que descrevem a situação de alguém (camada contextual, ex.: "diagnosticado com…") são
    tarjadas; termos isolados (camada semântica, ex.: "asma") só são tarjados quando a frase se
    refere a uma pessoa determinada — caso contrário, são sinalizados. Essa regra evita tarjar
    conteúdo de interesse público, como "a política de saúde mental prevê atendimento para depressão".
"""

from __future__ import annotations

from dataclasses import dataclass, field

TARJAR, ALERTAR, MANTER, VINCULADO = "tarjar", "alertar", "manter", "vinculado"

#: Categorias que identificam a pessoa diretamente. Nelas, um achado de confiança moderada é tarjado
#: por precaução em vez de apenas sinalizado (ver :meth:`themis_lgpd.motor.Anonimizador._decidir`).
CATEGORIAS_IDENTIFICADORAS = frozenset({
    "PESSOA", "DOCUMENTO", "DADO_PESSOAL", "CONTATO", "LOCALIZACAO", "FINANCEIRO", "VEICULO", "PROCESSO",
    "MANUAL",
})

#: Categorias de nomes próprios que não designam pessoas (lugares e organizações). Quando uma entidade
#: dessas categorias não é tarjada, as ocorrências de valores tarjados contidas nela são preservadas:
#: "Paulo" tarjado como pessoa não transforma "São Paulo" em "São [NOME]".
NOMES_NAO_PESSOAIS = frozenset({"LOCALIDADE", "EMPRESA"})

_IDENTIFICADORES = dict.fromkeys(CATEGORIAS_IDENTIFICADORAS, TARJAR)


@dataclass(frozen=True)
class Perfil:
    """Política de anonimização.

    Attributes:
        nome: Identificador usado na CLI, na API e na interface.
        titulo: Nome legível.
        descricao: Finalidade do perfil.
        regras: Regra por categoria (``tarjar``, ``alertar``, ``manter`` ou ``vinculado``). Categorias
            ausentes recebem ``alertar``.
        score_minimo: Confiança mínima para aplicar a regra da categoria. Abaixo dela, o achado é
            sinalizado — exceto em categorias identificadoras, em que é tarjado por precaução.
        score_alerta: Confiança mínima para que o achado seja considerado.
        tarjar_sensivel_sempre: Tipos sensíveis tarjados mesmo sem vínculo com pessoa.
    """

    nome: str
    titulo: str
    descricao: str
    regras: dict[str, str] = field(default_factory=dict)
    score_minimo: float = 0.6
    score_alerta: float = 0.4
    tarjar_sensivel_sempre: frozenset[str] = frozenset()

    def regra(self, categoria: str) -> str:
        """Regra aplicável à categoria; ``alertar`` quando não definida."""
        return self.regras.get(categoria, ALERTAR)


PERFIS: dict[str, Perfil] = {
    p.nome: p
    for p in [
        Perfil(
            "lai", "Transparência (LAI)",
            "Padrão para publicar respostas e documentos públicos: tarja identificadores e dados sensíveis "
            "ligados a pessoas; mantém CNPJ, cidades e termos genéricos, que viram alerta para revisão.",
            {**_IDENTIFICADORES, "SENSIVEL": VINCULADO, "INTIMIDADE": VINCULADO, "MENOR": VINCULADO,
             "EMPRESA": MANTER, "LOCALIDADE": ALERTAR, "URL": MANTER, "QUASE_IDENTIFICADOR": ALERTAR},
        ),
        Perfil(
            "identificadores", "Somente identificadores",
            "Tarja apenas o que identifica diretamente a pessoa (nomes, documentos, contatos, endereços, "
            "processos). Dados sensíveis viram alerta. Útil para bases de dados e pesquisa.",
            {**_IDENTIFICADORES, "SENSIVEL": ALERTAR, "INTIMIDADE": ALERTAR, "MENOR": ALERTAR,
             "EMPRESA": MANTER, "LOCALIDADE": MANTER, "URL": MANTER, "QUASE_IDENTIFICADOR": ALERTAR},
        ),
        Perfil(
            "saude", "Saúde",
            "Como o perfil LAI, mas tarja qualquer menção a doenças, tratamentos e condições de saúde.",
            {**_IDENTIFICADORES, "SENSIVEL": VINCULADO, "INTIMIDADE": VINCULADO, "MENOR": VINCULADO,
             "EMPRESA": MANTER, "LOCALIDADE": ALERTAR, "URL": MANTER, "QUASE_IDENTIFICADOR": ALERTAR},
            tarjar_sensivel_sempre=frozenset({"SAUDE", "GENETICO_BIOMETRICO"}),
        ),
        Perfil(
            "maxima", "Proteção máxima",
            "Tarja tudo o que for detectado, inclusive termos sensíveis isolados, cidades, CNPJ, URLs e "
            "quase-identificadores. Maior proteção, menor legibilidade.",
            {**_IDENTIFICADORES, "SENSIVEL": TARJAR, "INTIMIDADE": TARJAR, "MENOR": TARJAR, "EMPRESA": TARJAR,
             "LOCALIDADE": TARJAR, "URL": TARJAR, "QUASE_IDENTIFICADOR": TARJAR},
            score_minimo=0.4, score_alerta=0.3,
        ),
    ]
}

PERFIL_PADRAO = "lai"


def obter_perfil(nome: str | Perfil | None) -> Perfil:
    """Resolve um perfil pelo nome (sem distinção de caixa) ou devolve a instância recebida.

    Raises:
        ValueError: Nome de perfil inexistente.
    """
    if isinstance(nome, Perfil):
        return nome
    chave = (nome or PERFIL_PADRAO).lower()
    if chave not in PERFIS:
        raise ValueError(f"Perfil desconhecido: {nome!r}. Opções: {', '.join(PERFIS)}")
    return PERFIS[chave]
