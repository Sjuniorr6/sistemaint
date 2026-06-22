from django.contrib import admin

from . import models


class responsavelagenteadmin(admin.ModelAdmin):
    list_display = ("nome", "criado_em")
    search_fields = ("nome",)


class clienteadmin(admin.ModelAdmin):
    list_display = ("nome_empresa", "cnpj", "criado_em")
    search_fields = ("nome_empresa", "cnpj")


class agenteadmin(admin.ModelAdmin):
    list_display = ("nome", "cpf", "tipo_conta", "banco", "criado_em")
    search_fields = ("nome", "cpf")
    filter_horizontal = ("clientes_vinculados",)


class franquiaagenteadmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "cliente",
        "valor_acionamento",
        "franquia_km",
        "escalonamento_automatico",
        "criado_em",
    )
    search_fields = ("nome", "cliente__nome_empresa")
    list_filter = ("escalonamento_automatico", "cliente")


admin.site.register(models.ResponsavelAgente, responsavelagenteadmin)
admin.site.register(models.Cliente, clienteadmin)
admin.site.register(models.Agente, agenteadmin)
admin.site.register(models.FranquiaAgente, franquiaagenteadmin)