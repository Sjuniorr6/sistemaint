"""Models do app Chamados.

`Chamado` guarda os fatos de abertura (imutáveis, RN-03) e um cache do estado
corrente (`status`); `ChamadoEvento` é o log append-only que é a fonte única de
auditoria e das métricas (RN-05, ADR-003). Nenhum campo mutável muda aqui — só
pela máquina de estados em `services.py` (ADR-004). Por isso os models ficam
declarativos: validação de coerência de dados no `clean()`, sem regra de fluxo.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from chamados.enums import Acao, Categoria, CustoEquipamento, MeioContato, Status


class Chamado(models.Model):
    # — Identificação —
    # AAAA-NNNNNN, sequencial reiniciado por ano (RN-07). Gerado pelo service de
    # abertura; UNIQUE garante que colisão sob concorrência falha no banco.
    protocolo = models.CharField(
        max_length=11, unique=True, editable=False, verbose_name="Protocolo"
    )

    # — Fatos de abertura (imutáveis, RN-03) —
    # Definidos só na abertura; nenhum form/view/service os reescreve depois.
    # cliente: vínculo ao cadastro do sistema (acompanhamento.Clientes). PROTECT
    # para que um cliente referenciado por um chamado não possa sumir por baixo
    # dele (mesma postura das FKs de responsável). Continua imutável após a
    # criação, como os demais fatos de abertura.
    cliente = models.ForeignKey(
        "acompanhamento.Clientes",
        on_delete=models.PROTECT,
        related_name="chamados",
        verbose_name="Cliente",
    )
    categoria = models.CharField(
        max_length=20, choices=Categoria.choices, verbose_name="Categoria"
    )
    # Pode conter mais de um equipamento, separados por vírgula ("EQ-1, EQ-2").
    # O form junta os vários inputs numa string; aqui é só o armazenamento.
    numero_equipamento = models.CharField(
        max_length=500, verbose_name="Nº do equipamento"
    )
    # modelo_equipamento: vínculo ao cadastro de produtos do sistema
    # (produto.Produto) — a mesma fonte do "Tipo produto" da entrada de
    # manutenção. PROTECT, no mesmo estilo da FK de cliente.
    modelo_equipamento = models.ForeignKey(
        "produto.Produto",
        on_delete=models.PROTECT,
        related_name="chamados",
        verbose_name="Modelo do equipamento",
    )
    problema_relatado = models.TextField(verbose_name="Problema relatado")

    # — Contato feito por (dados de quem acionou o Quality, fatos de abertura) —
    # Nome e meio são obrigatórios; telefone/email são complementares (blank).
    # `blank=True` sem `null=True` nos CharField segue o estilo do projeto:
    # ausência é string vazia, não NULL.
    contato_nome = models.CharField(
        max_length=120, verbose_name="Contato — nome"
    )
    contato_telefone = models.CharField(
        max_length=30, blank=True, verbose_name="Contato — telefone"
    )
    contato_email = models.EmailField(
        max_length=254, blank=True, verbose_name="Contato — email"
    )
    contato_meio = models.CharField(
        max_length=20,
        choices=MeioContato.choices,
        verbose_name="Meio de comunicação",
    )

    # — Campos mutáveis (só via ação da máquina de estados, RN-04) —
    procedimento_realizado = models.TextField(
        null=True, blank=True, verbose_name="Procedimento realizado"
    )
    tratativa = models.TextField(null=True, blank=True, verbose_name="Tratativa")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ABERTO,
        db_index=True,  # o painel filtra por status; índice explícito (RF-08)
        verbose_name="Status",
    )

    # — Responsáveis —
    # responsavel (Quality): obrigatório e FIXO após a criação (RN-02).
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chamados_responsavel",
        verbose_name="Responsável (Quality)",
    )
    # responsavel_inteligencia: definido no encaminhamento, sem apagar o de
    # Quality (RN-15). Nullable porque o chamado nasce sem ele (salvo RN-08).
    responsavel_inteligencia = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="chamados_inteligencia",
        verbose_name="Responsável (Inteligência)",
    )

    # — Auditoria de abertura (imutáveis) —
    aberto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chamados_abertos",
        editable=False,
        verbose_name="Aberto por",
    )
    aberto_em = models.DateTimeField(
        editable=False, verbose_name="Aberto em"
    )  # gravado pelo servidor na criação (RN-06); NÃO auto_now_add (o service o define)

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Chamado"
        verbose_name_plural = "Chamados"
        ordering = ["-aberto_em"]

    def clean(self):
        super().clean()
        # Trim + obrigatoriedade dos textos de abertura, no estilo dos models
        # irmãos (controle_acionamentos). Só coerência de dado — nada de fluxo.
        # `cliente` agora é FK: a obrigatoriedade/integridade fica a cargo do
        # campo (null=False) e do PROTECT, não precisa de trim aqui.
        self.numero_equipamento = (self.numero_equipamento or "").strip()
        if not self.numero_equipamento:
            raise ValidationError(
                {"numero_equipamento": "O número do equipamento não pode ficar vazio."}
            )

        # modelo_equipamento agora é FK (produto.Produto): obrigatoriedade e
        # integridade ficam a cargo do campo (null=False) e do PROTECT.

        self.problema_relatado = (self.problema_relatado or "").strip()
        if not self.problema_relatado:
            raise ValidationError(
                {"problema_relatado": "O problema relatado não pode ficar vazio."}
            )

        # Contato: nome obrigatório (trim); telefone/email complementares (trim).
        self.contato_nome = (self.contato_nome or "").strip()
        if not self.contato_nome:
            raise ValidationError(
                {"contato_nome": "Informe o nome de quem fez o contato."}
            )
        self.contato_telefone = (self.contato_telefone or "").strip()
        self.contato_email = (self.contato_email or "").strip()

    def __str__(self):
        return f"{self.protocolo} · {self.cliente}"


class ChamadoEvento(models.Model):
    """Log append-only de transições (RN-05, ADR-003/ADR-010).

    Sem update nem delete após criação — é a trilha de auditoria e a fonte das
    métricas. Cada evento guarda os textos informados na ação (snapshots), para
    que o histórico do detalhe reconstrua o que foi dito em cada passo, mesmo que
    o campo mutável do Chamado tenha mudado depois.
    """

    chamado = models.ForeignKey(
        Chamado,
        on_delete=models.PROTECT,
        related_name="eventos",
        verbose_name="Chamado",
    )
    acao = models.CharField(
        max_length=20, choices=Acao.choices, verbose_name="Ação"
    )
    # null no evento de criação (não há estado de origem antes de existir).
    estado_origem = models.CharField(
        max_length=20,
        choices=Status.choices,
        null=True,
        blank=True,
        verbose_name="Estado de origem",
    )
    estado_destino = models.CharField(
        max_length=20, choices=Status.choices, verbose_name="Estado de destino"
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="eventos_chamado",
        verbose_name="Autor",
    )

    # Snapshots do que foi informado na ação (quando houver).
    procedimento_snapshot = models.TextField(
        null=True, blank=True, verbose_name="Procedimento (snapshot)"
    )
    tratativa_snapshot = models.TextField(
        null=True, blank=True, verbose_name="Tratativa (snapshot)"
    )
    motivo = models.TextField(null=True, blank=True, verbose_name="Motivo")
    responsavel_inteligencia = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="eventos_encaminhados",
        verbose_name="Responsável (Inteligência)",
    )

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Evento de chamado"
        verbose_name_plural = "Eventos de chamado"
        ordering = ["criado_em"]  # histórico em ordem cronológica (RF-10)

    def save(self, *args, **kwargs):
        # Append-only (ADR-010): um evento nunca é reescrito. Já criado (tem pk),
        # qualquer novo save é bloqueado — a integridade do log sustenta a
        # derivação da reabertura (ADR-005) e das métricas (ADR-011).
        if self.pk is not None:
            raise ValidationError("ChamadoEvento é append-only: não pode ser alterado.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("ChamadoEvento é append-only: não pode ser excluído.")

    def __str__(self):
        return f"{self.chamado.protocolo}: {self.get_acao_display()} → {self.get_estado_destino_display()}"


class TratativaEquipamento(models.Model):
    """Tratativa dada a UM equipamento do chamado, registrada quando o Laboratório
    encaminha para o Comercial.

    Como um chamado pode ter vários equipamentos (numero_equipamento é multi-valor),
    o laboratório informa a tratativa de cada um separadamente — uma linha aqui por
    equipamento tratado.
    """

    chamado = models.ForeignKey(
        Chamado,
        on_delete=models.PROTECT,
        related_name="tratativas_equipamento",
        verbose_name="Chamado",
    )
    numero_equipamento = models.CharField(
        max_length=60, verbose_name="Nº do equipamento"
    )
    # Tratativa do Laboratório (gravada ao encaminhar p/ o Comercial).
    tratativa = models.TextField(verbose_name="Tratativa (laboratório)")
    # — Preenchidos pelo Comercial ao finalizar o chamado —
    tratativa_comercial = models.TextField(
        blank=True, verbose_name="Tratativa (comercial)"
    )
    custo = models.CharField(
        max_length=20,
        choices=CustoEquipamento.choices,
        blank=True,
        verbose_name="Custo",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Tratativa de equipamento"
        verbose_name_plural = "Tratativas de equipamento"
        ordering = ["id"]  # mantém a ordem em que os equipamentos foram informados

    def __str__(self):
        return f"{self.chamado.protocolo} · {self.numero_equipamento}"
