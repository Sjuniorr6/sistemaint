"""Rotas do Iscas Fast.

Todas exigem operador autenticado — a proteção fica nas views, na fronteira da
URL (mesmo padrão do app Chamados).
"""
from django.urls import path

from iscas.views import api, cadastro, custodia, dashboard, mapa, relatorio, solicitacao

app_name = "iscas"

urlpatterns = [
    path("", dashboard.painel, name="painel"),

    # — Cadastros —
    path("agentes/", cadastro.agente_lista, name="agente_lista"),
    path("agentes/novo/", cadastro.agente_criar, name="agente_criar"),
    path("agentes/<int:pk>/", cadastro.agente_detalhe, name="agente_detalhe"),
    path("agentes/<int:pk>/editar/", cadastro.agente_editar, name="agente_editar"),
    path("agentes/<int:pk>/desativar/", cadastro.agente_desativar, name="agente_desativar"),
    path("agentes/<int:pk>/pin/", cadastro.agente_ajustar_pin, name="agente_ajustar_pin"),

    path("clientes/", cadastro.cliente_lista, name="cliente_lista"),
    path("clientes/novo/", cadastro.cliente_criar, name="cliente_criar"),
    path("clientes/<int:pk>/", cadastro.cliente_detalhe, name="cliente_detalhe"),
    path("clientes/<int:pk>/editar/", cadastro.cliente_editar, name="cliente_editar"),
    path("clientes/<int:pk>/desativar/", cadastro.cliente_desativar, name="cliente_desativar"),
    path("clientes/<int:pk>/pin/", cadastro.cliente_ajustar_pin, name="cliente_ajustar_pin"),

    path("depositos/", cadastro.deposito_lista, name="deposito_lista"),
    path("depositos/novo/", cadastro.deposito_criar, name="deposito_criar"),
    path("depositos/<int:pk>/editar/", cadastro.deposito_editar, name="deposito_editar"),
    path("depositos/<int:pk>/desativar/", cadastro.deposito_desativar, name="deposito_desativar"),

    path("modelos/", cadastro.modelo_lista, name="modelo_lista"),
    path("modelos/novo/", cadastro.modelo_criar, name="modelo_criar"),
    path("modelos/<int:pk>/editar/", cadastro.modelo_editar, name="modelo_editar"),
    path("modelos/<int:pk>/desativar/", cadastro.modelo_desativar, name="modelo_desativar"),

    # — Estoque e custódia —
    path("unidades/", custodia.unidade_lista, name="unidade_lista"),
    path("unidades/<str:identificador>/", custodia.unidade_detalhe, name="unidade_detalhe"),
    path("entrada/", custodia.entrada, name="entrada"),
    path("transferencia/", custodia.transferencia, name="transferencia"),
    path("baixa/", custodia.baixa, name="baixa"),
    path("manutencao/", custodia.manutencao, name="manutencao"),
    path("manutencao/retorno/", custodia.manutencao_retorno, name="manutencao_retorno"),
    path("movimentacoes/<int:pk>/estornar/", custodia.estornar, name="estornar"),
    path("saldos/", custodia.painel_saldo, name="painel_saldo"),

    # — Mapa —
    path("mapa/", mapa.mapa, name="mapa"),
    path("mapa/proximidade/", mapa.busca_proximidade, name="busca_proximidade"),

    # — Solicitações —
    path("solicitacoes/", solicitacao.lista, name="solicitacao_lista"),
    path("solicitacoes/nova/", solicitacao.criar, name="solicitacao_criar"),
    path("solicitacoes/<int:pk>/", solicitacao.detalhe, name="solicitacao_detalhe"),
    path("solicitacoes/<int:pk>/atribuir/", solicitacao.atribuir, name="solicitacao_atribuir"),
    path("solicitacoes/<int:pk>/cancelar/", solicitacao.cancelar, name="solicitacao_cancelar"),
    path("solicitacoes/<int:pk>/excluir/", solicitacao.excluir, name="solicitacao_excluir"),
    path("solicitacoes/<int:pk>/restaurar/", solicitacao.restaurar, name="solicitacao_restaurar"),
    path(
        "solicitacoes/<int:pk>/pin/",
        solicitacao.ajustar_pin_entrega,
        name="solicitacao_ajustar_pin",
    ),
    path("atribuicoes/<int:pk>/rota/", solicitacao.marcar_em_rota, name="atribuicao_rota"),
    path("atribuicoes/<int:pk>/entregar/", solicitacao.confirmar_entrega, name="atribuicao_entregar"),
    path("atribuicoes/<int:pk>/cancelar/", solicitacao.cancelar_atribuicao, name="atribuicao_cancelar"),
    path("atribuicoes/<int:pk>/mensagem/", solicitacao.mensagem, name="atribuicao_mensagem"),

    # — Retornáveis —
    path("retornaveis/", custodia.retornaveis, name="retornaveis"),
    path("retornaveis/retorno/", custodia.registrar_retorno, name="registrar_retorno"),

    # — Histórico e relatórios —
    path("extrato/", relatorio.extrato, name="extrato"),
    path("extrato/csv/", relatorio.extrato_csv, name="extrato_csv"),
    path("historico/agente/<int:pk>/", relatorio.historico_agente, name="historico_agente"),
    path("historico/cliente/<int:pk>/", relatorio.historico_cliente, name="historico_cliente"),

    # — JSON para o mapa (sem DRF, ISC-ADR-12) —
    path("api/agentes.geojson", api.agentes_geojson, name="api_agentes"),
    path(
        "api/solicitacoes.geojson",
        api.solicitacoes_geojson,
        name="api_solicitacoes",
    ),
    path("api/proximidade/", api.proximidade, name="api_proximidade"),
    path("api/saldo/<int:agente_id>/", api.saldo_agente, name="api_saldo_agente"),
    path("api/unidades/", api.unidades_da_custodia, name="api_unidades_custodia"),
    path(
        "api/cliente/<int:cliente_id>/",
        api.dados_do_cliente,
        name="api_dados_cliente",
    ),
    path("api/cep/", api.consultar_cep, name="api_cep"),
    path("api/geocodificar/", api.geocodificar_endereco, name="api_geocodificar"),
    path(
        "api/geocodificar-reverso/",
        api.geocodificar_reverso,
        name="api_geocodificar_reverso",
    ),
]
