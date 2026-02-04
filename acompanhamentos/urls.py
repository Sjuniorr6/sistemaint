from django.urls import path
from . import views

urlpatterns = [
    # ============== Acompanhamentos ==============

    # Agentes Acompanhamento URLs
    path("novoAgente/",views.AgenteAcompanhamentoCreateView.as_view(),name="agenteAcompanhamentoCreate",),
    path("listAgente/",views.AgenteAcompanhamentoListView.as_view(),name="agenteAcompanhamentoList",),
    path('<int:pk>/editarAgente/',views.RegistroAgenteAcompanhamentoUpdateView.as_view(),name='agenteAcompanhamentoUpdate'),

    # Responsável Agentes Acompanhamento URLs
    path("ajax/novo-responsavel-agente/",views.criar_responsavel_agente_ajax,name="criar_responsavel_agente_ajax"),
    path("listResponsavelAgente/",views.ResponsavelAgenteAcompanhamentoListView.as_view(),name="responsavelagenteAcompanhamentoList",),
    path("ajax/editar-responsavel-agente/<int:pk>/",views.editar_responsavel_agente_ajax,name="editar_responsavel_agente_ajax"),

    # Clientes Acompanhamento URLs
    path("novoCliente/",views.ClienteAcompanhamentoCreateView.as_view(),name="clienteAcompanhamentoCreate",),
    path("listCliente/",views.ClienteAcompanhamentoListView.as_view(),name="clienteAcompanhamentoList",),
    path('<int:pk>/editarCliente/',views.RegistroClienteAcompanhamentoUpdateView.as_view(),name='clienteAcompanhamentoUpdate'),

    # Serviços Acompanhamento URLs
    path("novoServico/",views.ServicoAcompanhamentoCreateView.as_view(),name="servicoAcompanhamentoCreate",),
    path("listServico/",views.ServicoAcompanhamentoListView.as_view(),name="servicoAcompanhamentoList",),
    path('<int:pk>/editarServico/',views.RegistroServicoAcompanhamentoUpdateView.as_view(),name='servicoAcompanhamentoUpdate'),
    
    # Acompanhamento URLs
    path("novo/",views.AcompanhamentoCreateView.as_view(),name="AcompanhamentosCreate",),
    path('<int:pk>/editar/',views.RegistroAcompanhamentoUpdateView.as_view(),name='acompanhamentosUpdate'),
    path("list/",views.AcompanhamentoListView.as_view(),name="acompanhamentosList",),
    path("atualizar-franquia/", views.atualizar_franquia_acompanhamento, name="acompanhamentosUpdateFranquia"),

    # Acompanhamento Faturamento URLs
    path("listFaturamento/",views.AcompanhamentoFaturamentoListView.as_view(),name="acompanhamentosListFaturamento",),
    path('validado/<int:id>/', views.validar_acompanhamento, name='Validar_Acompanhamento'),
    path('Pago/<int:id>/', views.validar_pagamento, name='Validar_Pagamento'),
    # path("atualizar-valor-contrato/", views.atualizar_valor_contrato_cliente, name="atualizar_valor_contrato_cliente"),
    path("atualizar-status/", views.atualizar_status_acompanhamento, name="atualizar_status_acompanhamento"),
    path("atualizar-nf/", views.atualizar_nf_acompanhamento, name="atualizar_nf_acompanhamento"),

    # =========================
    # LISTA PANICO (CENTRAL)
    # =========================
    path(
        "panico/",
        views.AcompanhamentoPanicoListView.as_view(),
        name="acompanhamentosPanicoList",
    ),

    # =========================
    # MISSÃO (AGENTE)
    # =========================
    path(
        "missao/<int:pk>/",
        views.acompanhamento_missao,
        name="acompanhamento_missao"
    ),

    # Aceitar missão
    path(
        "missao/<int:pk>/aceitar/",
        views.aceitar_missao,
        name="acompanhamento_aceitar_missao"
    ),

    # Envio de localização (30s)
    path(
        "missao/<int:pk>/localizacao/",
        views.salvar_localizacao,
        name="acompanhamento_salvar_localizacao"
    ),

    # Botão de pânico
    path(
        "missao/<int:pk>/panico/",
        views.acionar_panico,
        name="acompanhamento_panico"
    ),

    # Finalizar operação
    path(
        "missao/<int:pk>/finalizar/",
        views.finalizar_operacao,
        name="acompanhamento_finalizar"
    ),

    path(
        "missao/<int:pk>/mapa/",
        views.acompanhamento_mapa,
        name="acompanhamento_mapa"
    ),


    # Página
    path(
    "dashboard/",
    views.AcompanhamentoDashboardView.as_view(),
    name="acompanhamentoDashboard"
    ),
    path(
        "dashboard/data/",
        views.acompanhamento_dashboard_data,
        name="acompanhamento_dashboard_data"
    ),
]