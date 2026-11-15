"""Configuração por órgão: o arquivo ``themis.toml``.

Cada órgão tem numerações, cargos e critérios próprios. O ``themis.toml`` reúne, num arquivo
versionável e auditável, o que a CLI, a API e a interface devem aplicar:

* ``[padrao]``: perfil, modo e opções usados quando a chamada não indica outros;
* ``[listas]``: termos que nunca são tarjados (``permitir``) ou que sempre são (``bloquear``),
  diretamente ou em arquivos de texto;
* ``[agentes_publicos]``: cargos do órgão, somados aos reconhecidos pelo Themis;
* ``[[tipos]]``: tipos de dado próprios (código, nome, categoria, etiqueta, prioridade);
* ``[[reconhecedores]]``: regras próprias — expressão regular, palavras de contexto e validador de
  dígito opcional —, registradas no Presidio como os reconhecedores do Themis;
* ``[perfis.<nome>]``: perfis derivados de um perfil do Themis, com regras e limiares próprios.

Exemplo comentado em ``exemplos/orgao.toml``. Erros de configuração interrompem a execução com a
indicação da seção e do campo: uma regra de proteção ignorada em silêncio seria um vazamento.

A CLI recebe o arquivo em ``--config``; a API e a interface, na variável ``THEMIS_CONFIG``.
"""

from __future__ import annotations

import hashlib
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import regex as re

from . import catalogo, validadores
from . import perfis as P
from .operadores import MODOS
from .reconhecedores.base import CONTEXTUAL, Padrao, ReconhecedorPadroes


class ConfiguracaoInvalida(ValueError):
    """Arquivo de configuração com erro; a mensagem indica a seção e o campo."""


#: Validadores de dígito que um reconhecedor próprio pode usar, pelo nome.
VALIDADORES = {
    "cpf": validadores.cpf_valido, "cnpj": validadores.cnpj_valido, "pis": validadores.pis_valido,
    "titulo_eleitor": validadores.titulo_eleitor_valido, "cns": validadores.cns_valido,
    "cnh": validadores.cnh_valida, "renavam": validadores.renavam_valido,
    "processo_cnj": validadores.processo_cnj_valido, "luhn": validadores.luhn_valido,
    "ano_plausivel": validadores.ano_plausivel,
}

_SECOES = {"padrao", "listas", "agentes_publicos", "tipos", "reconhecedores", "perfis"}
_CAMPOS = {
    "padrao": {"perfil", "modo", "preservar_agentes_publicos", "usar_ner", "ocr"},
    "listas": {"permitir", "bloquear", "permitir_arquivo", "bloquear_arquivo"},
    "agentes_publicos": {"cargos"},
    "tipos": {"codigo", "nome", "categoria", "etiqueta", "prioridade"},
    "reconhecedores": {"nome", "tipo", "regex", "grupo", "score", "contexto", "contexto_obrigatorio", "janela",
                       "validador", "score_invalido", "ignorar_caixa"},
    "perfis": {"base", "titulo", "descricao", "regras", "score_minimo", "score_alerta", "tarjar_sensivel_sempre"},
}


@dataclass(frozen=True)
class ConfiguracaoOrgao:
    """Configuração validada.

    Attributes:
        origem: Caminho do arquivo lido (vazio para a configuração padrão).
        perfil: Perfil padrão (nome de um perfil do Themis ou instância de perfil próprio).
        modo: Modo de substituição padrão.
        preservar_agentes_publicos: Mantém nomes acompanhados de cargo público.
        usar_ner: Usa o modelo de linguagem.
        ocr: Permite OCR.
        permitir: Termos nunca tarjados.
        bloquear: Termos sempre tarjados.
        cargos: Cargos públicos adicionais.
        tipos: Tipos de dado próprios.
        padroes: Regras dos reconhecedores próprios.
        perfis: Perfis próprios, pelo nome.
    """

    origem: str = ""
    perfil: str | P.Perfil = P.PERFIL_PADRAO
    modo: str = "etiqueta"
    preservar_agentes_publicos: bool = False
    usar_ner: bool = True
    ocr: bool = True
    permitir: tuple[str, ...] = ()
    bloquear: tuple[str, ...] = ()
    cargos: tuple[str, ...] = ()
    tipos: tuple[catalogo.TipoInfo, ...] = ()
    padroes: tuple[Padrao, ...] = field(default=(), compare=False)
    perfis: Mapping[str, P.Perfil] = field(default_factory=dict)

    def impressao(self) -> dict:
        """Conteúdo efetivo da configuração em valores simples e ordenados, estável entre execuções.

        Usado no identificador de configuração do manifesto de lote; termos das listas entram como
        resumo SHA-256, para que o manifesto não os exponha.
        """
        def perfil(p: str | P.Perfil) -> object:
            if isinstance(p, str):
                return p
            return [p.nome, sorted(p.regras.items()), p.score_minimo, p.score_alerta, sorted(p.tarjar_sensivel_sempre)]

        def resumo(termos: tuple[str, ...]) -> str:
            return hashlib.sha256("\n".join(sorted(termos)).encode("utf-8")).hexdigest()

        return {
            "perfil": perfil(self.perfil), "modo": self.modo, "agentes": self.preservar_agentes_publicos,
            "ner": self.usar_ner, "ocr": self.ocr, "permitir": resumo(self.permitir), "bloquear": resumo(self.bloquear),
            "cargos": sorted(self.cargos), "tipos": sorted((t.codigo, t.categoria, t.etiqueta, t.prioridade) for t in self.tipos),
            "padroes": [(p.nome, p.tipo, p.regex, p.score, str(p.grupo), list(p.contexto), p.contexto_obrigatorio, p.janela,
                         getattr(p.validador, "__name__", None), p.score_invalido, p.ignorar_caixa) for p in self.padroes],
            "perfis": {n: perfil(p) for n, p in sorted(self.perfis.items())},
        }

    def obter_perfil(self, nome: str | None) -> str | P.Perfil:
        """Perfil pelo nome: primeiro os próprios do órgão, depois os do Themis; ``None`` = padrão."""
        if nome is None:
            return self.perfil
        if nome.lower() in self.perfis:
            return self.perfis[nome.lower()]
        return P.obter_perfil(nome).nome

    def argumentos(self, **sobrepor: Any) -> dict:
        """Argumentos de :class:`themis_lgpd.motor.Anonimizador`; ``sobrepor`` substitui os padrões.

        Valores ``None`` em ``sobrepor`` mantêm o valor da configuração. As listas de permissão e de
        bloqueio informadas na chamada são somadas às do arquivo.
        """
        registrar(self)
        sobrepor = {k: v for k, v in sobrepor.items() if v is not None}
        perfil = self.obter_perfil(sobrepor.pop("perfil", None))
        extras = [ReconhecedorPadroes("orgao", self.padroes)] if self.padroes else []
        args = {
            "perfil": perfil, "modo": self.modo, "preservar_agentes_publicos": self.preservar_agentes_publicos,
            "usar_ner": self.usar_ner, "cargos": list(self.cargos), "reconhecedores_extras": extras,
            "permitir": list(self.permitir) + list(sobrepor.pop("permitir", [])),
            "bloquear": list(self.bloquear) + list(sobrepor.pop("bloquear", [])),
        }
        args.update(sobrepor)
        return args


def registrar(cfg: ConfiguracaoOrgao) -> None:
    """Registra no catálogo os tipos próprios (idempotente; repetido em cada processo de trabalho)."""
    for info in cfg.tipos:
        catalogo.registrar_tipo(info)


def carregar(caminho: str | Path | None = None) -> ConfiguracaoOrgao:
    """Lê e valida o arquivo de configuração.

    Args:
        caminho: Arquivo ``.toml``. Sem caminho, usa ``THEMIS_CONFIG`` ou, na ausência dela, a
            configuração padrão do Themis.

    Raises:
        ConfiguracaoInvalida: Arquivo inexistente, TOML malformado ou campo inválido.
    """
    caminho = caminho or os.environ.get("THEMIS_CONFIG") or None
    if not caminho:
        return ConfiguracaoOrgao()
    p = Path(caminho)
    try:
        dados = tomllib.loads(p.read_text(encoding="utf-8"))
    except OSError as erro:
        raise ConfiguracaoInvalida(f"{p}: não foi possível ler o arquivo ({erro.strerror})") from erro
    except tomllib.TOMLDecodeError as erro:
        raise ConfiguracaoInvalida(f"{p}: TOML inválido ({erro})") from erro
    return interpretar(dados, origem=str(p), pasta=p.parent)


def interpretar(dados: Mapping[str, Any], origem: str = "", pasta: Path | None = None) -> ConfiguracaoOrgao:
    """Valida a configuração já lida (dicionário com a estrutura do ``themis.toml``)."""
    pasta = pasta or Path.cwd()
    _sem_campos_desconhecidos("raiz", dados, _SECOES)
    padrao = _secao(dados, "padrao")
    listas = _secao(dados, "listas")
    agentes = _secao(dados, "agentes_publicos")

    tipos = tuple(_tipo(i, t) for i, t in enumerate(_lista_de_tabelas(dados, "tipos"), start=1))
    codigos_validos = set(catalogo.TIPOS) | {t.codigo for t in tipos}
    padroes = tuple(_padrao(i, r, codigos_validos) for i, r in enumerate(_lista_de_tabelas(dados, "reconhecedores"),
                                                                           start=1))
    perfis_proprios = _perfis(dados.get("perfis", {}), tipos)

    nome_perfil = _texto(padrao, "padrao", "perfil", P.PERFIL_PADRAO)
    if nome_perfil.lower() in perfis_proprios:
        perfil: str | P.Perfil = perfis_proprios[nome_perfil.lower()]
    elif nome_perfil.lower() in P.PERFIS:
        perfil = nome_perfil.lower()
    else:
        raise ConfiguracaoInvalida(f"[padrao] perfil: {nome_perfil!r} não existe; opções: "
                                   f"{', '.join([*P.PERFIS, *perfis_proprios])}")
    modo = _texto(padrao, "padrao", "modo", "etiqueta")
    if modo not in MODOS:
        raise ConfiguracaoInvalida(f"[padrao] modo: {modo!r} não existe; opções: {', '.join(MODOS)}")

    return ConfiguracaoOrgao(
        origem=origem, perfil=perfil, modo=modo,
        preservar_agentes_publicos=_booleano(padrao, "padrao", "preservar_agentes_publicos", False),
        usar_ner=_booleano(padrao, "padrao", "usar_ner", True),
        ocr=_booleano(padrao, "padrao", "ocr", True),
        permitir=tuple(_termos(listas, "permitir", pasta)),
        bloquear=tuple(_termos(listas, "bloquear", pasta)),
        cargos=tuple(_lista_texto(agentes, "agentes_publicos", "cargos")),
        tipos=tipos, padroes=padroes, perfis=perfis_proprios,
    )


# ------------------------------------------------------------------ validação
def _sem_campos_desconhecidos(onde: str, tabela: Mapping, permitidos: set[str]) -> None:
    desconhecidos = sorted(set(tabela) - permitidos)
    if desconhecidos:
        raise ConfiguracaoInvalida(f"[{onde}] campo(s) desconhecido(s): {', '.join(desconhecidos)}; "
                                   f"aceitos: {', '.join(sorted(permitidos))}")


def _secao(dados: Mapping, nome: str) -> Mapping:
    secao = dados.get(nome, {})
    if not isinstance(secao, Mapping):
        raise ConfiguracaoInvalida(f"[{nome}] deve ser uma tabela")
    _sem_campos_desconhecidos(nome, secao, _CAMPOS[nome])
    return secao


def _lista_de_tabelas(dados: Mapping, nome: str) -> list[Mapping]:
    itens = dados.get(nome, [])
    if not isinstance(itens, list) or not all(isinstance(i, Mapping) for i in itens):
        raise ConfiguracaoInvalida(f"[[{nome}]] deve ser uma lista de tabelas ([[{nome}]] repetido)")
    for i, item in enumerate(itens, start=1):
        _sem_campos_desconhecidos(f"{nome} nº {i}", item, _CAMPOS[nome])
    return itens


def _texto(tabela: Mapping, onde: str, campo: str, padrao: str | None = None) -> str:
    valor = tabela.get(campo, padrao)
    if not isinstance(valor, str) or not valor.strip():
        raise ConfiguracaoInvalida(f"[{onde}] {campo}: informe um texto não vazio")
    return valor.strip()


def _booleano(tabela: Mapping, onde: str, campo: str, padrao: bool) -> bool:
    valor = tabela.get(campo, padrao)
    if not isinstance(valor, bool):
        raise ConfiguracaoInvalida(f"[{onde}] {campo}: use true ou false")
    return valor


def _numero(tabela: Mapping, onde: str, campo: str, padrao: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    valor = tabela.get(campo, padrao)
    if isinstance(valor, bool) or not isinstance(valor, int | float) or not minimo <= valor <= maximo:
        raise ConfiguracaoInvalida(f"[{onde}] {campo}: use um número entre {minimo} e {maximo}")
    return float(valor)


def _lista_texto(tabela: Mapping, onde: str, campo: str) -> list[str]:
    valor = tabela.get(campo, [])
    if not isinstance(valor, list) or not all(isinstance(v, str) for v in valor):
        raise ConfiguracaoInvalida(f"[{onde}] {campo}: use uma lista de textos")
    return [v.strip() for v in valor if v.strip()]


def _termos(listas: Mapping, nome: str, pasta: Path) -> list[str]:
    termos = _lista_texto(listas, "listas", nome)
    arquivo = listas.get(f"{nome}_arquivo")
    if arquivo:
        caminho = (pasta / arquivo) if not Path(arquivo).is_absolute() else Path(arquivo)
        try:
            linhas = caminho.read_text(encoding="utf-8").splitlines()
        except OSError as erro:
            raise ConfiguracaoInvalida(f"[listas] {nome}_arquivo: não foi possível ler {caminho}") from erro
        termos += [linha.strip() for linha in linhas if linha.strip() and not linha.startswith("#")]
    return termos


def _codigo(valor: str, onde: str) -> str:
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,40}", valor):
        raise ConfiguracaoInvalida(f"[{onde}] codigo: use letras maiúsculas, dígitos e _ (ex.: MATRICULA_CUSTODIADO)")
    return valor


def _tipo(i: int, t: Mapping) -> catalogo.TipoInfo:
    onde = f"tipos nº {i}"
    codigo = _codigo(_texto(t, onde, "codigo"), onde)
    categoria = _texto(t, onde, "categoria")
    if categoria not in catalogo.CATEGORIAS:
        raise ConfiguracaoInvalida(f"[{onde}] categoria: {categoria!r} não existe; opções: "
                                   f"{', '.join(catalogo.CATEGORIAS)}")
    if codigo in catalogo.TIPOS and catalogo.TIPOS[codigo].categoria != categoria:
        raise ConfiguracaoInvalida(f"[{onde}] codigo: {codigo!r} já existe no catálogo do Themis")
    etiqueta = t.get("etiqueta", f"[{codigo}]")
    if not isinstance(etiqueta, str) or not etiqueta:
        raise ConfiguracaoInvalida(f"[{onde}] etiqueta: informe um texto")
    prioridade = int(_numero(t, onde, "prioridade", 80, 1, 109))
    return catalogo.TipoInfo(codigo, _texto(t, onde, "nome"), categoria, etiqueta, prioridade)


def _padrao(i: int, r: Mapping, codigos: set[str]) -> Padrao:
    onde = f"reconhecedores nº {i}"
    nome = _texto(r, onde, "nome")
    tipo = _texto(r, onde, "tipo")
    if tipo not in codigos:
        raise ConfiguracaoInvalida(f"[{onde}] tipo: {tipo!r} não existe; declare-o em [[tipos]] ou use um tipo "
                                   "do catálogo (docs/TIPOS_DE_DADOS.md)")
    expressao = _texto(r, onde, "regex")
    ignorar_caixa = _booleano(r, onde, "ignorar_caixa", True)
    try:
        compilada = re.compile(expressao, re.IGNORECASE if ignorar_caixa else 0)
    except re.error as erro:
        raise ConfiguracaoInvalida(f"[{onde}] regex: expressão inválida ({erro})") from erro
    grupo = r.get("grupo", 0)
    if grupo and (not isinstance(grupo, str) or grupo not in compilada.groupindex):
        raise ConfiguracaoInvalida(f"[{onde}] grupo: {grupo!r} não é um grupo nomeado da expressão")
    if compilada.search(""):
        raise ConfiguracaoInvalida(f"[{onde}] regex: a expressão aceita texto vazio")
    contexto = tuple(re.escape(c) for c in _lista_texto(r, onde, "contexto"))
    obrigatorio = _booleano(r, onde, "contexto_obrigatorio", False)
    if obrigatorio and not contexto:
        raise ConfiguracaoInvalida(f"[{onde}] contexto_obrigatorio exige a lista contexto")
    validador = r.get("validador")
    if validador is not None and validador not in VALIDADORES:
        raise ConfiguracaoInvalida(f"[{onde}] validador: {validador!r} não existe; opções: {', '.join(VALIDADORES)}")
    score_invalido = r.get("score_invalido")
    if score_invalido is not None:
        score_invalido = _numero(r, onde, "score_invalido", 0.0)
    return Padrao(
        tipo, expressao, _numero(r, onde, "score", 0.85), camada=CONTEXTUAL, grupo=grupo or 0,
        validador=VALIDADORES.get(validador) if validador else None, contexto=contexto,
        contexto_obrigatorio=obrigatorio, score_invalido=score_invalido,
        janela=int(_numero(r, onde, "janela", 40, 1, 400)), ignorar_caixa=ignorar_caixa, nome=f"orgao:{nome}",
    )


def _perfis(tabela: Any, tipos: tuple[catalogo.TipoInfo, ...]) -> dict[str, P.Perfil]:
    if not isinstance(tabela, Mapping):
        raise ConfiguracaoInvalida("[perfis] deve conter tabelas [perfis.<nome>]")
    saida: dict[str, P.Perfil] = {}
    tipos_sensiveis = {t for t, info in catalogo.TIPOS.items() if info.categoria in {"SENSIVEL", "INTIMIDADE"}}
    tipos_sensiveis |= {t.codigo for t in tipos if t.categoria in {"SENSIVEL", "INTIMIDADE"}}
    for nome, d in tabela.items():
        onde = f"perfis.{nome}"
        if not isinstance(d, Mapping):
            raise ConfiguracaoInvalida(f"[{onde}] deve ser uma tabela")
        _sem_campos_desconhecidos(onde, d, _CAMPOS["perfis"])
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,40}", nome):
            raise ConfiguracaoInvalida(f"[{onde}] use um nome em minúsculas, sem espaços (ex.: ouvidoria_mg)")
        if nome in P.PERFIS:
            raise ConfiguracaoInvalida(f"[{onde}] já é um perfil do Themis; derive dele com base = \"{nome}\"")
        base_nome = _texto(d, onde, "base", P.PERFIL_PADRAO)
        if base_nome not in P.PERFIS:
            raise ConfiguracaoInvalida(f"[{onde}] base: {base_nome!r} não existe; opções: {', '.join(P.PERFIS)}")
        base = P.PERFIS[base_nome]
        regras = d.get("regras", {})
        if not isinstance(regras, Mapping):
            raise ConfiguracaoInvalida(f"[{onde}] regras: use uma tabela {{ CATEGORIA = \"tarjar\" }}")
        for categoria, regra in regras.items():
            if categoria not in catalogo.CATEGORIAS:
                raise ConfiguracaoInvalida(f"[{onde}] regras: categoria {categoria!r} não existe; opções: "
                                           f"{', '.join(catalogo.CATEGORIAS)}")
            if regra not in {P.TARJAR, P.ALERTAR, P.MANTER, P.VINCULADO}:
                raise ConfiguracaoInvalida(f"[{onde}] regras.{categoria}: use tarjar, alertar, manter ou vinculado")
        sempre = _lista_texto(d, onde, "tarjar_sensivel_sempre")
        if set(sempre) - tipos_sensiveis:
            raise ConfiguracaoInvalida(f"[{onde}] tarjar_sensivel_sempre: tipos não sensíveis ou inexistentes: "
                                       f"{', '.join(sorted(set(sempre) - tipos_sensiveis))}")
        saida[nome] = replace(
            base, nome=nome, titulo=d.get("titulo", nome), descricao=d.get("descricao", f"Derivado de {base.titulo}"),
            regras={**base.regras, **regras},
            score_minimo=_numero(d, onde, "score_minimo", base.score_minimo),
            score_alerta=_numero(d, onde, "score_alerta", base.score_alerta),
            tarjar_sensivel_sempre=base.tarjar_sensivel_sempre | frozenset(sempre),
        )
    return saida
