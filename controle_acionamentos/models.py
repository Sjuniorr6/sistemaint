from django.core.exceptions import ValidationError
from django.db import models

from controle_acionamentos.services import validar_cnpj, validar_cpf, validar_cnh


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
    

class Agente(models.Model):
    class TipoConta(models.TextChoices):
        CORRENTE = "CORRENTE", "Corrente"
        POUPANCA = "POUPANCA", "Poupança"

    nome = models.CharField(max_length=120, verbose_name="Nome")
    cpf = models.CharField(max_length=14, unique=True, verbose_name="CPF")
    cnh = models.CharField(max_length=20, blank=True, verbose_name="CNH")
    chave_pix = models.CharField(max_length=140, blank=True, verbose_name="Chave PIX")
    banco = models.CharField(max_length=80, blank=True, verbose_name="Banco")
    tipo_conta = models.CharField(
        max_length=10,
        choices=TipoConta.choices,
        blank=True,
        verbose_name="Tipo de conta",
    )
    agencia = models.CharField(max_length=10, blank=True, verbose_name="Agência")
    conta = models.CharField(max_length=20, blank=True, verbose_name="Conta")
    clientes_vinculados = models.ManyToManyField(
        Cliente,
        blank=True,
        related_name="agentes_vinculados",
        verbose_name="Clientes vinculados",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"
        ordering = ["-criado_em"]

    def clean(self):
        super().clean()
        self.nome = (self.nome or "").strip()
        if not self.nome:
            raise ValidationError({"nome": "O nome não pode ficar vazio."})

        self.cpf = "".join(ch for ch in (self.cpf or "") if ch.isdigit())
        if not validar_cpf(self.cpf):
            raise ValidationError({"cpf": "CPF inválido."})

        self.cnh = "".join(ch for ch in (self.cnh or "") if ch.isdigit())
        if self.cnh and not validar_cnh(self.cnh):
            raise ValidationError({"cnh": "CNH inválida."})

    def __str__(self):
        return self.nome