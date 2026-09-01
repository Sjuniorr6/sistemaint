"""O estorno saiu da tela, mas continua existindo como caminho de correcao.

Esconder o botao e decisao de interface. Se a ROTA cair junto, um lancamento
errado passa a nao ter conserto pela aplicacao — e baixa indevida prende a
unidade em estado terminal.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, TipoMovimentacao
from iscas.services import entrada as entrada_service
from iscas.services import transferencia as transferencia_service
from iscas.services.saldo import saldo_em_custodia

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


@pytest.fixture
def movimentacao(deposito, agente, modelo_descartavel, operador):
    """Uma transferencia deposito → agente, candidata a estorno."""
    _, unidades = entrada_service.registrar_entrada(
        modelo=modelo_descartavel,
        identificadores=["E001", "E002"],
        destino=deposito,
        autor=operador,
    )
    return transferencia_service.transferir(
        origem=deposito, destino=agente, unidades=unidades, autor=operador
    )


def test_botao_de_estorno_nao_aparece(client, operador_logado, movimentacao):
    conteudo = client.get(reverse("iscas:extrato")).content.decode()

    # O lancamento aparece; o botao de desfazer, nao.
    assert f"#{movimentacao.pk}" in conteudo
    assert "Estornar" not in conteudo
    assert f'id="estorno{movimentacao.pk}"' not in conteudo


def test_a_rota_de_estorno_continua_funcionando(
    client, operador_logado, movimentacao, deposito, agente, modelo_descartavel
):
    """A correcao segue possivel por URL direta — e o que torna a remocao
    reversivel sem risco de deixar lancamento errado preso."""
    assert saldo_em_custodia(agente, modelo=modelo_descartavel) == 2

    resposta = client.post(
        reverse("iscas:estornar", args=[movimentacao.pk]),
        {"justificativa": "Transferência lançada para o agente errado"},
    )

    assert resposta.status_code == 302
    # As unidades voltaram ao depósito.
    assert saldo_em_custodia(agente, modelo=modelo_descartavel) == 0
    assert saldo_em_custodia(deposito, modelo=modelo_descartavel) == 2

    movimentacao.refresh_from_db()
    assert movimentacao.foi_estornada
    # O original permanece intacto no histórico (ISC-ADR-16).
    assert movimentacao.tipo == TipoMovimentacao.TRANSFERENCIA


def test_estorno_feito_por_fora_aparece_no_extrato(
    client, operador_logado, movimentacao, operador
):
    """Escondido o botao, o REGISTRO do estorno continua visivel — senao a
    correcao viraria movimento invisivel no extrato."""
    from iscas.services import estorno as estorno_service

    estorno_service.estornar(
        movimentacao=movimentacao, autor=operador, justificativa="Engano"
    )
    conteudo = client.get(reverse("iscas:extrato")).content.decode()

    assert "anulada pelo estorno" in conteudo
    assert f"desfaz o lançamento #{movimentacao.pk}" in conteudo
