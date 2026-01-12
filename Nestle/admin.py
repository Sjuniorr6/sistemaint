from django.contrib import admin
from .models import GridInternacional

@admin.register(GridInternacional)
class GridInternacionalAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_planilha', 'cliente', 'container', 'status_operacao')
    search_fields = ('id_planilha', 'cliente', 'container')
