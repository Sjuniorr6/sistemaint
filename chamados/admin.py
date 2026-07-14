from django.contrib import admin

from . import models


class ChamadoEventoInline(admin.TabularInline):
    """Log append-only exibido só para leitura no admin do Chamado (ADR-010)."""

    model = models.ChamadoEvento
    extra = 0
    can_delete = False
    fields = (
        "criado_em",
        "acao",
        "estado_origem",
        "estado_destino",
        "autor",
        "motivo",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class chamadoadmin(admin.ModelAdmin):
    list_display = ("protocolo", "cliente", "categoria", "status", "responsavel", "aberto_em")
    list_filter = ("status", "categoria")
    search_fields = ("protocolo", "cliente", "numero_equipamento")
    date_hierarchy = "aberto_em"
    inlines = [ChamadoEventoInline]
    # Fatos de abertura são imutáveis (RN-03): read-only no admin também.
    readonly_fields = (
        "protocolo",
        "cliente",
        "categoria",
        "numero_equipamento",
        "problema_relatado",
        "responsavel",
        "aberto_por",
        "aberto_em",
        "criado_em",
        "atualizado_em",
    )


class chamadoeventoadmin(admin.ModelAdmin):
    list_display = ("chamado", "acao", "estado_origem", "estado_destino", "autor", "criado_em")
    list_filter = ("acao", "estado_destino")
    search_fields = ("chamado__protocolo",)

    def has_change_permission(self, request, obj=None):
        return False  # append-only

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(models.Chamado, chamadoadmin)
admin.site.register(models.ChamadoEvento, chamadoeventoadmin)
