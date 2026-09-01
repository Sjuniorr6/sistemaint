"""Testes da reserva — a seção crítica (ISC-RN-07, ISC-ADR-06).

Inclui o teste do índice único parcial, que neste projeto (SQLite) é a garantia
PRINCIPAL contra dupla alocação, não a terceira camada. Ver `services/reserva.py`.
"""
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from iscas.enums import StatusAtribuicao, StatusSolicitacao, TipoMovimentacao
from iscas.models.operacao import Atribuicao, AtribuicaoUnidade, Solicitacao
from iscas.services import custodia as custodia_service
from iscas.services import reserva as reserva_service
from iscas.services import saldo as saldo_service
from iscas.services.exceptions import SaldoInsuficiente, UnidadeIndisponivel

pytestmark = pytest.mark.django_db


@pytest.fixture
def solicitacao(db, cliente, operador):
    return Solicitacao.objects.create(
        cliente=cliente,
        aberta_em=timezone.now(),
        aberta_por=operador,
        status=StatusSolicitacao.ABERTA,
    )


@pytest.fixture
def atribuicao(db, solicitacao, agente, operador):
    return Atribuicao.objects.create(
        solicitacao=solicitacao, agente=agente, criada_por=operador
    )


@pytest.fixture
def outra_atribuicao(db, solicitacao, agente, operador):
    return Atribuicao.objects.create(
        solicitacao=solicitacao, agente=agente, criada_por=operador
    )


class TestAlocarUnidades:
    def test_reserva_a_quantidade_pedida(
        self, unidades_com_agente, agente, modelo_descartavel, atribuicao
    ):
        reservadas = reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=3,
            atribuicao=atribuicao,
        )
        assert len(reservadas) == 3
        assert AtribuicaoUnidade.objects.filter(
            atribuicao=atribuicao, liberada_em__isnull=True
        ).count() == 3

    def test_reserva_nao_move_custodia(
        self, unidades_com_agente, agente, modelo_descartavel, atribuicao
    ):
        """ISC-RN-07: reservada continua com o agente, só fica indisponível."""
        reservadas = reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=3,
            atribuicao=atribuicao,
        )
        custodia_agente = custodia_service.custodia_de(agente)
        for unidade in reservadas:
            unidade.refresh_from_db()
            assert unidade.custodia_atual_id == custodia_agente.pk

    def test_saldo_disponivel_desconta_reserva(
        self, unidades_com_agente, agente, modelo_descartavel, atribuicao
    ):
        assert saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel) == 8
        reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=3,
            atribuicao=atribuicao,
        )
        assert saldo_service.saldo_em_custodia(agente, modelo=modelo_descartavel) == 8
        assert saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel) == 5
        assert saldo_service.saldo_reservado(agente, modelo=modelo_descartavel) == 3

    def test_saldo_insuficiente_nao_reserva_nada(
        self, unidades_com_agente, agente, modelo_descartavel, atribuicao
    ):
        """Nunca há reserva parcial silenciosa."""
        with pytest.raises(SaldoInsuficiente):
            reserva_service.alocar_unidades(
                agente=agente,
                modelo=modelo_descartavel,
                quantidade=99,
                atribuicao=atribuicao,
            )
        assert AtribuicaoUnidade.objects.filter(atribuicao=atribuicao).count() == 0

    def test_aloca_em_ordem_fifo(
        self, unidades_com_agente, agente, modelo_descartavel, atribuicao
    ):
        """ISC-RF-25: primeiro a entrar em custódia, primeiro a sair."""
        reservadas = reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=3,
            atribuicao=atribuicao,
        )
        esperadas = sorted(
            unidades_com_agente, key=lambda u: (u.custodia_desde, u.pk)
        )[:3]
        assert {u.pk for u in reservadas} == {u.pk for u in esperadas}

    def test_segunda_atribuicao_nao_pega_as_mesmas_unidades(
        self,
        unidades_com_agente,
        agente,
        modelo_descartavel,
        atribuicao,
        outra_atribuicao,
    ):
        """O caso que o PRD chama de dupla alocação."""
        primeiras = reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=4,
            atribuicao=atribuicao,
        )
        segundas = reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=4,
            atribuicao=outra_atribuicao,
        )
        assert {u.pk for u in primeiras}.isdisjoint({u.pk for u in segundas})

    def test_esgota_saldo_e_falha_na_proxima(
        self,
        unidades_com_agente,
        agente,
        modelo_descartavel,
        atribuicao,
        outra_atribuicao,
    ):
        reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=8,
            atribuicao=atribuicao,
        )
        with pytest.raises(SaldoInsuficiente):
            reserva_service.alocar_unidades(
                agente=agente,
                modelo=modelo_descartavel,
                quantidade=1,
                atribuicao=outra_atribuicao,
            )

    def test_nao_aloca_unidade_de_outro_modelo(
        self, unidades_com_agente, retornaveis_com_agente, agente,
        modelo_retornavel, atribuicao
    ):
        reservadas = reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_retornavel,
            quantidade=5,
            atribuicao=atribuicao,
        )
        assert {u.pk for u in reservadas} == {u.pk for u in retornaveis_com_agente}

    def test_quantidade_zero_e_rejeitada(
        self, unidades_com_agente, agente, modelo_descartavel, atribuicao
    ):
        with pytest.raises(SaldoInsuficiente, match="positiva"):
            reserva_service.alocar_unidades(
                agente=agente,
                modelo=modelo_descartavel,
                quantidade=0,
                atribuicao=atribuicao,
            )


class TestUnidadesEspecificas:
    """ISC-RF-25: o operador pode escolher unidades à mão."""

    def test_reserva_as_unidades_escolhidas(
        self, unidades_com_agente, agente, modelo_descartavel, atribuicao
    ):
        escolhidas = unidades_com_agente[5:8]
        reservadas = reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=3,
            atribuicao=atribuicao,
            unidades=escolhidas,
        )
        assert {u.pk for u in reservadas} == {u.pk for u in escolhidas}

    def test_rejeita_unidade_ja_reservada(
        self,
        unidades_com_agente,
        agente,
        modelo_descartavel,
        atribuicao,
        outra_atribuicao,
    ):
        reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=2,
            atribuicao=atribuicao,
            unidades=unidades_com_agente[:2],
        )
        with pytest.raises(UnidadeIndisponivel):
            reserva_service.alocar_unidades(
                agente=agente,
                modelo=modelo_descartavel,
                quantidade=2,
                atribuicao=outra_atribuicao,
                unidades=unidades_com_agente[:2],
            )

    def test_quantidade_precisa_bater_com_a_lista(
        self, unidades_com_agente, agente, modelo_descartavel, atribuicao
    ):
        with pytest.raises(SaldoInsuficiente, match="quantidade"):
            reserva_service.alocar_unidades(
                agente=agente,
                modelo=modelo_descartavel,
                quantidade=5,
                atribuicao=atribuicao,
                unidades=unidades_com_agente[:2],
            )


class TestIndiceUnicoParcial:
    """A garantia de banco — verifica o índice, não a aplicação.

    Neste projeto (SQLite) é a proteção principal contra dupla reserva ativa,
    já que `select_for_update(skip_locked=True)` é inócuo aqui.
    """

    def test_segunda_reserva_ativa_da_mesma_unidade_estoura(
        self, unidades_com_agente, atribuicao, outra_atribuicao
    ):
        unidade = unidades_com_agente[0]
        AtribuicaoUnidade.objects.create(atribuicao=atribuicao, unidade=unidade)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AtribuicaoUnidade.objects.create(
                    atribuicao=outra_atribuicao, unidade=unidade
                )

    def test_reserva_liberada_permite_nova_reserva(
        self, unidades_com_agente, atribuicao, outra_atribuicao
    ):
        """A condição do índice é `liberada_em IS NULL` — liberada não conta."""
        unidade = unidades_com_agente[0]
        primeira = AtribuicaoUnidade.objects.create(
            atribuicao=atribuicao, unidade=unidade
        )
        primeira.liberada_em = timezone.now()
        primeira.save(update_fields=["liberada_em"])

        segunda = AtribuicaoUnidade.objects.create(
            atribuicao=outra_atribuicao, unidade=unidade
        )
        assert segunda.esta_ativa


class TestLiberarReservas:
    """ISC-RN-09: cancelamento devolve as unidades ao saldo disponível."""

    def test_libera_e_restaura_o_saldo(
        self, unidades_com_agente, agente, modelo_descartavel, atribuicao
    ):
        antes = saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel)
        reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=3,
            atribuicao=atribuicao,
        )
        assert saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel) == antes - 3

        liberadas = reserva_service.liberar_reservas(atribuicao)

        assert liberadas == 3
        assert saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel) == antes

    def test_liberar_nao_apaga_o_registro(
        self, unidades_com_agente, agente, modelo_descartavel, atribuicao
    ):
        """ISC-ADR-06: o histórico de reservas canceladas fica auditável."""
        reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=3,
            atribuicao=atribuicao,
        )
        reserva_service.liberar_reservas(atribuicao)

        assert AtribuicaoUnidade.objects.filter(atribuicao=atribuicao).count() == 3
        assert AtribuicaoUnidade.objects.filter(
            atribuicao=atribuicao, liberada_em__isnull=False
        ).count() == 3

    def test_liberar_permite_realocar_as_mesmas_unidades(
        self,
        unidades_com_agente,
        agente,
        modelo_descartavel,
        atribuicao,
        outra_atribuicao,
    ):
        primeiras = reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=8,
            atribuicao=atribuicao,
        )
        reserva_service.liberar_reservas(atribuicao)
        segundas = reserva_service.alocar_unidades(
            agente=agente,
            modelo=modelo_descartavel,
            quantidade=8,
            atribuicao=outra_atribuicao,
        )
        assert {u.pk for u in primeiras} == {u.pk for u in segundas}
