"""Testes do livro-razão: ponto de escrita único, imutabilidade e projeção.

É a base de tudo — se estes testes falharem, nenhum saldo do app é confiável.
"""
import pytest

from iscas.enums import (
    MotivoBaixa,
    SituacaoUnidade,
    TipoCustodia,
    TipoMovimentacao,
)
from iscas.models.custodia import Movimentacao, MovimentacaoUnidade, Unidade
from iscas.services import custodia as custodia_service
from iscas.services.exceptions import MovimentacaoInvalida, UnidadeTerminal

pytestmark = pytest.mark.django_db


class TestRegistrarMovimentacao:
    """`registrar_movimentacao()` — o gargalo por onde toda escrita passa."""

    def test_move_unidades_e_atualiza_ponteiros(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        mov = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito,
            destino=agente,
            unidades=unidades_no_deposito[:3],
            autor=operador,
        )

        assert mov.linhas.count() == 3
        custodia_agente = custodia_service.custodia_de(agente)
        for unidade in Unidade.objects.filter(
            pk__in=[u.pk for u in unidades_no_deposito[:3]]
        ):
            # Os três ponteiros de projeção, atualizados na mesma transação.
            assert unidade.custodia_atual_id == custodia_agente.pk
            assert unidade.ultima_movimentacao_id == mov.pk
            assert unidade.custodia_desde == mov.ocorrido_em

    def test_unidades_nao_movidas_ficam_onde_estavam(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito,
            destino=agente,
            unidades=unidades_no_deposito[:3],
            autor=operador,
        )
        custodia_deposito = custodia_service.custodia_de(deposito)
        restantes = Unidade.objects.filter(custodia_atual=custodia_deposito)
        assert restantes.count() == 7

    def test_rejeita_unidade_que_nao_esta_na_origem(
        self, unidades_no_deposito, deposito, agente, agente2, operador
    ):
        """O erro que silenciosamente duplicaria estoque."""
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito,
            destino=agente,
            unidades=unidades_no_deposito[:2],
            autor=operador,
        )
        # Agora estão com `agente`, não mais no depósito.
        with pytest.raises(MovimentacaoInvalida, match="não estão em"):
            custodia_service.registrar_movimentacao(
                tipo=TipoMovimentacao.TRANSFERENCIA,
                origem=deposito,
                destino=agente2,
                unidades=unidades_no_deposito[:2],
                autor=operador,
            )

    def test_rejeita_lancamento_sem_unidades(self, deposito, agente, operador):
        with pytest.raises(MovimentacaoInvalida, match="ao menos uma unidade"):
            custodia_service.registrar_movimentacao(
                tipo=TipoMovimentacao.TRANSFERENCIA,
                origem=deposito,
                destino=agente,
                unidades=[],
                autor=operador,
            )

    def test_rejeita_origem_igual_ao_destino(
        self, unidades_no_deposito, deposito, operador
    ):
        with pytest.raises(MovimentacaoInvalida, match="mesma custódia"):
            custodia_service.registrar_movimentacao(
                tipo=TipoMovimentacao.TRANSFERENCIA,
                origem=deposito,
                destino=deposito,
                unidades=unidades_no_deposito[:1],
                autor=operador,
            )

    def test_baixa_exige_motivo(self, unidades_no_deposito, deposito, operador):
        with pytest.raises(MovimentacaoInvalida, match="motivo válido"):
            custodia_service.registrar_movimentacao(
                tipo=TipoMovimentacao.BAIXA,
                origem=deposito,
                destino=custodia_service.custodia_singleton(TipoCustodia.BAIXA),
                unidades=unidades_no_deposito[:1],
                autor=operador,
                justificativa="Sumiu",
            )

    def test_baixa_exige_justificativa(self, unidades_no_deposito, deposito, operador):
        """ISC-RN-13: baixa sem motivo é buraco no inventário."""
        with pytest.raises(MovimentacaoInvalida, match="justificativa"):
            custodia_service.registrar_movimentacao(
                tipo=TipoMovimentacao.BAIXA,
                origem=deposito,
                destino=custodia_service.custodia_singleton(TipoCustodia.BAIXA),
                unidades=unidades_no_deposito[:1],
                autor=operador,
                motivo_baixa=MotivoBaixa.PERDA,
            )

    def test_rejeita_unidade_terminal_como_origem(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        """ISC-RN-05: unidade baixada não é origem de nada."""
        baixa = custodia_service.custodia_singleton(TipoCustodia.BAIXA)
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.BAIXA,
            origem=deposito,
            destino=baixa,
            unidades=unidades_no_deposito[:1],
            autor=operador,
            motivo_baixa=MotivoBaixa.PERDA,
            justificativa="Perdida em campo",
        )
        with pytest.raises(UnidadeTerminal, match="terminal"):
            custodia_service.registrar_movimentacao(
                tipo=TipoMovimentacao.TRANSFERENCIA,
                origem=baixa,
                destino=agente,
                unidades=unidades_no_deposito[:1],
                autor=operador,
            )

    def test_ocorrido_em_difere_de_created_at(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        """A defasagem operacional é medida, não escondida."""
        from django.utils import timezone
        from datetime import timedelta

        ontem = timezone.now() - timedelta(days=1)
        mov = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito,
            destino=agente,
            unidades=unidades_no_deposito[:1],
            autor=operador,
            ocorrido_em=ontem,
        )
        assert mov.ocorrido_em == ontem
        assert mov.created_at > mov.ocorrido_em


class TestLogAppendOnly:
    """ISC-RN-17 / ISC-ADR-15: o log não se edita nem se apaga."""

    def test_movimentacao_nao_aceita_update(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        mov = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito,
            destino=agente,
            unidades=unidades_no_deposito[:1],
            autor=operador,
        )
        mov.justificativa = "tentando reescrever o passado"
        with pytest.raises(ValueError, match="append-only"):
            mov.save()

    def test_movimentacao_nao_aceita_delete(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        mov = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito,
            destino=agente,
            unidades=unidades_no_deposito[:1],
            autor=operador,
        )
        with pytest.raises(ValueError, match="append-only"):
            mov.delete()

    def test_linha_de_movimentacao_nao_aceita_update(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        mov = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito,
            destino=agente,
            unidades=unidades_no_deposito[:1],
            autor=operador,
        )
        linha = mov.linhas.first()
        with pytest.raises(ValueError, match="append-only"):
            linha.save()


class TestSituacaoDerivada:
    """ISC-ADR-07: situação é anotação, nunca campo."""

    def test_unidade_no_deposito(self, unidades_no_deposito):
        unidade = Unidade.objects.com_situacao().get(pk=unidades_no_deposito[0].pk)
        assert unidade.situacao == SituacaoUnidade.EM_DEPOSITO

    def test_unidade_com_agente(self, unidades_com_agente):
        unidade = Unidade.objects.com_situacao().get(pk=unidades_com_agente[0].pk)
        assert unidade.situacao == SituacaoUnidade.COM_AGENTE

    def test_descartavel_entregue_fica_consumida(
        self, unidades_com_agente, agente, cliente, operador
    ):
        """ISC-RN-05: a entrega é o fim do ciclo de vida do descartável."""
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.ENTREGA,
            origem=agente,
            destino=cliente,
            unidades=unidades_com_agente[:2],
            autor=operador,
        )
        unidade = Unidade.objects.com_situacao().get(pk=unidades_com_agente[0].pk)
        assert unidade.situacao == SituacaoUnidade.CONSUMIDA

    def test_retornavel_entregue_fica_com_cliente(
        self, retornaveis_com_agente, agente, cliente, operador
    ):
        """ISC-RN-06: o passivo em posse de terceiro é informação de estoque."""
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.ENTREGA,
            origem=agente,
            destino=cliente,
            unidades=retornaveis_com_agente[:2],
            autor=operador,
        )
        unidade = Unidade.objects.com_situacao().get(pk=retornaveis_com_agente[0].pk)
        assert unidade.situacao == SituacaoUnidade.COM_CLIENTE

    def test_baixada(self, unidades_no_deposito, deposito, operador):
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.BAIXA,
            origem=deposito,
            destino=custodia_service.custodia_singleton(TipoCustodia.BAIXA),
            unidades=unidades_no_deposito[:1],
            autor=operador,
            motivo_baixa=MotivoBaixa.AVARIA,
            justificativa="Carcaça quebrada",
        )
        unidade = Unidade.objects.com_situacao().get(pk=unidades_no_deposito[0].pk)
        assert unidade.situacao == SituacaoUnidade.BAIXADA

    def test_em_manutencao(self, unidades_no_deposito, deposito, operador):
        """ISC-RN-14: manutenção é ciclo reversível, não baixa."""
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.ENVIO_MANUTENCAO,
            origem=deposito,
            destino=custodia_service.custodia_singleton(TipoCustodia.MANUTENCAO),
            unidades=unidades_no_deposito[:1],
            autor=operador,
        )
        unidade = Unidade.objects.com_situacao().get(pk=unidades_no_deposito[0].pk)
        assert unidade.situacao == SituacaoUnidade.EM_MANUTENCAO


class TestCustodiaAutomatica:
    """ISC-ADR-03: a conta nasce junto com a entidade."""

    def test_agente_ganha_custodia(self, agente):
        conta = custodia_service.custodia_de(agente)
        assert conta.tipo == TipoCustodia.AGENTE
        assert conta.agente_id == agente.pk

    def test_cliente_ganha_custodia(self, cliente):
        assert custodia_service.custodia_de(cliente).tipo == TipoCustodia.CLIENTE

    def test_deposito_ganha_custodia(self, deposito):
        assert custodia_service.custodia_de(deposito).tipo == TipoCustodia.DEPOSITO

    def test_singletons_existem(self, db):
        for tipo in (TipoCustodia.EXTERNO, TipoCustodia.MANUTENCAO, TipoCustodia.BAIXA):
            assert custodia_service.custodia_singleton(tipo).pk is not None
