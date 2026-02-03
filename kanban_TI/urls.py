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
]
