from django.db import models 
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from datetime import datetime, timedelta, date
from decimal import Decimal
from django.core.validators import MinValueValidator


# ------------------------------------------------------
#             Novo Acompanhamento
# ------------------------------------------------------

class Cliente(models.Model):
    id_externo = models.IntegerField(unique=True, help_text="ID do cliente no GSAcionamento")
    
    nome = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=18, unique=True)
    email = models.EmailField(blank=True, null=True)
    ativo = models.BooleanField(default=True)

    comercial = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Cliente Comercial"
    )
    
    tipo_cadastro = models.CharField(
        max_length=40, 
        blank=True,
        null=True,
        verbose_name="Tipo de atendimento"
    )

    permite_comboio = models.BooleanField(
        default=False,
        verbose_name="Permite comboio"
    )

    max_veiculos_comboio = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Máximo de veículos em comboio"
    )

    reutilizar_franquia = models.BooleanField(
        default=False,
        verbose_name="Reutilizar franquia"
    )

    sincronizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return self.nome
    
    def get_tipos_servico_disponiveis(self):
        return self.tipos_servico.filter(ativo=True)

class TipoServico(models.Model):
    class TipoAtendimento(models.TextChoices):
        ACOMPANHAMENTO = "acompanhamento", "Acompanhamento"
        PRONTA_RESPOSTA = "pronta_resposta", "Pronta Resposta"

    TIPOS_CHOICES = [
        ('MOTO_1', 'Moto | 1 Agente(s) - MOTO MONITORAMENTO ATIVO'),
        ('CARRO_1', 'Carro | 1 Agente(s) - CARRO MONITORAMENTO ATIVO'),
        ('CARRO_2', 'Carro | 2 Agente(s) - CARRO MONITORAMENTO ATIVO'),
        ('CARRO_1_1P+', 'Carro | 1 Agente(s) - CARRO MONITORAMENTO ATIVO - 1P+'),
        ('CARRO_2_1P-1P+', 'Carro | 2 Agente(s) - CARRO MONITORAMENTO ATIVO - 1P-/1P+'),
        ('CARRO_2_2P+', 'Carro | 2 Agente(s) - CARRO MONITORAMENTO ATIVO - 2P+'),

        ('Pronta_Resposta_P+', 'Pronta Resposta - 1 Agente(s) - P+'),
        ('Pronta_Resposta_P-', 'Pronta Resposta - 1 Agente(s) - P-'),
        ('Antenista', 'Antenista'),
    ]

    id_externo = models.IntegerField(unique=True, help_text="ID do tipo de serviço no GSAcionamento")
    
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='tipos_servico'
    )

    codigo = models.CharField(max_length=20, choices=TIPOS_CHOICES)

    tipo_cadastro = models.CharField(
        max_length=20,
        choices=TipoAtendimento.choices,
        blank=True,
        null=True,
        verbose_name="Tipo de atendimento"
    )

    nome_variacao = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Nome da variação"
    )
    
    ativo = models.BooleanField(default=True)

    valor_acionamento = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
        help_text="Valor fixo de acionamento do serviço."
    )
    franquia_km = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    franquia_horas = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    valor_hora = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valor_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    lat_origem = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    long_origem = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    lat_destino = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    long_destino = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    sincronizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tipo de Serviço'
        verbose_name_plural = 'Tipos de Serviço'

    def __str__(self):
        base = self.get_codigo_display()

        if self.nome_variacao:
            return f"{base} - {self.nome_variacao} - {self.cliente.nome}"

        return f"{base} - {self.cliente.nome}"
    
    def get_codigo_display(self):
        return dict(self.TIPOS_CHOICES).get(self.codigo, self.codigo)

class Missao(models.Model):
    class StatusMissao(models.TextChoices):
        ATIVA = 'ativa', 'Ativa'
        ENCERRADA = 'encerrada', 'Encerrada'

    id_externo = models.IntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text="PK da missão no GS Acionamento"
    )

    nome = models.CharField(max_length=255)

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='missoes'
    )

    criado_por = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=10,
        choices=StatusMissao.choices,
        default=StatusMissao.ATIVA
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Missão'
        verbose_name_plural = 'Missões'

    def __str__(self):
        return f"Missão #{self.pk} - {self.nome} ({self.get_status_display()})"

class RequisicaoSolicitacao(models.Model):

    requisicao_id_externo = models.IntegerField(
        null=True, blank=True,
        help_text="PK da Requisicao (acompanhamento) no GS Acionamento"
    )

    id_externo = models.IntegerField(unique=True, null=True, blank=True, help_text="ID da requisição no GSAcionamento")

    missao = models.ForeignKey(
        Missao,
        on_delete=models.CASCADE,
        related_name='requisicoes',
        null=True,
        blank=True,
        help_text="Missão vinculada (sincronizada do GS Acionamento)"
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True
    )

    tipo_servico = models.ForeignKey(
        TipoServico,
        on_delete=models.PROTECT,
        related_name='requisicoes'
    )

    campo_personalizado_titulo = models.CharField(max_length=100, blank=True, null=True)
    campo_personalizado_valor = models.CharField(max_length=255, blank=True, null=True)

    origem = models.CharField(max_length=500)
    origem_2 = models.CharField(max_length=500)
    origem_3 = models.CharField(max_length=500)
    latitude_origem = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude_origem = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    latitude_origem_2 = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude_origem_2 = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    latitude_origem_3 = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude_origem_3 = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    destino = models.CharField(max_length=500, blank=True, null=True)
    destino_2 = models.CharField(max_length=500, blank=True)
    destino_3 = models.CharField(max_length=500, blank=True)
    latitude_destino = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude_destino = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    latitude_destino_2 = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude_destino_2 = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    latitude_destino_3 = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude_destino_3 = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    km_estimado_carro = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    km_estimado_moto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    motorista = models.CharField(max_length=255)
    numero_motorista = models.CharField(max_length=255)
    placa = models.CharField(max_length=10)
    data_agendamento = models.DateField()
    horario_agendamento = models.TimeField()

    agente = models.CharField(max_length=255, blank=True, null=True)
    placa_agente = models.CharField(max_length=10, blank=True, null=True)

    comboio = models.BooleanField(default=False)
    quantidade_veiculos_comboio = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Quantidade total de veículos no comboio (quando aplicável)."
    )

    is_reuso = models.BooleanField(
        default=False,
        verbose_name="É reuso de agente"
    )
    
    agente_nome_reuso = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="Nome do agente (reuso)"
    )

    agente_placa_reuso = models.CharField(
        max_length=10, blank=True, null=True,
        verbose_name="Placa do agente (reuso)"
    )

    ocorrencia = models.TextField(blank=True, null=True)
    nome_user = models.CharField(max_length=150, blank=True, null=True)

    solicitado = models.BooleanField(default=False)

    status_requisicao = models.CharField(max_length=50, blank=True, null=True)
    taxa_cancelamento_percentual = models.PositiveSmallIntegerField(null=True, blank=True)
    valor_cancelamento = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    aceitou_termos_cancelamento = models.BooleanField(default=False)
    usuario_aceitou_termos_cancelamento = models.CharField(max_length=150, blank=True, null=True)
    justificativa_cancelamento = models.TextField(blank=True)
    motivos_cancelamento = models.JSONField(default=list, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    cancelamento_aprovado = models.BooleanField(default=False)

    sincronizado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Requisição de Solicitação"
        verbose_name_plural = "Requisições de Solicitações"
    
    def __str__(self):
        return f"#{self.id} - {self.cliente}"

class FranquiaAgente(models.Model):
    id_externo = models.IntegerField(unique=True, help_text="ID do tipo de serviço no GSAcionamento")

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='franquias_agente',
        verbose_name="Cliente"
    )

    tipo_servico = models.ForeignKey(
        TipoServico,
        on_delete=models.PROTECT,
        related_name='franquias',
        null=True,
        blank=True,
        verbose_name="Tipo de Serviço"
    )

    nome = models.CharField(max_length=100, verbose_name="Nome da Franquia")
    valor_acionamento = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, verbose_name="Valor do Acionamento (R$)")

    franquia_km = models.PositiveIntegerField(blank=True, null=True, verbose_name="Franquia de KM")
    franquia_horas = models.PositiveIntegerField(blank=True, null=True, verbose_name="Franquia de Horas")

    valor_km_excedente = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, verbose_name="Valor de KM Excedentes (R$)")
    valor_horas_excedente = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, verbose_name="Valor de Horas Excedentes (R$)")

    nome_user = models.CharField(max_length=150, blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True) 

    class Meta:
        ordering = ['-criado_em']
        permissions = [
            ("view_listfranquia", "Pode visualizar lista de franquias"),
        ]

    def __str__(self):
        return f"{self.nome} (#{self.id})"

# ------------------------------------------------------
#                 Registro de Agentes
# ------------------------------------------------------
class registrodeagenteacompanhamento(models.Model):
    # =========================
    # DADOS PRINCIPAIS
    # =========================
    nome = models.CharField(
        max_length=150,
        verbose_name="Nome do Agente"
    )

    cpf = models.CharField(
        max_length=14,
        blank=True,
        null=True,
        verbose_name="CPF"
    )

    pix = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Chave Pix"
    )
    
    banco = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Banco"
    )

    agencia = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Agência"
    )

    conta = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Conta"
    )

    tipo_conta = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name="Tipo de Conta"
    )

    clientes_vinculados = models.ManyToManyField(
        Cliente,
        blank=True,
        related_name="agentes_vinculados",
        verbose_name="Clientes vinculados"
    )

    # =========================
    # CONTROLE
    # =========================
    nome_user = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Usuário responsável"
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )

    class Meta:
        ordering = ['-criado_em']
        verbose_name = "Registro de Agentes"
        verbose_name_plural = "Registros de Agentes"

    def __str__(self):
        return f"{self.nome}"

# ------------------------------------------------------
#               Responsável de Agentes
# ------------------------------------------------------
class registroderesposavelagenteacompanhamento(models.Model):
    # =========================
    # DADOS PRINCIPAIS
    # =========================
    nome = models.CharField(
        max_length=150,
        verbose_name="Nome do Responsável Agente"
    )

    # =========================
    # CONTROLE
    # =========================
    nome_user = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Criado por Usuário"
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )

    class Meta:
        ordering = ['-criado_em']
        verbose_name = "Registro de Responsável Agentes"
        verbose_name_plural = "Registros de Responsável Agentes"

    def __str__(self):
        return f"{self.nome}"

# ------------------------------------------------------
#               Registro de Acompanhamentos
# ------------------------------------------------------
class registroacompanhamento(models.Model):
    STATUS_CHOICES = (
        ("pendente", "Pendente"),
        ("aguardando", "Aguardando Autorização"),
        ("faturado", "Faturado"),
    )

    STATUS_ACOMPANHAMENTO_CHOICES = (
        ("pendente", "Pendente"),
        ("missao_aceita", "Missão Aceita"),
        ("agendada", "Missão Agendada"),
        ("em_deslocamento", "Em Deslocamento"),
        ("no_local", "No Local"),
        ("odometro_inicio_verificado", "Odômetro Inicial Verificado"),
        ("teste_panico", "Teste Pânico"),
        ("teste_panico_verificado", "Teste Pânico Verificado"),
        ("em_andamento", "Em Andamento"),
        ("disponivel", "Disponível"),
        ("sem_sinal", "Sem Sinal"),
        ("odometro_final_verificado", "Odômetro Final Verificado"),
        ("concluido", "Concluído"),
        ("verificado", "Verificado"),
    )

    supabase_mission_id = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        verbose_name="ID da missão (Supabase)"
    )

    botao_panico = models.BooleanField(
        default=False,
        verbose_name="Acionamento via Botão de Pânico"
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True
    )

    tipo_servico = models.ForeignKey(
        TipoServico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acompanhamentos'
    )

    requisicao_solicitacao = models.ForeignKey(
        "RequisicaoSolicitacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acompanhamentos_int",
        help_text="Requisição de solicitação (INT) que originou este acompanhamento. Usado para sincronizar status com o GSAcionamento."
    )

    campo_personalizado_titulo = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Título do Campo Personalizado"
    )

    campo_personalizado_valor = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Valor do Campo Personalizado"
    )

    origem = models.CharField(max_length=100)

    latitude_origem = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Latitude do Origem"
    )

    longitude_origem = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Longitude do Origem"
    )

    origem_2 = models.CharField(max_length=100, blank=True, null=True)

    latitude_origem2 = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Latitude do Origem"
    )

    longitude_origem2 = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Longitude do Origem"
    )

    origem_3 = models.CharField(max_length=100, blank=True, null=True)

    latitude_origem3 = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Latitude do Origem"
    )

    longitude_origem3 = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Longitude do Origem"
    )

    raio_cerca = models.PositiveIntegerField(
        default=60,
        verbose_name="Raio da Cerca (metros)"
    )

    raio_cerca_2 = models.PositiveIntegerField(
        default=60,
        verbose_name="Raio da Cerca 2 (metros)",
        blank=True,
        null=True,
    )

    raio_cerca_3 = models.PositiveIntegerField(
        default=60,
        verbose_name="Raio da Cerca 3 (metros)",
        blank=True,
        null=True,
    )

    destino = models.CharField(max_length=100, blank=True, null=True,)
    destino_2 = models.CharField(max_length=100, blank=True, null=True,)
    destino_3 = models.CharField(max_length=100, blank=True, null=True,)

    latitude_destino = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Latitude do Destino"
    )

    longitude_destino = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Longitude do Destino"
    )

    latitude_destino_2 = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Latitude do Destino"
    )

    longitude_destino_2 = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Longitude do Destino"
    )

    latitude_destino_3 = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Latitude do Destino"
    )

    longitude_destino_3 = models.DecimalField(
        max_digits=9, decimal_places=7,
        blank=True, null=True,
        verbose_name="Longitude do Destino"
    )

    km_estimado_carro = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    km_estimado_moto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    valor_contrato = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    lucro_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pendente"
    )

    status_acompanhamento = models.CharField(
        max_length=40,
        choices=STATUS_ACOMPANHAMENTO_CHOICES,
        default="pendente"
    )

    nf = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Nota Fiscal"
    )

    validado_cliente = models.BooleanField(default=False)
    validar_acompanhamento = models.BooleanField(default=False)
    validar_pagamento = models.BooleanField(default=False)

    comboio = models.BooleanField(default=False)
    quantidade_veiculos_comboio = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Quantidade total de veículos no comboio (quando aplicável)."
    )

    is_reuso = models.BooleanField(
        default=False,
        verbose_name="É reuso de agente",
        help_text="Acompanhamentos de reuso não têm custo para o cliente."
    )

    status_requisicao = models.CharField(max_length=50, blank=True, null=True)
    taxa_cancelamento_percentual = models.PositiveSmallIntegerField(null=True, blank=True)
    valor_cancelamento = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    aceitou_termos_cancelamento = models.BooleanField(default=False)
    usuario_aceitou_termos_cancelamento = models.CharField(max_length=150, blank=True, null=True)
    justificativa_cancelamento = models.TextField(blank=True)
    motivos_cancelamento = models.JSONField(default=list, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)

    ocorrencia = models.TextField(blank=True, null=True)
    nome_user = models.CharField(max_length=150, blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    tempo_criacao_desde_requisicao = models.DurationField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="Tempo para criar (desde a requisição)",
        help_text="Diferença entre a criação da RequisiçãoSolicitacao e a criação deste acompanhamento."
    )

    def save(self, *args, **kwargs):
        if self.requisicao_solicitacao_id:
            req = self.requisicao_solicitacao
            if req and req.criado_em:
                agora = timezone.now()

                if self._state.adding or self.tempo_criacao_desde_requisicao is None:
                    self.tempo_criacao_desde_requisicao = agora - req.criado_em

        super().save(*args, **kwargs)

    @property
    def tempo_criacao_desde_requisicao_humanizado(self):
        td = self.tempo_criacao_desde_requisicao
        if not td:
            return "-"
        total = int(td.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h}h {m}m {s}s"
    
    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Acompanhamentos"
        verbose_name_plural = "Acompanhamentoss"
    
    def __str__(self):
        return f"#{self.id} - {self.cliente}"

    # def recalcular_lucro_total(self):
    #     total_agentes = sum(
    #         (agente.valor_agente or Decimal("0.00"))
    #         for agente in self.agentes.all()
    #     )

    #     if self.valor_contrato is not None:
    #         self.lucro_total = self.valor_contrato - total_agentes
    #     else:
    #         self.lucro_total = None

    #     self.save(update_fields=["lucro_total"])

    # def recalcular_financeiro(self):
    #     self.valor_contrato = self.calcular_valor_contrato()

    #     total_agentes = self.total_valor_agentes or Decimal("0.00")

    #     if self.valor_contrato is not None:
    #         self.lucro_total = self.valor_contrato - total_agentes
    #     else:
    #         self.lucro_total = None

    #     self.save(update_fields=["valor_contrato", "lucro_total"])

    def recalcular_financeiro(self, commit=True):
        if self.status_acompanhamento != "verificado":
            self.valor_contrato = None
            self.lucro_total = None

            if commit:
                self.save(update_fields=["valor_contrato", "lucro_total"])
            return

        if self.is_reuso:
            self.valor_contrato = Decimal("0.00")
            self.lucro_total = Decimal("0.00")

            if commit:
                self.save(update_fields=["valor_contrato", "lucro_total"])
            return

        self.valor_contrato = self.calcular_valor_contrato()
        total_agentes = self.total_valor_agentes or Decimal("0.00")

        self.lucro_total = (
            self.valor_contrato - total_agentes
            if self.valor_contrato is not None
            else None
        )

        if commit:
            self.save(update_fields=["valor_contrato", "lucro_total"])

    @property
    def total_valor_agentes(self):
        return sum(
            (agente.valor_agente or Decimal("0.00"))
            for agente in self.agentes.all()
        )

    @property
    def total_valor_agentes_formatado(self):
        valor = self.total_valor_agentes
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def calcular_valor_contrato(self):
        ts = self.tipo_servico
        if not ts:
            return None

        total = Decimal("0.00")

        if ts.valor_acionamento:
            total += ts.valor_acionamento

        agentes_validos = self.agentes.exclude(tipo_agente="carona")
        km_total = sum(a.km_total or 0 for a in agentes_validos)

        if ts.franquia_km is not None:
            km_excedente = max(0, km_total - int(ts.franquia_km))
            if km_excedente > 0 and ts.valor_km:
                total += Decimal(km_excedente) * ts.valor_km

        segundos_totais = sum(
            int(a.horario_total.total_seconds())
            for a in agentes_validos
            if a.horario_total
        )

        if ts.franquia_horas is not None:
            segundos_franquia = int(ts.franquia_horas) * 3600
            excedente = segundos_totais - segundos_franquia

            if excedente > 0 and ts.valor_hora:
                horas = Decimal(excedente) / Decimal("3600")
                total += horas * ts.valor_hora

        total_pedagio = sum(
            a.pedagio or Decimal("0.00")
            for a in agentes_validos
            if a.pedagio
        )
        total += total_pedagio

        return total.quantize(Decimal("0.01"))

class registroacompanhamentoagente(models.Model):
    TIPO_CHOICES = (
        ("principal", "Agente Principal"),
        ("carona", "Agente no Mesmo Veículo"),
    )

    acompanhamento = models.ForeignKey(
        "registroacompanhamento",
        on_delete=models.CASCADE,
        related_name="agentes"
    )

    tipo_agente = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="principal"
    )

    responsavel_agente = models.ForeignKey(
        registroderesposavelagenteacompanhamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agentes_vinculados",
        verbose_name="Responsável pelo Agente"
    )


    agente = models.ForeignKey(
        registrodeagenteacompanhamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    franquia = models.ForeignKey(
        FranquiaAgente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    tipo_servico = models.ForeignKey(
        TipoServico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agentes_acompanhamento',
        verbose_name="Tipo de Serviço"
    )

    placa_agente = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )

    motorista = models.CharField(max_length=100, blank=True, null=True)
    placa_motorista = models.CharField(max_length=10, blank=True, null=True)

    numero_motorista = models.CharField(max_length=15, blank=True, null=True)
    
    bancario = models.BooleanField(
        default=False,
        verbose_name="Pagamento Bancário?"
    )

    pix = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Chave Pix"
    )

    banco = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Banco"
    )

    agencia = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Agência"
    )

    conta = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Conta"
    )

    tipo_conta = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name="Tipo de Conta"
    )

    nome_completo_conta = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Nome Completo (Conta Bancária)"
    )

    cpf_conta = models.CharField(
        max_length=14,
        blank=True,
        null=True,
        verbose_name="CPF (Conta Bancária)"
    )

    km_inicio = models.IntegerField(blank=True, null=True)
    km_final = models.IntegerField(blank=True, null=True)
    km_total = models.IntegerField(blank=True, null=True)

    km_excedente = models.IntegerField(blank=True, null=True)

    horario_solicitado = models.TimeField(blank=True, null=True)
    horario_inicio = models.TimeField(blank=True, null=True)
    horario_finalizacao = models.TimeField(blank=True, null=True)

    data_solicitada = models.DateField(blank=True, null=True)
    data_inicio = models.DateField(blank=True, null=True)
    data_finalizacao = models.DateField(blank=True, null=True)

    horario_total = models.DurationField(blank=True, null=True)
    horario_excedente = models.DurationField(blank=True, null=True)

    pedagio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    valor_agente = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Agente do Acompanhamento"
        verbose_name_plural = "Agentes do Acompanhamento"

    def __str__(self):
        return f"{self.agente}"

    def _get_inicio_real_para_calculo(self):
        """
        Início real da jornada: prioriza data_inicio/horario_inicio (no_local).
        Fallback para data_solicitada/horario_solicitado para legado.
        """
        if self.data_inicio and self.horario_inicio:
            return datetime.combine(self.data_inicio, self.horario_inicio)

        if self.data_solicitada and self.horario_solicitado:
            return datetime.combine(self.data_solicitada, self.horario_solicitado)

        return None

    def _get_fim_para_calculo(self):
        if self.data_finalizacao and self.horario_finalizacao:
            return datetime.combine(self.data_finalizacao, self.horario_finalizacao)

        return None

    def calcular_horario_total(self):
        inicio = self._get_inicio_real_para_calculo()
        fim = self._get_fim_para_calculo()

        if not inicio or not fim:
            return None

        if fim < inicio:
            fim += timedelta(days=1)

        return fim - inicio

    def calcular_horario_excedente(self):
        if not self.franquia or not self.horario_total:
            return None

        if self.franquia.franquia_horas is None:
            return None

        segundos_franquia = self.franquia.franquia_horas * 3600
        segundos_totais = int(self.horario_total.total_seconds())

        excedente = segundos_totais - segundos_franquia

        if excedente > 0:
            return timedelta(seconds=excedente)

        return None

    def recalcular_franquia_e_valores(self):
        self.horario_excedente = self.calcular_horario_excedente()

        if not self.franquia:
            self.km_excedente = 0
            self.valor_agente = Decimal("0.00")
            return

        km_excedente = 0
        valor_km_excedente = Decimal("0.00")

        if self.franquia.franquia_km is not None and self.km_total is not None:
            km_excedente = max(0, self.km_total - self.franquia.franquia_km)

            if km_excedente > 0 and self.franquia.valor_km_excedente:
                valor_km_excedente = (
                    Decimal(km_excedente) * self.franquia.valor_km_excedente
                )

        self.km_excedente = km_excedente

        valor_total = Decimal("0.00")

        if self.franquia.valor_acionamento:
            valor_total += self.franquia.valor_acionamento

        valor_total += valor_km_excedente

        if self.horario_excedente and self.franquia.valor_horas_excedente:
            horas = (
                Decimal(self.horario_excedente.total_seconds()) / Decimal("3600")
            )
            valor_total += horas * self.franquia.valor_horas_excedente

        if self.pedagio:
            valor_total += self.pedagio

        self.valor_agente = valor_total.quantize(Decimal("0.01"))

    # def save(self, *args, **kwargs):
    #     if self.km_inicio is not None and self.km_final is not None:
    #         self.km_total = self.km_final - self.km_inicio

    #     if (
    #         self.data_solicitada
    #         and self.horario_solicitado
    #         and self.data_finalizacao
    #         and self.horario_finalizacao
    #     ):
    #         self.horario_total = self.calcular_horario_total()

    #     self.recalcular_franquia_e_valores()
    #     super().save(*args, **kwargs)

    def save(self, *args, **kwargs):

        if self.km_inicio is not None and self.km_final is not None:
            self.km_total = self.km_final - self.km_inicio
        else:
            self.km_total = None

        self.horario_total = self.calcular_horario_total()

        # ✅ REUSO: zera todos os valores R$ (reuso não tem custo)
        if self.acompanhamento and self.acompanhamento.is_reuso:
            self.pedagio = Decimal("0.00")
            self.valor_agente = Decimal("0.00")
            self.km_excedente = None
            self.horario_excedente = None

            super().save(*args, **kwargs)
            return

        if self.tipo_agente == "carona":
            self.valor_agente = Decimal("0.00")
            self.km_excedente = None
            self.horario_excedente = None

            super().save(*args, **kwargs)
            return

        self.recalcular_franquia_e_valores()

        super().save(*args, **kwargs)
