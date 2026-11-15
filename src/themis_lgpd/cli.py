"""Interface de linha de comando (``themis``).

Subcomandos: ``anonimizar``, ``analisar``, ``perfis``, ``interface``, ``api`` e ``reverter``. Todo o
processamento é local; nenhum dado é enviado para fora da máquina.

Mensagens de progresso e avisos são escritos na saída de erro; a saída padrão é reservada ao
conteúdo (texto anonimizado, JSON da análise ou texto revertido), o que permite o uso em pipelines.
Mensagens de erro nunca reproduzem conteúdo dos arquivos.

Exemplo::

    themis anonimizar despacho.pdf planilha.xlsx -o saida/ -r relatorio.xlsx --perfil lai
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from . import __version__
from .operadores import MODOS
from .perfis import PERFIL_PADRAO, PERFIS


def _ler_lista(valores: list[str] | None, arquivo: str | None) -> list[str]:
    """Termos informados na linha de comando e, opcionalmente, em arquivo (um por linha, ``#`` comenta)."""
    itens = list(valores or [])
    if arquivo:
        itens += [linha.strip() for linha in Path(arquivo).read_text(encoding="utf-8").splitlines()
                  if linha.strip() and not linha.startswith("#")]
    return itens


def _anonimizador(args):
    from .motor import Anonimizador

    # A chave do HMAC vem do ambiente para não ficar no histórico do shell.
    chave = os.environ.get("THEMIS_CHAVE_HMAC") if args.modo == "hmac" else None
    return Anonimizador(
        args.perfil, args.modo,
        permitir=_ler_lista(args.permitir, args.permitir_arquivo),
        bloquear=_ler_lista(args.bloquear, args.bloquear_arquivo),
        usar_ner=not args.sem_ner, modelo_spacy=args.modelo,
        preservar_agentes_publicos=args.preservar_agentes_publicos, chave_hmac=chave,
    )


def _saida_para(entrada: Path, args, nome_sugerido: str) -> Path:
    """Caminho do arquivo gerado: ``--saida`` (arquivo ou pasta) ou ao lado da entrada."""
    if args.saida:
        destino = Path(args.saida)
        if destino.is_dir() or len(args.entradas) > 1:
            destino.mkdir(parents=True, exist_ok=True)
            return destino / nome_sugerido
        return destino
    return entrada.with_name(nome_sugerido)


def _gravar_relatorio(caminho: str, resultados: list, incluir_valores: bool) -> None:
    """Grava o relatório no formato indicado pela extensão (``.xlsx``, ``.csv``, ``.txt``/``.md`` ou JSON)."""
    from . import relatorio

    rel = Path(caminho)
    fmt = rel.suffix.lower()
    if fmt == ".xlsx":
        rel.write_bytes(relatorio.para_xlsx(resultados, incluir_valores))
    elif fmt == ".csv":
        rel.write_text(relatorio.para_csv(resultados, incluir_valores), encoding="utf-8")
    elif fmt in {".txt", ".md"}:
        rel.write_text(relatorio.nota_de_tarjamento(resultados), encoding="utf-8")
    else:
        rel.write_text(relatorio.para_json(resultados, incluir_valores), encoding="utf-8")
    aviso = "  (CONTÉM DADOS PESSOAIS)" if incluir_valores else ""
    print(f"✓ relatório: {rel}{aviso}", file=sys.stderr)


def cmd_anonimizar(args) -> int:
    """Anonimiza arquivos ou a entrada padrão.

    Returns:
        ``0`` em caso de sucesso; ``1`` se algum arquivo foi rejeitado ou falhou na verificação;
        ``2`` em caso de erro interno. Os demais arquivos do lote continuam sendo processados.
    """
    from .formatos import ArquivoInvalido, FalhaOCR, VazamentoDetectado, anonimizar_arquivo
    from .formatos.texto import anonimizar_txt

    anon = _anonimizador(args)
    todos = []
    codigo = 0
    for caminho in args.entradas:
        if caminho == "-":
            try:
                res = anonimizar_txt(sys.stdin.buffer.read(), anon, "entrada.txt")
            except VazamentoDetectado as erro:
                print(f"✗ entrada padrão: {erro}", file=sys.stderr)
                codigo = 1
                continue
            sys.stdout.write(res.dados.decode("utf-8"))
            todos += res.resultados
            continue
        entrada = Path(caminho)
        try:
            res = anonimizar_arquivo(entrada.read_bytes(), entrada.name, anon, ocr=not args.sem_ocr,
                                     limite_bytes=args.limite_mb * 1024 * 1024,
                                     colunas_integrais=args.coluna_integral)
        except (ArquivoInvalido, VazamentoDetectado, FalhaOCR, OSError) as erro:
            print(f"✗ {entrada.name}: {erro}", file=sys.stderr)
            codigo = 1
            continue
        except Exception as erro:  # noqa: BLE001 - nenhum arquivo é gerado; o lote segue para o próximo
            # A mensagem de bibliotecas de terceiros pode citar trechos do arquivo: só o tipo é exibido.
            print(f"✗ {entrada.name}: erro interno ({type(erro).__name__}); nenhum arquivo foi gerado.",
                  file=sys.stderr)
            codigo = 2
            continue
        destino = _saida_para(entrada, args, res.nome)
        if destino.resolve() == entrada.resolve():
            print(f"✗ {entrada.name}: a saída sobrescreveria a entrada.", file=sys.stderr)
            codigo = 1
            continue
        destino.write_bytes(res.dados)
        todos += res.resultados
        if args.cofre:
            if res.formato != "txt":
                print("  ! --cofre só é suportado para arquivos de texto (.txt).", file=sys.stderr)
            else:
                from .cofre import criar_cofre

                senha = os.environ.get("THEMIS_SENHA_COFRE") or getpass.getpass("Senha para o cofre (mín. 12): ")
                Path(args.cofre).write_bytes(criar_cofre(res.resultados[0], senha))
                print(f"  ✓ cofre de reversão: {args.cofre} (guarde-o separado do documento)", file=sys.stderr)
        tarjados = sum(len(r.tarjadas) for r in res.resultados)
        alertas = sum(len(r.alertas) for r in res.resultados)
        print(f"✓ {entrada.name} → {destino}  ({tarjados} tarjado(s), {alertas} para revisar)", file=sys.stderr)
        for aviso in res.avisos:
            print(f"  ! {aviso}", file=sys.stderr)
    if args.relatorio and todos:
        _gravar_relatorio(args.relatorio, todos, args.incluir_valores)
    return codigo


def cmd_analisar(args) -> int:
    """Lista em JSON o que seria tarjado ou sinalizado em um texto, sem alterá-lo."""
    anon = _anonimizador(args)
    texto = sys.stdin.read() if args.entrada == "-" else Path(args.entrada).read_text(encoding="utf-8")
    ents = anon.analisar(texto)
    print(json.dumps([e.para_dict(incluir_valor=args.incluir_valores) for e in ents], ensure_ascii=False, indent=2))
    return 0


def cmd_perfis(_args) -> int:
    """Lista os perfis e os modos de saída disponíveis."""
    for p in PERFIS.values():
        print(f"{p.nome:16} {p.titulo}\n{'':16} {p.descricao}\n")
    print("Modos de saída:")
    for nome, desc in MODOS.items():
        print(f"  {nome:12} {desc}")
    return 0


def cmd_reverter(args) -> int:
    """Reconstitui o texto original a partir do texto pseudonimizado e do cofre."""
    from .cofre import reverter

    senha = os.environ.get("THEMIS_SENHA_COFRE") or getpass.getpass("Senha do cofre: ")
    texto = Path(args.texto).read_text(encoding="utf-8")
    print(reverter(texto, Path(args.cofre).read_bytes(), senha), end="")
    return 0


#: Opções do Streamlit aplicadas pela CLI: sem telemetria, proteção contra XSRF e mensagens de erro
#: sem detalhes (que poderiam exibir trechos do documento).
STREAMLIT_SEGURO = [
    "--browser.gatherUsageStats", "false",
    "--server.enableXsrfProtection", "true",
    "--server.enableCORS", "true",
    "--client.showErrorDetails", "none",
    "--client.toolbarMode", "minimal",
    "--server.fileWatcherType", "none",
    "--theme.base", "light",
]


def cmd_interface(args) -> int:
    """Inicia a interface web local (Streamlit) com as opções de :data:`STREAMLIT_SEGURO`."""
    import subprocess  # noqa: S404  # nosec B404

    from .config import carregar

    app = Path(__file__).with_name("ui") / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app), "--server.port", str(args.porta),
           "--server.address", args.endereco, "--server.maxUploadSize", str(carregar().max_mb), *STREAMLIT_SEGURO]
    return subprocess.call(cmd)  # noqa: S603 - executa o próprio Streamlit, sem shell  # nosec B603


def cmd_api(args) -> int:
    """Inicia a API HTTP local, sem log de acesso e sem cabeçalho de identificação do servidor."""
    import uvicorn

    uvicorn.run("themis_lgpd.api.app:app", host=args.endereco, port=args.porta, access_log=False,
                server_header=False, proxy_headers=False)
    return 0


def _opcoes_motor(p: argparse.ArgumentParser) -> None:
    """Opções comuns aos subcomandos que analisam texto."""
    p.add_argument("--perfil", default=PERFIL_PADRAO, choices=list(PERFIS), help="padrão: lai")
    p.add_argument("--modo", default="etiqueta", choices=list(MODOS), help="como substituir (padrão: etiqueta)")
    p.add_argument("--permitir", action="append", metavar="TERMO", help="nunca tarjar este termo (repetível)")
    p.add_argument("--permitir-arquivo", metavar="ARQ", help="lista de termos permitidos, um por linha")
    p.add_argument("--bloquear", action="append", metavar="TERMO", help="sempre tarjar este termo (repetível)")
    p.add_argument("--bloquear-arquivo", metavar="ARQ", help="lista de termos a tarjar, um por linha")
    p.add_argument("--preservar-agentes-publicos", action="store_true",
                   help="não tarjar nomes precedidos de cargo público (validar com a área jurídica)")
    p.add_argument("--sem-ner", action="store_true", help="não usar o modelo spaCy (menor cobertura de nomes)")
    p.add_argument("--modelo", default="pt_core_news_lg", help="modelo spaCy (padrão: pt_core_news_lg)")
    p.add_argument("--incluir-valores", action="store_true",
                   help="incluir os valores originais no relatório/saída (CONTÉM DADOS PESSOAIS)")


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada do comando ``themis``."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="themis", description="Themis LGPD — anonimização local de documentos (LGPD/LAI).")
    ap.add_argument("--versao", action="version", version=f"themis-lgpd {__version__}")
    sub = ap.add_subparsers(dest="comando", required=True)

    a = sub.add_parser("anonimizar", help="anonimiza arquivos (PDF, DOCX, XLSX, CSV, TXT, PNG/JPG) ou '-' (stdin)")
    a.add_argument("entradas", nargs="+")
    a.add_argument("-o", "--saida", help="arquivo ou pasta de saída (padrão: <nome>_anonimizado.<ext>)")
    a.add_argument("-r", "--relatorio", help="relatório de tarjamento (.json, .csv, .xlsx ou .txt = nota de tarjamento)")
    a.add_argument("--coluna-integral", action="append", metavar="CABEÇALHO",
                   help="em planilhas, tarjar a coluna inteira (repetível)")
    a.add_argument("--sem-ocr", action="store_true", help="não usar OCR em páginas digitalizadas")
    a.add_argument("--cofre", metavar="ARQ",
                   help="(texto) gera cofre cifrado para reverter a pseudonimização — senha via THEMIS_SENHA_COFRE")
    a.add_argument("--limite-mb", type=int, default=50)
    _opcoes_motor(a)
    a.set_defaults(func=cmd_anonimizar)

    b = sub.add_parser("analisar", help="lista (JSON) o que seria tarjado num texto")
    b.add_argument("entrada", help="arquivo .txt ou '-' para stdin")
    _opcoes_motor(b)
    b.set_defaults(func=cmd_analisar)

    c = sub.add_parser("perfis", help="lista perfis e modos")
    c.set_defaults(func=cmd_perfis)

    ui = sub.add_parser("interface", help="abre a interface web local (Streamlit)")
    ui.add_argument("--porta", type=int, default=8501)
    ui.add_argument("--endereco", default="127.0.0.1", help="use 0.0.0.0 só atrás de um proxy com HTTPS")
    ui.set_defaults(func=cmd_interface)

    api = sub.add_parser("api", help="inicia a API HTTP local")
    api.add_argument("--porta", type=int, default=8000)
    api.add_argument("--endereco", default="127.0.0.1")
    api.set_defaults(func=cmd_api)

    d = sub.add_parser("reverter", help="reverte um texto pseudonimizado com o cofre e a senha")
    d.add_argument("texto")
    d.add_argument("cofre")
    d.set_defaults(func=cmd_reverter)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
