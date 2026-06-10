from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class TarefaInteligencia(models.Model):
    STATUS_CHOICES = [
        ('avaliar', 'Avaliar'),
        ('a_fazer', 'A Fazer'),
        ('em_progresso', 'Em Progresso'),
        ('validacao', 'Aguardando Validação'),
        ('concluido', 'Concluído'),
       
    ]

    DESTINADO_CHOICES = [
        ('desenvolvimento', 'Desenvolvimento'),
        ('inteligencia', 'Inteligência'),
    ]

    RESPONSAVEL_CHOICES = [
        ('analia', 'Anália'),
        ('eurico', 'Eurico'),
        ('fernanda', 'Fernanda'),
        ('gabriel', 'Gabriel'),
        ('joao', 'João'),
        ('julio', 'Julio'),
        ('murillo', 'Murillo'),
        ('kethleen', 'Kethleen'),
        ('nathalia', 'Nathalia'),
    ]
    
    COR_CHOICES = [
        ('azul', 'Azul'),
        ('verde', 'Verde'),
        ('amarelo', 'Amarelo'),
        ('laranja', 'Laranja'),
        ('vermelho', 'Vermelho'),
    ]
    
    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'),
        ('media', 'Média'),
        ('alta', 'Alta'),
        ('avaliar', 'Avaliar'),
    ]
    
    titulo = models.CharField(max_length=255, verbose_name='Título')
    descricao = models.TextField(blank=True, verbose_name='Descrição')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='avaliar', verbose_name='Status')
    destinado = models.CharField(max_length=25, choices=DESTINADO_CHOICES, default='inteligencia', verbose_name='Destinado')
    responsavel = models.CharField(max_length=50, choices=RESPONSAVEL_CHOICES, blank=True, null=True, verbose_name='Responsável')
    responsavel_cor = models.CharField(max_length=20, null=True, blank=True,default='azul', verbose_name='Cor do Responsável')
    data_criacao = models.DateField(auto_now_add=True, verbose_name='Data de Criação')
    data_conclusao = models.DateField(null=True, blank=True, verbose_name='Data de Conclusão')
    data_limite = models.DateField(null=True, blank=True, verbose_name='Prazo')
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default='avaliar', verbose_name='Prioridade')
    cor = models.CharField(max_length=20, choices=COR_CHOICES, default='azul', verbose_name='Cor')
    imagem = models.ImageField(upload_to='imagens/kanban/', null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name = 'Tarefa de Inteligência'
        verbose_name_plural = 'Tarefas de Inteligência'
        ordering = ['-data_criacao', '-id']

        
    def __str__(self):
        return f"INT-{self.id:03d} - {self.titulo}"
    
    @property
    def esta_atrasada(self):
        """Verifica se a tarefa está atrasada"""
        if self.status == 'concluido' or not self.data_limite:
            return False
        return timezone.now().date() > self.data_limite
