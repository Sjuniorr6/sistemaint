"""Criptografia e hash do CPF do agente (ISC-ADR-14, ISC-RN-16).

O CPF é dado pessoal sensível sob a LGPD. Fica cifrado em repouso; a unicidade
é garantida por um hash SHA-256 com pepper, indexado UNIQUE — assim o sistema
detecta agente duplicado sem precisar decifrar a base inteira a cada validação.

Consequência assumida no ADR: busca por CPF só por igualdade (via hash), nunca
por trecho. E a chave entra na rotina de backup de segredos — perdê-la torna os
CPFs ilegíveis.

Chave e pepper vêm de settings (`ISCAS_CPF_KEY`, `ISCAS_CPF_PEPPER`). Em DEBUG,
sem configuração, derivamos ambos do SECRET_KEY para não travar o
desenvolvimento; em produção a ausência é erro explícito — falhar cedo é melhor
que cifrar a base com uma chave derivada por acidente.
"""
import base64
import hashlib
import hmac
import re

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet, InvalidToken

_SO_DIGITOS = re.compile(r"\D")


def normalizar_cpf(cpf: str) -> str:
    """Reduz o CPF a 11 dígitos. Formatação não é dado."""
    return _SO_DIGITOS.sub("", cpf or "")


def cpf_valido(cpf: str) -> bool:
    """Valida CPF pelos dois dígitos verificadores."""
    numeros = normalizar_cpf(cpf)
    if len(numeros) != 11 or numeros == numeros[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(
            int(numeros[i]) * (tamanho + 1 - i) for i in range(tamanho)
        )
        digito = (soma * 10) % 11 % 10
        if digito != int(numeros[tamanho]):
            return False
    return True


def _material_de_fallback(rotulo: str) -> bytes:
    """Deriva material de chave do SECRET_KEY — apenas fora de produção."""
    if not settings.DEBUG:
        raise ImproperlyConfigured(
            f"ISCAS_CPF_{rotulo} não configurado. O app Iscas Fast cifra o CPF "
            "do agente em repouso (ISC-ADR-14) e exige chave e pepper próprios "
            "em produção."
        )
    return hashlib.sha256(
        f"iscas-{rotulo}-{settings.SECRET_KEY}".encode()
    ).digest()


def _fernet() -> Fernet:
    chave = getattr(settings, "ISCAS_CPF_KEY", "") or ""
    if not chave:
        chave = base64.urlsafe_b64encode(_material_de_fallback("KEY")).decode()
    if isinstance(chave, str):
        chave = chave.encode()
    try:
        return Fernet(chave)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "ISCAS_CPF_KEY inválida: precisa ser uma chave Fernet "
            "(32 bytes em base64 urlsafe, como Fernet.generate_key() produz)."
        ) from exc


def _pepper() -> bytes:
    pepper = getattr(settings, "ISCAS_CPF_PEPPER", "") or ""
    if not pepper:
        return _material_de_fallback("PEPPER")
    return pepper.encode() if isinstance(pepper, str) else pepper


def cifrar_cpf(cpf: str) -> str:
    """Cifra o CPF normalizado para gravação."""
    numeros = normalizar_cpf(cpf)
    if not numeros:
        return ""
    return _fernet().encrypt(numeros.encode()).decode()


def decifrar_cpf(valor: str) -> str:
    """Decifra o CPF. Devolve "" se o valor for ilegível.

    Token inválido não estoura: um CPF ilegível (chave rotacionada, dado
    legado) não pode derrubar a listagem de agentes. A ausência aparece como
    campo vazio na UI.
    """
    if not valor:
        return ""
    try:
        return _fernet().decrypt(valor.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return ""


def hash_cpf(cpf: str) -> str:
    """Hash SHA-256 com pepper, para o índice UNIQUE (ISC-ADR-14).

    HMAC em vez de concatenação simples: é a construção correta para hash com
    chave secreta.
    """
    numeros = normalizar_cpf(cpf)
    if not numeros:
        return ""
    return hmac.new(_pepper(), numeros.encode(), hashlib.sha256).hexdigest()


def mascarar_cpf(cpf: str) -> str:
    """`***.456.789-**` — o que as listagens podem exibir (ISC-RN-16)."""
    numeros = normalizar_cpf(cpf)
    if len(numeros) != 11:
        return "***"
    return f"***.{numeros[3:6]}.{numeros[6:9]}-**"
