"""Preço unitário por item e o total derivado dele.

O total da solicitação deixa de ser digitado e passa a ser calculado. A regra
que mais importa aqui não é a soma — é a recusa da MISTURA: somar só os itens
que têm preço produziria um total que mente sobre o pedido inteiro.
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from iscas.models.operacao import ItemSolicitacao
from iscas.services import solicitacao as service
from iscas.services.exceptions import MovimentacaoInvalida

pytestmark = pytest.mark.django_db


class TestConstraint:
    # sabotagem: remover iscas_item_valor_unitario_nao_negativo → vermelho
    def test_recusa_negativo(self, cliente, operador, modelo_descartavel):
        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador,
        )
        item = solicitacao.itens.get()

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ItemSolicitacao.objects.filter(pk=item.pk).update(
                    valor_unitario=Decimal("-0.01")
                )

    def test_aceita_nulo(self, cliente, operador, modelo_descartavel):
        """Prova que a migration roda sobre as solicitações já gravadas."""
        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador,
        )

        assert solicitacao.itens.get().valor_unitario is None


class TestTotalCalculado:
    def test_soma_dois_modelos_de_precos_diferentes(
        self, cliente, operador, modelo_descartavel, modelo_retornavel
    ):
        solicitacao = service.abrir_solicitacao(
            cliente=cliente, autor=operador,
            itens=[
                (modelo_descartavel, 2, Decimal("450.00")),
                (modelo_retornavel, 3, Decimal("100.00")),
            ],
        )

        assert solicitacao.valor_cliente == Decimal("1200.00")
        assert solicitacao.itens.get(modelo=modelo_descartavel).valor_unitario == Decimal("450.00")

    # sabotagem: somar só os itens com preço em vez de recusar → vermelho
    def test_recusa_mistura_com_e_sem_preco(
        self, cliente, operador, modelo_descartavel, modelo_retornavel
    ):
        """Total parcial mente sobre o pedido inteiro."""
        from iscas.models.operacao import Solicitacao

        antes = Solicitacao.todos.count()

        with pytest.raises(MovimentacaoInvalida):
            service.abrir_solicitacao(
                cliente=cliente, autor=operador,
                itens=[
                    (modelo_descartavel, 2, Decimal("450.00")),
                    (modelo_retornavel, 3),
                ],
            )

        assert Solicitacao.todos.count() == antes

    def test_tupla_de_dois_continua_valida(
        self, cliente, operador, modelo_descartavel
    ):
        """~15 chamadas legadas dependem disso, incluindo test_arquitetura."""
        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador,
            valor_cliente=Decimal("900.00"),
        )

        assert solicitacao.valor_cliente == Decimal("900.00")
        assert solicitacao.itens.get().valor_unitario is None

    def test_preco_dos_itens_vence_o_parametro(
        self, cliente, operador, modelo_descartavel
    ):
        """O total vem dos itens — o parâmetro é caminho legado, não override."""
        solicitacao = service.abrir_solicitacao(
            cliente=cliente, autor=operador,
            itens=[(modelo_descartavel, 2, Decimal("450.00"))],
            valor_cliente=Decimal("1.00"),
        )

        assert solicitacao.valor_cliente == Decimal("900.00")

    @pytest.mark.parametrize("quantidade,unitario,esperado", [
        (3, "333.333", "1000.00"),
        (7, "0.015", "0.11"),
        (1, "0.005", "0.01"),
    ])
    def test_arredondamento_em_duas_casas(
        self, cliente, operador, modelo_descartavel, quantidade, unitario, esperado
    ):
        """Sem quantize, o Decimal produz 4 casas e o SQLite trunca calado."""
        solicitacao = service.abrir_solicitacao(
            cliente=cliente, autor=operador,
            itens=[(modelo_descartavel, quantidade, Decimal(unitario))],
        )

        assert solicitacao.valor_cliente == Decimal(esperado)

    def test_exigir_valor_recusa_item_sem_preco(
        self, cliente, operador, modelo_descartavel
    ):
        with pytest.raises(MovimentacaoInvalida):
            service.abrir_solicitacao(
                cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador,
                exigir_valor=True,
            )

    def test_exigir_valor_aceita_com_preco(
        self, cliente, operador, modelo_descartavel
    ):
        solicitacao = service.abrir_solicitacao(
            cliente=cliente, autor=operador, exigir_valor=True,
            itens=[(modelo_descartavel, 2, Decimal("450.00"))],
        )

        assert solicitacao.valor_cliente == Decimal("900.00")


class TestNaoRegressaoFinanceiro:
    def test_totais_seguem_iguais_no_caminho_legado(
        self, cliente, operador, modelo_descartavel
    ):
        from iscas.services import financeiro

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador,
            valor_cliente=Decimal("900.00"),
        )

        assert financeiro.totais_da_solicitacao(solicitacao)["valor_cliente"] == Decimal("900.00")
