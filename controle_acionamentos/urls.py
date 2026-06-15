from django.urls import path

from . import views

app_name = 'controle_acionamentos'

urlpatterns = [
    path('', views.index, name='index'),
]