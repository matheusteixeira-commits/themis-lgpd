"""Conversão de formatos antigos do Office (.doc, .xls, .ppt) e de RTF pelo LibreOffice.

Esses formatos não são lidos diretamente: os binários do Office 97–2003 guardam texto em estruturas
que só um leitor completo interpreta com segurança, e o RTF codifica caracteres em escapes próprios.
Quando o LibreOffice está instalado, o arquivo é convertido para o formato aberto correspondente
(DOCX, XLSX ou PPTX) e anonimizado como tal — passando por toda a limpeza daquele formato
(propriedades, comentários, revisões, objetos incorporados). O arquivo gerado fica no formato novo.
Sem o LibreOffice, o arquivo é recusado com orientação ao usuário.

A conversão roda em processo separado, sem interface, com perfil de usuário temporário descartado
ao final (sem macros habilitadas nem histórico de arquivos recentes) e tempo máximo de execução.

O executável é procurado em ``THEMIS_SOFFICE``, no ``PATH`` (``soffice`` ou ``libreoffice``) e nos
locais de instalação padrão do Windows e do macOS.
"""

from __future__ import annotations

import os
import shutil
import subprocess  # noqa: S404 - executa apenas o LibreOffice, com argumentos fixos  # nosec B404
import tempfile
from pathlib import Path

from . import ArquivoInvalido

#: Formato gerado pela conversão de cada formato antigo.
DESTINOS = {"doc": "docx", "rtf": "docx", "xls": "xlsx", "ppt": "pptx"}
#: Tempo máximo de uma conversão.
TEMPO_MAXIMO_S = 180

_LOCAIS_PADRAO = (
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "LibreOffice" / "program" / "soffice.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "LibreOffice" / "program" / "soffice.exe",
    Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
)


def localizar_soffice() -> str | None:
    """Caminho do executável do LibreOffice, ou ``None`` se não estiver instalado."""
    configurado = os.environ.get("THEMIS_SOFFICE")
    if configurado:
        return configurado if Path(configurado).is_file() else None
    for nome in ("soffice", "libreoffice"):
        achado = shutil.which(nome)
        if achado:
            return achado
    return next((str(p) for p in _LOCAIS_PADRAO if p.is_file()), None)


def tipo_ole(dados: bytes) -> str | None:
    """Tipo de um arquivo no formato composto da Microsoft (OLE), pelos nomes dos fluxos internos.

    Returns:
        ``doc``, ``xls`` ou ``ppt``; ``msg`` (mensagem do Outlook); ``protegido`` (documento do
        Office 2007+ criptografado por senha); ``None`` se não identificado.
    """
    def fluxo(nome: str) -> bytes:
        return nome.encode("utf-16-le") + b"\x00\x00"

    if fluxo("EncryptedPackage") in dados:
        return "protegido"
    if fluxo("WordDocument") in dados:
        return "doc"
    if fluxo("Workbook") in dados or fluxo("Book") in dados:
        return "xls"
    if fluxo("PowerPoint Document") in dados:
        return "ppt"
    if "__substg1.0_".encode("utf-16-le") in dados:
        return "msg"
    return None


def converter(dados: bytes, origem: str) -> bytes:
    """Converte o arquivo para o formato aberto correspondente (ver :data:`DESTINOS`).

    Raises:
        ArquivoInvalido: LibreOffice ausente, conversão sem resultado (arquivo corrompido ou
            protegido por senha) ou acima do tempo máximo.
    """
    destino = DESTINOS[origem]
    soffice = localizar_soffice()
    if soffice is None:
        raise ArquivoInvalido(f"Arquivos .{origem} são convertidos pelo LibreOffice, que não foi encontrado: instale-o "
                              f"(ou indique o executável em THEMIS_SOFFICE) ou salve o arquivo como .{destino} ou PDF.")
    with tempfile.TemporaryDirectory(prefix="themis-conversao-") as temporaria:
        pasta = Path(temporaria)
        entrada = pasta / f"entrada.{origem}"
        entrada.write_bytes(dados)
        saida = pasta / "saida"
        comando = [soffice, f"-env:UserInstallation={(pasta / 'perfil').as_uri()}", "--headless", "--invisible",
                   "--norestore", "--nolockcheck", "--nodefault", "--nologo", "--convert-to", destino,
                   "--outdir", str(saida), str(entrada)]
        try:
            subprocess.run(  # noqa: S603 - argumentos fixos, sem shell  # nosec B603
                comando, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=TEMPO_MAXIMO_S, check=False)
        except subprocess.TimeoutExpired as erro:
            raise ArquivoInvalido(f"A conversão do arquivo .{origem} pelo LibreOffice excedeu o tempo máximo.") from erro
        except OSError as erro:
            raise ArquivoInvalido("Não foi possível executar o LibreOffice para converter o arquivo.") from erro
        gerado = saida / f"entrada.{destino}"
        if not gerado.is_file() or gerado.stat().st_size == 0:
            raise ArquivoInvalido(f"O LibreOffice não conseguiu converter o arquivo .{origem}: ele pode estar "
                                  "corrompido ou protegido por senha.")
        return gerado.read_bytes()
