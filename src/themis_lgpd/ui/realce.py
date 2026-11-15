"""Geração de HTML seguro para a interface.

Todo texto do usuário passa por ``html.escape`` antes de qualquer marcação ser inserida, e o
resultado é exibido com ``st.html`` (sem interpretação de Markdown) — nada vindo de um documento
pode virar tag, script, link ou imagem externa.
"""

from __future__ import annotations

import html

from ..motor import Entidade, Resultado

#: Cores de fundo e de destaque por ação: vermelho para tarjar, amarelo para revisar, azul para manter.
CORES = {
    "tarjar": ("#fde2e1", "#b42318"),
    "alertar": ("#fef3c7", "#92400e"),
    "manter": ("#e0f2fe", "#075985"),
}
_CAIXA = ("font-family:ui-monospace,Consolas,monospace;font-size:13.5px;line-height:1.65;white-space:pre-wrap;"
          "word-break:break-word;padding:14px 16px;border:1px solid #d0d5dd;border-radius:8px;background:#fcfcfd;"
          "max-height:440px;overflow-y:auto;color:#101828")


def _marca(trecho: str, cor: tuple[str, str], dica: str, rotulo: str = "") -> str:
    """Trecho destacado com dica ao passar o mouse; trecho, dica e rótulo são escapados."""
    fundo, borda = cor
    extra = (f'<sup style="font-size:10px;color:{borda};font-weight:600;margin-left:2px">'
             f"{html.escape(rotulo)}</sup>") if rotulo else ""
    return (f'<mark title="{html.escape(dica, quote=True)}" style="background:{fundo};border-bottom:2px solid {borda};'
            f'padding:0 2px;border-radius:3px">{html.escape(trecho)}</mark>{extra}')


def realcar_original(texto: str, entidades: list[Entidade]) -> str:
    """Texto original com as detecções marcadas (vermelho = tarjar, amarelo = revisar)."""
    partes, cursor = [], 0
    for e in sorted(entidades, key=lambda e: (e.inicio, -e.fim)):
        if e.inicio < cursor:
            continue  # sobreposição: a primeira marcação prevalece na visualização
        partes.append(html.escape(texto[cursor:e.inicio]))
        dica = f"{e.rotulo} — {e.acao}. {e.base_legal}" + (f" ({e.motivo})" if e.motivo else "")
        partes.append(_marca(texto[e.inicio:e.fim], CORES.get(e.acao, CORES["alertar"]), dica, e.rotulo))
        cursor = e.fim
    partes.append(html.escape(texto[cursor:]))
    return f'<div style="{_CAIXA}">{"".join(partes)}</div>'


def realcar_saida(r: Resultado) -> str:
    """Texto anonimizado com as substituições destacadas."""
    partes, cursor = [], 0
    for s in sorted(r.substituicoes, key=lambda s: s["inicio_saida"]):
        partes.append(html.escape(r.texto[cursor:s["inicio_saida"]]))
        partes.append(_marca(r.texto[s["inicio_saida"]:s["fim_saida"]], ("#dcfce7", "#166534"), s["tipo"]))
        cursor = s["fim_saida"]
    partes.append(html.escape(r.texto[cursor:]))
    return f'<div style="{_CAIXA}">{"".join(partes)}</div>'
