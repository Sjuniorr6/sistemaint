"""Soft-delete do agente (ISC-RN-18) e contagem constante de queries nas listagens."""
import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext

from iscas.enums import GRUPO_OPERADORES
from iscas.models.cadastro import Agente
from iscas.services import cadastro as cadastro_service
from iscas.services.exceptions import AgenteComSaldo

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


def _novo_agente(nome, cpf):
    agente = Agente(
        nome=nome,
        telefone="11999990000",
        logradouro="Rua X",
        cidade="São Paulo",
        uf="SP",
        latitude="-23.550520",
        longitude="-46.633308",
    )
    agente.cpf = cpf
    agente.save()
    return agente


def test_desativado_sai_das_listas_mas_nao_do_banco(agente):
    cadastro_service.desativar_agente(agente)

    assert not Agente.objects.filter(pk=agente.pk).exists()
    # Soft-delete: nunca some do banco — o histórico e as movimentações dele
    # continuam apontando para este registro.
    assert Agente.todos.filter(pk=agente.pk).exists()


def test_desativar_com_equipamento_em_posse_e_bloqueado(
    agente, unidades_com_agente
):
    """Desativar quem segura estoque o faria sumir da operação sem sair do livro."""
    with pytest.raises(AgenteComSaldo):
        cadastro_service.desativar_agente(agente)

    agente.refresh_from_db()
    assert agente.is_active is True


def test_reativar_devolve_o_agente_a_operacao(agente):
    cadastro_service.desativar_agente(agente)
    cadastro_service.reativar_agente(agente)

    assert Agente.objects.filter(pk=agente.pk).exists()


class TestTelaDeAgentes:
    def test_lista_esconde_desativados_e_a_lixeira_os_mostra(
        self, client, operador_logado, agente, agente2
    ):
        cadastro_service.desativar_agente(agente)

        ativos = client.get("/iscas/agentes/")
        assert [l["agente"] for l in ativos.context["linhas"]] == [agente2]

        lixeira = client.get("/iscas/agentes/", {"desativados": "1"})
        assert [l["agente"] for l in lixeira.context["linhas"]] == [agente]

    def test_botoes_de_desativar_e_reativar_estao_na_tela(
        self, client, operador_logado, agente
    ):
        """O recurso só existe se houver como acioná-lo: a lista não tinha botão."""
        ativos = client.get("/iscas/agentes/").content.decode()
        assert f"/iscas/agentes/{agente.pk}/desativar/" in ativos

        cadastro_service.desativar_agente(agente)
        lixeira = client.get("/iscas/agentes/", {"desativados": "1"}).content.decode()
        assert f"/iscas/agentes/{agente.pk}/reativar/" in lixeira

    def test_post_desativa_e_reativa(self, client, operador_logado, agente):
        client.post(f"/iscas/agentes/{agente.pk}/desativar/")
        agente.refresh_from_db()
        assert agente.is_active is False

        client.post(f"/iscas/agentes/{agente.pk}/reativar/")
        agente.refresh_from_db()
        assert agente.is_active is True


class TestSemNMaisUm:
    """As listagens agregam saldo em lote: o custo não cresce com o cadastro.

    O teto de 5 testes por task é estourado aqui de propósito: contagem
    constante de queries é nível 1 (performance de listagem), e cada listagem
    corrigida precisa da sua própria medição — a de uma não prova a da outra.
    """

    #: CPFs válidos distintos, para criar vários agentes.
    CPFS = ["39053344705", "11144477735", "12345678909", "52998224725"]

    @staticmethod
    def _medir(client, url):
        """Consultas de UMA requisição, sem o ruído da primeira.

        A primeira requisição do cliente carrega sessão e usuário, e a segunda
        não — sem o aquecimento, a base sai maior que a medição seguinte e o
        teste falha ao contrário, escondendo o que deveria provar.
        """
        client.get(url)
        with CaptureQueriesContext(connection) as capturado:
            client.get(url)
        return len(capturado)

    def test_lista_de_agentes(
        self, client, operador_logado, django_assert_num_queries
    ):
        # sabotagem: trocar saldo_por_modelo_em_lote por saldo_por_modelo no
        # laço de agente_lista -> vermelho
        _novo_agente("Agente A", self.CPFS[0])
        base = self._medir(client, "/iscas/agentes/")

        for nome, cpf in zip("BCD", self.CPFS[1:]):
            _novo_agente(f"Agente {nome}", cpf)

        # Quatro agentes em vez de um: o número de consultas não muda.
        with django_assert_num_queries(base):
            client.get("/iscas/agentes/")

    def test_lista_de_depositos(
        self, client, operador_logado, deposito, django_assert_num_queries
    ):
        from iscas.models.cadastro import Deposito

        # sabotagem: voltar saldo_por_modelo/tem_saldo por depósito -> vermelho
        base = self._medir(client, "/iscas/depositos/")

        for i in range(3):
            Deposito.objects.create(
                nome=f"Depósito {i}", logradouro="Rua Y", cidade="São Paulo", uf="SP"
            )

        with django_assert_num_queries(base):
            client.get("/iscas/depositos/")

    def test_geojson_do_mapa(
        self, client, operador_logado, django_assert_num_queries
    ):
        """O endpoint carrega a base inteira de agentes de uma vez."""
        # sabotagem: voltar saldo_por_modelo por agente em agentes_geojson -> vermelho
        _novo_agente("Agente A", self.CPFS[0])
        base = self._medir(client, "/iscas/api/agentes.geojson")

        for nome, cpf in zip("BCD", self.CPFS[1:]):
            _novo_agente(f"Agente {nome}", cpf)

        with django_assert_num_queries(base):
            client.get("/iscas/api/agentes.geojson")

    def test_painel(self, client, operador_logado, django_assert_num_queries):
        """O alerta de saldo baixo varria todos os agentes, um por consulta."""
        # sabotagem: voltar saldo_disponivel por agente no painel -> vermelho
        _novo_agente("Agente A", self.CPFS[0])
        base = self._medir(client, "/iscas/")

        for nome, cpf in zip("BCD", self.CPFS[1:]):
            _novo_agente(f"Agente {nome}", cpf)

        with django_assert_num_queries(base):
            client.get("/iscas/")
