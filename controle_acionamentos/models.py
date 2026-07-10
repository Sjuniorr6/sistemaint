from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from controle_acionamentos.services import (
    validar_cnpj,
    validar_cpf,
    validar_cnh,
    recalcular_valor_agente,
)


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
    
class FranquiaAgente(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="franquias",
        verbose_name="Cliente",
    )
    nome = models.CharField(max_length=120, verbose_name="Nome")
    valor_acionamento = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Valor do acionamento",
    )
    franquia_km = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="Franquia de KM",
    )
    franquia_horas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Franquia de horas",
    )
    valor_km_excedente = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Valor por KM excedente",
    )
    valor_hora_excedente = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Valor por hora excedente",
    )
    escalonamento_automatico = models.BooleanField(
        default=False,
        verbose_name="Escalonamento automático",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Franquia de Agente"
        verbose_name_plural = "Franquias de Agente"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["cliente", "nome"],
                name="unique_franquia_cliente_nome",
            )
        ]

    def clean(self):
        super().clean()
        self.nome = (self.nome or "").strip()
        if not self.nome:
            raise ValidationError({"nome": "O nome não pode ficar vazio."})
        if self.escalonamento_automatico and self.franquia_km == 0:
            raise ValidationError(
                {"franquia_km": "Franquia escalonável exige franquia_km ≥ 1 (evita divisão por zero no escalonamento)."}
            )

    def __str__(self):
        return f"{self.nome} ({self.cliente.nome_empresa})"


class Acionamento(models.Model):
    # — Relacionamentos —
    # on_delete=PROTECT: cadastro referenciado (cliente, responsável, agente,
    # franquia) não pode sumir por baixo de um acionamento já registrado. Toda
    # FK já ganha índice automático do Django (cobre cliente/agente/franquia do §9).
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="acionamentos",
        verbose_name="Cliente",
    )
    responsavel_agente = models.ForeignKey(
        ResponsavelAgente,
        on_delete=models.PROTECT,
        related_name="acionamentos",
        verbose_name="Responsável de agente",
    )
    agente = models.ForeignKey(
        Agente,
        on_delete=models.PROTECT,
        related_name="acionamentos",
        verbose_name="Agente",
    )
    franquia_agente = models.ForeignKey(
        FranquiaAgente,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="acionamentos",
        verbose_name="Franquia de agente",
    )

    # — Serviço inline —
    # O que o operador digita no acionamento; é a fonte default do cálculo
    # (§8.1). Quando uma franquia é vinculada, ela faz override destes valores,
    # mas eles permanecem registrados para auditoria.
    nome_servico = models.CharField(max_length=120, verbose_name="Nome do serviço")
    valor_acionamento = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Valor do acionamento",
    )
    franquia_km = models.PositiveIntegerField(
        # PRD v1.4 (AC-04.3): aceita 0 no inline — sem flag de escalonamento aqui,
        # nunca há divisão por franquia_km (guard no services.py cobre o caso com franquia).
        validators=[MinValueValidator(0)],
        verbose_name="Franquia de KM",
    )
    franquia_horas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Franquia de horas",
    )
    valor_km_excedente = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Valor por KM excedente",
    )
    valor_hora_excedente = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Valor por hora excedente",
    )

    # — Localização —
    origem = models.CharField(max_length=200, verbose_name="Origem")
    destino = models.CharField(max_length=200, blank=True, verbose_name="Destino")

    # — Pessoas —
    placa_agente = models.CharField(
        max_length=8, blank=True, verbose_name="Placa do agente"
    )
    motorista = models.CharField(
        max_length=120, blank=True, verbose_name="Motorista"
    )
    placa_motorista = models.CharField(
        max_length=8, blank=True, verbose_name="Placa do motorista"
    )
    numero_motorista = models.CharField(
        max_length=20, blank=True, verbose_name="Número do motorista"
    )

    # — Tempo / KM —
    data_hora_solicitado = models.DateTimeField(
        db_index=True,  # §9: índice explícito (não é FK, não ganha índice de graça)
        verbose_name="Data/hora solicitado",
    )
    data_hora_inicio = models.DateTimeField(verbose_name="Data/hora de início")
    data_hora_final = models.DateTimeField(verbose_name="Data/hora final")
    km_inicio = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="KM inicial",
    )
    km_final = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="KM final",
    )
    pedagio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Pedágio",
    )

    # — Calculados (RN-07) —
    # Nunca editáveis pelo usuário; populados só pelo service no marco 7. Nascem
    # null porque o acionamento existe antes do cálculo rodar.
    km_total = models.PositiveIntegerField(
        null=True, blank=True, editable=False, verbose_name="KM total"
    )
    horas_total = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
        verbose_name="Horas totais",
    )
    km_excedente = models.PositiveIntegerField(
        null=True, blank=True, editable=False, verbose_name="KM excedente"
    )
    hora_excedente = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
        verbose_name="Hora excedente",
    )
    valor_agente = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
        verbose_name="Valor do agente",
    )

    # — Auditoria —
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Acionamento"
        verbose_name_plural = "Acionamentos"
        ordering = ["-data_hora_solicitado"]  # AC-08.3: default por solicitação DESC

    def clean(self):
        super().clean()

        # nome_servico: Trim + obrigatório (§5.1.5), no estilo da FranquiaAgente.
        self.nome_servico = (self.nome_servico or "").strip()
        if not self.nome_servico:
            raise ValidationError(
                {"nome_servico": "O nome do serviço não pode ficar vazio."}
            )

        # RN-04 — coerência temporal: solicitado ≤ início < final.
        # Guard de None: o clean() roda mesmo quando clean_fields() já acusou um
        # datetime obrigatório ausente; sem o guard, comparar None com datetime
        # estouraria TypeError e mascararia o erro real do campo.
        if self.data_hora_solicitado and self.data_hora_inicio:
            if self.data_hora_inicio < self.data_hora_solicitado:
                raise ValidationError(
                    {"data_hora_inicio": "O início não pode ser anterior à solicitação."}
                )
        if self.data_hora_inicio and self.data_hora_final:
            if self.data_hora_final <= self.data_hora_inicio:
                raise ValidationError(
                    {"data_hora_final": "O término deve ser posterior ao início."}
                )

        # RN-05 — coerência de quilometragem: km_inicio ≤ km_final.
        if self.km_inicio is not None and self.km_final is not None:
            if self.km_inicio > self.km_final:
                raise ValidationError(
                    {"km_final": "O KM final não pode ser menor que o KM inicial."}
                )

        # RN-06 — coerência de franquia × acionamento: a franquia vinculada tem
        # de pertencer ao MESMO cliente do acionamento. Comparo pelos *_id para
        # não disparar query desnecessária quando não há franquia/cliente.
        if self.franquia_agente_id and self.cliente_id:
            if self.franquia_agente.cliente_id != self.cliente_id:
                raise ValidationError(
                    {"franquia_agente": "A franquia deve pertencer ao mesmo cliente do acionamento."}
                )

    def save(self, *args, **kwargs):
        # RN-07/§8: os 5 campos calculados são populados pelo service a cada save,
        # nunca digitados. O save fica fino — só delega o cálculo e persiste.
        recalcular_valor_agente(self)
        super().save(*args, **kwargs)

    @property
    def codigo(self):
        """Código de exibição do acionamento (DD-032): "ACN-" + pk zero-padded a 6 dígitos.

        Exibição pura — sem coluna, sem migration; deriva do pk. Fonte única do
        formato: templates devem usar {{ acionamento.codigo }}, nunca formatar
        o pk manualmente.
        """
        return f"ACN-{self.pk:06d}"

    def __str__(self):
        return f"{self.nome_servico} ({self.cliente.nome_empresa})"
