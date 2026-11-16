"""Ferramentas do conjunto de referência: validação, concordância entre anotadores e congelamento.

Uso::

    python benchmark/ouro/ferramentas.py validar ARQUIVO.jsonl
    python benchmark/ouro/ferramentas.py concordancia REDATOR.jsonl CEGA.jsonl [--divergencias saida.jsonl]
    python benchmark/ouro/ferramentas.py congelar ARQUIVO.jsonl [...]

Ver ``benchmark/ouro/DIRETRIZES.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROTULOS = frozenset({
    "NOME_PESSOA", "DOC_PESSOAL", "CONTATO", "ENDERECO", "DATA_NASC", "DADO_SAUDE", "DADO_SENSIVEL",
    "DADO_FINANCEIRO", "ID_PROCESSUAL", "DOC_PROFISSIONAL", "ID_VEICULO", "QUASI_IDENTIFICADOR",
})
#: Rótulos que o perfil LAI sinaliza para revisão: protegidos quando tarjados ou sinalizados.
SO_ALERTA = frozenset({"QUASI_IDENTIFICADOR"})
PASTA = Path(__file__).parent


def ler(arquivo: Path) -> list[dict]:
    return [json.loads(linha) for linha in Path(arquivo).read_text(encoding="utf-8").splitlines() if linha.strip()]


def ocorrencias(texto: str, valor: str) -> list[tuple[int, int]]:
    """Ocorrências de ``valor`` como palavra inteira (sem letra ou dígito colado antes ou depois)."""
    if not valor.strip():
        return []
    padrao = re.compile(r"(?<![\w])" + re.escape(valor) + r"(?![\w])")
    return [(m.start(), m.end()) for m in padrao.finditer(texto)]


def validar(docs: list[dict]) -> list[str]:
    """Problemas de formato: rótulo desconhecido, valor ausente do texto, identificador repetido,
    trecho anotado como pessoal e público ao mesmo tempo."""
    problemas, vistos = [], set()
    for d in docs:
        ident = d.get("id")
        if not ident or ident in vistos:
            problemas.append(f"{ident}: identificador ausente ou repetido")
        vistos.add(ident)
        texto = d.get("texto", "")
        if not texto.strip():
            problemas.append(f"{ident}: texto vazio")
        pessoais = set()
        for e in d.get("entidades", []):
            if e.get("tipo") not in ROTULOS:
                problemas.append(f"{ident}: rótulo desconhecido {e.get('tipo')!r}")
            if not ocorrencias(texto, e.get("valor", "")):
                problemas.append(f"{ident}: valor {e.get('valor')!r} não encontrado como palavra inteira")
            pessoais.add(e.get("valor"))
        for p in d.get("publicos", []):
            if not ocorrencias(texto, p):
                problemas.append(f"{ident}: trecho público {p!r} não encontrado como palavra inteira")
            if p in pessoais:
                problemas.append(f"{ident}: {p!r} anotado como pessoal e como público")
    return problemas


def _conjunto(d: dict, com_rotulo: bool = True) -> set:
    return {(e["tipo"], e["valor"].strip()) if com_rotulo else e["valor"].strip() for e in d.get("entidades", [])}


def concordancia(redator: list[dict], cega: list[dict]) -> tuple[dict, list[dict]]:
    """Concordância entre as anotações (F1 por valor, com e sem rótulo) e as divergências por documento.

    Com dois anotadores e anotações por valor, o F1 entre eles é a medida usual de concordância em
    reconhecimento de entidades (o kappa exige um universo fechado de itens, que aqui não existe).
    """
    por_id = {d["id"]: d for d in cega}
    soma = Counter()
    divergencias = []
    for d in redator:
        outro = por_id.get(d["id"])
        if outro is None:
            continue
        for chave, rotulado in (("rotulo", True), ("valor", False)):
            a, b = _conjunto(d, rotulado), _conjunto(outro, rotulado)
            soma[f"{chave}:comum"] += len(a & b)
            soma[f"{chave}:redator"] += len(a)
            soma[f"{chave}:cega"] += len(b)
        pa, pb = set(d.get("publicos", [])), set(outro.get("publicos", []))
        a, b = _conjunto(d), _conjunto(outro)
        if a != b or pa != pb:
            divergencias.append({"id": d["id"], "so_redator": sorted(a - b), "so_cega": sorted(b - a),
                                 "publicos_so_redator": sorted(pa - pb), "publicos_so_cega": sorted(pb - pa)})
    resultado = {"documentos": len(redator), "documentos_com_divergencia": len(divergencias)}
    for chave in ("rotulo", "valor"):
        comum, r, c = soma[f"{chave}:comum"], soma[f"{chave}:redator"], soma[f"{chave}:cega"]
        resultado[f"f1_por_{chave}"] = round(2 * comum / max(1, r + c), 4)
    return resultado, divergencias


def congelar(arquivos: list[Path]) -> dict:
    """Registra o SHA-256 e as contagens de cada arquivo final em ``CONGELAMENTO.json``."""
    registro = {}
    for arq in arquivos:
        docs = ler(arq)
        registro[Path(arq).name] = {
            "sha256": hashlib.sha256(Path(arq).read_bytes()).hexdigest(), "documentos": len(docs),
            "entidades": dict(sorted(Counter(e["tipo"] for d in docs for e in d["entidades"]).items())),
            "publicos": sum(len(d.get("publicos", [])) for d in docs),
        }
    (PASTA / "CONGELAMENTO.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8", newline="\n")
    return registro


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="comando", required=True)
    v = sub.add_parser("validar")
    v.add_argument("arquivo", type=Path)
    c = sub.add_parser("concordancia")
    c.add_argument("redator", type=Path)
    c.add_argument("cega", type=Path)
    c.add_argument("--divergencias", type=Path)
    g = sub.add_parser("congelar")
    g.add_argument("arquivos", type=Path, nargs="+")
    args = ap.parse_args()
    if args.comando == "validar":
        problemas = validar(ler(args.arquivo))
        print("\n".join(problemas) or "sem problemas")
        sys.exit(1 if problemas else 0)
    if args.comando == "concordancia":
        resultado, divergencias = concordancia(ler(args.redator), ler(args.cega))
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        if args.divergencias:
            args.divergencias.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in divergencias),
                                         encoding="utf-8", newline="\n")
        return
    print(json.dumps(congelar(args.arquivos), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
