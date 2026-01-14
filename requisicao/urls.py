from django.urls import path
from . import views
from .views import download_pdf_requisicao, enviar_email_com_pdf, get_cliente_data,gerar_pdf_saida,AntenistaCreateView,AntenistaListView,RequisicaoUpdateView


    #-------------------------------------------------------------------------------------------------------------

urlpatterns = [
    # ============== KANBAN BOARD URLS ==============
    path('kanban/gestao/', views.KanbanGestaoView.as_view(), name='kanban_gestao'),
    path('api/kanban/update-status/', views.update_kanban_status, name='kanban_update_status'),
    path('api/kanban/toggle-priority/<int:pk>/', views.toggle_prioridade, name='kanban_toggle_priority'),
    path('api/kanban/detalhes/<int:pk>/', views.kanban_detalhes_requisicao, name='kanban_detalhes'),
    path('api/kanban/expedir-parcial/', views.expedir_requisicao_parcial, name='kanban_expedir_parcial'),
    path('api/kanban/salvar-ids/<int:pk>/', views.salvar_ids_equipamentos, name='kanban_salvar_ids'),
    
    # Outras URLs
    path('requisicao/<int:id>/download/', download_pdf_requisicao, name='download_pdf_requisicao'),
    path('requisicao/<int:id>/download1/', gerar_pdf_saida, name='gerar_pdf_saida'),
    path('requisicao/<int:id>/enviar-email/', enviar_email_com_pdf, name='enviar_email_com_pdf'),
    path('requisicao/', views.RequisicoesViews.as_view(), name='requisicoes'),
    path('requisicaocreate', views.RequisicaoCreateView.as_view(), name='requisicoescrateview'),
    path('antenistaview', views.RegistrarEstoqueantenistaView.as_view(), name='RegistrarEstoqueantenistaView'),
    path('estoque-antenista/<int:pk>/delete/', views.delete_estoque_antenista, name='delete_estoque_antenista'),
    path('saida-equipamentos/', views.AntenistaCardCreateView.as_view(), name='saida_equipamentos'),
    path('requisicoes/list', views.RequisicaoDetailView.as_view(), name='RequisicaoDetailView'),
    path('requisicao/<int:pk>/update/', views.RequisicaoUpdateView.as_view(), name='RequisicaoUpdateView'),
    path('requisicao/<int:pk>/delete/', views.requisicoesDeleteView.as_view(), name='requisicoesdeleteview'),
    
    # Acompanhamento URLs
    path("acompanhamento/novo/",views.AcompanhamentoCreateView.as_view(),name="acompanhamentoCreate",),
    path("acompanhamento/list/",views.AcompanhamentoListView.as_view(),name="acompanhamentoList",),
    path('acompanhamento/<int:pk>/editar/',views.RegistroAcompanhamentoUpdateView.as_view(),name='acompanhamentoUpdate'),
    path("acompanhamento/dashboard/",views.acompanhamento_dashboard,name="acompanhamentoDashboard",),

#----------------------------------------------------------------------------------------------------------------

#--------------------------------------------------------------------------------------------------------------------
    path('tecnicoListView/', views.tecnicoListView.as_view(), name='tecnicoListView'),
    path('FinanceiroListViews/', views.FinanceiroListViews.as_view(), name='FinanceiroListViews'),
    path('tecnicoListView/<int:pk>/Update/', views.tecnicoUpdateView.as_view(), name='tecnicoUpdateView'),
    path('configlistview/', views.ConfiguracaoListView.as_view(), name='ConfiguracaoListView'),
    path('configuracao/<int:pk>/delete/', views.configuracaodeleteview.as_view(), name='ConfiguracaoListView'),
    path('config/list/<int:pk>/Update/', views.ConfiguracaoUpdateView.as_view(), name='ConfiguracaoUpdateView'),
    path('controle/', views.ControleCreateView.as_view(), name='controle'),
    path('controleList/', views.ControleListView.as_view(), name='controleList'),
   

    path('req/list/<int:pk>/Update/', views.Requisicao2UpdateView.as_view(), name='Requisicao2UpdateView'),
    path('config/list2/<int:pk>/Update/', views.ConfiguracaoUpdateView2.as_view(), name='ConfiguracaoUpdateView2'),
 #---------------------------------------------------------------------------------------------------------------
    path('ceo_list/list', views.ceoListViews.as_view(), name='ceoListViews'),  
      path('ceo_list/<int:pk>/detail/', views.ceodetailview.as_view(), name='ceodetailview'),
#--------------------------------------------------------------------------------------------------------------------   
      path('diretoria_list/', views.diretoriaListViews.as_view(), name='diretoriaListViews'),
#---------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------   
      path('expedicao_list/', views.expedicaoListViews.as_view(), name='expedicaoListViews'),
#---------------------------------------------------------------------------------------------------------------------
    path('historico_list/', views.historicoListView.as_view(), name='historicoListViews'),
#----------------------------------------------------------------------------------------------------------------------
    path('requisicao/diretoriaap/<int:id>/', views.aprovar_requisicao, name='aprovar_requisicao'),
    path('requisicao/diretoriaap/<int:id>/', views.reprovar_requisicao, name='reprovar_requisicao'),
  #--------------------------------------------------------------------------------------------------------------------- 
   #-----------------------------------------------------------------------------------------------------------------------------

    path('requisicao/reprovarrp/<int:id>/', views.Reprovar_diretoria, name='Reprovar_diretoria'),
    path('requisicao/aprovarrp/<int:id>/', views.Aprovar_diretoria, name='Aprovar_diretoria'),
#-----------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------
# 
 path('financeiro/ap/<int:id>/', views.aprovar_FINANCEIRO, name='APROVARFINANCEIRO'),
# 
# 
# ------------------------

     path('requisicao/aprovar/<int:id>/', views.aprovar_ceo, name='aprovar_ceo'),
    path('requisicao/reprovar/<int:id>/', views.reprovar_ceo, name='reprovar_ceo'),
#-------------------------------------------------------------------------------------------------------------  
  path('requisicao/expedir/<int:id>/', views.configurado_expedicao, name='configurado_expedicao'),
#---------------------------------------------------------------------------------------------------------------
path('requisicao/expedido/<int:id>/', views.expedicao_expedido, name='expedicao_expedido'),
path('manutencao/expedido/<int:id>/', views.expedicao_expedido2, name='expedicao_expedido2'),
path('expedir_requisicao/<int:id>/', views.expedir_requisicao, name='expedir_requisicao'),
path('expedir_requisicao_tec/<int:id>/', views.expedir_requisicaotec, name='expedir_requisicaotec'),
    path('expedir_manutencao/<int:id>/', views.expedir_manutencao, name='expedir_manutencao'),
     path('get-cliente-data/<int:cliente_id>/', get_cliente_data, name='get_cliente_data'),
path('novo-antenista/', AntenistaCreateView.as_view(), name='novo_antenista'),
    path('lista-antenistas/', AntenistaListView.as_view(), name='lista_antenistas'),
    path('lista-antenistas-cadastrados/', views.AntenistaCadastradosListView.as_view(), name='lista_antenistas_cadastrados'),
    path('lista-antenistas/export-excel/', views.export_antenistas_excel, name='export_antenistas_excel'),
     
    path('antenista/<int:pk>/atualizado/', views.atualizar_status_atualizado, name='atualizar_atualizado'),
    path('antenista/<int:pk>/delete/', views.delete_antenista_card, name='delete_antenista_card'),
    path('antenista-cadastrado/<int:pk>/edit/', views.AntenistaUpdateView.as_view(), name='editar_antenista'),
    path('antenista-cadastrado/<int:pk>/delete/', views.AntenistaDeleteView.as_view(), name='apagar_antenista'),
        path('antenistaview/zerar-estoque/', views.zerar_estoque_antenista, name='zerar_estoque_antenista'),
path('requisicoes/<int:pk>/editar/', RequisicaoUpdateView.as_view(), name='requisicao_update'),
path('manutencao/configurado/<int:id>/', views.configurado_manutencao, name='configurado_manutencao'),
    
    # URLs de Auditoria
    path('requisicao/<int:id>/logs/', views.ver_logs_requisicao, name='ver_logs_requisicao'),
    path('manutencao/<int:id>/logs/', views.ver_logs_manutencao, name='ver_logs_manutencao'),
    
    # API de Requisições
    path('api/requisicoes/', views.api_requisicoes, name='api_requisicoes'),
]
