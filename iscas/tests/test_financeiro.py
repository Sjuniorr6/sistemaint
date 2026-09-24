"""Receita, custo e margem por solicitação (ISC-RF-39).

O que estes testes fixam não é aritmética — é a SEMÂNTICA das ausências:
cancelada não custa, retirada não custa, sem valor não é zero.
"""
from decimal import Decimal

import pytest

from iscas.services import financeiro
from iscas.services import solicitacao as service

pytestmark = pytest.mark.django_db


@pytest.fixture
def pedido(cliente, operador, modelo_descartavel):
    def _criar(valor=None, quantidade=10):
        return service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, quantidade)],
            autor=operador, valor_cliente=valor,
        )

    return _criar


class TestTotais:
    def test_receita_menos_custo(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        solicitacao = pedido(valor=Decimal("500.00"))
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("120.00"),
        )

        totais = financeiro.totais_da_solicitacao(solicitacao)

        assert totais["valor_cliente"] == Decimal("500.00")
        assert totais["custo_agentes"] == Decimal("120.00")
        assert totais["margem"] == Decimal("380.00")
        assert totais["tem_custo_incompleto"] is False

    # sabotagem: incluir CANCELADA em _STATUS_QUE_CUSTAM → vermelho
    def test_cancelada_nao_custa(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        """O agente não entregou — não há o que pagar."""
        solicitacao = pedido(valor=Decimal("500.00"))
        atribuicao = service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("120.00"),
        )
        service.cancelar_atribuicao(
            atribuicao=atribuicao, motivo="desistiu", autor=operador
        )

        totais = financeiro.totais_da_solicitacao(solicitacao)

        assert totais["custo_agentes"] == Decimal("0.00")
        assert totais["margem"] == Decimal("500.00")

    def test_retirada_na_base_nao_custa(
        self, pedido, operador, deposito, modelo_descartavel, unidades_no_deposito
    ):
        solicitacao = pedido(valor=Decimal("300.00"))
        service.criar_atribuicao(
            solicitacao=solicitacao, deposito=deposito,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )

        totais = financeiro.totais_da_solicitacao(solicitacao)

        assert totais["custo_agentes"] == Decimal("0.00")
        assert totais["margem"] == Decimal("300.00")
        assert totais["tem_custo_incompleto"] is False

    # sabotagem: tratar valor_cliente None como Decimal("0") → vermelho
    def test_sem_valor_a_margem_e_none_nao_zero(self, pedido):
        """Zero é cortesia; None é "ninguém informou". Não são a mesma coisa."""
        totais = financeiro.totais_da_solicitacao(pedido(valor=None))

        assert totais["valor_cliente"] is None
        assert totais["margem"] is None

    def test_agente_sem_valor_levanta_a_flag(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        """Somar zero e ficar calado faria a margem mentir."""
        solicitacao = pedido(valor=Decimal("500.00"))
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )

        totais = financeiro.totais_da_solicitacao(solicitacao)

        assert totais["custo_agentes"] == Decimal("0.00")
        assert totais["tem_custo_incompleto"] is True

    def test_margem_negativa_e_reportada(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        """Cobrar mais que o cliente pagou é alerta de negócio, não erro."""
        solicitacao = pedido(valor=Decimal("50.00"))
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("80.00"),
        )

        assert financeiro.totais_da_solicitacao(solicitacao)["margem"] == Decimal("-30.00")

    def test_soma_dois_agentes(
        self, pedido, operador, agente, agente2, modelo_descartavel,
        unidades_com_agente,
    ):
        from iscas.services import transferencia as transferencia_service

        solicitacao = pedido(valor=Decimal("500.00"))
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("100.00"),
        )
        transferencia_service.transferir(
            origem=agente, destino=agente2, modelo=modelo_descartavel,
            quantidade=2, autor=operador,
        )
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente2,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("60.50"),
        )

        assert financeiro.totais_da_solicitacao(solicitacao)["custo_agentes"] == Decimal("160.50")


class TestEquivalenciaEmLote:
    """As duas funções precisam concordar — senão a lista e o detalhe divergem."""

    def test_lote_concorda_com_individual(
        self, pedido, operador, agente, deposito, modelo_descartavel,
        unidades_com_agente, unidades_no_deposito,
    ):
        com_agente = pedido(valor=Decimal("500.00"))
        service.criar_atribuicao(
            solicitacao=com_agente, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("120.00"),
        )
        com_retirada = pedido(valor=Decimal("300.00"))
        service.criar_atribuicao(
            solicitacao=com_retirada, deposito=deposito,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        sem_valor = pedido(valor=None)
        vazia = pedido(valor=Decimal("10.00"))

        todas = [com_agente, com_retirada, sem_valor, vazia]
        em_lote = financeiro.totais_em_lote(todas)

        for solicitacao in todas:
            assert em_lote[solicitacao.pk] == financeiro.totais_da_solicitacao(
                solicitacao
            ), f"divergiu na solicitação {solicitacao.pk}"

    def test_lote_vazio(self):
        assert financeiro.totais_em_lote([]) == {}

    # sabotagem: trocar a annotate por laço python → vermelho
    def test_consultas_nao_crescem_com_a_quantidade(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        """Impede a regressão para N+1 na listagem.

        Mede com solicitações que TÊM atribuição nas duas rodadas: com uma só,
        um laço em Python custaria o mesmo e o teste passaria sem o agregado.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def com_atribuicao(valor):
            solicitacao = pedido(valor=valor, quantidade=1)
            service.criar_atribuicao(
                solicitacao=solicitacao, agente=agente,
                itens=[(modelo_descartavel, 1)], autor=operador,
                valor_agente=Decimal("10.00"),
            )
            return solicitacao

        poucas = [com_atribuicao(Decimal("100.00")) for _ in range(2)]
        with CaptureQueriesContext(connection) as com_duas:
            financeiro.totais_em_lote(poucas)

        muitas = poucas + [com_atribuicao(Decimal("100.00")) for _ in range(6)]
        with CaptureQueriesContext(connection) as com_oito:
            financeiro.totais_em_lote(muitas)

        assert len(com_oito) == len(com_duas)


class TestReceitaComEntrega:
    """O frete cobrado do cliente soma na receita (decisão do usuário)."""

    # sabotagem: ignorar valor_entrega_cliente no _montar → vermelho
    def test_entrega_soma_na_receita_e_na_margem(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        solicitacao = pedido(valor=Decimal("500.00"))
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("80.00"),
            valor_entrega_cliente=Decimal("120.00"),
        )

        totais = financeiro.totais_da_solicitacao(solicitacao)

        assert totais["valor_cliente"] == Decimal("500.00")
        assert totais["valor_entregas"] == Decimal("120.00")
        assert totais["receita_total"] == Decimal("620.00")
        assert totais["custo_agentes"] == Decimal("80.00")
        assert totais["margem"] == Decimal("540.00")

    def test_sem_valor_de_material_a_margem_continua_none(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        """Frete sozinho não basta: faltaria a maior parte da receita."""
        solicitacao = pedido(valor=None)
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_entrega_cliente=Decimal("120.00"),
        )

        totais = financeiro.totais_da_solicitacao(solicitacao)

        assert totais["valor_entregas"] == Decimal("120.00")
        assert totais["receita_total"] is None
        assert totais["margem"] is None

    def test_retirada_na_base_nao_soma_entrega(
        self, pedido, operador, deposito, modelo_descartavel, unidades_no_deposito
    ):
        solicitacao = pedido(valor=Decimal("300.00"))
        service.criar_atribuicao(
            solicitacao=solicitacao, deposito=deposito,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )

        totais = financeiro.totais_da_solicitacao(solicitacao)

        assert totais["valor_entregas"] == Decimal("0.00")
        assert totais["receita_total"] == Decimal("300.00")

    def test_lote_concorda_com_individual_incluindo_entrega(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        """As duas funções compartilham `_com_totais` — o teste trava isso."""
        solicitacao = pedido(valor=Decimal("500.00"))
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("80.00"),
            valor_entrega_cliente=Decimal("120.00"),
        )

        em_lote = financeiro.totais_em_lote([solicitacao])

        assert em_lote[solicitacao.pk] == financeiro.totais_da_solicitacao(solicitacao)
