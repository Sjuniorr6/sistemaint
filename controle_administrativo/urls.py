from django.urls import path
from . import views

app_name = 'controle_administrativo'

urlpatterns = [
    # Painel
    path('', views.painel, name='painel'),
    path('<int:semana_iso>/<int:ano>/', views.painel, name='painel_semana'),

    # Histórico
    path('historico/', views.historico, name='historico'),
    path('historico/<int:semana_iso>/<int:ano>/', views.historico, name='historico_semana'),

    # Execuções de tarefa
    path('execucao/<int:execucao_id>/toggle/', views.toggle_execucao, name='toggle_execucao'),
    path('execucao/<int:execucao_id>/comentario/', views.adicionar_comentario, name='adicionar_comentario'),
    path('execucao/<int:execucao_id>/detalhe/', views.detalhe_execucao, name='detalhe_execucao'),
    path('execucao/criar/', views.criar_tarefa, name='criar_tarefa'),
    path('execucao/<int:execucao_id>/excluir/', views.excluir_tarefa, name='excluir_tarefa'),

    # Blocos especiais
    path('bloco/<int:bloco_id>/item/adicionar/', views.adicionar_item_bloco_view, name='adicionar_item_bloco'),
    path('bloco/item/<int:item_id>/toggle/', views.toggle_item_bloco_view, name='toggle_item_bloco'),
    path('bloco/item/<int:item_id>/excluir/', views.excluir_item_bloco_view, name='excluir_item_bloco'),
    path('bloco/item/<int:item_id>/detalhe/', views.detalhe_item_bloco, name='detalhe_item_bloco'),
    path('bloco/item/<int:item_id>/atualizar/', views.atualizar_item_bloco_view, name='atualizar_item_bloco'),
    path('bloco/item/<int:item_id>/comentario/', views.adicionar_comentario_item_bloco_view, name='adicionar_comentario_item_bloco'),

    # Divisão de tarefas
    path('divisao/<int:funcionario_id>/adicionar/', views.adicionar_tarefa_divisao_view, name='adicionar_tarefa_divisao'),
    path('divisao/tarefa/<int:tarefa_id>/editar/', views.editar_tarefa_divisao_view, name='editar_tarefa_divisao'),
    path('divisao/tarefa/<int:tarefa_id>/excluir/', views.excluir_tarefa_divisao_view, name='excluir_tarefa_divisao'),
    path('divisao/tarefa/<int:tarefa_id>/detalhe/', views.detalhe_tarefa_divisao_view, name='detalhe_tarefa_divisao'),
    path('divisao/tarefa/<int:tarefa_id>/atualizar/', views.atualizar_tarefa_divisao_view, name='atualizar_tarefa_divisao'),
    path('divisao/tarefa/<int:tarefa_id>/comentario/', views.adicionar_comentario_tarefa_divisao_view, name='comentario_tarefa_divisao'),

    # Exportação Excel
    path('exportar/<int:semana_iso>/<int:ano>/', views.exportar_excel, name='exportar_excel'),
]