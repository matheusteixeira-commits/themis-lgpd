"""Comparação entre sistemas no esic-ner e na avaliação sintética, com os mesmos critérios.

Sistemas comparados:

* **Presidio puro (pt)**: ``AnalyzerEngine`` com o modelo ``pt_core_news_lg`` e os reconhecedores
  genéricos do Presidio (SpacyRecognizer, e-mail, telefone com região BR, cartão, IP, IBAN, URL,
  data, criptomoeda, MAC e UUID); tudo o que for detectado é tarjado. Representa o resultado de
  configurar o Presidio para português sem reconhecedores brasileiros.
* **Themis LGPD**, na versão instalada, com o perfil LAI.
* Opcionalmente, outra versão do Themis (``--outro-src caminho/src``), executada em subprocesso
  para não misturar os dois códigos-fonte no mesmo interpretador.

O resultado é gravado em ``benchmark/COMPARACAO.md`` (tabela) e ``benchmark/COMPARACAO.json``.

Uso::

    python benchmark/comparar.py [--n 1000] [--semente 7] [--outro-src ../outra-versao/src --outro-rotulo "Themis 1.0"]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from esic_ner import carregar, metricas, trechos_themis  # noqa: E402
from sintetico import avaliar, gerar  # noqa: E402


def presidio_puro():
    """Monta o Presidio sem reconhecedores brasileiros.

    Returns:
        ``(trechos, anonimizar)``: funções que recebem uma lista de textos e devolvem,
        respectivamente, os trechos detectados (todos com ação ``tarjar``) e os textos anonimizados.
    """
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_analyzer.predefined_recognizers import (
        CreditCardRecognizer,
        CryptoRecognizer,
        DateRecognizer,
        EmailRecognizer,
        IbanRecognizer,
        IpRecognizer,
        MacAddressRecognizer,
        PhoneRecognizer,
        SpacyRecognizer,
        UrlRecognizer,
        UuidRecognizer,
    )
    from presidio_anonymizer import AnonymizerEngine

    nlp = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy", "models": [{"lang_code": "pt", "model_name": "pt_core_news_lg"}]}).create_engine()
    registro = RecognizerRegistry(supported_languages=["pt"])
    for cls in (SpacyRecognizer, CreditCardRecognizer, CryptoRecognizer, DateRecognizer, EmailRecognizer,
                IbanRecognizer, IpRecognizer, MacAddressRecognizer, UrlRecognizer, UuidRecognizer):
        registro.add_recognizer(cls(supported_language="pt"))
    registro.add_recognizer(PhoneRecognizer(supported_language="pt", supported_regions=("BR",)))
    engine = AnalyzerEngine(registry=registro, nlp_engine=nlp, supported_languages=["pt"])
    anonimizador = AnonymizerEngine()

    def trechos(textos):
        return [[(r.start, r.end, "tarjar") for r in engine.analyze(text=t, language="pt")] for t in textos]

    def anonimizar(textos):
        return [anonimizador.anonymize(text=t, analyzer_results=engine.analyze(text=t, language="pt")).text
                for t in textos]

    return trechos, anonimizar


def medir(rotulo, trechos_fn, anonimizar_fn, dados, docs_sint, ignorar_cnpj):
    """Avalia um sistema nos dois conjuntos.

    Args:
        rotulo: Nome do sistema na tabela.
        trechos_fn: Função ``list[str] -> list[list[(início, fim, ação)]]`` (ver ``esic_ner.metricas``).
        anonimizar_fn: Função ``list[str] -> list[str]`` (ver ``sintetico.avaliar``).
        dados: Documentos do esic-ner.
        docs_sint: Documentos da avaliação sintética.
        ignorar_cnpj: Exclui o CNPJ da avaliação sintética (público no perfil LAI).
    """
    t0 = time.perf_counter()
    trechos = trechos_fn([d["text"] for d in dados])
    esic, _ = metricas(dados, trechos, time.perf_counter() - t0, rotulo)
    sint = avaliar("lai", docs_sint, anonimizar_fn, ignorar_cnpj=ignorar_cnpj)
    return {"sistema": rotulo, "esic_ner": esic, "sintetico": sint}


def outro_themis(src: str, rotulo: str, n: int, semente: int) -> dict:
    """Mede outra versão do Themis em subprocesso, com o código-fonte dela no ``PYTHONPATH``.

    Usa os scripts de avaliação da própria versão comparada (``<raiz>/benchmark``), com o mesmo
    número de documentos e a mesma semente da avaliação sintética.
    """
    raiz = Path(src).resolve().parent
    env = {**os.environ, "PYTHONPATH": str(Path(src).resolve()), "PYTHONIOENCODING": "utf-8"}
    saida_esic = raiz / "esic.json"
    subprocess.run([sys.executable, str(raiz / "benchmark" / "esic_ner.py"), "--json", str(saida_esic)],  # noqa: S603
                   env=env, check=True, capture_output=True, cwd=raiz)
    sint = subprocess.run([sys.executable, str(raiz / "benchmark" / "sintetico.py"), "--n", str(n),  # noqa: S603
                           "--semente", str(semente)], env=env, check=True, capture_output=True, cwd=raiz)
    return {"sistema": rotulo, "esic_ner": json.loads(saida_esic.read_text(encoding="utf-8")),
            "sintetico": json.loads(sint.stdout.decode("utf-8"))}


def tabela(res: list[dict]) -> str:
    """Tabela Markdown com as principais métricas, um sistema por coluna."""
    linhas = ["| Métrica | " + " | ".join(r["sistema"] for r in res) + " |",
              "|---|" + "---|" * len(res)]

    def lin(nome, f):
        linhas.append(f"| {nome} | " + " | ".join(f(r) for r in res) + " |")

    pct = "{:.1%}".format
    lin("esic-ner: entidades pessoais tarjadas", lambda r: pct(r["esic_ner"]["recall_entidades"]))
    lin("esic-ner: nomes tarjados", lambda r: pct(r["esic_ner"]["recall_por_rotulo"].get("NOME_PESSOA", 0)))
    lin("esic-ner: documentos pessoais tarjados", lambda r: pct(r["esic_ner"]["recall_por_rotulo"].get("DOC_PESSOAL", 0)))
    lin("esic-ner: datas de nascimento tarjadas", lambda r: pct(r["esic_ner"]["recall_por_rotulo"].get("DATA_NASC", 0)))
    lin("esic-ner: pedidos com algum vazamento", lambda r: pct(r["esic_ner"]["documentos_com_vazamento"]))
    lin("esic-ner: F1 de triagem", lambda r: f"{r['esic_ner']['triagem']['f1']:.3f}")
    lin("esic-ner: tarja fora do gabarito (excesso)", lambda r: pct(r["esic_ner"]["tarja_fora_do_gabarito"]))
    lin("esic-ner: ms por pedido", lambda r: f"{1000 * r['esic_ner']['segundos_por_documento']:.0f}")
    lin("sintético: identificadores tarjados", lambda r: pct(r["sintetico"]["recall"]))
    lin("sintético: documentos com vazamento", lambda r: pct(r["sintetico"]["documentos_com_vazamento"]))
    return "\n".join(linhas)


def main() -> None:
    """Executa a comparação pela linha de comando."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--semente", type=int, default=7)
    ap.add_argument("--outro-src", help="src/ de outra versão do Themis para comparar")
    ap.add_argument("--outro-rotulo", default="Themis (outra versão)")
    ap.add_argument("--saida", type=Path, default=AQUI / "COMPARACAO.md")
    args = ap.parse_args()

    from themis_lgpd import Anonimizador, __version__

    dados = carregar("test")
    docs = gerar(args.n, args.semente)
    resultados = []
    trechos_p, anon_p = presidio_puro()
    resultados.append(medir("Presidio puro (pt)", trechos_p, anon_p, dados, docs, ignorar_cnpj=True))
    if args.outro_src:
        resultados.append(outro_themis(args.outro_src, args.outro_rotulo, args.n, args.semente))
    anon = Anonimizador("lai")
    resultados.append(medir(f"Themis {__version__} (sobre o Presidio)", lambda t: trechos_themis(anon, t),
                            lambda t: [r.texto for r in anon.anonimizar_lote(t)], dados, docs, ignorar_cnpj=True))
    md = (f"# Comparação\n\nesic-ner (teste, {len(dados)} pedidos) e benchmark sintético ({args.n} documentos, "
          f"semente {args.semente}); perfil LAI do Themis. Gerado por `benchmark/comparar.py`.\n\n"
          + tabela(resultados) + "\n")
    args.saida.write_text(md, encoding="utf-8")
    (args.saida.with_suffix(".json")).write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
