"""Interface de linha de comando (``themis``).

Subcomandos: ``anonimizar``, ``analisar``, ``perfis``, ``interface``, ``api``, ``reverter`` e ``saude``. Todo o
processamento é local; nenhum dado é enviado para fora da máquina.

Mensagens de progresso e avisos são escritos na saída de erro; a saída padrão é reservada ao
conteúdo (texto anonimizado, JSON da análise ou texto revertido), o que permite o uso em pipelines.
Mensagens de erro nunca reproduzem conteúdo dos arquivos.

Exemplos::

    themis anonimizar despacho.pdf planilha.xlsx -o saida/ -r relatorio.xlsx --perfil lai
    themis anonimizar processos/ -R -o publicacao/ --manifesto custodia.jsonl -j 4 --config themis.toml
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


def _caminho_config(args) -> str | None:
    """Arquivo de configuração do órgão: ``--config`` ou ``THEMIS_CONFIG``; ``None`` usa a padrão."""
    return getattr(args, "config", None) or os.environ.get("THEMIS_CONFIG") or None


def _configuracao(args):
    from .configuracao import ConfiguracaoOrgao, carregar

    caminho = _caminho_config(args)
    return carregar(caminho) if caminho else ConfiguracaoOrgao()


def _sobrepor(args) -> dict:
    """Opções informadas na linha de comando, que prevalecem sobre a configuração do órgão."""
    return {
        "perfil": args.perfil, "modo": args.modo,
        "permitir": _ler_lista(args.permitir, args.permitir_arquivo),
        "bloquear": _ler_lista(args.bloquear, args.bloquear_arquivo),
        "usar_ner": False if args.sem_ner else None, "modelo_spacy": args.modelo,
        "preservar_agentes_publicos": True if args.preservar_agentes_publicos else None,
        # A chave do HMAC vem do ambiente para não ficar no histórico do shell.
        "chave_hmac": os.environ.get("THEMIS_CHAVE_HMAC") if args.modo == "hmac" else None,
    }


def _anonimizador(args):
    from .motor import Anonimizador

    return Anonimizador(**_configuracao(args).argumentos(**_sobrepor(args)))


def _gravar_relatorio(caminho: str, resultados: list, incluir_valores: bool, documentos: list[str] | None = None) -> None:
    """Grava o relatório no formato indicado pela extensão (``.xlsx``, ``.csv``, ``.txt``/``.md`` ou JSON)."""
    from . import relatorio

    rel = Path(caminho)
    fmt = rel.suffix.lower()
    if fmt == ".xlsx":
        rel.write_bytes(relatorio.para_xlsx(resultados, incluir_valores, documentos))
    elif fmt == ".csv":
        rel.write_text(relatorio.para_csv(resultados, incluir_valores, documentos), encoding="utf-8")
    elif fmt in {".txt", ".md"}:
        rel.write_text(relatorio.nota_de_tarjamento(resultados), encoding="utf-8")
    else:
        rel.write_text(relatorio.para_json(resultados, incluir_valores, documentos), encoding="utf-8")
    aviso = "  (CONTÉM DADOS PESSOAIS)" if incluir_valores else ""
    print(f"✓ relatório: {rel}{aviso}", file=sys.stderr)


def _anonimizar_entrada_padrao(args) -> int:
    from .formatos import VazamentoDetectado
    from .formatos.texto import anonimizar_txt

    try:
        res = anonimizar_txt(sys.stdin.buffer.read(), _anonimizador(args), "entrada.txt")
    except VazamentoDetectado as erro:
        print(f"✗ entrada padrão: {erro}", file=sys.stderr)
        return 1
    sys.stdout.write(res.dados.decode("utf-8"))
    if args.relatorio:
        _gravar_relatorio(args.relatorio, res.resultados, args.incluir_valores)
    return 0


def _senha_do_cofre() -> str:
    return os.environ.get("THEMIS_SENHA_COFRE") or getpass.getpass("Senha para o cofre (mín. 12): ")


def cmd_anonimizar(args) -> int:
    """Anonimiza arquivos, pastas ou a entrada padrão.

    Pastas são percorridas (com ``--recursivo``, inclusive as subpastas) e a árvore é preservada na
    pasta de saída. Cada arquivo concluído é registrado no manifesto (``--manifesto``), que permite
    retomar um lote interrompido (``--retomar``).

    Returns:
        A maior gravidade do lote: ``0`` sucesso; ``1`` arquivo rejeitado (inválido, vazamento
        detectado na verificação, OCR indisponível) ou erro de uso; ``2`` erro interno; ``130``
        interrupção pelo usuário. Os demais arquivos do lote continuam sendo processados.
    """
    from . import lote
    from .cofre import MINIMO_SENHA
    from .configuracao import ConfiguracaoInvalida

    if args.entradas == ["-"]:
        return _anonimizar_entrada_padrao(args)
    if "-" in args.entradas:
        print("✗ a entrada padrão ('-') não pode ser combinada com arquivos.", file=sys.stderr)
        return 1
    if args.retomar and not args.manifesto:
        print("✗ --retomar exige --manifesto (o registro dos arquivos já concluídos).", file=sys.stderr)
        return 1
    try:
        cfg = _configuracao(args)
        tarefas = lote.coletar(args.entradas, args.recursivo)
    except (ConfiguracaoInvalida, FileNotFoundError) as erro:
        print(f"✗ {erro}", file=sys.stderr)
        return 1
    if not tarefas:
        extensoes = ", ".join(sorted(e.lstrip(".") for e in lote.EXTENSOES))
        print(f"✗ nenhum arquivo suportado encontrado (extensões: {extensoes}).", file=sys.stderr)
        return 1

    # Uma única entrada de arquivo com --saida que não é pasta: --saida é o próprio arquivo gerado.
    saida_arquivo = (bool(args.saida) and len(args.entradas) == 1 and Path(args.entradas[0]).is_file()
                     and not args.saida.endswith(("/", "\\")) and not Path(args.saida).is_dir())
    senha = _senha_do_cofre() if args.cofre else None
    if senha is not None and len(senha) < MINIMO_SENHA:
        print(f"✗ use uma senha com pelo menos {MINIMO_SENHA} caracteres para o cofre.", file=sys.stderr)
        return 1
    opcoes = lote.Opcoes(
        sobrepor=_sobrepor(args), config=_caminho_config(args), ocr=cfg.ocr and not args.sem_ocr,
        limite_bytes=args.limite_mb * 1024 * 1024, colunas_integrais=args.coluna_integral,
        saida=None if saida_arquivo else args.saida, arquivo_saida=args.saida if saida_arquivo else None,
        cofre=args.cofre, senha_cofre=senha, pdfa=args.pdfa,
    )
    if args.retomar:
        tarefas = _pendentes(tarefas, lote.concluidos(lote.ler_manifesto(args.manifesto), opcoes.identificador()))

    manifesto = lote.Manifesto(args.manifesto)
    concluidas, codigo = [], 0
    try:
        for linha in lote.executar(tarefas, opcoes, args.trabalhos):
            manifesto.registrar(linha)
            codigo = max(codigo, lote.CODIGOS[linha["situacao"]])
            if linha["situacao"] != lote.OK:
                print(f"✗ {linha['arquivo']}: {linha['mensagem']}", file=sys.stderr)
                continue
            concluidas.append(linha)
            print(f"✓ {linha['arquivo']} → {linha['saida']}  ({linha['tarjados']} tarjado(s), "
                  f"{linha['para_revisar']} para revisar)", file=sys.stderr)
            if "cofre" in linha:
                print(f"  ✓ cofre de reversão: {linha['cofre']} (guarde-o separado do documento)", file=sys.stderr)
            for aviso in linha["avisos"]:
                print(f"  ! {aviso}", file=sys.stderr)
    except KeyboardInterrupt:
        print("✗ interrompido: os arquivos concluídos estão registrados no manifesto.", file=sys.stderr)
        codigo = 130
    finally:
        manifesto.fechar()
    if args.relatorio and concluidas:
        resultados, documentos = lote.documentos_do_relatorio(concluidas)
        if resultados:
            _gravar_relatorio(args.relatorio, resultados, args.incluir_valores, documentos)
    return codigo


def _pendentes(tarefas: list, feitos: dict[str, dict]) -> list:
    """Tarefas ainda não concluídas: muda o conteúdo, a configuração ou falta a saída, o arquivo é refeito."""
    from . import lote

    pendentes = []
    for t in tarefas:
        anterior = feitos.get(t.relativo.as_posix())
        if (anterior and Path(anterior.get("saida", "")).exists()
                and anterior.get("sha256_entrada") == lote.sha256(t.caminho.read_bytes())):
            print(f"↷ {t.relativo}: já concluído com a mesma configuração (retomada)", file=sys.stderr)
            continue
        pendentes.append(t)
    return pendentes


def cmd_analisar(args) -> int:
    """Lista em JSON o que seria tarjado ou sinalizado em um texto, sem alterá-lo."""
    from .configuracao import ConfiguracaoInvalida

    try:
        anon = _anonimizador(args)
        texto = sys.stdin.read() if args.entrada == "-" else Path(args.entrada).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"✗ {args.entrada}: o texto não está em UTF-8; para outros formatos, use 'themis anonimizar'.",
              file=sys.stderr)
        return 1
    except (ConfiguracaoInvalida, ValueError) as erro:
        print(f"✗ {erro}", file=sys.stderr)
        return 1
    except OSError as erro:
        print(f"✗ {args.entrada}: não foi possível ler o arquivo ({erro.strerror}).", file=sys.stderr)
        return 1
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

    try:
        texto = Path(args.texto).read_text(encoding="utf-8")
        cofre = Path(args.cofre).read_bytes()
    except UnicodeDecodeError:
        print(f"✗ {args.texto}: o texto não está em UTF-8.", file=sys.stderr)
        return 1
    except OSError as erro:
        print(f"✗ não foi possível ler {erro.filename}: {erro.strerror}.", file=sys.stderr)
        return 1
    senha = os.environ.get("THEMIS_SENHA_COFRE") or getpass.getpass("Senha do cofre: ")
    try:
        print(reverter(texto, cofre, senha), end="")
    except ValueError as erro:
        print(f"✗ {erro}", file=sys.stderr)
        return 1
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


def _validar_config_servico(args) -> bool:
    """Valida ``--config`` antes de iniciar um serviço e o repassa pela variável ``THEMIS_CONFIG``."""
    from .configuracao import ConfiguracaoInvalida, carregar

    if args.config:
        os.environ["THEMIS_CONFIG"] = str(Path(args.config).resolve())
    try:
        carregar()
    except ConfiguracaoInvalida as erro:
        print(f"✗ {erro}", file=sys.stderr)
        return False
    return True


def cmd_interface(args) -> int:
    """Inicia a interface web local (Streamlit) com as opções de :data:`STREAMLIT_SEGURO`."""
    import subprocess  # noqa: S404  # nosec B404

    from .config import carregar

    if not _validar_config_servico(args):
        return 1
    app = Path(__file__).with_name("ui") / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app), "--server.port", str(args.porta),
           "--server.address", args.endereco, "--server.maxUploadSize", str(carregar().max_mb), *STREAMLIT_SEGURO]
    return subprocess.call(cmd)  # noqa: S603 - executa o próprio Streamlit, sem shell  # nosec B603


def cmd_api(args) -> int:
    """Inicia a API HTTP local, sem log de acesso e sem cabeçalho de identificação do servidor.

    Com ``--processos N``, as análises são distribuídas entre N processos de trabalho, num único
    processo HTTP — o que mantém as tarefas assíncronas consultáveis em qualquer requisição.
    """
    import uvicorn

    if not _validar_config_servico(args):
        return 1
    if args.processos:
        os.environ["THEMIS_PROCESSOS"] = str(args.processos)
    uvicorn.run("themis_lgpd.api.app:app", host=args.endereco, port=args.porta, access_log=False,
                server_header=False, proxy_headers=False)
    return 0


#: Endereços verificados por ``themis saude``: a API e a interface, nas portas padrão.
URLS_SAUDE = ("http://127.0.0.1:8000/saude", "http://127.0.0.1:8501/_stcore/health")


def cmd_saude(args) -> int:
    """Verifica se a API ou a interface local responde (uso: HEALTHCHECK de contêiner).

    Returns:
        ``0`` se algum dos endereços responder com HTTP 200; ``1`` caso contrário.
    """
    import urllib.error
    import urllib.request

    for url in args.url or URLS_SAUDE:
        if not url.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
            print(f"✗ {url}: a verificação só consulta endereços locais.", file=sys.stderr)
            return 1
        try:
            with urllib.request.urlopen(url, timeout=args.tempo) as resposta:  # noqa: S310  # nosec B310
                if resposta.status == 200:
                    return 0
        except (urllib.error.URLError, OSError):
            continue
    print("✗ nenhum serviço do Themis respondeu.", file=sys.stderr)
    return 1


def _opcoes_motor(p: argparse.ArgumentParser) -> None:
    """Opções comuns aos subcomandos que analisam texto."""
    p.add_argument("--config", metavar="ARQ",
                   help="configuração do órgão (themis.toml); padrão: variável THEMIS_CONFIG, se definida")
    p.add_argument("--perfil", help=f"{', '.join(PERFIS)} ou perfil do themis.toml (padrão: {PERFIL_PADRAO})")
    p.add_argument("--modo", choices=list(MODOS), help="como substituir (padrão: etiqueta)")
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

    a = sub.add_parser("anonimizar",
                       help="anonimiza arquivos e pastas (PDF, DOCX, XLSX, PPTX, ODT, ODS, CSV, TXT, HTML, EML, "
                            "PNG/JPG/TIFF, ZIP; DOC/XLS/PPT/RTF com o LibreOffice) ou '-' (stdin)")
    a.add_argument("entradas", nargs="+", help="arquivos e pastas; '-' lê a entrada padrão")
    a.add_argument("-o", "--saida",
                   help="arquivo ou pasta de saída, com a árvore das entradas (padrão: <nome>_anonimizado.<ext>)")
    a.add_argument("-R", "--recursivo", action="store_true", help="inclui as subpastas das pastas indicadas")
    a.add_argument("-j", "--trabalhos", type=int, default=1, metavar="N",
                   help="arquivos processados em paralelo (cada processo carrega o modelo: ~1 GB de memória)")
    a.add_argument("--manifesto", metavar="ARQ.jsonl",
                   help="manifesto de cadeia de custódia: uma linha por arquivo, com SHA-256 de entrada e saída")
    a.add_argument("--retomar", action="store_true",
                   help="pula arquivos já concluídos com a mesma configuração, conforme o manifesto")
    a.add_argument("-r", "--relatorio", help="relatório de tarjamento (.json, .csv, .xlsx ou .txt = nota de tarjamento)")
    a.add_argument("--coluna-integral", action="append", metavar="CABEÇALHO",
                   help="em planilhas, tarjar a coluna inteira (repetível)")
    a.add_argument("--sem-ocr", action="store_true", help="não usar OCR em páginas digitalizadas")
    a.add_argument("--pdfa", action="store_true",
                   help="PDFs em PDF/A-2b (arquivamento): páginas em imagem com camada de texto, sRGB e fontes "
                        "incorporadas")
    a.add_argument("--cofre", metavar="ARQ|PASTA",
                   help="(texto) cofre cifrado para reverter a pseudonimização: um arquivo para uma entrada ou "
                        "uma pasta com um .cofre por documento; senha via THEMIS_SENHA_COFRE")
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
    ui.add_argument("--config", metavar="ARQ", help="configuração do órgão (themis.toml)")
    ui.set_defaults(func=cmd_interface)

    api = sub.add_parser("api", help="inicia a API HTTP local")
    api.add_argument("--porta", type=int, default=8000)
    api.add_argument("--endereco", default="127.0.0.1")
    api.add_argument("--config", metavar="ARQ", help="configuração do órgão (themis.toml)")
    api.add_argument("--processos", type=int, metavar="N",
                     help="processos de análise em paralelo (cada um carrega o modelo: ~1 GB de memória)")
    api.set_defaults(func=cmd_api)

    d = sub.add_parser("reverter", help="reverte um texto pseudonimizado com o cofre e a senha")
    d.add_argument("texto")
    d.add_argument("cofre")
    d.set_defaults(func=cmd_reverter)

    s = sub.add_parser("saude", help="verifica se a API ou a interface local responde (HEALTHCHECK de contêiner)")
    s.add_argument("--url", action="append", help=f"endereço local a verificar (padrão: {', '.join(URLS_SAUDE)})")
    s.add_argument("--tempo", type=float, default=4.0, help="tempo máximo de cada tentativa, em segundos")
    s.set_defaults(func=cmd_saude)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
