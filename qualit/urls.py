from django.urls import path
from . import views

urlpatterns = [
   
    path('criar-qualit/', views.QualitCreateView.as_view(), name='criar_qualit'),
    path('exportar-excel/', views.exportar_qualits_excel, name='exportar_qualits_excel'),
    path('', views.QualitListView.as_view(), name='listar_qualits'),

]