from django.urls import path
from . import views

app_name = 'controle_administrativo'

urlpatterns = [
    path('', views.painel, name='painel'),
    path('execucao/<int:execucao_id>/toggle/', views.toggle_execucao, name='toggle_execucao'),
    path('execucao/<int:execucao_id>/comentario/', views.adicionar_comentario, name='adicionar_comentario'),
    path('execucao/<int:execucao_id>/detalhe/', views.detalhe_execucao, name='detalhe_execucao'),
]