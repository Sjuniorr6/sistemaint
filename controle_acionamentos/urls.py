from django.urls import path

from . import views

app_name = 'controle_acionamentos'

urlpatterns = [
    path('', views.index, name='index'),
    path('acionamentos/novo/', views.acionamento_create, name='acionamento_create'),
    path('acionamentos/<int:pk>/', views.acionamento_detail, name='acionamento_detail'),
]