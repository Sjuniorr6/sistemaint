"""Testes do botão "Download PDF" na tela Histórico de Manutenções.

Referência estrutural: controle_acionamentos (SCA) — pytest + @pytest.mark.django_db,
asserts diretos, sem importar regra de negócio.

Regra coberta: o botão "Download PDF" deve aparecer para os status que liberam o
laudo (Comercial, Manutenção, Aprovado pela Inteligência, Tratativa Finalizada) e
NÃO deve aparecer para os demais (ex.: Pendente).
"""
import pytest
from django.contrib.auth.models import Permission, User
from django.test import Client
from django.urls import reverse

from acompanhamento.models import Clientes
from registrodemanutencao.models import registrodemanutencao


def _cliente():
    return Clientes.objects.create(
        nome="Cliente Teste",
        endereco="Rua Teste, 123",
        cnpj="11222333000181",
    )


def _registro(cliente, status):
    return registrodemanutencao.objects.create(nome=cliente, status=status)


@pytest.fixture
def client_autorizado():
    """Client autenticado com a permissão exigida pela historico_manutencaoListView."""
    user = User.objects.create_user(username="faturamento", password="x")
    user.user_permissions.add(
        Permission.objects.get(codename="view_registrodemanutencao")
    )
    api = Client()
    api.force_login(user)
    return api


def _link_pdf(registro):
    return reverse("download_pdfmanutencao", args=[registro.id])


@pytest.mark.django_db
def test_botao_pdf_aparece_em_manutencao(client_autorizado):
    cliente = _cliente()
    registro = _registro(cliente, "Manutenção")

    resp = client_autorizado.get(reverse("historico_manutencaoListView"))

    assert resp.status_code == 200
    assert _link_pdf(registro) in resp.content.decode()


@pytest.mark.django_db
def test_botao_pdf_aparece_em_aprovado_pela_inteligencia(client_autorizado):
    cliente = _cliente()
    registro = _registro(cliente, "Aprovado pela Inteligência")

    resp = client_autorizado.get(reverse("historico_manutencaoListView"))

    assert resp.status_code == 200
    assert _link_pdf(registro) in resp.content.decode()


@pytest.mark.django_db
def test_botao_pdf_nao_aparece_em_pendente(client_autorizado):
    cliente = _cliente()
    registro = _registro(cliente, "Pendente")

    resp = client_autorizado.get(reverse("historico_manutencaoListView"))

    assert resp.status_code == 200
    assert _link_pdf(registro) not in resp.content.decode()
