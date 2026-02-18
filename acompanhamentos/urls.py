from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from . import views
from . import api_views

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

    path(
        "missao/<int:pk>/mapa/",
        views.acompanhamento_mapa,
        name="acompanhamento_mapa"
    ),

    path(
        "missao/<uuid:mission_id>/mapa/",
        views.acompanhamento_mapa_supabase,
        name="acompanhamento_mapa_supabase"
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

    path('api/token/', obtain_auth_token, name='api_token'),
    path('api/sync/cliente/', api_views.sync_cliente, name='sync_cliente'),
    path('api/sync/tipo-servico/', api_views.sync_tipo_servico, name='sync_tipo_servico'),
    path('api/sync/requisicao/', api_views.sync_requisicao, name='sync_requisicao'),
]