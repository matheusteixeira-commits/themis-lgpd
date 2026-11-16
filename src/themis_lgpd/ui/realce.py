"""Geração de HTML seguro e acessível para a interface.

Todo texto do usuário passa por ``html.escape`` antes de qualquer marcação ser inserida, e o
resultado é exibido com ``st.html`` (sem interpretação de Markdown) — nada vindo de um documento
pode virar tag, script, link ou imagem externa.

A ação sobre cada trecho não depende só da cor: cada marcação tem um símbolo e um estilo de
sublinhado próprios (■ contínuo para tarjar, ? tracejado para revisar, ✓ pontilhado para manter) e um
texto para leitores de tela com a ação, o tipo e a base legal — que, de outro modo, só apareceria ao
passar o mouse.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from ..motor import Entidade, Resultado


@dataclass(frozen=True)
class Acao:
    """Apresentação de uma ação: cores, sublinhado, símbolo e descrição em texto."""

    fundo: str
    destaque: str
    sublinhado: str
    simbolo: str
    descricao: str


ACOES = {
    "tarjar": Acao("#fde2e1", "#b42318", "solid", "■", "será tarjado"),
    "alertar": Acao("#fef3c7", "#92400e", "dashed", "?", "alerta para revisão, não será tarjado"),
    "manter": Acao("#e0f2fe", "#075985", "dotted", "✓", "mantido"),
}
_SUBSTITUIDO = Acao("#dcfce7", "#166534", "solid", "", "substituído")
_SUBLINHADOS = {"solid": "contínuo", "dashed": "tracejado", "dotted": "pontilhado"}
_CAIXA = ("font-family:ui-monospace,Consolas,monospace;font-size:13.5px;line-height:1.65;white-space:pre-wrap;"
          "word-break:break-word;padding:14px 16px;border:1px solid #d0d5dd;border-radius:8px;background:#fcfcfd;"
          "max-height:440px;overflow-y:auto;color:#101828")
#: Texto lido por leitores de tela e invisível na tela.
_SO_LEITOR = ("position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;"
              "clip:rect(0,0,0,0);white-space:nowrap;border:0")


def _so_leitor(texto: str) -> str:
    return f'<span style="{_SO_LEITOR}">{html.escape(texto)}</span>'


def _marca(trecho: str, acao: Acao, dica: str, rotulo: str = "") -> str:
    """Trecho destacado: cor, sublinhado e símbolo da ação, rótulo visível e descrição para leitores de tela.

    Trecho, dica e rótulo são escapados.
    """
    extra = ""
    if rotulo:
        extra = (f'<sup aria-hidden="true" style="font-size:10px;color:{acao.destaque};font-weight:600;'
                 f'margin-left:2px">{html.escape(f"{acao.simbolo} {rotulo}".strip())}</sup>')
    return (f'<mark title="{html.escape(dica, quote=True)}" style="background:{acao.fundo};'
            f'border-bottom:2px {acao.sublinhado} {acao.destaque};padding:0 2px;border-radius:3px">'
            f"{html.escape(trecho)}</mark>{extra}{_so_leitor(f' ({dica})')}")


def realcar_original(texto: str, entidades: list[Entidade]) -> str:
    """Texto original com as detecções marcadas pela ação (tarjar, revisar ou manter)."""
    partes, cursor = [], 0
    for e in sorted(entidades, key=lambda e: (e.inicio, -e.fim)):
        if e.inicio < cursor:
            continue  # sobreposição: a primeira marcação prevalece na visualização
        acao = ACOES.get(e.acao, ACOES["alertar"])
        partes.append(html.escape(texto[cursor:e.inicio]))
        dica = f"{e.rotulo}: {acao.descricao}. {e.base_legal}" + (f" ({e.motivo})" if e.motivo else "")
        partes.append(_marca(texto[e.inicio:e.fim], acao, dica, e.rotulo))
        cursor = e.fim
    partes.append(html.escape(texto[cursor:]))
    return f'<div style="{_CAIXA}">{"".join(partes)}</div>'


def realcar_saida(r: Resultado) -> str:
    """Texto anonimizado com as substituições destacadas."""
    partes, cursor = [], 0
    for s in sorted(r.substituicoes, key=lambda s: s["inicio_saida"]):
        partes.append(html.escape(r.texto[cursor:s["inicio_saida"]]))
        partes.append(_marca(r.texto[s["inicio_saida"]:s["fim_saida"]], _SUBSTITUIDO, f"{s['tipo']} substituído"))
        cursor = s["fim_saida"]
    partes.append(html.escape(r.texto[cursor:]))
    return f'<div style="{_CAIXA}">{"".join(partes)}</div>'


def legenda() -> str:
    """Legenda das marcações, em texto: símbolo, sublinhado e descrição de cada ação."""
    itens = "".join(
        f'<li style="margin-right:18px;display:inline-block"><mark aria-hidden="true" style="background:{a.fundo};'
        f'border-bottom:2px {a.sublinhado} {a.destaque};padding:0 4px;border-radius:3px">{a.simbolo}</mark> '
        f"{html.escape(a.descricao.capitalize())} (sublinhado {_SUBLINHADOS[a.sublinhado]})</li>"
        for a in ACOES.values())
    return (f'<ul aria-label="Legenda das marcações" style="list-style:none;padding:0;margin:4px 0;'
            f'font-size:13px;color:#344054">{itens}</ul>'
            '<p style="font-size:12.5px;color:#475467;margin:0">A base legal de cada trecho é lida pelos leitores '
            "de tela junto com o trecho, aparece ao passar o mouse e consta da tabela de revisão.</p>")
