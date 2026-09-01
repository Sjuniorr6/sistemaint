"""Testes de geolocalização (ISC-ADR-09, ISC-RN-11, ISC-RN-12).

O teste do bounding box é o mais importante do arquivo: falso negativo ali
significa agente com saldo real sumindo da busca — estoque invisível.
"""
import math

import pytest

from iscas.enums import GeoOrigem
from iscas.models.cadastro import Agente
from iscas.services import geo as geo_service

pytestmark = pytest.mark.django_db


# Coordenadas de referência, com distâncias documentadas.
SE_SP = (-23.550520, -46.633308)          # Praça da Sé, São Paulo
CENTRO_RJ = (-22.906847, -43.172896)      # Centro, Rio de Janeiro
#: Sé ↔ Centro RJ em grande círculo (esfera de raio 6371 km) ≈ 360,7 km.
#: Conferido com cálculo independente em Python puro.
SP_RJ_KM = 360.7


def _criar_agente(nome, cpf, lat, lng):
    agente = Agente(
        nome=nome,
        telefone="11999990000",
        logradouro="Rua X",
        cidade="São Paulo",
        uf="SP",
        latitude=str(lat),
        longitude=str(lng),
    )
    agente.cpf = cpf
    agente.save()
    return agente


#: CPFs válidos distintos, para os testes que criam vários agentes.
CPFS = [
    "39053344705", "11144477735", "12345678909", "52998224725",
    "15350946056", "48151623733", "01234567890", "71428650417",
    "35524001803", "24971563792",
]


class TestHaversine:
    """Distância contra pares conhecidos, tolerância de 1%."""

    def test_distancia_sp_rj(self):
        _criar_agente("RJ", CPFS[0], *CENTRO_RJ)
        resultado = geo_service.agentes_proximos(
            latitude=SE_SP[0], longitude=SE_SP[1], raio_km=500
        )
        assert len(resultado) == 1
        distancia = resultado[0]["distancia_km"]
        assert abs(distancia - SP_RJ_KM) / SP_RJ_KM < 0.01

    def test_ponto_identico_nao_estoura_acos(self):
        """O clamp em [-1,1]: sem ele, `acos` estoura com domain error."""
        _criar_agente("Mesmo ponto", CPFS[1], *SE_SP)
        resultado = geo_service.agentes_proximos(
            latitude=SE_SP[0], longitude=SE_SP[1], raio_km=10
        )
        assert len(resultado) == 1
        assert resultado[0]["distancia_km"] == pytest.approx(0, abs=0.01)


class TestBoundingBox:
    """O erro grave da geolocalização: candidato dentro do raio que some."""

    @pytest.mark.parametrize(
        "rumo_graus",
        [0, 45, 90, 135, 180, 225, 270, 315],
        ids=["N", "NE", "L", "SE", "S", "SO", "O", "NO"],
    )
    def test_agente_a_099_do_raio_aparece_em_todas_as_direcoes(self, rumo_graus):
        """Agente a 0,99×raio em oito direções TEM que aparecer (ISC-RN-12)."""
        raio_km = 50.0
        distancia = raio_km * 0.99
        lat0, lng0 = SE_SP

        # Projeta o ponto a `distancia` no rumo dado.
        lat_rad = math.radians(lat0)
        rumo_rad = math.radians(rumo_graus)
        delta_lat = (distancia * math.cos(rumo_rad)) / geo_service.KM_POR_GRAU_LAT
        delta_lng = (distancia * math.sin(rumo_rad)) / (
            geo_service.KM_POR_GRAU_LAT * math.cos(lat_rad)
        )
        _criar_agente(f"Agente {rumo_graus}", CPFS[0], lat0 + delta_lat, lng0 + delta_lng)

        resultado = geo_service.agentes_proximos(
            latitude=lat0, longitude=lng0, raio_km=raio_km
        )
        assert len(resultado) == 1, (
            f"Agente a {distancia:.1f}km no rumo {rumo_graus}° sumiu da busca "
            f"— bounding box produziu falso negativo."
        )

    def test_agente_fora_do_raio_e_descartado(self):
        _criar_agente("Longe", CPFS[0], *CENTRO_RJ)
        resultado = geo_service.agentes_proximos(
            latitude=SE_SP[0], longitude=SE_SP[1], raio_km=50
        )
        assert resultado == []

    def test_caixa_nao_estoura_perto_dos_polos(self):
        """cos(latitude) → 0 faria o delta de longitude explodir."""
        lat_min, lat_max, lng_min, lng_max = geo_service.bounding_box(89.9, 0, 50)
        assert lng_max - lng_min <= 360.0
        assert math.isfinite(lng_min) and math.isfinite(lng_max)


class TestBuscaProximidade:
    def test_ordena_por_distancia_crescente(self):
        """ISC-RN-11: o resultado ordena candidatos, do mais perto ao mais longe."""
        lat0, lng0 = SE_SP
        _criar_agente("Longe", CPFS[0], lat0 + 0.30, lng0)
        _criar_agente("Perto", CPFS[1], lat0 + 0.01, lng0)
        _criar_agente("Medio", CPFS[2], lat0 + 0.10, lng0)

        resultado = geo_service.agentes_proximos(
            latitude=lat0, longitude=lng0, raio_km=100
        )
        nomes = [r["agente"].nome for r in resultado]
        assert nomes == ["Perto", "Medio", "Longe"]

    def test_agente_sem_coordenada_nao_aparece(self, agente_sem_coordenada):
        """ISC-RN-12: sem coordenada, fora da busca."""
        resultado = geo_service.agentes_proximos(
            latitude=SE_SP[0], longitude=SE_SP[1], raio_km=500
        )
        assert agente_sem_coordenada.pk not in {r["agente"].pk for r in resultado}

    def test_agente_sem_coordenada_aparece_na_listagem_separada(
        self, agente_sem_coordenada
    ):
        """ISC-RF-21: omitir em silêncio criaria estoque invisível."""
        assert agente_sem_coordenada.pk in {
            a.pk for a in geo_service.agentes_sem_coordenada()
        }

    def test_filtra_por_saldo_minimo(
        self, agente, unidades_com_agente, modelo_descartavel
    ):
        """ISC-RF-18: quem não tem o mínimo não interessa ao operador."""
        lat, lng = float(agente.latitude), float(agente.longitude)

        com_saldo = geo_service.agentes_proximos(
            latitude=lat, longitude=lng, raio_km=10,
            modelo=modelo_descartavel, quantidade_minima=5,
        )
        assert len(com_saldo) == 1
        assert com_saldo[0]["disponivel"] == 8

        exigente = geo_service.agentes_proximos(
            latitude=lat, longitude=lng, raio_km=10,
            modelo=modelo_descartavel, quantidade_minima=20,
        )
        assert exigente == []

    def test_saldo_reflete_reserva(
        self, agente, unidades_com_agente, modelo_descartavel, cliente, operador
    ):
        """O disponível exibido no mapa desconta reservas (ISC-RN-07)."""
        from django.utils import timezone

        from iscas.models.operacao import Atribuicao, Solicitacao
        from iscas.services import reserva as reserva_service

        solicitacao = Solicitacao.objects.create(
            cliente=cliente, aberta_em=timezone.now(), aberta_por=operador
        )
        atribuicao = Atribuicao.objects.create(
            solicitacao=solicitacao, agente=agente, criada_por=operador
        )
        reserva_service.alocar_unidades(
            agente=agente, modelo=modelo_descartavel, quantidade=3,
            atribuicao=atribuicao,
        )

        resultado = geo_service.agentes_proximos(
            latitude=float(agente.latitude), longitude=float(agente.longitude),
            raio_km=10, modelo=modelo_descartavel,
        )
        assert resultado[0]["disponivel"] == 5


class TestAjustePin:
    """ISC-RF-03: a correção manual do operador não pode ser desfeita."""

    def test_ajuste_marca_origem_manual(self, agente):
        geo_service.ajustar_pin(agente, latitude=-23.6, longitude=-46.7)
        agente.refresh_from_db()
        assert agente.geo_origem == GeoOrigem.MANUAL
        assert float(agente.latitude) == pytest.approx(-23.6)

    def test_geocodificacao_nao_sobrescreve_pin_manual(self, agente):
        geo_service.ajustar_pin(agente, latitude=-23.6, longitude=-46.7)
        # O Nominatim está desligado nos testes; se tentasse chamar, falharia.
        alterou = geo_service.geocodificar_entidade(agente)
        agente.refresh_from_db()
        assert alterou is False
        assert agente.geo_origem == GeoOrigem.MANUAL
        assert float(agente.latitude) == pytest.approx(-23.6)

    def test_falha_de_geocodificacao_marca_pendente_sem_quebrar(
        self, agente_sem_coordenada
    ):
        """ISC-RF-02: falha não impede o cadastro."""
        alterou = geo_service.geocodificar_entidade(agente_sem_coordenada)
        agente_sem_coordenada.refresh_from_db()
        assert alterou is False
        assert agente_sem_coordenada.geo_origem == GeoOrigem.PENDENTE
        assert agente_sem_coordenada.pk is not None
