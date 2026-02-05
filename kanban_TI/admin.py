from django.contrib import admin
from .models import TarefaTI
from django.utils.html import format_html

@admin.register(TarefaTI)
class TarefaTIAdmin(admin.ModelAdmin):
    # Colunas que aparecerão na listagem
    list_display = ('get_codigo', 'titulo', 'status', 'responsavel', 'prioridade', 'data_limite', 'status_atraso')
    
    # Filtros na lateral direita
    list_filter = ('status', 'prioridade', 'responsavel', 'data_criacao')
    
    # Campos para pesquisa
    search_fields = ('titulo', 'descricao', 'id')
    
    # Organização do formulário de edição
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('titulo', 'descricao', 'usuario')
        }),
        ('Controle de Fluxo', {
            'fields': (('status', 'prioridade'), ('responsavel', 'responsavel_cor'))
        }),
        ('Prazos e Visual', {
            'fields': (('data_limite', 'data_conclusao'), 'cor', 'imagem')
        }),
    )

    # Método para exibir o ID formatado (Ex: INT-001)
    def get_codigo(self, obj):
        return f"INT-{obj.id:03d}"
    get_codigo.short_description = 'Código'

    # Método visual para mostrar se está atrasado direto na lista
    def status_atraso(self, obj):
        if obj.esta_atrasada:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ Atrasada</span>')
        if obj.status == 'concluido':
            return format_html('<span style="color: green;">✅ Concluída</span>')
        return "No prazo"
    status_atraso.short_description = 'Status de Prazo'

    # Define automaticamente o usuário logado como dono da tarefa ao criar pelo Admin
    def save_model(self, request, obj, form, change):
        if not obj.usuario:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)