from django.contrib import admin
from django.utils.html import format_html
from .models import registrodemanutencao, ImagemRegistro, retorno


# Classe para personalizar o modelo registrodemanutencao
class RegistroDeManutencaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo_produto', 'motivo', 
                    'entregue_por_retirado_por', 'numero_equipamento', 'tratativa', 'imagem_display', 'quantidade',
                    
                     'data_criacao', 'status')
    search_fields = ('nome__nome',)  # Permite busca pelo nome do cliente relacionado
    list_filter = ( 'status',  'tratativa')  # Filtros no admin

    # Exibição da imagem como miniatura no admin
    def imagem_display(self, obj):
        if obj.imagem:
            return format_html('<img src="{}" style="width: 50px; height: auto;" />', obj.imagem.url)
        return "Sem imagem"

    imagem_display.short_description = "Imagem"

    # Personaliza a edição no admin
    fieldsets = (
        ("Informações Gerais", {
            'fields': ('nome', 'tipo_entrada', 'tipo_produto', 'motivo', 'tipo_customizacao',
                       'recebimento', 'entregue_por_retirado_por', 'id_equipamentos', 'quantidade')
        }),
        ("Detalhes da Manutenção", {
            # 'fields': ('faturamento', 'setor', 'customizacaoo', 'numero_equipamento', 'observacoes', 'tratativa', 'status')
            'fields': ('customizacaoo', 'numero_equipamento', 'observacoes', 'tratativa', 'status')
        }),
        ("Imagens", {
            'fields': ('imagem', 'imagem2')
        }),
    )

# Classe para personalizar o modelo ImagemRegistro
class ImagemRegistroAdmin(admin.ModelAdmin):
    list_display = ('registro', 'tipo_problema', 'id_equipamento', 'imagem_display')
    search_fields = ('registro__id', 'id_equipamento')
    list_filter = ('tipo_problema',)

    def imagem_display(self, obj):
        if obj.imagem:
            return format_html('<img src="{}" style="width: 50px; height: auto;" />', obj.imagem.url)
        return "Sem imagem"

    imagem_display.short_description = "Imagem"

# Classe para personalizar o modelo retorno
class RetornoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'produto', 'tipo_problema', 'imagem_display', 'id_equipamentos')
    search_fields = ('cliente__nome', 'produto__nome')
    list_filter = ('tipo_problema',)

    def imagem_display(self, obj):
        if obj.imagem:
            return format_html('<img src="{}" style="width: 50px; height: auto;" />', obj.imagem.url)
        return "Sem imagem"

    imagem_display.short_description = "Imagem"

# Registros no Django Admin
admin.site.register(registrodemanutencao, RegistroDeManutencaoAdmin)
admin.site.register(ImagemRegistro, ImagemRegistroAdmin)
admin.site.register(retorno, RetornoAdmin)
