"""A tela de detalhe: painel unificado e acoes destrutivas em modal.

O que estes testes protegem nao e a aparencia — e o encanamento que a
reestruturacao poderia ter quebrado em silencio: os formularios dos modais
continuam apontando para as views certas e continuam sendo aceitos por elas.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, StatusAtribuicao, StatusSolicitacao
from iscas.services import solicitacao as solicitacao_service
from iscas.services.saldo import saldo_disponivel

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


@pytest.fixture
def pedido(cliente, modelo_descartavel, operador):
    return solicitacao_service.abrir_solicitacao(
        cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
    )


class TestEstrutura:
    def test_entrega_e_cobertura_no_mesmo_painel(
        self, client, operador_logado, pedido, modelo_descartavel
    ):
        conteudo = client.get(
            reverse("iscas:solicitacao_detalhe", args=[pedido.pk])
        ).content.decode()

        assert "Entrega e cobertura" in conteudo
        # Os dois conteudos continuam presentes apos a fusao dos cartoes.
        assert pedido.endereco_entrega in conteudo
        assert modelo_descartavel.nome in conteudo

    def test_acoes_destrutivas_sao_modais(self, client, operador_logado, pedido):
        """Botao que abre modal, e nao formulario aberto ocupando a coluna."""
        conteudo = client.get(
            reverse("iscas:solicitacao_detalhe", args=[pedido.pk])
        ).content.decode()

        assert 'data-bs-target="#modalCancelar"' in conteudo
        assert 'data-bs-target="#modalExcluir"' in conteudo
        assert 'id="modalCancelar"' in conteudo
        assert 'id="modalExcluir"' in conteudo

    def test_sem_id_duplicado_de_motivo(
        self, client, operador_logado, pedido, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        """Cada modal renderiza um campo de motivo; id repetido faria o
        <label> focar o campo errado."""
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        conteudo = client.get(
            reverse("iscas:solicitacao_detalhe", args=[pedido.pk])
        ).content.decode()

        assert conteudo.count('id="id_motivo"') == 0
        assert conteudo.count('id="motivoSolicitacao"') == 1


class TestOsModaisContinuamFuncionando:
    """Reestruturar markup nao pode quebrar o que os formularios fazem."""

    def test_cancelar_pelo_modal_libera_reservas(
        self, client, operador_logado, pedido, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        client.post(
            reverse("iscas:solicitacao_cancelar", args=[pedido.pk]),
            {"motivo": "Cliente desistiu"},
        )
        pedido.refresh_from_db()

        assert pedido.status == StatusSolicitacao.CANCELADA
        assert saldo_disponivel(agente, modelo=modelo_descartavel) == 8

    def test_excluir_pelo_modal(self, client, operador_logado, pedido):
        client.post(
            reverse("iscas:solicitacao_excluir", args=[pedido.pk]),
            {"motivo": "Duplicada"},
        )
        pedido.refresh_from_db()

        assert pedido.is_active is False

    def test_confirmar_entrega_pelo_modal(
        self, client, operador_logado, pedido, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=pedido, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        client.post(
            reverse("iscas:atribuicao_entregar", args=[atribuicao.pk]),
            {"entregue_em": "", "recebido_por": "Portaria"},
        )
        atribuicao.refresh_from_db()

        assert atribuicao.status == StatusAtribuicao.ENTREGUE

    def test_cancelar_atribuicao_pelo_modal(
        self, client, operador_logado, pedido, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=pedido, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        client.post(
            reverse("iscas:atribuicao_cancelar", args=[atribuicao.pk]),
            {"motivo": "Agente indisponível"},
        )
        atribuicao.refresh_from_db()

        assert atribuicao.status == StatusAtribuicao.CANCELADA
        assert saldo_disponivel(agente, modelo=modelo_descartavel) == 8


class TestEstadosDaTela:
    def test_terminal_nao_oferece_cancelar(
        self, client, operador_logado, pedido, operador
    ):
        """Solicitacao cancelada nao pode ser cancelada de novo."""
        solicitacao_service.cancelar_solicitacao(
            solicitacao=pedido, motivo="Teste", autor=operador
        )
        conteudo = client.get(
            reverse("iscas:solicitacao_detalhe", args=[pedido.pk])
        ).content.decode()

        assert 'data-bs-target="#modalCancelar"' not in conteudo
        # Excluir continua disponivel: serve para tirar da lista o registro
        # de teste, que e justamente um caso terminal.
        assert 'data-bs-target="#modalExcluir"' in conteudo

    def test_excluida_mostra_restaurar_no_lugar(
        self, client, operador_logado, pedido, operador
    ):
        solicitacao_service.excluir_solicitacao(solicitacao=pedido, autor=operador)
        conteudo = client.get(
            reverse("iscas:solicitacao_detalhe", args=[pedido.pk])
        ).content.decode()

        assert "Restaurar" in conteudo
        assert 'data-bs-target="#modalExcluir"' not in conteudo
