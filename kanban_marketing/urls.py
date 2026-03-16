from django.urls import path
from . import views

app_name = "kanban_marketing"

urlpatterns = [
    # Quando o usuário acessar o endereço vazio deste app, chama a nossa view home_marketing
    path("", views.home_marketing, name="home"),

    path("atualizar-status/<int:tarefa_id>/", views.atualizar_status_marketing, name="atualizar_status"),

    path("obter/<int:tarefa_id>/", views.obter_tarefa_marketing, name="obter_tarefa"),
    path("editar/<int:tarefa_id>/", views.editar_tarefa_marketing, name="editar_tarefa"),
    path("toggle-aprovacao/<int:tarefa_id>/", views.toggle_aprovacao_briefing, name="toggle_aprovacao"),
]