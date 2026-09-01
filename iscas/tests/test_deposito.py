"""CRUD de depósito e os avisos quando não existe nenhum.

`Deposito` era model desde o início — o livro-razão, os forms de entrada e de
transferência já o usavam — mas não havia tela para criar um. O dropdown de
destino ficava vazio sem explicação, e a entrada de estoque não funcionava.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, TipoCustodia
from iscas.models.cadastro import Deposito
from iscas.models.custodia import Custodia
from iscas.services import cadastro as cadastro_service
from iscas.services.exceptions import DepositoComSaldo

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


DADOS_VALIDOS = {
    "nome": "Depósito Filial",
    "logradouro": "Rua da Filial",
    "numero": "200",
    "complemento": "",
    "bairro": "Centro",
    "cidade": "Campinas",
    "uf": "SP",
    "cep": "13010-000",
    "latitude_ajustada": "",
    "longitude_ajustada": "",
    "pin_movido": "",
}


class TestCriar:
    def test_cria_pela_tela(self, client, operador_logado):
        resposta = client.post(reverse("iscas:deposito_criar"), DADOS_VALIDOS)

        assert resposta.status_code == 302
        assert Deposito.objects.filter(nome="Depósito Filial").exists()

    def test_ganha_conta_de_custodia(self, client, operador_logado):
        """Sem conta, o depósito não pode receber lançamento (ISC-ADR-03)."""
        client.post(reverse("iscas:deposito_criar"), DADOS_VALIDOS)
        deposito = Deposito.objects.get(nome="Depósito Filial")

        conta = Custodia.todos.get(deposito=deposito)
        assert conta.tipo == TipoCustodia.DEPOSITO

    def test_aceita_pin_ajustado(self, client, operador_logado):
        client.post(
            reverse("iscas:deposito_criar"),
            {
                **DADOS_VALIDOS,
                "latitude_ajustada": "-22.905000",
                "longitude_ajustada": "-47.060000",
                "pin_movido": "1",
            },
        )
        deposito = Deposito.objects.get(nome="Depósito Filial")

        assert float(deposito.latitude) == pytest.approx(-22.905)
        assert deposito.geo_origem == "MANUAL"

    def test_form_tem_cep_e_mapa(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:deposito_criar")).content.decode()

        assert "mapaEndereco" in conteudo
        assert "api/cep/" in conteudo


class TestListarEEditar:
    def test_lista_mostra_estoque(
        self, client, operador_logado, deposito, unidades_no_deposito
    ):
        conteudo = client.get(reverse("iscas:deposito_lista")).content.decode()

        assert deposito.nome in conteudo
        assert "10/10" in conteudo  # 10 disponíveis de 10 em custódia

    def test_editar(self, client, operador_logado, deposito):
        client.post(
            reverse("iscas:deposito_editar", args=[deposito.pk]),
            {**DADOS_VALIDOS, "nome": "Depósito Renomeado"},
        )
        deposito.refresh_from_db()
        assert deposito.nome == "Depósito Renomeado"

    def test_editar_centraliza_no_pin_salvo(self, client, operador_logado, deposito):
        conteudo = client.get(
            reverse("iscas:deposito_editar", args=[deposito.pk])
        ).content.decode()
        assert "const latSalva = -23.550520;" in conteudo


class TestDesativar:
    """Mesma regra do agente: desativação não pode evaporar estoque."""

    def test_com_estoque_e_bloqueado(self, deposito, unidades_no_deposito):
        with pytest.raises(DepositoComSaldo, match="em estoque"):
            cadastro_service.desativar_deposito(deposito)

        deposito.refresh_from_db()
        assert deposito.is_active

    def test_vazio_e_permitido(self, deposito):
        cadastro_service.desativar_deposito(deposito)

        deposito.refresh_from_db()
        assert not deposito.is_active

    def test_bloqueio_pela_tela(
        self, client, operador_logado, deposito, unidades_no_deposito
    ):
        client.post(reverse("iscas:deposito_desativar", args=[deposito.pk]))

        deposito.refresh_from_db()
        assert deposito.is_active

    def test_mantem_historico_apos_desativar(
        self, deposito, unidades_no_deposito, agente, modelo_descartavel, operador
    ):
        from iscas.models.custodia import Movimentacao
        from iscas.services import transferencia as transferencia_service
        from iscas.services.custodia import custodia_de

        transferencia_service.transferir(
            origem=deposito, destino=agente, modelo=modelo_descartavel,
            quantidade=10, autor=operador,
        )
        cadastro_service.desativar_deposito(deposito)

        assert Movimentacao.objects.filter(origem=custodia_de(deposito)).exists()


class TestAvisoQuandoNaoHaDeposito:
    """A causa da confusão: telas dependiam de depósito sem dizer isso."""

    def test_painel_avisa(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:painel")).content.decode()

        assert "Nenhum depósito cadastrado" in conteudo
        assert reverse("iscas:deposito_criar") in conteudo

    def test_painel_nao_avisa_quando_existe(self, client, operador_logado, deposito):
        conteudo = client.get(reverse("iscas:painel")).content.decode()
        assert "Nenhum depósito cadastrado" not in conteudo

    def test_entrada_avisa(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:entrada")).content.decode()

        assert "Nenhum depósito cadastrado" in conteudo
        assert reverse("iscas:deposito_criar") in conteudo

    def test_entrada_nao_avisa_quando_existe(self, client, operador_logado, deposito):
        conteudo = client.get(reverse("iscas:entrada")).content.decode()
        assert "Nenhum depósito cadastrado" not in conteudo

    def test_lista_vazia_explica_o_conceito(self, client, operador_logado):
        """Quem nunca viu o app precisa entender o que é um depósito."""
        conteudo = client.get(reverse("iscas:deposito_lista")).content.decode()

        assert "O que é um depósito?" in conteudo
        assert "ponto de estoque" in conteudo


class TestNavegacao:
    def test_esta_no_menu_do_app(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:painel")).content.decode()
        assert reverse("iscas:deposito_lista") in conteudo

    def test_menu_do_topo_nao_duplica_a_navegacao(self, client, operador_logado):
        """O "Iscas Fast" do header virou link direto para o painel.

        Antes ele era um dropdown que repetia os destinos da barra do app — e
        os dois divergiam: faltavam Saldos e a lixeira de solicitações. A
        navegação entre abas mora só na barra, coberta por `test_navegacao`.
        """
        conteudo = client.get(reverse("iscas:painel")).content.decode()

        assert "dropdownIscas" not in conteudo
        assert reverse("iscas:deposito_lista") in conteudo


class TestPermissao:
    ROTAS = ["iscas:deposito_lista", "iscas:deposito_criar"]

    @pytest.mark.parametrize("rota", ROTAS)
    def test_anonimo_vai_para_login(self, client, rota):
        assert client.get(reverse(rota)).status_code == 302

    @pytest.mark.parametrize("rota", ROTAS)
    def test_operador_acessa(self, client, operador_logado, rota):
        assert client.get(reverse(rota)).status_code == 200


class TestFluxoCompletoComDeposito:
    def test_entrada_transferencia_e_retorno(
        self, client, operador_logado, agente, cliente,
        modelo_retornavel, operador,
    ):
        """O ciclo que só funciona com depósito cadastrado."""
        from iscas.services import entrada as entrada_service
        from iscas.services import retorno as retorno_service
        from iscas.services import solicitacao as solicitacao_service
        from iscas.services import transferencia as transferencia_service
        from iscas.services.saldo import saldo_em_custodia

        client.post(reverse("iscas:deposito_criar"), DADOS_VALIDOS)
        deposito = Deposito.objects.get(nome="Depósito Filial")

        entrada_service.registrar_entrada(
            modelo=modelo_retornavel,
            identificadores=[f"DEP{i:03d}" for i in range(1, 6)],
            destino=deposito, autor=operador,
        )
        assert saldo_em_custodia(deposito, modelo=modelo_retornavel) == 5

        transferencia_service.transferir(
            origem=deposito, destino=agente, modelo=modelo_retornavel,
            quantidade=5, autor=operador,
        )
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_retornavel, 5)], autor=operador
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_retornavel, 5)], autor=operador,
        )
        solicitacao_service.confirmar_entrega(atribuicao=atribuicao, autor=operador)

        # E o retornável volta para o depósito.
        em_posse = list(retorno_service.retornaveis_em_posse(cliente=cliente))
        retorno_service.registrar_retorno(
            unidades=em_posse, destino=deposito, autor=operador
        )
        assert saldo_em_custodia(deposito, modelo=modelo_retornavel) == 5
