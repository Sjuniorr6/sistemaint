from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class AuditLog(models.Model):
    """
    Modelo genérico para registrar todas as ações/mudanças em Requisições e Manutenções
    """
    ACAO_CHOICES = [
        # Requisições
        ('criacao', 'Criação'),
        ('aprovacao', 'Aprovação'),
        ('reprovacao', 'Reprovação'),
        ('atribuicao', 'Atribuição de Responsável'),
        ('status_change', 'Mudança de Status'),
        ('expedicao', 'Expedição'),
        ('envio_cliente', 'Envio ao Cliente'),
        ('edicao', 'Edição'),
        ('exclusao', 'Exclusão'),
        # Kanban
        ('kanban_movido', 'Card Movido no Kanban'),
        ('ids_incluidos', 'IDs Incluídos'),
        ('expedicao_parcial', 'Expedição Parcial'),
        # Manutenção
        ('manutencao_criacao', 'Criação de Manutenção'),
        ('manutencao_aprovacao', 'Aprovação de Manutenção'),
        ('manutencao_reprovacao', 'Reprovação de Manutenção'),
        ('manutencao_atribuicao', 'Atribuição de Responsável (Manutenção)'),
        ('manutencao_status', 'Mudança de Status (Manutenção)'),
        ('manutencao_expedicao', 'Expedição (Manutenção)'),
        ('manutencao_edicao', 'Edição (Manutenção)'),
        ('manutencao_exclusao', 'Exclusão (Manutenção)'),
    ]

    # Referência genérica para Requisicao ou Manutencao
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Dados da ação
    acao = models.CharField(max_length=50, choices=ACAO_CHOICES)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    usuario_nome = models.CharField(max_length=150, help_text="Nome do usuário no momento da ação")
    data_hora = models.DateTimeField(default=timezone.now)
    
    # Detalhes da mudança
    status_anterior = models.CharField(max_length=100, null=True, blank=True)
    status_novo = models.CharField(max_length=100, null=True, blank=True)
    
    # Campo para armazenar informações adicionais em JSON
    detalhes = models.JSONField(null=True, blank=True, help_text="Detalhes adicionais da ação")
    
    # Observações
    observacao = models.TextField(null=True, blank=True)
    
    # IP do usuário (opcional, para segurança)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-data_hora']
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['acao']),
            models.Index(fields=['data_hora']),
            models.Index(fields=['usuario']),
        ]

    def __str__(self):
        return f"{self.get_acao_display()} - {self.usuario_nome} - {self.data_hora.strftime('%d/%m/%Y %H:%M')}"

    @classmethod
    def registrar(cls, objeto, acao, usuario, status_anterior=None, status_novo=None, 
                  detalhes=None, observacao=None, request=None):
        """
        Método helper para registrar uma ação de auditoria
        
        Args:
            objeto: Instância de Requisicoes ou registrodemanutencao
            acao: Tipo de ação (deve estar em ACAO_CHOICES)
            usuario: Instância de User
            status_anterior: Status antes da mudança
            status_novo: Status após a mudança
            detalhes: Dict com informações adicionais
            observacao: Texto livre com observações
            request: Request object para capturar IP
        """
        ip_address = None
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
        
        usuario_nome = usuario.username if usuario else "Sistema"
        
        content_type = ContentType.objects.get_for_model(objeto)
        
        return cls.objects.create(
            content_type=content_type,
            object_id=objeto.id,
            acao=acao,
            usuario=usuario,
            usuario_nome=usuario_nome,
            status_anterior=status_anterior,
            status_novo=status_novo,
            detalhes=detalhes,
            observacao=observacao,
            ip_address=ip_address
        )


class CampoAlterado(models.Model):
    """
    Modelo para registrar campos específicos que foram alterados em uma edição
    """
    audit_log = models.ForeignKey(AuditLog, on_delete=models.CASCADE, related_name='campos_alterados')
    nome_campo = models.CharField(max_length=100)
    valor_anterior = models.TextField(null=True, blank=True)
    valor_novo = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Campo Alterado'
        verbose_name_plural = 'Campos Alterados'

    def __str__(self):
        return f"{self.nome_campo}: {self.valor_anterior} → {self.valor_novo}"
