from django.views.generic import TemplateView
import os
from django.conf import settings

class PdfListView(TemplateView):
    template_name = "documentation.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pdf_dir = os.path.join(settings.BASE_DIR, 'static', 'downloads')

        print("🛠️ PDF_DIR:", pdf_dir)  # Para debug
        print("📄 Arquivos:", os.listdir(pdf_dir))  # Para ver se ele encontra

        arquivos = []
        extensoes_permitidas = ('.pdf', '.doc', '.docx')
        
        for nome_arquivo in os.listdir(pdf_dir):
            if nome_arquivo.lower().endswith(extensoes_permitidas):
                arquivos.append({
                    'nome': nome_arquivo,
                    'url': f"{settings.STATIC_URL}downloads/{nome_arquivo}"
                })

        context['arquivos_pdf'] = arquivos
        return context