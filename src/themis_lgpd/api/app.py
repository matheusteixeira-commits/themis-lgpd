"""API HTTP do Themis LGPD.

Proteções aplicadas por padrão:

* limite de tamanho do corpo (HTTP 413), de requisições por cliente (HTTP 429), de análises
  simultâneas e de tempo de processamento (HTTP 503);
* chave de API opcional (cabeçalho ``X-API-Key``), comparada em tempo constante;
* CORS fechado, a menos que origens sejam configuradas, e sem credenciais;
* respostas com ``Cache-Control: no-store`` e cabeçalhos de segurança;
* nenhum conteúdo enviado é devolvido em mensagens de erro nem registrado em log — inclusive pelo
  servidor ASGI, cujos registros de exceção são reduzidos ao tipo do erro (ver :class:`_SemConteudo`);
* nenhum dado é gravado em disco: textos e arquivos existem apenas em memória durante a requisição;
  o resultado de uma tarefa assíncrona fica em memória até o download ou até expirar
  (``THEMIS_TAREFA_TTL_S``) e só pode ser obtido com a mesma chave de API que criou a tarefa.

A configuração é lida de variáveis de ambiente (ver :mod:`themis_lgpd.config`); a configuração do
órgão (perfis, listas, reconhecedores próprios), de ``THEMIS_CONFIG`` (ver
:mod:`themis_lgpd.configuracao`). Com ``THEMIS_PROCESSOS`` maior que 1, as análises são distribuídas
entre processos de trabalho (ver :mod:`themis_lgpd.api.trabalho`).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import multiprocessing
import secrets
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import partial
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
from ..formatos import ArquivoInvalido, FalhaOCR, ResultadoArquivo, VazamentoDetectado
from ..operadores import MODOS
from ..perfis import PERFIS
from . import trabalho

log = logging.getLogger("themis.api")
CFG = carregar()
#: Configuração do órgão; um erro nela impede o início do serviço (falhar fechado).
trabalho.orgao.cache_clear()  # releitura a cada carga do módulo; os processos de trabalho leem a sua
ORGAO = trabalho.orgao()


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
    description="Anonimização de documentos públicos brasileiros (LGPD/LAI). Nada é gravado em disco.",
    docs_url="/docs" if CFG.docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if CFG.docs else None,
)
if CFG.cors_origens:
    app.add_middleware(CORSMiddleware, allow_origins=list(CFG.cors_origens), allow_credentials=False,
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type", "X-API-Key"])

_SEMAFORO = asyncio.Semaphore(max(1, CFG.concorrencia, CFG.processos))
_JANELAS: dict[str, deque] = defaultdict(deque)
_TRAVA_JANELAS = threading.Lock()
#: Limite de clientes acompanhados pelo controle de taxa; ao ser atingido, o registro é reiniciado,
#: o que mantém a memória limitada mesmo sob varredura de endereços.
_MAXIMO_CLIENTES = 50_000
#: Tempo máximo de espera por uma vaga de processamento antes de responder 503.
_ESPERA_VAGA_S = 15
_POOL: ProcessPoolExecutor | None = None


def _pool() -> ProcessPoolExecutor | None:
    """Processos de análise, criados no primeiro uso (``THEMIS_PROCESSOS`` > 1).

    Iniciados por "spawn" em todas as plataformas: o servidor já tem threads em execução, que um
    "fork" copiaria em estado inconsistente.
    """
    global _POOL
    if CFG.processos > 1 and _POOL is None:
        _POOL = ProcessPoolExecutor(max_workers=CFG.processos, mp_context=multiprocessing.get_context("spawn"))
    return _POOL


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


def _detalhes(erros: list) -> list[dict]:
    """Erros de validação sem o campo ``input`` do Pydantic, que repetiria o conteúdo enviado."""
    return [{"campo": ".".join(str(p) for p in e.get("loc", [])), "erro": e.get("msg", "")} for e in erros]


@app.exception_handler(RequestValidationError)
async def erro_validacao(_request: Request, exc: RequestValidationError):
    """Erro de validação no formato padrão, sem repetir o conteúdo."""
    return JSONResponse({"erro": "Requisição inválida.", "detalhes": _detalhes(exc.errors())}, status_code=422)


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
#: Código HTTP de cada erro previsto.
_STATUS_ERRO = {ArquivoInvalido: 422, VazamentoDetectado: 500, FalhaOCR: 503}


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


def _iniciar_analise(func, *args) -> asyncio.Future:
    """Agenda a análise numa thread ou, com ``THEMIS_PROCESSOS`` > 1, num processo de trabalho."""
    pool = _pool()
    if pool is not None:
        return asyncio.get_running_loop().run_in_executor(pool, partial(func, *args))
    return asyncio.ensure_future(run_in_threadpool(func, *args))


async def _executar(func, *args, espera_vaga: float | None = _ESPERA_VAGA_S, limite_s: float | None = None):
    """Executa uma análise respeitando o limite de concorrência e o tempo máximo.

    Uma thread ou um processo em execução não pode ser interrompido: quando o tempo limite é
    atingido, o cliente recebe 503, mas a vaga só é liberada quando a análise termina. Assim, o
    número de análises em execução nunca excede o limite configurado.

    Raises:
        HTTPException: 503 se não houver vaga ou se o tempo limite for atingido; 500 em erro interno.
    """
    try:
        await asyncio.wait_for(_SEMAFORO.acquire(), timeout=espera_vaga)
    except TimeoutError as erro:
        raise HTTPException(status_code=503, detail="Servidor ocupado. Tente novamente.") from erro
    tarefa = _iniciar_analise(func, *args)
    tarefa.add_done_callback(_liberar)
    try:
        return await asyncio.wait_for(asyncio.shield(tarefa), timeout=limite_s or CFG.timeout_s)
    except TimeoutError as erro:
        raise HTTPException(status_code=503, detail="Tempo de processamento excedido.") from erro
    except _ERROS_PREVISTOS:
        raise
    except Exception as erro:  # noqa: BLE001 - convertido em resposta genérica, sem a mensagem
        raise HTTPException(status_code=500, detail="Erro interno ao processar.") from erro


# ------------------------------------------------------------------ modelos
def _perfis_disponiveis() -> list[str]:
    return [*PERFIS, *ORGAO.perfis]


class Opcoes(BaseModel):
    """Opções de anonimização comuns a todas as rotas. Campos omitidos seguem a configuração do órgão."""

    perfil: str | None = Field(None, description="Perfil; padrão: o da configuração do órgão (lai)")
    modo: str | None = Field(None, description=f"Um de: {', '.join(MODOS)}; padrão: etiqueta")
    permitir: list[str] = Field(default_factory=list, max_length=200, description="Termos que nunca são tarjados")
    bloquear: list[str] = Field(default_factory=list, max_length=200, description="Termos sempre tarjados")
    preservar_agentes_publicos: bool | None = Field(None, description="Mantém nomes acompanhados de cargo público")

    @field_validator("perfil")
    @classmethod
    def _perfil(cls, v: str | None) -> str | None:
        if v is not None and v.lower() not in _perfis_disponiveis():
            raise ValueError(f"perfil inválido; opções: {', '.join(_perfis_disponiveis())}")
        return v

    @field_validator("modo")
    @classmethod
    def _modo(cls, v: str | None) -> str | None:
        # Na demonstração pública, o modo HMAC usaria uma chave do servidor compartilhada entre usuários.
        if v is not None and (v not in MODOS or (CFG.demo and v == "hmac")):
            raise ValueError(f"modo inválido; opções: {', '.join(MODOS)}")
        return v

    @field_validator("permitir", "bloquear")
    @classmethod
    def _termos(cls, v: list[str]) -> list[str]:
        if any(len(t) > 200 for t in v):
            raise ValueError("cada termo deve ter até 200 caracteres")
        return v

    def sobrepor(self) -> dict:
        """Argumentos que prevalecem sobre a configuração do órgão (ver :mod:`themis_lgpd.api.trabalho`)."""
        return {"perfil": self.perfil, "modo": self.modo, "permitir": self.permitir, "bloquear": self.bloquear,
                "preservar_agentes_publicos": self.preservar_agentes_publicos, "usar_ner": CFG.usar_ner,
                "modelo_spacy": CFG.modelo_spacy}


class PedidoTexto(Opcoes):
    """Pedido de anonimização ou análise de texto."""

    texto: str = Field(..., min_length=1, max_length=CFG.max_caracteres)
    incluir_valores: bool = Field(False, description="Incluir os valores detectados na resposta")


@dataclass
class _PedidoArquivo:
    """Arquivo recebido e opções já validadas."""

    dados: bytes
    nome: str
    opcoes: Opcoes
    arquivo: dict
    resposta: str


async def _pedido_arquivo(arquivo: UploadFile, perfil: str | None, modo: str | None, permitir: list[str],
                          bloquear: list[str], preservar_agentes_publicos: bool | None, coluna_integral: list[str],
                          ocr: bool, resposta: str) -> _PedidoArquivo:
    """Valida as opções de um envio de arquivo e lê o arquivo, respeitando o limite de tamanho."""
    try:
        op = Opcoes(perfil=perfil, modo=modo, permitir=permitir, bloquear=bloquear,
                    preservar_agentes_publicos=preservar_agentes_publicos)
    except ValidationError as erro:
        raise HTTPException(status_code=422, detail="Requisição inválida: " + "; ".join(
            f"{d['campo']}: {d['erro']}" for d in _detalhes(erro.errors()))) from erro
    if resposta not in {"arquivo", "json"}:
        raise HTTPException(status_code=422, detail="Requisição inválida: resposta deve ser 'arquivo' ou 'json'.")
    if len(coluna_integral) > 100 or any(len(c) > 200 for c in coluna_integral):
        raise HTTPException(status_code=422, detail="Requisição inválida: coluna_integral com itens demais.")
    dados = await arquivo.read(CFG.max_mb * 1024 * 1024 + 1)
    if len(dados) > CFG.max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Arquivo maior que {CFG.max_mb} MB.")
    opcoes_arquivo = {"limite_bytes": CFG.max_mb * 1024 * 1024, "limite_paginas": CFG.max_paginas,
                      "ocr": ocr and ORGAO.ocr, "colunas_integrais": coluna_integral or None}
    return _PedidoArquivo(dados, arquivo.filename or "documento", op, opcoes_arquivo, resposta)


def _resposta_arquivo(res: ResultadoArquivo, resposta: str) -> Response:
    """O arquivo gerado (com totais nos cabeçalhos) ou, com ``resposta=json``, arquivo e relatório em JSON."""
    tarjados = sum(len(r.tarjadas) for r in res.resultados)
    alertas = sum(len(r.alertas) for r in res.resultados)
    if resposta == "json":
        return JSONResponse({
            "nome": res.nome, "formato": res.formato, "mime": res.mime,
            "conteudo_base64": base64.b64encode(res.dados).decode("ascii"),
            "tarjados": tarjados, "para_revisar": alertas, "avisos": res.avisos,
            "relatorio": {"resumo": relatorio.resumo(res.resultados), "itens": relatorio.linhas(res.resultados)},
            "nota_de_tarjamento": relatorio.nota_de_tarjamento(res.resultados),
        })
    return Response(res.dados, media_type=res.mime, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(res.nome)}",
        "X-Themis-Tarjados": str(tarjados),
        "X-Themis-Para-Revisar": str(alertas),
        "X-Themis-Avisos": quote(" | ".join(res.avisos))[:4000],
    })


# ------------------------------------------------------------------ rotas
@app.get("/saude")
def saude():
    """Estado do serviço, versão, disponibilidade de OCR e configuração em uso."""
    from ..formatos.ocr import ocr_disponivel

    return {"status": "ok", "versao": __version__, "ocr": ocr_disponivel(), "demo": CFG.demo,
            "processos": CFG.processos, "configuracao_do_orgao": bool(ORGAO.origem)}


@app.get("/v1/perfis")
def listar_perfis():
    """Perfis de anonimização (do Themis e do órgão) e modos de saída."""
    perfis = [*PERFIS.values(), *ORGAO.perfis.values()]
    padrao = ORGAO.perfil if isinstance(ORGAO.perfil, str) else ORGAO.perfil.nome
    return {"perfis": [{"nome": p.nome, "titulo": p.titulo, "descricao": p.descricao} for p in perfis],
            "padrao": padrao, "modos": MODOS}


@app.get("/v1/tipos")
def listar_tipos():
    """Tipos de dado reconhecidos, com categoria, etiqueta e base legal."""
    return [{"tipo": t.codigo, "nome": t.nome, "categoria": t.categoria, "etiqueta": t.etiqueta,
             "base_legal": CATEGORIAS[t.categoria].base_legal} for t in TIPOS.values()]


@app.post("/v1/anonimizar", dependencies=[Depends(exigir_chave)])
async def anonimizar_texto(pedido: PedidoTexto):
    """Anonimiza um texto e devolve o texto anonimizado, as entidades e a nota de tarjamento."""
    r = await _executar(trabalho.anonimizar_texto, pedido.sobrepor(), pedido.texto)
    corpo = r.para_dict(incluir_valores=pedido.incluir_valores)
    corpo["nota_de_tarjamento"] = relatorio.nota_de_tarjamento([r], "o texto")
    return corpo


@app.post("/v1/analisar", dependencies=[Depends(exigir_chave)])
async def analisar_texto(pedido: PedidoTexto):
    """Lista o que seria tarjado ou sinalizado, sem alterar o texto."""
    ents = await _executar(trabalho.analisar_texto, pedido.sobrepor(), pedido.texto)
    return {"entidades": [e.para_dict(incluir_valor=pedido.incluir_valores) for e in ents]}


_CAMPOS_ARQUIVO = (
    " Campos do formulário (todos opcionais, exceto `arquivo`): `perfil`, `modo`, `permitir` e `bloquear` "
    "(repetíveis), `preservar_agentes_publicos`, `coluna_integral` (repetível; planilhas), `ocr` e `resposta` "
    "(`arquivo`, padrão, ou `json`, que devolve o arquivo em base64 com o relatório de tarjamento)."
)


@app.post("/v1/arquivos/anonimizar", dependencies=[Depends(exigir_chave)],
          description="Anonimiza um arquivo e devolve o arquivo gerado. Os totais e os avisos são informados nos "
                      "cabeçalhos `X-Themis-Tarjados`, `X-Themis-Para-Revisar` e `X-Themis-Avisos` (codificado "
                      "para URL)." + _CAMPOS_ARQUIVO)
async def anonimizar_arquivo_rota(
    arquivo: UploadFile = File(...),
    perfil: str | None = Form(None),
    modo: str | None = Form(None),
    permitir: list[str] = Form([]),
    bloquear: list[str] = Form([]),
    preservar_agentes_publicos: bool | None = Form(None),
    coluna_integral: list[str] = Form([]),
    ocr: bool = Form(True),
    resposta: str = Form("arquivo"),
):
    """Anonimiza um arquivo e devolve o arquivo gerado (ou, com ``resposta=json``, também o relatório)."""
    pedido = await _pedido_arquivo(arquivo, perfil, modo, permitir, bloquear, preservar_agentes_publicos,
                                   coluna_integral, ocr, resposta)
    try:
        res = await _executar(trabalho.anonimizar_arquivo, pedido.opcoes.sobrepor(), pedido.dados, pedido.nome,
                              pedido.arquivo)
    except _ERROS_PREVISTOS as erro:
        raise HTTPException(status_code=_STATUS_ERRO[type(erro)], detail=str(erro)) from erro
    return _resposta_arquivo(res, pedido.resposta)


# ------------------------------------------------------------------ tarefas assíncronas
@dataclass
class _Tarefa:
    """Tarefa assíncrona mantida em memória até o download ou a expiração."""

    id: str
    dono: str
    resposta: str
    situacao: str = "na_fila"
    concluida_em: float | None = None
    resultado: ResultadoArquivo | None = None
    mensagem: str | None = None


_TAREFAS: dict[str, _Tarefa] = {}
_EXECUCOES: set[asyncio.Task] = set()


def _dono(request: Request) -> str:
    """Resumo da chave de API que criou a tarefa: só ela pode consultá-la e baixar o resultado."""
    return hashlib.sha256(request.headers.get("x-api-key", "").encode("utf-8")).hexdigest()


def _expurgar() -> None:
    """Apaga da memória os resultados não baixados no prazo de ``THEMIS_TAREFA_TTL_S``."""
    agora = time.monotonic()
    for t in list(_TAREFAS.values()):
        if t.concluida_em is not None and agora - t.concluida_em > CFG.tarefa_ttl_s:
            del _TAREFAS[t.id]


def _obter(id_tarefa: str, request: Request) -> _Tarefa:
    _expurgar()
    t = _TAREFAS.get(id_tarefa)
    if t is None or not hmac.compare_digest(t.dono, _dono(request)):
        raise HTTPException(status_code=404, detail="Tarefa inexistente ou expirada.")
    return t


async def _rodar(t: _Tarefa, pedido: _PedidoArquivo) -> None:
    t.situacao = "processando"
    try:
        t.resultado = await _executar(trabalho.anonimizar_arquivo, pedido.opcoes.sobrepor(), pedido.dados,
                                      pedido.nome, pedido.arquivo, espera_vaga=None, limite_s=CFG.tarefa_timeout_s)
        t.situacao = "concluida"
    except _ERROS_PREVISTOS as erro:
        t.situacao, t.mensagem = "falhou", str(erro)
    except HTTPException as erro:
        t.situacao, t.mensagem = "falhou", erro.detail
    except Exception as erro:  # noqa: BLE001 - registrado só pelo tipo
        log.error("Erro interno (%s)", type(erro).__name__)
        t.situacao, t.mensagem = "falhou", "Erro interno ao processar."
    finally:
        t.concluida_em = time.monotonic()


@app.post("/v1/tarefas", status_code=202, dependencies=[Depends(exigir_chave)],
          description="Agenda a anonimização de um arquivo e responde imediatamente (HTTP 202), para documentos "
                      "longos, como PDFs digitalizados, que excederiam o tempo de uma requisição. Consulte a "
                      "situação em `GET /v1/tarefas/{id}` e baixe o resultado em `GET /v1/tarefas/{id}/resultado`; "
                      "o resultado é apagado da memória após o download ou após `THEMIS_TAREFA_TTL_S` segundos."
                      + _CAMPOS_ARQUIVO)
async def criar_tarefa(
    request: Request,
    arquivo: UploadFile = File(...),
    perfil: str | None = Form(None),
    modo: str | None = Form(None),
    permitir: list[str] = Form([]),
    bloquear: list[str] = Form([]),
    preservar_agentes_publicos: bool | None = Form(None),
    coluna_integral: list[str] = Form([]),
    ocr: bool = Form(True),
    resposta: str = Form("arquivo"),
):
    """Agenda a anonimização de um arquivo."""
    _expurgar()
    if len(_TAREFAS) >= CFG.max_tarefas:
        raise HTTPException(status_code=503, detail="Limite de tarefas em andamento atingido. Tente mais tarde.",
                            headers={"Retry-After": "60"})
    pedido = await _pedido_arquivo(arquivo, perfil, modo, permitir, bloquear, preservar_agentes_publicos,
                                   coluna_integral, ocr, resposta)
    t = _Tarefa(id=secrets.token_urlsafe(24), dono=_dono(request), resposta=pedido.resposta)
    _TAREFAS[t.id] = t
    execucao = asyncio.create_task(_rodar(t, pedido))
    _EXECUCOES.add(execucao)
    execucao.add_done_callback(_EXECUCOES.discard)
    return {"id": t.id, "situacao": t.situacao, "consulta": f"/v1/tarefas/{t.id}",
            "resultado": f"/v1/tarefas/{t.id}/resultado", "expira_apos_conclusao_s": CFG.tarefa_ttl_s}


@app.get("/v1/tarefas/{id_tarefa}", dependencies=[Depends(exigir_chave)])
def consultar_tarefa(id_tarefa: str, request: Request):
    """Situação da tarefa: ``na_fila``, ``processando``, ``concluida`` ou ``falhou``."""
    t = _obter(id_tarefa, request)
    corpo: dict = {"id": t.id, "situacao": t.situacao}
    if t.resultado is not None:
        corpo.update(nome=t.resultado.nome, formato=t.resultado.formato, avisos=t.resultado.avisos,
                     tarjados=sum(len(r.tarjadas) for r in t.resultado.resultados),
                     para_revisar=sum(len(r.alertas) for r in t.resultado.resultados))
    if t.mensagem:
        corpo["mensagem"] = t.mensagem
    return corpo


@app.get("/v1/tarefas/{id_tarefa}/resultado", dependencies=[Depends(exigir_chave)])
def baixar_resultado(id_tarefa: str, request: Request):
    """Devolve o resultado de uma tarefa concluída e o apaga da memória."""
    t = _obter(id_tarefa, request)
    if t.situacao != "concluida" or t.resultado is None:
        raise HTTPException(status_code=409, detail=f"Tarefa ainda não concluída (situação: {t.situacao}).")
    del _TAREFAS[t.id]
    return _resposta_arquivo(t.resultado, t.resposta)


@app.delete("/v1/tarefas/{id_tarefa}", status_code=204, dependencies=[Depends(exigir_chave)])
def apagar_tarefa(id_tarefa: str, request: Request):
    """Apaga a tarefa e o seu resultado; uma análise em andamento termina, mas o resultado é descartado."""
    t = _obter(id_tarefa, request)
    del _TAREFAS[t.id]
    return Response(status_code=204)
