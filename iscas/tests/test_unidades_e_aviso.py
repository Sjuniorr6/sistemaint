"""Lista de unidades por custódia e pop-up de solicitações pendentes."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from iscas.enums import TipoMovimentacao
from iscas.services import custodia as custodia_service
from iscas.services import entrada as entrada_service
from iscas.services import solicitacao as solicitacao_service
from iscas.tests.conftest import _criar_agente

pytestmark = pytest.mark.django_db


def _titulos(resposta):
    return [secao["titulo"] for secao in resposta.context["secoes"]]


def test_agrupa_por_custodia_e_esconde_consumidas(
    client, operador_logado, agente, cliente, operador, unidades_com_agente,
):
    custodia_service.registrar_movimentacao(
        tipo=TipoMovimentacao.ENTREGA, origem=agente, destino=cliente,
        unidades=unidades_com_agente[:2], autor=operador,
    )
    url = reverse("iscas:unidade_lista")

    padrao = client.get(url)
    [grupo] = padrao.context["secoes"][0]["grupos"]
    assert _titulos(padrao) == ["Agentes"]
    assert (grupo["nome"], grupo["total"]) == (agente.nome, 6)
    assert _titulos(client.get(url, {"encerradas": "1"})) == ["Agentes", "Clientes"]


# sabotagem: tirar o select_related das custódias em unidades_por_custodia → vermelho
def test_contagem_de_consultas_nao_cresce_com_os_agentes(
    client, operador_logado, operador, modelo_descartavel,
):
    def carregar_agentes(n, inicio):
        for i in range(n):
            novo = _criar_agente(f"Agente {inicio + i}", f"{inicio + i:011d}", "-23.5", "-46.6")
            entrada_service.registrar_entrada(
                modelo=modelo_descartavel, identificadores=[f"X{inicio + i}"],
                destino=novo, autor=operador,
            )

    def contar():
        with CaptureQueriesContext(connection) as consultas:
            client.get(reverse("iscas:unidade_lista"))
        return len(consultas)

    carregar_agentes(1, 100)
    com_um = contar()
    carregar_agentes(4, 200)

    assert contar() == com_um


def test_grupo_aberto_traz_so_as_iscas_daquela_custodia(
    client, operador_logado, agente, agente2, operador, modelo_descartavel,
    unidades_com_agente,
):
    entrada_service.registrar_entrada(
        modelo=modelo_descartavel, identificadores=["OUTRO1"], destino=agente2, autor=operador,
    )

    resposta = client.get(
        reverse("iscas:unidade_lista"), {"custodia": agente.custodia.pk},
        HTTP_HX_REQUEST="true",
    )

    assert {u.identificador for u in resposta.context["unidades"]} == {
        u.identificador for u in unidades_com_agente
    }


# sabotagem: devolver todas as abertas em solicitacoes_pendentes, sem olhar a falta → vermelho
def test_aviso_fica_ate_a_solicitacao_estar_coberta(
    client, operador_logado, agente, cliente, operador, modelo_descartavel,
    unidades_com_agente,
):
    pedido = solicitacao_service.abrir_solicitacao(
        cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador
    )
    url = reverse("iscas:unidade_lista")

    [pendente] = client.get(url).context["solicitacoes_pendentes"]
    assert pendente["solicitacao"] == pedido

    solicitacao_service.criar_atribuicao(
        solicitacao=pedido, agente=agente, itens=[(modelo_descartavel, 2)], autor=operador,
    )
    assert client.get(url).context["solicitacoes_pendentes"] == []


# sabotagem: tirar a checagem de ATENDER_SOLICITACAO em aviso_solicitacoes → vermelho
def test_aviso_nao_aparece_para_quem_nao_atende(
    client, comercial_logado, cliente, operador, modelo_descartavel,
):
    solicitacao_service.abrir_solicitacao(
        cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador
    )

    resposta = client.get(reverse("iscas:solicitacao_lista"))

    assert "solicitacoes_pendentes" not in resposta.context
