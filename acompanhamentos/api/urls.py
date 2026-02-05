from django.urls import path
from .views import (
    api_missao_detail,
    api_missao_location,
    api_missao_panic,
    api_missao_localizacoes,
    api_resolver_panico,
    api_missao_wait_panic,
    api_missao_panic_status
)

urlpatterns = [
    path("missao/<str:id>/", api_missao_detail, name="api_missao_detail"),
    path("missao/<str:id>/location/", api_missao_location, name="api_missao_location"),
    path("missao/<str:id>/panic/", api_missao_panic, name="api_missao_panic"),
    path("missao/<str:id>/localizacoes/", api_missao_localizacoes, name="api_missao_localizacoes"),
    path("missao/<str:id>/wait-panic/", api_missao_wait_panic, name="api_missao_wait_panic"),
    path("localizacao/<int:localizacao_id>/resolver-panico/", api_resolver_panico, name="api_resolver_panico"),
    path("missao/<str:id>/panic-status/", api_missao_panic_status, name="api_missao_panic_status"),

]
