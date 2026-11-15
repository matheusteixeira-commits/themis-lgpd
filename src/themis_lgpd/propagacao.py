"""Propagação de valores tarjados para todas as ocorrências do mesmo documento.

Um reconhecedor pode identificar um dado apenas onde há contexto suficiente — por exemplo, o nome
logo após "Requerente:" ou o CPF após a palavra "CPF". Se o mesmo valor reaparece em outro ponto
do documento sem esse contexto (assinatura, rodapé, outra célula da planilha), ele precisa ser
tarjado também; caso contrário, a tarja de uma ocorrência seria anulada pela exposição da outra.

A busca é feita sobre uma representação *compacta* do texto — apenas letras e dígitos, em
minúsculas e sem acentos —, o que torna a comparação indiferente a diferenças de formatação
(``529.982.247-25`` × ``52998224725``; ``Maria  Souza`` × ``MARIA SOUZA``). Cada ocorrência
encontrada só é aceita se começar e terminar em fronteira de palavra no texto original.
"""

from __future__ import annotations

from array import array
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .catalogo import tipo as info_tipo
from .reconhecedores.nomes import (
    CONECTORES,
    NAO_INICIAM_NOME,
    PALAVRAS_COMUNS,
    ambiguos,
    contexto_nao_pessoal,
)
from .texto import dobrar

#: Categorias cujos valores identificam a pessoa por si sós e, portanto, são propagados.
CATEGORIAS_PROPAGAVEIS = frozenset({
    "PESSOA", "DOCUMENTO", "DADO_PESSOAL", "CONTATO", "LOCALIZACAO", "FINANCEIRO", "VEICULO", "PROCESSO",
    "MANUAL",
})

#: Tamanho mínimo (em letras e dígitos) para propagar um valor completo. Valores mais curtos geram
#: coincidências demais para serem propagados com segurança.
MINIMO_VALOR = 4

#: Tamanho mínimo de uma parte isolada de nome (ex.: o sobrenome "Souza" de "Maria Souza").
MINIMO_PARTE_NOME = 4

#: Separador entre textos na representação compacta; nunca é letra nem dígito.
_SEPARADOR = "|"


@dataclass(frozen=True)
class Ocorrencia:
    """Nova ocorrência de um valor já tarjado, em coordenadas do texto original."""

    indice_texto: int
    inicio: int
    fim: int
    tipo: str
    parcial: bool


class _IndiceCompacto:
    """Representação compacta (só letras e dígitos, dobrados) de um conjunto de textos.

    Mantém, para cada caractere compacto, o texto de origem e a posição no original, permitindo
    traduzir de volta qualquer ocorrência encontrada.
    """

    def __init__(self, textos: Sequence[str]):
        self.textos = textos
        partes: list[str] = []
        self.origem_texto = array("i")
        self.origem_pos = array("i")
        for i, texto in enumerate(textos):
            dobrado = dobrar(texto)
            for pos, ch in enumerate(dobrado):
                if ch.isalnum():
                    partes.append(ch)
                    self.origem_texto.append(i)
                    self.origem_pos.append(pos)
            partes.append(_SEPARADOR)
            self.origem_texto.append(-1)
            self.origem_pos.append(-1)
        self.compacto = "".join(partes)

    def buscar(self, alvo: str) -> Iterable[tuple[int, int, int]]:
        """Gera ``(índice do texto, início, fim)`` de cada ocorrência de ``alvo`` (já compacto)."""
        inicio = self.compacto.find(alvo)
        while inicio >= 0:
            fim = inicio + len(alvo) - 1
            i_txt = self.origem_texto[inicio]
            # Ocorrência que atravessa a fronteira entre dois textos não é válida.
            if i_txt >= 0 and self.origem_texto[fim] == i_txt:
                ini_orig = self.origem_pos[inicio]
                fim_orig = self.origem_pos[fim] + 1
                texto = self.textos[i_txt]
                antes_ok = ini_orig == 0 or not texto[ini_orig - 1].isalnum()
                depois_ok = fim_orig >= len(texto) or not texto[fim_orig].isalnum()
                if antes_ok and depois_ok:
                    yield i_txt, ini_orig, fim_orig
            inicio = self.compacto.find(alvo, inicio + 1)


def _compactar(valor: str) -> str:
    return "".join(ch for ch in dobrar(valor) if ch.isalnum())


def _partes_de_nome(valor: str) -> list[str]:
    """Partes de um nome que podem ser propagadas isoladamente (sobrenomes e prenomes distintivos).

    Exclui conectores ("da", "de"), palavras comuns, termos institucionais e prenomes que também são
    palavras do vocabulário ("Rosa", "Clara"), que gerariam tarjas indevidas.
    """
    comuns = ambiguos()
    partes = []
    for palavra in valor.split():
        limpa = palavra.strip(".,;:()[]\"'")
        dobrada = dobrar(limpa)
        if (len(limpa) >= MINIMO_PARTE_NOME and limpa[:1].isupper() and dobrada not in CONECTORES
                and dobrada not in NAO_INICIAM_NOME and dobrada not in PALAVRAS_COMUNS and dobrada not in comuns):
            partes.append(limpa)
    return partes


def localizar(textos: Sequence[str], tarjadas: Iterable[tuple[str, str]]) -> list[Ocorrencia]:
    """Localiza todas as ocorrências dos valores tarjados nos textos.

    Args:
        textos: Textos originais do mesmo documento (páginas, parágrafos, células…).
        tarjadas: Pares ``(tipo, valor)`` de entidades já tarjadas em qualquer um dos textos.

    Returns:
        Ocorrências encontradas, inclusive as já cobertas por entidades existentes; cabe ao chamador
        descartar as sobrepostas. Partes isoladas de nomes só são aceitas quando, no texto, começam
        com letra maiúscula (o que distingue o sobrenome "Rocha" da palavra "rocha"). Nomes de pessoa
        não são propagados para dentro de nomes de lugares e instituições: "Paulo" tarjado não torna
        "São Paulo" em "São [NOME]" (ver :func:`~themis_lgpd.reconhecedores.nomes.contexto_nao_pessoal`).
    """
    completos: dict[str, str] = {}
    parciais: dict[str, str] = {}
    for tipo, valor in tarjadas:
        if info_tipo(tipo).categoria not in CATEGORIAS_PROPAGAVEIS:
            continue
        compacto = _compactar(valor)
        if len(compacto) >= MINIMO_VALOR:
            completos.setdefault(compacto, tipo)
        if tipo == "NOME":
            for parte in _partes_de_nome(valor):
                parciais.setdefault(_compactar(parte), tipo)
    if not completos and not parciais:
        return []
    indice = _IndiceCompacto(textos)
    achados: list[Ocorrencia] = []
    for alvo, tipo in completos.items():
        for i, a, b in indice.buscar(alvo):
            if tipo != "NOME" or not contexto_nao_pessoal(textos[i], a):
                achados.append(Ocorrencia(i, a, b, tipo, False))
    for alvo, tipo in parciais.items():
        if alvo in completos:
            continue
        for i, a, b in indice.buscar(alvo):
            if textos[i][a].isupper() and not contexto_nao_pessoal(textos[i], a):
                achados.append(Ocorrencia(i, a, b, tipo, True))
    return achados
