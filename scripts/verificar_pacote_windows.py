"""Verifica o pacote portátil para Windows já extraído: executa-o como um usuário o faria.

Usa apenas o próprio pacote — o ``themis.bat`` e o Python incorporável —, com o ``PATH`` reduzido às
pastas do Windows, para comprovar que nada depende de um Python instalado. Anonimiza os exemplos
fictícios (PDF e DOCX) e confere, com as bibliotecas do próprio pacote, que os dados pessoais não
estão nos arquivos gerados e que o manifesto foi gravado.

Uso::

    python scripts/verificar_pacote_windows.py <pasta do pacote extraído>
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - executa o pacote em verificação
import sys
import tempfile
from pathlib import Path

PROIBIDOS = ["529.982.247-25", "Maria Aparecida", "maria.souza@exemplo.com.br", "111.444.777-35", "João Pereira"]

CONFERIR = r"""
import sys, docx, pdfplumber
pdf, doc = sys.argv[1], sys.argv[2]
with pdfplumber.open(pdf) as p:
    texto = "\n".join(pg.extract_text() or "" for pg in p.pages)
texto += "\n" + "\n".join(par.text for par in docx.Document(doc).paragraphs)
sys.stdout.buffer.write(texto.encode("utf-8"))
"""


def main() -> int:
    pacote = Path(sys.argv[1]).resolve()
    bat, python = pacote / "themis.bat", pacote / "python" / "python.exe"
    interface = pacote / "Iniciar Themis.bat"
    if not (interface.exists() and " interface " in interface.read_text(encoding="ascii")
            and "themis_lgpd.cli %*" in bat.read_text(encoding="ascii")):
        print("lançadores ausentes ou trocados (Iniciar Themis.bat e themis.bat)")
        return 1
    # Caminhos internos curtos: extraído em C:\Users\<nome>\Downloads\<pasta do zip>, o pacote precisa
    # caber no limite de 260 caracteres do Windows. O bytecode (__pycache__) gerado em execução fica de
    # fora: se não couber, o Python apenas deixa de gravá-lo.
    maior = max(len(str(f.relative_to(pacote.parent))) for f in pacote.rglob("*") if "__pycache__" not in f.parts)
    print(f"maior caminho interno: {maior} caracteres")
    if maior > 150:
        print("caminho interno longo demais para extração em pastas comuns")
        return 1
    raiz_windows = os.environ.get("SYSTEMROOT", r"C:\Windows")
    env = {**os.environ, "PATH": f"{raiz_windows}\\System32;{raiz_windows}"}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    with tempfile.TemporaryDirectory() as tmp:
        saida, manifesto = Path(tmp) / "saida", Path(tmp) / "custodia.jsonl"
        versao = subprocess.run(["cmd", "/c", str(bat), "--versao"], env=env, capture_output=True, text=True,  # noqa: S603, S607
                                check=True)
        print(versao.stdout.strip())
        exemplos = pacote / "exemplos"
        r = subprocess.run(["cmd", "/c", str(bat), "anonimizar", str(exemplos / "despacho_ficticio.pdf"),  # noqa: S603, S607
                            str(exemplos / "oficio_ficticio.docx"), "-o", str(saida), "--manifesto", str(manifesto)],
                           env=env, capture_output=True, text=True, encoding="utf-8")
        print(r.stderr)
        if r.returncode != 0:
            print(f"falhou com código {r.returncode}")
            return 1
        pdf, doc = saida / "despacho_ficticio_anonimizado.pdf", saida / "oficio_ficticio_anonimizado.docx"
        texto = subprocess.run([str(python), "-c", CONFERIR, str(pdf), str(doc)], env=env, capture_output=True,  # noqa: S603
                               text=True, encoding="utf-8", check=True).stdout
        vazados = [p for p in PROIBIDOS if p in texto]
        linhas = [json.loads(linha) for linha in manifesto.read_text(encoding="utf-8").splitlines()]
        print(f"manifesto: {len(linhas)} arquivo(s), situações {sorted({x['situacao'] for x in linhas})}")
        if vazados or len(linhas) != 2 or any(x["situacao"] != "ok" for x in linhas) or "[CPF]" not in texto:
            print(f"falha: vazados={vazados}")
            return 1
    print("pacote portátil verificado: exemplos anonimizados sem vazamento, manifesto gravado")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
