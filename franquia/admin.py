from django.contrib import admin
from . import models
from .models import registrodefranquia

@admin.register(registrodefranquia)
class RegistroFranquiaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nome',
        'franquia_km',
        'franquia_horas',
        'valor_km_excedente',
        'valor_horas_excedente',
    )
    search_fields = ('id', 'nome', 'franquia_km', 'franquia_horas', 'valor_km_excedente', 'valor_horas_excedente')
    list_filter = ('criado_em',)
