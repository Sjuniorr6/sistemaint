"""Devolução de iscas do cliente — retornável ou descartável com defeito."""
import pytest
from django.urls import reverse

from iscas.enums import MotivoBaixa, TipoCustodia, TipoMovimentacao
from iscas.models.cadastro import Cliente
from iscas.services import custodia as custodia_service
from iscas.services import retorno as retorno_service
from iscas.services.exceptions import MovimentacaoInvalida, UnidadeTerminal

pytestmark = pytest.mark.django_db


@pytest.fixture
def outro_cliente(db):
    return Cliente.objects.create(
        nome_razao_social="Outro Cliente SA", documento="45723174000110",
        contato_nome="C", telefone="1130000000", logradouro="Rua B", numero="2",
        cidade="Santos", uf="SP",
    )


def _entregar(unidades, agente, cliente, operador):
    custodia_service.registrar_movimentacao(
        tipo=TipoMovimentacao.ENTREGA, origem=agente, destino=cliente,
        unidades=unidades, autor=operador,
    )


# sabotagem: tirar a exceção de RETORNO-de-cliente em _eh_terminal → vermelho
def test_devolve_descartavel_e_retornavel_de_dois_clientes(
    agente, cliente, outro_cliente, deposito, operador,
    unidades_com_agente, retornaveis_com_agente,
):
    _entregar(unidades_com_agente[:2], agente, cliente, operador)
    _entregar(retornaveis_com_agente[:1], agente, outro_cliente, operador)
    devolvidas = [*unidades_com_agente[:2], *retornaveis_com_agente[:1]]

    movimentacoes = retorno_service.registrar_devolucao(
        unidades=devolvidas, destino=deposito, motivo="Isca com defeito", autor=operador,
    )

    assert len(movimentacoes) == 2
    assert {m.justificativa for m in movimentacoes} == {"Isca com defeito"}
    for unidade in devolvidas:
        unidade.refresh_from_db()
        assert unidade.custodia_atual.deposito == deposito


# sabotagem: remover a recusa de unidade fora de cliente em registrar_devolucao → vermelho
def test_unidade_fora_de_cliente_recusa_a_devolucao_inteira(
    agente, cliente, deposito, operador, unidades_com_agente,
):
    _entregar(unidades_com_agente[:1], agente, cliente, operador)

    with pytest.raises(MovimentacaoInvalida, match="não estão com cliente"):
        retorno_service.registrar_devolucao(
            unidades=unidades_com_agente[:2], destino=deposito,
            motivo="defeito", autor=operador,
        )
    unidades_com_agente[0].refresh_from_db()
    assert unidades_com_agente[0].custodia_atual.tipo == TipoCustodia.CLIENTE


# sabotagem: remover a exigência de motivo em registrar_devolucao → vermelho
def test_devolucao_exige_motivo(agente, cliente, deposito, operador, unidades_com_agente):
    _entregar(unidades_com_agente[:1], agente, cliente, operador)

    with pytest.raises(MovimentacaoInvalida, match="motivo"):
        retorno_service.registrar_devolucao(
            unidades=unidades_com_agente[:1], destino=deposito, motivo="  ", autor=operador,
        )


# sabotagem: liberar RETORNO antes da checagem de BAIXA em _eh_terminal → vermelho
def test_baixa_continua_terminal_para_retorno(deposito, agente, operador, unidades_no_deposito):
    baixa = custodia_service.custodia_singleton(TipoCustodia.BAIXA)
    custodia_service.registrar_movimentacao(
        tipo=TipoMovimentacao.BAIXA, origem=deposito, destino=baixa,
        unidades=unidades_no_deposito[:1], autor=operador,
        motivo_baixa=MotivoBaixa.PERDA, justificativa="Perdida",
    )

    with pytest.raises(UnidadeTerminal):
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.RETORNO, origem=baixa, destino=agente,
            unidades=unidades_no_deposito[:1], autor=operador,
        )


# sabotagem: tirar o filtro de custódia CLIENTE da busca → vermelho
def test_busca_so_traz_iscas_com_cliente(
    client, operador_logado, agente, cliente, operador, unidades_com_agente,
):
    _entregar(unidades_com_agente[:1], agente, cliente, operador)

    resposta = client.get(reverse("iscas:api_unidades_com_cliente"), {"q": "A00"})

    encontrados = [u["identificador"] for u in resposta.json()["unidades"]]
    assert encontrados == [unidades_com_agente[0].identificador]
