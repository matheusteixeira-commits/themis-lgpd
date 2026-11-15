"""Anonimização de arquivos: TXT, CSV, XLSX, DOCX, PDF e imagens (PNG e JPEG, por OCR).

O formato é identificado pelo conteúdo (assinatura do arquivo), não pela extensão. Cada formato
produz um arquivo novo no mesmo formato — imagens são sempre gravadas em PNG — e, por padrão,
relê o arquivo gerado para confirmar que nenhum valor tarjado permanece legível
(ver :mod:`themis_lgpd.formatos.verificacao`).

Exemplo::

    from themis_lgpd import Anonimizador
    from themis_lgpd.formatos import anonimizar_arquivo

    with open("despacho.pdf", "rb") as f:
        resultado = anonimizar_arquivo(f.read(), "despacho.pdf", Anonimizador(perfil="lai"))
    with open(resultado.nome, "wb") as f:
        f.write(resultado.dados)
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field

from ..motor import Anonimizador, Entidade, Resultado

#: Tamanho máximo de arquivo aceito por padrão.
LIMITE_BYTES_PADRAO = 50 * 1024 * 1024
#: Número máximo de páginas de PDF aceito por padrão.
LIMITE_PAGINAS_PADRAO = 500
#: Tamanho descompactado máximo de DOCX e XLSX (proteção contra "bombas" de compressão).
LIMITE_DESCOMPACTADO = 300 * 1024 * 1024
#: Número máximo de entradas em DOCX e XLSX.
LIMITE_ENTRADAS = 10_000

MIMES = {
    "txt": "text/plain; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/png",  # imagens são sempre gravadas em PNG, sem metadados
}


class ArquivoInvalido(ValueError):
    """Arquivo corrompido, de formato não suportado ou acima dos limites.

    A mensagem é destinada ao usuário e nunca inclui conteúdo do arquivo.
    """


class VazamentoDetectado(RuntimeError):
    """A verificação final encontrou valor tarjado ainda legível no arquivo gerado.

    Quando levantada, nenhum arquivo é entregue. A mensagem informa apenas a quantidade de trechos,
    nunca os valores.
    """


class FalhaOCR(RuntimeError):
    """O mecanismo de OCR falhou ou não está disponível; a página ou imagem não pode ser analisada.

    O processamento é interrompido, pois tratar a falha como "página sem texto" entregaria o conteúdo
    sem tarja.
    """


@dataclass
class ResultadoArquivo:
    """Arquivo anonimizado e informações da análise.

    Attributes:
        dados: Conteúdo do arquivo gerado.
        formato: Formato detectado na entrada (``txt``, ``csv``, ``xlsx``, ``docx``, ``pdf``, ``png``
            ou ``jpg``).
        nome: Nome sugerido para o arquivo gerado.
        resultados: Resultado da análise de cada trecho de texto do arquivo.
        avisos: Informações ao usuário sobre conteúdo removido, não analisado ou convertido.
    """

    dados: bytes
    formato: str
    nome: str
    resultados: list[Resultado] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def mime(self) -> str:
        """Tipo MIME do arquivo gerado."""
        return MIMES.get(self.formato, "application/octet-stream")

    @property
    def entidades(self) -> list[Entidade]:
        """Todas as entidades encontradas no arquivo."""
        return [e for r in self.resultados for e in r.entidades]


def detectar_formato(dados: bytes, nome: str = "") -> str:
    """Identifica o formato pelo conteúdo; a extensão só distingue CSV de texto simples.

    Raises:
        ArquivoInvalido: Formato não suportado.
    """
    cabeca = dados[:8]
    nome = (nome or "").lower()
    if cabeca.startswith(b"%PDF-") or dados[:1024].find(b"%PDF-") >= 0:
        return "pdf"
    if cabeca.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if cabeca.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if cabeca.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(dados)) as z:
                nomes = set(z.namelist())
        except zipfile.BadZipFile as erro:
            raise ArquivoInvalido("Arquivo compactado corrompido.") from erro
        if "word/document.xml" in nomes:
            return "docx"
        if "xl/workbook.xml" in nomes:
            return "xlsx"
        raise ArquivoInvalido("Arquivo ZIP que não é DOCX nem XLSX.")
    if cabeca.startswith(b"\xd0\xcf\x11\xe0"):
        raise ArquivoInvalido("Formato antigo do Office (.doc/.xls), mensagem do Outlook (.msg) ou documento protegido "
                              "por senha, que não são suportados: remova a senha e salve como .docx/.xlsx/.pdf.")
    if cabeca.startswith((b"II*\x00", b"MM\x00*", b"GIF87a", b"GIF89a", b"BM")) or (
            cabeca.startswith(b"RIFF") and dados[8:12] == b"WEBP"):
        raise ArquivoInvalido("Formato de imagem não suportado: converta para PNG, JPEG ou PDF.")
    if b"\x00" in dados[:4096]:
        raise ArquivoInvalido("Formato binário não suportado.")
    # Extensão de formato binário com conteúdo de texto: arquivo corrompido ou renomeado. Processá-lo
    # como texto geraria uma saída com outra extensão, que o usuário poderia não conferir.
    extensao = nome.rsplit(".", 1)[-1] if "." in nome else ""
    if extensao in {"pdf", "docx", "xlsx", "png", "jpg", "jpeg", "doc", "xls"}:
        raise ArquivoInvalido(f"O conteúdo não corresponde à extensão .{extensao}: o arquivo está corrompido ou "
                              "foi renomeado.")
    _recusar_texto_estruturado(dados)
    return "csv" if nome.endswith(".csv") else "txt"


#: Início de marcação HTML ou XML.
_MARCACAO = re.compile(rb"^<(?:!doctype|\?xml|!--|html\b|[a-z][\w:.-]*(?:\s[^>]*)?/?>)", re.IGNORECASE)
#: Cabeçalhos típicos de mensagem de e-mail (RFC 5322).
_CABECALHO_EMAIL = re.compile(rb"^(?:from|to|cc|subject|date|message-id|mime-version|received|return-path|"
                              rb"content-type|reply-to|x-mailer):", re.IGNORECASE)


def _recusar_texto_estruturado(dados: bytes) -> None:
    """Recusa formatos de texto com estrutura própria que não podem ser tratados como texto simples.

    Em HTML, XML e RTF, o conteúdo pode estar codificado (entidades como ``&#46;``, escapes como
    ``\\'e3``) e a marcação se mistura ao texto; em e-mails, o corpo costuma estar em base64. Tratá-los
    como texto simples deixaria dados pessoais sem análise.

    Raises:
        ArquivoInvalido: O conteúdo é HTML, XML, RTF ou mensagem de e-mail.
    """
    inicio = dados[:8192].lstrip(b"\xef\xbb\xbf \t\r\n")
    if inicio[:5].lower() == b"{\\rtf":
        raise ArquivoInvalido("Arquivos RTF não são suportados: salve o documento como DOCX ou PDF.")
    if _MARCACAO.match(inicio):
        raise ArquivoInvalido("Arquivos HTML ou XML ainda não são suportados como texto: salve como PDF ou DOCX.")
    linhas = inicio.split(b"\n\n", 1)[0].replace(b"\r", b"").split(b"\n")[:40]
    if sum(1 for linha in linhas if _CABECALHO_EMAIL.match(linha)) >= 2:
        raise ArquivoInvalido("Mensagens de e-mail (.eml) ainda não são suportadas: salve o conteúdo e os anexos "
                              "como PDF.")


def verificar_zip(dados: bytes, limite: int = LIMITE_DESCOMPACTADO) -> None:
    """Rejeita pacotes cujo tamanho descompactado ou número de entradas excede os limites.

    Raises:
        ArquivoInvalido: Limites excedidos.
    """
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        infos = z.infolist()
        if sum(i.file_size for i in infos) > limite or len(infos) > LIMITE_ENTRADAS:
            raise ArquivoInvalido("Arquivo compactado excede o tamanho descompactado permitido.")


def nome_saida(nome: str, formato: str) -> str:
    """Nome do arquivo gerado: o nome original, sem caminho e sem caracteres especiais, com sufixo."""
    base = (nome or "documento").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base = base.rsplit(".", 1)[0] if "." in base else base
    base = "".join(c for c in base if c.isalnum() or c in "-_ ")[:80].strip() or "documento"
    extensao = "png" if formato in {"png", "jpg"} else formato
    return f"{base}_anonimizado.{extensao}"


def anonimizar_arquivo(
    dados: bytes,
    nome: str = "",
    anonimizador: Anonimizador | None = None,
    *,
    limite_bytes: int = LIMITE_BYTES_PADRAO,
    limite_paginas: int = LIMITE_PAGINAS_PADRAO,
    ocr: bool = True,
    colunas: list[str] | None = None,
    colunas_integrais: list[str] | None = None,
    verificar: bool = True,
    pdfa: bool = False,
) -> ResultadoArquivo:
    """Anonimiza um arquivo e devolve um novo arquivo no mesmo formato.

    Args:
        dados: Conteúdo do arquivo.
        nome: Nome original, usado para distinguir CSV de texto e para nomear a saída.
        anonimizador: Anonimizador configurado; o padrão usa o perfil LAI.
        limite_bytes: Tamanho máximo aceito.
        limite_paginas: Número máximo de páginas de PDF.
        ocr: Permite OCR em PDFs digitalizados, imagens e imagens incorporadas em DOCX e XLSX.
        colunas: Em planilhas, restringe o processamento a estas colunas (pelo cabeçalho).
        colunas_integrais: Em planilhas, colunas a tarjar por inteiro.
        verificar: Relê o arquivo gerado e falha se algum valor tarjado continuar legível. Só deve
            ser desligado em testes de desempenho.
        pdfa: Em PDFs, gera PDF/A-2b para arquivamento (ver :mod:`themis_lgpd.formatos.pdfa`); sem
            efeito nos demais formatos.

    Returns:
        O arquivo gerado, os resultados da análise e os avisos ao usuário.

    Raises:
        ArquivoInvalido: Arquivo vazio, corrompido, de formato não suportado ou acima dos limites.
        VazamentoDetectado: A verificação final encontrou valor tarjado no arquivo gerado.
    """
    if len(dados) > limite_bytes:
        raise ArquivoInvalido(f"Arquivo maior que o limite de {limite_bytes // (1024 * 1024)} MB.")
    if not dados:
        raise ArquivoInvalido("Arquivo vazio.")
    anon = anonimizador or Anonimizador()
    formato = detectar_formato(dados, nome)
    saida = nome_saida(nome, formato)
    if formato == "txt":
        from .texto import anonimizar_txt
        return anonimizar_txt(dados, anon, saida, verificar=verificar)
    if formato == "csv":
        from .planilha import anonimizar_csv
        return anonimizar_csv(dados, anon, saida, colunas, colunas_integrais, verificar=verificar)
    if formato == "xlsx":
        verificar_zip(dados)
        from .planilha import anonimizar_xlsx
        return anonimizar_xlsx(dados, anon, saida, colunas, colunas_integrais, ocr=ocr, verificar=verificar)
    if formato == "docx":
        verificar_zip(dados)
        from .docx import anonimizar_docx
        return anonimizar_docx(dados, anon, saida, ocr=ocr, verificar=verificar)
    if formato == "pdf":
        from .pdf import anonimizar_pdf
        return anonimizar_pdf(dados, anon, saida, limite_paginas=limite_paginas, ocr=ocr, verificar=verificar,
                              pdfa=pdfa)
    from .imagem import anonimizar_imagem
    return anonimizar_imagem(dados, anon, saida, ocr=ocr, verificar=verificar)
