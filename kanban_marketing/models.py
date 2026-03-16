from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class TarefaMarketing(models.Model):
    # Status típicos de um time de marketing
    STATUS_CHOICES = [
        ('briefing', 'Briefing/Ideia'),
        ('em_producao', 'Em Produção'),
        ('concluido', 'Concluído'),
        ('publicado', 'Publicado'),
    ]

    # Time de Marketing pode ter um responsável específico ou ser atribuído ao time geral, dependendo da estrutura da agência
    RESPONSAVEL_CHOICES = [
        ('felipe nery', 'Felipe Nery'),
    ]
    
    # Cores (Mantemos a lógica de cores para o Kanban)
    COR_CHOICES = [
        ('azul', 'Azul'), ('verde', 'Verde'), ('amarelo', 'Amarelo'),
        ('laranja', 'Laranja'), ('vermelho', 'Vermelho'),
    ]
    
    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'), ('media', 'Média'), ('alta', 'Alta'),
    ]
    
    titulo = models.CharField(max_length=255, verbose_name='Título da Campanha')
    descricao = models.TextField(blank=True, verbose_name='Descrição/Briefing')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='briefing', verbose_name='Status')
    responsavel = models.CharField(max_length=50, choices=RESPONSAVEL_CHOICES, blank=True, null=True, verbose_name='Responsável')
    
    data_criacao = models.DateField(auto_now_add=True, verbose_name='Data de Criação')
    data_conclusao = models.DateField(null=True, blank=True, verbose_name='Data de Conclusão')
    data_limite = models.DateField(null=True, blank=True, verbose_name='Prazo Final')
    
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, verbose_name='Prioridade')
    cor = models.CharField(max_length=20, choices=COR_CHOICES, default='azul', verbose_name='Cor')
    briefing_aprovado = models.BooleanField(default=False, verbose_name='Briefing Aprovado')
    imagem = models.ImageField(upload_to='imagens/marketing/', null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name = 'Tarefa de Marketing'
        verbose_name_plural = 'Tarefas de Marketing'
        ordering = ['-data_criacao', '-id']

    def __str__(self):
        return self.titulo

    @property
    def esta_atrasada(self):
        if self.data_limite and self.status != 'publicado':
            return timezone.now().date() > self.data_limite
        return False