# acompanhamentos/api/urls.py
from django.urls import path
from .views import api_missao_detail

urlpatterns = [
    path("missao/<str:id>/", api_missao_detail, name="api_missao_detail"),
]
