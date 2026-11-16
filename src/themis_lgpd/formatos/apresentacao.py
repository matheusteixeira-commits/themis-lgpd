"""Anonimização de apresentações PowerPoint (.pptx, e também .pptm, .potx e .ppsx, gravadas como .pptx).

O tratamento é o mesmo dos documentos Word (ver :mod:`themis_lgpd.formatos.docx`): o pacote é
processado no nível do XML, parte por parte.

**Conteúdo analisado e tarjado**: texto de todos os slides, inclusive ocultos, das anotações do
orador, dos slides mestres e layouts, de tabelas, gráficos (com os valores em cache), SmartArt e
formas; texto alternativo e nome de imagens e formas; destinos de hiperlinks externos; texto e QR
codes das imagens (OCR), com tarja nos pixels.

**Conteúdo removido**: comentários e a lista de autores (inclusive os comentários modernos do
Microsoft 365), histórico de alterações e de revisões da coautoria, propriedades do documento e
miniatura, marcas (*tags*) de suplementos, dados XML personalizados, objetos incorporados (OLE,
ActiveX), áudios e vídeos incorporados, macros e assinaturas digitais. O usuário é avisado.

Ao final, todo o texto e todos os atributos do pacote gerado são relidos e comparados com os
valores tarjados.
"""

from __future__ import annotations

from ..motor import Anonimizador
from . import ResultadoArquivo
from .docx import anonimizar_ooxml

#: Relacionamentos removidos do pacote, pelo último segmento do tipo, e a categoria usada nos avisos.
_RELACIONAMENTOS_REMOVER = {
    "extended-properties": None, "custom-properties": None, "thumbnail": None,
    "comments": "comentarios", "commentauthors": None, "authors": None,
    "changesinfo": None, "revisioninfo": None, "tags": None,
    "customxml": None, "printersettings": None, "webextensiontaskpanes": None, "extensibility": None,
    "package": "objetos", "oleobject": "objetos", "control": "objetos", "activexcontrolbinary": "objetos",
    "video": "midia", "audio": "midia", "media": "midia",
    "origin": "assinatura",
    "vbaproject": "macros",
}

_TIPO_APRESENTACAO = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
#: Tipos da parte principal convertidos para apresentação comum (sem macros, não modelo, não exibição).
_TIPOS_PRINCIPAIS = {
    "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml": _TIPO_APRESENTACAO,
    "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml": _TIPO_APRESENTACAO,
    "application/vnd.ms-powerpoint.template.macroEnabled.main+xml": _TIPO_APRESENTACAO,
    "application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml": _TIPO_APRESENTACAO,
    "application/vnd.ms-powerpoint.slideshow.macroEnabled.main+xml": _TIPO_APRESENTACAO,
}


def anonimizar_pptx(dados: bytes, anon: Anonimizador, nome: str, *, ocr: bool = True,
                    verificar: bool = True) -> ResultadoArquivo:
    """Anonimiza uma apresentação PowerPoint.

    Raises:
        ArquivoInvalido: Pacote corrompido, criptografado, no formato Strict ou com XML inválido.
        FalhaOCR: Há imagens a analisar e nenhum mecanismo de OCR está disponível.
        VazamentoDetectado: A verificação encontrou valor tarjado na apresentação gerada.
    """
    return anonimizar_ooxml(dados, anon, nome, formato="pptx", relacionamentos=_RELACIONAMENTOS_REMOVER,
                            tipos_principais=_TIPOS_PRINCIPAIS, ocr=ocr, verificar=verificar)
