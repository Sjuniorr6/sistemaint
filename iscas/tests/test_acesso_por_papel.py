"""O que cada papel alcança e o que leva 403 (ISC-RN-19).

As listas abaixo são o requisito do usuário em forma de rota. O teste exercita
a fronteira real (cliente HTTP), não o predicado: é a diferença entre "a regra
existe" e "a regra está ligada na porta".

Em rota `require_POST`, o GET de quem TEM a capacidade responde 405 — e isso é
justamente a prova de que passou pela autorização e morreu no método.
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


#: Rotas sem argumento que o Comercial NÃO pode alcançar.
NEGADAS_AO_COMERCIAL = [
    "iscas:entrada",
    "iscas:transferencia",
    "iscas:baixa",
    "iscas:manutencao",
    "iscas:manutencao_retorno",
    "iscas:agente_lista",
    "iscas:agente_criar",
    "iscas:deposito_lista",
    "iscas:deposito_criar",
    "iscas:modelo_lista",
    "iscas:modelo_criar",
    "iscas:unidade_lista",
    "iscas:painel_saldo",
    "iscas:retornaveis",
    "iscas:extrato",
    "iscas:extrato_csv",
    "iscas:auditoria",
]

#: Rotas sem argumento que o Comercial PODE alcançar.
PERMITIDAS_AO_COMERCIAL = [
    "iscas:painel",
    "iscas:mapa",
    "iscas:solicitacao_lista",
    "iscas:solicitacao_criar",
    "iscas:cliente_lista",
    "iscas:cliente_criar",
]

#: Rotas sem argumento que o Operador Fast NÃO pode alcançar.
NEGADAS_AO_OPERADOR_FAST = [
    "iscas:entrada",
    "iscas:transferencia",
    "iscas:agente_lista",
    "iscas:agente_criar",
    "iscas:deposito_lista",
    "iscas:deposito_criar",
    "iscas:auditoria",
]

#: Rotas sem argumento que o Operador Fast PODE alcançar.
PERMITIDAS_AO_OPERADOR_FAST = [
    "iscas:painel",
    "iscas:mapa",
    "iscas:solicitacao_lista",
    "iscas:solicitacao_criar",
    "iscas:cliente_lista",
    "iscas:cliente_criar",
    "iscas:modelo_lista",
    "iscas:modelo_criar",
    "iscas:baixa",
    "iscas:manutencao",
    "iscas:manutencao_retorno",
    "iscas:unidade_lista",
    "iscas:painel_saldo",
    "iscas:retornaveis",
    "iscas:extrato",
]


class TestComercial:
    """Só painel, mapa, solicitações e cliente."""

    # sabotagem: dar VER_ESTOQUE ao Comercial → vermelho
    @pytest.mark.parametrize("rota", NEGADAS_AO_COMERCIAL)
    def test_nao_alcanca(self, client, comercial_logado, rota):
        assert client.get(reverse(rota)).status_code == 403

    @pytest.mark.parametrize("rota", PERMITIDAS_AO_COMERCIAL)
    def test_alcanca(self, client, comercial_logado, rota):
        assert client.get(reverse(rota)).status_code == 200

    def test_nao_exclui_solicitacao(self, client, comercial_logado, solicitacao_simples):
        url = reverse("iscas:solicitacao_excluir", args=[solicitacao_simples.pk])
        assert client.post(url).status_code == 403

    def test_nao_atribui(self, client, comercial_logado, solicitacao_simples):
        url = reverse("iscas:solicitacao_atribuir", args=[solicitacao_simples.pk])
        assert client.post(url).status_code == 403

    def test_ve_a_solicitacao_que_abriu(
        self, client, comercial_logado, solicitacao_simples
    ):
        """Decisão registrada: ele vê a lista inteira, sem filtro por autor.

        Fica como teste para que ninguém "corrija" isso para um filtro por
        `aberta_por` achando que é bug.
        """
        url = reverse("iscas:solicitacao_detalhe", args=[solicitacao_simples.pk])
        assert client.get(url).status_code == 200
        assert client.get(reverse("iscas:solicitacao_lista")).status_code == 200


class TestOperadorFast:
    """Atende e dá baixa; não movimenta estoque nem cadastra agente."""

    # sabotagem: dar MOVIMENTAR_ESTOQUE ao Operador Fast → vermelho
    @pytest.mark.parametrize("rota", NEGADAS_AO_OPERADOR_FAST)
    def test_nao_alcanca(self, client, operador_fast_logado, rota):
        assert client.get(reverse(rota)).status_code == 403

    @pytest.mark.parametrize("rota", PERMITIDAS_AO_OPERADOR_FAST)
    def test_alcanca(self, client, operador_fast_logado, rota):
        assert client.get(reverse(rota)).status_code == 200

    def test_nao_desativa_cadastro(self, client, operador_fast_logado, cliente):
        url = reverse("iscas:cliente_desativar", args=[cliente.pk])
        assert client.post(url).status_code == 403

    def test_nao_exclui_solicitacao(
        self, client, operador_fast_logado, solicitacao_simples
    ):
        url = reverse("iscas:solicitacao_excluir", args=[solicitacao_simples.pk])
        assert client.post(url).status_code == 403

    def test_atribui(self, client, operador_fast_logado, solicitacao_simples):
        """Atender é o que define este papel — 405 prova que passou da porta."""
        url = reverse("iscas:solicitacao_atribuir", args=[solicitacao_simples.pk])
        assert client.get(url).status_code == 405
