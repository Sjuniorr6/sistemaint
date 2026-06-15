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
        ('recusado', 'Recusado'),
    ]

    DESTINADO_CHOICES = [
        ('desenvolvimento', 'Desenvolvimento'),
        ('inteligencia', 'Inteligência'),
        ('TI', 'T.I'),
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
    # Data e hora reais de abertura (data_criacao é só data). Nulo para tickets
    # antigos criados antes deste campo — o template faz fallback para data_criacao.
    criado_em = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name='Criado em')
    data_conclusao = models.DateField(null=True, blank=True, verbose_name='Data de Conclusão')
    data_limite = models.DateField(null=True, blank=True, verbose_name='Prazo')
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default='avaliar', verbose_name='Prioridade')
    cor = models.CharField(max_length=20, choices=COR_CHOICES, default='azul', verbose_name='Cor')
    imagem = models.ImageField(upload_to='imagens/kanban/', null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    # Tickets destinados ao T.I não entram direto no board; ficam na "inbox" do
    # Kanban TI até serem triados. Este flag marca os já movidos para "A fazer".
    enviado_kanban_ti = models.BooleanField(default=False, verbose_name='Enviado ao Kanban TI')
    # Mensagem de acompanhamento exibida ao criador na central de tickets,
    # atualizada ao longo do ciclo de vida (criado → avaliado → concluído).
    mensagem_status = models.TextField(
        blank=True,
        default='Ticket criado, retornaremos em até 48h.',
        verbose_name='Mensagem de status',
    )
    prazo_resposta = models.CharField(
        max_length=100,
        blank=True,
        default='48h',
        verbose_name='Prazo de resposta',
    )
    # Motivo informado pelo T.I ao recusar o ticket na triagem. Exibido ao
    # criador na central de tickets quando o ticket é recusado.
    motivo_recusa = models.TextField(
        blank=True,
        default='',
        verbose_name='Motivo da recusa',
    )

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
