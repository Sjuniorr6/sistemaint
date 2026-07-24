from django.contrib import admin
from django.utils.html import format_html

from . import models


def _fmt_duracao(delta):
    """Formata um timedelta como '2d 03:15' / '03:15' — legível na listagem."""
    if delta is None:
        return "—"
    total = int(delta.total_seconds())
    sinal = "-" if total < 0 else ""
    total = abs(total)
    dias, resto = divmod(total, 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    if dias:
        return f"{sinal}{dias}d {horas:02d}:{minutos:02d}"
    return f"{sinal}{horas:02d}:{minutos:02d}"


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


class PassagemSetorInline(admin.TabularInline):
    """SLA por setor no próprio chamado (somente leitura — vem do fluxo)."""

    model = models.PassagemSetor
    extra = 0
    can_delete = False
    fields = (
        "setor",
        "chegou_em",
        "aceito_em",
        "aceito_por",
        "finalizado_em",
        "finalizado_por",
        "acao_saida",
        "espera_fmt",
        "trabalho_fmt",
        "total_fmt",
    )
    readonly_fields = fields

    @admin.display(description="Espera")
    def espera_fmt(self, obj):
        return _fmt_duracao(obj.espera)

    @admin.display(description="Trabalho")
    def trabalho_fmt(self, obj):
        return _fmt_duracao(obj.trabalho)

    @admin.display(description="Total")
    def total_fmt(self, obj):
        return _fmt_duracao(obj.total)

    def has_add_permission(self, request, obj=None):
        return False


class TratativaEquipamentoInline(admin.TabularInline):
    """Tratativas por equipamento (laboratório + comercial) no chamado."""

    model = models.TratativaEquipamento
    extra = 0
    can_delete = False
    fields = ("numero_equipamento", "tratativa", "tratativa_comercial", "custo")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class ContatoExpedicaoInline(admin.TabularInline):
    """Tentativas de contato da Expedição com o cliente (somente leitura)."""

    model = models.ContatoExpedicao
    extra = 0
    can_delete = False
    fields = (
        "criado_em",
        "nome_contato",
        "telefone",
        "tratativa",
        "codigo_rastreio",
        "registrado_por",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class chamadoadmin(admin.ModelAdmin):
    list_display = (
        "protocolo", "cliente", "categoria", "status", "responsavel",
        "termo_link", "valor_faturamento", "nota_fiscal", "aberto_em",
    )
    list_filter = ("status", "categoria")
    search_fields = ("protocolo", "cliente__nome", "numero_equipamento")
    date_hierarchy = "aberto_em"

    @admin.display(description="Termo de substituição")
    def termo_link(self, obj):
        """Link para baixar o termo (PDF) anexado pelo Comercial na finalização."""
        if not obj.termo_substituicao:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            '<i class="bi bi-file-earmark-pdf"></i> Baixar PDF</a>',
            obj.termo_substituicao.url,
        )
    inlines = [
        PassagemSetorInline,
        ContatoExpedicaoInline,
        TratativaEquipamentoInline,
        ChamadoEventoInline,
    ]
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


class passagemsetoradmin(admin.ModelAdmin):
    """SLA por setor — visão analítica (uso interno; não aparece no fluxo)."""

    list_display = (
        "chamado",
        "setor",
        "chegou_em",
        "aceito_em",
        "finalizado_em",
        "espera_fmt",
        "trabalho_fmt",
        "total_fmt",
        "aceito_por",
        "finalizado_por",
    )
    list_filter = ("setor", "acao_saida")
    search_fields = ("chamado__protocolo",)
    date_hierarchy = "chegou_em"
    list_select_related = ("chamado", "aceito_por", "finalizado_por")

    @admin.display(description="Espera (chegada→aceite)")
    def espera_fmt(self, obj):
        return _fmt_duracao(obj.espera)

    @admin.display(description="Trabalho (aceite→saída)")
    def trabalho_fmt(self, obj):
        return _fmt_duracao(obj.trabalho)

    @admin.display(description="Total (chegada→saída)")
    def total_fmt(self, obj):
        return _fmt_duracao(obj.total)

    # Os dados vêm do fluxo: read-only, sem criação/edição manual.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class tratativaequipamentoadmin(admin.ModelAdmin):
    list_display = (
        "chamado",
        "numero_equipamento",
        "custo",
        "criado_em",
    )
    list_filter = ("custo",)
    search_fields = ("chamado__protocolo", "numero_equipamento")


class contatoexpedicaoadmin(admin.ModelAdmin):
    list_display = (
        "chamado",
        "nome_contato",
        "telefone",
        "codigo_rastreio",
        "registrado_por",
        "criado_em",
    )
    search_fields = ("chamado__protocolo", "nome_contato", "codigo_rastreio")
    date_hierarchy = "criado_em"
    list_select_related = ("chamado", "registrado_por")


admin.site.register(models.Chamado, chamadoadmin)
admin.site.register(models.ChamadoEvento, chamadoeventoadmin)
admin.site.register(models.PassagemSetor, passagemsetoradmin)
admin.site.register(models.TratativaEquipamento, tratativaequipamentoadmin)
admin.site.register(models.ContatoExpedicao, contatoexpedicaoadmin)
