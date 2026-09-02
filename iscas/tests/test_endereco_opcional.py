"""Endereço de cliente opcional, entrega com coordenada própria e busca reversa.

O que estes testes protegem, e por que cada um existe, está na mensagem do
commit. Aqui ficam só as asserções.
"""
import json
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group

from iscas.enums import GRUPO_OPERADORES, GeoOrigem
from iscas.forms.cadastro import AgenteForm, ClienteForm, DepositoForm
from iscas.models.cadastro import Cliente
from iscas.services import geo as geo_service
from iscas.services import solicitacao as solicitacao_service
from iscas.services.exceptions import GeocodificacaoFalhou

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


# ---------------------------------------------------------------------------
# Endereço do cliente é opcional; do agente e do depósito, não
# ---------------------------------------------------------------------------


def test_cliente_salva_sem_nenhum_campo_de_endereco():
    form = ClienteForm(
        data={
            "nome_razao_social": "Cliente Sem Endereço LTDA",
            "tipo_documento": "CNPJ",
            "documento": "11222333000181",
            "telefone": "1133334444",
        }
    )
    assert form.is_valid(), form.errors

    cliente = form.save()
    assert cliente.pk
    assert cliente.logradouro == ""
    assert cliente.tem_endereco is False
    # Endereço vazio não pode virar linha suja ("" - "", "CEP ") na tela nem
    # no texto de WhatsApp.
    assert cliente.endereco_completo == ""


@pytest.mark.parametrize(
    "classe_form, dados_base",
    [
        (
            AgenteForm,
            {"nome": "Agente Sem Rua", "cpf": "39053344705", "telefone": "11999990000"},
        ),
        (DepositoForm, {"nome": "Depósito Sem Rua"}),
    ],
)
def test_agente_e_deposito_continuam_exigindo_endereco(classe_form, dados_base):
    """Sem endereço eles saem da busca por proximidade — que é a razão de existirem."""
    form = classe_form(data=dados_base)

    assert not form.is_valid()
    assert {"logradouro", "cidade", "uf"} <= set(form.errors)


# ---------------------------------------------------------------------------
# Geocodificação reversa
# ---------------------------------------------------------------------------


#: Resposta do Nominatim `/reverse` para a Praça da Sé, com os nomes de chave
#: que o serviço real usa.
_RESPOSTA_REVERSA = {
    "display_name": "Praça da Sé, Sé, São Paulo, SP, Brasil",
    "address": {
        "road": "Praça da Sé",
        "house_number": "100",
        "suburb": "Sé",
        "city": "São Paulo",
        "ISO3166-2-lvl4": "BR-SP",
        "postcode": "01001-000",
    },
}


def test_reverso_converte_coordenada_em_endereco_estruturado():
    with patch("iscas.services.geo.urllib.request.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            _RESPOSTA_REVERSA
        ).encode()

        endereco = geo_service.geocodificar_reverso("-23.550520", "-46.633308")

    assert endereco["logradouro"] == "Praça da Sé"
    assert endereco["numero"] == "100"
    assert endereco["bairro"] == "Sé"
    assert endereco["cidade"] == "São Paulo"
    # A sigla, não "São Paulo" por extenso: é o que o campo UF do cadastro guarda.
    assert endereco["uf"] == "SP"
    assert endereco["cep"] == "01001-000"
    assert endereco["latitude"] == Decimal("-23.550520")


@pytest.mark.parametrize(
    "latitude, longitude",
    [
        ("", "-46.633308"),          # campo vazio
        ("abc", "-46.633308"),       # texto
        ("-91.0", "-46.633308"),     # fora do intervalo geográfico
        ("-23.550520", "181.0"),
    ],
)
def test_reverso_recusa_coordenada_invalida_sem_chamar_o_provedor(latitude, longitude):
    """A guarda é local: coordenada inválida não gasta chamada de rede."""
    with patch("iscas.services.geo.urllib.request.urlopen") as urlopen:
        with pytest.raises(GeocodificacaoFalhou):
            geo_service.geocodificar_reverso(latitude, longitude)

    urlopen.assert_not_called()


def test_api_reverso_devolve_erro_como_200_e_nao_500(client, operador_logado):
    """Erro do provedor não é erro de servidor — a tela mostra e o operador digita à mão."""
    with patch(
        "iscas.services.geo.geocodificar_reverso",
        side_effect=GeocodificacaoFalhou("Nenhum endereço conhecido nesta coordenada."),
    ):
        resposta = client.get(
            "/iscas/api/geocodificar-reverso/",
            {"latitude": "-23.550520", "longitude": "-46.633308"},
        )

    assert resposta.status_code == 200
    assert resposta.json()["ok"] is False


# ---------------------------------------------------------------------------
# A busca por proximidade mede do PONTO DE ENTREGA
# ---------------------------------------------------------------------------


def test_busca_mede_da_entrega_e_nao_do_cadastro_do_cliente(
    cliente, modelo_descartavel, operador
):
    """A entrega no Rio não pode medir distância a partir da sede em São Paulo."""
    solicitacao = solicitacao_service.abrir_solicitacao(
        cliente=cliente,
        itens=[(modelo_descartavel, 1)],
        autor=operador,
        entrega_logradouro="Rua da Obra",
        entrega_cidade="Rio de Janeiro",
        entrega_uf="RJ",
    )
    # Pin no Centro do Rio; o cadastro do cliente está em São Paulo.
    solicitacao_service.resolver_coordenada_de_entrega(
        solicitacao, pin=("-22.906847", "-43.172896")
    )

    assert solicitacao.entrega_geo_origem == GeoOrigem.MANUAL
    latitude, longitude = solicitacao.coordenada_de_busca
    assert (latitude, longitude) == (Decimal("-22.906847"), Decimal("-43.172896"))
    # O cadastro do cliente segue intocado — a entrega não o sobrescreve.
    cliente.refresh_from_db()
    assert cliente.latitude == Decimal("-23.560000")


def test_solicitacao_de_cliente_sem_endereco_entra_na_busca(
    modelo_descartavel, operador
):
    """O caso que motivou a mudança: cliente sem endereço, entrega com coordenada."""
    cliente = Cliente.objects.create(nome_razao_social="Cliente Sem Endereço LTDA")
    assert cliente.tem_coordenada is False

    solicitacao = solicitacao_service.abrir_solicitacao(
        cliente=cliente,
        itens=[(modelo_descartavel, 1)],
        autor=operador,
        entrega_logradouro="Av. Paulista",
        entrega_numero="1000",
        entrega_cidade="São Paulo",
        entrega_uf="SP",
    )
    solicitacao_service.resolver_coordenada_de_entrega(
        solicitacao, pin=("-23.561414", "-46.655881")
    )

    assert solicitacao.tem_coordenada_de_busca
    # Sem endereço no cadastro não há divergência a sinalizar.
    assert solicitacao.entrega_em_outro_endereco is False


def test_solicitacao_antiga_sem_coordenada_de_entrega_cai_no_cadastro(
    cliente, modelo_descartavel, operador
):
    """Fallback dos pedidos abertos antes de a entrega ter coordenada própria."""
    solicitacao = solicitacao_service.abrir_solicitacao(
        cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador
    )
    assert solicitacao.entrega_latitude is None

    assert solicitacao.coordenada_de_busca == (cliente.latitude, cliente.longitude)
