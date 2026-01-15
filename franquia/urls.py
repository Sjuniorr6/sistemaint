from django.urls import path
from . import views

urlpatterns = [
    # ============== FRANQUIA ==============
    # Franquia URLs
    path("novo/",views.FranquiaCreateView.as_view(),name="franquiaCreate",),
    path("list/",views.FranquiaListView.as_view(),name="franquiaList",),
    path('<int:pk>/editar/',views.RegistroFranquiaUpdateView.as_view(),name='franquiaUpdate'),
]