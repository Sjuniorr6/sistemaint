"""Assinatura mensal do cliente em pedido com isca retornável."""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from iscas.enums import TipoModelo
from iscas.models.operacao import Solicitacao
from iscas.services import financeiro
from iscas.services import solicitacao as service
from iscas.services.exceptions import MovimentacaoInvalida

pytestmark = pytest.mark.django_db

D, R = TipoModelo.DESCARTAVEL, TipoModelo.RETORNAVEL


def _post_abertura(cliente, **extra):
    return {
        "cliente": cliente.pk,
        "documento": cliente.documento,
        "telefone": cliente.telefone,
        "entrega_logradouro": cliente.logradouro,
        "entrega_numero": cliente.numero,
        "entrega_cidade": cliente.cidade,
        "entrega_uf": cliente.uf,
        f"quantidade_{R}": "2", f"preco_{R}": "100.00",
        **extra,
    }


# sabotagem: remover a exigência de assinatura com retornável em abrir_solicitacao → vermelho
def test_tela_recusa_retornavel_sem_assinatura(client, operador_logado, cliente):
    resposta = client.post(reverse("iscas:solicitacao_criar"), _post_abertura(cliente))

    assert "Informe o valor da assinatura mensal" in resposta.content.decode()
    assert not cliente.solicitacoes.exists()


# sabotagem: remover a recusa de assinatura sem retornável → vermelho
def test_service_recusa_assinatura_sem_retornavel(cliente, operador):
    with pytest.raises(MovimentacaoInvalida, match="só existe com isca retornável"):
        service.abrir_solicitacao(
            cliente=cliente, itens=[(D, 1, Decimal("10.00"))], autor=operador,
            valor_assinatura_mensal=Decimal("50.00"),
        )


# sabotagem: somar a assinatura em _total_dos_itens → vermelho
def test_assinatura_grava_e_fica_fora_do_total(client, operador_logado, cliente):
    client.post(
        reverse("iscas:solicitacao_criar"),
        _post_abertura(cliente, valor_assinatura_mensal="50.00"),
    )
    solicitacao = cliente.solicitacoes.get()

    assert solicitacao.valor_assinatura_mensal == Decimal("50.00")
    assert solicitacao.valor_cliente == Decimal("200.00")
    assert financeiro.totais_da_solicitacao(solicitacao)["receita_total"] == Decimal("200.00")


# sabotagem: remover iscas_sol_assinatura_nao_negativa da migração → vermelho
def test_banco_recusa_assinatura_negativa(cliente, operador):
    solicitacao = service.abrir_solicitacao(
        cliente=cliente, itens=[(R, 1)], autor=operador
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Solicitacao.objects.filter(pk=solicitacao.pk).update(
            valor_assinatura_mensal=Decimal("-1.00")
        )


# sabotagem: não zerar a assinatura em _totais_visiveis para quem não vê valor do cliente → vermelho
@pytest.mark.parametrize("usuario, ve", [
    ("comercial_logado", True),
    ("operador_fast_logado", False),
])
def test_assinatura_so_para_quem_ve_valor_do_cliente(
    request, usuario, ve, client, cliente, operador
):
    request.getfixturevalue(usuario)
    solicitacao = service.abrir_solicitacao(
        cliente=cliente, itens=[(R, 1, Decimal("10.00"))], autor=operador,
        valor_assinatura_mensal=Decimal("4321.87"),
    )

    resposta = client.get(reverse("iscas:solicitacao_detalhe", args=[solicitacao.pk]))

    # Contexto, não só HTML: o valor não pode nem chegar ao template.
    assert (resposta.context["totais"]["assinatura_mensal"] is not None) is ve
    assert ("4321,87" in resposta.content.decode()) is ve
