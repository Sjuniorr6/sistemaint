# acompanhamentos/api/urls.py
from django.urls import path
from .views import api_missao_detail, api_missao_location, api_missao_panic

urlpatterns = [
    path("missao/<str:id>/", api_missao_detail, name="api_missao_detail"),
    path("missao/<str:id>/location/", api_missao_location, name="api_missao_location"),
    path("missao/<str:id>/panic/", api_missao_panic, name="api_missao_panic"),
]