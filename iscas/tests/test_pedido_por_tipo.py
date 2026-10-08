"""Pedido por tipo de isca (descartável/retornável), não por modelo."""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from iscas.enums import TipoModelo
from iscas.models import ItemSolicitacao, ModeloEquipamento
from iscas.selectors import agentes_que_atendem
from iscas.services import entrada as entrada_service
from iscas.services import solicitacao as service
from iscas.services.exceptions import MovimentacaoInvalida
from iscas.services.geo import agentes_para_solicitacao

pytestmark = pytest.mark.django_db

D, R = TipoModelo.DESCARTAVEL, TipoModelo.RETORNAVEL


@pytest.fixture
def outro_descartavel(db):
    return ModeloEquipamento.objects.create(
        nome="Isca Descartável Y9", codigo="ISC-D-Y9", tipo=D
    )


def _cobertura_unitaria(solicitacao):
    return service.cobertura(solicitacao)


def _cobertura_em_lote(solicitacao):
    return service.cobertura_em_lote([solicitacao])[solicitacao.pk]


# sabotagem: contar atribuído por unidade__modelo_id em vez de tipo → vermelho
@pytest.mark.parametrize("calcular", [_cobertura_unitaria, _cobertura_em_lote])
def test_cobertura_soma_por_tipo_inclusive_linhas_antigas(
    calcular, cliente, operador, agente, modelo_descartavel, outro_descartavel,
    unidades_com_agente,
):
    # Pedido antigo: dois modelos descartáveis, cada um na sua linha.
    solicitacao = service.abrir_solicitacao(
        cliente=cliente, itens=[(D, 1)], autor=operador
    )
    solicitacao.itens.all().delete()
    ItemSolicitacao.objects.bulk_create([
        ItemSolicitacao(solicitacao=solicitacao, modelo=outro_descartavel, tipo=D, quantidade=2),
        ItemSolicitacao(solicitacao=solicitacao, modelo=modelo_descartavel, tipo=D, quantidade=3),
    ])
    service.criar_atribuicao(
        solicitacao=solicitacao, agente=agente,
        itens=[(modelo_descartavel, 4)], autor=operador,
    )

    [linha] = calcular(solicitacao)

    assert (linha["tipo"], linha["solicitado"], linha["atribuido"], linha["falta"]) == (D, 5, 4, 1)


# sabotagem: remover a checagem de excesso por tipo em _validar_contra_o_pedido → vermelho
def test_atribuicao_recusa_exceder_o_pedido_por_tipo(
    cliente, operador, agente, modelo_descartavel, outro_descartavel, unidades_com_agente
):
    entrada_service.registrar_entrada(
        modelo=outro_descartavel, identificadores=["Y01", "Y02"],
        destino=agente, autor=operador,
    )
    solicitacao = service.abrir_solicitacao(
        cliente=cliente, itens=[(D, 3)], autor=operador
    )
    service.criar_atribuicao(
        solicitacao=solicitacao, agente=agente,
        itens=[(modelo_descartavel, 2)], autor=operador,
    )

    with pytest.raises(MovimentacaoInvalida, match="cabem no máximo 1"):
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(outro_descartavel, 2)], autor=operador,
        )


# sabotagem: filtrar unidades disponíveis sem modelo__tipo → vermelho
def test_agente_so_com_outro_tipo_nao_atende(
    cliente, operador, agente, agente2, modelo_retornavel, unidades_com_agente
):
    entrada_service.registrar_entrada(
        modelo=modelo_retornavel, identificadores=["R01", "R02"],
        destino=agente2, autor=operador,
    )
    solicitacao = service.abrir_solicitacao(
        cliente=cliente, itens=[(R, 5)], autor=operador
    )

    assert list(agentes_que_atendem(solicitacao)) == [agente2]
    candidatos = agentes_para_solicitacao(solicitacao=solicitacao, raio_km=50)
    assert [(c["agente"], c["disponivel"]) for c in candidatos] == [(agente2, 2)]


# sabotagem: ignorar minimo_disponivel em agentes_para_solicitacao → vermelho
@pytest.mark.parametrize("minimo, esperados", [(None, 2), (5, 1)])
def test_minimo_de_iscas_disponiveis(
    minimo, esperados, cliente, operador, agente, agente2,
    modelo_descartavel, unidades_com_agente,
):
    entrada_service.registrar_entrada(
        modelo=modelo_descartavel, identificadores=["B01", "B02"],
        destino=agente2, autor=operador,
    )
    solicitacao = service.abrir_solicitacao(
        cliente=cliente, itens=[(D, 10)], autor=operador
    )

    candidatos = agentes_para_solicitacao(
        solicitacao=solicitacao, raio_km=50, minimo_disponivel=minimo
    )

    assert len(candidatos) == esperados


# sabotagem: trocar a chave quantidade_<tipo> lida em _itens_do_post → vermelho
def test_abertura_pela_tela_cria_um_item_por_tipo(client, operador_logado, cliente):
    resposta = client.post(reverse("iscas:solicitacao_criar"), {
        "cliente": cliente.pk,
        "documento": cliente.documento,
        "telefone": cliente.telefone,
        "entrega_logradouro": cliente.logradouro,
        "entrega_numero": cliente.numero,
        "entrega_cidade": cliente.cidade,
        "entrega_uf": cliente.uf,
        f"quantidade_{D}": "3", f"preco_{D}": "10.00",
        f"quantidade_{R}": "1", f"preco_{R}": "50.00",
        "valor_assinatura_mensal": "30.00",
    })
    assert resposta.status_code == 302

    solicitacao = cliente.solicitacoes.get()
    itens = {(i.tipo, i.modelo_id, i.quantidade, i.valor_unitario) for i in solicitacao.itens.all()}
    assert itens == {(D, None, 3, Decimal("10.00")), (R, None, 1, Decimal("50.00"))}
    assert solicitacao.valor_cliente == Decimal("80.00")


# sabotagem: remover iscas_item_tipo_unico da migração → vermelho
def test_banco_recusa_dois_itens_novos_do_mesmo_tipo(cliente, operador):
    solicitacao = service.abrir_solicitacao(
        cliente=cliente, itens=[(D, 1)], autor=operador
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        ItemSolicitacao.objects.create(solicitacao=solicitacao, tipo=D, quantidade=2)
