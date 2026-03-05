from django.contrib import admin
from .models import (
    registrodeagenteacompanhamento,
    registroacompanhamento,
    registroacompanhamentoagente,
    registroderesposavelagenteacompanhamento,
    Cliente,
    TipoServico,
    RequisicaoSolicitacao,
    FranquiaAgente,
    Missao
)
from django.db.models import Count

# ======================================================
# Agentes Cadastrados
# ======================================================
@admin.register(registrodeagenteacompanhamento)
class RegistroDeAgenteAcompanhamentoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nome',
        'cpf',
        'banco',
        'tipo_conta',
        'pix',
        'criado_em',
    )

    list_display_links = ('id', 'nome')

    search_fields = (
        'nome',
        'cpf',
        'pix',
        'banco',
        'agencia',
        'conta',
    )

    list_filter = (
        'banco',
        'tipo_conta',
        'criado_em',
    )

    ordering = ('-criado_em',)

    readonly_fields = (
        'criado_em',
        'atualizado_em',
    )
    fieldsets = (
        ('Dados do Agente', {
            'fields': (
                'nome',
                'cpf',
            )
        }),

        ('Dados Bancários / Pix', {
            'fields': (
                'pix',
                'banco',
                'agencia',
                'conta',
                'tipo_conta',
            )
        }),

        ('Controle', {
            'fields': (
                'nome_user',
                'criado_em',
                'atualizado_em',
            )
        }),
    )

# ======================================================
# Responsável Agentes Cadastrados
# ======================================================
@admin.register(registroderesposavelagenteacompanhamento)
class RegistroDeResponsavelAgenteAcompanhamentoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nome',
    )

    list_display_links = ('id', 'nome')

    search_fields = (
        'nome',
    )

    ordering = ('-criado_em',)

    readonly_fields = (
        'criado_em',
        'atualizado_em',
    )
    fieldsets = (
        ('Dados do Agente', {
            'fields': (
                'nome',
            )
        }),

        ('Controle', {
            'fields': (
                'nome_user',
                'criado_em',
                'atualizado_em',
            )
        }),
    )

# ======================================================
# ACOMPANHAMENTO (MASTER)
# ======================================================
@admin.register(registroacompanhamento)
class RegistroAcompanhamentoAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "requisicao_solicitacao",
        "cliente",
        "tipo_servico",
        "status",
        "status_acompanhamento",
        "valor_contrato",
        "lucro_total",
        "validar_acompanhamento",
        "validado_cliente",
        "validar_pagamento",
        "is_reuso",
        "criado_em",
        "tempo_criacao_desde_requisicao_fmt",
    )

    list_filter = (
        "status",
        "status_acompanhamento",
        "validar_acompanhamento",
        "validado_cliente",
        "validar_pagamento",
        "tipo_servico",
    )

    search_fields = (
        "id",
        "requisicao_solicitacao",
        "cliente__nome",
        "nf",
        "origem",
        "destino",
    )

    readonly_fields = (
        "lucro_total",
        "botao_panico",
        "criado_em",
        "comboio",
        "quantidade_veiculos_comboio",
        "nome_user",
        "tipo_servico",
        "tempo_criacao_desde_requisicao",
        "tempo_criacao_desde_requisicao_fmt",
    )

    fieldsets = (
        ("Informações Principais", {
            "fields": (
                "cliente",
                "tipo_servico",
                "comboio",
                "quantidade_veiculos_comboio",
                "origem",
                "latitude_origem",
                "longitude_origem",
                "raio_cerca",
                "destino",
            )
        }),

        ("Financeiro", {
            "fields": (
                "valor_contrato",
                "lucro_total",
            )
        }),

        ("Faturamento", {
            "fields": (
                "status",
                "status_acompanhamento",
                "nf",
            )
        }),

        ("Validações", {
            "fields": (
                "botao_panico",
                "validar_acompanhamento",
                "validado_cliente",
                "validar_pagamento",
                "is_reuso",
            )
        }),

        ("Tempo de Criação", {
            "fields": (
                "tempo_criacao_desde_requisicao_fmt",
                "tempo_criacao_desde_requisicao",
            )
        }),

        ("Observações / Auditoria", {
            "fields": (
                "ocorrencia",
                "nome_user",
                "criado_em",
            )
        }),
    )

    @admin.display(description="Tempo p/ criar (desde requisição)", ordering="tempo_criacao_desde_requisicao")
    def tempo_criacao_desde_requisicao_fmt(self, obj):
        """
        Exibe o DurationField em formato amigável: 2h 15m 03s
        """
        td = getattr(obj, "tempo_criacao_desde_requisicao", None)
        if not td:
            return "-"
        total = int(td.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h}h {m}m {s}s"

    def get_readonly_fields(self, request, obj=None):
        """
        NF só pode ser editada quando status = faturado
        """
        readonly = list(self.readonly_fields)

        if obj and obj.status != "faturado":
            readonly.append("nf")

        return readonly

    def save(self, *args, **kwargs):
        if self.pk:
            original = registroacompanhamento.objects.get(pk=self.pk)
            self.botao_panico = original.botao_panico
        super().save(*args, **kwargs)

# ======================================================
# AGENTES DO ACOMPANHAMENTO
# ======================================================
@admin.register(registroacompanhamentoagente)
class RegistroAcompanhamentoAgenteAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "acompanhamento",
        "agente",
        "responsavel_agente",
        "valor_agente",
        "bancario",
        "criado_em",
    )

    list_filter = (
        "bancario",
        "franquia",
        "agente",
    )

    search_fields = (
        "id",
        "agente__nome",
        "responsavel_agente",
        "placa_agente",
        "placa_motorista",
    )

    readonly_fields = (
        "km_total",
        "km_excedente",
        "horario_total",
        "horario_excedente",
        "tipo_agente",
        "valor_agente",
        "criado_em",
    )

    fieldsets = (
        ("Vínculo", {
            "fields": (
                "acompanhamento",
                "tipo_agente",
                "responsavel_agente",
                "agente",
                "franquia",
            )
        }),

        ("Veículo / Motorista", {
            "fields": (
                "placa_agente",
                "motorista",
                "placa_motorista",
            )
        }),

        ("Deslocamento", {
            "fields": (
                "km_inicio",
                "km_final",
                "km_total",
                "km_excedente",
            )
        }),

        ("Horários", {
            "fields": (
                "data_solicitada",
                "horario_solicitado",
                "data_inicio",
                "horario_inicio",
                "data_finalizacao",
                "horario_finalizacao",
                "horario_total",
                "horario_excedente",
            )
        }),

        ("Valores", {
            "fields": (
                "pedagio",
                "valor_agente",
            )
        }),

        ("Pagamento Bancário", {
            "fields": (
                "bancario",
                "pix",
                "banco",
                "agencia",
                "conta",
                "tipo_conta",
                "nome_completo_conta",
                "cpf_conta",
            )
        }),

        ("Auditoria", {
            "fields": (
                "criado_em",
            )
        }),
    )


# ------------------------------------------------------
#             Novo Acompanhamento
# ------------------------------------------------------

@admin.register(FranquiaAgente)
class FranquiaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'id_externo',
        'valor_acionamento',
        'nome',
        'franquia_km',
        'franquia_horas',
        'valor_km_excedente',
        'valor_horas_excedente',
    )
    list_filter = ('criado_em',)
    search_fields = ('id', 'id_externo', 'valor_acionamento', 'nome_user', 'nome', 'franquia_km', 'franquia_horas', 'valor_km_excedente', 'valor_horas_excedente')
    readonly_fields = ('id', 'id_externo', 'valor_acionamento', 'nome_user', 'nome', 'franquia_km', 'franquia_horas', 'valor_km_excedente', 'valor_horas_excedente',)

    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['id', 'id_externo', 'comercial', 'nome', 'cnpj', 'ativo', 'sincronizado_em']
    search_fields = ['nome', 'cnpj']
    list_filter = ['ativo']
    fildsets = [ 'comercial']
    readonly_fields = ['id_externo', 'nome', 'cnpj', 'email', 'ativo', 'sincronizado_em', 'criado_em']
    
    def has_add_permission(self, request):
        return False  # Não pode adicionar pelo admin
    
    def has_delete_permission(self, request, obj=None):
        return False  # Não pode deletar pelo admin
    
    def has_change_permission(self, request, obj=None):
        return True  # Pode visualizar

@admin.register(TipoServico)
class TipoServicoAdmin(admin.ModelAdmin):
    list_display = ['id', 'id_externo', 'cliente', 'codigo', 'ativo', 'valor_acionamento']
    list_filter = ['cliente', 'codigo', 'ativo']
    search_fields = ['cliente__nome', 'codigo']
    readonly_fields = [
        'id_externo', 'cliente', 'codigo', 'ativo',
        'valor_acionamento', 'franquia_km', 'franquia_horas',
        'valor_hora', 'valor_km', 'sincronizado_em'
    ]
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Missao)
class MissaoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        'id_externo',
        "nome",
        "cliente",
        "criado_por",
        "status",
        "criado_em",
        "atualizado_em",
    )
    list_filter = ("status", "cliente", "criado_em", "atualizado_em")
    search_fields = ("nome", "cliente__nome", "criado_por")
    ordering = ("-criado_em",)
    date_hierarchy = "criado_em"
    list_select_related = ("cliente",)

    readonly_fields = ("id_externo","nome", "cliente", "criado_por", "status", "criado_em", "atualizado_em")
    fieldsets = (
        ("Dados da Missão", {"fields": ("id_externo", "nome", "cliente", "criado_por")}),
        ("Status", {"fields": ("status",)}),
        ("Auditoria", {"fields": ("criado_em", "atualizado_em")}),
    )

    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method == "GET"

    def has_delete_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_save"] = False
        extra_context["show_save_and_continue"] = False
        extra_context["show_save_and_add_another"] = False
        extra_context["show_delete"] = False
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

@admin.register(RequisicaoSolicitacao)
class RequisicaoSolicitacaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'id_externo', 'requisicao_id_externo', 'missao', 'cliente', 'motorista', 'placa', 'data_agendamento', 'is_reuso', 'agente_nome_reuso', 'agente_placa_reuso', 'criado_em']
    list_filter = ['cliente', 'data_agendamento']
    search_fields = ['motorista', 'placa', 'cliente__nome']
    
    # Campos do GSAcionamento são readonly, campos internos são editáveis
    readonly_fields = [
        'id_externo', 'requisicao_id_externo', 'missao', 'cliente', 'tipo_servico',
        'campo_personalizado_titulo', 'campo_personalizado_valor',
        'origem', 'destino',
        'motorista', 'placa', 'comboio', 'quantidade_veiculos_comboio', 'data_agendamento', 'horario_agendamento',
        'nome_user', 'sincronizado_em', 'criado_em'
    ]
    
    # ocorrencia e atualizado_em podem ser editados
    fieldsets = (
        ('Dados do GSAcionamento (Somente Leitura)', {
            'fields': (
                'id_externo', 'requisicao_id_externo', 'missao', 'cliente', 'tipo_servico', 'nome_user',
                'origem', 'destino',
                'motorista', 'placa', 'comboio', 'quantidade_veiculos_comboio', 'data_agendamento', 'horario_agendamento',
                'campo_personalizado_titulo', 'campo_personalizado_valor',

                'is_reuso', 'agente_nome_reuso', 'agente_placa_reuso',
            )
        }),
        ('Campos Editáveis', {
            'fields': ('ocorrencia', 'solicitado', 'latitude_origem', 'longitude_origem',)
        }),
        ('Metadados', {
            'fields': ('sincronizado_em', 'criado_em'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Só cria via API
    
    def has_delete_permission(self, request, obj=None):
        return False