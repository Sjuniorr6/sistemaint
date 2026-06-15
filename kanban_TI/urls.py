from django.urls import path
from . import views

app_name = "kanban_TI"

urlpatterns = [
    path("", views.home, name="home"),
    path("adicionar/", views.adicionar_tarefa, name="adicionar_tarefa"),
    path("obter/<int:tarefa_id>/", views.obter_tarefa, name="obter_tarefa"),
    path("atualizar/<int:tarefa_id>/", views.atualizar_tarefa, name="atualizar_tarefa"),
    path("deletar/<int:tarefa_id>/", views.deletar_tarefa, name="deletar_tarefa"),
    path("atualizar-status/<int:tarefa_id>/", views.atualizar_status, name='atualizar_status'),
    path('exportar/', views.exportar_tarefas, name='exportar_tarefas'),

    # Inbox de tickets destinados ao T.I
    path('inbox/partial/', views.inbox_tickets_partial, name='inbox_partial'),
    path('inbox/badge/', views.inbox_badge, name='inbox_badge'),
    path('inbox/<int:pk>/mover-afazer/', views.ticket_mover_para_afazer, name='ticket_mover_para_afazer'),
    path('inbox/<int:pk>/editar-partial/', views.ticket_editar_partial, name='ticket_editar_partial'),
    path('inbox/<int:pk>/salvar-triagem/', views.ticket_salvar_triagem, name='ticket_salvar_triagem'),
    path('inbox/<int:pk>/recusar-partial/', views.ticket_recusar_partial, name='ticket_recusar_partial'),
    path('inbox/<int:pk>/recusar/', views.ticket_recusar, name='ticket_recusar'),
]
