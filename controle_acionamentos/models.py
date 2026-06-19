from django.core.exceptions import ValidationError
from django.db import models

from controle_acionamentos.services import validar_cnpj


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
    
class Cliente(models.Model):
    nome_empresa = models.CharField(max_length=160, verbose_name="Nome da empresa")
    cnpj = models.CharField(max_length=18, unique=True, verbose_name="CNPJ")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["-criado_em"]

    def clean(self):
        super().clean()
        self.nome_empresa = (self.nome_empresa or "").strip()
        if not self.nome_empresa:
            raise ValidationError(
                {"nome_empresa": "O nome da empresa não pode ficar vazio."}
            )

        self.cnpj = "".join(ch for ch in (self.cnpj or "") if ch.isdigit())
        if not validar_cnpj(self.cnpj):
            raise ValidationError({"cnpj": "CNPJ inválido."})

    def __str__(self):
        return self.nome_empresa