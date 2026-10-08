"""Requisição com vários modelos (ItemRequisicao)."""
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.urls import reverse

from acompanhamento.models import Clientes
from produto.models import Produto
from requisicao.models import ItemRequisicao, Requisicoes


@pytest.fixture
def cliente(db):
    return Clientes.objects.create(nome="ACME", endereco="Rua 1", cnpj="11222333000181")


@pytest.fixture
def produtos(db):
    return {n: Produto.objects.create(nome=n) for n in ("Isca 4G", "Isca 2G", "GS310")}


@pytest.fixture
def client_req(client, db):
    user = User.objects.create_user(username="comercial", password="x")
    user.user_permissions.add(*Permission.objects.filter(
        codename__in=["add_requisicoes", "view_requisicoes"]
    ))
    client.force_login(user)
    return client


def _post(cliente, *blocos):
    dados = {"nome": cliente.pk, "email": "cliente@acme.com", "contrato": "Retornavel",
             "motivo": "Substituição", "status": "Pendente", "taxa_envio": "0",
             "item": [str(i) for i in range(len(blocos))]}
    for i, (produto, qtd, custom, valor) in enumerate(blocos):
        dados.update({f"item_{i}_tipo_produto": produto, f"item_{i}_quantidade": qtd,
                      f"item_{i}_customizacao": custom, f"item_{i}_valor_unitario": valor})
    return dados


def _requisicao(cliente, *itens, status="Aprovado pelo CEO"):
    """Requisição gravada direto, com itens (produto, quantidade)."""
    req = Requisicoes(nome=cliente, email="a@b.com", tipo_produto=itens[0][0],
                      numero_de_equipamentos=str(sum(q for _, q in itens)), status=status)
    req._skip_signals = True
    req.save()
    ItemRequisicao.objects.bulk_create(
        ItemRequisicao(requisicao=req, tipo_produto=p, quantidade=q) for p, q in itens
    )
    return req


@pytest.mark.django_db
def test_cria_requisicao_com_varios_modelos_e_resumo(client_req, cliente, produtos, monkeypatch,
                                                     django_capture_on_commit_callbacks):
    itens_ao_notificar = []
    monkeypatch.setattr("requisicao.signals.notificar_requisicao_criada",
                        lambda req: itens_ao_notificar.append(req.itens.count()))

    with django_capture_on_commit_callbacks(execute=True):
        resp = client_req.post(reverse("requisicoescrateview"), _post(
            cliente,
            (produtos["Isca 4G"].pk, "2", "Termo branco", "10.50"),
            ("", "", "", ""),  # bloco aberto e deixado vazio: ignorado
            (produtos["Isca 2G"].pk, "1", "", "8"),
        ))

    assert resp.status_code == 302
    req = Requisicoes.objects.get()
    assert (req.tipo_produto, req.numero_de_equipamentos, req.valor_total) == (
        produtos["Isca 4G"], "3", Decimal("29.00"))
    assert list(req.itens.values_list("tipo_produto__nome", "quantidade")) == [
        ("Isca 4G", 2), ("Isca 2G", 1)]
    # sabotagem: notificar no post_save (antes dos itens) → vermelho
    assert itens_ao_notificar == [2]  # e-mail/PDF só depois de gravar os itens


@pytest.mark.django_db
@pytest.mark.parametrize("blocos, erro", [
    ([("", "2", "", "1")], "Modelo 1: selecione o tipo de produto."),
    ([("4g", "0", "", "1")], "Modelo 1: informe a quantidade (número inteiro maior que zero)."),
    ([("4g", "1", "", "-5")], "Modelo 1: valor unitário inválido."),
    ([("", "", "", "")], "Informe ao menos um modelo de equipamento."),
])
def test_recusa_modelo_invalido_sem_gravar(client_req, cliente, produtos, blocos, erro):
    resp = client_req.post(reverse("requisicoescrateview"), _post(
        cliente, *[(produtos["Isca 4G"].pk if p == "4g" else p, q, c, v) for p, q, c, v in blocos]
    ))

    assert erro in resp.context["form"].errors["itens"]
    assert not Requisicoes.objects.exists()


@pytest.mark.django_db
def test_requisicao_mista_aparece_na_configuracao_e_no_tecnico(cliente, produtos):
    from requisicao.services import (
        PRODUTOS_LISTA_TECNICO, PRODUTOS_SETOR_TECNICO, com_algum_item_em, com_algum_item_fora,
    )

    so_gs310 = _requisicao(cliente, (produtos["GS310"], 1))
    mista = _requisicao(cliente, (produtos["GS310"], 1), (produtos["Isca 4G"], 2))
    so_isca = _requisicao(cliente, (produtos["Isca 4G"], 2))
    todas = Requisicoes.objects.all()

    # sabotagem: voltar ao exclude(itens__tipo_produto__nome__in=...) → vermelho
    assert set(com_algum_item_fora(todas, PRODUTOS_SETOR_TECNICO)) == {mista, so_isca}
    assert set(com_algum_item_em(todas, PRODUTOS_LISTA_TECNICO)) == {so_gs310, mista}


@pytest.mark.django_db
def test_expedicao_parcial_recusa_requisicao_com_varios_modelos(client, cliente, produtos):
    user = User.objects.create_user(username="kanban", password="x")
    user.groups.add(Group.objects.get_or_create(name="Gestão Kanban")[0])
    client.force_login(user)
    req = _requisicao(cliente, (produtos["Isca 4G"], 2), (produtos["Isca 2G"], 1))

    resp = client.post(reverse("kanban_expedir_parcial"),
                       {"requisicao_id": req.pk, "quantidade_expedir": 1},
                       content_type="application/json")

    assert resp.status_code == 400
    assert Requisicoes.objects.count() == 1  # nenhuma requisição de sobra criada


@pytest.mark.django_db
@pytest.mark.parametrize("nomes, esperado", [
    (["CARREGADOR + CABO", "CARREGADOR+CABO USB"], True),
    (["CARREGADOR + CABO", "Isca 4G"], False),
])
def test_carregador_cabo_so_quando_todos_os_modelos_sao(cliente, nomes, esperado):
    from requisicao.services import eh_carregador_cabo

    req = _requisicao(cliente, *[(Produto.objects.create(nome=n), 1) for n in nomes])

    assert eh_carregador_cabo(req) is esperado


@pytest.mark.django_db
def test_lista_de_pendentes_com_consulta_constante(client_req, cliente, produtos,
                                                   django_assert_max_num_queries):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    _requisicao(cliente, (produtos["Isca 4G"], 2), (produtos["Isca 2G"], 1), status="Pendente")
    client_req.get(reverse("requisicoes"))  # aquece sessão/permissões
    with CaptureQueriesContext(connection) as uma:
        client_req.get(reverse("requisicoes"))
    for _ in range(4):
        _requisicao(cliente, (produtos["Isca 4G"], 2), (produtos["Isca 2G"], 1), status="Pendente")

    # sabotagem: remover o prefetch_related dos itens na lista de pendentes → vermelho
    with django_assert_max_num_queries(len(uma)):
        resp = client_req.get(reverse("requisicoes"))
    assert "Isca 2G (1)" in resp.content.decode()



@pytest.mark.django_db
def test_falha_de_email_nao_derruba_a_criacao(client_req, cliente, produtos, monkeypatch,
                                              django_capture_on_commit_callbacks):
    """SMTP recusando destinatário derrubava a tela depois de gravar a requisição."""
    import smtplib

    def recusa(*args, **kwargs):
        raise smtplib.SMTPRecipientsRefused({"x@y.com": (453, b"Access Denied")})

    monkeypatch.setattr("requisicao.signals.send_mail", recusa)
    monkeypatch.setattr("requisicao.signals.gerar_pdf_requisicao", recusa)
    dados = _post(cliente, (produtos["Isca 4G"].pk, "1", "", "1"))
    dados["comercial"] = "MAYRA"  # o ramo que mandava e-mail sem proteção

    with django_capture_on_commit_callbacks(execute=True):
        resp = client_req.post(reverse("requisicoescrateview"), dados)

    assert resp.status_code == 302
    assert Requisicoes.objects.count() == 1



@pytest.fixture
def client_edicao_req(client, db):
    user = User.objects.create_user(username="editor", password="x")
    user.user_permissions.add(Permission.objects.get(codename="change_requisicoes"))
    client.force_login(user)
    return client


def _dados_da_tela(resp):
    """POST com os valores que a própria tela de edição renderizou."""
    form = resp.context["form"]
    return {campo.name: campo.value() for campo in form if campo.value() is not None}


@pytest.mark.django_db
def test_edicao_altera_quantidades_e_ids_e_recalcula_o_resumo(client_edicao_req, cliente, produtos):
    req = _requisicao(cliente, (produtos["Isca 4G"], 2), (produtos["Isca 2G"], 1), status="Pendente")
    req.itens.update(valor_unitario=Decimal("10"))
    i4g, i2g = req.itens.order_by("id")
    url = reverse("RequisicaoUpdateView", args=[req.pk])
    dados = _dados_da_tela(client_edicao_req.get(url))
    dados.update({f"quantidade_{i4g.pk}": 5, f"quantidade_{i2g.pk}": 1, "id_equipamentos": "111 222"})

    resp = client_edicao_req.post(url, dados)

    req.refresh_from_db()
    assert resp.status_code == 302
    assert list(req.itens.order_by("id").values_list("quantidade", flat=True)) == [5, 1]
    # sabotagem: não recalcular o resumo em atualizar_quantidades → vermelho
    assert (req.numero_de_equipamentos, req.valor_total, req.id_equipamentos) == (
        "6", Decimal("60.00"), "111 222")


@pytest.mark.django_db
def test_edicao_recusa_quantidade_zero_sem_gravar(client_edicao_req, cliente, produtos):
    req = _requisicao(cliente, (produtos["Isca 4G"], 2), status="Pendente")
    item = req.itens.get()
    url = reverse("RequisicaoUpdateView", args=[req.pk])
    dados = _dados_da_tela(client_edicao_req.get(url))
    dados[f"quantidade_{item.pk}"] = 0

    resp = client_edicao_req.post(url, dados)

    assert resp.status_code == 200
    item.refresh_from_db()
    assert item.quantidade == 2


@pytest.mark.django_db
def test_edicao_da_requisicao_exige_login(client, cliente, produtos):
    """A view ativa não exigia login: qualquer pessoa com o link editava."""
    req = _requisicao(cliente, (produtos["Isca 4G"], 2), status="Pendente")

    resp = client.get(reverse("RequisicaoUpdateView", args=[req.pk]))

    # sabotagem: tirar PermissionRequiredMixin/LoginRequiredMixin da view → vermelho
    assert resp.status_code == 302 and "login" in resp.url.lower()



@pytest.mark.django_db
def test_valor_total_soma_a_taxa_de_envio_na_criacao_e_na_edicao(client_req, cliente, produtos):
    User.objects.get(username="comercial").user_permissions.add(
        Permission.objects.get(codename="change_requisicoes"))
    dados = _post(cliente, (produtos["Isca 4G"].pk, "2", "", "10.50"), (produtos["Isca 2G"].pk, "1", "", "8"))
    dados["taxa_envio"] = "15.50"
    client_req.post(reverse("requisicoescrateview"), dados)
    req = Requisicoes.objects.get()
    # sabotagem: tirar a taxa_envio de valor_total_da → vermelho
    assert req.valor_total == Decimal("44.50")  # 2×10,50 + 1×8 + 15,50

    url = reverse("RequisicaoUpdateView", args=[req.pk])
    edicao = _dados_da_tela(client_req.get(url))
    edicao["taxa_envio"] = "5"  # taxa alterada na própria edição
    client_req.post(url, edicao)
    req.refresh_from_db()
    assert req.valor_total == Decimal("34.00")  # 29 + 5
