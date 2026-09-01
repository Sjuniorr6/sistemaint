"""Exclusao (soft delete) da solicitacao e a listagem paginada.

Excluir e correcao de cadastro — duplicata, engano. Cancelar e evento de
negocio. A diferenca aparece no que cada um faz com as reservas.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, StatusSolicitacao
from iscas.models.operacao import Solicitacao
from iscas.services import solicitacao as solicitacao_service
from iscas.services.exceptions import MovimentacaoInvalida
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


class TestExclusaoNaoDeixaEstoquePreso:
    """A regra que protege o saldo: excluir nao pode esconder reserva viva."""

    def test_recusa_excluir_com_reserva_ativa(
        self, pedido, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """Excluir com reserva de pe prenderia unidades numa solicitacao
        invisivel: some da tela e o estoque segue bloqueado, sem ninguem
        para liberar."""
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        antes = saldo_disponivel(agente, modelo=modelo_descartavel)

        with pytest.raises(MovimentacaoInvalida, match="Cancele a solicitação primeiro"):
            solicitacao_service.excluir_solicitacao(solicitacao=pedido, autor=operador)

        pedido.refresh_from_db()
        assert pedido.is_active is True
        assert saldo_disponivel(agente, modelo=modelo_descartavel) == antes

    def test_cancelar_libera_e_ai_a_exclusao_passa(
        self, pedido, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """O caminho correto, ponta a ponta."""
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        solicitacao_service.cancelar_solicitacao(
            solicitacao=pedido, motivo="Duplicada", autor=operador
        )
        solicitacao_service.excluir_solicitacao(solicitacao=pedido, autor=operador)

        pedido.refresh_from_db()
        assert pedido.is_active is False
        # O cancelamento devolveu as 8 ao saldo; a exclusao nao mexeu nisso.
        assert saldo_disponivel(agente, modelo=modelo_descartavel) == 8


class TestExclusaoPreservaHistorico:
    def test_nao_apaga_a_linha_do_banco(self, pedido, operador):
        """Soft delete: some da operacao, permanece no banco (ISC-ADR-15)."""
        solicitacao_service.excluir_solicitacao(solicitacao=pedido, autor=operador)

        assert not Solicitacao.objects.filter(pk=pedido.pk).exists()
        assert Solicitacao.todos.filter(pk=pedido.pk).exists()

    def test_registra_quem_excluiu_na_trilha(self, pedido, operador):
        """"Sumiu da lista" nao pode ser misterio."""
        solicitacao_service.excluir_solicitacao(
            solicitacao=pedido, autor=operador, motivo="Aberta em duplicidade"
        )
        evento = pedido.eventos.order_by("-id").first()

        assert evento.status_novo == "EXCLUIDA"
        assert evento.autor == operador
        assert evento.dados["motivo"] == "Aberta em duplicidade"

    def test_restaurar_devolve_para_a_lista(self, pedido, operador):
        solicitacao_service.excluir_solicitacao(solicitacao=pedido, autor=operador)
        solicitacao_service.restaurar_solicitacao(solicitacao=pedido, autor=operador)

        assert Solicitacao.objects.filter(pk=pedido.pk).exists()

    def test_excluir_duas_vezes_e_inocuo(self, pedido, operador):
        solicitacao_service.excluir_solicitacao(solicitacao=pedido, autor=operador)
        solicitacao_service.excluir_solicitacao(solicitacao=pedido, autor=operador)

        # Sem evento duplicado na trilha.
        assert pedido.eventos.filter(status_novo="EXCLUIDA").count() == 1


class TestListagem:
    def test_excluida_some_da_lista_e_aparece_na_lixeira(
        self, client, operador_logado, pedido, operador
    ):
        solicitacao_service.excluir_solicitacao(solicitacao=pedido, autor=operador)

        lista = client.get(reverse("iscas:solicitacao_lista"))
        lixeira = client.get(reverse("iscas:solicitacao_lista"), {"excluidas": "1"})

        assert pedido not in lista.context["pagina"].object_list
        assert pedido in lixeira.context["pagina"].object_list

    def test_pagina_de_25_em_25(
        self, client, operador_logado, cliente, modelo_descartavel, operador
    ):
        """A pergunta do usuario: 500 solicitacoes nao viram 500 linhas."""
        for _ in range(30):
            solicitacao_service.abrir_solicitacao(
                cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador
            )
        pagina = client.get(reverse("iscas:solicitacao_lista")).context["pagina"]

        assert len(pagina.object_list) == 25
        assert pagina.paginator.count == 30

    def test_paginacao_preserva_o_filtro_de_status(
        self, client, operador_logado, cliente, agente, unidades_com_agente,
        modelo_descartavel, operador,
    ):
        """Ir para a pagina 2 com filtro nao pode devolver a lista inteira.

        O template ja montava o link com `querystring`, mas a view nunca
        mandava a variavel — entao ela saia vazia e o filtro sumia em
        silencio na pagina 2.
        """
        # sabotagem: remover `querystring` do contexto da view → vermelho
        for _ in range(30):
            solicitacao_service.abrir_solicitacao(
                cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador
            )
        resposta = client.get(
            reverse("iscas:solicitacao_lista"), {"status": StatusSolicitacao.ABERTA}
        )

        assert "status=ABERTA" in resposta.context["querystring"]
        assert "page=" not in resposta.context["querystring"]

    def test_busca_por_numero_e_por_cliente(
        self, client, operador_logado, pedido, cliente
    ):
        por_id = client.get(
            reverse("iscas:solicitacao_lista"), {"q": f"#{pedido.pk}"}
        ).context["pagina"].object_list
        por_nome = client.get(
            reverse("iscas:solicitacao_lista"), {"q": cliente.nome_razao_social[:8]}
        ).context["pagina"].object_list

        assert list(por_id) == [pedido]
        assert pedido in por_nome

    def test_listagem_nao_faz_n_mais_1(
        self, client, operador_logado, cliente, modelo_descartavel,
        modelo_retornavel, operador, django_assert_num_queries,
    ):
        """A contagem precisa ser constante: 25 linhas nao podem custar 25
        consultas a mais para montar os badges de item."""
        for _ in range(3):
            solicitacao_service.abrir_solicitacao(
                cliente=cliente,
                itens=[(modelo_descartavel, 1), (modelo_retornavel, 2)],
                autor=operador,
            )
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        client.get(reverse("iscas:solicitacao_lista"))  # aquece sessão/auth

        with CaptureQueriesContext(connection) as com_3:
            client.get(reverse("iscas:solicitacao_lista"))

        for _ in range(12):
            solicitacao_service.abrir_solicitacao(
                cliente=cliente,
                itens=[(modelo_descartavel, 1), (modelo_retornavel, 2)],
                autor=operador,
            )
        with CaptureQueriesContext(connection) as com_15:
            client.get(reverse("iscas:solicitacao_lista"))

        # O valor absoluto nao importa e muda com middleware; o que prova o
        # prefetch e a contagem NAO crescer com o numero de linhas.
        assert len(com_15) == len(com_3), (
            f"{len(com_3)} consultas com 3 solicitações e {len(com_15)} com 15: "
            "a listagem voltou a ter N+1."
        )


class TestExclusaoPelaTela:
    def test_botao_exclui_e_redireciona(
        self, client, operador_logado, pedido
    ):
        resposta = client.post(
            reverse("iscas:solicitacao_excluir", args=[pedido.pk]), follow=True
        )
        pedido.refresh_from_db()

        assert pedido.is_active is False
        assert any("excluída" in str(m) for m in resposta.context["messages"])

    def test_tela_explica_por_que_recusou(
        self, client, operador_logado, pedido, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        resposta = client.post(
            reverse("iscas:solicitacao_excluir", args=[pedido.pk]), follow=True
        )
        mensagens = [str(m) for m in resposta.context["messages"]]

        pedido.refresh_from_db()
        assert pedido.is_active is True
        assert any("Cancele a solicitação primeiro" in m for m in mensagens), mensagens

    def test_get_nao_exclui(self, client, operador_logado, pedido):
        """Exclusao por GET viraria exclusao por link visitado."""
        resposta = client.get(reverse("iscas:solicitacao_excluir", args=[pedido.pk]))
        pedido.refresh_from_db()

        assert resposta.status_code == 405
        assert pedido.is_active is True
