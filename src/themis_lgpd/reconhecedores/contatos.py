"""Reconhecedores de meios de contato: e-mail, telefone, perfis em redes sociais e URLs.

Os reconhecedores de e-mail e URL do Presidio não são usados porque consultam a lista pública de
sufixos de domínio pela internet (``tldextract``), o que contraria a operação offline. Endereços IP
ficam a cargo do ``IpRecognizer`` do Presidio, e telefones são reconhecidos tanto por este módulo
(formatos brasileiros, inclusive sem DDD) quanto pelo ``PhoneRecognizer`` do Presidio
(biblioteca ``phonenumbers``, região BR).
"""

from __future__ import annotations

import regex as re

from .base import ANTES_NUM, CONTEXTUAL, DEPOIS_NUM, Deteccao, Padrao, ReconhecedorPadroes

#: Palavras que indicam número de telefone; sustentam telefones sem DDD e números sem pontuação.
CTX_TEL = ("telefone", "tel", "fone", "celular", "cel", "whats(?:app)?", "zap", "contato", "ligar", "ramal",
           "fixo", "recado", "telefones")

#: Domínios em que o caminho da URL identifica uma pessoa (perfil, currículo, página pessoal).
REDES_SOCIAIS = (
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com", "tiktok.com", "linkedin.com",
    "youtube.com", "youtu.be", "wa.me", "t.me", "github.com", "threads.net", "bsky.app", "kwai.com",
    "pinterest.com", "flickr.com", "medium.com", "lattes.cnpq.br", "orcid.org", "escavador.com", "jusbrasil.com.br",
)

#: Regras de e-mail, telefone e perfil (``@usuario``).
PADROES: list[Padrao] = [
    Padrao("EMAIL", r"(?<![\w.%+\-])[\w.%+\-]{1,64}@[\w\-]{1,63}(?:\.[\w\-]{1,63})+(?<![.\-])", 0.95,
           nome="email"),
    # E-mail escrito de forma a escapar de filtros: "maria [at] gmail (ponto) com", "maria [arroba]
    # gmail [ponto] com", "maria @ gmail . com".
    Padrao("EMAIL",
           r"(?<![\w.])[\w.\-]{2,64}\s?(?:[\[({](?:at|arroba)[\])}]|\sarroba\s|\s@\s)\s?[\w\-]{2,63}"
           r"(?:\s?(?:\.|\s\.\s|[\[({](?:dot|ponto)[\])}]|\sponto\s|\sdot\s)\s?[\w\-]{2,10}){1,3}", 0.85,
           nome="email:ofuscado"),
    # Telefone com DDD, com ou sem o código do país (+55); celular com o nono dígito ou fixo.
    Padrao("TELEFONE",
           ANTES_NUM + r"(?:\+?\s?55[\s.\-]?)?(?:\(\s?0?[1-9]{2}\s?\)|0?[1-9]{2})[\s.\-]?(?:9\s?\d{4}|[2-9]\d{3})"
           r"[\s.\-]?\d{4}" + DEPOIS_NUM, 0.85, contexto=CTX_TEL, nome="telefone:ddd"),
    # Telefone sem DDD: exige hífen ou ponto separando os blocos e descarta intervalos de anos
    # ("2019-2020"), que têm a mesma forma.
    Padrao("TELEFONE",
           ANTES_NUM + r"(?!(?:19|20)\d{2}[\-.](?:19|20)\d{2})(?:9\s?\d{4}|[2-5]\d{3})[\-.]\d{4}" + DEPOIS_NUM,
           0.7, contexto=CTX_TEL, nome="telefone:local"),
    # Número sem pontuação logo após a palavra que o identifica ("Tel: 61999990000").
    Padrao("TELEFONE", r"(?:telefone|tel\.?|fone|celular|whats(?:app)?|zap)\s*[:\-]?\s*(?P<v>\d{8,11})(?!\d)", 0.85,
           camada=CONTEXTUAL, grupo="v", nome="telefone:contexto"),
    # Perfil "@usuario": não pode fazer parte de um e-mail; o contexto eleva a confiança.
    Padrao("PERFIL_REDE_SOCIAL", r"(?<![\w@.])@[A-Za-z0-9_](?:[A-Za-z0-9_.]{1,28}[A-Za-z0-9_])(?![\w@])", 0.75,
           contexto=("instagram", "insta", "twitter", "tiktok", "perfil", "rede social", "redes sociais",
                     "arroba", "threads", "kwai", "telegram"), nome="perfil:@"),
]

_URL = re.compile(r"(?:\bhttps?://|\bwww\.)[^\s<>\"'()\[\]{}]+", re.IGNORECASE)
_REDES = re.compile(r"(?:^|\.|//)(?:" + "|".join(re.escape(d) for d in REDES_SOCIAIS) + r")(?:[/:?#]|$)",
                    re.IGNORECASE)


class ReconhecedorURL:
    """Classifica URLs em perfil pessoal ou endereço genérico.

    * URL de rede social com caminho (``instagram.com/maria.souza``) → ``PERFIL_REDE_SOCIAL``.
    * URL com ``@`` ou parâmetro pessoal (``?cpf=``, ``?email=``) → ``PERFIL_REDE_SOCIAL``.
    * Demais URLs → ``URL``, que os perfis em geral mantêm visível (endereço institucional).

    A pontuação final de frase não é incluída no trecho.
    """

    nome = "url"

    def detectar(self, texto: str) -> list[Deteccao]:
        """URLs encontradas no texto, já classificadas."""
        saida = []
        for m in _URL.finditer(texto):
            ini, fim = m.span()
            while fim > ini and texto[fim - 1] in ".,;:!?":
                fim -= 1
            url = texto[ini:fim]
            if _REDES.search(url) and re.search(r"\.[a-z]{2,}(?:\.[a-z]{2})?/[^/?#\s]{2,}", url, re.IGNORECASE):
                saida.append(Deteccao(ini, fim, "PERFIL_REDE_SOCIAL", 0.9, "url:rede-social"))
            elif "@" in url or re.search(r"[?&](?:cpf|email|nome|user|id)=", url, re.IGNORECASE):
                saida.append(Deteccao(ini, fim, "PERFIL_REDE_SOCIAL", 0.8, "url:parametro-pessoal"))
            else:
                saida.append(Deteccao(ini, fim, "URL", 0.6, "url:generica"))
        return saida


def reconhecedores():
    """Reconhecedores deste módulo, na forma esperada por :mod:`themis_lgpd.analisador`."""
    return [ReconhecedorPadroes("contatos", PADROES), ReconhecedorURL()]
