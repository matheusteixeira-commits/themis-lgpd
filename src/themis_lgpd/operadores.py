"""Modos de saída: como cada trecho tarjado é substituído no texto.

A substituição em si é executada pelo ``AnonymizerEngine`` do Presidio (``presidio-anonymizer``);
este módulo define o texto de cada substituto e os operadores correspondentes.

Em termos da LGPD e do guia da ANPD, os modos ``etiqueta``, ``tarja`` e ``mascara`` produzem
documentos anonimizados (o dado não é recuperável a partir da saída), enquanto ``pseudonimo`` e
``hmac`` produzem pseudonimização: permitem relacionar ocorrências do mesmo titular e, no caso do
HMAC, conferir um valor conhecido por quem detém a chave.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from collections import defaultdict
from functools import lru_cache

from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig, RecognizerResult

from .catalogo import tipo as info_tipo
from .texto import dobrar

# Mesmo critério de themis_lgpd.analisador: nenhum registro de depuração sobre documentos processados.
logging.getLogger("presidio-anonymizer").setLevel(logging.WARNING)

#: Modos de saída disponíveis e a descrição exibida na interface e na CLI.
MODOS = {
    "etiqueta": "Etiqueta do tipo de dado — ex.: [CPF], [NOME]. Padrão.",
    "tarja": "Tarja opaca de tamanho fixo (████████), sem indicar o tipo.",
    "mascara": "Mantém pontuação e formato, troca letras e dígitos por * — ex.: ***.***.***-**.",
    "pseudonimo": "Pseudônimo consistente no documento/lote — ex.: Pessoa 1, [CPF 2]. "
                  "A mesma pessoa recebe sempre o mesmo pseudônimo (inclusive 'Maria' ↔ 'Maria Souza').",
    "hmac": "Código derivado do valor com chave secreta (HMAC-SHA256) — permite cruzar registros sem revelar o "
            "valor. É pseudonimização (ANPD), não anonimização.",
}

# Tamanho fixo: a tarja não revela o comprimento do dado substituído.
_TARJA = "████████"
_CONECTORES = {"da", "de", "do", "das", "dos", "e", "d'"}

#: Tipos cujo valor é comparado apenas por letras e dígitos: "529.982.247-25" e "52998224725" são o
#: mesmo CPF e recebem o mesmo pseudônimo ou código HMAC.
_TIPOS_CODIGO = frozenset({"CPF", "CNPJ", "PIS", "TITULO_ELEITOR", "CNS", "CNH", "RENAVAM", "TELEFONE", "CEP",
                           "CARTAO", "PROCESSO_JUDICIAL", "PROCESSO_ADMINISTRATIVO", "RG", "MATRICULA"})


def _chave_valor(tipo: str, valor: str) -> str:
    """Forma canônica do valor, usada para reconhecer ocorrências do mesmo dado."""
    if tipo in _TIPOS_CODIGO:
        return re.sub(r"[^0-9A-Za-z]", "", valor).upper()
    return " ".join(dobrar(valor).split())


def _tokens_nome(valor: str) -> frozenset[str]:
    """Palavras significativas de um nome, sem conectores e iniciais."""
    return frozenset(t for t in re.findall(r"\w+", dobrar(valor)) if t not in _CONECTORES and len(t) > 1)


class Substituidor:
    """Produz o texto que substitui cada trecho tarjado, conforme o modo de saída.

    No modo ``pseudonimo``, a numeração é atribuída na ordem em que os dados aparecem e é mantida
    enquanto a instância existir; :meth:`reiniciar` recomeça a numeração. Nomes são agrupados por
    inclusão de palavras: "Maria" e "Maria Souza" recebem o mesmo pseudônimo.

    Args:
        modo: Um dos :data:`MODOS`.
        chave_hmac: Chave do modo ``hmac``. Sem ela, uma chave aleatória é gerada para a instância e
            os códigos não podem ser reproduzidos depois.

    Raises:
        ValueError: Modo desconhecido.
    """

    def __init__(self, modo: str = "etiqueta", chave_hmac: bytes | str | None = None):
        if modo not in MODOS:
            raise ValueError(f"Modo desconhecido: {modo!r}. Opções: {', '.join(MODOS)}")
        self.modo = modo
        if isinstance(chave_hmac, str):
            chave_hmac = chave_hmac.encode("utf-8")
        self._chave = chave_hmac or secrets.token_bytes(32)
        self.reiniciar()

    def reiniciar(self) -> None:
        """Descarta a numeração de pseudônimos acumulada."""
        self._contadores: dict[str, int] = defaultdict(int)
        self._valores: dict[tuple[str, str], str] = {}
        self._pessoas: list[tuple[set[str], str]] = []

    def substituto(self, tipo: str, valor: str) -> str:
        """Texto que substitui ``valor``, do tipo ``tipo``."""
        info = info_tipo(tipo)
        if self.modo == "etiqueta":
            return info.etiqueta
        if self.modo == "tarja":
            return _TARJA
        if self.modo == "mascara":
            return re.sub(r"\w", "*", valor)
        if self.modo == "hmac":
            # O tipo entra no cálculo para que o mesmo número em tipos diferentes gere códigos diferentes.
            # Dez dígitos hexadecimais bastam para distinguir os valores de um documento sem tornar o
            # código longo; sem a chave, o código não permite recuperar nem testar valores.
            digest = hmac.new(self._chave, f"{tipo}:{_chave_valor(tipo, valor)}".encode(), hashlib.sha256).hexdigest()
            return f"[{info.etiqueta.strip('[]')}:{digest[:10]}]"
        if tipo == "NOME":
            return self._pessoa(valor)
        chave = (tipo, _chave_valor(tipo, valor))
        if chave not in self._valores:
            self._contadores[tipo] += 1
            self._valores[chave] = f"[{info.etiqueta.strip('[]')} {self._contadores[tipo]}]"
        return self._valores[chave]

    def operador_presidio(self, tipo: str, mapa: dict[tuple[str, str], str]) -> OperatorConfig:
        """Operador do ``presidio-anonymizer`` equivalente ao modo, para um tipo de dado.

        Args:
            tipo: Tipo de dado.
            mapa: Substituto de cada ``(tipo, trecho)``, calculado previamente na ordem do texto (ver
                :func:`aplicar_com_presidio`). Usado pelos modos que dependem do valor.
        """
        if self.modo in ("etiqueta", "tarja"):
            return OperatorConfig("replace", {"new_value": self.substituto(tipo, "")})
        return OperatorConfig("custom", {"lambda": lambda trecho, tipo=tipo: mapa[(tipo, trecho)]})

    def _pessoa(self, valor: str) -> str:
        """Pseudônimo de pessoa; nomes contidos um no outro compartilham o mesmo pseudônimo."""
        toks = set(_tokens_nome(valor))
        if toks:
            for grupo, rotulo in self._pessoas:
                if toks <= grupo or grupo <= toks:
                    grupo |= toks
                    return rotulo
        self._contadores["NOME"] += 1
        rotulo = f"Pessoa {self._contadores['NOME']}"
        self._pessoas.append((toks, rotulo))
        return rotulo


@lru_cache(maxsize=1)
def _motor_anonimizacao() -> AnonymizerEngine:
    return AnonymizerEngine()


def aplicar_com_presidio(original: str, segmentos: list, substituidor: Substituidor) -> tuple[str, list[dict]]:
    """Aplica as substituições ao texto original com o ``AnonymizerEngine`` do Presidio.

    Args:
        original: Texto original.
        segmentos: ``(início, fim, entidade)`` de cada trecho a substituir, sem sobreposição e em
            ordem de posição. As sobreposições são resolvidas antes, pelo motor, de forma que nenhum
            caractere do mesmo dado fique fora da substituição.
        substituidor: Define o texto de cada substituto.

    Returns:
        O texto anonimizado e o registro de cada substituição (posições no original e na saída,
        trecho original, substituto e tipo).

    Raises:
        RuntimeError: O ``AnonymizerEngine`` devolveu um número de substituições diferente do
            número de segmentos; o resultado não seria confiável.
    """
    if not segmentos:
        return original, []
    # Os substitutos dependentes do valor são calculados na ordem do texto, para que "Pessoa 1" seja
    # sempre a primeira pessoa mencionada.
    mapa: dict[tuple[str, str], str] = {}
    for a, b, dono in segmentos:
        trecho = original[a:b]
        if (dono.tipo, trecho) not in mapa:
            mapa[(dono.tipo, trecho)] = substituidor.substituto(
                dono.tipo, trecho if substituidor.modo == "mascara" else dono.valor)
    tipos = {dono.tipo for _, _, dono in segmentos}
    resultado = _motor_anonimizacao().anonymize(
        text=original,
        analyzer_results=[RecognizerResult(dono.tipo, a, b, 1.0) for a, b, dono in segmentos],
        operators={t: substituidor.operador_presidio(t, mapa) for t in tipos},
        merge_entities_with_spaces=False,  # a segmentação já foi definida pelo motor
    )
    itens = sorted(resultado.items, key=lambda it: it.start)
    if len(itens) != len(segmentos):
        raise RuntimeError("presidio-anonymizer devolveu número inesperado de substituições")
    subs = [{"inicio": a, "fim": b, "inicio_saida": it.start, "fim_saida": it.end, "original": original[a:b],
             "substituto": it.text, "tipo": dono.tipo} for (a, b, dono), it in zip(segmentos, itens)]
    return resultado.text, subs
