from django.contrib import admin
from . import models

# Configuração para exibir os modelos no admin

# Admin personalizado para o modelo Requisicoes
class RequisicoesAdmin(admin.ModelAdmin):
    list_display = (
        'nome', 'endereco', 'cnpj', 'contrato', 'inicio_de_contrato', 
        'vigencia', 'data', 'motivo', 'envio', 'comercial', 'tipo_produto',
        'carregador', 'cabo', 'tipo_fatura', 'valor_unitario', 'valor_total',
        'forma_pagamento', 'observacoes', 'TP', 'status_faturamento', 
        'id_equipamentos', 'numero_de_equipamentos', 'aos_cuidados', 'iccid',
        'kanban_status', 'prioridade'
    )
    search_fields = ('nome',)  # Campo de pesquisa para o admin
    list_filter = ('kanban_status', 'prioridade', 'status')

admin.site.register(models.Requisicoes, RequisicoesAdmin)


# Admin para KanbanHistorico
class KanbanHistoricoAdmin(admin.ModelAdmin):
    list_display = ('requisicao', 'usuario', 'status_anterior', 'status_novo', 'data_movimentacao')
    list_filter = ('status_anterior', 'status_novo', 'data_movimentacao')
    search_fields = ('requisicao__id', 'usuario__username')
    readonly_fields = ('requisicao', 'usuario', 'status_anterior', 'status_novo', 'data_movimentacao')
    
    def has_add_permission(self, request):
        # Não permite adicionar manualmente (apenas via signal)
        return False

admin.site.register(models.KanbanHistorico, KanbanHistoricoAdmin)


# Admin para KanbanAuditLog
class KanbanAuditLogAdmin(admin.ModelAdmin):
    list_display = ('requisicao', 'usuario', 'acao', 'coluna_origem', 'coluna_destino', 'quantidade_expedida', 'data_acao')
    list_filter = ('acao', 'coluna_origem', 'coluna_destino', 'data_acao')
    search_fields = ('requisicao__id', 'usuario__username', 'observacao')
    readonly_fields = ('requisicao', 'usuario', 'acao', 'coluna_origem', 'coluna_destino', 'quantidade_expedida', 'observacao', 'data_acao')
    
    def has_add_permission(self, request):
        # Não permite adicionar manualmente (apenas via código)
        return False

admin.site.register(models.KanbanAuditLog, KanbanAuditLogAdmin)


# Admin para AuditLog (Logs de Auditoria Completos)
class CampoAlteradoInline(admin.TabularInline):
    model = models.CampoAlterado
    extra = 0
    readonly_fields = ('nome_campo', 'valor_anterior', 'valor_novo')
    can_delete = False

class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('data_hora', 'acao', 'usuario_nome', 'content_type', 'object_id', 'status_anterior', 'status_novo', 'ip_address')
    list_filter = ('acao', 'content_type', 'data_hora', 'usuario')
    search_fields = ('usuario_nome', 'observacao', 'object_id')
    readonly_fields = ('content_type', 'object_id', 'acao', 'usuario', 'usuario_nome', 'data_hora', 
                       'status_anterior', 'status_novo', 'detalhes', 'observacao', 'ip_address')
    inlines = [CampoAlteradoInline]
    date_hierarchy = 'data_hora'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Apenas superusuários podem deletar logs
        return request.user.is_superuser

admin.site.register(models.AuditLog, AuditLogAdmin)


# Inline do Equipamfrom django.contrib import admin
from .models import ControleModel
from django.contrib import admin
from .models import ControleModel

class ControleModelAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'iccid_equipamento1', 'id_equipamento1', 'iccid_equipamento2', 'id_equipamento2', 
                    'iccid_equipamento3', 'id_equipamento3', 'iccid_equipamento4', 'id_equipamento4', 
                    'iccid_equipamento5', 'id_equipamento5', 'iccid_equipamento6', 'id_equipamento6', 
                    'iccid_equipamento7', 'id_equipamento7', 'iccid_equipamento8', 'id_equipamento8', 
                    'iccid_equipamento9', 'id_equipamento9', 'iccid_equipamento10', 'id_equipamento10', 'quantidade')

admin.site.register(ControleModel, ControleModelAdmin)
