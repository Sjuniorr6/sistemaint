from django.db import models
from acompanhamento.models import Clientes   


class Formulario(models.Model):
    razao_social = models.CharField(max_length=100)
    cnpj = models.CharField(max_length=14)
    inicio_de_contrato = models.DateField()
    vigencia = models.CharField(max_length=14)
    
    def __str__(self):
        return self.razao_social

class Faturamento(models.Model):
    reajuste_choice = [
        ('RENOVADO', 'RENOVADO'),
        ('REAJUSTADO', 'REAJUSTADO'),
        ('*REAJUSTE*', '*REAJUSTE*'),
        ('OK', 'OK'),
    ] 
    contrato_choices = [
        ('SIM', 'SIM'),
        ('NÃO', 'NÃO'),
    ]
    temp_choices = [ 
        ('4', '4'),
        ('6', '6'),
        ('12', '12'),
        ('24', '24'),
        ('36', '36'),
        ('48', '48'),
        ('60', '60'),
        ('72', '72'),
    ]
    comercial_choices = [
        ('Marcio', 'Marcio'),
        ('Cido', 'Cido'),
        ('Daniel', 'Daniel'),
        ('Fabio', 'Fabio'),
        ('Alison', 'Alison'),
        ('Marcia', 'Marcia'),
        ('Mayra', 'Mayra'),
        ('Penha', 'Penha'),
        ('Golden', 'Golden'),
        ('Rubens', 'Rubens'),
        ('Sheyla', 'Sheyla'),
    ]    
    tipo_documento_choices = [
        ('Recibo', 'Recibo'),
        ('NF', 'NF'),
    ]
    empresa_choices =[
        ('Nife - ita', 'Nife - ita'),
    ]
    forma_ágamento_choices = [
        ('Boleto', 'Boleto'),
        ('Transferência', 'Transferência'),
    ]
    status2_choices = [
        ('Recebido', 'Recebido'),
        ('A Receber', 'A Receber'),
    ]
    situacao_choices = [ 
        ('OK', 'OK'),
        ('Em dia', 'Em dia'),
        ('Vence em breve', 'Vence em breve'),
        ('Vence Hoje', 'Vence Hoje'),
        ('Vencida', 'Vencida'),
        
    ]
    
    
    faturamento = models.DateField(null=True, blank=True)
    emissao = models.DateField(null=True, blank=True)
    reajustado = models.CharField(max_length=100, choices=reajuste_choice,null=True, blank=True)
    reajuste = models.DateField(null=True, blank=True)
    contrato =models.CharField(max_length=100,choices=contrato_choices,null=True, blank=True)
    tempo = models.CharField(max_length=100,choices=temp_choices,null=True, blank=True)
    comercial = models.CharField(max_length=100,choices=comercial_choices,null=True, blank=True)
    n_contrato =models.CharField(max_length=100,null=True, blank=True)
    tipo_documento = models.CharField(max_length=100,choices=tipo_documento_choices,null=True, blank=True)
    sistema_omie = models.CharField(max_length=100,null=True, blank=True)
    empresa = models.CharField(max_length=100,choices=empresa_choices,null=True, blank=True)
    cliente = models.CharField(max_length=100, null=True, blank=True)
    nome_fantasia = models.CharField(max_length=100,null=True, blank=True)
    email = models.EmailField(max_length=100,null=True, blank=True)
    tipo_servico = models.CharField(max_length=100,null=True, blank=True)
    descricao = models.TextField(null=True, blank=True)
    forma_pagamento = models.CharField(max_length=100,choices=forma_ágamento_choices,null=True, blank=True)
    vecimento_documento = models.DateField(null=True, blank=True)
    
    valor_bruto = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    coluna1 =models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    valor_liquido = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    juros = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    data_pgto = models.DateField(null=True, blank=True)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    status2 =models.CharField(max_length=100,choices=status2_choices,null=True, blank=True)
    situacao = models.CharField(max_length=100,choices=situacao_choices,null=True, blank=True)
    
    def __str__(self):
        return f"{self.cliente} - {self.n_contrato}" if self.cliente and self.n_contrato else f"Faturamento {self.id}"