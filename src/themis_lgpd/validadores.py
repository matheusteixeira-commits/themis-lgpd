"""Dígitos verificadores de documentos brasileiros e geradores de números válidos para testes.

A validação do dígito verificador é o que permite distinguir um CPF de um número qualquer de onze
dígitos sem depender de contexto. Todos os validadores aceitam o número com ou sem pontuação e
rejeitam sequências de um único dígito repetido ("111.111.111-11"), que satisfazem vários dos
algoritmos mas não são emitidas.

Os geradores produzem números válidos e aleatórios para a suíte de testes e para o benchmark
sintético; não usam dados reais.
"""

from __future__ import annotations

import ipaddress
import random
import re
from datetime import date

_NAO_DIGITO = re.compile(r"\D")
_NAO_ALNUM = re.compile(r"[^0-9A-Za-z]")


def so_digitos(valor: str) -> str:
    """Remove tudo o que não é dígito decimal."""
    return _NAO_DIGITO.sub("", valor)


def _repetido(s: str) -> bool:
    return len(set(s)) == 1


# ---------------------------------------------------------------- CPF
def _dv_cpf(base: str) -> str:
    """Dígitos verificadores do CPF: módulo 11 com pesos decrescentes de 10 e de 11."""
    d1 = sum(int(base[i]) * (10 - i) for i in range(9)) * 10 % 11 % 10
    d2 = sum(int((base + str(d1))[i]) * (11 - i) for i in range(10)) * 10 % 11 % 10
    return f"{d1}{d2}"


def cpf_valido(valor: str) -> bool:
    """Indica se ``valor`` é um CPF com dígitos verificadores corretos."""
    d = so_digitos(valor)
    return len(d) == 11 and not _repetido(d) and _dv_cpf(d[:9]) == d[9:]


# ---------------------------------------------------------------- CNPJ (numérico e alfanumérico)
_PESOS_CNPJ1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_CNPJ2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def _dv_cnpj(base12: str) -> str:
    """Dígitos verificadores do CNPJ: módulo 11 sobre os doze primeiros caracteres.

    No CNPJ alfanumérico, cada caractere vale o seu código ASCII menos 48: os dígitos mantêm o
    valor ("0" → 0) e as letras passam a valer de 17 ("A") a 42 ("Z"). Para CNPJs só com dígitos o
    cálculo coincide com o algoritmo tradicional.
    """
    vals = [ord(c) - 48 for c in base12.upper()]
    r1 = sum(v * p for v, p in zip(vals, _PESOS_CNPJ1)) % 11
    d1 = 0 if r1 < 2 else 11 - r1
    r2 = sum(v * p for v, p in zip(vals + [d1], _PESOS_CNPJ2)) % 11
    d2 = 0 if r2 < 2 else 11 - r2
    return f"{d1}{d2}"


def cnpj_valido(valor: str) -> bool:
    """Indica se ``valor`` é um CNPJ válido, numérico ou alfanumérico.

    O formato alfanumérico foi instituído pela Instrução Normativa RFB nº 2.229/2024 e está em
    vigor desde julho de 2026: os doze primeiros caracteres podem ser letras ou dígitos; os dois
    verificadores continuam numéricos.
    """
    s = _NAO_ALNUM.sub("", valor).upper()
    if len(s) != 14 or not s[12:].isdigit() or _repetido(s):
        return False
    return _dv_cnpj(s[:12]) == s[12:]


# ---------------------------------------------------------------- PIS/PASEP/NIS/NIT
_PESOS_PIS = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def _dv_pis(base10: str) -> str:
    """Dígito verificador do PIS/PASEP/NIS/NIT: módulo 11; restos que resultam em 10 ou 11 valem 0."""
    dv = 11 - sum(int(base10[i]) * _PESOS_PIS[i] for i in range(10)) % 11
    return "0" if dv >= 10 else str(dv)


def pis_valido(valor: str) -> bool:
    """Indica se ``valor`` é um PIS/PASEP/NIS/NIT válido (mesma numeração e mesmo algoritmo)."""
    d = so_digitos(valor)
    return len(d) == 11 and not _repetido(d) and _dv_pis(d[:10]) == d[10]


# ---------------------------------------------------------------- Título de eleitor
def _dv_titulo(seq8: str, uf: str) -> str:
    """Dígitos verificadores do título de eleitor (algoritmo do TSE).

    O primeiro dígito incide sobre o número sequencial; o segundo, sobre o código da UF e o
    primeiro dígito. Resto 10 vale 0; para São Paulo (01) e Minas Gerais (02), resto 0 vale 1.
    """
    r1 = sum(int(seq8[i]) * (i + 2) for i in range(8)) % 11
    if r1 == 10:
        r1 = 0
    elif r1 == 0 and uf in ("01", "02"):
        r1 = 1
    r2 = (int(uf[0]) * 7 + int(uf[1]) * 8 + r1 * 9) % 11
    if r2 == 10:
        r2 = 0
    elif r2 == 0 and uf in ("01", "02"):
        r2 = 1
    return f"{r1}{r2}"


def titulo_eleitor_valido(valor: str) -> bool:
    """Indica se ``valor`` é um título de eleitor válido.

    O número tem doze dígitos: oito sequenciais, dois do código da UF (01 a 28, sendo 28 o exterior)
    e dois verificadores.
    """
    d = so_digitos(valor)
    if len(d) != 12 or _repetido(d):
        return False
    uf = d[8:10]
    return 1 <= int(uf) <= 28 and _dv_titulo(d[:8], uf) == d[10:]


# ---------------------------------------------------------------- CNS (Cartão SUS)
def cns_valido(valor: str) -> bool:
    """Indica se ``valor`` é um Cartão Nacional de Saúde válido.

    Números definitivos começam com 1 ou 2 e provisórios com 7, 8 ou 9. Em ambos, a soma dos quinze
    dígitos multiplicados pelos pesos de 15 a 1 deve ser múltipla de 11.
    """
    d = so_digitos(valor)
    if len(d) != 15 or d[0] not in "12789" or _repetido(d):
        return False
    return sum(int(d[i]) * (15 - i) for i in range(15)) % 11 == 0


# ---------------------------------------------------------------- CNH
def _dv_cnh(base9: str) -> str:
    """Dígitos verificadores do registro da CNH.

    Quando o primeiro dígito resulta em 10 ou mais, ele vale 0 e o segundo é calculado com desconto
    de 2, conforme o algoritmo adotado pelos órgãos de trânsito.
    """
    s1 = sum(int(base9[i]) * (9 - i) for i in range(9))
    d1 = s1 % 11
    desconto = 0
    if d1 >= 10:
        d1, desconto = 0, 2
    s2 = sum(int(base9[i]) * (1 + i) for i in range(9))
    d2 = s2 % 11 - desconto
    if d2 < 0:
        d2 += 11
    if d2 >= 10:
        d2 = 0
    return f"{d1}{d2}"


def cnh_valida(valor: str) -> bool:
    """Indica se ``valor`` é um número de registro de CNH válido (onze dígitos)."""
    d = so_digitos(valor)
    return len(d) == 11 and not _repetido(d) and _dv_cnh(d[:9]) == d[9:]


# ---------------------------------------------------------------- RENAVAM
_PESOS_RENAVAM = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def _dv_renavam(base10: str) -> str:
    """Dígito verificador do RENAVAM: módulo 11 sobre os dez primeiros dígitos; resto 10 vale 0."""
    dv = sum(int(base10[i]) * _PESOS_RENAVAM[i] for i in range(10)) * 10 % 11
    return "0" if dv == 10 else str(dv)


def renavam_valido(valor: str) -> bool:
    """Indica se ``valor`` é um RENAVAM válido.

    Números do formato antigo, com nove dígitos, são completados com zeros à esquerda, como no
    formato atual de onze dígitos.
    """
    d = so_digitos(valor).zfill(11)
    return len(d) == 11 and not _repetido(d) and _dv_renavam(d[:10]) == d[10]


# ---------------------------------------------------------------- Processo judicial (CNJ, Res. 65/2008)
def processo_cnj_valido(valor: str) -> bool:
    """Indica se ``valor`` é um número único de processo judicial válido.

    Formato da Resolução CNJ nº 65/2008: ``NNNNNNN-DD.AAAA.J.TR.OOOO``. O verificador ``DD`` segue o
    módulo 97 da ISO 7064: o número reordenado como ``NNNNNNN AAAAJTROOOO DD`` deve deixar resto 1.
    """
    d = so_digitos(valor)
    if len(d) != 20:
        return False
    n, dv, resto = d[:7], d[7:9], d[9:]
    return int(n + resto + dv) % 97 == 1


def _dv_cnj(n7: str, resto11: str) -> str:
    """Verificador de um número de processo a partir do sequencial e dos demais campos."""
    return f"{98 - int(n7 + resto11 + '00') % 97:02d}"


# ---------------------------------------------------------------- Cartão (Luhn)
def luhn_valido(valor: str) -> bool:
    """Indica se ``valor`` tem de 13 a 19 dígitos e satisfaz o algoritmo de Luhn (cartões de pagamento)."""
    d = so_digitos(valor)
    if not 13 <= len(d) <= 19 or _repetido(d):
        return False
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


# ---------------------------------------------------------------- IP
def ip_valido(valor: str) -> bool:
    """Indica se ``valor`` é um endereço IPv4 ou IPv6 que pode identificar uma máquina.

    Endereços não especificados (``0.0.0.0``) e de loopback (``127.0.0.1``) não identificam ninguém e
    são rejeitados.
    """
    try:
        ip = ipaddress.ip_address(valor.strip())
    except ValueError:
        return False
    return not (ip.is_unspecified or ip.is_loopback)


# ---------------------------------------------------------------- Ano plausível (processos)
def ano_plausivel(valor: str) -> bool:
    """Indica se ``valor`` contém um ano entre 1960 e o ano seguinte ao atual.

    Usado para distinguir números de processo administrativo, que incluem o ano de autuação, de
    outros números com a mesma forma.
    """
    for m in re.finditer(r"(?<!\d)(19[6-9]\d|20\d{2})(?!\d)", valor):
        if 1960 <= int(m.group()) <= date.today().year + 1:
            return True
    return False


# ================================================================ Geradores (testes e benchmark)
# Os geradores usam ``random`` deliberadamente: produzem dados fictícios reprodutíveis por semente,
# não segredos (por isso as marcações ``nosec B311``).

def gerar_cpf(rng: random.Random | None = None, formatado: bool = True) -> str:
    """CPF válido e aleatório, com pontuação (``000.000.000-00``) ou só com dígitos."""
    rng = rng or random.Random()  # nosec B311
    while True:
        base = "".join(str(rng.randint(0, 9)) for _ in range(9))
        if not _repetido(base):
            break
    d = base + _dv_cpf(base)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if formatado else d


def gerar_cnpj(rng: random.Random | None = None, alfanumerico: bool = False) -> str:
    """CNPJ válido de matriz (ordem ``0001``), numérico ou alfanumérico, com pontuação."""
    rng = rng or random.Random()  # nosec B311
    alfabeto = "0123456789ABCDEFGHIJKLMNPQRSTUVWXYZ" if alfanumerico else "0123456789"
    base = "".join(rng.choice(alfabeto) for _ in range(8)) + "0001"
    s = base + _dv_cnpj(base)
    return f"{s[:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:]}"


def gerar_pis(rng: random.Random | None = None) -> str:
    """PIS/PASEP válido, no formato ``000.00000.00-0``."""
    rng = rng or random.Random()  # nosec B311
    base = "1" + "".join(str(rng.randint(0, 9)) for _ in range(9))
    d = base + _dv_pis(base)
    return f"{d[:3]}.{d[3:8]}.{d[8:10]}-{d[10]}"


def gerar_titulo(rng: random.Random | None = None) -> str:
    """Título de eleitor válido, no formato ``0000 0000 0000``."""
    rng = rng or random.Random()  # nosec B311
    seq = "".join(str(rng.randint(0, 9)) for _ in range(8))
    uf = f"{rng.randint(1, 28):02d}"
    d = seq + uf + _dv_titulo(seq, uf)
    return f"{d[:4]} {d[4:8]} {d[8:]}"


def gerar_cns(rng: random.Random | None = None) -> str:
    """Cartão Nacional de Saúde definitivo válido, no formato ``000 0000 0000 0000``."""
    rng = rng or random.Random()  # nosec B311
    while True:
        corpo = rng.choice("12") + "".join(str(rng.randint(0, 9)) for _ in range(13))
        soma = sum(int(corpo[i]) * (15 - i) for i in range(14))
        dv = (11 - soma % 11) % 11
        if dv < 10:  # nem toda base admite um dígito final que torne a soma múltipla de 11
            d = corpo + str(dv)
            if cns_valido(d):
                return f"{d[:3]} {d[3:7]} {d[7:11]} {d[11:]}"


def gerar_cnh(rng: random.Random | None = None) -> str:
    """Registro de CNH válido, com onze dígitos."""
    rng = rng or random.Random()  # nosec B311
    base = "".join(str(rng.randint(0, 9)) for _ in range(9))
    return base + _dv_cnh(base)


def gerar_renavam(rng: random.Random | None = None) -> str:
    """RENAVAM válido, com onze dígitos."""
    rng = rng or random.Random()  # nosec B311
    base = "".join(str(rng.randint(0, 9)) for _ in range(10))
    return base + _dv_renavam(base)


def gerar_processo_cnj(rng: random.Random | None = None) -> str:
    """Número único de processo válido do Tribunal de Justiça do Distrito Federal e Territórios (8.07)."""
    rng = rng or random.Random()  # nosec B311
    n = "".join(str(rng.randint(0, 9)) for _ in range(7))
    ano = str(rng.randint(2005, 2026))
    resto = ano + "8" + "07" + f"{rng.randint(1, 9999):04d}"
    dv = _dv_cnj(n, resto)
    return f"{n}-{dv}.{ano}.8.07.{resto[-4:]}"


def gerar_cartao(rng: random.Random | None = None) -> str:
    """Número de cartão de pagamento válido (bandeira iniciada por 4), em quatro grupos de quatro."""
    rng = rng or random.Random()  # nosec B311
    corpo = "4" + "".join(str(rng.randint(0, 9)) for _ in range(14))
    for dv in range(10):
        if luhn_valido(corpo + str(dv)):
            d = corpo + str(dv)
            return " ".join(d[i:i + 4] for i in range(0, 16, 4))
    raise RuntimeError("Nenhum dígito satisfaz o algoritmo de Luhn")  # impossível: sempre há exatamente um
