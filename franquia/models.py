from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class registrodefranquia(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome da Franquia")
    valor_acionamento = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, verbose_name="Valor do Acionamento (R$)")

    franquia_km = models.PositiveIntegerField(blank=True, null=True, verbose_name="Franquia de KM")
    franquia_horas = models.PositiveIntegerField(blank=True, null=True, verbose_name="Franquia de Horas")


    valor_km_excedente = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, verbose_name="Valor de KM Excedentes (R$)")
    valor_horas_excedente = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, verbose_name="Valor de Horas Excedentes (R$)")

    # Nome do usuário que criou/atualizou a franquia
    nome_user = models.CharField(max_length=150, blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True) 

    class Meta:
        ordering = ['-criado_em']
        permissions = [
            ("view_listfranquia", "Pode visualizar lista de franquias"),
        ]

    def __str__(self):
        return f'Franquia #{self.id}'

