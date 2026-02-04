from django.urls import path
from . import api_views

urlpatterns = [
    path("missoes/<int:pk>/", api_views.api_missao_detalhe),
]
