"""Admin do Iscas Fast — parâmetros sistêmicos para o Superusuário GSInt.

O operador do dia a dia usa as telas do app; o /admin existe para o que o PRD
atribui ao superusuário: raio padrão, prazos de alerta e provedor de tiles.

Os models de log aparecem em modo leitura. `Movimentacao` é append-only
(ISC-RN-17): permitir edição aqui contornaria o ponto de escrita único e
reescreveria saldo derivado.
"""
from django.contrib import admin

from iscas.models.cadastro import Agente, Cliente, Deposito, ModeloEquipamento
from iscas.models.config import ConfiguracaoIscas, GeocodeCache
from iscas.models.custodia import Custodia, Movimentacao, MovimentacaoUnidade, Unidade
from iscas.models.operacao import (
    Atribuicao,
    AtribuicaoUnidade,
    ItemSolicitacao,
    Solicitacao,
    SolicitacaoEvento,
)


class _SomenteLeitura(admin.ModelAdmin):
    """Base para os registros de log: visíveis, nunca editáveis."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConfiguracaoIscas)
class ConfiguracaoIscasAdmin(admin.ModelAdmin):
    """Singleton: sem adicionar, sem remover — só editar o registro existente."""

    fieldsets = (
        ("Busca por proximidade", {"fields": ("raio_padrao_km",)}),
        (
            "Alertas do painel",
            {
                "fields": (
                    "dias_alerta_retornavel",
                    "saldo_minimo_alerta",
                    "horas_alerta_em_rota",
                )
            },
        ),
        (
            "Mapa",
            {
                "fields": ("tiles_url", "tiles_atribuicao"),
                "description": (
                    "A atribuição é obrigatória pela política de uso do "
                    "OpenStreetMap. Trocar de provedor é mudança destes dois campos."
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return not ConfiguracaoIscas.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ModeloEquipamento)
class ModeloEquipamentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "codigo", "tipo", "fabricante", "is_active")
    list_filter = ("tipo", "is_active")
    search_fields = ("nome", "codigo", "fabricante")

    def get_readonly_fields(self, request, obj=None):
        # ISC-RN-04: com histórico gravado, o tipo não muda nem pelo admin.
        if obj and obj.tem_movimentacao():
            return ("tipo",)
        return ()


@admin.register(Agente)
class AgenteAdmin(admin.ModelAdmin):
    list_display = ("nome", "cpf_mascarado", "telefone", "cidade", "uf", "geo_origem", "is_active")
    list_filter = ("is_active", "uf", "geo_origem")
    search_fields = ("nome", "telefone", "cidade")
    # O CPF cifrado e o hash não são editáveis à mão: a coerência entre os dois
    # é responsabilidade da property `cpf` (ISC-ADR-14).
    readonly_fields = ("cpf_cifrado", "cpf_hash", "geocodificado_em")

    @admin.display(description="CPF")
    def cpf_mascarado(self, obj):
        return obj.cpf_mascarado


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nome_razao_social", "documento_mascarado", "cidade", "uf", "geo_origem", "is_active")
    list_filter = ("is_active", "uf", "geo_origem")
    search_fields = ("nome_razao_social", "documento", "cidade")
    readonly_fields = ("geocodificado_em",)

    @admin.display(description="Documento")
    def documento_mascarado(self, obj):
        return obj.documento_mascarado


@admin.register(Deposito)
class DepositoAdmin(admin.ModelAdmin):
    list_display = ("nome", "cidade", "uf", "is_active")
    search_fields = ("nome", "cidade")


@admin.register(Custodia)
class CustodiaAdmin(_SomenteLeitura):
    list_display = ("__str__", "tipo", "is_active")
    list_filter = ("tipo",)


@admin.register(Unidade)
class UnidadeAdmin(_SomenteLeitura):
    """Leitura apenas: os ponteiros são escritos por registrar_movimentacao()."""

    list_display = ("identificador", "modelo", "custodia_atual", "custodia_desde")
    list_filter = ("modelo", "identificador_gerado")
    search_fields = ("identificador",)


@admin.register(Movimentacao)
class MovimentacaoAdmin(_SomenteLeitura):
    list_display = ("id", "tipo", "origem", "destino", "ocorrido_em", "autor")
    list_filter = ("tipo", "motivo_baixa")
    search_fields = ("nota_fiscal", "lote", "justificativa")
    date_hierarchy = "ocorrido_em"


@admin.register(MovimentacaoUnidade)
class MovimentacaoUnidadeAdmin(_SomenteLeitura):
    list_display = ("movimentacao", "unidade")
    search_fields = ("unidade__identificador",)


@admin.register(Solicitacao)
class SolicitacaoAdmin(_SomenteLeitura):
    list_display = ("id", "cliente", "status", "aberta_em", "aberta_por")
    list_filter = ("status",)
    date_hierarchy = "aberta_em"


@admin.register(Atribuicao)
class AtribuicaoAdmin(_SomenteLeitura):
    list_display = ("id", "solicitacao", "agente", "status", "entregue_em")
    list_filter = ("status",)


@admin.register(AtribuicaoUnidade)
class AtribuicaoUnidadeAdmin(_SomenteLeitura):
    list_display = ("unidade", "atribuicao", "reservada_em", "liberada_em")


@admin.register(ItemSolicitacao)
class ItemSolicitacaoAdmin(_SomenteLeitura):
    list_display = ("solicitacao", "modelo", "quantidade")


@admin.register(SolicitacaoEvento)
class SolicitacaoEventoAdmin(_SomenteLeitura):
    list_display = ("solicitacao", "atribuicao", "status_anterior", "status_novo", "autor", "created_at")


@admin.register(GeocodeCache)
class GeocodeCacheAdmin(admin.ModelAdmin):
    list_display = ("endereco_normalizado", "latitude", "longitude", "provedor", "consultado_em")
    search_fields = ("endereco_normalizado",)
    readonly_fields = ("endereco_hash", "consultado_em")
