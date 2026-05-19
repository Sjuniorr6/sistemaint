from django.urls import path
from . import views

app_name = 'controle_administrativo'

urlpatterns = [
    # Painel
    path('', views.painel, name='painel'),

    # Execuções de tarefa
    path('execucao/<int:execucao_id>/toggle/', views.toggle_execucao, name='toggle_execucao'),
    path('execucao/<int:execucao_id>/comentario/', views.adicionar_comentario, name='adicionar_comentario'),
    path('execucao/<int:execucao_id>/detalhe/', views.detalhe_execucao, name='detalhe_execucao'),
    path('execucao/criar/', views.criar_tarefa, name='criar_tarefa'),
    path('execucao/<int:execucao_id>/excluir/', views.excluir_tarefa, name='excluir_tarefa'),

    # Blocos especiais — itens
    path('bloco/<int:bloco_id>/item/adicionar/', views.adicionar_item_bloco_view, name='adicionar_item_bloco'),
    path('bloco/item/<int:item_id>/toggle/', views.toggle_item_bloco_view, name='toggle_item_bloco'),
    path('bloco/item/<int:item_id>/excluir/', views.excluir_item_bloco_view, name='excluir_item_bloco'),
    path('bloco/item/<int:item_id>/detalhe/', views.detalhe_item_bloco, name='detalhe_item_bloco'),
    path('bloco/item/<int:item_id>/atualizar/', views.atualizar_item_bloco_view, name='atualizar_item_bloco'),
    path('bloco/item/<int:item_id>/comentario/', views.adicionar_comentario_item_bloco_view, name='adicionar_comentario_item_bloco'),
]