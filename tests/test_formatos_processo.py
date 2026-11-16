"""ZIP de processo, TIFF de digitalizadora, apresentações PPTX e formatos antigos (via LibreOffice)."""

import hashlib
import io
import json
import os
import subprocess  # nosec B404
import zipfile
from pathlib import Path

import pytest

from apoio.odf import _jpeg_com_exif
from themis_lgpd.formatos import ArquivoInvalido, VazamentoDetectado, anonimizar_arquivo, detectar_formato
from themis_lgpd.formatos.midia import metadados_restantes
from themis_lgpd.formatos.verificacao import imagens_com_metadados, texto_de_pacote

EXEMPLOS = Path(__file__).parents[1] / "exemplos"
REQUERIMENTO = "Requerente: Maria Aparecida Souza, CPF 529.982.247-25, telefone (61) 99999-8888."
PROIBIDOS = ["529.982.247-25", "111.444.777-35", "Maria", "Aparecida", "João Pereira", "Joao Pereira", "99999-8888",
             "joao.silva", "Carlos Eduardo", "Beatriz Helena"]


def _sem_proibidos(texto: str) -> None:
    for p in PROIBIDOS:
        assert p not in texto, p


# ---------------------------------------------------------------------------- ZIP de processo
def _marcar_criptografado(dados: bytes, nome: str) -> bytes:
    """Liga o bit de criptografia da entrada (cabeçalho local e diretório central)."""
    dados, alvo = bytearray(dados), nome.encode()
    inicio = dados.find(alvo)
    while inicio >= 0:
        if dados[inicio - 30:inicio - 26] == b"PK\x03\x04":
            dados[inicio - 24] |= 0x1
        elif dados[inicio - 46:inicio - 42] == b"PK\x01\x02":
            dados[inicio - 38] |= 0x1
        inicio = dados.find(alvo, inicio + 1)
    return bytes(dados)


def _zip_processo() -> bytes:
    interno = io.BytesIO()
    with zipfile.ZipFile(interno, "w") as z:
        z.writestr("nota.txt", "Contato do interessado: joao.silva@gmail.com")
    laudo = ("<html><body><p>Laudo de João Pereira Lima, CPF 111.444.777-35.</p></body></html>").encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.comment = b"Exportado por Carlos Eduardo Lima"
        z.writestr("Processo de acesso/01 - Requerimento de Maria Aparecida Souza.txt", REQUERIMENTO)
        z.writestr("Processo de acesso/02 - Oficio.docx", (EXEMPLOS / "oficio_ficticio.docx").read_bytes())
        z.writestr("Processo de acesso/03 - Despacho.pdf", (EXEMPLOS / "despacho_ficticio.pdf").read_bytes())
        z.writestr("Processo de acesso/anexos/Laudo_Joao_Pereira_Lima.html", laudo)
        z.writestr("Processo de acesso/anexos/complemento.zip", interno.getvalue())
        z.writestr("Processo de acesso/DeclaraXXo de JoXo Pereira Lima.txt", "Declaro que recebi a cópia.")
        z.writestr("Processo de acesso/programa.exe", b"MZ\x90\x00" + b"\x00" * 200)
        z.writestr("Processo de acesso/protegido.pdf", b"%PDF-1.7 conteudo cifrado")
        z.writestr("Processo de acesso/Thumbs.db", b"\x00miniaturas")
        z.writestr("__MACOSX/Processo de acesso/._02 - Oficio.docx", b"\x00\x05\x16\x07")
        z.writestr("../../fora.txt", "Texto sem dados pessoais.")
    dados = buf.getvalue().replace(b"DeclaraXXo de JoXo", "Declaração de João".encode("cp850"))
    return _marcar_criptografado(dados, "Processo de acesso/protegido.pdf")


@pytest.fixture(scope="module")
def processo(anon):
    return anonimizar_arquivo(_zip_processo(), "processo.zip", anon, ocr=False)


def test_zip_detectado():
    assert detectar_formato(_zip_processo(), "processo.zip") == "zip"


def test_zip_nomes_tarjados_e_estrutura(processo):
    with zipfile.ZipFile(io.BytesIO(processo.dados)) as z:
        nomes = z.namelist()
        assert z.comment == b""
        assert {i.date_time for i in z.infolist()} == {(1980, 1, 1, 0, 0, 0)}
    assert processo.formato == "zip" and processo.nome.endswith(".zip")
    _sem_proibidos("\n".join(nomes))
    assert "Processo de acesso/01 - Requerimento de [NOME].txt" in nomes
    assert "Processo de acesso/02 - Oficio.docx" in nomes and "Processo de acesso/03 - Despacho.pdf" in nomes
    assert "Processo de acesso/anexos/Laudo [NOME].html" in nomes
    assert "Processo de acesso/Declaração de [NOME].txt" in nomes  # nome em CP850 decodificado e analisado
    assert "fora.txt" in nomes and not any(".." in n or n.startswith("/") for n in nomes)
    assert not any("MACOSX" in n or "Thumbs" in n or n.endswith((".exe", "protegido.pdf")) for n in nomes)


def test_zip_conteudo_anonimizado(processo):
    with zipfile.ZipFile(io.BytesIO(processo.dados)) as z:
        requerimento = z.read("Processo de acesso/01 - Requerimento de [NOME].txt").decode("utf-8")
        laudo = z.read("Processo de acesso/anexos/Laudo [NOME].html").decode("utf-8")
        docx = z.read("Processo de acesso/02 - Oficio.docx")
        with zipfile.ZipFile(io.BytesIO(z.read("Processo de acesso/anexos/complemento.zip"))) as interno:
            nota = interno.read("nota.txt").decode("utf-8")
            assert "manifesto_anonimizacao.json" in interno.namelist()
    for texto in (requerimento, laudo, nota, texto_de_pacote(docx)):
        _sem_proibidos(texto)
    assert "[CPF]" in requerimento and "[CPF]" in laudo and "[E-MAIL]" in nota


def test_zip_manifesto(processo):
    with zipfile.ZipFile(io.BytesIO(processo.dados)) as z:
        texto = z.read("manifesto_anonimizacao.json").decode("utf-8")
    _sem_proibidos(texto)
    manifesto = json.loads(texto)
    por_arquivo = {linha["arquivo"]: linha for linha in manifesto["arquivos"]}
    assert len(por_arquivo) == 9 and manifesto["perfil"] == "lai"
    requerimento = por_arquivo["Processo de acesso/01 - Requerimento de [NOME].txt"]
    assert requerimento["situacao"] == "anonimizado"
    assert requerimento["sha256_entrada"] == hashlib.sha256(REQUERIMENTO.encode()).hexdigest()
    assert requerimento["por_tipo"]["CPF"] == 1 and requerimento["sha256_saida"]
    assert por_arquivo["Processo de acesso/programa.exe"]["situacao"] == "removido"
    assert por_arquivo["Processo de acesso/protegido.pdf"]["motivo"] == "protegido por senha"
    assert any("removido" in a for a in processo.avisos)


def test_zip_verifica_nomes(anon, monkeypatch):
    """Um nome de arquivo que escape da análise interrompe a operação."""
    from themis_lgpd.formatos import compactado

    original = compactado._nomes_de_saida

    def sem_tarja(entradas, anonimizador, resultados):
        nomes = original(entradas, anonimizador, resultados)
        nomes.nomes = ["/".join(e.componentes) for e in entradas]
        return nomes

    monkeypatch.setattr(compactado, "_nomes_de_saida", sem_tarja)
    with pytest.raises(VazamentoDetectado):
        anonimizar_arquivo(_zip_processo(), "processo.zip", anon, ocr=False)


def test_zip_aninhado_alem_do_limite(anon):
    dados = b"conteudo"
    for nivel in range(6):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(f"nivel{nivel}.zip" if nivel else "a.txt", dados)
        dados = buf.getvalue()
    dados = anonimizar_arquivo(dados, "aninhado.zip", anon, ocr=False).dados
    niveis = 0
    while True:
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            linha = json.loads(z.read("manifesto_anonimizacao.json"))["arquivos"][0]
            if linha["situacao"] != "anonimizado":
                break
            dados, niveis = z.read(linha["arquivo"]), niveis + 1
    assert linha["situacao"] == "removido" and "profundidade" in linha["motivo"] and niveis == 3


# ---------------------------------------------------------------------------- TIFF
def _tiff(paginas: list[list[str]]) -> bytes:
    import reportlab
    from PIL import Image, ImageDraw, ImageFont, TiffImagePlugin

    fonte = ImageFont.truetype(str(Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"), 44)
    imagens = []
    for linhas in paginas:
        img = Image.new("L", (1700, 120 + 90 * len(linhas)), 255)
        desenho = ImageDraw.Draw(img)
        for i, linha in enumerate(linhas):
            desenho.text((60, 60 + 90 * i), linha, fill=0, font=fonte)
        imagens.append(img.convert("1"))
    etiquetas = TiffImagePlugin.ImageFileDirectory_v2()
    etiquetas[315] = "Beatriz Helena"  # Artist
    etiquetas[270] = "Digitalizado por Carlos Eduardo Lima"  # ImageDescription
    etiquetas[305] = "Digitalizadora do protocolo"  # Software
    buf = io.BytesIO()
    imagens[0].save(buf, "TIFF", save_all=True, append_images=imagens[1:], compression="group4", dpi=(200, 200),
                    tiffinfo=etiquetas)
    return buf.getvalue()


@pytest.mark.lento
def test_tiff_multipagina(anon):
    from PIL import Image, ImageSequence

    from themis_lgpd.formatos.ocr import ocr_disponivel, reconhecer

    if not ocr_disponivel():
        pytest.skip("OCR indisponível")
    entrada = _tiff([["Requerente: Maria Aparecida Souza", "CPF 529.982.247-25"],
                     ["Telefone (61) 99999-8888", "Solicita copia do processo."]])
    assert metadados_restantes(entrada)  # a entrada tem autor, descrição e programa
    assert detectar_formato(entrada, "digitalizado.tif") == "tiff"
    res = anonimizar_arquivo(entrada, "digitalizado.tif", anon)
    assert res.formato == "tiff" and res.nome.endswith(".tiff") and res.mime == "image/tiff"
    assert metadados_restantes(res.dados) == []
    with Image.open(io.BytesIO(res.dados)) as img:
        assert img.n_frames == 2 and img.info["compression"] == "group4"
        assert round(img.info["dpi"][0]) == 200
        paginas = [p.copy() for p in ImageSequence.Iterator(img)]
    assert all(p.mode == "1" for p in paginas)
    relido = " ".join(w.texto for p in paginas for w in reconhecer(p.convert("RGB")))
    for proibido in ("Maria", "Souza", "529", "247", "99999"):
        assert proibido not in relido, relido
    assert "processo" in relido


# ---------------------------------------------------------------------------- PPTX
def _com_comentario_e_marcas(dados: bytes) -> bytes:
    """Acrescenta comentário (com autor), marcas de suplemento e um vídeo à apresentação."""
    p = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    extras = {
        "ppt/commentAuthors.xml": f'<p:cmAuthorLst {p}><p:cmAuthor id="0" name="Carlos Eduardo Lima" initials="CEL" '
                                  'lastIdx="1" clrIdx="0"/></p:cmAuthorLst>',
        "ppt/comments/comment1.xml": f'<p:cmLst {p}><p:cm authorId="0" dt="2026-01-01T10:00:00.000" idx="1">'
                                     '<p:pos x="10" y="10"/><p:text>Conferir o CPF 111.444.777-35</p:text></p:cm>'
                                     "</p:cmLst>",
        "ppt/tags/tag1.xml": f'<p:tagLst {p}><p:tag name="RESPONSAVEL" val="Beatriz Helena Duarte"/></p:tagLst>',
        "ppt/media/gravacao.mp4": b"\x00\x00\x00\x18ftypmp42 audio de Maria Aparecida Souza",
    }
    tipos = {
        "/ppt/commentAuthors.xml": "application/vnd.openxmlformats-officedocument.presentationml.commentAuthors+xml",
        "/ppt/comments/comment1.xml": "application/vnd.openxmlformats-officedocument.presentationml.comments+xml",
        "/ppt/tags/tag1.xml": "application/vnd.openxmlformats-officedocument.presentationml.tags+xml",
    }
    origem = zipfile.ZipFile(io.BytesIO(dados))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for info in origem.infolist():
            conteudo = origem.read(info)
            if info.filename == "[Content_Types].xml":
                sobrepor = "".join(f'<Override PartName="{n}" ContentType="{t}"/>' for n, t in tipos.items())
                conteudo = conteudo.replace(b"</Types>", f'<Default Extension="mp4" ContentType="video/mp4"/>'
                                            f"{sobrepor}</Types>".encode())
            elif info.filename == "ppt/_rels/presentation.xml.rels":
                conteudo = conteudo.replace(b"</Relationships>", f'<Relationship Id="rId900" Type="{rel}/commentAuthors"'
                                            ' Target="commentAuthors.xml"/></Relationships>'.encode())
            elif info.filename == "ppt/slides/_rels/slide1.xml.rels":
                conteudo = conteudo.replace(b"</Relationships>", (
                    f'<Relationship Id="rId901" Type="{rel}/comments" Target="../comments/comment1.xml"/>'
                    f'<Relationship Id="rId902" Type="{rel}/tags" Target="../tags/tag1.xml"/>'
                    f'<Relationship Id="rId903" Type="{rel}/video" Target="../media/gravacao.mp4"/>'
                    "</Relationships>").encode())
            z.writestr(info, conteudo)
        for nome, conteudo in extras.items():
            z.writestr(nome, conteudo)
    return buf.getvalue()


def _pptx() -> bytes:
    from pptx import Presentation
    from pptx.util import Inches

    apresentacao = Presentation()
    apresentacao.core_properties.author = "Beatriz Helena Duarte"
    apresentacao.core_properties.last_modified_by = "Carlos Eduardo Lima"
    apresentacao.core_properties.title = "Caso de Maria Aparecida Souza"
    slide = apresentacao.slides.add_slide(apresentacao.slide_layouts[1])
    slide.shapes.title.text = "Despacho"
    slide.placeholders[1].text = "Requerente: Maria Aparecida Souza, CPF 529.982.247-25."
    slide.notes_slide.notes_text_frame.text = "Ligar para João Pereira Lima no telefone (61) 99999-8888."
    caixa = slide.shapes.add_textbox(Inches(1), Inches(6), Inches(6), Inches(1))
    trecho = caixa.text_frame.paragraphs[0].add_run()
    trecho.text = "Fale com o interessado"
    trecho.hyperlink.address = "mailto:joao.silva@gmail.com"
    foto = slide.shapes.add_picture(io.BytesIO(_jpeg_com_exif("Maria Aparecida Souza")), Inches(7), Inches(1))
    foto._element.nvPicPr.cNvPr.set("descr", "Foto de Maria Aparecida Souza")
    oculto = apresentacao.slides.add_slide(apresentacao.slide_layouts[5])
    oculto.shapes.title.text = "Rascunho de Carlos Eduardo Lima"
    oculto._element.set("show", "0")
    buf = io.BytesIO()
    apresentacao.save(buf)
    return _com_comentario_e_marcas(buf.getvalue())


@pytest.fixture(scope="module")
def apresentacao(anon):
    return anonimizar_arquivo(_pptx(), "apresentacao.pptx", anon, ocr=False)


def test_pptx_detectado():
    assert detectar_formato(_pptx(), "apresentacao.pptx") == "pptx"


def test_pptx_nada_vaza(apresentacao):
    _sem_proibidos(texto_de_pacote(apresentacao.dados))
    assert imagens_com_metadados(apresentacao.dados) == []
    with zipfile.ZipFile(io.BytesIO(apresentacao.dados)) as z:
        nomes = z.namelist()
    assert not any("comment" in n.lower() or "/tags/" in n or n.endswith(".mp4") or "app.xml" in n for n in nomes)


def test_pptx_abre_e_mantem_estrutura(apresentacao):
    from pptx import Presentation

    resultado = Presentation(io.BytesIO(apresentacao.dados))
    slides = list(resultado.slides)
    assert len(slides) == 2 and slides[1]._element.get("show") == "0"
    corpo = slides[0].placeholders[1].text
    assert "[NOME]" in corpo and "[CPF]" in corpo
    assert "[NOME]" in slides[0].notes_slide.notes_text_frame.text
    assert not resultado.core_properties.author and not resultado.core_properties.title
    assert apresentacao.formato == "pptx" and apresentacao.nome.endswith(".pptx")
    assert any("comentário" in a for a in apresentacao.avisos)
    assert any("vídeo" in a for a in apresentacao.avisos)


# ---------------------------------------------------------------------------- formatos antigos
_RTF = (rb"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0 Arial;}}\f0\fs24 Requerente: Jo\'e3o Pereira Lima, "
        rb"CPF 529.982.247-25.\par Solicita c\'f3pia do processo.\par}")


def _ole(fluxo: str) -> bytes:
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 504 + fluxo.encode("utf-16-le") + b"\x00" * 66


def test_formatos_antigos_identificados_pelo_conteudo():
    assert detectar_formato(_RTF, "requerimento.rtf") == "rtf"
    assert detectar_formato(_RTF, "requerimento.doc") == "rtf"  # ".doc" gerado como RTF por sistemas antigos
    assert detectar_formato(_ole("WordDocument"), "a.doc") == "doc"
    assert detectar_formato(_ole("Workbook"), "a.xls") == "xls"
    assert detectar_formato(_ole("PowerPoint Document"), "a.ppt") == "ppt"
    with pytest.raises(ArquivoInvalido, match="senha"):
        detectar_formato(_ole("EncryptedPackage"), "a.docx")
    with pytest.raises(ArquivoInvalido, match=r"\.msg"):
        detectar_formato(_ole("__substg1.0_0037001F"), "a.msg")


def test_sem_libreoffice_recusa_com_orientacao(anon, tmp_path, monkeypatch):
    monkeypatch.setenv("THEMIS_SOFFICE", str(tmp_path / "inexistente"))
    with pytest.raises(ArquivoInvalido, match="LibreOffice"):
        anonimizar_arquivo(_RTF, "requerimento.rtf", anon)


def test_convertido_passa_pelo_formato_de_destino(anon, monkeypatch):
    from themis_lgpd.formatos import conversao

    monkeypatch.setattr(conversao, "converter", lambda dados, origem: (EXEMPLOS / "oficio_ficticio.docx").read_bytes())
    res = anonimizar_arquivo(_ole("WordDocument"), "oficio.doc", anon, ocr=False)
    assert res.formato == "docx" and res.nome == "oficio_anonimizado.docx"
    assert res.avisos[0].startswith("Arquivo .doc convertido para .docx")
    assert "João Pereira" not in texto_de_pacote(res.dados)


def _soffice() -> str:
    from themis_lgpd.formatos.conversao import localizar_soffice

    caminho = localizar_soffice()
    if caminho is None:
        if os.environ.get("THEMIS_EXIGIR_LIBREOFFICE"):
            pytest.fail("LibreOffice exigido neste ambiente e não encontrado")
        pytest.skip("LibreOffice não instalado")
    return caminho


def _converter_para(soffice: str, dados: bytes, origem: str, destino: str, pasta: Path) -> bytes:
    pasta.mkdir(parents=True)
    entrada = pasta / f"entrada.{origem}"
    entrada.write_bytes(dados)
    subprocess.run([soffice, f"-env:UserInstallation={(pasta / 'perfil').as_uri()}", "--headless",  # noqa: S603
                    "--convert-to", destino, "--outdir", str(pasta / "saida"), str(entrada)],
                   check=True, timeout=180, capture_output=True)
    return (pasta / "saida" / f"entrada.{destino}").read_bytes()


@pytest.mark.lento
def test_libreoffice_rtf_doc_xls_ppt(anon, tmp_path):
    import openpyxl

    soffice = _soffice()
    res = anonimizar_arquivo(_RTF, "requerimento.rtf", anon, ocr=False)
    texto = texto_de_pacote(res.dados)
    assert res.formato == "docx" and "[CPF]" in texto and "cópia" in texto
    _sem_proibidos(texto)

    doc = _converter_para(soffice, (EXEMPLOS / "oficio_ficticio.docx").read_bytes(), "docx", "doc", tmp_path / "d")
    assert detectar_formato(doc, "oficio.doc") == "doc"
    res = anonimizar_arquivo(doc, "oficio.doc", anon, ocr=False)
    assert res.formato == "docx"
    _sem_proibidos(texto_de_pacote(res.dados))

    livro = openpyxl.Workbook()
    livro.active.append(["Nome", "CPF"])
    livro.active.append(["Maria Aparecida Souza", "529.982.247-25"])
    buf = io.BytesIO()
    livro.save(buf)
    xls = _converter_para(soffice, buf.getvalue(), "xlsx", "xls", tmp_path / "x")
    assert detectar_formato(xls, "planilha.xls") == "xls"
    res = anonimizar_arquivo(xls, "planilha.xls", anon, ocr=False)
    assert res.formato == "xlsx"
    _sem_proibidos(texto_de_pacote(res.dados))

    ppt = _converter_para(soffice, _pptx(), "pptx", "ppt", tmp_path / "p")
    assert detectar_formato(ppt, "apresentacao.ppt") == "ppt"
    res = anonimizar_arquivo(ppt, "apresentacao.ppt", anon, ocr=False)
    assert res.formato == "pptx"
    _sem_proibidos(texto_de_pacote(res.dados))
