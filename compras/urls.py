from django.urls import path
from . import views

app_name = 'compras'

urlpatterns = [
    path('', views.index, name='index'),
    path('cadastro-tipo-produto/', views.cadastro_tipo_produto, name='cadastro_tipo_produto'),
    path('entrada-produto/', views.entrada_produto, name='entrada_produto'),
    path('recebimento-chip/', views.recebimento_chip, name='recebimento_chip'),
    path('recebimento-chip/editar/<int:pk>/', views.editar_recebimento_chip, name='editar_recebimento_chip'),
    path('recebimento-chip/entrega/<int:pk>/', views.registrar_entrega_chip, name='registrar_entrega_chip'),
    path('recebimento-chip/deletar/<int:pk>/', views.deletar_recebimento_chip, name='deletar_recebimento_chip'),
]
