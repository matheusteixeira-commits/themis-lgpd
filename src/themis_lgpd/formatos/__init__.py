"""Anonimização de arquivos.

Formatos: PDF; DOCX, XLSX e PPTX; ODT e ODS; TXT, CSV e HTML; mensagens de e-mail (EML); imagens
PNG, JPEG e TIFF (por OCR); ZIP (cada arquivo pelo seu formato); e, com o LibreOffice instalado,
DOC, XLS, PPT e RTF, convertidos para o formato aberto correspondente.

O formato é identificado pelo conteúdo (assinatura do arquivo), não pela extensão. Cada formato
produz um arquivo novo no mesmo formato — PNG e JPEG são gravados em PNG; formatos antigos do
Office, no formato aberto — e, por padrão, relê o arquivo gerado para confirmar que nenhum valor
tarjado permanece legível (ver :mod:`themis_lgpd.formatos.verificacao`).

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
    "odt": "application/vnd.oasis.opendocument.text",
    "html": "text/html; charset=utf-8",
    "eml": "message/rfc822",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "tiff": "image/tiff",
    "zip": "application/zip",
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
        formato: Formato do arquivo (``pdf``, ``docx``, ``xlsx``, ``pptx``, ``odt``, ``ods``, ``txt``,
            ``csv``, ``html``, ``eml``, ``png``, ``jpg``, ``tiff`` ou ``zip``). Arquivos convertidos
            pelo LibreOffice têm o formato gerado pela conversão.
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
        if "ppt/presentation.xml" in nomes:
            return "pptx"
        if "mimetype" in nomes:
            from .odf import tipo_odf

            tipo = tipo_odf(dados)
            if tipo in {"odt", "ods"}:
                return tipo
            raise ArquivoInvalido("Documento ODF de tipo não suportado: use ODT (texto) ou ODS (planilha).")
        return "zip"
    if cabeca.startswith(b"\xd0\xcf\x11\xe0"):
        from .conversao import tipo_ole

        tipo = tipo_ole(dados)
        if tipo in {"doc", "xls", "ppt"}:
            return tipo
        if tipo == "protegido":
            raise ArquivoInvalido("Documento protegido por senha: remova a senha e tente novamente.")
        if tipo == "msg":
            raise ArquivoInvalido("Mensagens do Outlook (.msg) não são suportadas: salve a mensagem como .eml.")
        raise ArquivoInvalido("Arquivo do Office em formato antigo não identificado: salve-o como .docx, .xlsx ou .pdf.")
    if cabeca.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    if cabeca.startswith((b"GIF87a", b"GIF89a", b"BM")) or (cabeca.startswith(b"RIFF") and dados[8:12] == b"WEBP"):
        raise ArquivoInvalido("Formato de imagem não suportado: converta para PNG, JPEG, TIFF ou PDF.")
    if b"\x00" in dados[:4096]:
        raise ArquivoInvalido("Formato binário não suportado.")
    # Sistemas antigos geram ".doc" que na verdade é RTF ou HTML: o conteúdo decide o formato.
    estruturado = _texto_estruturado(dados)
    if estruturado:
        return estruturado
    # Extensão de formato binário com conteúdo de texto: arquivo corrompido ou renomeado. Processá-lo
    # como texto geraria uma saída com outra extensão, que o usuário poderia não conferir.
    extensao = nome.rsplit(".", 1)[-1] if "." in nome else ""
    if extensao in {"pdf", "docx", "xlsx", "pptx", "odt", "ods", "png", "jpg", "jpeg", "tif", "tiff", "doc", "xls",
                    "ppt", "zip"}:
        raise ArquivoInvalido(f"O conteúdo não corresponde à extensão .{extensao}: o arquivo está corrompido ou "
                              "foi renomeado.")
    return "csv" if nome.endswith(".csv") else "txt"


#: Início de marcação HTML ou XML.
_MARCACAO = re.compile(rb"^<(?:!doctype|\?xml|!--|html\b|[a-z][\w:.-]*(?:\s[^>]*)?/?>)", re.IGNORECASE)
#: Cabeçalhos típicos de mensagem de e-mail (RFC 5322).
_CABECALHO_EMAIL = re.compile(rb"^(?:from|to|cc|subject|date|message-id|mime-version|received|return-path|"
                              rb"content-type|reply-to|x-mailer):", re.IGNORECASE)


def _texto_estruturado(dados: bytes) -> str | None:
    """Identifica formatos de texto com estrutura própria, que não podem ser tratados como texto simples.

    Em HTML, XML e RTF, o conteúdo pode estar codificado (entidades como ``&#46;``, escapes como
    ``\\'e3``) e a marcação se mistura ao texto; em e-mails, o corpo costuma estar em base64. Tratá-los
    como texto simples deixaria dados pessoais sem análise.

    Returns:
        ``html``, ``eml`` ou ``rtf``, que têm tratamento próprio; ``None`` para texto simples.

    Raises:
        ArquivoInvalido: O conteúdo é XML que não é página HTML.
    """
    inicio = dados[:8192].lstrip(b"\xef\xbb\xbf \t\r\n")
    if inicio[:5].lower() == b"{\\rtf":
        return "rtf"
    if _MARCACAO.match(inicio):
        if re.search(rb"<(?:html|body|head|div|p|table|span|br)\b", inicio, re.IGNORECASE) or \
                inicio[:9].lower() == b"<!doctype":
            return "html"
        raise ArquivoInvalido("Arquivos XML não são suportados: salve o conteúdo como PDF, DOCX ou ODT.")
    linhas = inicio.split(b"\n\n", 1)[0].replace(b"\r", b"").split(b"\n")[:40]
    if sum(1 for linha in linhas if _CABECALHO_EMAIL.match(linha)) >= 2:
        return "eml"
    return None


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
    if formato in {"doc", "xls", "ppt", "rtf"}:
        return _anonimizar_convertido(dados, nome, formato, anon, limite_bytes=limite_bytes,
                                      limite_paginas=limite_paginas, ocr=ocr, colunas=colunas,
                                      colunas_integrais=colunas_integrais, verificar=verificar)
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
    if formato == "pptx":
        verificar_zip(dados)
        from .apresentacao import anonimizar_pptx
        return anonimizar_pptx(dados, anon, saida, ocr=ocr, verificar=verificar)
    if formato == "zip":
        from .compactado import anonimizar_zip
        return anonimizar_zip(dados, anon, saida, ocr=ocr, verificar=verificar, limite_paginas=limite_paginas,
                              limite_bytes=limite_bytes, colunas_integrais=colunas_integrais, pdfa=pdfa)
    if formato == "tiff":
        from .imagem import anonimizar_tiff
        return anonimizar_tiff(dados, anon, saida, ocr=ocr, verificar=verificar, limite_paginas=limite_paginas)
    if formato == "pdf":
        from .pdf import anonimizar_pdf
        return anonimizar_pdf(dados, anon, saida, limite_paginas=limite_paginas, ocr=ocr, verificar=verificar,
                              pdfa=pdfa)
    if formato == "eml":
        from .email_eml import anonimizar_eml
        return anonimizar_eml(dados, anon, saida, ocr=ocr, verificar=verificar, limite_paginas=limite_paginas)
    if formato == "html":
        from .html import anonimizar_html
        return anonimizar_html(dados, anon, saida, ocr=ocr, verificar=verificar)
    if formato in {"odt", "ods"}:
        verificar_zip(dados)
        from .odf import anonimizar_odf
        return anonimizar_odf(dados, anon, saida, ocr=ocr, verificar=verificar)
    from .imagem import anonimizar_imagem
    return anonimizar_imagem(dados, anon, saida, ocr=ocr, verificar=verificar)


def _anonimizar_convertido(dados: bytes, nome: str, origem: str, anon: Anonimizador, **opcoes) -> ResultadoArquivo:
    """Converte DOC, XLS, PPT ou RTF pelo LibreOffice e anonimiza o arquivo convertido."""
    from .conversao import DESTINOS, converter

    destino = DESTINOS[origem]
    convertido = converter(dados, origem)
    if detectar_formato(convertido) != destino:
        raise ArquivoInvalido(f"A conversão do arquivo .{origem} não produziu um arquivo .{destino} válido.")
    base = nome.rsplit(".", 1)[0] if "." in (nome or "") else (nome or "documento")
    resultado = anonimizar_arquivo(convertido, f"{base}.{destino}", anon, **opcoes)
    resultado.avisos.insert(0, f"Arquivo .{origem} convertido para .{destino} pelo LibreOffice; o arquivo gerado "
                               f"está no formato .{destino}.")
    return resultado
