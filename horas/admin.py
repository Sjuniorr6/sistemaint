from django.contrib import admin
from .models import horas

@admin.register(horas)
class HorasAdmin(admin.ModelAdmin):
    list_display = ("id", "funcionario", "hora_inicial", "hora_final", "total", "status_choice")
    list_filter = ("status_choice", "funcionario")
    search_fields = ("funcionario__username", "motivo")
    ordering = ("-id",)
