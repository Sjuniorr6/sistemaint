from django.contrib import admin
from .models import TarefaInteligencia

@admin.register(TarefaInteligencia)
class TarefaInteligenciaAdmin(admin.ModelAdmin):
    list_display = ('id', 'titulo', 'status', 'data_criacao', 'data_limite')
    search_fields = ('titulo', 'descricao')

# Register your models here.
