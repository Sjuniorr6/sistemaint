"""Pedágio pago pelo agente: repasse — soma na receita e no custo."""
import re
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from iscas.enums import OrigemAtribuicao, StatusAtribuicao, StatusSolicitacao
from iscas.models.operacao import Atribuicao, Solicitacao
from iscas.services import financeiro
from iscas.services import solicitacao as service

pytestmark = pytest.mark.django_db


@pytest.fixture
def pedido(cliente, operador, modelo_descartavel):
    return service.abrir_solicitacao(
        cliente=cliente, itens=[(modelo_descartavel, 4)], autor=operador,
        valor_cliente=Decimal("500.00"),
    )


def _totais_unitario(solicitacao):
    return financeiro.totais_da_solicitacao(solicitacao)


def _totais_em_lote(solicitacao):
    return financeiro.totais_em_lote([solicitacao])[solicitacao.pk]


# sabotagem: tirar o pedágio da receita ou do custo em _montar / totais_em_lote → vermelho
@pytest.mark.parametrize("calcular", [_totais_unitario, _totais_em_lote])
def test_pedagio_e_repasse_nas_duas_pontas(
    calcular, pedido, operador, agente, modelo_descartavel, unidades_com_agente
):
    service.criar_atribuicao(
        solicitacao=pedido, agente=agente, itens=[(modelo_descartavel, 2)],
        autor=operador, valor_agente=Decimal("80.00"),
        valor_entrega_cliente=Decimal("160.00"), valor_pedagio=Decimal("30.00"),
    )

    totais = calcular(pedido)

    assert totais["valor_pedagios"] == Decimal("30.00")
    assert totais["receita_total"] == Decimal("690.00")
    assert totais["custo_agentes"] == Decimal("110.00")
    assert totais["margem"] == Decimal("580.00")


# sabotagem: tirar valor_pedagio de _campos_da_origem → vermelho
def test_pedagio_sobrevive_aos_dois_passos(
    client, operador_logado, pedido, agente, modelo_descartavel, unidades_com_agente
):
    url = reverse("iscas:solicitacao_atribuir", args=[pedido.pk])
    dados = {
        "origem_tipo": OrigemAtribuicao.AGENTE,
        "agente": agente.pk,
        "valor_agente": "80.00",
        "valor_pedagio": "30.00",
    }
    passo_2 = client.post(url, dados).content.decode()
    # O passo 2 envia só o que a tela devolveu em hidden — como o navegador.
    reenviados = dict(re.findall(r'type="hidden" name="(\w+)" value="([^"]*)"', passo_2))
    client.post(url, {
        **reenviados, "confirmar": "1",
        f"unidades_{modelo_descartavel.pk}": [u.pk for u in unidades_com_agente[:2]],
    })

    assert pedido.atribuicoes.get().valor_pedagio == Decimal("30.00")


# sabotagem: remover cada AddConstraint da migração 0014 → vermelho
@pytest.mark.parametrize("origem, valor", [
    ("retirada", Decimal("10.00")),
    ("agente", Decimal("-0.01")),
])
def test_banco_recusa_pedagio_invalido(
    origem, valor, cliente, operador, agente, deposito
):
    solicitacao = Solicitacao.objects.create(
        cliente=cliente, aberta_em=timezone.now(), aberta_por=operador,
        status=StatusSolicitacao.ABERTA,
    )
    destino = (
        {"origem_tipo": OrigemAtribuicao.RETIRADA_BASE, "deposito": deposito}
        if origem == "retirada"
        else {"origem_tipo": OrigemAtribuicao.AGENTE, "agente": agente}
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Atribuicao.objects.create(
                solicitacao=solicitacao, criada_por=operador,
                status=StatusAtribuicao.RESERVADA, valor_pedagio=valor, **destino,
            )


# sabotagem: remover a checagem de pedágio em retirada no form → vermelho
def test_form_recusa_pedagio_em_retirada(
    client, operador_logado, pedido, deposito, unidades_no_deposito
):
    resposta = client.post(
        reverse("iscas:solicitacao_atribuir", args=[pedido.pk]),
        {
            "origem_tipo": OrigemAtribuicao.RETIRADA_BASE,
            "deposito": deposito.pk,
            "valor_pedagio": "10.00",
        },
        follow=True,
    )

    assert "Retirada na base não tem pedágio a pagar." in resposta.content.decode()
