"""Relatórios de tarjamento.

São produzidos dois tipos de relatório, que nunca se confundem:

* **Relatório de tarjamento**, que pode acompanhar a publicação: informa o que foi tarjado, com a
  base legal e a justificativa de cada categoria, sem os valores originais. Atende ao Enunciado
  CGU nº 4/2022, segundo o qual a restrição de acesso deve ser motivada, e serve de nota de
  tarjamento na resposta ao pedido de acesso à informação.
* **Relatório de auditoria com valores**, de uso interno: contém os dados pessoais originais e só é
  gerado mediante pedido explícito (``incluir_valores=True``). Todas as saídas desse tipo começam
  com :data:`AVISO_VALORES`.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime

from . import __version__
from .catalogo import CATEGORIAS, categoria_de
from .motor import Entidade, Resultado

#: Aviso que abre todo relatório que contém valores originais.
AVISO_VALORES = "ATENÇÃO: CONTÉM DADOS PESSOAIS ORIGINAIS — uso interno, não publicar."


def _contexto(r: Resultado, e: Entidade, largura: int = 45) -> str:
    """Trecho do texto já anonimizado em torno da entidade.

    Auxilia a revisão sem expor o dado: o contexto é extraído da saída, onde o valor tarjado já foi
    substituído.
    """
    if e.inicio_saida is None:
        return ""
    a = max(0, e.inicio_saida - largura)
    b = min(len(r.texto), (e.fim_saida or e.inicio_saida) + largura)
    return ("…" if a else "") + r.texto[a:b].replace("\n", " ") + ("…" if b < len(r.texto) else "")


def linhas(resultados: list[Resultado], incluir_valores: bool = False, incluir_alertas: bool = True,
           documentos: Sequence[str] | None = None) -> list[dict]:
    """Uma linha por entidade tarjada ou sinalizada para revisão.

    Args:
        resultados: Resultados da anonimização.
        incluir_valores: Acrescenta a coluna ``valor_original``. Torna o relatório de uso interno.
        incluir_alertas: Inclui as entidades sinalizadas para revisão (não tarjadas).
        documentos: Identificação de cada resultado (em lotes, o arquivo de origem); sem ela, os
            documentos são numerados.

    Returns:
        Dicionários com documento, ação, tipo, categoria, base legal, justificativa, confiança,
        validação por dígito verificador e contexto anonimizado.
    """
    saida = []
    for n_doc, r in enumerate(resultados, start=1):
        for e in r.entidades:
            if e.acao == "manter" or (e.acao == "alertar" and not incluir_alertas):
                continue
            linha = {
                "documento": documentos[n_doc - 1] if documentos else n_doc,
                "acao": "Tarjado" if e.acao == "tarjar" else "Revisar (não tarjado)",
                "tipo": e.rotulo,
                "categoria": CATEGORIAS[e.categoria].nome,
                "base_legal": e.base_legal,
                "justificativa": e.motivo or categoria_de(e.tipo).justificativa,
                "confianca": f"{e.score:.0%}",
                "validado_por_digito": "sim" if e.validado else "",
                "contexto_anonimizado": _contexto(r, e),
            }
            if incluir_valores:
                linha["valor_original"] = e.valor
            saida.append(linha)
    return saida


def resumo(resultados: list[Resultado]) -> dict:
    """Totais por tipo e fundamentação por categoria, sem nenhum valor original."""
    tarjadas = [e for r in resultados for e in r.tarjadas]
    por_categoria = Counter(e.categoria for e in tarjadas)
    return {
        "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "ferramenta": f"Themis LGPD {__version__}",
        "perfil": resultados[0].perfil if resultados else None,
        "modo": resultados[0].modo if resultados else None,
        "documentos": len(resultados),
        "tarjados": len(tarjadas),
        "para_revisar": sum(len(r.alertas) for r in resultados),
        "por_tipo": dict(Counter(e.rotulo for e in tarjadas).most_common()),
        "fundamentacao": [
            {"categoria": CATEGORIAS[c].nome, "quantidade": n, "base_legal": CATEGORIAS[c].base_legal,
             "justificativa": CATEGORIAS[c].justificativa}
            for c, n in por_categoria.most_common()
        ],
    }


def nota_de_tarjamento(resultados: list[Resultado], documento: str = "o documento") -> str:
    """Nota de tarjamento para acompanhar a resposta a um pedido de acesso à informação.

    Args:
        resultados: Resultados da anonimização do documento.
        documento: Como o documento é referido no texto da nota.
    """
    r = resumo(resultados)
    if not r["tarjados"]:
        return f"Não foram identificadas informações pessoais a tarjar em {documento}."
    partes = [
        f"NOTA DE TARJAMENTO — {documento}",
        "",
        f"Foram tarjados {r['tarjados']} trecho(s) contendo informações pessoais, com fundamento na "
        "Lei nº 12.527/2011 (LAI), art. 31, e na Lei nº 13.709/2018 (LGPD), conforme abaixo. As demais "
        "informações do documento foram mantidas, em atenção ao princípio da máxima divulgação e ao "
        "art. 7º, § 2º, da LAI (acesso à parte não sigilosa).",
        "",
    ]
    for f in r["fundamentacao"]:
        partes.append(f"• {f['categoria']} ({f['quantidade']}): {f['justificativa']} Fundamento: {f['base_legal']}.")
    partes += ["", f"Tarjamento realizado com apoio da ferramenta {r['ferramenta']} e revisado por servidor responsável."]
    return "\n".join(partes)


def para_json(resultados: list[Resultado], incluir_valores: bool = False,
              documentos: Sequence[str] | None = None) -> str:
    """Relatório em JSON: resumo e itens."""
    dados = {"resumo": resumo(resultados), "itens": linhas(resultados, incluir_valores, documentos=documentos)}
    if incluir_valores:
        dados = {"aviso": AVISO_VALORES, **dados}
    return json.dumps(dados, ensure_ascii=False, indent=2)


def para_csv(resultados: list[Resultado], incluir_valores: bool = False,
             documentos: Sequence[str] | None = None) -> str:
    """Relatório em CSV (separador ``;``, UTF-8 com BOM para abertura direta no Excel)."""
    itens = linhas(resultados, incluir_valores, documentos=documentos)
    buf = io.StringIO()
    if incluir_valores:
        buf.write(f"# {AVISO_VALORES}\n")
    if itens:
        w = csv.DictWriter(buf, fieldnames=list(itens[0]), delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(_sem_formula(i) for i in itens)
    return chr(0xFEFF) + buf.getvalue()


def _sem_formula(item: dict) -> dict:
    """Neutraliza injeção de fórmula em planilhas (células iniciadas por ``=``, ``+``, ``-`` ou ``@``).

    O contexto do relatório vem do documento analisado, que pode conter texto preparado para ser
    executado como fórmula ao abrir o relatório no Excel.
    """
    return {k: ("'" + v if isinstance(v, str) and v[:1] and v[:1] in "=+-@" else v) for k, v in item.items()}


def para_xlsx(resultados: list[Resultado], incluir_valores: bool = False,
              documentos: Sequence[str] | None = None) -> bytes:
    """Relatório em XLSX, com as abas "Resumo" e "Itens"."""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Resumo"
    r = resumo(resultados)
    if incluir_valores:
        ws.append([AVISO_VALORES])
        ws["A1"].font = Font(bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor="B00020")
    for chave in ("ferramenta", "gerado_em", "perfil", "modo", "documentos", "tarjados", "para_revisar"):
        ws.append([chave.replace("_", " ").capitalize(), r[chave]])
    ws.append([])
    ws.append(["Categoria", "Quantidade", "Base legal", "Justificativa"])
    for f in r["fundamentacao"]:
        ws.append([f["categoria"], f["quantidade"], f["base_legal"], f["justificativa"]])
    itens = linhas(resultados, incluir_valores, documentos=documentos)
    ws2 = wb.create_sheet("Itens")
    if itens:
        ws2.append(list(itens[0]))
        for c in ws2[1]:
            c.font = Font(bold=True)
        for i in itens:
            ws2.append(list(_sem_formula(i).values()))
    for planilha in (ws, ws2):
        for col in planilha.columns:
            planilha.column_dimensions[col[0].column_letter].width = 28
            for c in col:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.properties.creator = "Themis LGPD"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
