"""Testes da busca por CEP e do pin ajustado no formulário.

O ViaCEP é isolado por mock: teste não depende de rede, e conseguimos
exercitar os casos de erro (CEP inexistente, serviço fora do ar) que na prática
são os que quebram o cadastro.
"""
import json
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, GeoOrigem
from iscas.services import cep as cep_service
from iscas.services.cep import CepIndisponivel, CepInvalido

pytestmark = pytest.mark.django_db


RESPOSTA_VIACEP = {
    "cep": "01310-100",
    "logradouro": "Avenida Paulista",
    "complemento": "de 612 a 1510 - lado par",
    "bairro": "Bela Vista",
    "localidade": "São Paulo",
    "uf": "SP",
}


def _mock_urlopen(payload):
    """Simula a resposta HTTP do ViaCEP."""
    contexto = mock.MagicMock()
    contexto.read.return_value = json.dumps(payload).encode("utf-8")
    resposta = mock.MagicMock()
    resposta.__enter__.return_value = contexto
    return resposta


class TestNormalizacao:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("01310-100", "01310100"),
            ("01310100", "01310100"),
            ("  01310 100 ", "01310100"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_normalizar_cep(self, entrada, esperado):
        assert cep_service.normalizar_cep(entrada) == esperado

    def test_formatar_cep(self):
        assert cep_service.formatar_cep("01310100") == "01310-100"

    def test_formatar_cep_invalido_devolve_original(self):
        assert cep_service.formatar_cep("123") == "123"


class TestBuscarCep:
    def test_devolve_endereco(self):
        with mock.patch(
            "urllib.request.urlopen", return_value=_mock_urlopen(RESPOSTA_VIACEP)
        ):
            endereco = cep_service.buscar_cep("01310-100")

        assert endereco["logradouro"] == "Avenida Paulista"
        assert endereco["bairro"] == "Bela Vista"
        assert endereco["cidade"] == "São Paulo"
        assert endereco["uf"] == "SP"
        assert endereco["cep"] == "01310-100"

    def test_uf_vem_maiuscula(self):
        payload = {**RESPOSTA_VIACEP, "uf": "sp"}
        with mock.patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            assert cep_service.buscar_cep("01310100")["uf"] == "SP"

    def test_campos_ausentes_viram_string_vazia(self):
        """CEP de cidade pequena vem sem logradouro — não pode virar None."""
        payload = {"cep": "12900-000", "localidade": "Bragança", "uf": "SP"}
        with mock.patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            endereco = cep_service.buscar_cep("12900000")

        assert endereco["logradouro"] == ""
        assert endereco["bairro"] == ""
        assert endereco["cidade"] == "Bragança"

    @pytest.mark.parametrize("cep", ["123", "", "0131010", "013101000"])
    def test_cep_com_tamanho_errado(self, cep):
        with pytest.raises(CepInvalido, match="8 dígitos"):
            cep_service.buscar_cep(cep)

    def test_cep_inexistente(self):
        """O ViaCEP devolve {"erro": true} com HTTP 200 — não é exceção de rede."""
        with mock.patch(
            "urllib.request.urlopen", return_value=_mock_urlopen({"erro": True})
        ):
            with pytest.raises(CepInvalido, match="não encontrado"):
                cep_service.buscar_cep("99999999")

    def test_cep_inexistente_com_erro_string(self):
        """A API já devolveu "true" como string; aceitamos as duas formas."""
        with mock.patch(
            "urllib.request.urlopen", return_value=_mock_urlopen({"erro": "true"})
        ):
            with pytest.raises(CepInvalido):
                cep_service.buscar_cep("99999999")

    def test_servico_fora_do_ar(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            with pytest.raises(CepIndisponivel):
                cep_service.buscar_cep("01310100")

    def test_resposta_ilegivel(self):
        contexto = mock.MagicMock()
        contexto.read.return_value = b"<html>nao sou json</html>"
        resposta = mock.MagicMock()
        resposta.__enter__.return_value = contexto
        with mock.patch("urllib.request.urlopen", return_value=resposta):
            with pytest.raises(CepIndisponivel):
                cep_service.buscar_cep("01310100")


@pytest.fixture
def operador_logado(client, operador, db):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


class TestEndpointCep:
    def test_devolve_endereco(self, client, operador_logado):
        with mock.patch(
            "urllib.request.urlopen", return_value=_mock_urlopen(RESPOSTA_VIACEP)
        ):
            resposta = client.get(reverse("iscas:api_cep"), {"cep": "01310-100"})

        dados = json.loads(resposta.content)
        assert dados["ok"] is True
        assert dados["endereco"]["logradouro"] == "Avenida Paulista"

    def test_cep_invalido_responde_200_com_erro(self, client, operador_logado):
        """Erro de CEP não é erro de servidor: a tela mostra a mensagem."""
        resposta = client.get(reverse("iscas:api_cep"), {"cep": "123"})
        dados = json.loads(resposta.content)

        assert resposta.status_code == 200
        assert dados["ok"] is False
        assert "8 dígitos" in dados["erro"]

    def test_servico_indisponivel_responde_200_com_erro(self, client, operador_logado):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            resposta = client.get(reverse("iscas:api_cep"), {"cep": "01310100"})

        assert resposta.status_code == 200
        assert json.loads(resposta.content)["ok"] is False

    def test_exige_operador(self, client):
        resposta = client.get(reverse("iscas:api_cep"), {"cep": "01310100"})
        assert resposta.status_code == 302


class TestEndpointGeocodificar:
    def test_devolve_coordenada(self, client, operador_logado):
        from decimal import Decimal

        with mock.patch(
            "iscas.services.geo.geocodificar",
            return_value=(Decimal("-23.561414"), Decimal("-46.655881")),
        ):
            resposta = client.get(
                reverse("iscas:api_geocodificar"), {"endereco": "Av. Paulista, 1000"}
            )

        dados = json.loads(resposta.content)
        assert dados["ok"] is True
        assert dados["latitude"] == pytest.approx(-23.561414)

    def test_endereco_vazio(self, client, operador_logado):
        resposta = client.get(reverse("iscas:api_geocodificar"), {"endereco": "  "})
        assert json.loads(resposta.content)["ok"] is False

    def test_falha_de_geocodificacao_responde_erro_tratado(
        self, client, operador_logado
    ):
        """Nominatim fora do ar não pode derrubar o cadastro."""
        resposta = client.get(
            reverse("iscas:api_geocodificar"), {"endereco": "Rua Inexistente 999"}
        )
        dados = json.loads(resposta.content)
        assert resposta.status_code == 200
        assert dados["ok"] is False


class TestPinNoFormulario:
    """ISC-RF-03: a posição ajustada no cadastro é salva e vence a automática."""

    def _dados_agente(self, **extra):
        base = {
            "nome": "Agente Pin", "cpf": "39053344705", "telefone": "11999998888",
            "logradouro": "Avenida Paulista", "numero": "1000", "complemento": "",
            "bairro": "Bela Vista", "cidade": "São Paulo", "uf": "SP",
            "cep": "01310-100", "email": "", "observacao": "",
            "latitude_ajustada": "", "longitude_ajustada": "", "pin_movido": "",
        }
        base.update(extra)
        return base

    def test_pin_arrastado_e_salvo_como_manual(self, client, operador_logado):
        from iscas.models.cadastro import Agente

        client.post(
            reverse("iscas:agente_criar"),
            self._dados_agente(
                latitude_ajustada="-23.561414",
                longitude_ajustada="-46.655881",
                pin_movido="1",
            ),
        )
        agente = Agente.objects.get(nome="Agente Pin")

        assert float(agente.latitude) == pytest.approx(-23.561414)
        assert float(agente.longitude) == pytest.approx(-46.655881)
        assert agente.geo_origem == GeoOrigem.MANUAL

    def test_previa_sem_arrasto_nao_marca_manual(self, client, operador_logado):
        """A prévia do mapa preenche os campos, mas não congela a coordenada.

        Se contasse como MANUAL, a geocodificação nunca mais atualizaria o pin
        quando o endereço mudasse.
        """
        from iscas.models.cadastro import Agente

        client.post(
            reverse("iscas:agente_criar"),
            self._dados_agente(
                latitude_ajustada="-23.561414",
                longitude_ajustada="-46.655881",
                pin_movido="",
            ),
        )
        agente = Agente.objects.get(nome="Agente Pin")
        # Nominatim está desligado em teste: sem pin manual, fica pendente.
        assert agente.geo_origem == GeoOrigem.PENDENTE

    def test_edicao_com_pin_ajustado(self, client, operador_logado, agente):
        client.post(
            reverse("iscas:agente_editar", args=[agente.pk]),
            self._dados_agente(
                nome=agente.nome,
                cpf=agente.cpf,
                latitude_ajustada="-23.600000",
                longitude_ajustada="-46.700000",
                pin_movido="1",
            ),
        )
        agente.refresh_from_db()

        assert float(agente.latitude) == pytest.approx(-23.6)
        assert agente.geo_origem == GeoOrigem.MANUAL

    def test_cliente_tambem_aceita_pin(self, client, operador_logado):
        from iscas.models.cadastro import Cliente

        client.post(
            reverse("iscas:cliente_criar"),
            {
                "nome_razao_social": "Cliente Pin", "documento": "11222333000181",
                "tipo_documento": "CNPJ", "contato_nome": "Ana",
                "telefone": "1133334444", "email": "",
                "logradouro": "Av. Faria Lima", "numero": "2000", "complemento": "",
                "bairro": "Itaim", "cidade": "São Paulo", "uf": "SP",
                "cep": "01452-000", "observacao": "",
                "latitude_ajustada": "-23.577000",
                "longitude_ajustada": "-46.687000",
                "pin_movido": "1",
            },
        )
        cliente = Cliente.objects.get(nome_razao_social="Cliente Pin")

        assert float(cliente.latitude) == pytest.approx(-23.577)
        assert cliente.geo_origem == GeoOrigem.MANUAL


class TestEnderecoParaGeocodificacao:
    """O endereço mandado ao Nominatim omite CEP e complemento.

    Não é preferência de estilo: verificado contra o serviço real, incluir
    "CEP 01310-100" faz a busca voltar VAZIA até para a Avenida Paulista.
    O complemento ("de 612 a 1510 - lado par") é ruído pelo mesmo motivo.
    """

    def test_omite_cep_e_complemento(self, agente):
        agente.logradouro = "Avenida Paulista"
        agente.numero = "1000"
        agente.complemento = "de 612 a 1510 - lado par"
        agente.bairro = "Bela Vista"
        agente.cidade = "São Paulo"
        agente.uf = "SP"
        agente.cep = "01310-100"

        endereco = agente.endereco_para_geocodificacao

        assert "CEP" not in endereco
        assert "01310" not in endereco
        assert "lado par" not in endereco

    def test_mantem_o_numero(self, agente):
        """Sem o número o pin cai no centroide da rua, não na porta."""
        agente.logradouro = "Avenida Paulista"
        agente.numero = "1000"
        agente.cidade = "São Paulo"
        agente.uf = "SP"

        assert "1000" in agente.endereco_para_geocodificacao

    def test_exibicao_continua_com_cep(self, agente):
        """`endereco_completo` é para o operador ler — mantém tudo."""
        agente.cep = "01310-100"
        agente.logradouro = "Avenida Paulista"
        agente.cidade = "São Paulo"
        agente.uf = "SP"

        assert "01310-100" in agente.endereco_completo

    def test_geocodificacao_usa_a_versao_enxuta(self, agente):
        """Guarda contra alguém voltar a mandar o `endereco_completo`."""
        from iscas.services.geo import geocodificar_entidade

        agente.cep = "01310-100"
        agente.complemento = "lado par"

        with mock.patch("iscas.services.geo.geocodificar") as geo:
            geo.side_effect = Exception("interrompe após capturar o argumento")
            try:
                geocodificar_entidade(agente)
            except Exception:
                pass

        enviado = geo.call_args[0][0]
        assert "CEP" not in enviado
        assert "lado par" not in enviado


class TestFormularioRenderiza:
    def test_form_de_agente_tem_cep_e_mapa(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:agente_criar")).content.decode()

        assert "mapaEndereco" in conteudo
        assert "api/cep/" in conteudo
        assert "id_pin_movido" in conteudo

    def test_form_de_cliente_tem_cep_e_mapa(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:cliente_criar")).content.decode()

        assert "mapaEndereco" in conteudo
        assert "api/cep/" in conteudo

    def test_edicao_centraliza_no_pin_salvo(self, client, operador_logado, agente):
        conteudo = client.get(
            reverse("iscas:agente_editar", args=[agente.pk])
        ).content.decode()

        assert str(float(agente.latitude)) in conteudo
