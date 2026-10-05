"""Entrada de manutenção com vários tipos de produto (ItemEntrada)."""
import pytest
from django.contrib.auth.models import Permission, User
from django.test import RequestFactory
from django.urls import reverse

from acompanhamento.models import Clientes
from produto.models import Produto
from registrodemanutencao.models import ItemEntrada, registrodemanutencao


@pytest.fixture
def cliente(db):
    return Clientes.objects.create(nome="ACME", endereco="Rua 1", cnpj="11222333000181")


@pytest.fixture
def isca_4g(db):
    return Produto.objects.create(nome="Isca 4G")


@pytest.fixture
def isca_2g(db):
    return Produto.objects.create(nome="Isca 2G")


@pytest.fixture
def client_entrada(client, db):
    user = User.objects.create_user(username="entrada", password="x")
    user.user_permissions.add(
        Permission.objects.get(codename="add_registrodemanutencao"),
        Permission.objects.get(codename="view_registrodemanutencao"),
    )
    client.force_login(user)
    return client


def _post(cliente, *blocos):
    """POST da tela: um bloco por (produto_pk, nºs, customização, contrato)."""
    dados = {
        "nome": cliente.pk, "tipo_entrada": "Manutenção", "status": "Pendente",
        "entregue_por_retirado_por": "Motoboy", "observacoes": "",
        "item": [str(i) for i in range(len(blocos))],
    }
    for i, (produto, numeros, customizacao, contrato) in enumerate(blocos):
        dados[f"item_{i}_tipo_produto"] = produto
        dados[f"item_{i}_numero"] = numeros
        dados[f"item_{i}_customizacao"] = customizacao
        dados[f"item_{i}_tipo_contrato"] = contrato
    return dados


def _entrada(cliente, *itens, status="Pendente"):
    registro = registrodemanutencao.objects.create(nome=cliente, status=status)
    ItemEntrada.objects.bulk_create(
        ItemEntrada(registro=registro, tipo_produto=p, numero_equipamento="1", quantidade=1)
        for p in itens
    )
    return registro


@pytest.mark.django_db
def test_cria_entrada_com_tipos_de_produto_diferentes(client_entrada, cliente, isca_4g, isca_2g):
    resp = client_entrada.post(reverse("FormulariosCreateView"), _post(
        cliente,
        (isca_4g.pk, "111 222\n333", "Caixa de papelão", "Retornavel"),
        ("", "", "", ""),  # bloco aberto e deixado vazio: ignorado
        (isca_2g.pk, "444", "Termo branco", "Descartavel"),
    ))

    assert resp.status_code == 302
    registro = registrodemanutencao.objects.get()
    # sabotagem: gravar a quantidade do 1º item como total no service → vermelho
    assert (registro.quantidade, registro.numero_equipamento) == (4, "111 222 333 444")
    assert list(registro.itens.values_list(
        "tipo_produto__nome", "numero_equipamento", "customizacao", "tipo_contrato", "quantidade"
    )) == [
        ("Isca 4G", "111 222 333", "Caixa de papelão", "Retornavel", 3),
        ("Isca 2G", "444", "Termo branco", "Descartavel", 1),
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "blocos, erro",
    [
        ([("", "111", "", "")], "Produto 1: selecione o tipo de produto."),
        ([("4g", "", "", "")], "Produto 1: informe os nºs dos equipamentos."),
        ([("4g", "111", "", ""), ("4g", "111", "", "")], "Produto 2: nº repetido na entrada (111)."),
        ([("", "", "", "")], "Informe ao menos um tipo de produto."),
        ([("4g", "111", "Inventada", "")], "Produto 1: customização inválida."),
    ],
)
def test_recusa_bloco_invalido_sem_gravar(client_entrada, cliente, isca_4g, blocos, erro):
    resp = client_entrada.post(reverse("FormulariosCreateView"), _post(
        cliente, *[(isca_4g.pk if p == "4g" else p, n, c, t) for p, n, c, t in blocos]
    ))

    assert resp.status_code == 200
    assert erro in resp.context["form"].errors["itens"]
    assert not registrodemanutencao.objects.exists()


@pytest.mark.django_db
def test_historico_consulta_constante_com_itens(client_entrada, cliente, isca_4g, isca_2g,
                                                django_assert_max_num_queries):
    _entrada(cliente, isca_4g, isca_2g)
    client_entrada.get(reverse("historico_manutencaoListView"))  # aquece sessão/perms
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as uma:
        client_entrada.get(reverse("historico_manutencaoListView"))
    for _ in range(4):
        _entrada(cliente, isca_4g, isca_2g)
    # sabotagem: remover prefetch_related('itens__tipo_produto') do histórico → vermelho
    with django_assert_max_num_queries(len(uma)):
        resp = client_entrada.get(reverse("historico_manutencaoListView"))
    assert "Isca 2G (1)" in resp.content.decode()


@pytest.mark.django_db
def test_configuracao_esconde_so_entrada_toda_de_produto_sem_configuracao(cliente, isca_4g):
    from requisicao.views import ConfiguracaoListView

    gs310 = Produto.objects.create(nome="GS310")
    so_gs310 = _entrada(cliente, gs310, status="Aprovado pelo CEO")
    mista = _entrada(cliente, gs310, isca_4g, status="Aprovado pelo CEO")
    sem_produto = _entrada(cliente, None, status="Aprovado pelo CEO")

    view = ConfiguracaoListView()
    view.setup(RequestFactory().get("/"))
    ids = {getattr(r, "pk", None) for r in view.get_queryset()
           if isinstance(r, registrodemanutencao)}

    # sabotagem: voltar ao exclude(itens__tipo_produto__nome__in=...) → vermelho
    assert so_gs310.pk not in ids
    assert {mista.pk, sem_produto.pk} <= ids


@pytest.mark.django_db
def test_laudo_do_email_aceita_produto_com_caractere_especial(cliente):
    """O PDF do e-mail de aprovação roda no worker: erro nele não aparece na tela."""
    from registrodemanutencao.tasks import _gerar_pdf_manutencao

    registro = _entrada(cliente, Produto.objects.create(nome="Isca <4G> & 2G"))

    assert _gerar_pdf_manutencao(registro)[:4] == b"%PDF"


def _post_update(registro, id_equipamento):
    """POST da edição com uma linha nova no laudo por equipamento."""
    return {
        "nome": registro.nome_id, "tipo_entrada": "Manutenção", "status": registro.status,
        "observacoes": "", "imagens-TOTAL_FORMS": "1", "imagens-INITIAL_FORMS": "0",
        "imagens-MIN_NUM_FORMS": "0", "imagens-MAX_NUM_FORMS": "1000",
        "imagens-0-id_equipamento": id_equipamento, "imagens-0-tipo_problema": "Oxidação",
        "imagens-0-faturamento": "", "imagens-0-observacao2": "",
    }


@pytest.fixture
def client_edicao(client, db):
    user = User.objects.create_user(username="lab", password="x")
    user.user_permissions.add(Permission.objects.get(codename="change_registrodemanutencao"))
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_edicao_oferece_so_os_equipamentos_da_entrada(client_edicao, cliente, isca_4g):
    registro = _entrada(cliente, isca_4g)
    registro.itens.update(numero_equipamento="111 222")

    html = client_edicao.get(reverse("FormulariosUpdateView", args=[registro.pk])).content.decode()

    assert '<option value="111">111 — Isca 4G</option>' in html
    assert '<option value="222">222 — Isca 4G</option>' in html


@pytest.mark.django_db
@pytest.mark.parametrize("id_equipamento, salvou", [("222", True), ("999", False)])
def test_edicao_aceita_so_equipamento_da_entrada(client_edicao, cliente, isca_4g,
                                                  id_equipamento, salvou):
    registro = _entrada(cliente, isca_4g)
    registro.itens.update(numero_equipamento="111 222")

    client_edicao.post(reverse("FormulariosUpdateView", args=[registro.pk]),
                       _post_update(registro, id_equipamento))

    assert registro.imagens.filter(id_equipamento=id_equipamento).exists() is salvou


@pytest.mark.django_db
def test_edicao_mantem_id_digitado_antes_do_select(client_edicao, cliente, isca_4g):
    registro = _entrada(cliente, isca_4g)
    registro.imagens.create(id_equipamento="ANTIGO-1", tipo_problema="Oxidação")

    html = client_edicao.get(reverse("FormulariosUpdateView", args=[registro.pk])).content.decode()

    assert 'value="ANTIGO-1" selected' in html


@pytest.mark.django_db
def test_edicao_recusa_mesmo_equipamento_em_duas_linhas(client_edicao, cliente, isca_4g):
    registro = _entrada(cliente, isca_4g)
    registro.itens.update(numero_equipamento="111 222")
    dados = _post_update(registro, "111")
    dados.update({"imagens-TOTAL_FORMS": "2", "imagens-1-id_equipamento": "111",
                  "imagens-1-tipo_problema": "Oxidação", "imagens-1-faturamento": ""})

    resp = client_edicao.post(reverse("FormulariosUpdateView", args=[registro.pk]), dados)

    assert "Equipamento 111 já escolhido em outra linha." in resp.content.decode()
    assert not registro.imagens.exists()



@pytest.mark.django_db
def test_detalhe_abre_com_laudo_sem_foto(client_edicao, cliente, isca_4g):
    """Laudo sem foto derrubava o detalhe (ValueError em imagem.url)."""
    registro = _entrada(cliente, isca_4g)
    registro.imagens.create(id_equipamento="111", tipo_problema="Oxidação")

    resp = client_edicao.get(reverse("FormularioDetailView", args=[registro.pk]))

    assert resp.status_code == 200
    assert "ID: 111" in resp.content.decode()
