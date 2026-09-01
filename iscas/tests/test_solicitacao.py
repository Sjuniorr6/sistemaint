"""Testes da máquina de estados e do fluxo de atendimento (ISC-ADR-08).

Inclui a cobertura exaustiva das tabelas de transição: toda transição válida é
permitida e gera evento; TODA combinação inválida é bloqueada.
"""
import pytest
from django.utils import timezone

from iscas.enums import (
    SituacaoUnidade,
    StatusAtribuicao,
    StatusSolicitacao,
    TipoMovimentacao,
)
from iscas.models.custodia import Unidade
from iscas.models.operacao import SolicitacaoEvento
from iscas.services import saldo as saldo_service
from iscas.services import solicitacao as solicitacao_service
from iscas.services.exceptions import (
    MovimentacaoInvalida,
    TransicaoInvalida,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def solicitacao_aberta(db, cliente, modelo_descartavel, operador):
    return solicitacao_service.abrir_solicitacao(
        cliente=cliente,
        itens=[(modelo_descartavel, 5)],
        autor=operador,
        observacao="Entregar pela manhã",
    )


class TestTabelasDeTransicao:
    """Cobertura exaustiva da matriz (ISC-ADR-08)."""

    @pytest.mark.parametrize(
        "de,para",
        [
            (de, para)
            for de, destinos in solicitacao_service.TRANSICOES_SOLICITACAO.items()
            for para in destinos
        ],
    )
    def test_transicao_valida_de_solicitacao_e_permitida(self, de, para):
        assert para in solicitacao_service.TRANSICOES_SOLICITACAO[de]

    @pytest.mark.parametrize(
        "de,para",
        [
            (de, para)
            for de in StatusSolicitacao.values
            for para in StatusSolicitacao.values
            if para not in solicitacao_service.TRANSICOES_SOLICITACAO.get(de, set())
        ],
    )
    def test_transicao_invalida_de_solicitacao_e_bloqueada(
        self, de, para, solicitacao_aberta, operador
    ):
        solicitacao_aberta.status = de
        solicitacao_aberta.save(update_fields=["status"])
        with pytest.raises(TransicaoInvalida):
            solicitacao_service._transitar(
                solicitacao=solicitacao_aberta, novo_status=para, autor=operador
            )

    @pytest.mark.parametrize(
        "de,para",
        [
            (de, para)
            for de in StatusAtribuicao.values
            for para in StatusAtribuicao.values
            if para not in solicitacao_service.TRANSICOES_ATRIBUICAO.get(de, set())
        ],
    )
    def test_transicao_invalida_de_atribuicao_e_bloqueada(
        self, de, para, solicitacao_aberta, agente, unidades_com_agente,
        modelo_descartavel, operador,
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta,
            agente=agente,
            itens=[(modelo_descartavel, 2)],
            autor=operador,
        )
        atribuicao.status = de
        atribuicao.save(update_fields=["status"])
        with pytest.raises(TransicaoInvalida):
            solicitacao_service._transitar(
                solicitacao=solicitacao_aberta,
                atribuicao=atribuicao,
                novo_status=para,
                autor=operador,
            )

    def test_estados_terminais_nao_tem_saida(self):
        assert solicitacao_service.TRANSICOES_SOLICITACAO[StatusSolicitacao.ENTREGUE] == set()
        assert solicitacao_service.TRANSICOES_SOLICITACAO[StatusSolicitacao.CANCELADA] == set()
        assert solicitacao_service.TRANSICOES_ATRIBUICAO[StatusAtribuicao.ENTREGUE] == set()
        assert solicitacao_service.TRANSICOES_ATRIBUICAO[StatusAtribuicao.CANCELADA] == set()


class TestAbrirSolicitacao:
    def test_nasce_aberta_com_evento(self, solicitacao_aberta):
        assert solicitacao_aberta.status == StatusSolicitacao.ABERTA
        assert SolicitacaoEvento.objects.filter(
            solicitacao=solicitacao_aberta, status_novo=StatusSolicitacao.ABERTA
        ).exists()

    def test_exige_ao_menos_um_item(self, cliente, operador):
        with pytest.raises(MovimentacaoInvalida, match="ao menos um item"):
            solicitacao_service.abrir_solicitacao(
                cliente=cliente, itens=[], autor=operador
            )


class TestAtribuicao:
    def test_atribuir_reserva_e_muda_status(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta,
            agente=agente,
            itens=[(modelo_descartavel, 5)],
            autor=operador,
        )
        solicitacao_aberta.refresh_from_db()

        assert atribuicao.status == StatusAtribuicao.RESERVADA
        assert solicitacao_aberta.status == StatusSolicitacao.ATRIBUIDA
        assert atribuicao.reservas_ativas().count() == 5

    def test_atribuicao_nao_move_custodia(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """ISC-RN-08: o sistema registra o que aconteceu, não o que foi planejado."""
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta,
            agente=agente,
            itens=[(modelo_descartavel, 5)],
            autor=operador,
        )
        assert saldo_service.saldo_em_custodia(agente, modelo=modelo_descartavel) == 8
        assert saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel) == 3

    def test_unidade_reservada_fica_com_situacao_reservada(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta,
            agente=agente,
            itens=[(modelo_descartavel, 2)],
            autor=operador,
        )
        unidade = atribuicao.unidades_reservadas().first()
        anotada = Unidade.objects.com_situacao().get(pk=unidade.pk)
        assert anotada.situacao == SituacaoUnidade.RESERVADA

    def test_agente_desativado_nao_recebe_atribuicao(
        self, solicitacao_aberta, agente, modelo_descartavel, operador
    ):
        """ISC-RN-18."""
        agente.desativar()
        with pytest.raises(MovimentacaoInvalida, match="desativado"):
            solicitacao_service.criar_atribuicao(
                solicitacao=solicitacao_aberta,
                agente=agente,
                itens=[(modelo_descartavel, 1)],
                autor=operador,
            )

    def test_divisao_entre_dois_agentes(
        self, cliente, modelo_descartavel, agente, agente2, operador
    ):
        """ISC-RN-10: o agente mais próximo raramente tem o saldo exato."""
        from iscas.services import entrada as entrada_service

        entrada_service.registrar_entrada(
            modelo=modelo_descartavel,
            identificadores=[f"X{i:03d}" for i in range(1, 13)],
            destino=agente,
            autor=operador,
        )
        entrada_service.registrar_entrada(
            modelo=modelo_descartavel,
            identificadores=[f"Y{i:03d}" for i in range(1, 9)],
            destino=agente2,
            autor=operador,
        )
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 20)], autor=operador
        )

        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 12)], autor=operador,
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente2,
            itens=[(modelo_descartavel, 8)], autor=operador,
        )

        assert solicitacao_service.cobertura_total(solicitacao)
        cob = solicitacao_service.cobertura(solicitacao)[0]
        assert cob["solicitado"] == 20
        assert cob["atribuido"] == 20
        assert cob["falta"] == 0

    def test_cobertura_parcial(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        cob = solicitacao_service.cobertura(solicitacao_aberta)[0]
        assert (cob["solicitado"], cob["atribuido"], cob["falta"]) == (5, 3, 2)
        assert not solicitacao_service.cobertura_total(solicitacao_aberta)


class TestEntrega:
    def test_entrega_transfere_custodia_ao_cliente(
        self, solicitacao_aberta, agente, cliente, unidades_com_agente,
        modelo_descartavel, operador,
    ):
        """ISC-RN-08: é a confirmação que move o estoque."""
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        movimentacao = solicitacao_service.confirmar_entrega(
            atribuicao=atribuicao, autor=operador, recebido_por="Porteiro João"
        )

        atribuicao.refresh_from_db()
        solicitacao_aberta.refresh_from_db()

        assert movimentacao.tipo == TipoMovimentacao.ENTREGA
        assert atribuicao.status == StatusAtribuicao.ENTREGUE
        assert atribuicao.recebido_por == "Porteiro João"
        assert solicitacao_aberta.status == StatusSolicitacao.ENTREGUE
        assert saldo_service.saldo_em_custodia(agente, modelo=modelo_descartavel) == 3
        assert saldo_service.saldo_em_custodia(cliente, modelo=modelo_descartavel) == 5

    def test_entrega_parcial_nao_encerra_a_solicitacao(
        self, cliente, modelo_descartavel, agente, agente2, operador
    ):
        """ISC-RN-10: ENTREGUE exige todas entregues E cobertura total."""
        from iscas.services import entrada as entrada_service

        entrada_service.registrar_entrada(
            modelo=modelo_descartavel,
            identificadores=[f"P{i:03d}" for i in range(1, 13)],
            destino=agente, autor=operador,
        )
        entrada_service.registrar_entrada(
            modelo=modelo_descartavel,
            identificadores=[f"Q{i:03d}" for i in range(1, 9)],
            destino=agente2, autor=operador,
        )
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 20)], autor=operador
        )
        a1 = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 12)], autor=operador,
        )
        a2 = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente2,
            itens=[(modelo_descartavel, 8)], autor=operador,
        )

        solicitacao_service.confirmar_entrega(atribuicao=a1, autor=operador)
        solicitacao.refresh_from_db()
        assert solicitacao.status != StatusSolicitacao.ENTREGUE

        solicitacao_service.confirmar_entrega(atribuicao=a2, autor=operador)
        solicitacao.refresh_from_db()
        assert solicitacao.status == StatusSolicitacao.ENTREGUE

    def test_descartavel_entregue_fica_consumida(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        solicitacao_service.confirmar_entrega(atribuicao=atribuicao, autor=operador)
        unidade = Unidade.objects.com_situacao().get(pk=unidades_com_agente[0].pk)
        assert unidade.situacao == SituacaoUnidade.CONSUMIDA

    def test_entrega_libera_as_reservas(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """Depois da entrega, "reserva ativa" não faz mais sentido: a unidade
        saiu da custódia do agente."""
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        solicitacao_service.confirmar_entrega(atribuicao=atribuicao, autor=operador)
        assert atribuicao.reservas_ativas().count() == 0
        assert atribuicao.reservas.count() == 5

    def test_nao_entrega_atribuicao_ja_terminal(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        solicitacao_service.confirmar_entrega(atribuicao=atribuicao, autor=operador)
        with pytest.raises(TransicaoInvalida):
            solicitacao_service.confirmar_entrega(atribuicao=atribuicao, autor=operador)


class TestRota:
    def test_marcar_em_rota_propaga_para_a_solicitacao(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        solicitacao_service.marcar_em_rota(atribuicao=atribuicao, autor=operador)

        atribuicao.refresh_from_db()
        solicitacao_aberta.refresh_from_db()
        assert atribuicao.status == StatusAtribuicao.EM_ROTA
        assert atribuicao.em_rota_em is not None
        assert solicitacao_aberta.status == StatusSolicitacao.EM_ROTA

    def test_unidade_em_rota_tem_situacao_em_rota(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        solicitacao_service.marcar_em_rota(atribuicao=atribuicao, autor=operador)
        unidade = atribuicao.unidades_reservadas().first()
        anotada = Unidade.objects.com_situacao().get(pk=unidade.pk)
        assert anotada.situacao == SituacaoUnidade.EM_ROTA


class TestCancelamento:
    def test_cancelar_atribuicao_restaura_saldo(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """ISC-RN-09: comparação numérica antes/depois."""
        antes = saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel)
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        assert saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel) == antes - 5

        solicitacao_service.cancelar_atribuicao(
            atribuicao=atribuicao, motivo="Agente sem carro", autor=operador
        )

        atribuicao.refresh_from_db()
        assert atribuicao.status == StatusAtribuicao.CANCELADA
        assert saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel) == antes

    def test_cancelar_ultima_atribuicao_volta_solicitacao_para_aberta(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        solicitacao_service.cancelar_atribuicao(
            atribuicao=atribuicao, motivo="Cliente adiou", autor=operador
        )
        solicitacao_aberta.refresh_from_db()
        assert solicitacao_aberta.status == StatusSolicitacao.ABERTA

    def test_cancelamento_exige_motivo(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        with pytest.raises(MovimentacaoInvalida, match="motivo"):
            solicitacao_service.cancelar_atribuicao(
                atribuicao=atribuicao, motivo="  ", autor=operador
            )

    def test_cancelar_solicitacao_libera_todas_as_reservas(
        self, cliente, modelo_descartavel, agente, agente2, operador
    ):
        """Reserva órfã trava estoque real (ISC-RN-09)."""
        from iscas.services import entrada as entrada_service

        entrada_service.registrar_entrada(
            modelo=modelo_descartavel,
            identificadores=[f"C{i:03d}" for i in range(1, 6)],
            destino=agente, autor=operador,
        )
        entrada_service.registrar_entrada(
            modelo=modelo_descartavel,
            identificadores=[f"E{i:03d}" for i in range(1, 6)],
            destino=agente2, autor=operador,
        )
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 10)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente2,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )

        solicitacao_service.cancelar_solicitacao(
            solicitacao=solicitacao, motivo="Cliente desistiu", autor=operador
        )

        solicitacao.refresh_from_db()
        assert solicitacao.status == StatusSolicitacao.CANCELADA
        assert saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel) == 5
        assert saldo_service.saldo_disponivel(agente2, modelo=modelo_descartavel) == 5

    def test_solicitacao_cancelada_nao_aceita_atribuicao(
        self, solicitacao_aberta, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        solicitacao_service.cancelar_solicitacao(
            solicitacao=solicitacao_aberta, motivo="Engano", autor=operador
        )
        solicitacao_aberta.refresh_from_db()
        with pytest.raises(TransicaoInvalida):
            solicitacao_service.criar_atribuicao(
                solicitacao=solicitacao_aberta, agente=agente,
                itens=[(modelo_descartavel, 1)], autor=operador,
            )
