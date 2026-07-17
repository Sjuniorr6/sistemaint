from django.urls import path

from . import views

app_name = 'controle_acionamentos'

urlpatterns = [
    path('', views.index, name='index'),
    path('acionamentos/', views.acionamento_list, name='acionamento_list'),
    path('acionamentos/novo/', views.acionamento_create, name='acionamento_create'),
    path(
        'acionamentos/vincular-franquia/',
        views.acionamento_vincular_franquia_lote,
        name='acionamento_vincular_franquia_lote',
    ),
    path('acionamentos/<int:pk>/', views.acionamento_detail, name='acionamento_detail'),
    path('acionamentos/<int:pk>/editar/', views.acionamento_update, name='acionamento_update'),
    path('acionamentos/<int:pk>/pedagio/', views.acionamento_pedagio_update, name='acionamento_pedagio_update'),
    path(
        'acionamentos/servicos-por-cliente/<int:cliente_id>/',
        views.servicos_por_cliente,
        name='servicos_por_cliente',
    ),

    # Cadastros — DD-050
    path('clientes/', views.cliente_list, name='cliente_list'),
    path('clientes/novo/', views.cliente_create, name='cliente_create'),
    path('clientes/<int:pk>/editar/', views.cliente_update, name='cliente_update'),
    path('agentes/', views.agente_list, name='agente_list'),
    path('agentes/novo/', views.agente_create, name='agente_create'),
    path('agentes/<int:pk>/editar/', views.agente_update, name='agente_update'),
    path('responsaveis/', views.responsavel_list, name='responsavel_list'),
    path('responsaveis/novo/', views.responsavel_create, name='responsavel_create'),
    path('responsaveis/<int:pk>/editar/', views.responsavel_update, name='responsavel_update'),
    path('franquias/', views.franquia_list, name='franquia_list'),
    path('franquias/novo/', views.franquia_create, name='franquia_create'),
    path('franquias/<int:pk>/editar/', views.franquia_update, name='franquia_update'),
]