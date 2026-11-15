"""Estruturas comuns aos reconhecedores do Themis.

Os reconhecedores brasileiros são escritos como coleções de :class:`Padrao` — uma expressão regular
com validação opcional de dígito verificador e exigência opcional de palavras de contexto — e
executados dentro de um ``EntityRecognizer`` do Presidio (ver :mod:`themis_lgpd.analisador`).

Cada achado é uma :class:`Deteccao` com posição no texto *normalizado*, tipo de dado, confiança,
origem e camada. A camada informa a natureza do achado e é usada pelos perfis para decidir entre
tarjar, sinalizar ou manter:

``estrutural``
    Formato próprio do dado (CPF, CEP, placa), em geral com dígito verificador.
``contextual``
    Depende de uma expressão que descreve a situação da pessoa ("diagnosticado com…").
``semantica``
    Termo isolado de uma categoria sensível ("asma", "católico").
``ner``
    Entidade nomeada reconhecida pelo modelo de linguagem.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import regex as re

ESTRUTURAL = "estrutural"
CONTEXTUAL = "contextual"
SEMANTICA = "semantica"
NER = "ner"

#: Fronteira à esquerda de um número: não pode estar colado a letra ou dígito, nem continuar uma
#: sequência pontuada ("1.234" não começa no "234"). Evita reconhecer parte de um número maior.
ANTES_NUM = r"(?<![\w])(?<!\d[.\-/])"
#: Fronteira à direita de um número, com o mesmo critério de :data:`ANTES_NUM`.
DEPOIS_NUM = r"(?![\w])(?![.\-/]\d)"


@dataclass
class Deteccao:
    """Trecho identificado por um reconhecedor, em coordenadas do texto normalizado.

    Attributes:
        inicio: Posição inicial (inclusiva).
        fim: Posição final (exclusiva).
        tipo: Código do tipo de dado (ver :data:`themis_lgpd.catalogo.TIPOS`).
        score: Confiança, entre 0 e 1.
        origem: Identificador do reconhecedor que produziu o achado.
        camada: ``estrutural``, ``contextual``, ``semantica`` ou ``ner``.
        validado: ``True``/``False`` se o dígito verificador foi conferido; ``None`` se não se aplica.
        contexto_aplicado: Indica que o reconhecedor já considerou as palavras de contexto ao
            calcular a confiança; o reforço por contexto do Presidio não é aplicado de novo.
    """

    inicio: int
    fim: int
    tipo: str
    score: float
    origem: str
    camada: str = ESTRUTURAL
    validado: bool | None = None
    contexto_aplicado: bool = False


@dataclass
class Padrao:
    """Regra baseada em expressão regular, executada dentro de um reconhecedor do Presidio.

    Attributes:
        tipo: Tipo de dado atribuído aos achados.
        regex: Expressão regular (biblioteca ``regex``, compatível com ``re``).
        score: Confiança atribuída a um achado sem validação.
        camada: Camada atribuída aos achados.
        grupo: Grupo da expressão que delimita o dado; o restante do casamento (ex.: o rótulo
            "CPF:") permanece visível no texto anonimizado.
        validador: Função que confere o dígito verificador. Valor válido recebe confiança mínima de
            0,95; valor inválido é descartado, a menos que haja contexto e ``score_invalido`` esteja
            definido — política de *falhar fechado*: um número com formato de CPF ao lado da palavra
            "CPF" é tarjado mesmo com erro de digitação.
        contexto: Expressões que, a até ``janela`` caracteres antes do achado (ou 15 depois),
            **exigem** a regra (``contexto_obrigatorio``) ou sustentam um número com dígito
            inválido. O simples reforço de confiança por palavras vizinhas fica a cargo do
            ``LemmaContextAwareEnhancer`` do Presidio.
        contexto_obrigatorio: Descarta achados sem contexto.
        score_invalido: Confiança de um número com dígito inválido, mas com contexto.
        janela: Distância máxima, em caracteres, entre o contexto e o início do achado.
        ignorar_caixa: Compila a expressão sem distinção de maiúsculas e minúsculas.
        nome: Identificador usado como origem dos achados; padrão ``regex:<tipo>``.

    Example:
        >>> from themis_lgpd.validadores import cpf_valido
        >>> p = Padrao("CPF", r"\\b\\d{3}\\.\\d{3}\\.\\d{3}-\\d{2}\\b", 0.5, validador=cpf_valido,
        ...            contexto=("cpf",), score_invalido=0.7)
        >>> [d.validado for d in p.detectar("CPF 529.982.247-25")]
        [True]
    """

    tipo: str
    regex: str
    score: float
    camada: str = ESTRUTURAL
    grupo: int | str = 0
    validador: Callable[[str], bool] | None = None
    contexto: tuple[str, ...] = ()
    contexto_obrigatorio: bool = False
    score_invalido: float | None = None
    janela: int = 40
    ignorar_caixa: bool = True
    nome: str = ""

    def __post_init__(self) -> None:
        flags = re.MULTILINE
        if self.ignorar_caixa:
            flags |= re.IGNORECASE
        self._re = re.compile(self.regex, flags)
        self._ctx = (
            re.compile(r"(?<![\w])(?:" + "|".join(self.contexto) + r")(?![\w])", re.IGNORECASE)
            if self.contexto else None
        )
        if not self.nome:
            self.nome = f"regex:{self.tipo}"

    def tem_contexto(self, texto: str, inicio: int, fim: int | None = None) -> bool:
        """Indica se há expressão de contexto antes do achado ou logo depois dele.

        Args:
            texto: Texto analisado.
            inicio: Início do casamento completo da expressão.
            fim: Fim do casamento; quando informado, os 15 caracteres seguintes também são
                examinados, pois o contexto pode vir depois do dado ("12345-6 (conta corrente)").
        """
        if self._ctx is None:
            return False
        if self._ctx.search(texto, max(0, inicio - self.janela), inicio):
            return True
        return bool(fim is not None and self._ctx.search(texto, fim, min(len(texto), fim + 15)))

    def detectar(self, texto: str) -> list[Deteccao]:
        """Aplica a regra ao texto.

        Returns:
            Um achado por casamento aceito, delimitado pelo grupo ``grupo``.
        """
        achados: list[Deteccao] = []
        for m in self._re.finditer(texto):
            ini, fim = m.span(self.grupo)
            if ini < 0 or fim <= ini:
                continue
            valor = texto[ini:fim]
            ctx = self.tem_contexto(texto, m.start(), m.end())
            if self.contexto_obrigatorio and not ctx:
                continue
            score, validado, usou_ctx = self.score, None, self.contexto_obrigatorio
            if self.validador is not None:
                if self.validador(valor):
                    score, validado = max(score, 0.95), True
                elif ctx and self.score_invalido is not None:
                    score, validado, usou_ctx = self.score_invalido, False, True
                else:
                    continue
            achados.append(Deteccao(ini, fim, self.tipo, round(score, 3), self.nome, self.camada, validado, usou_ctx))
        return achados


class ReconhecedorPadroes:
    """Conjunto nomeado de :class:`Padrao`, executados em sequência sobre o mesmo texto.

    Attributes:
        nome: Identificador do conjunto.
        padroes: Regras do conjunto.
    """

    def __init__(self, nome: str, padroes: Iterable[Padrao]):
        self.nome = nome
        self.padroes = list(padroes)

    def detectar(self, texto: str) -> list[Deteccao]:
        """Achados de todas as regras do conjunto, sem resolução de sobreposições."""
        saida: list[Deteccao] = []
        for p in self.padroes:
            saida.extend(p.detectar(texto))
        return saida


def alternativas(*termos: str) -> str:
    """Grupo não capturante com os termos alternativos: ``(?:a|b|c)``."""
    return "(?:" + "|".join(termos) + ")"
