"""Contrato do endpoint /requisicao/api/requisicoes/ids/."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from acompanhamento.models import Clientes
from produto.models import Produto
from requisicao.models import Requisicoes


@pytest.fixture
def cliente_api(db):
    usuario = get_user_model().objects.create_user(username="api", password="x")
    token = Token.objects.create(user=usuario)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return api


@pytest.fixture
def produto(db):
    return Produto.objects.create(nome="Isca Fast")


@pytest.fixture
def cliente_acme(db):
    return Clientes.objects.create(nome="ACME LTDA", endereco="Rua A, 1", cnpj="1")


@pytest.fixture
def url():
    return reverse("api_requisicoes_ids")


def _requisicao(cliente, produto, **kwargs):
    """Cria a requisição sem disparar o post_save que gera PDF e manda e-mail.

    `_skip_signals` é a flag que o próprio `requisicao/signals.py` consulta —
    a expedição parcial já a usa em produção.
    """
    req = Requisicoes(nome=cliente, tipo_produto=produto, **kwargs)
    req._skip_signals = True
    req.save()
    return req


@pytest.mark.django_db
def test_retorna_cliente_data_quantidade_e_ids(cliente_api, url, cliente_acme, produto):
    _requisicao(
        cliente_acme,
        produto,
        numero_de_equipamentos="3",
        id_equipamentos="  ID-001   ID-002\nID-003 ",
    )

    corpo = cliente_api.get(url).json()

    assert corpo["total"] == 1
    (item,) = corpo["requisicoes"]
    assert item["cliente"] == "ACME LTDA"
    assert item["quantidade"] == 3
    # A string de ids é separada por espaços/quebras — o split normaliza ambos.
    assert item["ids"] == ["ID-001", "ID-002", "ID-003"]
    assert item["data"]


@pytest.mark.django_db
def test_exige_autenticacao(url):
    assert APIClient().get(url).status_code in (401, 403)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "numero, ids_brutos, quantidade_esperada, ids_esperados",
    [
        (None, None, 0, []),
        ("", "", 0, []),
        ("abc", "ID-9", 0, ["ID-9"]),  # numero_de_equipamentos é CharField livre
        ("2", None, 2, []),
    ],
)
def test_campos_vazios_ou_invalidos_nao_quebram(
    cliente_api, url, cliente_acme, produto, numero, ids_brutos, quantidade_esperada, ids_esperados
):
    _requisicao(cliente_acme, produto, numero_de_equipamentos=numero, id_equipamentos=ids_brutos)

    (item,) = cliente_api.get(url).json()["requisicoes"]

    assert item["quantidade"] == quantidade_esperada
    assert item["ids"] == ids_esperados


@pytest.mark.django_db
def test_filtra_por_cliente_e_intervalo_de_data(cliente_api, url, cliente_acme, produto):
    outro = Clientes.objects.create(nome="OUTRA SA", endereco="Rua B, 2", cnpj="2")
    _requisicao(cliente_acme, produto, numero_de_equipamentos="1")
    _requisicao(outro, produto, numero_de_equipamentos="1")

    corpo = cliente_api.get(url, {"cliente": "acme"}).json()

    assert [i["cliente"] for i in corpo["requisicoes"]] == ["ACME LTDA"]

    # `data` é auto_now_add: tudo cai em hoje, então uma janela no passado zera.
    vazio = cliente_api.get(url, {"data_fim": "2000-01-01"}).json()
    assert vazio["total"] == 0


@pytest.mark.django_db
def test_pagina_resultados_sem_carregar_tudo(cliente_api, url, cliente_acme, produto):
    for _ in range(3):
        _requisicao(cliente_acme, produto, numero_de_equipamentos="1")

    corpo = cliente_api.get(url, {"page_size": 2}).json()

    assert corpo["total"] == 3, "total é o do queryset inteiro, não o da página"
    assert len(corpo["requisicoes"]) == 2
    assert corpo["page"] == 1 and corpo["num_pages"] == 2

    pagina2 = cliente_api.get(url, {"page_size": 2, "page": 2}).json()
    assert len(pagina2["requisicoes"]) == 1


@pytest.mark.django_db
def test_nao_faz_query_por_requisicao(cliente_api, url, cliente_acme, produto, django_assert_num_queries):
    for _ in range(5):
        _requisicao(cliente_acme, produto, numero_de_equipamentos="1", id_equipamentos="X")

    with django_assert_num_queries(3) as ctx:
        cliente_api.get(url)
    # sabotagem: remover select_related("nome") da view → vermelho (3 → 8 queries)
    baseline = len(ctx.captured_queries)

    for _ in range(5):
        _requisicao(cliente_acme, produto, numero_de_equipamentos="1", id_equipamentos="X")

    with django_assert_num_queries(baseline):
        cliente_api.get(url)
