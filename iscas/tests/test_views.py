"""Testes de integração: views, permissões, endpoint GeoJSON e CSV.

Cobre o que o ARCHITECTURE lista na camada de integração, incluindo o
mascaramento de CPF nas listagens (ISC-RN-16) — que precisa valer mesmo sob
manipulação de parâmetro.
"""
import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from iscas.enums import GRUPO_OPERADORES, StatusAtribuicao, StatusSolicitacao
from iscas.services import solicitacao as solicitacao_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def grupo_operadores(db):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    return grupo


@pytest.fixture
def operador_logado(client, operador, grupo_operadores):
    operador.groups.add(grupo_operadores)
    client.force_login(operador)
    return operador


@pytest.fixture
def usuario_sem_papel(db):
    return get_user_model().objects.create_user(username="intruso", password="x")


class TestPermissoes:
    """As rotas do app são restritas ao grupo de operadores (ISC-RN-19)."""

    ROTAS = [
        "iscas:painel",
        "iscas:agente_lista",
        "iscas:cliente_lista",
        "iscas:modelo_lista",
        "iscas:unidade_lista",
        "iscas:mapa",
        "iscas:solicitacao_lista",
        "iscas:painel_saldo",
        "iscas:retornaveis",
        "iscas:extrato",
        "iscas:api_agentes",
    ]

    @pytest.mark.parametrize("rota", ROTAS)
    def test_anonimo_vai_para_o_login(self, client, rota):
        resposta = client.get(reverse(rota))
        assert resposta.status_code == 302
        assert "/login" in resposta.url or "next=" in resposta.url

    @pytest.mark.parametrize("rota", ROTAS)
    def test_autenticado_sem_papel_leva_403(self, client, usuario_sem_papel, rota):
        client.force_login(usuario_sem_papel)
        assert client.get(reverse(rota)).status_code == 403

    @pytest.mark.parametrize("rota", ROTAS)
    def test_operador_acessa(self, client, operador_logado, rota):
        assert client.get(reverse(rota)).status_code == 200


class TestTelasPrincipais:
    def test_painel_carrega(self, client, operador_logado, unidades_no_deposito):
        resposta = client.get(reverse("iscas:painel"))
        assert resposta.status_code == 200
        assert b"Painel operacional" in resposta.content

    def test_lista_de_agentes_mostra_cpf_mascarado(
        self, client, operador_logado, agente
    ):
        """ISC-RN-16: listagem nunca expõe o CPF completo."""
        resposta = client.get(reverse("iscas:agente_lista"))
        conteudo = resposta.content.decode()
        assert "39053344705" not in conteudo
        assert "390.533.447-05" not in conteudo
        assert "***" in conteudo

    def test_ficha_do_agente_mostra_cpf_completo(self, client, operador_logado, agente):
        """A ficha é o único lugar autorizado (ISC-RN-16)."""
        resposta = client.get(reverse("iscas:agente_detalhe", args=[agente.pk]))
        assert "39053344705" in resposta.content.decode()

    def test_detalhe_da_unidade(self, client, operador_logado, unidades_no_deposito):
        unidade = unidades_no_deposito[0]
        resposta = client.get(
            reverse("iscas:unidade_detalhe", args=[unidade.identificador])
        )
        assert resposta.status_code == 200
        assert unidade.identificador.encode() in resposta.content

    def test_mapa_carrega(self, client, operador_logado, agente):
        resposta = client.get(reverse("iscas:mapa"))
        assert resposta.status_code == 200
        assert b"leaflet" in resposta.content.lower()

    def test_painel_de_saldo(
        self, client, operador_logado, unidades_com_agente, agente
    ):
        resposta = client.get(reverse("iscas:painel_saldo"))
        assert resposta.status_code == 200
        assert agente.nome.encode() in resposta.content


class TestEndpointGeoJSON:
    """ISC-ADR-12: JsonResponse, sem DRF, com teste de formato."""

    def test_formato_geojson(
        self, client, operador_logado, agente, unidades_com_agente
    ):
        resposta = client.get(reverse("iscas:api_agentes"))
        dados = json.loads(resposta.content)

        assert dados["type"] == "FeatureCollection"
        assert len(dados["features"]) == 1

        feature = dados["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        # GeoJSON é [longitude, latitude] — trocar a ordem põe o pin na China.
        lng, lat = feature["geometry"]["coordinates"]
        assert lng == pytest.approx(float(agente.longitude))
        assert lat == pytest.approx(float(agente.latitude))
        assert feature["properties"]["nome"] == agente.nome
        assert feature["properties"]["saldos"][0]["disponivel"] == 8

    def test_agente_sem_coordenada_fora_do_geojson(
        self, client, operador_logado, agente_sem_coordenada
    ):
        dados = json.loads(client.get(reverse("iscas:api_agentes")).content)
        assert dados["features"] == []

    def test_api_proximidade(
        self, client, operador_logado, agente, unidades_com_agente, cliente
    ):
        resposta = client.get(
            reverse("iscas:api_proximidade"),
            {"cliente": cliente.pk, "raio_km": 50},
        )
        dados = json.loads(resposta.content)
        assert dados["cliente"]["properties"]["nome"] == cliente.nome_razao_social
        assert len(dados["agentes"]) == 1
        assert dados["agentes"][0]["nome"] == agente.nome
        assert dados["agentes"][0]["disponivel"] == 8
        assert dados["agentes"][0]["distancia_km"] >= 0

    def test_api_proximidade_sem_ponto_recusa(self, client, operador_logado):
        resposta = client.get(reverse("iscas:api_proximidade"), {"raio_km": 10})
        assert resposta.status_code == 400


class TestFluxoPelasViews:
    """A jornada do atendimento, pelas telas."""

    def test_cadastro_de_agente_pela_view(self, client, operador_logado):
        resposta = client.post(
            reverse("iscas:agente_criar"),
            {
                "nome": "Novo Agente",
                "cpf": "390.533.447-05",
                "telefone": "11999998888",
                "logradouro": "Rua Nova",
                "numero": "10",
                "cidade": "São Paulo",
                "uf": "SP",
                "cep": "01000-000",
                "email": "",
                "complemento": "",
                "bairro": "",
                "observacao": "",
            },
        )
        assert resposta.status_code == 302

        from iscas.models.cadastro import Agente

        agente = Agente.objects.get(nome="Novo Agente")
        assert agente.cpf == "39053344705"
        # Nominatim está desligado nos testes: o cadastro grava mesmo assim.
        assert agente.geo_origem == "PENDENTE"

    def test_cpf_duplicado_e_rejeitado_no_form(self, client, operador_logado, agente):
        resposta = client.post(
            reverse("iscas:agente_criar"),
            {
                "nome": "Clone", "cpf": "39053344705", "telefone": "11900000000",
                "logradouro": "Rua X", "cidade": "São Paulo", "uf": "SP",
                "numero": "", "complemento": "", "bairro": "", "cep": "",
                "email": "", "observacao": "",
            },
        )
        assert resposta.status_code == 200
        assert "Já existe um agente com este CPF" in resposta.content.decode()

    def test_entrada_pela_view(
        self, client, operador_logado, modelo_descartavel, deposito
    ):
        resposta = client.post(
            reverse("iscas:entrada"),
            {
                "modelo": modelo_descartavel.pk,
                "identificadores": "V001\nV002\nV003",
                "tipo_destino": "DEPOSITO",
                "destino_deposito": deposito.pk,
                "nota_fiscal": "NF-77",
                "destino_agente": "", "lote": "", "ocorrido_em": "",
            },
        )
        assert resposta.status_code == 302

        from iscas.models.custodia import Unidade

        assert Unidade.objects.filter(identificador__in=["V001", "V002", "V003"]).count() == 3

    def test_atribuicao_e_entrega_pelas_views(
        self, client, operador_logado, cliente, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 5)], autor=operador
        )

        resposta = client.post(
            reverse("iscas:solicitacao_atribuir", args=[solicitacao.pk]),
            {
                "agente": agente.pk,
                "confirmar": "1",
                f"unidades_{modelo_descartavel.pk}": [
                    u.pk for u in unidades_com_agente[:5]
                ],
            },
        )
        assert resposta.status_code == 302

        atribuicao = solicitacao.atribuicoes.get()
        assert atribuicao.status == StatusAtribuicao.RESERVADA

        client.post(
            reverse("iscas:atribuicao_entregar", args=[atribuicao.pk]),
            {"entregue_em": "", "recebido_por": "Portaria"},
        )
        atribuicao.refresh_from_db()
        solicitacao.refresh_from_db()
        assert atribuicao.status == StatusAtribuicao.ENTREGUE
        assert solicitacao.status == StatusSolicitacao.ENTREGUE

    def test_cancelamento_exige_motivo_na_view(
        self, client, operador_logado, cliente, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        client.post(
            reverse("iscas:atribuicao_cancelar", args=[atribuicao.pk]), {"motivo": ""}
        )
        atribuicao.refresh_from_db()
        assert atribuicao.status == StatusAtribuicao.RESERVADA

    def test_desativar_agente_com_saldo_bloqueado_na_view(
        self, client, operador_logado, agente, unidades_com_agente
    ):
        client.post(reverse("iscas:agente_desativar", args=[agente.pk]))
        agente.refresh_from_db()
        assert agente.is_active

    def test_ajuste_de_pin_pela_view(self, client, operador_logado, agente):
        client.post(
            reverse("iscas:agente_ajustar_pin", args=[agente.pk]),
            {"latitude": "-23.700000", "longitude": "-46.700000"},
        )
        agente.refresh_from_db()
        assert float(agente.latitude) == pytest.approx(-23.7)
        assert agente.geo_origem == "MANUAL"


class TestExtratoECsv:
    def test_extrato_lista_movimentacoes(
        self, client, operador_logado, unidades_no_deposito
    ):
        resposta = client.get(reverse("iscas:extrato"))
        assert resposta.status_code == 200
        assert b"Entrada" in resposta.content

    def test_csv_respeita_filtros(
        self, client, operador_logado, unidades_no_deposito, modelo_descartavel
    ):
        resposta = client.get(
            reverse("iscas:extrato_csv"), {"modelo": modelo_descartavel.pk}
        )
        assert resposta.status_code == 200
        assert resposta["Content-Type"].startswith("text/csv")
        assert "attachment" in resposta["Content-Disposition"]

        conteudo = b"".join(resposta.streaming_content).decode("utf-8-sig")
        linhas = [l for l in conteudo.splitlines() if l.strip()]
        assert linhas[0].startswith("ID;Tipo;")
        assert len(linhas) == 2  # cabeçalho + a movimentação de entrada

    def test_csv_sem_resultado_traz_so_cabecalho(self, client, operador_logado):
        resposta = client.get(reverse("iscas:extrato_csv"))
        conteudo = b"".join(resposta.streaming_content).decode("utf-8-sig")
        assert len([l for l in conteudo.splitlines() if l.strip()]) == 1


class TestMensagemWhatsAppNaView:
    def test_tela_de_mensagem(
        self, client, operador_logado, cliente, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        resposta = client.get(reverse("iscas:atribuicao_mensagem", args=[atribuicao.pk]))
        conteudo = resposta.content.decode()

        assert resposta.status_code == 200
        assert cliente.nome_razao_social in conteudo
        assert "wa.me" in conteudo
