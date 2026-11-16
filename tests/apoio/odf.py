"""Documentos ODF (ODT e ODS) mínimos e adversariais para os testes."""

from __future__ import annotations

import io
import zipfile

CABECALHO = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
    'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
    'xmlns:calcext="urn:org:documentfoundation:names:experimental:calc:xmlns:calcext:1.0" '
    'office:version="1.3"'
)


def _jpeg_com_exif(autor: str) -> bytes:
    from PIL import Image

    img = Image.new("RGB", (80, 60), "white")
    exif = Image.Exif()
    exif[0x013B] = autor  # Artist
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    return buf.getvalue()


def pacote(mime: str, conteudo: str, estilos: str = "", extras: dict[str, bytes] | None = None) -> bytes:
    """ODF com conteúdo, estilos, metadados, configurações, miniatura e as partes extras indicadas."""
    extras = extras or {}
    partes = {
        "content.xml": f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {CABECALHO}>'
                       f"<office:body>{conteudo}</office:body></office:document-content>".encode(),
        "styles.xml": f'<?xml version="1.0" encoding="UTF-8"?><office:document-styles {CABECALHO}>'
                      f"{estilos}</office:document-styles>".encode(),
        "meta.xml": f'<?xml version="1.0" encoding="UTF-8"?><office:document-meta {CABECALHO}><office:meta>'
                    "<meta:initial-creator>Beatriz Helena de Souza Matos</meta:initial-creator>"
                    "<dc:creator>Beatriz Helena de Souza Matos</dc:creator><dc:title>Processo de Maria Aparecida "
                    "Souza</dc:title></office:meta></office:document-meta>".encode(),
        "settings.xml": f'<?xml version="1.0" encoding="UTF-8"?><office:document-settings {CABECALHO}>'
                        "<office:settings>Impressora do gabinete de Beatriz Helena</office:settings>"
                        "</office:document-settings>".encode(),
        "Thumbnails/thumbnail.png": b"\x89PNG\r\n\x1a\n" + b"miniatura com Maria Aparecida Souza",
        **extras,
    }
    entradas = "".join(f'<manifest:file-entry manifest:full-path="{n}" manifest:media-type=""/>' for n in partes)
    manifesto = ('<?xml version="1.0" encoding="UTF-8"?><manifest:manifest '
                 'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">'
                 f'<manifest:file-entry manifest:full-path="/" manifest:media-type="{mime}"/>{entradas}'
                 "</manifest:manifest>").encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", mime)
        for nome, dados in partes.items():
            z.writestr(nome, dados)
        z.writestr("META-INF/manifest.xml", manifesto)
    return buf.getvalue()


def odt_adversarial() -> bytes:
    conteudo = (
        "<office:text>"
        "<text:tracked-changes><text:changed-region text:id=\"ct1\"><text:deletion><office:change-info>"
        "<dc:creator>Revisor Carlos Eduardo Lima</dc:creator></office:change-info>"
        "<text:p>CPF anterior 111.444.777-35</text:p></text:deletion></text:changed-region></text:tracked-changes>"
        '<text:p>Requerente: <text:span text:style-name="T1">Maria</text:span> Aparecida<text:s/>Souza, '
        "CPF 529.982.247-25.<text:change text:change-id=\"ct1\"/></text:p>"
        "<text:p>Comentário: <office:annotation><dc:creator>Joana Revisora</dc:creator>"
        "<text:p>conferir CPF 111.444.777-35</text:p></office:annotation>sem pendências.</text:p>"
        '<text:p>Contato: <text:a xlink:href="mailto:joao.silva@gmail.com">clique aqui</text:a> ou '
        "telefone (61) 99999-8888.</text:p>"
        '<text:p><draw:frame draw:name="Foto de Maria Aparecida Souza"><draw:image xlink:href="Pictures/foto.jpg"/>'
        "<svg:title>Assinatura de Maria Aparecida Souza</svg:title></draw:frame></text:p>"
        "</office:text>"
    )
    estilos = ("<office:master-styles><style:master-page style:name=\"Standard\"><style:header>"
               "<text:p>Servidor responsável: João Pereira Lima</text:p></style:header></style:master-page>"
               "</office:master-styles>")
    return pacote("application/vnd.oasis.opendocument.text", conteudo, estilos,
                  {"Pictures/foto.jpg": _jpeg_com_exif("Maria Aparecida Souza")})


def ods_adversarial() -> bytes:
    conteudo = (
        '<office:spreadsheet><table:table table:name="Maria Aparecida Souza">'
        "<table:table-row>"
        '<table:table-cell office:value-type="string"><text:p>Nome</text:p></table:table-cell>'
        '<table:table-cell office:value-type="string"><text:p>CPF</text:p></table:table-cell>'
        '<table:table-cell office:value-type="string"><text:p>Observação</text:p></table:table-cell>'
        "</table:table-row><table:table-row>"
        '<table:table-cell office:value-type="string" office:string-value="João Pereira Lima">'
        "<text:p>João Pereira Lima</text:p></table:table-cell>"
        '<table:table-cell office:value-type="float" office:value="52998224725" calcext:value-type="float">'
        "<text:p>529.982.247-25</text:p></table:table-cell>"
        '<table:table-cell table:formula="of:=CONCATENATE(&quot;Maria Aparecida &quot;;&quot;Souza&quot;)" '
        'office:value-type="string" office:string-value="Maria Aparecida Souza">'
        "<text:p>Maria Aparecida Souza</text:p></table:table-cell>"
        "</table:table-row>"
        '<table:table-row table:number-rows-repeated="3"><table:table-cell table:number-columns-repeated="3"/>'
        "</table:table-row></table:table></office:spreadsheet>"
    )
    return pacote("application/vnd.oasis.opendocument.spreadsheet", conteudo)


def entradas(dados: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        return {n: z.read(n) for n in z.namelist()}
