"""A atribuição não pode ultrapassar o que o cliente pediu.

O pedido é o contrato: atribuir mais do que foi solicitado tira equipamento do
estoque sem lastro, e atribuir um modelo fora do pedido cria reserva invisível
— essas unidades não aparecem na cobertura, então a solicitação nunca fecharia.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES
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
def pedido_de_3(cliente, modelo_descartavel, operador):
    """Cliente pediu 3; o agente das fixtures tem 8 disponíveis."""
    return solicitacao_service.abrir_solicitacao(
        cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
    )


class TestQuantidadeAcimaDoPedido:
    def test_uma_atribuicao_maior_que_o_pedido(
        self, pedido_de_3, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """O caso relatado: pediu 3, tentou enviar 5."""
        with pytest.raises(MovimentacaoInvalida, match="cabem no máximo 3"):
            solicitacao_service.criar_atribuicao(
                solicitacao=pedido_de_3, agente=agente,
                itens=[(modelo_descartavel, 5)], autor=operador,
            )

    def test_nada_e_reservado_quando_recusa(
        self, pedido_de_3, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """A recusa não pode deixar unidades presas nem atribuição órfã."""
        antes = saldo_disponivel(agente, modelo=modelo_descartavel)

        with pytest.raises(MovimentacaoInvalida):
            solicitacao_service.criar_atribuicao(
                solicitacao=pedido_de_3, agente=agente,
                itens=[(modelo_descartavel, 5)], autor=operador,
            )

        assert saldo_disponivel(agente, modelo=modelo_descartavel) == antes
        assert pedido_de_3.atribuicoes.count() == 0

    def test_exatamente_a_quantidade_pedida_passa(
        self, pedido_de_3, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=pedido_de_3, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        assert atribuicao.reservas_ativas().count() == 3
        assert solicitacao_service.cobertura_total(pedido_de_3)

    def test_menos_que_o_pedido_passa(
        self, pedido_de_3, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido_de_3, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        linha = solicitacao_service.cobertura(pedido_de_3)[0]
        assert (linha["atribuido"], linha["falta"]) == (2, 1)


class TestSomaDasAtribuicoes:
    """Duas atribuições parciais não podem exceder o total por acumulação."""

    def test_segunda_atribuicao_que_estoura(
        self, pedido_de_3, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido_de_3, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        with pytest.raises(MovimentacaoInvalida, match="cabem no máximo 1"):
            solicitacao_service.criar_atribuicao(
                solicitacao=pedido_de_3, agente=agente,
                itens=[(modelo_descartavel, 2)], autor=operador,
            )

    def test_segunda_atribuicao_que_completa(
        self, pedido_de_3, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido_de_3, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido_de_3, agente=agente,
            itens=[(modelo_descartavel, 1)], autor=operador,
        )
        assert solicitacao_service.cobertura_total(pedido_de_3)

    def test_pedido_ja_completo_recusa_qualquer_adicao(
        self, pedido_de_3, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido_de_3, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        with pytest.raises(MovimentacaoInvalida, match="totalmente atendido"):
            solicitacao_service.criar_atribuicao(
                solicitacao=pedido_de_3, agente=agente,
                itens=[(modelo_descartavel, 1)], autor=operador,
            )

    def test_cancelar_libera_espaco_no_pedido(
        self, pedido_de_3, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """Atribuição cancelada não conta — o espaço volta a caber."""
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=pedido_de_3, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        solicitacao_service.cancelar_atribuicao(
            atribuicao=atribuicao, motivo="agente desistiu", autor=operador
        )

        nova = solicitacao_service.criar_atribuicao(
            solicitacao=pedido_de_3, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        assert nova.reservas_ativas().count() == 3

    def test_entregue_continua_ocupando_o_pedido(
        self, cliente, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """Unidade já entregue não abre espaço para enviar de novo.

        Usa entrega PARCIAL de propósito: com cobertura total a solicitação
        vira ENTREGUE e a guarda de estado barraria antes, sem exercitar o
        limite do pedido.
        """
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        solicitacao_service.confirmar_entrega(atribuicao=atribuicao, autor=operador)

        solicitacao.refresh_from_db()
        # Restou 1 do pedido: 2 cabem não.
        with pytest.raises(MovimentacaoInvalida, match="cabem no máximo 1"):
            solicitacao_service.criar_atribuicao(
                solicitacao=solicitacao, agente=agente,
                itens=[(modelo_descartavel, 2)], autor=operador,
            )
        # E 1 ainda passa.
        nova = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 1)], autor=operador,
        )
        assert nova.reservas_ativas().count() == 1


class TestModeloForaDoPedido:
    """Modelo não solicitado cria reserva que a cobertura não enxerga."""

    def test_recusa_modelo_nao_solicitado(
        self, pedido_de_3, agente, retornaveis_com_agente,
        modelo_retornavel, operador,
    ):
        with pytest.raises(MovimentacaoInvalida, match="não faz parte desta solicitação"):
            solicitacao_service.criar_atribuicao(
                solicitacao=pedido_de_3, agente=agente,
                itens=[(modelo_retornavel, 2)], autor=operador,
            )

    def test_recusa_mesmo_misturado_com_modelo_valido(
        self, pedido_de_3, agente, unidades_com_agente, retornaveis_com_agente,
        modelo_descartavel, modelo_retornavel, operador,
    ):
        """A validação roda antes de reservar qualquer unidade."""
        antes = saldo_disponivel(agente, modelo=modelo_descartavel)

        with pytest.raises(MovimentacaoInvalida):
            solicitacao_service.criar_atribuicao(
                solicitacao=pedido_de_3, agente=agente,
                itens=[(modelo_descartavel, 1), (modelo_retornavel, 1)],
                autor=operador,
            )

        assert saldo_disponivel(agente, modelo=modelo_descartavel) == antes
        assert pedido_de_3.atribuicoes.count() == 0

    def test_pedido_com_dois_modelos_aceita_ambos(
        self, cliente, agente, unidades_com_agente, retornaveis_com_agente,
        modelo_descartavel, modelo_retornavel, operador,
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente,
            itens=[(modelo_descartavel, 3), (modelo_retornavel, 2)],
            autor=operador,
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 3), (modelo_retornavel, 2)],
            autor=operador,
        )
        assert solicitacao_service.cobertura_total(solicitacao)


class TestPelaTela:
    """A tela escolhe unidades, não digita quantidade (ISC-RF-25)."""

    def test_form_recusa_excesso_com_mensagem_util(
        self, client, operador_logado, pedido_de_3, agente,
        unidades_com_agente, modelo_descartavel,
    ):
        """O operador precisa saber o limite, não levar um erro genérico."""
        resposta = client.post(
            reverse("iscas:solicitacao_atribuir", args=[pedido_de_3.pk]),
            {
                "agente": agente.pk,
                "confirmar": "1",
                f"unidades_{modelo_descartavel.pk}": [
                    u.pk for u in unidades_com_agente[:5]
                ],
            },
            follow=True,
        )
        mensagens = [str(m) for m in resposta.context["messages"]]

        assert pedido_de_3.atribuicoes.count() == 0
        assert any("Faltam apenas 3" in m for m in mensagens), mensagens

    def test_form_aceita_dentro_do_limite(
        self, client, operador_logado, pedido_de_3, agente,
        unidades_com_agente, modelo_descartavel,
    ):
        escolhidas = unidades_com_agente[:3]
        client.post(
            reverse("iscas:solicitacao_atribuir", args=[pedido_de_3.pk]),
            {
                "agente": agente.pk,
                "confirmar": "1",
                f"unidades_{modelo_descartavel.pk}": [u.pk for u in escolhidas],
            },
        )
        atribuicao = pedido_de_3.atribuicoes.get()

        # O que prova o rastreio não é a contagem, é a identidade: as unidades
        # reservadas são exatamente as que o operador marcou.
        assert {u.identificador for u in atribuicao.unidades_reservadas()} == {
            u.identificador for u in escolhidas
        }

    def test_escolha_vazia_e_recusada(
        self, client, operador_logado, pedido_de_3, agente, unidades_com_agente,
    ):
        resposta = client.post(
            reverse("iscas:solicitacao_atribuir", args=[pedido_de_3.pk]),
            {"agente": agente.pk, "confirmar": "1"},
            follow=True,
        )
        mensagens = [str(m) for m in resposta.context["messages"]]

        assert pedido_de_3.atribuicoes.count() == 0
        assert any("ao menos uma unidade" in m for m in mensagens), mensagens

    def test_primeiro_passo_lista_as_unidades_do_agente(
        self, client, operador_logado, pedido_de_3, agente,
        unidades_com_agente, modelo_descartavel,
    ):
        """Escolher o agente leva à tela de unidades, sem reservar nada ainda."""
        resposta = client.post(
            reverse("iscas:solicitacao_atribuir", args=[pedido_de_3.pk]),
            {"agente": agente.pk},
        )
        conteudo = resposta.content.decode()

        assert pedido_de_3.atribuicoes.count() == 0
        assert unidades_com_agente[0].identificador in conteudo

    def test_a_tela_trava_a_escolha_no_teto_do_pedido(
        self, client, operador_logado, pedido_de_3, agente, unidades_com_agente,
    ):
        """O agente tem 8 disponíveis, mas o pedido só comporta 3.

        Sem o teto declarado para o navegador, dá para marcar as 8 e só
        descobrir o limite ao submeter. A garantia continua sendo do servidor
        (`test_form_recusa_excesso_com_mensagem_util`); esta asserção cobre o
        atrito, que é silencioso — nada quebra, o operador só perde a escolha.
        """
        # sabotagem: trocar limitador() por x-data fixo na tela → vermelho
        conteudo = client.post(
            reverse("iscas:solicitacao_atribuir", args=[pedido_de_3.pk]),
            {"agente": agente.pk},
        ).content.decode()

        assert "limitador(3)" in conteudo

    def test_tela_mostra_o_quanto_cabe(
        self, client, operador_logado, pedido_de_3, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido_de_3, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        conteudo = client.get(
            reverse("iscas:solicitacao_detalhe", args=[pedido_de_3.pk])
        ).content.decode()

        assert "Ainda cabe nesta solicita" in conteudo

    def test_botao_desabilita_com_pedido_completo(
        self, client, operador_logado, pedido_de_3, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        solicitacao_service.criar_atribuicao(
            solicitacao=pedido_de_3, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        conteudo = client.get(
            reverse("iscas:solicitacao_detalhe", args=[pedido_de_3.pk])
        ).content.decode()

        assert "totalmente atribu" in conteudo


class TestAgentesOferecidos:
    """O select só oferece quem pode atender — o resto vira erro tardio."""

    def test_agente_sem_o_modelo_nao_aparece(
        self, pedido_de_3, agente, agente2, unidades_com_agente
    ):
        """`agente2` não tem unidade nenhuma; `agente` tem 8 do modelo pedido."""
        from iscas.forms import AtribuicaoForm

        oferecidos = list(
            AtribuicaoForm(solicitacao=pedido_de_3).fields["agente"].queryset
        )

        assert agente in oferecidos
        assert agente2 not in oferecidos

    def test_agente_com_todo_o_estoque_reservado_some(
        self, pedido_de_3, agente, unidades_com_agente, modelo_descartavel,
        cliente, operador,
    ):
        """Saldo disponível, não saldo em custódia: reservado não conta."""
        from iscas.forms import AtribuicaoForm

        outro_pedido = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 8)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=outro_pedido, agente=agente,
            itens=[(modelo_descartavel, 8)], autor=operador,
        )

        oferecidos = list(
            AtribuicaoForm(solicitacao=pedido_de_3).fields["agente"].queryset
        )

        assert agente not in oferecidos

    def test_agente_so_com_modelo_fora_do_pedido_nao_aparece(
        self, pedido_de_3, agente, retornaveis_com_agente
    ):
        """O agente tem retornáveis, mas o pedido é de descartáveis."""
        from iscas.forms import AtribuicaoForm

        oferecidos = list(
            AtribuicaoForm(solicitacao=pedido_de_3).fields["agente"].queryset
        )

        assert agente not in oferecidos


class TestVariosModelosNumaAtribuicao:
    """Um agente cobre vários modelos de uma vez (ISC-RN-10)."""

    def test_dois_modelos_numa_unica_atribuicao_pela_tela(
        self, client, operador_logado, cliente, agente, operador,
        unidades_com_agente, retornaveis_com_agente,
        modelo_descartavel, modelo_retornavel,
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente,
            itens=[(modelo_descartavel, 3), (modelo_retornavel, 2)],
            autor=operador,
        )

        client.post(
            reverse("iscas:solicitacao_atribuir", args=[solicitacao.pk]),
            {
                "agente": agente.pk,
                "confirmar": "1",
                f"unidades_{modelo_descartavel.pk}": [
                    u.pk for u in unidades_com_agente[:3]
                ],
                f"unidades_{modelo_retornavel.pk}": [
                    u.pk for u in retornaveis_com_agente[:2]
                ],
            },
        )

        # UMA atribuição cobrindo os DOIS modelos — antes exigia vincular o
        # mesmo agente duas vezes.
        atribuicao = solicitacao.atribuicoes.get()
        modelos = {u.modelo_id for u in atribuicao.unidades_reservadas()}

        assert modelos == {modelo_descartavel.pk, modelo_retornavel.pk}
        assert solicitacao_service.cobertura_total(solicitacao)

    def test_excesso_num_modelo_nao_reserva_o_outro(
        self, client, operador_logado, cliente, agente, operador,
        unidades_com_agente, retornaveis_com_agente,
        modelo_descartavel, modelo_retornavel,
    ):
        """Erro num bloco barra a atribuição inteira — nada pela metade."""
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente,
            itens=[(modelo_descartavel, 3), (modelo_retornavel, 2)],
            autor=operador,
        )

        client.post(
            reverse("iscas:solicitacao_atribuir", args=[solicitacao.pk]),
            {
                "agente": agente.pk,
                "confirmar": "1",
                f"unidades_{modelo_descartavel.pk}": [
                    u.pk for u in unidades_com_agente[:5]  # o pedido só cabe 3
                ],
                f"unidades_{modelo_retornavel.pk}": [
                    u.pk for u in retornaveis_com_agente[:2]
                ],
            },
        )

        assert solicitacao.atribuicoes.count() == 0
        assert saldo_disponivel(agente, modelo=modelo_retornavel) == 5
