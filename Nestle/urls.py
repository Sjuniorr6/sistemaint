from django.urls import path
from . import views
from .views import (
    GridInternacional, GridInternacionalCreate, GridInternacionalUpdate,
    GridInternacionalDelete, GridInternacionalDetail, grid_internacional_quick_edit,
    ClienteListView, ClienteCreateView, ClienteUpdateView, ClienteDeleteView,
    GridInternacionalFinalizados, grid_internacional_send_email, grid_internacional_json, clientes_sla_view,
    grid_internacional_sla_resumo, CargaListView, CargaCreateView, carga_aprovar_reprovar,
    atualizar_cotacao_ajax, atualizar_valor_mensal, sla_por_cliente_json, sla_simples_por_cliente_json,
    asset_convertido, asset_convertido_com_enderecos, mongol_assets, mongol_assets_com_enderecos, mongol_test_view, assets_unificado, assets_unificado_test_view
    
)
from .api_views import GridInternacionalUpdateAPIView

urlpatterns = [
    # Grid Internacional URLs
    path('grid/', views.GridInternacional.as_view(), name='grid_internacional_list'),
    path('grid/finalizados/', views.GridInternacionalFinalizados.as_view(), name='grid_internacional_finalizados'),
    path('grid/novo/', views.GridInternacionalCreate.as_view(), name='grid_internacional_create'),
    path('grid/<int:pk>/editar/', views.GridInternacionalUpdate.as_view(), name='grid_internacional_update'),
    path('grid/<int:pk>/excluir/', views.GridInternacionalDelete.as_view(), name='grid_internacional_delete'),
    path('grid/<int:pk>/', views.GridInternacionalDetail.as_view(), name='grid_internacional_detail'),
    path('grid/quick-edit/', views.grid_internacional_quick_edit, name='grid_internacional_quick_edit'),
    path('grid/send-email/', views.grid_internacional_send_email, name='grid_internacional_send_email'),
    path('grid/exportar-excel/', views.grid_internacional_export_excel, name='grid_internacional_export_excel'),
    path('grid/api/', views.grid_internacional_api, name='grid_internacional_api'),
    path('grid/api/equipamentos-bateria/', views.grid_internacional_equipamentos_bateria_api, name='grid_internacional_equipamentos_bateria_api'),
    path('grid/json/', views.grid_internacional_json, name='grid_internacional_json'),
    path('grid/sla-resumo/', grid_internacional_sla_resumo, name='grid_internacional_sla_resumo'),
    path('grid/sla-por-cliente/', sla_por_cliente_json, name='sla_por_cliente_json'),
    path('grid/sla-simples/', sla_simples_por_cliente_json, name='sla_simples_por_cliente_json'),
  
    # Cliente Nestle URLs
    path('clientes/', views.ClienteListView.as_view(), name='clientes_nestle_list'),
    path('clientes/novo/', views.ClienteCreateView.as_view(), name='clientes_nestle_create'),
    path('clientes/<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='clientes_nestle_update'),
    path('clientes/<int:pk>/excluir/', views.ClienteUpdateView.as_view(), name='clientes_nestle_delete'),
    path('clientes/sla/', views.clientes_sla_view, name='clientes_sla'),
    path('clientes/json/', views.clientes_nestle_json, name='clientes_nestle_json'),
    path('valores-mensais/', views.ValoresMensaisView.as_view(), name='valores_mensais'),
    path('valores-mensais/atualizar/', views.atualizar_valor_mensal, name='atualizar_valor_mensal'),
    
    # Carga/Cotações URLs
    path('controle/lista', views.CargaListView.as_view(), name='carga-list'),
    path('controle/nova/', views.CargaCreateView.as_view(), name='cotacoes-criar'),
    path('controle/aprovar/<int:pk>/<str:status>/', views.carga_aprovar_reprovar, name='carga-aprovar-reprovar'),
    path('atualizar-cotacao/', views.atualizar_cotacao_ajax, name='atualizar-cotacao-ajax'),
    path('atualizar-valor-mensal/', atualizar_valor_mensal, name='atualizar-valor-mensal'),
    
    # Asset URLs
    path('assetconvertido/', views.asset_convertido, name='asset_convertido'),
    path('assetconvertido/convert/', views.asset_convertido_com_enderecos, name='asset_convertido_com_enderecos'),
    
    # Mongol URLs
    path('mongol/', views.mongol_assets, name='mongol_assets'),
    path('mongol/convert/', views.mongol_assets_com_enderecos, name='mongol_assets_com_enderecos'),
    path('mongol/test/', views.mongol_test_view, name='mongol_test'),
    
    # Endpoint Unificado
    path('assets/unificado/', views.assets_unificado, name='assets_unificado'),
    path('assets/unificado/test/', views.assets_unificado_test_view, name='assets_unificado_test'),
    path('debug/gs-controller/', views.debug_gs_controller_raw, name='debug_gs_controller'),
    
    #api
    path('api/grid/<str:id_planilha>/', GridInternacionalUpdateAPIView.as_view(), name='grid-update-api'),
]


