from django.urls import path

from . import views

app_name = 'controle_acionamentos'

urlpatterns = [
    path('', views.index, name='index'),
    path('acionamentos/', views.acionamento_list, name='acionamento_list'),
    path('acionamentos/novo/', views.acionamento_create, name='acionamento_create'),
    path(
        'acionamentos/vincular-franquia/',
        views.acionamento_vincular_franquia_lote,
        name='acionamento_vincular_franquia_lote',
    ),
    path('acionamentos/<int:pk>/', views.acionamento_detail, name='acionamento_detail'),
    path('acionamentos/<int:pk>/editar/', views.acionamento_update, name='acionamento_update'),
    path('acionamentos/<int:pk>/pedagio/', views.acionamento_pedagio_update, name='acionamento_pedagio_update'),
]