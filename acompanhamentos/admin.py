from django.contrib import admin
from .models import (
    registrodeagenteacompanhamento,
    registrodeclienteacompanhamento,
    servicosacompanhamentos,
    registroacompanhamento,
    registroacompanhamentoagente,
    registroderesposavelagenteacompanhamento,
    AcompanhamentoLocalizacao
)


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
# Clientes Cadastrados
# ======================================================
@admin.register(registrodeclienteacompanhamento)
class RegistroClienteAcompanhamentoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nome',
        'cnpj',
        'email',
        'valor_acionamento',
        'nome_user',
        'criado_em',
    )

    search_fields = (
        'nome',
        'cnpj',
        'email',
    )

    list_filter = (
        'criado_em',
        'atualizado_em',
    )

    ordering = ('-criado_em',)

    readonly_fields = (
        'criado_em',
        'atualizado_em',
        'nome_user',
    )

    fieldsets = (
        ('Dados do Cliente', {
            'fields': (
                'nome',
                'cnpj',
                'email',
            )
        }),

        ('Valores Contratuais (Cliente)', {
            'description': 'Tabela de valores utilizada para cálculo automático do contrato.',
            'fields': (
                'valor_acionamento',
                'franquia_km',
                'valor_km_excedente',
                'franquia_horas',
                'valor_horas_excedente',
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

    def save_model(self, request, obj, form, change):
        if not obj.nome_user:
            obj.nome_user = request.user.get_full_name() or request.user.username
        super().save_model(request, obj, form, change)
 
# ======================================================
# Serviços Cadastrados
# ======================================================
@admin.register(servicosacompanhamentos)
class ServicosAcompanhamentosAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nomeclatura',
        'tipo',
        'agentes',
        'criado_em',
    )

    list_display_links = ('id', 'nomeclatura')

    search_fields = (
        'nomeclatura',
    )

    list_filter = (
        'tipo',
        'agentes',
        'criado_em',
    )

    ordering = ('-criado_em',)

    readonly_fields = (
        'criado_em',
        'atualizado_em',
    )

    fieldsets = (
        ('Dados do Serviço', {
            'fields': (
                'nomeclatura',
                'tipo',
                'agentes',
            )
        }),
        ('Controle', {
            'fields': (
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
        "cliente",
        "tipo_servico",
        "status",
        "valor_contrato",
        "lucro_total",
        "validar_acompanhamento",
        "validar_pagamento",
        "criado_em",
    )

    list_filter = (
        "status",
        "validar_acompanhamento",
        "validar_pagamento",
        "tipo_servico",
    )

    search_fields = (
        "id",
        "cliente__nome",
        "nf",
        "origem",
        "destino",
    )

    readonly_fields = (
        "lucro_total",
        "botao_panico",
        "criado_em",
    )

    fieldsets = (
        ("Informações Principais", {
            "fields": (
                "cliente",
                "tipo_servico",
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
                "nf",
            )
        }),

        ("Validações", {
            "fields": (
                "botao_panico",
                "validar_acompanhamento",
                "validar_pagamento",
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

# ======================================================
# ACOMPANHAMENTO PANICO
# ======================================================
# admin.py
from django.contrib import admin
from .models import AcompanhamentoLocalizacao

@admin.register(AcompanhamentoLocalizacao)
class AcompanhamentoLocalizacaoAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "acompanhamento",
        "origem",
        "is_panic",
        "panic_resolved",
        "resolved_at",
        "resolved_by",
        "agente",
        "usuario",
        "latitude",
        "longitude",
        "accuracy",
        "criado_em",
    )

    list_filter = (
        "is_panic",
        "panic_resolved",
        "origem",
        "criado_em",
    )

    search_fields = (
        "acompanhamento__id",
        "agente__nome",
        "usuario__username",
        "resolved_by__username",
        "origem",
    )

    ordering = ("-criado_em",)

    readonly_fields = (
        "acompanhamento",
        "agente",
        "usuario",
        "latitude",
        "longitude",
        "accuracy",
        "origem",
        "is_panic",
        "panic_resolved",
        "resolved_by",
        "resolved_at",
        "criado_em",
    )

    fieldsets = (
        ("Vínculo", {
            "fields": (
                "acompanhamento",
                "agente",
                "usuario",
                "origem",
            )
        }),

        ("Localização", {
            "fields": (
                "latitude",
                "longitude",
                "accuracy",
            )
        }),

        ("Pânico", {
            "fields": (
                "is_panic",
                "panic_resolved",
                "resolved_by",
                "resolved_at",
            )
        }),

        ("Auditoria", {
            "fields": (
                "criado_em",
            )
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
