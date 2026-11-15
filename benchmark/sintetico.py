"""Avaliação sintética e reprodutível com todos os identificadores brasileiros.

Gera pedidos de acesso à informação fictícios — nomes do Faker (pt_BR), documentos com dígitos
verificadores válidos e, para o CPF, também inválidos — em formatações variadas: texto todo em
minúsculas, em CAIXA ALTA, com quebras de linha e com ruído de OCR em números. Mede a fração de
cada tipo de dado que não permaneceu legível no texto anonimizado.

Os documentos são gerados a partir de uma semente fixa, de modo que o resultado é reprodutível e
pode ser usado como trava de regressão na integração contínua (opção ``--minimo``).

Uso::

    python benchmark/sintetico.py [--n 400] [--semente 2026] [--perfil lai] [--minimo 0.99]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter

from faker import Faker

from themis_lgpd import Anonimizador
from themis_lgpd import validadores as v


def _ocr(s: str, rng: random.Random) -> str:
    """Simula erros de OCR, trocando cada "0", "1" e "5" por letra semelhante com probabilidade de 25%."""
    trocas = {"0": "O", "1": "l", "5": "S"}
    return "".join(trocas[c] if c in trocas and rng.random() < 0.25 else c for c in s)


def gerar(n: int, semente: int) -> list[tuple[str, list[tuple[str, str]]]]:
    """Gera ``n`` documentos fictícios.

    Returns:
        Para cada documento, o texto e a lista ``(tipo, valor)`` dos dados que devem ser tarjados.
    """
    rng = random.Random(semente)  # dados fictícios reprodutíveis, não segredos  # nosec B311
    fk = Faker("pt_BR")
    fk.seed_instance(semente)
    docs = []
    for _ in range(n):
        nome = fk.name()
        # 20% dos CPFs são aleatórios, quase sempre com dígito verificador inválido: devem ser
        # tarjados pela presença da palavra "CPF" (falhar fechado).
        cpf = v.gerar_cpf(rng) if rng.random() < 0.8 else f"{rng.randint(100, 999)}.{rng.randint(100, 999)}." \
                                                          f"{rng.randint(100, 999)}-{rng.randint(10, 99)}"
        if rng.random() < 0.2:
            cpf = cpf.replace(".", "").replace("-", "")
        tel = f"({rng.choice(['61', '11', '21', '31'])}) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
        email = fk.email()
        itens = [("NOME", nome), ("CPF", cpf), ("TELEFONE", tel), ("EMAIL", email)]
        extras = [
            ("RG", f"RG {rng.randint(1, 9)}.{rng.randint(100, 999)}.{rng.randint(100, 999)} SSP/DF"),
            ("CNH", f"CNH {v.gerar_cnh(rng)}"),
            ("PIS", f"PIS {v.gerar_pis(rng)}"),
            ("TITULO_ELEITOR", f"título de eleitor {v.gerar_titulo(rng)}"),
            ("CNS", f"cartão SUS {v.gerar_cns(rng)}"),
            ("PLACA", f"placa {rng.choice(['JKL', 'PAV', 'OVM'])}{rng.randint(0, 9)}{rng.choice('ABCDEFGHJ')}"
                      f"{rng.randint(10, 99)}"),
            ("PROCESSO_JUDICIAL", f"processo {v.gerar_processo_cnj(rng)}"),
            ("PROCESSO_ADMINISTRATIVO", f"processo SEI {rng.randint(10, 99999):05d}-{rng.randint(1, 99999999):08d}/"
                                        f"{rng.randint(2015, 2026)}-{rng.randint(10, 99)}"),
            ("CEP", f"CEP {rng.randint(70000, 73999)}-{rng.randint(100, 999)}"),
            ("ENDERECO", f"moro na QNM {rng.randint(1, 40)} Conjunto {rng.choice('ABCDEFGH')} Casa {rng.randint(1, 40)}"),
            ("DATA_NASCIMENTO", f"nascido em {rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(1950, 2005)}"),
            ("CONTA_BANCARIA", f"conta corrente {rng.randint(10000, 999999)}-{rng.randint(0, 9)}"),
            ("CARTAO", f"cartão de crédito {v.gerar_cartao(rng)}"),
            ("CNPJ", f"CNPJ {v.gerar_cnpj(rng, alfanumerico=rng.random() < 0.5)}"),
            ("MATRICULA", f"matrícula {rng.randint(100, 999)}.{rng.randint(100, 999)}-{rng.randint(0, 9)}"),
            ("IP", f"IP {rng.randint(11, 223)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"),
        ]
        rng.shuffle(extras)
        frases = [f"Eu, {nome}, CPF {cpf}, telefone {tel}, e-mail {email},"]
        for tipo, trecho in extras[: rng.randint(3, 7)]:
            frases.append(trecho + ",")
            # O valor esperado é o trecho sem a primeira palavra (o rótulo). Em endereço e RG o
            # trecho inteiro é guardado e o rótulo é descartado na avaliação.
            itens.append((tipo, trecho.split(" ", 1)[1] if tipo not in {"ENDERECO", "RG"} else trecho))
        frases.append("solicito cópia do meu processo.")
        texto = " ".join(frases)
        variante = rng.random()
        if variante < 0.15:
            texto = texto.lower()
            itens = [(t, x.lower()) for t, x in itens]
        elif variante < 0.25:
            texto = texto.upper()
            itens = [(t, x.upper()) for t, x in itens]
        elif variante < 0.35:
            # O valor esperado passa a ser a versão com ruído, que é a que aparece no texto.
            com_ruido = []
            for tipo, x in itens:
                if any(c.isdigit() for c in x) and "@" not in x:
                    ruidoso = _ocr(x, rng)
                    texto = texto.replace(x, ruidoso)
                    com_ruido.append((tipo, ruidoso))
                else:
                    com_ruido.append((tipo, x))
            itens = com_ruido
        elif variante < 0.45:
            texto = texto.replace(", ", ",\n", 3)
        docs.append((texto, itens))
    return docs


def avaliar(perfil: str, docs, anonimizar_textos=None, ignorar_cnpj: bool | None = None) -> dict:
    """Mede quanto de cada tipo de dado permaneceu legível após a anonimização.

    Um valor é considerado vazado se aparecer literalmente no texto de saída ou se suas letras e
    dígitos (quatro ou mais) aparecerem em sequência no texto de saída sem pontuação.

    Args:
        perfil: Perfil do Themis avaliado.
        docs: Documentos produzidos por :func:`gerar`.
        anonimizar_textos: Função ``list[str] -> list[str]`` que anonimiza os textos; permite
            avaliar outro sistema com os mesmos documentos. Por padrão, usa o Themis.
        ignorar_cnpj: Exclui o CNPJ da avaliação; por padrão, apenas no perfil LAI, em que o CNPJ é
            informação pública e permanece visível.

    Returns:
        Recall geral e por tipo, fração de documentos com vazamento e tempo por documento.
    """
    if anonimizar_textos is None:
        anon = Anonimizador(perfil)

        def anonimizar_textos(textos):
            return [r.texto for r in anon.anonimizar_lote(textos)]
    if ignorar_cnpj is None:
        ignorar_cnpj = perfil == "lai"
    total, ok = Counter(), Counter()
    vazados = 0
    t0 = time.perf_counter()
    saidas = anonimizar_textos([d[0] for d in docs])
    duracao = time.perf_counter() - t0
    for (_texto, itens), saida in zip(docs, saidas):
        vazou = False
        compacto = "".join(c for c in saida if c.isalnum())
        for tipo, valor in itens:
            if tipo == "CNPJ" and ignorar_cnpj:
                continue
            alvo = valor.split(" ", 1)[-1] if tipo in {"ENDERECO", "RG"} else valor
            digitos = "".join(c for c in alvo if c.isalnum())
            restou = len(digitos) >= 4 and digitos in compacto
            total[tipo] += 1
            if not restou and alvo not in saida:
                ok[tipo] += 1
            else:
                vazou = True
        vazados += vazou
    return {
        "perfil": perfil, "documentos": len(docs), "segundos_por_documento": round(duracao / max(1, len(docs)), 4),
        "recall": round(sum(ok.values()) / max(1, sum(total.values())), 4),
        "recall_por_tipo": {k: round(ok[k] / total[k], 4) for k in sorted(total)},
        "documentos_com_vazamento": round(vazados / max(1, len(docs)), 4),
    }


def main() -> int:
    """Executa a avaliação pela linha de comando; devolve 1 se o recall ficar abaixo de ``--minimo``."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--semente", type=int, default=2026)
    ap.add_argument("--perfil", default="lai")
    ap.add_argument("--minimo", type=float, default=0.0, help="falha (código 1) se o recall ficar abaixo")
    args = ap.parse_args()
    res = avaliar(args.perfil, gerar(args.n, args.semente))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["recall"] >= args.minimo else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
