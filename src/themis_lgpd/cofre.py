"""Cofre de reversão: pseudonimização reversível, desativada por padrão.

O cofre guarda, cifrado com senha, o mapa "trecho substituído → valor original" de um texto
anonimizado. A chave é derivada da senha com scrypt e o conteúdo é cifrado com Fernet (AES-128-CBC
com HMAC-SHA256). Sem a senha, o arquivo não revela nenhum valor; com ela, o texto original pode ser
reconstituído.

Por permitir a reversão, o uso do cofre caracteriza **pseudonimização**, e não anonimização, na
terminologia da LGPD e da ANPD. O cofre e a senha devem ser guardados separados do documento
publicado, com o mesmo cuidado dispensado ao documento original.
"""

from __future__ import annotations

import base64
import json
import os

from .motor import Resultado

_VERSAO = 1

#: Tamanho mínimo da senha do cofre.
MINIMO_SENHA = 12

# Parâmetros do scrypt (custo de CPU e memória de ~32 MiB), adequados a uma derivação interativa.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**15, 8, 1


def _chave(senha: str, sal: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    kdf = Scrypt(salt=sal, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return base64.urlsafe_b64encode(kdf.derive(senha.encode("utf-8")))


def criar_cofre(resultado: Resultado, senha: str) -> bytes:
    """Cria o cofre de reversão de um resultado.

    Args:
        resultado: Resultado da anonimização de um texto.
        senha: Senha com pelo menos :data:`MINIMO_SENHA` caracteres.

    Returns:
        Conteúdo do arquivo de cofre (JSON com sal e dados cifrados).

    Raises:
        ValueError: Senha curta demais.
    """
    if len(senha) < MINIMO_SENHA:
        raise ValueError(f"Use uma senha com pelo menos {MINIMO_SENHA} caracteres para o cofre.")
    from cryptography.fernet import Fernet

    sal = os.urandom(16)
    conteudo = json.dumps({
        "texto_anonimizado_tamanho": len(resultado.texto),
        "substituicoes": [{k: s[k] for k in ("inicio_saida", "fim_saida", "original", "substituto")}
                          for s in resultado.substituicoes],
    }, ensure_ascii=False).encode("utf-8")
    token = Fernet(_chave(senha, sal)).encrypt(conteudo)
    return json.dumps({"themis_cofre": _VERSAO, "sal": base64.b64encode(sal).decode(),
                       "dados": token.decode()}).encode("utf-8")


def reverter(texto_anonimizado: str, cofre: bytes, senha: str) -> str:
    """Reconstitui o texto original a partir do texto anonimizado e do cofre.

    Raises:
        ValueError: Cofre inválido, senha incorreta, cofre adulterado ou texto anonimizado
            modificado depois da geração do cofre.
    """
    from cryptography.fernet import Fernet, InvalidToken

    pacote = json.loads(cofre)
    if pacote.get("themis_cofre") != _VERSAO:
        raise ValueError("Arquivo de cofre inválido.")
    try:
        dados = json.loads(Fernet(_chave(senha, base64.b64decode(pacote["sal"]))).decrypt(pacote["dados"].encode()))
    except InvalidToken as erro:
        raise ValueError("Senha incorreta ou cofre adulterado.") from erro
    if dados["texto_anonimizado_tamanho"] != len(texto_anonimizado):
        raise ValueError("O texto não corresponde ao cofre (foi editado depois da anonimização?).")
    texto = texto_anonimizado
    # Da última para a primeira substituição, para que as posições anteriores continuem válidas.
    for s in sorted(dados["substituicoes"], key=lambda s: s["inicio_saida"], reverse=True):
        if texto[s["inicio_saida"]:s["fim_saida"]] != s["substituto"]:
            raise ValueError("O texto não corresponde ao cofre.")
        texto = texto[:s["inicio_saida"]] + s["original"] + texto[s["fim_saida"]:]
    return texto
