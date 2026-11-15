"""Anonimização de arquivos de texto simples."""

from __future__ import annotations

from ..motor import Anonimizador
from . import ResultadoArquivo, VazamentoDetectado
from .verificacao import valores_protegidos, valores_tarjados, verificar_ausencia


def decodificar(dados: bytes) -> tuple[str, str]:
    """Decodifica o conteúdo como UTF-8 (com ou sem BOM) ou, na falha, como Windows-1252.

    Returns:
        ``(texto, codificação usada)``.
    """
    for codificacao in ("utf-8-sig", "utf-8"):
        try:
            return dados.decode(codificacao), codificacao
        except UnicodeDecodeError:
            continue
    return dados.decode("cp1252", errors="replace"), "cp1252"


def anonimizar_txt(dados: bytes, anon: Anonimizador, nome: str, *, verificar: bool = True) -> ResultadoArquivo:
    """Anonimiza um arquivo de texto; a saída é sempre gravada em UTF-8.

    Raises:
        VazamentoDetectado: A verificação encontrou valor tarjado no texto gerado.
    """
    texto, codificacao = decodificar(dados)
    r = anon.anonimizar(texto)
    if verificar and verificar_ausencia(r.texto, valores_tarjados([r]), valores_protegidos([r], anon.permitir)):
        raise VazamentoDetectado("Trecho tarjado ainda presente no texto gerado.")
    avisos = list(r.avisos)
    if codificacao == "cp1252":
        avisos.append("Arquivo não estava em UTF-8; foi lido como Windows-1252 e salvo em UTF-8.")
    return ResultadoArquivo(r.texto.encode("utf-8"), "txt", nome, [r], avisos)
