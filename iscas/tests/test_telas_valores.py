"""Os valores e a retirada na base pela borda HTTP.

O teste que carrega mais peso é o da sobrevivência entre os dois passos da
atribuição: a view revalida o form do passo 1 a partir do POST do passo 2, então
o que não for reenviado se perde em silêncio — a atribuição nasceria sem valor.
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from iscas.enums import OrigemAtribuicao
from iscas.models.operacao import Solicitacao

pytestmark = pytest.mark.django_db


def _post_solicitacao(cliente, modelo, **extra):
    dados = {
        "cliente": cliente.pk,
        "documento": "", "email": "", "contato_nome": "", "telefone": "",
        "comercial_responsavel": "",
        "entrega_logradouro": "Rua Teste", "entrega_numero": "10",
        "entrega_complemento": "", "entrega_bairro": "Centro",
        "entrega_cidade": "Sao Paulo", "entrega_uf": "SP", "entrega_cep": "",
        "prazo_desejado": "", "observacao": "",
        "valor_cliente": "450.00",
        "solicitante_nome": "Maria Compras",
        f"quantidade_{modelo.pk}": "2",
    }
    dados.update(extra)
    return dados


class TestCriacao:
    def test_persiste_valor_e_solicitante(
        self, client, operador_logado, cliente, modelo_descartavel
    ):
        """Ponta a ponta da armadilha, agora pela tela."""
        client.post(
            reverse("iscas:solicitacao_criar"),
            _post_solicitacao(cliente, modelo_descartavel),
        )
        solicitacao = Solicitacao.objects.latest("id")

        assert solicitacao.valor_cliente == Decimal("450.00")
        assert solicitacao.solicitante_nome == "Maria Compras"

    # sabotagem: tirar required=True de valor_cliente → vermelho
    @pytest.mark.parametrize("valor", ["", "-10.00", "abc"])
    def test_recusa_valor_invalido(
        self, client, operador_logado, cliente, modelo_descartavel, valor
    ):
        antes = Solicitacao.objects.count()
        resposta = client.post(
            reverse("iscas:solicitacao_criar"),
            _post_solicitacao(cliente, modelo_descartavel, valor_cliente=valor),
        )

        assert resposta.status_code == 200
        assert Solicitacao.objects.count() == antes

    def test_solicitante_nao_e_sobrescrito_pelo_cadastro(
        self, client, operador_logado, cliente, modelo_descartavel
    ):
        """Prova que ficou fora de `_CAMPOS_DO_CLIENTE`.

        `contato_nome` vazio é preenchido do cadastro; o solicitante não pode
        ser — senão o dado do evento some sob o dado do cadastro.
        """
        cliente.contato_nome = "Recepção"
        cliente.save(update_fields=["contato_nome"])

        client.post(
            reverse("iscas:solicitacao_criar"),
            _post_solicitacao(cliente, modelo_descartavel, solicitante_nome=""),
        )
        solicitacao = Solicitacao.objects.latest("id")

        assert solicitacao.contato_nome == "Recepção"
        assert solicitacao.solicitante_nome == ""


class TestAtribuicaoEmDoisPassos:
    @pytest.fixture
    def pedido(self, cliente, operador, modelo_descartavel):
        from iscas.services import solicitacao as service

        return service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador,
            valor_cliente=Decimal("500.00"),
        )

    # sabotagem: reenviar só `agente` no hidden → vermelho
    def test_valor_do_agente_sobrevive_aos_dois_passos(
        self, client, operador_logado, pedido, agente, modelo_descartavel,
        unidades_com_agente,
    ):
        url = reverse("iscas:solicitacao_atribuir", args=[pedido.pk])

        intermediaria = client.post(url, {
            "origem_tipo": OrigemAtribuicao.AGENTE,
            "agente": agente.pk,
            "valor_agente": "75.50",
        })
        html = intermediaria.content.decode()

        # O hidden precisa estar na tela intermediária, senão o passo 2 perde.
        assert 'name="valor_agente"' in html
        assert "75.50" in html

        client.post(url, {
            "origem_tipo": OrigemAtribuicao.AGENTE,
            "agente": agente.pk,
            "valor_agente": "75.50",
            "confirmar": "1",
            f"unidades_{modelo_descartavel.pk}": [
                u.pk for u in unidades_com_agente[:2]
            ],
        })

        assert pedido.atribuicoes.get().valor_agente == Decimal("75.50")

    def test_retirada_sobrevive_aos_dois_passos(
        self, client, operador_logado, pedido, deposito, modelo_descartavel,
        unidades_no_deposito,
    ):
        url = reverse("iscas:solicitacao_atribuir", args=[pedido.pk])

        intermediaria = client.post(url, {
            "origem_tipo": OrigemAtribuicao.RETIRADA_BASE,
            "deposito": deposito.pk,
        })
        html = intermediaria.content.decode()

        assert 'name="deposito"' in html
        assert 'name="origem_tipo"' in html

        client.post(url, {
            "origem_tipo": OrigemAtribuicao.RETIRADA_BASE,
            "deposito": deposito.pk,
            "confirmar": "1",
            f"unidades_{modelo_descartavel.pk}": [
                u.pk for u in unidades_no_deposito[:2]
            ],
        })
        atribuicao = pedido.atribuicoes.get()

        assert atribuicao.eh_retirada_base
        assert atribuicao.deposito == deposito
        assert atribuicao.valor_agente is None

    def test_post_antigo_sem_origem_tipo_continua_valendo(
        self, client, operador_logado, pedido, agente, modelo_descartavel,
        unidades_com_agente,
    ):
        """O POST que o app sempre mandou — 24 testes dependem disso."""
        client.post(reverse("iscas:solicitacao_atribuir", args=[pedido.pk]), {
            "agente": agente.pk,
            "confirmar": "1",
            f"unidades_{modelo_descartavel.pk}": [
                u.pk for u in unidades_com_agente[:2]
            ],
        })
        atribuicao = pedido.atribuicoes.get()

        assert atribuicao.origem_tipo == OrigemAtribuicao.AGENTE
        assert atribuicao.agente == agente

    @pytest.mark.parametrize("dados,motivo", [
        ({"origem_tipo": "RETIRADA_BASE"}, "retirada sem depósito"),
        ({"origem_tipo": "AGENTE"}, "agente sem agente"),
    ])
    def test_recusa_origem_incompleta(
        self, client, operador_logado, pedido, dados, motivo
    ):
        resposta = client.post(
            reverse("iscas:solicitacao_atribuir", args=[pedido.pk]),
            dados, follow=True,
        )

        assert pedido.atribuicoes.count() == 0, motivo
        assert [str(m) for m in resposta.context["messages"]]

    def test_recusa_valor_de_agente_em_retirada(
        self, client, operador_logado, pedido, deposito, unidades_no_deposito
    ):
        client.post(
            reverse("iscas:solicitacao_atribuir", args=[pedido.pk]),
            {
                "origem_tipo": OrigemAtribuicao.RETIRADA_BASE,
                "deposito": deposito.pk,
                "valor_agente": "50.00",
            },
            follow=True,
        )

        assert pedido.atribuicoes.count() == 0


class TestVisibilidadeDosValores:
    """Quem vê o quê (decisão de negócio confirmada, é contra-intuitiva).

    Comercial vê tudo; Operador Fast vê só o custo do agente — ele DIGITA o
    valor do cliente ao abrir, mas não o consulta depois.
    """

    @pytest.fixture
    def pedido_com_valores(self, cliente, operador, agente, modelo_descartavel,
                           unidades_com_agente):
        from iscas.services import solicitacao as service

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador,
            valor_cliente=Decimal("900.00"),
        )
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("111.00"),
        )
        return solicitacao

    def _detalhe(self, client, solicitacao):
        return client.get(
            reverse("iscas:solicitacao_detalhe", args=[solicitacao.pk])
        )

    def test_comercial_ve_tudo(
        self, client, comercial_logado, pedido_com_valores
    ):
        conteudo = self._detalhe(client, pedido_com_valores).content.decode()

        assert "900,00" in conteudo or "900.00" in conteudo
        assert "111,00" in conteudo or "111.00" in conteudo
        # margem = 900 - 111
        assert "789,00" in conteudo or "789.00" in conteudo

    # sabotagem: dar VER_VALOR_CLIENTE ao Operador Fast → vermelho
    def test_operador_fast_ve_custo_mas_nao_o_valor_do_cliente(
        self, client, operador_fast_logado, pedido_com_valores
    ):
        """Assere o NÚMERO, não o rótulo: o rótulo some junto e não prova nada."""
        conteudo = self._detalhe(client, pedido_com_valores).content.decode()

        assert "111,00" in conteudo or "111.00" in conteudo
        assert "900,00" not in conteudo and "900.00" not in conteudo
        assert "789,00" not in conteudo and "789.00" not in conteudo

    def test_a_view_nao_envia_o_valor_no_contexto(
        self, client, operador_fast_logado, pedido_com_valores
    ):
        """Distingue "escondido no template" de "não enviado".

        Se estivesse só escondido, o número apareceria no código-fonte da
        página para quem soubesse abrir o inspetor.
        """
        resposta = self._detalhe(client, pedido_com_valores)
        totais = resposta.context["totais"]

        assert totais["valor_cliente"] is None
        assert totais["margem"] is None
        assert totais["custo_agentes"] == Decimal("111.00")

    def test_operador_total_ve_tudo(
        self, client, operador_logado, pedido_com_valores
    ):
        totais = self._detalhe(client, pedido_com_valores).context["totais"]

        assert totais["valor_cliente"] == Decimal("900.00")
        assert totais["margem"] == Decimal("789.00")
