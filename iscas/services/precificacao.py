"""Quanto o agente cobra por uma atribuição, pela tabela dele.

- Retirada (o cliente busca na casa do agente): `Agente.valor_retirada`.
- Entrega: distância em linha reta da base do agente ao ponto de entrega →
  menor faixa que cobre essa distância (até X km, inclusive) → 2 × o valor
  da faixa, porque o agente vai e volta. Acima da última faixa, vale a
  última.

O resultado é SUGESTÃO: preenche o campo, o operador pode ajustar. Quando
falta dado (tabela, valor de retirada, coordenada), não há sugestão — `None`,
nunca zero: zero seria uma afirmação de que a entrega é de graça.
"""
import math
from decimal import Decimal

from iscas.enums import FormaEntrega
from iscas.services.geo import RAIO_TERRA_KM

#: Ida e volta: o agente paga o trajeto de volta à base.
_PERNAS = 2


def distancia_km(lat1, lng1, lat2, lng2) -> float:
    """Haversine em Python — mesma fórmula que a busca por proximidade usa."""
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = p2 - p1
    dl = math.radians(float(lng2) - float(lng1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RAIO_TERRA_KM * math.asin(min(1.0, math.sqrt(a)))


def preco_da_faixa(faixas, distancia):
    """`(km_ate, valor)` da menor faixa com `km_ate >= distancia`.

    Acima da última, devolve a última (decisão do negócio). `faixas` é uma
    lista de pares `(km_ate, valor)` em qualquer ordem; vazia → `None`.
    """
    ordenadas = sorted(faixas, key=lambda f: f[0])
    if not ordenadas:
        return None
    for km_ate, valor in ordenadas:
        if distancia <= km_ate:
            return km_ate, valor
    return ordenadas[-1]


def _moeda(valor) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def valor_sugerido(*, agente, solicitacao, forma_entrega):
    """Sugestão de valor do agente para esta solicitação.

    Returns:
        `{"valor": Decimal, "explicacao": str, "distancia_km": float|None}`,
        ou `None` quando a tabela do agente não permite calcular.
    """
    if forma_entrega == FormaEntrega.RETIRADA:
        if agente.valor_retirada is None:
            return None
        return {
            "valor": agente.valor_retirada,
            "explicacao": f"Retirada com o agente: {_moeda(agente.valor_retirada)}",
            "distancia_km": None,
        }

    destino = solicitacao.coordenada_de_busca
    if destino is None or agente.latitude is None or agente.longitude is None:
        return None

    faixas = list(agente.faixas_preco.values_list("km_ate", "valor"))
    distancia = distancia_km(agente.latitude, agente.longitude, *destino)
    faixa = preco_da_faixa(faixas, distancia)
    if faixa is None:
        return None

    km_ate, valor_faixa = faixa
    valor = (valor_faixa * _PERNAS).quantize(Decimal("0.01"))
    acima = " (acima da tabela: última faixa)" if distancia > km_ate else ""
    km_txt = f"{distancia:.1f}".replace(".", ",")
    return {
        "valor": valor,
        "explicacao": (
            f"{km_txt} km → faixa até {km_ate} km{acima}: "
            f"{_PERNAS} × {_moeda(valor_faixa)} (ida e volta) = {_moeda(valor)}"
        ),
        "distancia_km": round(distancia, 1),
    }
