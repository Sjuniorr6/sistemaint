"""Solicitações em aberto no mapa.

O mapa mostrava só a oferta (agentes com saldo); estes testes cobrem a camada
de demanda — onde estão os pedidos que ainda precisam de atendimento.
"""
import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, StatusSolicitacao
from iscas.services import solicitacao as solicitacao_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


@pytest.fixture
def solicitacao_aberta(cliente, modelo_descartavel, operador):
    return solicitacao_service.abrir_solicitacao(
        cliente=cliente,
        itens=[(modelo_descartavel, 10)],
        autor=operador,
        observacao="Entregar pela manhã",
    )


def _geojson(client):
    return json.loads(client.get(reverse("iscas:api_solicitacoes")).content)


class TestFormatoGeoJSON:
    def test_estrutura(self, client, operador_logado, solicitacao_aberta):
        dados = _geojson(client)

        assert dados["type"] == "FeatureCollection"
        assert len(dados["features"]) == 1

        feature = dados["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"

    def test_coordenadas_na_ordem_geojson(
        self, client, operador_logado, solicitacao_aberta, cliente
    ):
        """[longitude, latitude] — trocar põe o pin do outro lado do mundo."""
        lng, lat = _geojson(client)["features"][0]["geometry"]["coordinates"]

        assert lng == pytest.approx(float(cliente.longitude))
        assert lat == pytest.approx(float(cliente.latitude))

    def test_propriedades_do_popup(
        self, client, operador_logado, solicitacao_aberta, cliente
    ):
        propriedades = _geojson(client)["features"][0]["properties"]

        assert propriedades["id"] == solicitacao_aberta.pk
        assert propriedades["cliente"] == cliente.nome_razao_social
        assert propriedades["cliente_id"] == cliente.pk
        assert propriedades["status"] == StatusSolicitacao.ABERTA
        assert propriedades["observacao"] == "Entregar pela manhã"
        assert cliente.cidade in propriedades["endereco"]

    def test_itens_com_cobertura(
        self, client, operador_logado, solicitacao_aberta, modelo_descartavel
    ):
        item = _geojson(client)["features"][0]["properties"]["itens"][0]

        assert item["modelo"] == modelo_descartavel.nome
        assert item["solicitado"] == 10
        assert item["atribuido"] == 0
        assert item["falta"] == 10


class TestQuaisSolicitacoesAparecem:
    def test_aberta_aparece(self, client, operador_logado, solicitacao_aberta):
        assert len(_geojson(client)["features"]) == 1

    def test_atribuida_aparece(
        self, client, operador_logado, solicitacao_aberta, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        """Cobertura parcial ainda é trabalho pendente."""
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        propriedades = _geojson(client)["features"][0]["properties"]

        assert propriedades["status"] == StatusSolicitacao.ATRIBUIDA
        assert propriedades["falta_total"] == 5
        assert propriedades["descoberta"] is True
        assert agente.nome in propriedades["agentes"]

    def test_entregue_nao_aparece(
        self, client, operador_logado, cliente, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        """Solicitação encerrada não é pendência."""
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 5)], autor=operador
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        solicitacao_service.confirmar_entrega(atribuicao=atribuicao, autor=operador)

        assert _geojson(client)["features"] == []

    def test_cancelada_nao_aparece(
        self, client, operador_logado, solicitacao_aberta, operador
    ):
        solicitacao_service.cancelar_solicitacao(
            solicitacao=solicitacao_aberta, motivo="desistiu", autor=operador
        )
        assert _geojson(client)["features"] == []

    def test_em_rota_aparece(
        self, client, operador_logado, solicitacao_aberta, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_aberta, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        solicitacao_service.marcar_em_rota(atribuicao=atribuicao, autor=operador)

        propriedades = _geojson(client)["features"][0]["properties"]
        assert propriedades["status"] == StatusSolicitacao.EM_ROTA


class TestCoberturaDefineACor:
    """`descoberta` decide o marcador vermelho (ação) ou âmbar (aguardando)."""

    def test_sem_atribuicao_e_descoberta(
        self, client, operador_logado, solicitacao_aberta
    ):
        propriedades = _geojson(client)["features"][0]["properties"]
        assert propriedades["descoberta"] is True
        assert propriedades["falta_total"] == 10

    def test_cobertura_total_nao_e_descoberta(
        self, client, operador_logado, cliente, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 5)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        propriedades = _geojson(client)["features"][0]["properties"]

        assert propriedades["descoberta"] is False
        assert propriedades["falta_total"] == 0


class TestListaSoMostraOQuePrecisaDeAgente:
    """A lista lateral é worklist; o mapa continua mostrando tudo.

    Solicitação totalmente atribuída não exige ação nenhuma do operador — ela
    aguarda rota e entrega. Misturada às descobertas, ela disputa atenção com
    o que de fato precisa de agente. O marcador âmbar permanece: a entrega
    ainda está acontecendo, e sumir do mapa esconderia onde ela está.
    """

    def test_o_endpoint_continua_entregando_as_cobertas(
        self, client, operador_logado, cliente, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        """O filtro é da lista, não do mapa — o marcador âmbar depende disto."""
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 5)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        features = _geojson(client)["features"]

        assert len(features) == 1
        assert features[0]["properties"]["falta_total"] == 0

    def test_a_tela_separa_a_lista_dos_marcadores(self, client, operador_logado):
        """A lista itera `descobertas`; o switch do mapa conta `solicitacoes`.

        O filtro roda no navegador, então o que dá para afirmar daqui é a
        ligação: se a lista voltar a iterar a coleção completa, as cobertas
        reaparecem — que é exatamente o defeito corrigido.
        """
        # sabotagem: trocar `s in descobertas` por `s in solicitacoes` → vermelho
        conteudo = client.get(reverse("iscas:mapa")).content.decode()

        assert 'x-for="s in descobertas"' in conteudo
        assert "get descobertas()" in conteudo


class TestClienteSemCoordenada:
    """ISC-RN-12 aplicado à demanda: ausência sinalizada, não silenciosa."""

    def test_nao_entra_no_geojson_mas_e_contado(
        self, client, operador_logado, modelo_descartavel, operador
    ):
        from iscas.models.cadastro import Cliente

        sem_geo = Cliente.objects.create(
            nome_razao_social="Cliente Sem Pin",
            logradouro="Rua X", cidade="São Paulo", uf="SP",
        )
        solicitacao_service.abrir_solicitacao(
            cliente=sem_geo, itens=[(modelo_descartavel, 3)], autor=operador
        )
        dados = _geojson(client)

        assert dados["features"] == []
        assert dados["sem_coordenada"] == 1


class TestPermissao:
    def test_anonimo_vai_para_login(self, client):
        resposta = client.get(reverse("iscas:api_solicitacoes"))
        assert resposta.status_code == 302

    def test_operador_acessa(self, client, operador_logado):
        assert client.get(reverse("iscas:api_solicitacoes")).status_code == 200


class TestTelaDoMapa:
    def test_mapa_carrega_a_camada(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:mapa")).content.decode()

        assert "api/solicitacoes.geojson" in conteudo
        assert "carregarSolicitacoes" in conteudo
        assert "mostrarSolicitacoes" in conteudo

    def test_javascript_do_mapa_e_valido(self, client, operador_logado):
        """Guarda contra o SyntaxError que já derrubou este script antes."""
        import os
        import re
        import shutil
        import subprocess
        import tempfile

        node = shutil.which("node")
        if not node:
            pytest.skip("node não disponível")

        html = client.get(reverse("iscas:mapa")).content.decode()
        codigo = "\n".join(
            b for b in re.findall(r"<script[^>]*>(.*?)</script>", html, re.S) if b.strip()
        )

        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as arquivo:
            arquivo.write(codigo)
            caminho = arquivo.name
        try:
            resultado = subprocess.run(
                [node, "--check", caminho], capture_output=True, text=True
            )
            assert resultado.returncode == 0, resultado.stderr[:600]
        finally:
            os.unlink(caminho)


class TestDesempenho:
    """O custo do endpoint não pode crescer com o número de solicitações."""

    def _criar(self, cliente, modelo, operador, quantas):
        for _ in range(quantas):
            solicitacao_service.abrir_solicitacao(
                cliente=cliente, itens=[(modelo, 5)], autor=operador
            )

    def test_custo_constante(
        self, client, operador_logado, cliente, modelo_descartavel, operador,
        django_assert_max_num_queries,
    ):
        """N+1 aqui degradaria o mapa conforme a operação cresce.

        A primeira versão gastava ~3 consultas por solicitação (52 para 16);
        `cobertura_em_lote` derrubou para um número fixo.
        """
        self._criar(cliente, modelo_descartavel, operador, 16)

        with django_assert_max_num_queries(8):
            dados = _geojson(client)

        assert len(dados["features"]) == 16

    def test_dobrar_o_volume_nao_dobra_o_custo(
        self, client, operador_logado, cliente, modelo_descartavel, operador,
        django_assert_max_num_queries,
    ):
        """A garantia de verdade: mesmo teto com o dobro de solicitações."""
        self._criar(cliente, modelo_descartavel, operador, 32)

        with django_assert_max_num_queries(8):
            assert len(_geojson(client)["features"]) == 32


class TestCoberturaEmLote:
    """A versão agregada precisa concordar com a original, item a item."""

    def test_concorda_com_a_versao_individual(
        self, cliente, agente, unidades_com_agente, modelo_descartavel,
        modelo_retornavel, retornaveis_com_agente, operador,
    ):
        from iscas.services.solicitacao import cobertura, cobertura_em_lote

        primeira = solicitacao_service.abrir_solicitacao(
            cliente=cliente,
            itens=[(modelo_descartavel, 10), (modelo_retornavel, 4)],
            autor=operador,
        )
        segunda = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=primeira, agente=agente,
            itens=[(modelo_descartavel, 6), (modelo_retornavel, 4)], autor=operador,
        )

        lote = cobertura_em_lote([primeira, segunda])

        for solicitacao in (primeira, segunda):
            individual = {
                linha["modelo"].pk: (linha["solicitado"], linha["atribuido"], linha["falta"])
                for linha in cobertura(solicitacao)
            }
            agregado = {
                linha["modelo"].pk: (linha["solicitado"], linha["atribuido"], linha["falta"])
                for linha in lote[solicitacao.pk]
            }
            assert agregado == individual, f"divergência na solicitação #{solicitacao.pk}"

    def test_conta_entregues(
        self, cliente, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """Unidade entregue continua contando como atendida."""
        from iscas.services.solicitacao import cobertura_em_lote

        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 5)], autor=operador
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        solicitacao_service.confirmar_entrega(atribuicao=atribuicao, autor=operador)

        linha = cobertura_em_lote([solicitacao])[solicitacao.pk][0]
        assert linha["atribuido"] == 5
        assert linha["falta"] == 0

    def test_ignora_atribuicao_cancelada(
        self, cliente, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """Reserva liberada não cobre nada."""
        from iscas.services.solicitacao import cobertura_em_lote

        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 5)], autor=operador
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        solicitacao_service.cancelar_atribuicao(
            atribuicao=atribuicao, motivo="desistiu", autor=operador
        )

        linha = cobertura_em_lote([solicitacao])[solicitacao.pk][0]
        assert linha["atribuido"] == 0
        assert linha["falta"] == 5

    def test_lista_vazia(self):
        from iscas.services.solicitacao import cobertura_em_lote

        assert cobertura_em_lote([]) == {}
