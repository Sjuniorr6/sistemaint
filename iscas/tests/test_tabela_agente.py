"""Tabela de preço do agente: retirada e faixas de km (ida e volta)."""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from iscas.enums import FormaEntrega, TipoModelo
from iscas.models import FaixaPrecoAgente
from iscas.services import precificacao
from iscas.services import solicitacao as solicitacao_service

pytestmark = pytest.mark.django_db

FAIXAS = [(30, Decimal("100.00")), (80, Decimal("130.00"))]


# sabotagem: trocar `<=` por `<` na escolha da faixa → vermelho (30 km cai na seguinte)
@pytest.mark.parametrize("distancia, esperado", [
    (10, Decimal("100.00")),
    (30, Decimal("100.00")),
    (30.01, Decimal("130.00")),
    (120, Decimal("130.00")),  # acima da tabela: última faixa
])
def test_escolhe_a_menor_faixa_que_cobre_a_distancia(distancia, esperado):
    assert precificacao.preco_da_faixa(FAIXAS, distancia)[1] == esperado


@pytest.fixture
def agente_com_tabela(agente):
    agente.valor_retirada = Decimal("50.00")
    agente.save(update_fields=["valor_retirada"])
    FaixaPrecoAgente.objects.bulk_create(
        FaixaPrecoAgente(agente=agente, km_ate=km, valor=valor) for km, valor in FAIXAS
    )
    return agente


@pytest.fixture
def pedido(cliente, operador):
    return solicitacao_service.abrir_solicitacao(
        cliente=cliente, itens=[(TipoModelo.DESCARTAVEL, 2)], autor=operador
    )


# sabotagem: tirar o fator 2 (ida e volta) em valor_sugerido → vermelho
# sabotagem: devolver a faixa também na retirada → vermelho
@pytest.mark.parametrize("forma, esperado", [
    (FormaEntrega.ENTREGA, Decimal("200.00")),  # ~1,5 km → faixa até 30 → 2 × 100
    (FormaEntrega.RETIRADA, Decimal("50.00")),
])
def test_valor_sugerido_por_forma_de_entrega(agente_com_tabela, pedido, forma, esperado):
    sugestao = precificacao.valor_sugerido(
        agente=agente_com_tabela, solicitacao=pedido, forma_entrega=forma
    )
    assert sugestao["valor"] == esperado


# sabotagem: devolver valor zero em vez de None quando falta dado → vermelho
@pytest.mark.parametrize("falta", ["tabela", "coordenada"])
def test_sem_dado_suficiente_nao_ha_sugestao(agente, agente_com_tabela, pedido, falta):
    if falta == "tabela":
        FaixaPrecoAgente.objects.filter(agente=agente).delete()
    else:
        agente.latitude = agente.longitude = None
        agente.save(update_fields=["latitude", "longitude"])

    assert precificacao.valor_sugerido(
        agente=agente, solicitacao=pedido, forma_entrega=FormaEntrega.ENTREGA
    ) is None


# sabotagem: remover iscas_faixa_km_unico da migração → vermelho
def test_banco_recusa_duas_faixas_com_o_mesmo_km(agente_com_tabela):
    with pytest.raises(IntegrityError), transaction.atomic():
        FaixaPrecoAgente.objects.create(agente=agente_com_tabela, km_ate=30, valor=Decimal("1.00"))


# sabotagem: não salvar o formset de faixas em agente_editar → vermelho
def test_edicao_do_agente_grava_retirada_e_faixas(client, operador_logado, agente):
    pagina = client.get(reverse("iscas:agente_editar", args=[agente.pk]))
    dados = {
        campo.html_name: campo.value() or ""
        for campo in pagina.context["form"]
        if campo.name != "cpf"
    }
    dados.update({
        "cpf": agente.cpf,
        "valor_retirada": "50.00",
        "faixas-TOTAL_FORMS": "2", "faixas-INITIAL_FORMS": "0",
        "faixas-MIN_NUM_FORMS": "0", "faixas-MAX_NUM_FORMS": "1000",
        "faixas-0-km_ate": "30", "faixas-0-valor": "100.00",
        "faixas-1-km_ate": "80", "faixas-1-valor": "130.00",
    })

    client.post(reverse("iscas:agente_editar", args=[agente.pk]), dados)

    agente.refresh_from_db()
    assert agente.valor_retirada == Decimal("50.00")
    assert list(agente.faixas_preco.values_list("km_ate", "valor")) == FAIXAS


def test_endpoint_devolve_a_sugestao_com_explicacao(
    client, operador_logado, agente_com_tabela, pedido,
):
    resposta = client.get(reverse("iscas:api_valor_agente"), {
        "solicitacao": pedido.pk, "agente": agente_com_tabela.pk, "forma": FormaEntrega.ENTREGA,
    })

    dados = resposta.json()
    assert dados["valor"] == "200.00"
    assert "faixa até 30 km" in dados["explicacao"]
