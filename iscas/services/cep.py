"""Busca de endereço por CEP (ViaCEP).

Complementa a geocodificação: o ViaCEP resolve CEP → logradouro/bairro/cidade/UF,
mas NÃO devolve coordenada. O fluxo do cadastro é:

    CEP → ViaCEP preenche o endereço → operador digita o número →
    ao salvar, Nominatim geocodifica o endereço completo (com número).

Incluir o número na consulta ao Nominatim é o que torna o pin preciso — sem ele
a coordenada cai no centroide da rua.

Mesma postura do `geo.py`: chamada síncrona, timeout curto, falha nunca bloqueia
o cadastro. O operador sempre pode digitar o endereço à mão.
"""
import json
import re
import urllib.error
import urllib.request

from django.conf import settings

from iscas.services.exceptions import IscasError

_SO_DIGITOS = re.compile(r"\D")


class CepInvalido(IscasError):
    """O CEP não tem 8 dígitos, ou não existe na base dos Correios."""


class CepIndisponivel(IscasError):
    """O serviço de CEP não respondeu. O operador digita o endereço à mão."""


def normalizar_cep(cep: str) -> str:
    """Reduz o CEP a 8 dígitos. Formatação não é dado."""
    return _SO_DIGITOS.sub("", cep or "")


def formatar_cep(cep: str) -> str:
    """`01310100` → `01310-100`, para exibição."""
    numeros = normalizar_cep(cep)
    if len(numeros) != 8:
        return cep or ""
    return f"{numeros[:5]}-{numeros[5:]}"


def buscar_cep(cep: str) -> dict:
    """Consulta o ViaCEP e devolve os campos de endereço.

    Returns:
        dict com `logradouro`, `bairro`, `cidade`, `uf`, `cep` (formatado).
        Campos que o ViaCEP não conhece vêm como string vazia — CEP de
        logradouro único (o caso dos CEPs "gerais" de cidade pequena) devolve
        logradouro e bairro vazios, e é o operador quem completa.

    Raises:
        CepInvalido: menos de 8 dígitos, ou CEP inexistente.
        CepIndisponivel: rede, timeout ou resposta ilegível.
    """
    numeros = normalizar_cep(cep)
    if len(numeros) != 8:
        raise CepInvalido("O CEP precisa ter 8 dígitos.")

    url = getattr(settings, "ISCAS_VIACEP_URL", "https://viacep.com.br/ws")
    timeout = getattr(settings, "ISCAS_CEP_TIMEOUT", 3)

    requisicao = urllib.request.Request(
        f"{url}/{numeros}/json/",
        headers={
            "User-Agent": getattr(
                settings, "ISCAS_NOMINATIM_USER_AGENT", "GSInt-IscasFast/1.0"
            )
        },
    )

    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # 400 do ViaCEP = CEP mal formatado; o resto é indisponibilidade.
        if exc.code == 400:
            raise CepInvalido("CEP em formato inválido.") from exc
        raise CepIndisponivel(
            f"O serviço de CEP respondeu com erro {exc.code}."
        ) from exc
    except Exception as exc:  # rede, timeout, JSON inválido — degradam igual
        raise CepIndisponivel(
            f"Não foi possível consultar o CEP: {exc}"
        ) from exc

    # O ViaCEP sinaliza CEP inexistente com {"erro": true} e HTTP 200.
    # Aceita bool e string porque a API já devolveu as duas formas.
    if dados.get("erro") in (True, "true", "True"):
        raise CepInvalido("CEP não encontrado.")

    return {
        "cep": formatar_cep(dados.get("cep") or numeros),
        "logradouro": dados.get("logradouro") or "",
        "complemento": dados.get("complemento") or "",
        "bairro": dados.get("bairro") or "",
        "cidade": dados.get("localidade") or "",
        "uf": (dados.get("uf") or "").upper(),
    }
