"""Monta o pacote portátil do Themis LGPD para Windows (64 bits): sem instalação, sem administrador.

O pacote reúne, numa única pasta que funciona a partir de qualquer local (disco, pen drive, pasta de
rede):

* o Python incorporável oficial (python.org), isolado — não lê nem altera nenhum Python instalado;
* as dependências nas versões testadas de ``requirements/producao.txt``, o modelo de linguagem
  ``pt_core_news_lg`` e o Themis;
* ``Iniciar Themis.bat``, que abre a interface web no navegador, e ``themis.bat``, para a linha de comando.

O OCR usa o RapidOCR incluído; nenhum programa externo precisa ser instalado.

Deve ser executado no Windows, com o Python (versão e 64 bits) que irá no pacote: as dependências
são instaladas a partir das rodas compiladas para essa versão. O Python incorporável é conferido pelo
resumo publicado na API do python.org (SHA-256 quando disponível; MD5 nas versões mais antigas).

Uso::

    python scripts/empacotar_windows.py [--saida dist] [--sem-zip]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess  # nosec B404 - executa o pip do próprio interpretador
import sys
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MODELO = ("pt_core_news_lg @ https://github.com/explosion/spacy-models/releases/download/pt_core_news_lg-3.8.0/"
          "pt_core_news_lg-3.8.0-py3-none-any.whl#sha256=2561c9a72a938d37141e9694e1a36d25061a44ce7e4f3bad2d3fa3bb836191af")
API_PYTHON = "https://www.python.org/api/v2/downloads"

THEMIS_BAT = r"""@echo off
rem Themis LGPD - interface web local (http://127.0.0.1:8501). Feche esta janela para encerrar.
rem Nada e enviado para fora deste computador.
setlocal
set "PYTHONUTF8=1"
"%~dp0python\python.exe" -m themis_lgpd.cli interface --porta 8501 %*
"""

CLI_BAT = r"""@echo off
rem Themis LGPD - linha de comando. Exemplo: themis.bat anonimizar documento.pdf
setlocal
set "PYTHONUTF8=1"
"%~dp0python\python.exe" -m themis_lgpd.cli %*
"""

LEIA_ME = """Themis LGPD {versao} — pacote portátil para Windows (64 bits)

Anonimização de documentos públicos (LGPD/LAI). Todo o processamento ocorre neste computador: nada é
enviado para a internet, e nada é instalado no Windows.

INTERFACE WEB
  Extraia o pacote numa pasta de caminho curto (por exemplo, C:\\Themis ou a pasta Downloads): o
  Windows limita os caminhos de arquivo a 260 caracteres.
  Dê dois cliques em "Iniciar Themis.bat". O navegador abre em http://127.0.0.1:8501 (a primeira abertura leva
  alguns segundos). Para encerrar, feche a janela preta.

LINHA DE COMANDO
  Abra o Prompt de Comando nesta pasta e use themis.bat, por exemplo:
    themis.bat anonimizar C:\\documentos\\despacho.pdf
    themis.bat anonimizar C:\\documentos -R -o C:\\publicacao --manifesto custodia.jsonl
    themis.bat --help

DOCUMENTAÇÃO
  https://github.com/matheusteixeira-commits/themis-lgpd

A ferramenta apoia, mas não substitui, a revisão humana antes da publicação.
Licenças: LICENSE e NOTICE nesta pasta; componentes de terceiros em python\\Lib\\site-packages.
"""


def _baixar(url: str, destino: Path) -> Path:
    if not destino.exists():
        print(f"baixando {url}")
        destino.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=300) as r, open(destino, "wb") as f:  # noqa: S310  # nosec B310
            shutil.copyfileobj(r, f)
    return destino


def _resumo_oficial(versao: str, url: str) -> tuple[str, str]:
    """Algoritmo e resumo publicados pelo python.org para o arquivo."""
    nome = urllib.request.quote(f"Python {versao}")
    with urllib.request.urlopen(f"{API_PYTHON}/release/?name={nome}", timeout=60) as r:  # noqa: S310  # nosec B310
        release = json.load(r)[0]["resource_uri"].rstrip("/").split("/")[-1]
    with urllib.request.urlopen(f"{API_PYTHON}/release_file/?release={release}", timeout=60) as r:  # noqa: S310  # nosec B310
        arquivos = json.load(r)
    item = next(a for a in arquivos if a["url"] == url)
    if item.get("sha256_sum"):
        return "sha256", item["sha256_sum"]
    return "md5", item["md5_sum"]


def _python_incorporavel(versao: str, cache: Path) -> Path:
    url = f"https://www.python.org/ftp/python/{versao}/python-{versao}-embed-amd64.zip"
    arquivo = _baixar(url, cache / Path(url).name)
    algoritmo, esperado = _resumo_oficial(versao, url)
    obtido = hashlib.new(algoritmo, arquivo.read_bytes(), usedforsecurity=False).hexdigest()
    if obtido != esperado:
        arquivo.unlink()
        raise SystemExit(f"resumo {algoritmo} do Python incorporável não confere ({obtido} ≠ {esperado})")
    print(f"Python {versao} incorporável conferido ({algoritmo})")
    return arquivo


def _pip(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "pip", "--disable-pip-version-check", *args], check=True)  # noqa: S603  # nosec B603


def montar(saida: Path, compactar: bool = True) -> Path:
    if sys.platform != "win32" or platform.architecture()[0] != "64bit":
        raise SystemExit("execute no Windows 64 bits, com o Python que irá no pacote")
    # A versão é lida do arquivo, sem importar o pacote: o Python que monta o pacote não precisa ter as
    # dependências do Themis instaladas.
    texto_versao = (RAIZ / "src" / "themis_lgpd" / "_versao.py").read_text(encoding="utf-8")
    __version__ = re.search(r'__version__ = "([^"]+)"', texto_versao).group(1)

    versao_py = platform.python_version()
    nome = f"themis-lgpd-{__version__}-windows-x64"
    # A pasta interna tem nome curto (a versão fica no nome do .zip): caminhos de arquivo no Windows
    # se limitam a 260 caracteres, e o pacote deve funcionar extraído em pastas comuns, como Downloads.
    pasta = saida / "themis-lgpd"
    if pasta.exists():
        shutil.rmtree(pasta)
    python = pasta / "python"
    with zipfile.ZipFile(_python_incorporavel(versao_py, saida / ".cache")) as z:
        z.extractall(python)

    # O arquivo ._pth isola o Python incorporável (ignora PYTHONPATH e o registro do Windows) e
    # declara onde ficam as dependências.
    pth = next(python.glob("python*._pth"))
    zipado = next(python.glob("python*.zip")).name
    pth.write_text(f"{zipado}\n.\nLib\\site-packages\nimport site\n", encoding="ascii")

    site = python / "Lib" / "site-packages"
    rodas = saida / ".cache" / "rodas"
    if rodas.exists():
        shutil.rmtree(rodas)
    _pip("wheel", "--no-deps", "--wheel-dir", str(rodas), str(RAIZ))
    _pip("install", "--no-warn-script-location", "--no-compile", "--target", str(site),
         "-r", str(RAIZ / "requirements" / "producao.txt"), MODELO, *[str(r) for r in rodas.glob("themis_lgpd-*.whl")])
    # Fora do pacote: executáveis de console (o pacote usa os .bat), modelos de projeto do Streamlit
    # para desenvolvedores e bytecode compilado, que alongam os caminhos sem uso em execução.
    shutil.rmtree(site / "bin", ignore_errors=True)
    shutil.rmtree(site / "streamlit" / ".agents", ignore_errors=True)
    for cache in list(pasta.rglob("__pycache__")):
        shutil.rmtree(cache)
    maior = max(len(str(f.relative_to(saida))) for f in pasta.rglob("*"))
    print(f"maior caminho dentro do pacote: {maior} caracteres (limite do Windows: 260 no total)")

    # Nomes distintos sem depender de maiúsculas: o sistema de arquivos do Windows não as distingue.
    (pasta / "Iniciar Themis.bat").write_text(THEMIS_BAT.replace("\n", "\r\n"), encoding="ascii")
    (pasta / "themis.bat").write_text(CLI_BAT.replace("\n", "\r\n"), encoding="ascii")
    (pasta / "LEIA-ME.txt").write_text(LEIA_ME.format(versao=__version__).replace("\n", "\r\n"), encoding="utf-8-sig")
    for licenca in ("LICENSE", "NOTICE"):
        shutil.copy(RAIZ / licenca, pasta / f"{licenca}.txt")
    shutil.copytree(RAIZ / "exemplos", pasta / "exemplos")

    tamanho = sum(f.stat().st_size for f in pasta.rglob("*") if f.is_file())
    print(f"pasta {pasta}: {tamanho / 2**20:.0f} MB")
    if not compactar:
        return pasta
    destino = saida / f"{nome}.zip"
    destino.unlink(missing_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(pasta.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(saida))
    print(f"pacote {destino}: {destino.stat().st_size / 2**20:.0f} MB")
    return destino


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saida", type=Path, default=RAIZ / "dist")
    ap.add_argument("--sem-zip", action="store_true", help="gera só a pasta, sem o arquivo .zip")
    args = ap.parse_args()
    montar(args.saida.resolve(), not args.sem_zip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
