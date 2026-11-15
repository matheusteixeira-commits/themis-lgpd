"""API HTTP do Themis LGPD.

Proteções aplicadas por padrão:

* limite de tamanho do corpo (HTTP 413), de requisições por cliente (HTTP 429), de análises
  simultâneas e de tempo de processamento (HTTP 503);
* chave de API opcional (cabeçalho ``X-API-Key``), comparada em tempo constante;
* CORS fechado, a menos que origens sejam configuradas, e sem credenciais;
* respostas com ``Cache-Control: no-store`` e cabeçalhos de segurança;
* nenhum conteúdo enviado é devolvido em mensagens de erro nem registrado em log — inclusive pelo
  servidor ASGI, cujos registros de exceção são reduzidos ao tipo do erro (ver :class:`_SemConteudo`);
* nenhum dado é armazenado: textos e arquivos existem apenas em memória durante a requisição.

A configuração é lida de variáveis de ambiente (ver :mod:`themis_lgpd.config`).
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import threading
import time
from collections import defaultdict, deque
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, ValidationError, field_validator
from starlette.concurrency import run_in_threadpool

from .. import __version__, relatorio
from ..catalogo import CATEGORIAS, TIPOS
from ..config import carregar
from ..formatos import ArquivoInvalido, FalhaOCR, VazamentoDetectado, anonimizar_arquivo
from ..motor import Anonimizador
from ..operadores import MODOS
from ..perfis import PERFIL_PADRAO, PERFIS

log = logging.getLogger("themis.api")
CFG = carregar()


class _SemConteudo(logging.Filter):
    """Reduz registros de exceção ao tipo do erro.

    O Starlette relança toda exceção não tratada depois de responder, para que o servidor a registre;
    o uvicorn registra então a mensagem e o rastreamento completos. Mensagens de exceção de
    bibliotecas de terceiros podem citar trechos do documento processado, por isso só o tipo é mantido.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            tipo = record.exc_info[0].__name__ if record.exc_info[0] else "desconhecido"
            record.msg, record.args = "Erro interno (%s)", (tipo,)
            record.exc_info, record.exc_text, record.stack_info = None, None, None
        return True


for _nome in ("uvicorn.error", "uvicorn", "gunicorn.error"):
    logging.getLogger(_nome).addFilter(_SemConteudo())

app = FastAPI(
    title="Themis LGPD",
    version=__version__,
    description="Anonimização de documentos públicos brasileiros (LGPD/LAI). Nada é armazenado.",
    docs_url="/docs" if CFG.docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if CFG.docs else None,
)
if CFG.cors_origens:
    app.add_middleware(CORSMiddleware, allow_origins=list(CFG.cors_origens), allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-API-Key"])

_SEMAFORO = asyncio.Semaphore(max(1, CFG.concorrencia))
_JANELAS: dict[str, deque] = defaultdict(deque)
_TRAVA_JANELAS = threading.Lock()
#: Limite de clientes acompanhados pelo controle de taxa; ao ser atingido, o registro é reiniciado,
#: o que mantém a memória limitada mesmo sob varredura de endereços.
_MAXIMO_CLIENTES = 50_000
#: Tempo máximo de espera por uma vaga de processamento antes de responder 503.
_ESPERA_VAGA_S = 15


# ------------------------------------------------------------------ proteções
def _cliente(request: Request) -> str:
    """Identificação do cliente para o controle de taxa.

    ``X-Forwarded-For`` só é considerado com ``THEMIS_CONFIAR_PROXY``; sem um proxy confiável, o
    cabeçalho seria livremente forjado para contornar o limite.
    """
    if CFG.confiar_proxy:
        encaminhado = request.headers.get("x-forwarded-for", "")
        if encaminhado:
            return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else "?"


@app.middleware("http")
async def protecoes(request: Request, call_next):
    """Limites de tamanho e de taxa, e cabeçalhos de segurança em todas as respostas."""
    limite = CFG.max_mb * 1024 * 1024 + 64 * 1024  # folga para o envelope multipart
    tamanho = request.headers.get("content-length")
    if tamanho and tamanho.isdigit() and int(tamanho) > limite:
        return JSONResponse({"erro": f"Requisição maior que {CFG.max_mb} MB."}, status_code=413)
    if request.method == "POST":
        agora, cliente = time.monotonic(), _cliente(request)
        with _TRAVA_JANELAS:
            janela = _JANELAS[cliente]
            while janela and agora - janela[0] > 60:
                janela.popleft()
            if len(janela) >= CFG.limite_req_minuto:
                return JSONResponse({"erro": "Muitas requisições. Tente novamente em instantes."}, status_code=429,
                                    headers={"Retry-After": "60"})
            janela.append(agora)
            if len(_JANELAS) > _MAXIMO_CLIENTES:
                _JANELAS.clear()
    resposta = await call_next(request)
    resposta.headers["Cache-Control"] = "no-store"
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["Referrer-Policy"] = "no-referrer"
    resposta.headers["X-Frame-Options"] = "DENY"
    if not request.url.path.startswith("/docs"):  # a página /docs precisa carregar seus próprios recursos
        resposta.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return resposta


@app.exception_handler(RequestValidationError)
async def erro_validacao(_request: Request, exc: RequestValidationError):
    """Erro de validação sem o campo ``input`` do Pydantic, que repetiria o texto enviado."""
    erros = [{"campo": ".".join(str(p) for p in e.get("loc", [])), "erro": e.get("msg", "")} for e in exc.errors()]
    return JSONResponse({"erro": "Requisição inválida.", "detalhes": erros}, status_code=422)


@app.exception_handler(HTTPException)
async def erro_http(_request: Request, exc: HTTPException):
    """Erros previstos no mesmo formato das demais respostas de erro: ``{"erro": mensagem}``."""
    return JSONResponse({"erro": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(Exception)
async def erro_generico(_request: Request, exc: Exception):
    """Resposta genérica para erros não previstos; o log registra apenas o tipo."""
    log.error("Erro interno (%s)", type(exc).__name__)
    return JSONResponse({"erro": "Erro interno ao processar."}, status_code=500)


def exigir_chave(request: Request) -> None:
    """Exige ``X-API-Key`` válida quando ``THEMIS_CHAVES_API`` está configurada.

    Raises:
        HTTPException: 401 se a chave estiver ausente ou incorreta.
    """
    if not CFG.chaves_api:
        return
    enviada = request.headers.get("x-api-key", "")
    if not any(hmac.compare_digest(enviada, c) for c in CFG.chaves_api):
        raise HTTPException(status_code=401, detail="Chave de API ausente ou inválida.")


#: Exceções que descrevem o arquivo ou o ambiente e são respondidas ao cliente; não são erros internos.
_ERROS_PREVISTOS = (ArquivoInvalido, VazamentoDetectado, FalhaOCR)


def _liberar(tarefa: asyncio.Future) -> None:
    """Libera a vaga quando a análise termina de fato, inclusive após o tempo limite da resposta.

    A exceção eventual é consumida aqui para que não seja registrada pelo laço de eventos com a
    mensagem completa; erros internos são registrados apenas pelo tipo.
    """
    _SEMAFORO.release()
    if tarefa.cancelled():
        return
    erro = tarefa.exception()
    if erro is not None and not isinstance(erro, _ERROS_PREVISTOS):
        log.error("Erro interno (%s)", type(erro).__name__)


async def _executar(func, *args, **kwargs):
    """Executa uma análise em thread, respeitando o limite de concorrência e o tempo máximo.

    Uma thread não pode ser interrompida: quando o tempo limite é atingido, o cliente recebe 503,
    mas a vaga só é liberada quando a análise termina. Assim, o número de análises em execução nunca
    excede ``THEMIS_CONCORRENCIA``.

    Raises:
        HTTPException: 503 se não houver vaga ou se o tempo limite for atingido; 500 em erro interno.
    """
    try:
        await asyncio.wait_for(_SEMAFORO.acquire(), timeout=_ESPERA_VAGA_S)
    except TimeoutError as erro:
        raise HTTPException(status_code=503, detail="Servidor ocupado. Tente novamente.") from erro
    tarefa = asyncio.ensure_future(run_in_threadpool(func, *args, **kwargs))
    tarefa.add_done_callback(_liberar)
    try:
        return await asyncio.wait_for(asyncio.shield(tarefa), timeout=CFG.timeout_s)
    except TimeoutError as erro:
        raise HTTPException(status_code=503, detail="Tempo de processamento excedido.") from erro
    except _ERROS_PREVISTOS:
        raise
    except Exception as erro:  # noqa: BLE001 - convertido em resposta genérica, sem a mensagem
        raise HTTPException(status_code=500, detail="Erro interno ao processar.") from erro


# ------------------------------------------------------------------ modelos
class Opcoes(BaseModel):
    """Opções de anonimização comuns a todas as rotas."""

    perfil: str = Field(PERFIL_PADRAO, description=f"Um de: {', '.join(PERFIS)}")
    modo: str = Field("etiqueta", description=f"Um de: {', '.join(MODOS)}")
    permitir: list[str] = Field(default_factory=list, max_length=200, description="Termos que nunca são tarjados")
    bloquear: list[str] = Field(default_factory=list, max_length=200, description="Termos sempre tarjados")
    preservar_agentes_publicos: bool = False

    @field_validator("perfil")
    @classmethod
    def _perfil(cls, v: str) -> str:
        if v not in PERFIS:
            raise ValueError(f"perfil inválido; opções: {', '.join(PERFIS)}")
        return v

    @field_validator("modo")
    @classmethod
    def _modo(cls, v: str) -> str:
        # Na demonstração pública, o modo HMAC usaria uma chave do servidor compartilhada entre usuários.
        if v not in MODOS or (CFG.demo and v == "hmac"):
            raise ValueError(f"modo inválido; opções: {', '.join(MODOS)}")
        return v

    @field_validator("permitir", "bloquear")
    @classmethod
    def _termos(cls, v: list[str]) -> list[str]:
        if any(len(t) > 200 for t in v):
            raise ValueError("cada termo deve ter até 200 caracteres")
        return v


class PedidoTexto(Opcoes):
    """Pedido de anonimização ou análise de texto."""

    texto: str = Field(..., min_length=1, max_length=CFG.max_caracteres)
    incluir_valores: bool = Field(False, description="Incluir os valores detectados na resposta")


def _anonimizador(op: Opcoes) -> Anonimizador:
    return Anonimizador(op.perfil, op.modo, permitir=op.permitir, bloquear=op.bloquear,
                        preservar_agentes_publicos=op.preservar_agentes_publicos, usar_ner=CFG.usar_ner,
                        modelo_spacy=CFG.modelo_spacy)


# ------------------------------------------------------------------ rotas
@app.get("/saude")
def saude():
    """Estado do serviço, versão e disponibilidade de OCR."""
    from ..formatos.ocr import ocr_disponivel

    return {"status": "ok", "versao": __version__, "ocr": ocr_disponivel(), "demo": CFG.demo}


@app.get("/v1/perfis")
def listar_perfis():
    """Perfis de anonimização e modos de saída."""
    return {"perfis": [{"nome": p.nome, "titulo": p.titulo, "descricao": p.descricao} for p in PERFIS.values()],
            "modos": MODOS}


@app.get("/v1/tipos")
def listar_tipos():
    """Tipos de dado reconhecidos, com categoria, etiqueta e base legal."""
    return [{"tipo": t.codigo, "nome": t.nome, "categoria": t.categoria, "etiqueta": t.etiqueta,
             "base_legal": CATEGORIAS[t.categoria].base_legal} for t in TIPOS.values()]


@app.post("/v1/anonimizar", dependencies=[Depends(exigir_chave)])
async def anonimizar_texto(pedido: PedidoTexto):
    """Anonimiza um texto e devolve o texto anonimizado, as entidades e a nota de tarjamento."""
    anon = _anonimizador(pedido)
    r = await _executar(anon.anonimizar, pedido.texto)
    corpo = r.para_dict(incluir_valores=pedido.incluir_valores)
    corpo["nota_de_tarjamento"] = relatorio.nota_de_tarjamento([r], "o texto")
    return corpo


@app.post("/v1/analisar", dependencies=[Depends(exigir_chave)])
async def analisar_texto(pedido: PedidoTexto):
    """Lista o que seria tarjado ou sinalizado, sem alterar o texto."""
    anon = _anonimizador(pedido)
    ents = await _executar(anon.analisar, pedido.texto)
    return {"entidades": [e.para_dict(incluir_valor=pedido.incluir_valores) for e in ents]}


@app.post("/v1/arquivos/anonimizar", dependencies=[Depends(exigir_chave)])
async def anonimizar_arquivo_rota(
    arquivo: UploadFile = File(...),
    perfil: str = Form(PERFIL_PADRAO),
    modo: str = Form("etiqueta"),
):
    """Anonimiza um arquivo e devolve o arquivo gerado.

    Os totais e os avisos são informados nos cabeçalhos ``X-Themis-Tarjados``,
    ``X-Themis-Para-Revisar`` e ``X-Themis-Avisos`` (codificado para URL).
    """
    try:
        op = Opcoes(perfil=perfil, modo=modo)
    except ValidationError as erro:
        detalhes = [{"campo": ".".join(str(p) for p in e.get("loc", [])), "erro": e.get("msg", "")}
                    for e in erro.errors()]
        return JSONResponse({"erro": "Requisição inválida.", "detalhes": detalhes}, status_code=422)
    dados = await arquivo.read(CFG.max_mb * 1024 * 1024 + 1)
    if len(dados) > CFG.max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Arquivo maior que {CFG.max_mb} MB.")
    try:
        res = await _executar(anonimizar_arquivo, dados, arquivo.filename or "documento", _anonimizador(op),
                              limite_bytes=CFG.max_mb * 1024 * 1024, limite_paginas=CFG.max_paginas)
    except ArquivoInvalido as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
    except VazamentoDetectado as erro:
        raise HTTPException(status_code=500, detail=str(erro)) from erro
    except FalhaOCR as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    tarjados = sum(len(r.tarjadas) for r in res.resultados)
    alertas = sum(len(r.alertas) for r in res.resultados)
    return Response(res.dados, media_type=res.mime, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(res.nome)}",
        "X-Themis-Tarjados": str(tarjados),
        "X-Themis-Para-Revisar": str(alertas),
        "X-Themis-Avisos": quote(" | ".join(res.avisos))[:4000],
    })
