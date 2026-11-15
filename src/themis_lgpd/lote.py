"""Processamento de lotes de arquivos: coleta, paralelismo, retomada e manifesto de cadeia de custódia.

Um lote é uma lista de arquivos e pastas. A árvore de pastas é preservada na saída — dois arquivos
com o mesmo nome em pastas diferentes nunca disputam o mesmo destino — e cada arquivo processado
gera uma linha no **manifesto** (JSON Lines), gravada assim que o arquivo termina: caminho relativo,
SHA-256 da entrada e da saída, tamanhos, formato, perfil, modo, versão, identificador da
configuração, contagens por tipo, avisos, situação e duração. O manifesto não contém nenhum
conteúdo dos documentos e permite comprovar, depois, qual versão de qual arquivo foi publicada e com
que configuração.

Com ``retomar``, arquivos já concluídos com o mesmo conteúdo e a mesma configuração (conforme o
manifesto) são pulados: um lote interrompido continua de onde parou.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import time
from collections import Counter
from collections.abc import Iterable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from . import __version__

#: Extensões incluídas ao percorrer pastas. Arquivos indicados explicitamente são aceitos com qualquer
#: extensão, pois o formato é identificado pelo conteúdo.
EXTENSOES = frozenset({".pdf", ".docx", ".xlsx", ".csv", ".txt", ".png", ".jpg", ".jpeg"})

#: Situação de cada arquivo e o código de saída correspondente; o código do lote é o maior deles.
OK, REJEITADO, ERRO = "ok", "rejeitado", "erro"
CODIGOS = {OK: 0, REJEITADO: 1, ERRO: 2}


@dataclass(frozen=True)
class Tarefa:
    """Arquivo do lote.

    Attributes:
        caminho: Caminho do arquivo de entrada.
        relativo: Caminho relativo à base comum das entradas, preservado na saída e no manifesto.
    """

    caminho: Path
    relativo: PurePosixPath


@dataclass
class Opcoes:
    """Configuração de um lote (serializável, para os processos de trabalho).

    Attributes:
        sobrepor: Argumentos de :class:`themis_lgpd.motor.Anonimizador` informados na chamada, que
            prevalecem sobre a configuração do órgão (ver
            :meth:`themis_lgpd.configuracao.ConfiguracaoOrgao.argumentos`).
        config: Arquivo ``themis.toml``; ``None`` usa a configuração padrão. Cada processo de
            trabalho relê o arquivo, o que registra nele os tipos próprios do órgão.
        ocr: Permite OCR.
        limite_bytes: Tamanho máximo de arquivo.
        colunas_integrais: Colunas de planilha tarjadas por inteiro.
        saida: Pasta de saída; ``None`` grava ao lado de cada entrada.
        arquivo_saida: Arquivo de saída, quando o lote tem uma única entrada.
        cofre: Pasta (ou arquivo, para uma única entrada) dos cofres de reversão de arquivos de texto.
        senha_cofre: Senha dos cofres; nunca gravada.
    """

    sobrepor: dict = field(default_factory=dict)
    config: str | None = None
    ocr: bool = True
    limite_bytes: int = 50 * 1024 * 1024
    colunas_integrais: list[str] | None = None
    saida: str | None = None
    arquivo_saida: str | None = None
    cofre: str | None = None
    senha_cofre: str | None = field(default=None, repr=False)

    def configuracao(self):
        """Configuração do órgão carregada do arquivo (ou a padrão)."""
        from . import configuracao

        return configuracao.carregar(self.config) if self.config else configuracao.ConfiguracaoOrgao()

    def identificador(self) -> str:
        """Resumo (SHA-256, 16 dígitos) de tudo o que influi no resultado: mesma configuração, mesmo valor.

        Termos das listas de permissão e de bloqueio entram apenas pelo resumo, para que o manifesto
        não os exponha.
        """
        sobrepor = {k: v for k, v in self.sobrepor.items() if k != "chave_hmac"}
        for lista in ("permitir", "bloquear"):
            if lista in sobrepor:
                sobrepor[lista] = sha256("\n".join(sorted(sobrepor[lista])).encode("utf-8"))
        base = {"versao": __version__, "config": self.configuracao().impressao(), "sobrepor": sobrepor,
                "ocr": self.ocr, "colunas": self.colunas_integrais}
        texto = json.dumps(base, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def coletar(entradas: Iterable[str | Path], recursivo: bool = False) -> list[Tarefa]:
    """Arquivos de um lote, com o caminho relativo de cada um.

    Pastas contribuem com os arquivos de extensão suportada (em todas as subpastas, com
    ``recursivo``); arquivos ocultos e saídas de execuções anteriores (``*_anonimizado.*``) são
    ignorados. O caminho relativo parte da base comum de todas as entradas, de modo que
    ``a/despacho.pdf`` e ``b/despacho.pdf`` mantêm as pastas ``a`` e ``b`` na saída.

    Raises:
        FileNotFoundError: Entrada inexistente.
    """
    arquivos: list[Path] = []
    bases: list[Path] = []
    for entrada in entradas:
        p = Path(entrada)
        if p.is_dir():
            bases.append(p.resolve())
            padrao = p.rglob("*") if recursivo else p.glob("*")
            arquivos += sorted(f for f in padrao if f.is_file() and f.suffix.lower() in EXTENSOES
                               and not _ignorar(f.relative_to(p)))
        elif p.is_file():
            bases.append(p.resolve().parent)
            arquivos.append(p)
        else:
            raise FileNotFoundError(f"Entrada não encontrada: {entrada}")
    base = _base_comum(bases)
    vistos: set[Path] = set()
    tarefas = []
    for f in arquivos:
        absoluto = f.resolve()
        if absoluto in vistos:
            continue
        vistos.add(absoluto)
        tarefas.append(Tarefa(f, _relativo(absoluto, base)))
    return tarefas


def _ignorar(relativo: Path) -> bool:
    return any(parte.startswith(".") for parte in relativo.parts) or relativo.stem.endswith("_anonimizado")


def _base_comum(bases: list[Path]) -> Path | None:
    try:
        return Path(os.path.commonpath(bases)) if bases else None
    except ValueError:  # unidades diferentes no Windows
        return None


def _relativo(absoluto: Path, base: Path | None) -> PurePosixPath:
    if base is not None:
        try:
            return PurePosixPath(absoluto.relative_to(base).as_posix())
        except ValueError:
            pass
    return PurePosixPath(*[p.replace(":", "") for p in absoluto.parts if p not in (absoluto.anchor,)])


def ler_manifesto(caminho: str | Path) -> list[dict]:
    """Linhas de um manifesto existente (linhas incompletas, de uma interrupção, são ignoradas)."""
    p = Path(caminho)
    if not p.exists():
        return []
    linhas = []
    for linha in p.read_text(encoding="utf-8").splitlines():
        try:
            linhas.append(json.loads(linha))
        except json.JSONDecodeError:
            continue
    return linhas


def concluidos(manifesto: Iterable[dict], configuracao: str) -> dict[str, dict]:
    """Arquivos concluídos com a configuração indicada, pelo caminho relativo (o registro mais recente)."""
    feitos: dict[str, dict] = {}
    for item in manifesto:
        if item.get("situacao") == OK and item.get("configuracao") == configuracao:
            feitos[item["arquivo"]] = item
    return feitos


def sha256(dados: bytes) -> str:
    """Resumo SHA-256 em hexadecimal."""
    return hashlib.sha256(dados).hexdigest()


# ------------------------------------------------------------------ processamento de um arquivo
_ANONIMIZADOR = None
_OPCOES: Opcoes | None = None


def _iniciar(opcoes: Opcoes) -> None:
    """Prepara o processo de trabalho: um anonimizador (e um modelo de linguagem) por processo."""
    global _ANONIMIZADOR, _OPCOES
    from .motor import Anonimizador

    _OPCOES = opcoes
    _ANONIMIZADOR = Anonimizador(**opcoes.configuracao().argumentos(**opcoes.sobrepor))


def destino_de(tarefa: Tarefa, opcoes: Opcoes, nome_gerado: str) -> Path:
    """Arquivo de saída: na pasta de saída, com a mesma árvore da entrada, ou ao lado da entrada."""
    if opcoes.arquivo_saida:
        return Path(opcoes.arquivo_saida)
    if opcoes.saida:
        return Path(opcoes.saida).joinpath(*tarefa.relativo.parent.parts, nome_gerado)
    return tarefa.caminho.with_name(nome_gerado)


def _cofre_de(tarefa: Tarefa, opcoes: Opcoes) -> Path | None:
    if not opcoes.cofre:
        return None
    if opcoes.arquivo_saida or Path(opcoes.cofre).suffix:
        return Path(opcoes.cofre)
    return Path(opcoes.cofre).joinpath(*tarefa.relativo.parent.parts, tarefa.relativo.name + ".cofre")


def processar(tarefa: Tarefa) -> dict:
    """Anonimiza um arquivo do lote e devolve a linha do manifesto, mais os resultados (``_resultados``).

    Nenhuma exceção escapa: falhas viram situação ``rejeitado`` (arquivo inválido, vazamento
    detectado, OCR indisponível, erro de leitura) ou ``erro`` (falha interna, da qual só o tipo é
    registrado, pois mensagens de bibliotecas podem citar o conteúdo).
    """
    from .formatos import ArquivoInvalido, FalhaOCR, VazamentoDetectado, anonimizar_arquivo

    opcoes, anon = _OPCOES, _ANONIMIZADOR
    assert opcoes is not None and anon is not None, "processo de trabalho não iniciado"  # nosec B101
    inicio = time.perf_counter()
    linha: dict = {
        "arquivo": tarefa.relativo.as_posix(), "inicio": datetime.now(UTC).isoformat(timespec="seconds"),
        "versao": __version__, "perfil": anon.perfil.nome, "modo": anon.modo, "configuracao": opcoes.identificador(),
    }
    resultados: list = []
    try:
        dados = tarefa.caminho.read_bytes()
        linha.update(sha256_entrada=sha256(dados), bytes_entrada=len(dados))
        res = anonimizar_arquivo(dados, tarefa.caminho.name, anon, ocr=opcoes.ocr, limite_bytes=opcoes.limite_bytes,
                                 colunas_integrais=opcoes.colunas_integrais)
        destino = destino_de(tarefa, opcoes, res.nome)
        if destino.resolve() == tarefa.caminho.resolve():
            raise ArquivoInvalido("a saída sobrescreveria a entrada")
        cofre, conteudo_cofre = _cofre_de(tarefa, opcoes), None
        avisos = list(res.avisos)
        if cofre is not None:
            if res.formato != "txt":
                avisos.append("Cofre de reversão só é gerado para arquivos de texto (.txt).")
                cofre = None
            else:
                from .cofre import criar_cofre

                conteudo_cofre = criar_cofre(res.resultados[0], opcoes.senha_cofre or "")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(res.dados)
        if cofre is not None and conteudo_cofre is not None:
            cofre.parent.mkdir(parents=True, exist_ok=True)
            cofre.write_bytes(conteudo_cofre)
            linha["cofre"] = cofre.as_posix()
        tarjadas = [e for r in res.resultados for e in r.tarjadas]
        linha.update(
            situacao=OK, formato=res.formato, saida=destino.as_posix(), sha256_saida=sha256(res.dados),
            bytes_saida=len(res.dados), tarjados=len(tarjadas),
            por_tipo=dict(Counter(e.tipo for e in tarjadas).most_common()),
            para_revisar=sum(len(r.alertas) for r in res.resultados), avisos=avisos,
        )
        resultados = res.resultados
    except (ArquivoInvalido, VazamentoDetectado, FalhaOCR, OSError, ValueError) as erro:
        linha.update(situacao=REJEITADO, mensagem=str(erro))
    except Exception as erro:  # noqa: BLE001 - registrado no manifesto; o lote segue para o próximo arquivo
        linha.update(situacao=ERRO, mensagem=f"erro interno ({type(erro).__name__}); nenhum arquivo foi gerado")
    linha["duracao_s"] = round(time.perf_counter() - inicio, 3)
    return {**linha, "_resultados": resultados}


def executar(tarefas: list[Tarefa], opcoes: Opcoes, trabalhos: int = 1) -> Iterator[dict]:
    """Processa as tarefas, em paralelo com ``trabalhos`` > 1, devolvendo cada linha assim que concluída.

    Cada processo de trabalho carrega o próprio modelo de linguagem; a memória cresce na mesma
    proporção (cerca de 1 GB por processo com o modelo ``pt_core_news_lg``).
    """
    if trabalhos <= 1 or len(tarefas) <= 1:
        _iniciar(opcoes)
        for t in tarefas:
            yield processar(t)
        return
    # "spawn" em todas as plataformas: o mesmo comportamento no Windows e no Linux, sem copiar para o
    # processo filho o estado de threads do processo principal.
    contexto = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=trabalhos, initializer=_iniciar, initargs=(opcoes,),
                             mp_context=contexto) as pool:
        futuros = [pool.submit(processar, t) for t in tarefas]
        try:
            for futuro in as_completed(futuros):
                yield futuro.result()
        finally:
            for futuro in futuros:
                futuro.cancel()


class Manifesto:
    """Gravação incremental do manifesto: cada linha é gravada e descarregada no disco ao ser recebida.

    Uma interrupção (Ctrl+C, queda de energia) preserva as linhas dos arquivos já concluídos.
    """

    def __init__(self, caminho: str | Path | None):
        self._arq = None
        if caminho:
            Path(caminho).parent.mkdir(parents=True, exist_ok=True)
            self._arq = open(caminho, "a", encoding="utf-8", newline="\n")  # noqa: SIM115 - fechado em fechar()

    def registrar(self, linha: dict) -> None:
        """Acrescenta uma linha (sem os campos internos, iniciados por ``_``)."""
        if self._arq is None:
            return
        self._arq.write(json.dumps({k: v for k, v in linha.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")
        self._arq.flush()
        os.fsync(self._arq.fileno())

    def fechar(self) -> None:
        if self._arq is not None:
            self._arq.close()


def documentos_do_relatorio(linhas: Iterable[dict]) -> tuple[list, list[str]]:
    """Resultados dos arquivos concluídos e o rótulo de cada um ("pasta/arquivo.pdf, parte 2 de 5").

    O relatório consolidado de um lote identifica, em cada item, o arquivo de origem.
    """
    resultados, documentos = [], []
    for linha in linhas:
        partes = linha.get("_resultados") or []
        for i, r in enumerate(partes, start=1):
            resultados.append(r)
            documentos.append(linha["arquivo"] if len(partes) == 1 else f"{linha['arquivo']}, parte {i} de {len(partes)}")
    return resultados, documentos
