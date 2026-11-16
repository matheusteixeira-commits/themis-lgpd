"""Ablação do classificador de trechos (``spancat``) no sistema completo, nas partições de seleção.

Cada configuração da grade — época do treino, limiar de cada rótulo (rótulo sem limiar fica desligado)
e limiar contextual — é avaliada com o Themis completo (perfil LAI) na seleção do esic-ner e na seleção
do corpus de documentos oficiais (``benchmark/oficial``) e, se pedido, nas partições de ajuste, pelos
mesmos critérios de ``benchmark/esic_ner.py`` e ``benchmark/avaliar_ouro.py``. Para cada configuração
são registradas as métricas agregadas, a diferença para a execução de referência (o sistema do ciclo
anterior, em ``benchmark/treino/ciclo1``) e a verificação dos portões do ciclo:

* esic-ner, seleção: nenhum rótulo perde mais de 0,5 ponto de recall e a tarja fora do gabarito não
  sobe mais de 0,5 ponto;
* documentos oficiais, seleção: precisão das tarjas e preservação de trechos públicos não caem mais de
  0,5 ponto e nenhum rótulo perde mais de 1 ponto de recall.

Só métricas agregadas são produzidas: os textos não são lidos fora do avaliador nem gravados. O
resultado por documento de cada configuração (só contagens) vai para ``--detalhes-dir``, para a
comparação pareada (``benchmark/treino/comparar_execucoes.py``).

A grade é um arquivo JSON com a lista de configurações::

    [{"nome": "saude_0.6", "epoca": 5, "limiares": {"DADO_SAUDE": 0.6},
      "limiares_contextuais": {"DADO_SAUDE": 0.95}, "decodificacao": "maximo"}]

``epoca`` (opcional) carrega os pesos gravados pelo treino em ``--pontos``; sem ela, valem os pesos do
artefato. ``decodificacao`` (opcional) é o modo de seleção dos trechos sobrepostos. ``"limiares": {}`` equivale ao sistema sem o classificador. A configuração é aplicada só neste
processo: os metadados e os pesos do artefato não são alterados.

Uso::

    python benchmark/treino/ablacao_spancat.py GRADE.json [--artefato pasta] [--pontos pasta]
        [--corpora esic_selecao oficial_selecao] [--saida benchmark/treino/ablacao_spancat.json] [--acrescentar]
    python benchmark/treino/ablacao_spancat.py --instalar DECISAO.json [--artefato pasta] [--pontos pasta]
        [--saida benchmark/treino/ablacao_spancat.json] [--destino src/themis_lgpd/dados/modelos/sensivel]

Com ``--instalar``, a configuração escolhida (``{"configuracao": nome, "descricao", "motivos" (rótulo →
motivo da desativação), "escolha_dos_limiares", "ativacao"}``) é gravada no artefato: pesos da época,
limiares, rótulos desativados e a grade resumida nos metadados; a decisão também vai para o relatório.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

PASTA = Path(__file__).parent
RAIZ = PASTA.parents[1]
sys.path.insert(0, str(PASTA.parent))
sys.path.insert(0, str(PASTA))

from avaliar_ouro import avaliar_documento  # noqa: E402
from esic_ner import agregadas, metricas, trechos_themis  # noqa: E402
from ouro.ferramentas import ler as ler_oficial  # noqa: E402
from particoes import carregar  # noqa: E402

OFICIAL = RAIZ / "benchmark" / "oficial"
CICLO1 = PASTA / "ciclo1"
#: Execução de referência de cada corpus (resultado por documento do sistema do ciclo anterior).
REFERENCIAS = {"esic_selecao": CICLO1 / "selecao_docs.jsonl", "oficial_selecao": CICLO1 / "oficial_selecao_docs.jsonl",
               "oficial_ajuste": CICLO1 / "oficial_ajuste_docs.jsonl"}
#: Tolerâncias dos portões (diferença máxima admitida em relação à referência).
TOLERANCIA_RECALL = {"esic_selecao": 0.005, "oficial_selecao": 0.01}
TOLERANCIA_TARJA_FORA = 0.005
TOLERANCIA_PRECISAO = 0.005


def ler_detalhes(arquivo: Path) -> list[dict]:
    return [json.loads(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines() if linha.strip()]


def avaliar(anon, corpus: str, dados: list[dict]) -> tuple[dict, list[dict]]:
    """Métricas agregadas e resultado por documento do sistema num corpus."""
    t0 = time.perf_counter()
    if corpus.startswith("esic"):
        trechos = trechos_themis(anon, [d["text"] for d in dados])
        detalhes: list[dict] = []
        res, _ = metricas(dados, trechos, time.perf_counter() - t0, "", detalhes)
        nao_tarjadas = res["nao_tarjadas"]["por_rotulo"]
        segundos = res["segundos_por_documento"]
    else:
        analises = anon.analisar_lote([d["texto"] for d in dados])
        segundos = round((time.perf_counter() - t0) / max(1, len(dados)), 4)
        detalhes = [avaliar_documento(d, ents) for d, ents in zip(dados, analises)]
        sinalizadas, nao_detectadas = Counter(), Counter()
        for x in detalhes:
            sinalizadas.update(x["sinalizadas"])
            nao_detectadas.update(x["nao_detectadas"])
        nao_tarjadas = {k: {"sinalizadas": sinalizadas[k], "nao_detectadas": nao_detectadas[k]}
                        for k in sorted(set(sinalizadas) | set(nao_detectadas))}
    saida: dict = {k: round(v, 4) for k, v in sorted(agregadas(detalhes).items())}
    saida["nao_tarjadas"] = nao_tarjadas
    saida["segundos_por_documento"] = segundos
    return saida, detalhes


def diferencas(atual: dict, referencia: dict) -> dict:
    """Diferença ``atual - referência`` de cada métrica agregada."""
    return {k: round(atual[k] - referencia[k], 4) for k in sorted(atual.keys() & referencia.keys())
            if isinstance(atual[k], float) and k != "segundos_por_documento"}


def portoes(dif: dict) -> dict:
    """Verificação dos portões do ciclo (ver a descrição do módulo) a partir das diferenças por corpus."""
    saida: dict = {}
    for corpus, tolerancia in TOLERANCIA_RECALL.items():
        if corpus not in dif:
            continue
        perdas = {k.split(":", 1)[1]: v for k, v in dif[corpus].items() if k.startswith("recall:") and v < -tolerancia}
        saida[f"{corpus}:recall_por_rotulo"] = not perdas
        if perdas:
            saida[f"{corpus}:perdas"] = perdas
    if "esic_selecao" in dif:
        saida["esic_selecao:tarja_fora_do_gabarito"] = dif["esic_selecao"]["tarja_fora_do_gabarito"] <= TOLERANCIA_TARJA_FORA
    if "oficial_selecao" in dif:
        for chave in ("precisao_tarjas", "preservacao_publicos"):
            saida[f"oficial_selecao:{chave}"] = dif["oficial_selecao"][chave] >= -TOLERANCIA_PRECISAO
    saida["aprovada"] = all(v for k, v in saida.items() if not k.endswith(":perdas"))
    return saida


def carregar_corpus(corpus: str) -> list[dict]:
    """Documentos de ``esic_selecao``, ``esic_ajuste``, ``oficial_selecao`` ou ``oficial_ajuste``."""
    fonte, particao = corpus.split("_", 1)
    return carregar(particao) if fonte == "esic" else ler_oficial(OFICIAL / f"{particao}.jsonl")


#: Métricas de cada configuração copiadas para a grade resumida dos metadados do artefato.
RESUMO_GRADE = {"esic_selecao": ("recall_entidades", "recall:DADO_SAUDE", "recall:NOME_PESSOA", "tarja_fora_do_gabarito"),
                "oficial_selecao": ("recall_entidades", "recall:DADO_SAUDE", "recall:NOME_PESSOA", "recall:DADO_SENSIVEL",
                                    "recall:QUASI_IDENTIFICADOR", "precisao_tarjas", "preservacao_publicos")}


def instalar(relatorio: dict, decisao: dict, artefato: Path, pontos: Path, destino: Path,
             relatorio_treino: Path | None = None) -> dict:
    """Grava em ``destino`` os pesos e os metadados da configuração escolhida (``decisao["configuracao"]``).

    Os metadados recebem os limiares, o modo de decodificação, os rótulos desativados com o motivo, a
    época escolhida, as métricas da configuração e a grade resumida de todas as configurações avaliadas.
    """
    escolhida = next(g for g in relatorio["grade"] if g["nome"] == decisao["configuracao"])
    meta = json.loads((artefato / "meta.json").read_text(encoding="utf-8"))
    destino.mkdir(parents=True, exist_ok=True)
    if artefato.resolve() != destino.resolve():
        for nome in ("cfg", "config.json"):
            shutil.copyfile(artefato / nome, destino / nome)
    epoca = escolhida["epoca"]
    pesos = (pontos / f"epoca_{epoca:02d}.bin").read_bytes() if epoca else (artefato / "model").read_bytes()
    (destino / "model").write_bytes(pesos)
    if epoca and relatorio_treino is not None:
        epocas = json.loads(relatorio_treino.read_text(encoding="utf-8"))["epocas"]
        registro = next(e for e in epocas if e["epoca"] == epoca)
        meta["selecao"] = {"f1_medio": registro["f1_medio_selecao"],
                           **{c: v["melhor_por_rotulo"] for c, v in registro["selecao"].items()}}
    # Sem época na configuração, os pesos são os do artefato, e a época registrada nele continua valendo.
    meta["treino"]["epoca_escolhida"] = epoca or meta["treino"].get("epoca_escolhida") or meta["treino"].get("melhor_epoca")
    meta.update({
        "descricao": decisao["descricao"],
        "limiares": escolhida["limiares"],
        "limiares_contextuais": escolhida["limiares_contextuais"],
        "decodificacao": escolhida["decodificacao"],
        "rotulos_desativados": {r: decisao["motivos"][r] for r in meta["rotulos"] if r not in escolhida["limiares"]},
        "ativo_por_padrao": True,
        "sha256_model": hashlib.sha256(pesos).hexdigest(),
        "escolha_dos_limiares": decisao["escolha_dos_limiares"],
        "ativacao": decisao["ativacao"],
        "escolha": {"configuracao": escolhida["nome"], "epoca": epoca,
                    **{c: {k: escolhida[c][k] for k in chaves if k in escolhida[c]} for c, chaves in RESUMO_GRADE.items()},
                    "diferenca_para_ciclo_anterior": escolhida["diferenca_para_referencia"],
                    "portoes": escolhida["portoes"]},
        "grade": [{"configuracao": g["nome"], "epoca": g["epoca"], "limiares": g["limiares"],
                   "limiares_contextuais": g["limiares_contextuais"], "decodificacao": g["decodificacao"],
                   **{c: {k: g[c][k] for k in chaves if k in g[c]} for c, chaves in RESUMO_GRADE.items() if c in g},
                   "aprovada": g["portoes"]["aprovada"]} for g in relatorio["grade"]],
    })
    (destino / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                                       newline="\n")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("grade", type=Path, nargs="?", help="arquivo JSON com a lista de configurações")
    ap.add_argument("--artefato", type=Path, help="pasta do artefato (padrão: o instalado no pacote)")
    ap.add_argument("--pontos", type=Path, default=RAIZ / ".trabalho" / "pontos_spancat",
                    help="pasta com os pesos de cada época gravados pelo treino")
    ap.add_argument("--corpora", nargs="+", default=["esic_selecao", "oficial_selecao"],
                    choices=["esic_selecao", "oficial_selecao", "esic_ajuste", "oficial_ajuste"])
    ap.add_argument("--saida", type=Path, default=PASTA / "ablacao_spancat.json")
    ap.add_argument("--acrescentar", action="store_true", help="acrescenta as configurações a um relatório existente")
    ap.add_argument("--detalhes-dir", type=Path, default=RAIZ / ".trabalho" / "ablacao")
    ap.add_argument("--instalar", type=Path, metavar="DECISAO.json",
                    help="em vez de avaliar, grava no artefato a configuração escolhida (ver instalar)")
    ap.add_argument("--destino", type=Path, default=RAIZ / "src" / "themis_lgpd" / "dados" / "modelos" / "sensivel")
    ap.add_argument("--relatorio-treino", type=Path, default=PASTA / "resultado_spancat.json")
    args = ap.parse_args()
    if args.instalar:
        relatorio = json.loads(args.saida.read_text(encoding="utf-8"))
        decisao = json.loads(args.instalar.read_text(encoding="utf-8"))
        meta = instalar(relatorio, decisao, args.artefato or args.destino, args.pontos, args.destino,
                        args.relatorio_treino if args.relatorio_treino.exists() else None)
        relatorio["decisao"] = {**decisao, "sha256_model": meta["sha256_model"]}
        args.saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                              newline="\n")
        print(json.dumps(meta["escolha"], ensure_ascii=False, indent=1))
        return
    args.detalhes_dir.mkdir(parents=True, exist_ok=True)
    grade = json.loads(args.grade.read_text(encoding="utf-8"))

    os.environ["THEMIS_MODELO_SENSIVEL"] = "1"
    from themis_lgpd.reconhecedores import aprendido

    if args.artefato:
        aprendido.PASTA = args.artefato.resolve()
    aprendido.metadados.cache_clear()
    meta_original = aprendido.metadados()
    if meta_original is None:
        raise SystemExit("artefato do classificador não encontrado")
    from themis_lgpd import Anonimizador
    from themis_lgpd.analisador import obter_analisador

    anon = Anonimizador(perfil="lai")
    componente = obter_analisador("pt_core_news_lg").nlp_engine.nlp["pt"].get_pipe(aprendido.NOME_COMPONENTE)
    pesos_originais = componente.model.to_bytes()
    dados = {c: carregar_corpus(c) for c in args.corpora}
    referencias = {c: {k: round(v, 4) for k, v in agregadas(ler_detalhes(REFERENCIAS[c])).items()}
                   for c in args.corpora if c in REFERENCIAS}

    relatorio: dict = {"grade": []}
    if args.acrescentar and args.saida.exists():
        relatorio = json.loads(args.saida.read_text(encoding="utf-8"))
    relatorio["artefato"] = {"rotulos": meta_original["rotulos"], "sha256_model": meta_original.get("sha256_model"),
                             "melhor_epoca_do_treino": meta_original.get("treino", {}).get("melhor_epoca")}
    relatorio.setdefault("referencia", {}).update(referencias)
    for config in grade:
        epoca = config.get("epoca")
        componente.model.from_bytes((args.pontos / f"epoca_{epoca:02d}.bin").read_bytes() if epoca else pesos_originais)
        meta = {**meta_original, "limiares": config["limiares"],
                "limiares_contextuais": config.get("limiares_contextuais", {}),
                "decodificacao": config.get("decodificacao", meta_original.get("decodificacao", "maximo"))}
        aprendido.metadados = lambda meta=meta: meta  # só neste processo
        item: dict = {"nome": config["nome"], "epoca": epoca, "limiares": config["limiares"],
                      "limiares_contextuais": meta["limiares_contextuais"], "decodificacao": meta["decodificacao"]}
        dif = {}
        for corpus, docs in dados.items():
            res, detalhes = avaliar(anon, corpus, docs)
            (args.detalhes_dir / f"{config['nome']}__{corpus}.jsonl").write_text(
                "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in detalhes), encoding="utf-8", newline="\n")
            item[corpus] = res
            if corpus in referencias:
                dif[corpus] = diferencas(res, referencias[corpus])
        item["diferenca_para_referencia"] = dif
        item["portoes"] = portoes(dif)
        relatorio["grade"] = [g for g in relatorio["grade"] if g["nome"] != item["nome"]] + [item]
        resumo = {c: {k: dif[c][k] for k in ("recall_entidades", "recall:DADO_SAUDE", "recall:NOME_PESSOA",
                                             "recall:DADO_SENSIVEL", "precisao_tarjas", "preservacao_publicos",
                                             "tarja_fora_do_gabarito") if k in dif[c]} for c in dif}
        print(json.dumps({"nome": item["nome"], "diferenca": resumo, "aprovada": item["portoes"]["aprovada"]},
                         ensure_ascii=False), flush=True)
        args.saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                              newline="\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
