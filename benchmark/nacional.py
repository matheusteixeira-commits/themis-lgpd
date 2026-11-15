"""Benchmark sintético de cobertura nacional: endereços e identificadores das 27 unidades da federação.

O conjunto esic-ner é dominado por pedidos do Distrito Federal; este benchmark mede o que um órgão de
qualquer estado encontra. Cada documento fictício traz uma pessoa, um endereço de uma UF sorteada —
com município real (lista do IBGE em ``src/themis_lgpd/dados/municipios.txt``) e os padrões de
endereçamento da região — e identificadores de abrangência nacional.

Padrões de endereço gerados:

* urbanos: logradouro com nome e número, abreviações (Av., Trav., Pça.), ruas numeradas ou com
  letra e quadra/lote (Goiânia, Palmas, conjuntos habitacionais), complementos (apartamento, sala,
  bloco) e bairro;
* rurais e regionais: sítio, fazenda e chácara sem número, povoado, assentamento, aldeia,
  comunidade, linha e lote (Rondônia), ramal (Amazônia), gleba, loteamento e trecho;
* rodovias estaduais das 27 UFs com quilômetro.

Identificadores: número de benefício do INSS, RENAVAM, chassi, recibo do CAR, matrícula de certidão,
prontuário, matrícula funcional estadual, registro em conselho com região, processos de sistemas
estaduais e RG de outras UFs.

Um valor é considerado vazado se o seu núcleo identificador (nome do logradouro ou da propriedade,
número do identificador) aparecer na saída, comparado só por letras e dígitos.

Há dois conjuntos de documentos pessoais:

* ``desenvolvimento``: frases no modelo "Eu, Fulano, residente em …", usadas para ajustar as regras;
* ``validacao``: outras redações (formulário "Endereço:", terceira pessoa, pedido de
  correspondência), outros nomes de logradouros e propriedades e outros rótulos dos identificadores.
  Não é usado para ajustar regras: mede a generalização.

E um conjunto de **textos públicos** (prefeituras, obras em rodovias, assentamentos e comunidades
citados em notícias, ruas sem número, Fazenda Pública), em que nada deve ser tarjado: mede o excesso
de tarja, a outra face da qualidade. O resultado traz a fração de termos públicos preservados e a
fração de documentos públicos sem nenhuma tarja.

Uso::

    python benchmark/nacional.py --n 1000 --semente 7 --perfil lai --conjunto validacao
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter, defaultdict
from importlib import resources

from faker import Faker

from themis_lgpd import Anonimizador
from themis_lgpd import validadores as v

#: Região de cada UF, para os recortes regionais.
REGIOES = {
    "Norte": ("AC", "AM", "AP", "PA", "RO", "RR", "TO"),
    "Nordeste": ("AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"),
    "Centro-Oeste": ("DF", "GO", "MS", "MT"),
    "Sudeste": ("ES", "MG", "RJ", "SP"),
    "Sul": ("PR", "RS", "SC"),
}
REGIAO_DA_UF = {uf: regiao for regiao, ufs in REGIOES.items() for uf in ufs}

_NOMES_RUA = ["das Acácias", "XV de Novembro", "Sete de Setembro", "Padre Eutíquio", "Barão do Rio Branco",
              "Tiradentes", "Duque de Caxias", "das Palmeiras", "Getúlio Vargas", "São Benedito", "Floriano Peixoto",
              "Marechal Deodoro", "Santos Dumont", "da Liberdade", "Bom Jesus", "Coronel Antônio Pinheiro"]
_PROPRIEDADES = ["Santa Rita", "Boa Esperança", "São José", "Três Irmãos", "Bela Vista", "Primavera", "Recanto Verde",
                 "Água Limpa", "Santa Luzia", "Paraíso"]
_BAIRROS = ["Centro", "Jardim América", "Setor Bueno", "Boa Viagem", "Cidade Nova", "Vila Nova", "Petrópolis",
            "São Cristóvão", "Aldeota", "Umarizal"]


def municipios() -> dict[str, list[str]]:
    """Municípios do IBGE por UF."""
    texto = resources.files("themis_lgpd.dados").joinpath("municipios.txt").read_text(encoding="utf-8")
    por_uf: dict[str, list[str]] = defaultdict(list)
    for linha in texto.splitlines():
        if linha and not linha.startswith("#"):
            nome, uf = linha.split("|")
            por_uf[uf].append(nome)
    return por_uf


def _endereco(rng: random.Random, uf: str, cidade: str) -> tuple[str, str, str]:
    """Endereço fictício: ``(tipo, frase, núcleo que não pode sobrar)``."""
    n = rng.randint(2, 2400)
    nome = rng.choice(_NOMES_RUA)
    bairro = rng.choice(_BAIRROS)
    propriedade = rng.choice(_PROPRIEDADES)
    q, lt = rng.randint(1, 90), rng.randint(1, 40)
    opcoes = [
        ("URBANO", f"Rua {nome}, nº {n}, bairro {bairro}, {cidade}/{uf}", f"{nome}, nº {n}"),
        ("URBANO", f"Av. {nome}, {n}, apto {rng.randint(101, 1504)}, {cidade} - {uf}", f"{nome}, {n}"),
        ("URBANO", f"Trav. {nome}, {n}, {bairro}, {cidade}/{uf}", f"{nome}, {n}"),
        ("URBANO", f"Pça. {nome}, {n}, sala {rng.randint(1, 30)}, {cidade}/{uf}", f"{nome}, {n}"),
        ("NUMERADO", f"Rua {rng.randint(1, 250)}, Qd. {q}, Lt. {lt}, {bairro}, {cidade}/{uf}", f"Qd. {q}, Lt. {lt}"),
        ("NUMERADO", f"Rua {rng.choice('ABCDEFGH')}{rng.randint(1, 30)}, nº {n}, {cidade}/{uf}", f"nº {n}"),
        ("RURAL", f"Sítio {propriedade}, zona rural de {cidade}/{uf}", f"Sítio {propriedade}"),
        ("RURAL", f"Fazenda {propriedade}, município de {cidade}/{uf}", f"Fazenda {propriedade}"),
        ("RURAL", f"Povoado {propriedade}, {cidade}/{uf}", f"Povoado {propriedade}"),
        ("RURAL", f"Assentamento {propriedade}, lote {lt}, {cidade}/{uf}", f"Assentamento {propriedade}"),
        ("RURAL", f"Linha {rng.randint(1, 200)}, Lote {lt}, Gleba {rng.randint(1, 30)}, {cidade}/{uf}",
         f"Lote {lt}, Gleba"),
        ("RURAL", f"Ramal do {propriedade}, km {rng.randint(1, 80)}, {cidade}/{uf}", f"Ramal do {propriedade}"),
        ("RODOVIA", f"{uf}-{rng.randint(10, 499):03d}, km {rng.randint(1, 300)}, {cidade}/{uf}", None),
    ]
    tipo, frase, nucleo = rng.choice(opcoes)
    if nucleo is None:  # rodovia: o trecho "UF-123, km 45" é o núcleo
        nucleo = frase.split(f", {cidade}")[0]
    return tipo, frase, nucleo


def _identificadores(rng: random.Random, uf: str) -> list[tuple[str, str, str]]:
    """Identificadores fictícios: ``(tipo, frase, valor que não pode sobrar)``."""
    nb = f"{rng.randint(100, 999)}.{rng.randint(100, 999)}.{rng.randint(100, 999)}-{rng.randint(0, 9)}"
    renavam = v.gerar_renavam(rng)
    chassi = "9BW" + "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789") for _ in range(14))
    car = (f"{uf}-{rng.randint(1000000, 5300000)}-" +
           ".".join("".join(rng.choice("0123456789ABCDEF") for _ in range(4)) for _ in range(8)))
    certidao = (f"{rng.randint(100000, 999999)} 01 55 {rng.randint(1990, 2024)} 1 {rng.randint(10000, 99999)} "
                f"{rng.randint(100, 999)} {rng.randint(1000000, 9999999)} {rng.randint(10, 99)}")
    regiao = rng.randint(1, 20)
    processos = [f"{rng.randint(1000, 9999)}.01.{rng.randint(1000000, 9999999)}/{rng.randint(2018, 2025)}-"
                 f"{rng.randint(10, 99)}",  # SEI-MG
                 f"{rng.randint(10**9, 10**10 - 1)}.{rng.randint(100000, 999999)}/{rng.randint(2018, 2025)}-"
                 f"{rng.randint(10, 99)}",  # SEI-PE
                 f"{rng.randint(100, 999)}.{rng.randint(1000, 9999)}.{rng.randint(2018, 2025)}."
                 f"{rng.randint(1000000, 9999999)}-{rng.randint(10, 99)}"]  # SEI-BA
    rg = rng.choice([f"{rng.randint(10, 99)}.{rng.randint(100, 999)}.{rng.randint(100, 999)}-{rng.choice('0123456789X')}",
                     f"{uf}-{rng.randint(10, 99)}.{rng.randint(100, 999)}.{rng.randint(100, 999)}"])
    return [
        ("NB_INSS", f"meu benefício do INSS NB {nb} foi suspenso", nb),
        ("RENAVAM", f"o veículo de RENAVAM {renavam}", renavam),
        ("CHASSI", f"chassi {chassi}", chassi),
        ("CAR", f"recibo do CAR nº {car}", car),
        ("CERTIDAO", f"certidão de nascimento matrícula {certidao}", certidao),
        ("PRONTUARIO", f"prontuário nº {rng.randint(100000, 9999999)}", None),
        ("MATRICULA", f"{rng.choice(['MASP', 'ID funcional', 'registro funcional'])} "
                      f"{rng.randint(100000, 9999999)}-{rng.randint(0, 9)}", None),
        ("CONSELHO", f"{rng.choice(['CRN', 'CRP', 'CREFITO', 'CREA'])}-{regiao} {rng.randint(10000, 999999)}", None),
        ("PROCESSO", f"o processo {rng.choice(processos)}", None),
        ("RG", f"RG {rg}", rg),
    ]


_RUAS_VALIDACAO = ["Rui Barbosa", "José Bonifácio", "das Mangueiras", "Desembargador Moreira", "Treze de Maio",
                   "Visconde de Mauá", "dos Andradas", "Professora Maria Clara", "Benjamin Constant", "do Comércio"]
_PROPRIEDADES_VALIDACAO = ["Pedra Branca", "Nossa Senhora Aparecida", "Rio Verde", "Lagoa Seca", "Morro Alto",
                           "Santo Antônio", "Vale do Sol", "Cachoeirinha"]


def _endereco_validacao(rng: random.Random, uf: str, cidade: str) -> tuple[str, str, str]:
    """Endereço do conjunto de validação: outras abreviações, ordens e tipos de localidade."""
    n = rng.randint(2, 4800)
    milhar = f"{n:,}".replace(",", ".")
    nome = rng.choice(_RUAS_VALIDACAO)
    propriedade = rng.choice(_PROPRIEDADES_VALIDACAO)
    q, lt = rng.randint(1, 120), rng.randint(1, 60)
    letra = rng.choice("ABCDEFGHJKLMN")
    opcoes = [
        ("URBANO", f"R. {nome}, {n} - Centro - {cidade}/{uf}", f"{nome}, {n}"),
        ("URBANO", f"Avenida {nome} n. {n}, casa {rng.randint(1, 9)}, {cidade} ({uf})", f"{nome} n. {n}"),
        ("URBANO", f"Alameda {nome}, {n}, bloco {letra}, apartamento {rng.randint(11, 904)}, {cidade}-{uf}",
         f"{nome}, {n}"),
        ("URBANO", f"Rua {nome}, {milhar}, {cidade}/{uf}", f"{nome}, {milhar}"),
        ("NUMERADO", f"Rua {letra}-{rng.randint(1, 40)}, Quadra {q}, Lote {lt}, {cidade}/{uf}",
         f"Quadra {q}, Lote {lt}"),
        ("NUMERADO", f"Avenida {rng.randint(1, 30)}, nº {n}, {cidade}/{uf}", f"nº {n}"),
        ("RURAL", f"Chácara {propriedade}, Núcleo Rural {rng.choice(_PROPRIEDADES)}, {cidade}/{uf}",
         f"Chácara {propriedade}"),
        ("RURAL", f"Comunidade {propriedade}, zona rural, {cidade}/{uf}", f"Comunidade {propriedade}"),
        ("RURAL", f"Estrada Vicinal {rng.randint(1, 90)}, km {rng.randint(1, 60)}, {cidade}/{uf}", None),
        ("RURAL", f"Granja {propriedade}, {cidade}/{uf}", f"Granja {propriedade}"),
        ("RODOVIA", f"km {rng.randint(1, 600)} da BR-{rng.choice([101, 116, 153, 230, 364, 40]):03d}, {cidade}/{uf}",
         None),
    ]
    tipo, frase, nucleo = rng.choice(opcoes)
    if nucleo is None:
        nucleo = frase.split(f", {cidade}")[0]
    return tipo, frase, nucleo


def _identificadores_validacao(rng: random.Random, uf: str) -> list[tuple[str, str, str | None]]:
    """Identificadores do conjunto de validação, com rótulos e pontuação diferentes."""
    nb = "".join(str(rng.randint(0, 9)) for _ in range(10))
    renavam = v.gerar_renavam(rng)
    chassi = "9" + "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789") for _ in range(16))
    rg = str(rng.randint(1000000, 99999999))
    return [
        ("NB_INSS", f"benefício previdenciário nº {nb}", nb),
        ("RENAVAM", f"Renavam: {renavam}", renavam),
        ("CHASSI", f"número do chassi {chassi}", chassi),
        ("PRONTUARIO", f"prontuário médico {rng.randint(100000, 9999999)}", None),
        ("MATRICULA", f"matrícula funcional {rng.randint(100000, 999999)}-{rng.randint(0, 9)}", None),
        ("CONSELHO", f"inscrito no {rng.choice(['CRM', 'COREN', 'CRO', 'CRF'])}/{uf} sob o nº "
                     f"{rng.randint(1000, 199999)}", None),
        ("RG", f"carteira de identidade nº {rg} SSP/{uf}", rg),
    ]


#: Modelos de frase do conjunto de validação: formulário, terceira pessoa e pedido de correspondência.
_MODELOS_VALIDACAO = (
    "Requerente: {nome}\nEndereço: {endereco}\n{ids}\nPedido: cópia integral do processo.",
    "O cidadão {nome}, que mora na {endereco}, informou {ids} e pede revisão do ato.",
    "Solicito que a resposta seja enviada a {nome}, no endereço {endereco}. Dados: {ids}.",
)


def gerar(n: int, semente: int, conjunto: str = "desenvolvimento") -> list[tuple[str, str, list[tuple[str, str]]]]:
    """Gera ``n`` documentos fictícios do conjunto ``desenvolvimento`` ou ``validacao``.

    Returns:
        Para cada documento, a UF, o texto e a lista ``(tipo, valor)`` dos dados que devem ser tarjados.
    """
    rng = random.Random(semente)  # dados fictícios reprodutíveis, não segredos  # nosec B311
    fk = Faker("pt_BR")
    fk.seed_instance(semente)
    cidades = municipios()
    ufs = sorted(cidades)
    validacao = conjunto == "validacao"
    gerar_endereco = _endereco_validacao if validacao else _endereco
    gerar_identificadores = _identificadores_validacao if validacao else _identificadores
    docs = []
    for k in range(n):
        uf = ufs[k % len(ufs)]  # todas as UFs aparecem na mesma proporção
        cidade = rng.choice(cidades[uf])
        nome = f"{fk.first_name()} {fk.last_name()}"  # sem pronome de tratamento, que fica visível por definição
        tipo_end, endereco, nucleo = gerar_endereco(rng, uf, cidade)
        itens = [("NOME", nome), (f"ENDERECO_{tipo_end}", nucleo)]
        ids = []
        for tipo, frase, valor in rng.sample(gerar_identificadores(rng, uf), 3):
            ids.append(frase)
            itens.append((tipo, valor if valor is not None else frase.rsplit(" ", 1)[-1]))
        if validacao:
            texto = rng.choice(_MODELOS_VALIDACAO).format(nome=nome, endereco=endereco, ids=", ".join(ids))
        else:
            texto = (f"Eu, {nome}, residente em {endereco}, " + ", ".join(ids)
                     + ", solicito informações sobre o andamento do meu pedido.")
        docs.append((uf, texto, itens))
    return docs


_ESTADOS = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
            "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
            "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
            "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
            "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
            "SE": "Sergipe", "TO": "Tocantins"}


def gerar_publicos(n: int, semente: int) -> list[tuple[str, str, list[str]]]:
    """Textos de interesse público, sem dado pessoal: ``(uf, texto, termos que devem permanecer)``."""
    rng = random.Random(semente + 1)  # nosec B311
    cidades = municipios()
    ufs = sorted(cidades)
    docs = []
    for k in range(n):
        uf = ufs[k % len(ufs)]
        cidade = rng.choice(cidades[uf])
        estado = _ESTADOS[uf]
        rua = rng.choice(_NOMES_RUA + _RUAS_VALIDACAO)
        lugar = rng.choice(_PROPRIEDADES + _PROPRIEDADES_VALIDACAO)
        rodovia = f"{uf}-{rng.randint(10, 499):03d}"
        km = rng.randint(1, 200)
        modelos = [
            (f"A Prefeitura Municipal de {cidade}/{uf} publicou o edital de chamamento nº {rng.randint(1, 90)}/2025.",
             [cidade]),
            (f"As obras de duplicação da {rodovia} entre os quilômetros {km} e {km + 30} foram concluídas pelo "
             f"governo do estado.", [rodovia]),
            (f"O Assentamento {lugar}, em {cidade}, recebeu investimentos do Incra para habitação rural.",
             [f"Assentamento {lugar}", cidade]),
            (f"A Comunidade Quilombola {lugar} foi certificada pela Fundação Cultural Palmares.",
             [f"Comunidade Quilombola {lugar}"]),
            (f"A Rua {rua} será recapeada pela Secretaria de Obras de {cidade} no próximo mês.", [f"Rua {rua}", cidade]),
            (f"A Fazenda Pública do Estado de {estado} foi condenada a fornecer o medicamento.", ["Fazenda Pública"]),
            (f"O Hospital Regional de {cidade} ampliou em 40 leitos a capacidade da UTI.", [cidade]),
            (f"O Distrito Industrial de {cidade} abriga 35 empresas e 2 mil empregos.", ["Distrito Industrial", cidade]),
            (f"A ponte sobre o rio na BR-{rng.choice([101, 116, 153, 230, 364])} será interditada para manutenção.",
             ["ponte"]),
            (f"A Secretaria de Estado de Educação de {estado} divulgou o calendário escolar de 2026.", [estado]),
        ]
        texto, termos = rng.choice(modelos)
        docs.append((uf, texto, termos))
    return docs


def avaliar_preservacao(perfil: str, docs) -> dict:
    """Fração de termos públicos que permanecem e de documentos públicos sem nenhuma tarja."""
    resultados = Anonimizador(perfil).anonimizar_lote([d[1] for d in docs])
    termos = preservados = intactos = 0
    for (_uf, texto, esperados), r in zip(docs, resultados):
        compacto = "".join(c for c in r.texto if c.isalnum()).lower()
        for termo in esperados:
            termos += 1
            preservados += "".join(c for c in termo if c.isalnum()).lower() in compacto
        intactos += r.texto == texto
    return {"documentos": len(docs), "termos_preservados": round(preservados / max(1, termos), 4),
            "documentos_sem_tarja": round(intactos / max(1, len(docs)), 4)}


def avaliar(perfil: str, docs) -> dict:
    """Recall por tipo e por região, e fração de documentos com vazamento."""
    anon = Anonimizador(perfil)
    t0 = time.perf_counter()
    saidas = [r.texto for r in anon.anonimizar_lote([d[1] for d in docs])]
    duracao = time.perf_counter() - t0
    total, ok = Counter(), Counter()
    regiao_total, regiao_ok = Counter(), Counter()
    vazados = 0
    for (uf, _texto, itens), saida in zip(docs, saidas):
        compacto = "".join(c for c in saida if c.isalnum()).lower()
        vazou = False
        for tipo, valor in itens:
            alvo = "".join(c for c in valor if c.isalnum()).lower()
            sobrou = len(alvo) >= 4 and alvo in compacto
            total[tipo] += 1
            regiao_total[REGIAO_DA_UF[uf]] += 1
            if not sobrou:
                ok[tipo] += 1
                regiao_ok[REGIAO_DA_UF[uf]] += 1
            else:
                vazou = True
        vazados += vazou
    return {
        "perfil": perfil, "documentos": len(docs), "segundos_por_documento": round(duracao / max(1, len(docs)), 4),
        "recall": round(sum(ok.values()) / max(1, sum(total.values())), 4),
        "recall_por_tipo": {k: round(ok[k] / total[k], 4) for k in sorted(total)},
        "recall_por_regiao": {k: round(regiao_ok[k] / regiao_total[k], 4) for k in REGIOES},
        "documentos_com_vazamento": round(vazados / max(1, len(docs)), 4),
    }


def main() -> int:
    """Executa a avaliação; devolve 1 se o recall ou a preservação ficarem abaixo dos mínimos."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=540)
    ap.add_argument("--semente", type=int, default=7)
    ap.add_argument("--perfil", default="lai")
    ap.add_argument("--conjunto", choices=("desenvolvimento", "validacao"), default="desenvolvimento")
    ap.add_argument("--publicos", type=int, default=270, help="quantidade de textos públicos (0 para omitir)")
    ap.add_argument("--minimo", type=float, default=0.0, help="falha (código 1) se o recall ficar abaixo")
    ap.add_argument("--preservacao-minima", type=float, default=0.0,
                    help="falha (código 1) se a fração de termos públicos preservados ficar abaixo")
    ap.add_argument("--json", help="grava o resultado neste arquivo")
    args = ap.parse_args()
    res = {"conjunto": args.conjunto, **avaliar(args.perfil, gerar(args.n, args.semente, args.conjunto))}
    if args.publicos:
        res["textos_publicos"] = avaliar_preservacao(args.perfil, gerar_publicos(args.publicos, args.semente))
    texto = json.dumps(res, ensure_ascii=False, indent=2)
    print(texto)
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto + "\n")
    preservacao = res.get("textos_publicos", {}).get("termos_preservados", 1.0)
    return 0 if res["recall"] >= args.minimo and preservacao >= args.preservacao_minima else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
