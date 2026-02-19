from django.db import models 
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from franquia.models import registrodefranquia
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
    TIPOS_CHOICES = [
        ('MOTO_1', 'Moto | 1 Agente(s) - MOTO MONITORAMENTO ATIVO'),
        ('CARRO_1', 'Carro | 1 Agente(s) - CARRO MONITORAMENTO ATIVO'),
        ('CARRO_2', 'Carro | 2 Agente(s) - CARRO MONITORAMENTO ATIVO'),
        ('CARRO_1_1G', 'Carro | 1 Agente(s) - CARRO MONITORAMENTO ATIVO - 1G'),
        ('CARRO_2_1S1G', 'Carro | 2 Agente(s) - CARRO MONITORAMENTO ATIVO - 1S/1G'),
        ('CARRO_2_2G', 'Carro | 2 Agente(s) - CARRO MONITORAMENTO ATIVO - 2G'),
    ]

    id_externo = models.IntegerField(unique=True, help_text="ID do tipo de serviço no GSAcionamento")
    
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='tipos_servico'
    )
    codigo = models.CharField(max_length=20, choices=TIPOS_CHOICES)
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

    sincronizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['cliente', 'codigo']
        verbose_name = 'Tipo de Serviço'
        verbose_name_plural = 'Tipos de Serviço'

    def __str__(self):
        return f"{self.get_codigo_display()} - {self.cliente.nome}"
    
    def get_codigo_display(self):
        return dict(self.TIPOS_CHOICES).get(self.codigo, self.codigo)

class RequisicaoSolicitacao(models.Model):
    id_externo = models.IntegerField(unique=True, null=True, blank=True, help_text="ID da requisição no GSAcionamento")
    
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
    latitude_origem = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude_origem = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    destino = models.CharField(max_length=500, blank=True, null=True)

    motorista = models.CharField(max_length=255)
    placa = models.CharField(max_length=10)
    data_agendamento = models.DateField()
    horario_agendamento = models.TimeField()

    ocorrencia = models.TextField(blank=True, null=True)
    nome_user = models.CharField(max_length=150, blank=True, null=True)

    solicitado = models.BooleanField(default=False)

    sincronizado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Requisição de Solicitação"
        verbose_name_plural = "Requisições de Solicitações"
    
    def __str__(self):
        return f"#{self.id} - {self.cliente}"
        

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
#                 Registro de Clientes
# ------------------------------------------------------
class registrodeclienteacompanhamento(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome do Cliente")
    cnpj = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    valor_acionamento = models.DecimalField(
        max_digits=8, decimal_places=2,
        blank=True, null=True,
        verbose_name="Valor do Acionamento (R$)"
    )

    franquia_km = models.PositiveIntegerField(
        blank=True, null=True,
        verbose_name="Franquia de KM"
    )

    franquia_horas = models.PositiveIntegerField(
        blank=True, null=True,
        verbose_name="Franquia de Horas"
    )

    valor_km_excedente = models.DecimalField(
        max_digits=8, decimal_places=2,
        blank=True, null=True,
        verbose_name="Valor do KM Excedente (R$)"
    )

    valor_horas_excedente = models.DecimalField(
        max_digits=8, decimal_places=2,
        blank=True, null=True,
        verbose_name="Valor Hora Excedente (R$)"
    )

    nome_user = models.CharField(max_length=150, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome

# ------------------------------------------------------
#            Registro de Serviços Acompanhamento
# ------------------------------------------------------
class servicosacompanhamentos(models.Model):
    TIPO_SERVICO_CHOICES = (
        ('moto', 'Moto'),
        ('carro', 'Carro'),
    )

    AGENTES_CHOICES = (
        (1, '1 Agente'),
        (2, '2 Agentes'),
    )

    tipo = models.CharField(
        max_length=10,
        choices=TIPO_SERVICO_CHOICES,
        verbose_name="Tipo do Serviço"
    )

    agentes = models.PositiveSmallIntegerField(
        choices=AGENTES_CHOICES,
        verbose_name="Quantidade de Agentes"
    )

    nomeclatura = models.CharField(
        max_length=150,
        verbose_name="Nomenclatura do Serviço"
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
        verbose_name = "Serviço de Acompanhamento"
        verbose_name_plural = "Serviços de Acompanhamento"

    def __str__(self):
        return f"{self.get_tipo_display()} | {self.agentes} agente(s) - {self.nomeclatura}"

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
        ("placa_inicio_verificada", "Placa Inicial Verificada"),  # NOVO v2.6.0
        ("odometro_inicio_verificado", "Odômetro Inicial Verificado"),
        ("teste_panico", "Teste Pânico"),
        ("teste_panico_verificado", "Teste Pânico Verificado"),
        ("em_andamento", "Em Andamento"),
        ("sem_sinal", "Sem Sinal"),
        ("odometro_final_verificado", "Odômetro Final Verificado"),
        ("placa_final_verificada", "Placa Final Verificada"),  # NOVO v2.6.0
        ("concluido", "Concluído"),
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

    raio_cerca = models.PositiveIntegerField(
        default=60,
        verbose_name="Raio da Cerca (metros)"
    )

    destino = models.CharField(max_length=100, blank=True, null=True,)

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

    ocorrencia = models.TextField(blank=True, null=True)
    nome_user = models.CharField(max_length=150, blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    
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
        # 🔒 Só calcula se estiver validado
        if not self.validar_acompanhamento:
            self.valor_contrato = None
            self.lucro_total = None

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
        if not self.cliente:
            return None

        cliente = self.cliente
        total = Decimal("0.00")

        if cliente.valor_acionamento:
            total += cliente.valor_acionamento

        agentes_validos = self.agentes.exclude(tipo_agente="carona")

        km_total = sum(a.km_total or 0 for a in agentes_validos)

        if cliente.franquia_km is not None:
            km_excedente = max(0, km_total - cliente.franquia_km)
            if km_excedente > 0 and cliente.valor_km_excedente:
                total += Decimal(km_excedente) * cliente.valor_km_excedente

        segundos_totais = sum(
            int(a.horario_total.total_seconds())
            for a in agentes_validos
            if a.horario_total
        )

        if cliente.franquia_horas is not None:
            segundos_franquia = cliente.franquia_horas * 3600
            excedente = segundos_totais - segundos_franquia

            if excedente > 0 and cliente.valor_horas_excedente:
                horas = Decimal(excedente) / Decimal("3600")
                total += horas * cliente.valor_horas_excedente

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
        registrodefranquia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    placa_agente = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )

    motorista = models.CharField(max_length=100, blank=True, null=True)
    placa_motorista = models.CharField(max_length=10, blank=True, null=True)
    
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

    # Campos para validação de placa (novo em v2.6.0)
    placa_inicio = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Placa Início"
    )
    placa_final = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Placa Final"
    )
    data_placa_inicio = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Data/Hora Placa Início"
    )
    data_placa_final = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Data/Hora Placa Final"
    )

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

    def calcular_horario_total(self):
        inicio = datetime.combine(self.data_solicitada, self.horario_solicitado)
        fim = datetime.combine(self.data_finalizacao, self.horario_finalizacao)

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

        if (
            self.data_solicitada and self.horario_solicitado and
            self.data_finalizacao and self.horario_finalizacao
        ):
            inicio = datetime.combine(self.data_solicitada, self.horario_solicitado)
            fim = datetime.combine(self.data_finalizacao, self.horario_finalizacao)

            if fim < inicio:
                fim += timedelta(days=1)

            self.horario_total = fim - inicio
        else:
            self.horario_total = None

        if self.tipo_agente == "carona":
            self.valor_agente = Decimal("0.00")
            self.km_excedente = None
            self.horario_excedente = None

            super().save(*args, **kwargs)
            return

        self.recalcular_franquia_e_valores()

        super().save(*args, **kwargs)

# ------------------------------------------------------
#             Acompanhamentos Panico
# ------------------------------------------------------
class AcompanhamentoLocalizacao(models.Model):
    acompanhamento = models.ForeignKey(
        "registroacompanhamento",
        on_delete=models.CASCADE,
        related_name="localizacoes"
    )

    agente = models.ForeignKey(
        registrodeagenteacompanhamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6
    )

    accuracy = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    is_panic = models.BooleanField(
        default=False,
        verbose_name="Alerta de Pânico"
    )

    panic_resolved = models.BooleanField(
        default=False,
        verbose_name="Pânico Resolvido"
    )

    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="panicos_resolvidos",
        verbose_name="Resolvido por"
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Resolvido em"
    )

    origem = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Origem do Acompanhamento"
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["acompanhamento", "criado_em"]),
        ]

    def __str__(self):
        panic_flag = "🚨" if self.is_panic and not self.panic_resolved else ""
        resolved_flag = "✅" if self.panic_resolved else ""
        return f"{panic_flag}{resolved_flag} {self.origem or 'Sem origem'} - {self.latitude}, {self.longitude}"

