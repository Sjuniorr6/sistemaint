from django.core.exceptions import ValidationError
from django.db import models


class ResponsavelAgente(models.Model):
    nome = models.CharField(max_length=120, verbose_name="Nome")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Responsável de Agente"
        verbose_name_plural = "Responsáveis de Agente"
        ordering = ["-criado_em"]

    def clean(self):
        super().clean()
        self.nome = (self.nome or "").strip()
        if not self.nome:
            raise ValidationError({"nome": "O nome não pode ficar vazio."})

    def __str__(self):
        return self.nome