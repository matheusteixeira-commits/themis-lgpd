"""Anonimização de mensagens de e-mail (``.eml``, RFC 5322 e MIME).

Pedidos de acesso, manifestações e respostas chegam por e-mail. A mensagem é interpretada — corpo
em base64 ou *quoted-printable* decodificado, cabeçalhos com codificação RFC 2047 — e reconstruída:

* **cabeçalhos**: apenas Assunto (anonimizado), Data e os endereços (De, Para, Cc, Responder-para),
  com o nome anonimizado e o endereço substituído por um endereço reservado
  (``tarjado@anonimizado.invalid``, domínio que a RFC 2606 garante inexistente). Rotas de entrega
  (``Received``), identificadores de mensagem, assinaturas DKIM e cabeçalhos ``X-…``, que registram
  endereços IP, servidores e programas, são descartados;
* **corpo**: as partes de texto e HTML (ver :mod:`themis_lgpd.formatos.html`), analisadas com o
  assunto e os nomes dos remetentes no mesmo lote;
* **anexos**: cada anexo é anonimizado pelo próprio formato (PDF, DOCX, planilha, imagem, outra
  mensagem…) e o nome do arquivo é analisado; anexos que não podem ser anonimizados (formato não
  suportado, protegidos por senha) são removidos, com aviso.

A mensagem gerada é relida por inteiro na verificação final.
"""

from __future__ import annotations

import email
import email.policy
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import getaddresses

from ..motor import Anonimizador, Resultado
from . import ArquivoInvalido, FalhaOCR, ResultadoArquivo, VazamentoDetectado
from .verificacao import valores_protegidos, valores_tarjados, verificar_ausencia

ENDERECO_RESERVADO = "tarjado@anonimizado.invalid"
_ENDERECOS = ("From", "To", "Cc", "Reply-To")
#: Profundidade máxima de mensagens anexadas a mensagens.
PROFUNDIDADE_MAXIMA = 3


def anonimizar_eml(dados: bytes, anon: Anonimizador, nome: str, *, ocr: bool = True, verificar: bool = True,
                   limite_paginas: int = 500, profundidade: int = 0) -> ResultadoArquivo:
    """Anonimiza uma mensagem de e-mail (ver a descrição do módulo).

    Raises:
        ArquivoInvalido: Mensagem ilegível ou anexos aninhados além do limite.
        VazamentoDetectado: A verificação encontrou valor tarjado legível na mensagem gerada.
    """
    from . import anonimizar_arquivo
    from .html import anonimizar_html

    if profundidade > PROFUNDIDADE_MAXIMA:
        raise ArquivoInvalido("Mensagens anexadas umas às outras além do limite de profundidade.")
    try:
        original = email.message_from_bytes(dados, policy=email.policy.default)
    except Exception as erro:
        raise ArquivoInvalido("Mensagem de e-mail ilegível.") from erro

    assunto = str(original.get("Subject", "") or "")
    enderecos = {h: getaddresses([str(v) for v in original.get_all(h, [])]) for h in _ENDERECOS}
    textos_corpo, htmls, anexos = [], [], []
    for parte in original.walk():
        if parte.is_multipart():
            continue
        disposicao = parte.get_content_disposition()
        tipo = parte.get_content_type()
        if disposicao != "attachment" and tipo == "text/plain":
            textos_corpo.append(_conteudo_texto(parte))
        elif disposicao != "attachment" and tipo == "text/html":
            htmls.append(_conteudo_texto(parte).encode("utf-8"))
        else:
            anexos.append((parte.get_filename() or "anexo", tipo, parte.get_payload(decode=True) or b""))

    # Assunto, nomes dos correspondentes, corpo e nomes de anexos num único lote.
    nomes_pessoas = [n for lista in enderecos.values() for n, _ in lista if n]
    textos = [assunto, *nomes_pessoas, *textos_corpo, *[a[0] for a in anexos]]
    resultados: list[Resultado] = anon.anonimizar_lote(textos, mesmo_documento=True)
    assunto_anon = resultados[0].texto
    nomes_anon = dict(zip(nomes_pessoas, (r.texto for r in resultados[1:1 + len(nomes_pessoas)])))
    k = 1 + len(nomes_pessoas)
    corpos = [r.texto for r in resultados[k:k + len(textos_corpo)]]
    nomes_anexos = [r.texto for r in resultados[k + len(textos_corpo):]]

    avisos: list[str] = []
    html_gerados = []
    for html in htmls:
        res = anonimizar_html(html, anon, "corpo.html", ocr=ocr, verificar=verificar)
        resultados += res.resultados
        html_gerados.append(res.dados.decode("utf-8"))
    anexos_gerados, removidos = [], []
    for (nome_anexo, tipo, conteudo), nome_anon in zip(anexos, nomes_anexos):
        try:
            if tipo == "message/rfc822" or nome_anexo.lower().endswith(".eml"):
                res = anonimizar_eml(conteudo, anon, nome_anon, ocr=ocr, verificar=verificar,
                                     limite_paginas=limite_paginas, profundidade=profundidade + 1)
            else:
                res = anonimizar_arquivo(conteudo, nome_anexo, anon, ocr=ocr, limite_paginas=limite_paginas,
                                         verificar=verificar)
        except (ArquivoInvalido, FalhaOCR):
            removidos.append(nome_anon)
            continue
        resultados += res.resultados
        extensao = res.nome.rsplit(".", 1)[-1]
        base = nome_anon.rsplit(".", 1)[0] if "." in nome_anon else nome_anon
        anexos_gerados.append((f"{base}.{extensao}", res.mime, res.dados))

    msg = EmailMessage(policy=email.policy.default)
    if assunto:
        msg["Subject"] = assunto_anon
    if original.get("Date"):
        msg["Date"] = str(original["Date"])
    for cabecalho, lista in enderecos.items():
        if lista:
            msg[cabecalho] = [Address(display_name=nomes_anon.get(n, n) if n else "", addr_spec=ENDERECO_RESERVADO)
                              for n, _ in lista]
    msg.set_content("\n\n".join(corpos) if corpos else "")
    for html in html_gerados:
        msg.add_alternative(html, subtype="html")
    for nome_anexo, mime, conteudo in anexos_gerados:
        principal, _, sub = mime.split(";")[0].partition("/")
        msg.add_attachment(conteudo, maintype=principal or "application", subtype=sub or "octet-stream",
                           filename=nome_anexo)
    saida = msg.as_bytes()

    descartados = [h for h in original if h not in ("Subject", "Date", *_ENDERECOS, "MIME-Version",
                                                            "Content-Type", "Content-Transfer-Encoding")]
    if descartados:
        avisos.append(f"{len(descartados)} cabeçalho(s) técnico(s) removido(s) (rotas de entrega, identificadores, "
                      "assinaturas e programas, que registram endereços IP e servidores).")
    if any(lista for lista in enderecos.values()):
        avisos.append(f"Endereços de e-mail substituídos por {ENDERECO_RESERVADO}.")
    if anexos_gerados:
        avisos.append(f"{len(anexos_gerados)} anexo(s) anonimizado(s).")
    if removidos:
        avisos.append(f"{len(removidos)} anexo(s) removido(s): formato não suportado, protegido por senha ou sem OCR "
                      "disponível.")
    if verificar:
        _verificar(saida, resultados, anon)
    return ResultadoArquivo(saida, "eml", nome, resultados, avisos)


def _conteudo_texto(parte) -> str:
    try:
        return parte.get_content()
    except (LookupError, UnicodeDecodeError):
        return (parte.get_payload(decode=True) or b"").decode("cp1252", errors="replace")


def texto_eml(dados: bytes) -> str:
    """Cabeçalhos, partes de texto e HTML e nomes de anexos da mensagem (verificação final)."""
    from .html import texto_html

    msg = email.message_from_bytes(dados, policy=email.policy.default)
    partes = [f"{k}: {v}" for k, v in msg.items()]
    for parte in msg.walk():
        if parte.is_multipart():
            continue
        tipo = parte.get_content_type()
        if parte.get_filename():
            partes.append(parte.get_filename())
        if parte.get_content_disposition() == "attachment":
            continue
        if tipo == "text/plain":
            partes.append(_conteudo_texto(parte))
        elif tipo == "text/html":
            partes.append(texto_html(_conteudo_texto(parte).encode("utf-8")))
    return "\n".join(partes)


def _verificar(saida: bytes, resultados, anon: Anonimizador) -> None:
    sobras = verificar_ausencia(texto_eml(saida), valores_tarjados(resultados),
                                valores_protegidos(resultados, anon.permitir))
    if sobras:
        raise VazamentoDetectado(f"{len(sobras)} trecho(s) tarjado(s) ainda legível(is) na mensagem gerada.")
