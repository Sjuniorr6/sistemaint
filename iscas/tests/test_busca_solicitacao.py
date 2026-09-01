"""Busca por proximidade ancorada na solicitação (ISC-RF-17, ISC-RF-18).

Antes o operador escolhia cliente, modelo e quantidade minima em campos
soltos — tres dados que a solicitacao ja tem, e que podiam descrever uma
combinacao que nao corresponde a pedido nenhum.
"""
import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES
from iscas.services import solicitacao as solicitacao_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


def _buscar(client, **params):
    return json.loads(
        client.get(reverse("iscas:api_proximidade"), params).content
    )


class TestBuscaPorSolicitacao:
    def test_traz_agente_que_tem_o_que_falta(
        self, client, operador_logado, cliente, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
        )
        dados = _buscar(client, solicitacao=solicitacao.pk, raio_km=50)

        assert [a["nome"] for a in dados["agentes"]] == [agente.nome]
        assert dados["solicitacao"]["id"] == solicitacao.pk

    def test_o_disponivel_e_o_que_cobre_do_pedido_nao_o_saldo_bruto(
        self, client, operador_logado, cliente, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        """O agente tem 8; o pedido quer 3. Ele contribui 3, nao 8.

        Mostrar 8 faria o operador achar que sobra folga onde nao sobra, e
        ordenaria a lista pelo estoque do agente em vez de pela utilidade
        dele para ESTE pedido.
        """
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
        )
        dados = _buscar(client, solicitacao=solicitacao.pk, raio_km=50)

        assert dados["agentes"][0]["disponivel"] == 3
        assert dados["agentes"][0]["cobre_tudo"] is True

    def test_agente_so_com_modelo_fora_do_pedido_nao_aparece(
        self, client, operador_logado, cliente, agente,
        retornaveis_com_agente, modelo_descartavel, operador,
    ):
        """O agente tem 5 retornaveis; o pedido e de descartaveis."""
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
        )
        dados = _buscar(client, solicitacao=solicitacao.pk, raio_km=50)

        assert dados["agentes"] == []

    def test_cobertura_parcial_aparece_marcada(
        self, client, operador_logado, cliente, agente,
        unidades_com_agente, retornaveis_com_agente,
        modelo_descartavel, modelo_retornavel, operador,
    ):
        """Pede 3+2 e o agente cobre so um dos modelos por inteiro?

        Ele continua util — atendimento em conjunto e normal (ISC-RN-10) —
        mas `cobre_tudo` precisa dizer a verdade, senao o operador acha que
        um agente so resolve o pedido.
        """
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente,
            itens=[(modelo_descartavel, 3), (modelo_retornavel, 20)],
            autor=operador,
        )
        dados = _buscar(client, solicitacao=solicitacao.pk, raio_km=50)
        agente_json = dados["agentes"][0]

        assert agente_json["cobre_tudo"] is False
        assert agente_json["disponivel"] == 3 + 5  # 3 do pedido + os 5 que tem
        por_modelo = {m["codigo"]: m for m in agente_json["por_modelo"]}
        assert por_modelo[modelo_retornavel.codigo]["cobre"] == 5
        assert por_modelo[modelo_retornavel.codigo]["falta"] == 20

    def test_solicitacao_ja_coberta_nao_tem_o_que_buscar(
        self, client, operador_logado, cliente, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        dados = _buscar(client, solicitacao=solicitacao.pk, raio_km=50)

        assert dados["agentes"] == []

    def test_cliente_sem_coordenada_explica_a_causa(
        self, client, operador_logado, agente, unidades_com_agente,
        modelo_descartavel, operador, db,
    ):
        """Lista vazia leria como "nao ha agente perto" — que e falso."""
        from iscas.models.cadastro import Cliente

        sem_pin = Cliente.objects.create(
            nome_razao_social="Cliente Sem Pin",
            documento="12345678000199",
            logradouro="Rua Sem Pin", numero="1",
            bairro="Centro", cidade="São Paulo", uf="SP", cep="01001-000",
        )
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=sem_pin, itens=[(modelo_descartavel, 3)], autor=operador
        )
        resposta = client.get(
            reverse("iscas:api_proximidade"),
            {"solicitacao": solicitacao.pk, "raio_km": 50},
        )

        assert resposta.status_code == 400
        assert "sem coordenada" in json.loads(resposta.content)["erro"]


class TestFormDeBusca:
    def test_so_oferece_solicitacao_que_precisa_de_agente(
        self, cliente, agente, unidades_com_agente, modelo_descartavel, operador,
    ):
        """Solicitacao entregue nao entra: nao ha o que buscar para ela."""
        from iscas.forms import BuscaProximidadeForm

        aberta = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
        )
        entregue = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=entregue, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        solicitacao_service.confirmar_entrega(
            atribuicao=atribuicao, autor=operador, recebido_por="Portaria"
        )

        oferecidas = list(BuscaProximidadeForm().fields["solicitacao"].queryset)

        assert aberta in oferecidas
        assert entregue not in oferecidas


def test_mapa_renderiza_com_busca_por_solicitacao(
    client, operador_logado, cliente, modelo_descartavel, operador,
):
    solicitacao = solicitacao_service.abrir_solicitacao(
        cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
    )
    resposta = client.get(reverse("iscas:mapa"))
    conteudo = resposta.content.decode()

    assert resposta.status_code == 200
    # O select de solicitacao substituiu o de cliente.
    assert 'id="id_solicitacao"' in conteudo
    assert f"Solicitação #{solicitacao.pk}" in conteudo
    assert 'id="id_cliente"' not in conteudo
    # Os pinos de solicitacao agora abrem em leque quando coincidem.
    assert "markerClusterGroup" in conteudo
    assert "spiderfyOnMaxZoom" in conteudo


def test_busca_htmx_por_solicitacao(
    client, operador_logado, cliente, agente, unidades_com_agente,
    modelo_descartavel, operador,
):
    """A view HTMX usa o mesmo form; sem isso ela quebraria em silencio."""
    solicitacao = solicitacao_service.abrir_solicitacao(
        cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
    )
    resposta = client.get(
        reverse("iscas:busca_proximidade"),
        {"solicitacao": solicitacao.pk, "raio_km": 50},
        headers={"HX-Request": "true"},
    )

    assert resposta.status_code == 200
    assert agente.nome in resposta.content.decode()
