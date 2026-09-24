"""CRUD dos destinatários de notificação.

Estes testes ACESSAM as telas. Ter a rota registrada e a capacidade declarada
não prova que a view roda — um import faltando passa pelas duas checagens e
só aparece como NameError na cara do operador.
"""
import pytest
from django.urls import reverse

from iscas.models.config import DestinatarioNotificacao

pytestmark = pytest.mark.django_db


@pytest.fixture
def destinatario(db):
    return DestinatarioNotificacao.objects.create(
        email="operacao@golden.com", nome="Operação"
    )


class TestTelasRespondem:
    """A varredura de capacidades não executa a view — estes testes executam."""

    # sabotagem: remover o import de DestinatarioNotificacao → vermelho
    @pytest.mark.parametrize("rota", ["iscas:notificacao_lista", "iscas:notificacao_criar"])
    def test_sem_argumento(self, client, operador_logado, rota):
        assert client.get(reverse(rota)).status_code == 200

    def test_lista_com_registro(self, client, operador_logado, destinatario):
        conteudo = client.get(reverse("iscas:notificacao_lista")).content.decode()

        assert destinatario.email in conteudo

    def test_editar(self, client, operador_logado, destinatario):
        url = reverse("iscas:notificacao_editar", args=[destinatario.pk])

        assert client.get(url).status_code == 200

    def test_lixeira(self, client, operador_logado, destinatario):
        destinatario.desativar()
        conteudo = client.get(
            reverse("iscas:notificacao_lista"), {"desativados": "1"}
        ).content.decode()

        assert destinatario.email in conteudo


class TestOperacoes:
    def test_criar_grava_em_minusculas(self, client, operador_logado):
        """`unique` do banco é sensível a caixa — sem normalizar, a mesma
        pessoa entraria duas vezes e receberia dois e-mails."""
        client.post(reverse("iscas:notificacao_criar"), {
            "email": "Fulano@Golden.COM", "nome": "Fulano",
        })

        assert DestinatarioNotificacao.objects.get().email == "fulano@golden.com"

    def test_email_duplicado_nao_da_500(self, client, operador_logado, destinatario):
        resposta = client.post(reverse("iscas:notificacao_criar"), {
            "email": destinatario.email, "nome": "Outro",
        })

        assert resposta.status_code == 200
        assert DestinatarioNotificacao.todos.count() == 1

    def test_desativar_e_reativar(self, client, operador_logado, destinatario):
        from iscas.services import notificacao

        client.post(reverse("iscas:notificacao_desativar", args=[destinatario.pk]))
        assert notificacao.destinatarios_ativos() == []

        client.post(reverse("iscas:notificacao_reativar", args=[destinatario.pk]))
        assert notificacao.destinatarios_ativos() == [destinatario.email]

    @pytest.mark.parametrize("rota", [
        "iscas:notificacao_desativar", "iscas:notificacao_reativar",
    ])
    def test_acao_destrutiva_exige_post(
        self, client, operador_logado, destinatario, rota
    ):
        resposta = client.get(reverse(rota, args=[destinatario.pk]))

        assert resposta.status_code == 405


class TestAcesso:
    """Quem recebe o e-mail vê dado comercial — só o grupo total cadastra."""

    # sabotagem: dar CADASTRAR_NOTIFICACAO a outro papel → vermelho
    @pytest.mark.parametrize("papel", ["operador_fast_logado", "comercial_logado"])
    @pytest.mark.parametrize("rota", [
        "iscas:notificacao_lista", "iscas:notificacao_criar",
    ])
    def test_papeis_restritos_levam_403(self, request, client, papel, rota):
        request.getfixturevalue(papel)

        assert client.get(reverse(rota)).status_code == 403

    def test_anonimo_vai_para_o_login(self, client):
        assert client.get(reverse("iscas:notificacao_lista")).status_code == 302
