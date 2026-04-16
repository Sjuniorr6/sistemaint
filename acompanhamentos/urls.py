from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from . import views
from . import api_views

urlpatterns = [
    # ============== Acompanhamentos ==============

    # Franquia Agentes URLs
    path("fraquia/",views.FranquiaListView.as_view(),name="franquiaList",),

    path("clientes/",views.ClientListView.as_view(),name="clienteList",),

    # Agentes Acompanhamento URLs
    path("novoAgente/",views.AgenteAcompanhamentoCreateView.as_view(),name="agenteAcompanhamentoCreate",),
    path("listAgente/",views.AgenteAcompanhamentoListView.as_view(),name="agenteAcompanhamentoList",),
    path('<int:pk>/editarAgente/',views.RegistroAgenteAcompanhamentoUpdateView.as_view(),name='agenteAcompanhamentoUpdate'),

    # Responsável Agentes Acompanhamento URLs
    path("ajax/novo-responsavel-agente/",views.criar_responsavel_agente_ajax,name="criar_responsavel_agente_ajax"),
    path("ajax/estimativa-km/", views.ajax_estimativa_km, name="ajax_estimativa_km"),
    path("listResponsavelAgente/",views.ResponsavelAgenteAcompanhamentoListView.as_view(),name="responsavelagenteAcompanhamentoList",),
    path("ajax/editar-responsavel-agente/<int:pk>/",views.editar_responsavel_agente_ajax,name="editar_responsavel_agente_ajax"),
    
    # Acompanhamento URLs
    path("novo/",views.AcompanhamentoCreateView.as_view(),name="AcompanhamentosCreate",),
    path('<int:pk>/editar/',views.RegistroAcompanhamentoUpdateView.as_view(),name='acompanhamentosUpdate'),
    path("list/",views.AcompanhamentoListView.as_view(),name="acompanhamentosList",),
    # path("atualizar-franquia/", views.atualizar_franquia_acompanhamento, name="acompanhamentosUpdateFranquia"),

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

    path(
        "monitoramento-ao-vivo/",
        views.MonitoramentoAoVivoView.as_view(),
        name="monitoramentoAoVivo",
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
    path('api/sync/cliente/', api_views.sync_cliente, name='api_sync_cliente'),
    path('api/sync/tipo-servico/', api_views.sync_tipo_servico, name='api_sync_tipo_servico'),
    path('api/sync/requisicao/', api_views.sync_requisicao, name='api_sync_requisicao'),
    path('api/sync/franquia/', api_views.sync_franquia, name='sync_franquia'),
    path('api/sync/missao/', api_views.sync_missao, name='sync_missao'),
    path('api/callback/acompanhamento-aprovado/', api_views.callback_acompanhamento_aprovado, name='callback_acompanhamento_aprovado',),
    path("api/sync-status-supabase/", views.sync_status_from_supabase, name="sync_status_supabase"),
    path("api/lucro-total-por-dia/", api_views.api_lucro_total_por_dia, name="api_lucro_total_por_dia"),
    path("api/top-clientes-pagadores/", api_views.api_top_clientes_pagadores),
    path("api/alertas-agendamento/", views.api_alertas_agendamento, name="api_alertas_agendamento",),

    path('requisicoes-solicitacao/', views.RequisicaoSolicitacaoListView.as_view(), name='requisicao_solicitacao_list'),
    path('requisicao/nova/<int:pk>/', views.AcompanhamentoFromRequisicaoCreateView.as_view(), name='RequisicaoCreate'),
    path(
        'requisicao/nova/grupo/<int:req_id_externo>/',
        views.AcompanhamentoFromGrupoCreateView.as_view(),
        name='RequisicaoGrupoCreate'
    ),
    path(
        'requisicoes-solicitacao/<int:pk>/recusar-reuso/',
        views.recusar_reuso,
        name='recusar_reuso'
    ),

    path(
        "<int:pk>/atualizar-pedagio/",
        views.atualizar_pedagio_acompanhamento,
        name="acompanhamentosUpdatePedagio",
    ),



    # path('requisicao/<int:pk>/editar/',views.RegistroAcompanhamentoUpdateView.as_view(),name='acompanhamentosUpdate'),
]