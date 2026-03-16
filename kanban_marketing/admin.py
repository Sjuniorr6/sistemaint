from django.contrib import admin
from .models import TarefaMarketing

@admin.register(TarefaMarketing)
class TarefaMarketingAdmin(admin.ModelAdmin):
    # Colunas que aparecem na lista do Admin
    list_display = ('titulo', 'status', 'responsavel', 'prioridade', 'data_limite')
    
    # Filtros na lateral
    list_filter = ('status', 'prioridade', 'responsavel')
    
    # Campo de busca
    search_fields = ('titulo', 'descricao')