from django.contrib import admin
from .models import (
    FuncionarioAdministrativo,
    CategoriaTarefaAdministrativa,
    TarefaModeloAdministrativa,
    ExecucaoTarefaAdministrativa,
    ComentarioTarefa,
    BlocoSemanal,
    ItemBlocoSemanal,
)


@admin.register(FuncionarioAdministrativo)
class FuncionarioAdministrativoAdmin(admin.ModelAdmin):
    list_display  = ['nome', 'usuario', 'perfil', 'ativo']
    list_filter   = ['perfil', 'ativo']
    search_fields = ['nome', 'usuario__username']


@admin.register(CategoriaTarefaAdministrativa)
class CategoriaTarefaAdministrativaAdmin(admin.ModelAdmin):
    list_display  = ['nome', 'cor', 'ativo']
    list_filter   = ['ativo']
    search_fields = ['nome']


@admin.register(TarefaModeloAdministrativa)
class TarefaModeloAdministrativaAdmin(admin.ModelAdmin):
    list_display  = ['titulo', 'dia_da_semana', 'periodo', 'tipo_controle', 'responsavel', 'ativo']
    list_filter   = ['dia_da_semana', 'periodo', 'tipo_controle', 'ativo', 'responsavel']
    search_fields = ['titulo']
    ordering      = ['dia_da_semana', 'periodo', 'ordem']


class ComentarioTarefaInline(admin.TabularInline):
    model   = ComentarioTarefa
    extra   = 1
    fields  = ['autor', 'conteudo', 'is_done']
    readonly_fields = ['criado_em']


@admin.register(ExecucaoTarefaAdministrativa)
class ExecucaoTarefaAdministrativaAdmin(admin.ModelAdmin):
    list_display    = ['tarefa_modelo', 'semana_iso', 'ano', 'status', 'is_done']
    list_filter     = ['status', 'ano', 'semana_iso']
    search_fields   = ['tarefa_modelo__titulo']
    readonly_fields = ['atualizado_em', 'atualizado_por', 'concluido_em']
    inlines         = [ComentarioTarefaInline]


@admin.register(ComentarioTarefa)
class ComentarioTarefaAdmin(admin.ModelAdmin):
    list_display  = ['autor', 'execucao', 'conteudo', 'criado_em', 'is_done']
    list_filter   = ['is_done', 'autor']
    search_fields = ['conteudo']
    readonly_fields = ['criado_em']


class ItemBlocoSemanalInline(admin.TabularInline):
    model  = ItemBlocoSemanal
    extra  = 1
    fields = ['conteudo', 'is_fixo', 'is_done', 'ordem']


@admin.register(BlocoSemanal)
class BlocoSemanalAdmin(admin.ModelAdmin):
    list_display = ['tipo', 'semana_iso', 'ano']
    list_filter  = ['tipo', 'ano']
    inlines      = [ItemBlocoSemanalInline]


@admin.register(ItemBlocoSemanal)
class ItemBlocoSemanalAdmin(admin.ModelAdmin):
    list_display  = ['conteudo', 'bloco', 'is_fixo', 'is_done', 'ordem']
    list_filter   = ['is_fixo', 'is_done']
    search_fields = ['conteudo']