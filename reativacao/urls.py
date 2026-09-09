from django.urls import path
from .views import RequisicoesListView, ReativacaoView, ReativacaoIdIccidCreateView, ReativacaoListView,update_status, ReativacaoUpdateView, ReativacaoCompleteUpdateView, ReativacaoExportExcelView
from django.urls import path
from .views import DownloadPdfView
from .views import delete_reativacao

urlpatterns = [
    path('reativacoes/', ReativacaoListView.as_view(), name='reativacao_list'),
    path('reativacoes/exportar-excel/', ReativacaoExportExcelView.as_view(), name='reativacao_export_excel'),
    path('reativacoes/adicionar/', ReativacaoIdIccidCreateView.as_view(), name='reativacao_id_iccid_adicionar'),
    path('reativacoes/update/<int:pk>/', ReativacaoUpdateView.as_view(), name='reativacao_update'),
    path('reativacoes/complete-update/<int:pk>/', ReativacaoCompleteUpdateView.as_view(), name='reativacao_complete_update'),
    path('reativacoes/delete/<int:pk>/', delete_reativacao, name='reativacao_delete'),
    path('reativacao/', ReativacaoView.as_view(), name='reativacao'),
    path('update_status/', update_status, name='update_status'),
    path('requisicoes/', RequisicoesListView.as_view(), name='requisicoes_list'),
    path('download_pdf/<int:id_iccid>/', DownloadPdfView.as_view(), name='download_pdf_REATIVACAO'),
]

