from django.db import models 
class Cliente(models.Model):
    vigencia_tipo = [

        ('' , ''),
        ('12' , '12'),
        ('24' , '24' ),
        ('36' , '36'),
        ('48' , '48'),
    ]
    status = [

        ('Ativo' , 'Ativo'),
        ('Inativo' , 'Inativo'),
    ]
    equipamentos = [

        ("Isca","Isca"),
        ("Rastreador","Rastreador"),
        ("Tetis","Tetis"),
    ]
    
    nome = models.CharField(max_length=100)
    endereco = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=50)
    inicio_de_contrato = models.CharField(max_length=14)
    vigencia = models.CharField(choices=vigencia_tipo ,null=True,blank=True, max_length=50)
    termino = models.CharField(max_length=10,null=True,blank=True)
    equipamento = models.CharField(choices=equipamentos, max_length= 50, null=True, blank=False )
    quantidade = models.IntegerField(null=True, blank=True)
    def __str__(self):
        return self.nome
    
