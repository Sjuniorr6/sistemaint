from django.db import models
from django.conf import settings  # Importa as configurações, inclusive o AUTH_USER_MODEL
from decimal import Decimal
# models.py
import datetime
from django.db import models
from django.conf import settings
class horas(models.Model):
    STATUS_CHOICES = [
        ('Pendente', 'Pendente'),
        ('Aprovado', 'Aprovado'),
    ]

    status_choice = models.CharField(
        choices=STATUS_CHOICES,
        max_length=50,
        null=True,
        blank=True
    )

    funcionario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    comprovante1 = models.ImageField(upload_to='imagens/', null=True, blank=True)
    comprovante2 = models.ImageField(upload_to='imagens/', null=True, blank=True)

    hora_inicial = models.DateTimeField(null=True, blank=True)
    hora_final   = models.DateTimeField(null=True, blank=True)

    motivo = models.CharField(max_length=50, null=True, blank=True)

    total = models.CharField(max_length=10, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.hora_inicial and self.hora_final and self.hora_final > self.hora_inicial:
            diff: timedelta = self.hora_final - self.hora_inicial
            total_seconds = int(diff.total_seconds())

            horas = total_seconds // 3600
            minutos = (total_seconds % 3600) // 60

            self.total = f"{horas:02d}:{minutos:02d}"
        else:
            self.total = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f'Horas extras - {self.funcionario}'
