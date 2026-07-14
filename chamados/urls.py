from django.urls import path

from . import views

app_name = 'chamados'

urlpatterns = [
    path('', views.fila, name='fila'),
    path('novo/', views.abrir, name='abrir'),
    path('<int:pk>/', views.detalhe, name='detalhe'),
    path('<int:pk>/acao/<str:acao>/', views.acao, name='acao'),
]
