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
        "solicitante_nome": "Maria Compras",
        f"quantidade_{modelo.pk}": "2",
        f"preco_{modelo.pk}": "225.00",
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

    # sabotagem: tirar a exigência de preço no service → vermelho
    @pytest.mark.parametrize("preco", ["", "abc"])
    def test_recusa_item_sem_preco(
        self, client, operador_logado, cliente, modelo_descartavel, preco
    ):
        """Quem bloqueia é o service (`exigir_valor=True`), não o form."""
        antes = Solicitacao.objects.count()
        dados = _post_solicitacao(cliente, modelo_descartavel)
        dados[f"preco_{modelo_descartavel.pk}"] = preco
        resposta = client.post(reverse("iscas:solicitacao_criar"), dados)

        assert resposta.status_code == 200
        assert Solicitacao.objects.count() == antes

    def test_total_vem_dos_itens_nao_do_post(
        self, client, operador_logado, cliente, modelo_descartavel
    ):
        """`valor_cliente` saiu do form justamente para não ser injetável."""
        dados = _post_solicitacao(cliente, modelo_descartavel)
        dados["valor_cliente"] = "1.00"
        client.post(reverse("iscas:solicitacao_criar"), dados)

        # 2 unidades × 225,00 — o POST malicioso é ignorado.
        assert Solicitacao.objects.latest("id").valor_cliente == Decimal("450.00")

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


class TestComercialPreenchido:
    """Quem é do comercial não redigita o próprio nome (requisito do usuário).

    Preenche `comercial_responsavel` — "quem da Golden Sat atende a conta" —
    e NÃO `solicitante_nome`, que é quem pediu DENTRO do cliente.
    """

    # sabotagem: remover o initial da view → vermelho
    def test_comercial_ve_o_proprio_nome_no_form(self, client, comercial_logado):
        comercial_logado.first_name = "Ana"
        comercial_logado.last_name = "Vendas"
        comercial_logado.save(update_fields=["first_name", "last_name"])

        resposta = client.get(reverse("iscas:solicitacao_criar"))

        assert resposta.context["form"].initial.get("comercial_responsavel") == "Ana Vendas"

    def test_usa_o_username_quando_nao_ha_nome_completo(
        self, client, comercial_logado
    ):
        """Padrão do projeto: `get_full_name() or username`."""
        resposta = client.get(reverse("iscas:solicitacao_criar"))

        assert resposta.context["form"].initial.get("comercial_responsavel") == (
            comercial_logado.username
        )

    def test_operador_nao_tem_o_campo_preenchido(self, client, operador_fast_logado):
        """Só o comercial — o operador atende contas de vários comerciais."""
        resposta = client.get(reverse("iscas:solicitacao_criar"))

        assert not resposta.context["form"].initial.get("comercial_responsavel")

    def test_nao_toca_no_solicitante(self, client, comercial_logado):
        """`solicitante_nome` é quem pediu DENTRO do cliente — outro sentido."""
        resposta = client.get(reverse("iscas:solicitacao_criar"))

        assert not resposta.context["form"].initial.get("solicitante_nome")


class TestValorDaEntregaNaTela:
    @pytest.fixture
    def pedido(self, cliente, operador, modelo_descartavel):
        from iscas.services import solicitacao as service

        return service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador,
            valor_cliente=Decimal("500.00"),
        )

    # sabotagem: tirar valor_entrega_cliente de _campos_da_origem → vermelho
    def test_sobrevive_aos_dois_passos(
        self, client, operador_logado, pedido, agente, modelo_descartavel,
        unidades_com_agente,
    ):
        """Mesma armadilha do valor do agente: o passo 2 revalida o form."""
        url = reverse("iscas:solicitacao_atribuir", args=[pedido.pk])
        dados = {
            "origem_tipo": OrigemAtribuicao.AGENTE,
            "agente": agente.pk,
            "valor_agente": "80.00",
            "valor_entrega_cliente": "120.00",
        }

        html = client.post(url, dados).content.decode()
        assert 'name="valor_entrega_cliente"' in html
        assert "120.00" in html

        client.post(url, {
            **dados, "confirmar": "1",
            f"unidades_{modelo_descartavel.pk}": [
                u.pk for u in unidades_com_agente[:2]
            ],
        })
        atribuicao = pedido.atribuicoes.get()

        assert atribuicao.valor_agente == Decimal("80.00")
        assert atribuicao.valor_entrega_cliente == Decimal("120.00")

    def test_recusa_entrega_em_retirada(
        self, client, operador_logado, pedido, deposito, unidades_no_deposito
    ):
        client.post(
            reverse("iscas:solicitacao_atribuir", args=[pedido.pk]),
            {
                "origem_tipo": OrigemAtribuicao.RETIRADA_BASE,
                "deposito": deposito.pk,
                "valor_entrega_cliente": "50.00",
            },
            follow=True,
        )

        assert pedido.atribuicoes.count() == 0

    def test_receita_total_soma_a_entrega_no_detalhe(
        self, client, operador_logado, pedido, agente, modelo_descartavel,
        unidades_com_agente, operador,
    ):
        from iscas.services import solicitacao as service

        service.criar_atribuicao(
            solicitacao=pedido, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("80.00"),
            valor_entrega_cliente=Decimal("120.00"),
        )
        totais = client.get(
            reverse("iscas:solicitacao_detalhe", args=[pedido.pk])
        ).context["totais"]

        assert totais["receita_total"] == Decimal("620.00")
        assert totais["margem"] == Decimal("540.00")

    def test_operador_fast_ve_a_entrega_mas_nao_a_receita_total(
        self, client, operador_fast_logado, pedido, agente, modelo_descartavel,
        unidades_com_agente, operador,
    ):
        """Decisão do usuário: quem vincula agente vê o valor da entrega.

        A receita total continua escondida — somá-la revelaria o valor do
        material por subtração.
        """
        from iscas.services import solicitacao as service

        service.criar_atribuicao(
            solicitacao=pedido, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_entrega_cliente=Decimal("120.00"),
        )
        resposta = client.get(reverse("iscas:solicitacao_detalhe", args=[pedido.pk]))

        assert "120,00" in resposta.content.decode()
        assert resposta.context["totais"]["receita_total"] is None
        assert resposta.context["totais"]["valor_cliente"] is None


class TestFormaEntregaNaTela:
    """A pergunta entrega/retirada no momento de vincular."""

    @pytest.fixture
    def pedido(self, cliente, operador, modelo_descartavel):
        from iscas.services import solicitacao as service

        return service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador,
            valor_cliente=Decimal("500.00"),
        )

    def test_a_pergunta_aparece_no_card(self, client, operador_logado, pedido):
        conteudo = client.get(
            reverse("iscas:solicitacao_detalhe", args=[pedido.pk])
        ).content.decode()

        assert "Como o cliente recebe?" in conteudo
        assert 'name="forma_entrega"' in conteudo

    # sabotagem: tirar forma_entrega de _campos_da_origem → vermelho
    def test_sobrevive_aos_dois_passos(
        self, client, operador_logado, pedido, agente, modelo_descartavel,
        unidades_com_agente,
    ):
        from iscas.enums import FormaEntrega

        url = reverse("iscas:solicitacao_atribuir", args=[pedido.pk])
        dados = {
            "origem_tipo": OrigemAtribuicao.AGENTE,
            "agente": agente.pk,
            "forma_entrega": FormaEntrega.RETIRADA,
        }

        html = client.post(url, dados).content.decode()
        assert 'name="forma_entrega"' in html
        assert "RETIRADA" in html

        client.post(url, {
            **dados, "confirmar": "1",
            f"unidades_{modelo_descartavel.pk}": [
                u.pk for u in unidades_com_agente[:2]
            ],
        })
        atribuicao = pedido.atribuicoes.get()

        assert atribuicao.eh_retirada is True
        assert atribuicao.agente == agente

    def test_post_sem_forma_continua_sendo_entrega(
        self, client, operador_logado, pedido, agente, modelo_descartavel,
        unidades_com_agente,
    ):
        """O POST que o app sempre mandou não muda de significado."""
        client.post(reverse("iscas:solicitacao_atribuir", args=[pedido.pk]), {
            "agente": agente.pk, "confirmar": "1",
            f"unidades_{modelo_descartavel.pk}": [
                u.pk for u in unidades_com_agente[:2]
            ],
        })

        assert pedido.atribuicoes.get().eh_retirada is False

    def test_selo_de_retirada_na_linha(
        self, client, operador_logado, pedido, agente, modelo_descartavel,
        unidades_com_agente, operador,
    ):
        from iscas.enums import FormaEntrega
        from iscas.services import solicitacao as service

        service.criar_atribuicao(
            solicitacao=pedido, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            forma_entrega=FormaEntrega.RETIRADA,
        )
        conteudo = client.get(
            reverse("iscas:solicitacao_detalhe", args=[pedido.pk])
        ).content.decode()

        assert "Cliente retira" in conteudo
