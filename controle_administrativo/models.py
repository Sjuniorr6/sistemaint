from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─────────────────────────────────────────
# CHOICES — opções fixas usadas nos campos
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
    NAO_ESQUECER = 'nao_esquecer', 'Importantes / Não Esquecer'
    DIARIO       = 'diario',       'Diário'
    OBSERVACAO   = 'observacao',   'Outros / Observação'


class PerfilFuncionario(models.TextChoices):
    GESTOR   = 'gestor',   'Gestor'
    OPERADOR = 'operador', 'Operador'


# ─────────────────────────────────────────
# FUNCIONÁRIO — perfil do usuário no SCA
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
# CATEGORIA — agrupamento de tarefas
# ─────────────────────────────────────────

class CategoriaTarefaAdministrativa(models.Model):
    nome = models.CharField(max_length=100, verbose_name='Nome')
    cor  = models.CharField(
        max_length=20,
        default='#665b1d',
        verbose_name='Cor (hex)'
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')

    class Meta:
        verbose_name = 'Categoria de Tarefa'
        verbose_name_plural = 'Categorias de Tarefas'
        ordering = ['nome']

    def __str__(self):
        return self.nome


# ─────────────────────────────────────────
# TAREFA MODELO — o "molde" recorrente
# ─────────────────────────────────────────

class TarefaModeloAdministrativa(models.Model):
    titulo = models.CharField(max_length=200, verbose_name='Título')
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
        null=True,
        blank=True,
        related_name='tarefas_modelo',
        verbose_name='Categoria'
    )
    ordem = models.PositiveIntegerField(
        default=0,
        verbose_name='Ordem de exibição'
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tarefa Modelo'
        verbose_name_plural = 'Tarefas Modelo'
        ordering = ['dia_da_semana', 'periodo', 'ordem']

    def __str__(self):
        return f"{self.titulo} ({self.get_dia_da_semana_display()} - {self.get_periodo_display()})"


# ─────────────────────────────────────────
# EXECUÇÃO — a tarefa numa semana específica
# ─────────────────────────────────────────

class ExecucaoTarefaAdministrativa(models.Model):
    tarefa_modelo = models.ForeignKey(
        TarefaModeloAdministrativa,
        on_delete=models.PROTECT,
        related_name='execucoes',
        verbose_name='Tarefa Modelo'
    )
    semana_iso = models.PositiveIntegerField(verbose_name='Semana ISO')
    ano        = models.PositiveIntegerField(verbose_name='Ano')
    status = models.CharField(
        max_length=15,
        choices=StatusExecucao.choices,
        default=StatusExecucao.PENDENTE,
        verbose_name='Status'
    )
    is_done    = models.BooleanField(default=False, verbose_name='Concluída')
    comentario = models.TextField(blank=True, verbose_name='Comentário')
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='execucoes_atualizadas',
        verbose_name='Atualizado por'
    )

    class Meta:
        verbose_name = 'Execução de Tarefa'
        verbose_name_plural = 'Execuções de Tarefas'
        ordering = ['tarefa_modelo__dia_da_semana', 'tarefa_modelo__periodo']
        # Garante que não existe duplicata: mesma tarefa, mesma semana, mesmo ano
        unique_together = [['tarefa_modelo', 'semana_iso', 'ano']]

    def __str__(self):
        return f"{self.tarefa_modelo.titulo} — Semana {self.semana_iso}/{self.ano}"

    @property
    def completion_pct(self):
        """
        Calcula o percentual de conclusão.
        - Tipo checkbox: 0 ou 100
        - Tipo percentual: baseado nas subtarefas concluídas
        """
        if self.tarefa_modelo.tipo_controle == TipoControle.CHECKBOX:
            return 100 if self.is_done else 0
        subtarefas = self.execucoes_subtarefa.all()
        total = subtarefas.count()
        if total == 0:
            return 0
        concluidas = subtarefas.filter(is_done=True).count()
        return round((concluidas / total) * 100)


# ─────────────────────────────────────────
# BLOCO SEMANAL — coluna lateral do painel
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
        null=True,
        blank=True,
        verbose_name='Criado por'
    )

    class Meta:
        verbose_name = 'Bloco Semanal'
        verbose_name_plural = 'Blocos Semanais'
        unique_together = [['tipo', 'semana_iso', 'ano']]

    def __str__(self):
        return f"{self.get_tipo_display()} — Semana {self.semana_iso}/{self.ano}"


# ─────────────────────────────────────────
# ITEM DO BLOCO — cada linha do bloco
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
    is_done  = models.BooleanField(default=False, verbose_name='Concluído')
    ordem    = models.PositiveIntegerField(default=0, verbose_name='Ordem')

    class Meta:
        verbose_name = 'Item do Bloco'
        verbose_name_plural = 'Itens do Bloco'
        ordering = ['ordem']

    def __str__(self):
        return f"{self.conteudo[:50]}"