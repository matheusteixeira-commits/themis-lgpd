"""ODT e ODS (padrão e-PING): mesma bateria adversarial de DOCX e XLSX."""

import io
import zipfile

import pytest

from apoio import odf
from themis_lgpd.formatos import anonimizar_arquivo, detectar_formato
from themis_lgpd.formatos.midia import metadados_restantes

PROIBIDOS = ["529.982.247-25", "52998224725", "111.444.777-35", "Maria", "Aparecida", "Joana Revisora",
             "Carlos Eduardo", "Beatriz Helena", "João Pereira", "joao.silva", "99999-8888"]


def _sem_proibidos(dados: bytes) -> None:
    for nome, conteudo in odf.entradas(dados).items():
        texto = conteudo.decode("utf-8", "ignore")
        for p in PROIBIDOS:
            assert p not in texto, f"{p!r} em {nome}"


@pytest.fixture(scope="module")
def odt(anon_modulo):
    return anonimizar_arquivo(odf.odt_adversarial(), "processo.odt", anon_modulo, ocr=False)


@pytest.fixture(scope="module")
def ods(anon_modulo):
    return anonimizar_arquivo(odf.ods_adversarial(), "planilha.ods", anon_modulo, ocr=False)


@pytest.fixture(scope="module")
def anon_modulo():
    from themis_lgpd import Anonimizador

    return Anonimizador("lai")


def test_formato_detectado():
    assert detectar_formato(odf.odt_adversarial(), "x.odt") == "odt"
    assert detectar_formato(odf.ods_adversarial(), "x.ods") == "ods"


def test_odt_nada_vaza(odt):
    assert odt.formato == "odt" and odt.nome.endswith(".odt")
    _sem_proibidos(odt.dados)


def test_odt_texto_dividido_em_trechos_e_cabecalho(odt):
    partes = odf.entradas(odt.dados)
    conteudo = partes["content.xml"].decode()
    assert "[NOME]" in conteudo and "[CPF]" in conteudo and "Requerente:" in conteudo
    assert "sem pendências." in conteudo  # texto após o comentário removido é preservado
    assert "[NOME]" in partes["styles.xml"].decode()


def test_odt_remove_comentarios_alteracoes_metadados_e_miniatura(odt):
    partes = odf.entradas(odt.dados)
    conteudo = partes["content.xml"].decode()
    assert "annotation" not in conteudo and "tracked-changes" not in conteudo and "text:change" not in conteudo
    assert "Thumbnails/thumbnail.png" not in partes and "settings.xml" not in partes
    assert b"generator>Themis LGPD" in partes["meta.xml"] and b"creator" not in partes["meta.xml"]
    manifesto = partes["META-INF/manifest.xml"].decode()
    assert "thumbnail" not in manifesto and "settings.xml" not in manifesto
    assert {"comentário", "alteração"} <= {p for a in odt.avisos for p in ("comentário", "alteração") if p in a}


def test_odt_link_com_dado_pessoal_neutralizado(odt):
    conteudo = odf.entradas(odt.dados)["content.xml"].decode()
    assert 'xlink:href="#"' in conteudo and "clique aqui" in conteudo


def test_odt_imagem_sem_metadados(odt):
    foto = odf.entradas(odt.dados)["Pictures/foto.jpg"]
    assert metadados_restantes(foto) == []


def test_pacote_valido_mimetype_primeiro_sem_compressao(odt, ods):
    for res in (odt, ods):
        with zipfile.ZipFile(io.BytesIO(res.dados)) as z:
            primeira = z.infolist()[0]
            assert primeira.filename == "mimetype" and primeira.compress_type == zipfile.ZIP_STORED
            assert z.testzip() is None


def test_ods_nada_vaza(ods):
    assert ods.formato == "ods"
    _sem_proibidos(ods.dados)


def test_ods_valor_e_formula_da_celula_removidos(ods):
    conteudo = odf.entradas(ods.dados)["content.xml"].decode()
    assert "office:value=" not in conteudo and "table:formula" not in conteudo
    assert 'table:number-columns-repeated="3"' in conteudo  # estrutura preservada


def test_odf_protegido_por_senha_e_recusado():
    from themis_lgpd.formatos import ArquivoInvalido

    dados = odf.pacote("application/vnd.oasis.opendocument.text", "<office:text/>")
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        partes = {n: z.read(n) for n in z.namelist()}
    partes["META-INF/manifest.xml"] = partes["META-INF/manifest.xml"].replace(
        b"</manifest:manifest>", b"<manifest:encryption-data/></manifest:manifest>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, d in partes.items():
            z.writestr(n, d)
    with pytest.raises(ArquivoInvalido, match="senha"):
        anonimizar_arquivo(buf.getvalue(), "x.odt")
