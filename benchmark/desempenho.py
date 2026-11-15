"""Benchmark de desempenho: tempo de análise de textos longos e de anonimização de PDFs.

Mede o que um órgão encontra em documentos reais extensos — processos com dezenas de páginas,
relatórios com centenas de milhares de caracteres:

* **texto**: análise de textos de 10, 50 e 100 mil caracteres (pedidos fictícios concatenados, com
  nomes, CPFs, telefones e endereços), em segundos e em milissegundos por mil caracteres — a
  segunda medida deve ficar estável com o tamanho (crescimento linear);
* **pdf**: anonimização de PDFs de texto com 10 e 50 páginas (uma tarja por página), em segundos,
  e o tamanho do arquivo gerado em relação ao original.

Uso::

    python benchmark/desempenho.py [--json benchmark/resultado_desempenho.json] [--sem-pdf]
"""

from __future__ import annotations

import argparse
import io
import json
import platform
import random
import sys
import time

from faker import Faker

from themis_lgpd import Anonimizador, __version__


def texto_longo(caracteres: int, semente: int = 7) -> str:
    """Texto fictício com dados pessoais distribuídos, com o tamanho pedido."""
    fk = Faker("pt_BR")
    fk.seed_instance(semente)
    rng = random.Random(semente)  # nosec B311 - dados fictícios
    partes, total = [], 0
    while total < caracteres:
        p = (f"Requerente {fk.first_name()} {fk.last_name()}, CPF {fk.cpf()}, telefone {fk.phone_number()}, "
             f"residente na {fk.street_name()}, {rng.randint(1, 999)}, solicita cópia do processo "
             f"{rng.randint(10000, 99999)}/{rng.randint(2018, 2025)} e informações sobre o atendimento prestado "
             f"pela unidade. {fk.paragraph(nb_sentences=4)}\n")
        partes.append(p)
        total += len(p)
    return "".join(partes)[:caracteres]


def pdf_de_texto(paginas: int, semente: int = 7) -> bytes:
    """PDF com uma página de texto por página pedida, cada uma com um nome e um CPF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    fk = Faker("pt_BR")
    fk.seed_instance(semente)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for _ in range(paginas):
        y = 800
        c.drawString(60, y, f"Requerente: {fk.first_name()} {fk.last_name()} — CPF {fk.cpf()}")
        for linha in fk.paragraphs(nb=12):
            y -= 18
            c.drawString(60, y, linha[:95])
        c.showPage()
    c.save()
    return buf.getvalue()


def medir_texto(anon: Anonimizador, tamanhos: list[int]) -> list[dict]:
    anon.analisar("aquecimento do modelo com CPF 529.982.247-25")
    saida = []
    for n in tamanhos:
        t = texto_longo(n)
        inicio = time.perf_counter()
        anon.analisar(t)
        s = time.perf_counter() - inicio
        saida.append({"caracteres": n, "segundos": round(s, 2), "ms_por_mil_caracteres": round(s * 1000 / (n / 1000), 1)})
    return saida


def medir_pdf(anon: Anonimizador, paginas: list[int]) -> list[dict]:
    from themis_lgpd.formatos import anonimizar_arquivo

    saida = []
    for n in paginas:
        dados = pdf_de_texto(n)
        inicio = time.perf_counter()
        res = anonimizar_arquivo(dados, "processo.pdf", anon, ocr=False)
        s = time.perf_counter() - inicio
        saida.append({"paginas": n, "segundos": round(s, 2), "segundos_por_pagina": round(s / n, 3),
                      "kb_original": len(dados) // 1024, "kb_gerado": len(res.dados) // 1024,
                      "proporcao_tamanho": round(len(res.dados) / len(dados), 1)})
    return saida


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="grava o resultado neste arquivo")
    ap.add_argument("--sem-pdf", action="store_true")
    ap.add_argument("--tamanhos", default="10000,50000,100000")
    ap.add_argument("--paginas", default="10,50")
    args = ap.parse_args()
    anon = Anonimizador("lai")
    res = {"versao": __version__, "python": platform.python_version(), "plataforma": platform.platform(terse=True),
           "texto": medir_texto(anon, [int(x) for x in args.tamanhos.split(",")])}
    if not args.sem_pdf:
        res["pdf"] = medir_pdf(anon, [int(x) for x in args.paginas.split(",")])
    texto = json.dumps(res, ensure_ascii=False, indent=2)
    print(texto)
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto + "\n")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
