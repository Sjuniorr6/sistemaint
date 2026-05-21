from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─────────────────────────────────────────
# CHOICES
# ─────────────────────────────────────────

class DiaDaSemana(models.TextChoices):
    SEGUNDA = 'segunda', 'Segunda-feira'
    TERCA   = 'terca',   'Terça-feira'
    QUARTA  = 'quarta',  'Quarta-feira'
    QUINTA  = 'quinta',  'Quinta-feira'
    SEXTA   = 'sexta',   'Sexta-feira'


class Periodo(models.TextChoices):
    MANHA = 'manha', 'Manhã'
    TARDE = 'tarde', 'Tarde'


class StatusExecucao(models.TextChoices):
    PENDENTE     = 'pendente',     'Pendente'
    EM_ANDAMENTO = 'em_andamento', 'Em Andamento'
    ATRASADA     = 'atrasada',     'Atrasada'
    CONCLUIDA    = 'concluida',    'Concluída'
    CANCELADA    = 'cancelada',    'Cancelada'


class TipoControle(models.TextChoices):
    CHECKBOX   = 'checkbox',   'Checkbox'
    PERCENTUAL = 'percentual', 'Percentual'


class TipoBloco(models.TextChoices):
    NAO_ESQUECER = 'nao_esquecer', 'Não Esquecer'
    QUINZENAL    = 'quinzenal',    'Quinzenal'
    MENSAL       = 'mensal',       'Mensal'


class PerfilFuncionario(models.TextChoices):
    GESTOR   = 'gestor',   'Gestor'
    OPERADOR = 'operador', 'Operador'


# ─────────────────────────────────────────
# FUNCIONÁRIO
# ─────────────────────────────────────────

class FuncionarioAdministrativo(models.Model):
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='funcionario_administrativo',
        verbose_name='Usuário'
    )
    nome = models.CharField(max_length=100, verbose_name='Nome')
    perfil = models.CharField(
        max_length=20,
        choices=PerfilFuncionario.choices,
        default=PerfilFuncionario.OPERADOR,
        verbose_name='Perfil'
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')

    class Meta:
        verbose_name = 'Funcionário Administrativo'
        verbose_name_plural = 'Funcionários Administrativos'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.get_perfil_display()})"


# ─────────────────────────────────────────
# CATEGORIA
# ─────────────────────────────────────────

class CategoriaTarefaAdministrativa(models.Model):
    nome = models.CharField(max_length=100, verbose_name='Nome')
    cor  = models.CharField(max_length=20, default='#665b1d', verbose_name='Cor (hex)')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')

    class Meta:
        verbose_name = 'Categoria de Tarefa'
        verbose_name_plural = 'Categorias de Tarefas'
        ordering = ['nome']

    def __str__(self):
        return self.nome


# ─────────────────────────────────────────
# TAREFA MODELO — recorrente
# ─────────────────────────────────────────

class TarefaModeloAdministrativa(models.Model):
    titulo = models.CharField(max_length=200, verbose_name='Título')
    descricao = models.TextField(blank=True, verbose_name='Descrição')
    dia_da_semana = models.CharField(
        max_length=10,
        choices=DiaDaSemana.choices,
        verbose_name='Dia da Semana'
    )
    periodo = models.CharField(
        max_length=10,
        choices=Periodo.choices,
        verbose_name='Período'
    )
    tipo_controle = models.CharField(
        max_length=15,
        choices=TipoControle.choices,
        default=TipoControle.CHECKBOX,
        verbose_name='Tipo de Controle'
    )
    responsavel = models.ForeignKey(
        FuncionarioAdministrativo,
        on_delete=models.PROTECT,
        related_name='tarefas_modelo',
        verbose_name='Responsável'
    )
    categoria = models.ForeignKey(
        CategoriaTarefaAdministrativa,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tarefas_modelo',
        verbose_name='Categoria'
    )
    ordem = models.PositiveIntegerField(default=0, verbose_name='Ordem de exibição')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tarefa Modelo'
        verbose_name_plural = 'Tarefas Modelo'
        ordering = ['dia_da_semana', 'periodo', 'ordem']

    def __str__(self):
        return f"{self.titulo} ({self.get_dia_da_semana_display()} - {self.get_periodo_display()})"


# ─────────────────────────────────────────
# EXECUÇÃO — tarefa numa semana específica
# ─────────────────────────────────────────

class ExecucaoTarefaAdministrativa(models.Model):
    # Tarefa modelo — opcional para tarefas avulsas
    tarefa_modelo = models.ForeignKey(
        TarefaModeloAdministrativa,
        on_delete=models.PROTECT,
        related_name='execucoes',
        verbose_name='Tarefa Modelo',
        null=True, blank=True
    )

    # Campos para tarefas avulsas (sem tarefa_modelo)
    titulo_avulso    = models.CharField(max_length=200, blank=True, verbose_name='Título (avulso)')
    descricao_avulsa = models.TextField(blank=True, verbose_name='Descrição (avulso)')
    dia_avulso       = models.CharField(
        max_length=10,
        choices=DiaDaSemana.choices,
        blank=True,
        verbose_name='Dia (avulso)'
    )
    periodo_avulso   = models.CharField(
        max_length=10,
        choices=Periodo.choices,
        blank=True,
        verbose_name='Período (avulso)'
    )
    responsavel_avulso = models.ForeignKey(
        FuncionarioAdministrativo,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='execucoes_avulsas',
        verbose_name='Responsável (avulso)'
    )
    is_avulsa = models.BooleanField(default=False, verbose_name='Tarefa avulsa')

    # Campos comuns
    semana_iso = models.PositiveIntegerField(verbose_name='Semana ISO')
    ano        = models.PositiveIntegerField(verbose_name='Ano')
    status = models.CharField(
        max_length=15,
        choices=StatusExecucao.choices,
        default=StatusExecucao.PENDENTE,
        verbose_name='Status'
    )
    is_done       = models.BooleanField(default=False, verbose_name='Concluída')
    prazo         = models.DateField(null=True, blank=True, verbose_name='Prazo')
    concluido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='execucoes_concluidas',
        verbose_name='Concluído por'
    )
    concluido_em   = models.DateTimeField(null=True, blank=True, verbose_name='Concluído em')
    atualizado_em  = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='execucoes_atualizadas',
        verbose_name='Atualizado por'
    )

    class Meta:
        verbose_name = 'Execução de Tarefa'
        verbose_name_plural = 'Execuções de Tarefas'
        ordering = ['tarefa_modelo__dia_da_semana', 'tarefa_modelo__periodo']

    def __str__(self):
        return f"{self.titulo_display} — Semana {self.semana_iso}/{self.ano}"

    # ── Propriedades que unificam modelo e avulso ──

    @property
    def titulo_display(self):
        if self.tarefa_modelo:
            return self.tarefa_modelo.titulo
        return self.titulo_avulso or '(sem título)'

    @property
    def descricao_display(self):
        if self.tarefa_modelo:
            return self.tarefa_modelo.descricao
        return self.descricao_avulsa

    @property
    def dia_display(self):
        if self.tarefa_modelo:
            return self.tarefa_modelo.get_dia_da_semana_display()
        return self.get_dia_avulso_display() if self.dia_avulso else '—'

    @property
    def dia_key(self):
        if self.tarefa_modelo:
            return self.tarefa_modelo.dia_da_semana
        return self.dia_avulso

    @property
    def periodo_display(self):
        if self.tarefa_modelo:
            return self.tarefa_modelo.get_periodo_display()
        return self.get_periodo_avulso_display() if self.periodo_avulso else '—'

    @property
    def periodo_key(self):
        if self.tarefa_modelo:
            return self.tarefa_modelo.periodo
        return self.periodo_avulso

    @property
    def responsavel_display(self):
        if self.tarefa_modelo:
            return self.tarefa_modelo.responsavel.nome
        return self.responsavel_avulso.nome if self.responsavel_avulso else '—'

    @property
    def completion_pct(self):
        if self.tarefa_modelo and self.tarefa_modelo.tipo_controle == TipoControle.CHECKBOX:
            return 100 if self.is_done else 0
        return 100 if self.is_done else 0

    def comentarios_nao_lidos(self, user):
        """Retorna quantidade de comentários não lidos pelo user."""
        lidos = LeituraComentario.objects.filter(
            comentario__execucao=self,
            usuario=user
        ).values_list('comentario_id', flat=True)
        return self.comentarios.exclude(id__in=lidos).exclude(autor=user).count()


# ─────────────────────────────────────────
# COMENTÁRIO
# ─────────────────────────────────────────

class ComentarioTarefa(models.Model):
    execucao  = models.ForeignKey(
        ExecucaoTarefaAdministrativa,
        on_delete=models.CASCADE,
        related_name='comentarios',
        verbose_name='Execução'
    )
    autor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='comentarios_tarefas',
        verbose_name='Autor'
    )
    conteudo  = models.TextField(verbose_name='Comentário')
    criado_em = models.DateTimeField(auto_now_add=True)
    is_done   = models.BooleanField(default=False, verbose_name='Visto')

    class Meta:
        verbose_name = 'Comentário'
        verbose_name_plural = 'Comentários'
        ordering = ['criado_em']

    def __str__(self):
        return f"{self.autor} — {self.conteudo[:50]}"


# ─────────────────────────────────────────
# LEITURA DE COMENTÁRIO — quem leu o quê
# ─────────────────────────────────────────

class LeituraComentario(models.Model):
    comentario = models.ForeignKey(
        ComentarioTarefa,
        on_delete=models.CASCADE,
        related_name='leituras',
        verbose_name='Comentário'
    )
    usuario   = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='leituras_comentarios',
        verbose_name='Usuário'
    )
    lido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Leitura de Comentário'
        verbose_name_plural = 'Leituras de Comentários'
        unique_together = [['comentario', 'usuario']]

    def __str__(self):
        return f"{self.usuario} leu comentário #{self.comentario.id}"


# ─────────────────────────────────────────
# BLOCO SEMANAL
# ─────────────────────────────────────────

class BlocoSemanal(models.Model):
    tipo = models.CharField(
        max_length=20,
        choices=TipoBloco.choices,
        verbose_name='Tipo do Bloco'
    )
    semana_iso = models.PositiveIntegerField(verbose_name='Semana ISO')
    ano        = models.PositiveIntegerField(verbose_name='Ano')
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Criado por'
    )

    class Meta:
        verbose_name = 'Bloco Semanal'
        verbose_name_plural = 'Blocos Semanais'
        unique_together = [['tipo', 'semana_iso', 'ano']]

    def __str__(self):
        return f"{self.get_tipo_display()} — Semana {self.semana_iso}/{self.ano}"


# ─────────────────────────────────────────
# ITEM DO BLOCO
# ─────────────────────────────────────────

class ItemBlocoSemanal(models.Model):
    bloco    = models.ForeignKey(
        BlocoSemanal,
        on_delete=models.CASCADE,
        related_name='itens',
        verbose_name='Bloco'
    )
    conteudo = models.TextField(verbose_name='Conteúdo')
    is_fixo  = models.BooleanField(
        default=False,
        verbose_name='Item fixo',
        help_text='Itens fixos são copiados automaticamente para a semana seguinte'
    )
    is_done      = models.BooleanField(default=False, verbose_name='Concluído')
    ordem        = models.PositiveIntegerField(default=0, verbose_name='Ordem')
    responsavel  = models.ForeignKey(
        FuncionarioAdministrativo,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='itens_bloco',
        verbose_name='Responsável'
    )
    prazo        = models.DateField(null=True, blank=True, verbose_name='Prazo')
    criado_em    = models.DateTimeField(auto_now_add=True)
    criado_por   = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='itens_bloco_criados',
        verbose_name='Criado por'
    )

    class Meta:
        verbose_name = 'Item do Bloco'
        verbose_name_plural = 'Itens do Bloco'
        ordering = ['ordem']

    def __str__(self):
        return f"{self.conteudo[:50]}"
    

# ─────────────────────────────────────────
# COMENTÁRIO DO ITEM DO BLOCO
# ─────────────────────────────────────────

class ComentarioItemBloco(models.Model):
    item = models.ForeignKey(
        ItemBlocoSemanal,
        on_delete=models.CASCADE,
        related_name='comentarios',
        verbose_name='Item'
    )
    autor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='comentarios_itens_bloco',
        verbose_name='Autor'
    )
    conteudo  = models.TextField(verbose_name='Comentário')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Comentário de Item'
        verbose_name_plural = 'Comentários de Itens'
        ordering = ['criado_em']

    def __str__(self):
        return f"{self.autor} — {self.conteudo[:50]}"


# ─────────────────────────────────────────
# TAREFA DA DIVISÃO — lista pessoal semanal
# ─────────────────────────────────────────

class TarefaDivisao(models.Model):
    funcionario = models.ForeignKey(
        FuncionarioAdministrativo,
        on_delete=models.CASCADE,
        related_name='tarefas_divisao',
        verbose_name='Funcionário'
    )
    semana_iso  = models.PositiveIntegerField(verbose_name='Semana ISO')
    ano         = models.PositiveIntegerField(verbose_name='Ano')
    conteudo    = models.CharField(max_length=300, verbose_name='Tarefa')
    is_done     = models.BooleanField(default=False, verbose_name='Concluída')
    is_fixo     = models.BooleanField(default=False, verbose_name='Item fixo')
    prazo       = models.DateField(null=True, blank=True, verbose_name='Prazo')
    ordem       = models.PositiveIntegerField(default=0, verbose_name='Ordem')
    criado_em   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tarefa da Divisão'
        verbose_name_plural = 'Tarefas da Divisão'
        ordering = ['ordem', 'criado_em']

    def __str__(self):
        return f"{self.funcionario.nome} — {self.conteudo[:50]}"