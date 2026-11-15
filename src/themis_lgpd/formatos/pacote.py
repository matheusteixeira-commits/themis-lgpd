"""Leitura e gravação de pacotes OPC (Open Packaging Conventions), o contêiner do DOCX e do XLSX.

Um pacote OPC é um arquivo ZIP com partes XML ligadas por relacionamentos (arquivos ``.rels``).
Este módulo oferece as operações de baixo nível usadas pelos formatos Office:

* leitura do ZIP rejeitando entradas duplicadas e criptografadas;
* interpretação de XML endurecida: sem DTD, sem resolução de entidades, sem acesso à rede, com
  comentários e instruções de processamento descartados (eles poderiam carregar texto que nenhum
  editor exibe, mas que permanece no arquivo);
* resolução de relacionamentos e cálculo das partes alcançáveis a partir da raiz, para descartar
  partes órfãs — conteúdo presente no ZIP mas não referenciado pelo documento;
* gravação de um ZIP novo, sem comentário de arquivo, campos extras nem datas originais.
"""

from __future__ import annotations

import io
import posixpath
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from urllib.parse import unquote

from . import ArquivoInvalido

TIPOS_CONTEUDO = "[Content_Types].xml"
NS_RELACIONAMENTOS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_TIPOS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

#: Data gravada em todas as entradas do ZIP gerado; as datas originais revelam quando o documento
#: foi editado e não têm utilidade para o leitor.
_DATA_FIXA = (1980, 1, 1, 0, 0, 0)


def ler_xml(conteudo: bytes):
    """Interpreta uma parte XML com o analisador endurecido.

    Raises:
        ArquivoInvalido: XML malformado ou com declaração de DTD (proibida em OOXML).
    """
    from lxml import etree

    analisador = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False,
                                 remove_comments=True, remove_pis=True)
    try:
        raiz = etree.fromstring(conteudo, analisador)  # noqa: S320 - analisador endurecido acima  # nosec B320
    except etree.XMLSyntaxError as erro:
        raise ArquivoInvalido("O documento contém uma parte XML inválida.") from erro
    if raiz.getroottree().docinfo.doctype:
        raise ArquivoInvalido("O documento contém declaração de DTD, que não é permitida em arquivos Office.")
    return raiz


def gravar_xml(raiz) -> bytes:
    """Serializa uma parte XML em UTF-8, com declaração ``standalone``."""
    from lxml import etree

    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)


def nome_rels(parte: str) -> str:
    """Nome do arquivo de relacionamentos de uma parte (``""`` designa a raiz do pacote)."""
    pasta, arquivo = posixpath.split(parte)
    return posixpath.join(pasta, "_rels", arquivo + ".rels")


def origem_de_rels(nome: str) -> str:
    """Parte de origem de um arquivo de relacionamentos (``""`` para ``_rels/.rels``)."""
    pasta, arquivo = posixpath.split(nome)
    return posixpath.join(posixpath.dirname(pasta), arquivo[: -len(".rels")]).lstrip("/")


def tipo_relacionamento(rel) -> str:
    """Último segmento do tipo de um relacionamento, em minúsculas (ex.: ``comments``)."""
    return (rel.get("Type") or "").rstrip("/").rsplit("/", 1)[-1].lower()


def externo(rel) -> bool:
    """Indica se o relacionamento aponta para fora do pacote (URL ou caminho de arquivo)."""
    return (rel.get("TargetMode") or "").lower() == "external"


@dataclass
class Pacote:
    """Conteúdo de um pacote OPC.

    Attributes:
        partes: Conteúdo de cada parte, pelo nome no ZIP.
        ordem: Ordem original das partes no ZIP.
        relacionamentos: Árvore XML de cada arquivo ``.rels``, pelo nome; editável in loco.
    """

    partes: dict[str, bytes]
    ordem: list[str]
    relacionamentos: dict[str, object] = field(default_factory=dict)

    @classmethod
    def ler(cls, dados: bytes) -> Pacote:
        """Lê o ZIP e interpreta os arquivos de relacionamentos.

        Raises:
            ArquivoInvalido: ZIP corrompido, com entradas duplicadas ou criptografadas.
        """
        try:
            arquivo = zipfile.ZipFile(io.BytesIO(dados))
        except zipfile.BadZipFile as erro:
            raise ArquivoInvalido("Arquivo compactado corrompido.") from erro
        partes: dict[str, bytes] = {}
        ordem: list[str] = []
        with arquivo:
            vistos: set[str] = set()
            for info in arquivo.infolist():
                if info.is_dir():
                    continue
                chave = info.filename.lower()
                if chave in vistos:
                    # Leitores diferentes escolhem entradas diferentes: uma delas poderia escapar à análise.
                    raise ArquivoInvalido("O documento contém partes duplicadas.")
                if info.flag_bits & 0x1:
                    raise ArquivoInvalido("O documento contém partes criptografadas.")
                vistos.add(chave)
                partes[info.filename] = arquivo.read(info)
                ordem.append(info.filename)
        pacote = cls(partes, ordem)
        pacote.relacionamentos = {n: ler_xml(c) for n, c in partes.items() if n.lower().endswith(".rels")}
        return pacote

    def localizar(self, nome: str) -> str | None:
        """Nome real de uma parte; nomes de partes OPC não distinguem maiúsculas de minúsculas."""
        if nome in self.partes:
            return nome
        alvo = nome.lower()
        return next((n for n in self.partes if n.lower() == alvo), None)

    def destino(self, origem: str, rel) -> str | None:
        """Parte interna apontada por um relacionamento, ou ``None`` se externa ou inexistente."""
        if externo(rel):
            return None
        alvo = unquote(rel.get("Target") or "")
        if alvo.startswith("/"):
            caminho = alvo.lstrip("/")
        else:
            caminho = posixpath.normpath(posixpath.join(posixpath.dirname(origem), alvo))
        return self.localizar(caminho)

    def rels_de(self, parte: str):
        """Árvore de relacionamentos de uma parte, ou ``None``."""
        nome = self.localizar(nome_rels(parte))
        return self.relacionamentos.get(nome) if nome else None

    def iterar_relacionamentos(self) -> Iterator[tuple[str, object, object]]:
        """Percorre todos os relacionamentos: ``(parte de origem, árvore .rels, elemento)``."""
        for nome, arvore in self.relacionamentos.items():
            origem = origem_de_rels(nome)
            for rel in list(arvore):
                yield origem, arvore, rel

    def alcancaveis(self) -> set[str]:
        """Partes alcançáveis a partir da raiz seguindo os relacionamentos internos."""
        vistos: set[str] = set()
        pendentes = [""]
        while pendentes:
            origem = pendentes.pop()
            arvore = self.rels_de(origem)
            if arvore is None:
                continue
            for rel in arvore:
                destino = self.destino(origem, rel)
                if destino and destino not in vistos:
                    vistos.add(destino)
                    pendentes.append(destino)
        return vistos

    def gravar(self, manter: set[str], substituir: dict[str, bytes]) -> bytes:
        """Grava um ZIP novo apenas com as partes de ``manter``.

        Os arquivos de relacionamentos são gravados a partir das árvores em :attr:`relacionamentos`,
        que podem ter sido editadas. ``[Content_Types].xml`` é sempre a primeira entrada.
        """
        nomes = [n for n in self.ordem if n in manter]
        nomes.sort(key=lambda n: n != TIPOS_CONTEUDO)
        saida = io.BytesIO()
        with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as arquivo:
            for nome in nomes:
                if nome in substituir:
                    conteudo = substituir[nome]
                elif nome in self.relacionamentos:
                    conteudo = gravar_xml(self.relacionamentos[nome])
                else:
                    conteudo = self.partes[nome]
                info = zipfile.ZipInfo(nome, date_time=_DATA_FIXA)
                info.compress_type = zipfile.ZIP_DEFLATED
                arquivo.writestr(info, conteudo)
        return saida.getvalue()

    def partes_a_manter(self) -> set[str]:
        """Partes alcançáveis, seus arquivos de relacionamentos e ``[Content_Types].xml``."""
        alcancaveis = self.alcancaveis()
        manter = set(alcancaveis)
        for parte in [""] + sorted(alcancaveis):
            nome = self.localizar(nome_rels(parte))
            if nome:
                manter.add(nome)
        if TIPOS_CONTEUDO in self.partes:
            manter.add(TIPOS_CONTEUDO)
        return manter

    def ajustar_tipos(self, manter: set[str], substituicoes: dict[str, str] | None = None) -> bytes:
        """``[Content_Types].xml`` sem as declarações de partes descartadas.

        Args:
            manter: Partes que permanecem no pacote.
            substituicoes: Tipos de conteúdo a trocar (ex.: documento com macros → documento comum).
        """
        raiz = ler_xml(self.partes[TIPOS_CONTEUDO])
        mantidas = {n.lower() for n in manter}
        for el in list(raiz):
            if not isinstance(el.tag, str) or el.tag != f"{{{NS_TIPOS}}}Override":
                continue
            parte = unquote(el.get("PartName") or "").lstrip("/").lower()
            if parte not in mantidas:
                raiz.remove(el)
            elif substituicoes and el.get("ContentType") in substituicoes:
                el.set("ContentType", substituicoes[el.get("ContentType")])
        return gravar_xml(raiz)
