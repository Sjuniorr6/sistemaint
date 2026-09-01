"""O livro-razão de custódia — o coração do Iscas Fast.

Mecânica de partidas dobradas aplicada a unidades físicas: toda mudança de
posse é um lançamento (`Movimentacao`) com conta de origem e conta de destino
(`Custodia`), detalhado em linhas (`MovimentacaoUnidade`) que carregam a
identidade de cada unidade envolvida.

Nenhum saldo é campo (ISC-RN-01). O log é append-only e imutável (ISC-RN-02):
correção só por estorno. A escrita destes models é exclusiva de
`iscas.services.custodia.registrar_movimentacao()` — nenhum outro módulo os
cria (ISC-ADR-02, com teste de arquitetura verificando isso).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, Exists, OuterRef, Q, Value, When

from iscas.enums import (
    CUSTODIAS_CONCRETAS,
    CUSTODIAS_SINGLETON,
    MotivoBaixa,
    SituacaoUnidade,
    StatusAtribuicao,
    TipoCustodia,
    TipoModelo,
    TipoMovimentacao,
)
from iscas.models.base import BaseModel, LogModel


class Custodia(BaseModel):
    """Uma "conta" do livro-razão (ISC-ADR-03).

    A alternativa — seis FKs nuláveis em `Movimentacao`, ou uma
    `GenericForeignKey` — poluiria o modelo e destruiria a indexabilidade. Com
    conta única, todo lançamento é um par de FKs indexadas, e acrescentar um
    novo tipo de custódia não altera `Movimentacao`.

    Contas de Agente, Cliente e Depósito nascem junto com a entidade (signal);
    EXTERNO, MANUTENCAO e BAIXA são singletons criados por migration de dados.
    """

    tipo = models.CharField(
        max_length=20, choices=TipoCustodia.choices, verbose_name="Tipo"
    )
    agente = models.OneToOneField(
        "iscas.Agente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="custodia",
        verbose_name="Agente",
    )
    cliente = models.OneToOneField(
        "iscas.Cliente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="custodia",
        verbose_name="Cliente",
    )
    deposito = models.OneToOneField(
        "iscas.Deposito",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="custodia",
        verbose_name="Depósito",
    )
    descricao = models.CharField(max_length=200, blank=True, verbose_name="Descrição")

    class Meta:
        verbose_name = "Custódia"
        verbose_name_plural = "Custódias"
        ordering = ["tipo"]
        constraints = [
            # Tipos concretos exigem exatamente uma FK; singletons, nenhuma.
            # É a constraint que impede uma conta órfã ou ambígua no livro.
            models.CheckConstraint(
                condition=(
                    (
                        Q(tipo=TipoCustodia.AGENTE)
                        & Q(agente__isnull=False)
                        & Q(cliente__isnull=True)
                        & Q(deposito__isnull=True)
                    )
                    | (
                        Q(tipo=TipoCustodia.CLIENTE)
                        & Q(agente__isnull=True)
                        & Q(cliente__isnull=False)
                        & Q(deposito__isnull=True)
                    )
                    | (
                        Q(tipo=TipoCustodia.DEPOSITO)
                        & Q(agente__isnull=True)
                        & Q(cliente__isnull=True)
                        & Q(deposito__isnull=False)
                    )
                    | (
                        Q(tipo__in=CUSTODIAS_SINGLETON)
                        & Q(agente__isnull=True)
                        & Q(cliente__isnull=True)
                        & Q(deposito__isnull=True)
                    )
                ),
                name="iscas_custodia_vinculo_coerente",
            ),
            # Um único registro por tipo singleton — a conta BAIXA é uma só.
            models.UniqueConstraint(
                fields=["tipo"],
                condition=Q(tipo__in=CUSTODIAS_SINGLETON),
                name="iscas_custodia_singleton_unica",
            ),
        ]

    def __str__(self):
        if self.agente_id:
            return f"Agente: {self.agente}"
        if self.cliente_id:
            return f"Cliente: {self.cliente}"
        if self.deposito_id:
            return f"Depósito: {self.deposito}"
        return self.get_tipo_display()

    @property
    def eh_singleton(self) -> bool:
        return self.tipo in CUSTODIAS_SINGLETON

    @property
    def eh_terminal(self) -> bool:
        """Conta da qual nada sai (a unidade que entra aqui não volta).

        BAIXA é terminal sempre. CLIENTE é terminal só para descartável — essa
        distinção depende do modelo da unidade e é resolvida em `com_situacao()`.
        """
        return self.tipo == TipoCustodia.BAIXA

    def clean(self):
        super().clean()
        vinculos = [self.agente_id, self.cliente_id, self.deposito_id]
        preenchidos = [v for v in vinculos if v is not None]
        if self.tipo in CUSTODIAS_CONCRETAS and len(preenchidos) != 1:
            raise ValidationError(
                f"Custódia do tipo {self.tipo} exige exatamente um vínculo."
            )
        if self.eh_singleton and preenchidos:
            raise ValidationError(
                f"Custódia do tipo {self.tipo} é singleton e não aceita vínculo."
            )


class UnidadeQuerySet(models.QuerySet):
    """Consultas de unidade — inclusive a situação derivada (ISC-ADR-07)."""

    def com_situacao(self):
        """Anota `situacao` a partir de custódia, tipo do modelo e reserva.

        A situação NÃO é campo: seria uma terceira cópia de uma verdade que já
        está na custódia atual e na existência de reserva ativa. A ordem dos
        `When` é a da tabela do ARCHITECTURE e importa — reserva com atribuição
        EM_ROTA precisa ser avaliada antes da reserva genérica.
        """
        from iscas.models.operacao import AtribuicaoUnidade

        reserva_ativa = AtribuicaoUnidade.objects.filter(
            unidade=OuterRef("pk"), liberada_em__isnull=True
        )
        reserva_em_rota = reserva_ativa.filter(
            atribuicao__status=StatusAtribuicao.EM_ROTA
        )

        return self.annotate(
            _tem_reserva=Exists(reserva_ativa),
            _tem_reserva_em_rota=Exists(reserva_em_rota),
            situacao=Case(
                When(
                    custodia_atual__tipo=TipoCustodia.BAIXA,
                    then=Value(SituacaoUnidade.BAIXADA),
                ),
                When(
                    custodia_atual__tipo=TipoCustodia.MANUTENCAO,
                    then=Value(SituacaoUnidade.EM_MANUTENCAO),
                ),
                When(
                    custodia_atual__tipo=TipoCustodia.CLIENTE,
                    modelo__tipo=TipoModelo.DESCARTAVEL,
                    then=Value(SituacaoUnidade.CONSUMIDA),
                ),
                When(
                    custodia_atual__tipo=TipoCustodia.CLIENTE,
                    then=Value(SituacaoUnidade.COM_CLIENTE),
                ),
                When(
                    custodia_atual__tipo=TipoCustodia.AGENTE,
                    _tem_reserva_em_rota=True,
                    then=Value(SituacaoUnidade.EM_ROTA),
                ),
                When(
                    custodia_atual__tipo=TipoCustodia.AGENTE,
                    _tem_reserva=True,
                    then=Value(SituacaoUnidade.RESERVADA),
                ),
                When(
                    custodia_atual__tipo=TipoCustodia.AGENTE,
                    then=Value(SituacaoUnidade.COM_AGENTE),
                ),
                When(
                    custodia_atual__tipo=TipoCustodia.DEPOSITO,
                    then=Value(SituacaoUnidade.EM_DEPOSITO),
                ),
                default=Value(""),
                output_field=models.CharField(),
            ),
        )

    def disponiveis(self):
        """Sem reserva ativa — o que pode ser alocado ou movimentado."""
        from iscas.models.operacao import AtribuicaoUnidade

        return self.exclude(
            Exists(
                AtribuicaoUnidade.objects.filter(
                    unidade=OuterRef("pk"), liberada_em__isnull=True
                )
            )
        )

    def em_custodia(self, custodia):
        return self.filter(custodia_atual=custodia)

    def nao_terminais(self):
        """Exclui CONSUMIDA e BAIXADA — não podem ser origem de lançamento."""
        return self.exclude(
            Q(custodia_atual__tipo=TipoCustodia.BAIXA)
            | Q(
                custodia_atual__tipo=TipoCustodia.CLIENTE,
                modelo__tipo=TipoModelo.DESCARTAVEL,
            )
        )


class Unidade(models.Model):
    """Uma isca física, individualmente identificada (ISC-RN-03).

    A interface opera em lote ("dar baixa em 8"), mas alocação, reserva e
    lançamento são sempre unitários — é o que permite responder "onde está esta
    isca" e rastrear retornável em posse de cliente.

    Sem soft-delete: unidade não é cadastro, é objeto rastreado. O fim de vida
    dela é uma situação derivada (CONSUMIDA/BAIXADA), não um flag.
    """

    modelo = models.ForeignKey(
        "iscas.ModeloEquipamento",
        on_delete=models.PROTECT,
        related_name="unidades",
        verbose_name="Modelo",
    )
    identificador = models.CharField(
        max_length=100, unique=True, verbose_name="Identificador"
    )
    identificador_gerado = models.BooleanField(
        default=False,
        verbose_name="Identificador gerado pelo sistema",
        help_text="True quando a unidade não trouxe identificador de fábrica (ISC-RF-09).",
    )
    observacao = models.TextField(blank=True, verbose_name="Observação")

    # — Ponteiros de projeção (ISC-ADR-04) —
    # Desvio consciente do princípio "derivado nunca é campo", por razão
    # técnica: a custódia atual seria uma window function sobre o livro, e o
    # SQL não permite travar linhas (SELECT ... FOR UPDATE) numa query com
    # window function. Sem ponteiro não existe forma atômica de reservar.
    # Escritos EXCLUSIVAMENTE por registrar_movimentacao(), na mesma transação
    # do lançamento. O command `recomputar_custodias` os reconstrói a partir do
    # livro, que continua sendo a autoridade — o ponteiro é cache reconstruível.
    custodia_atual = models.ForeignKey(
        "iscas.Custodia",
        on_delete=models.PROTECT,
        related_name="unidades",
        verbose_name="Custódia atual",
    )
    custodia_desde = models.DateTimeField(verbose_name="Em custódia desde")
    ultima_movimentacao = models.ForeignKey(
        "iscas.Movimentacao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="unidades_apontadas",
        verbose_name="Última movimentação",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criada em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizada em")

    objects = UnidadeQuerySet.as_manager()

    class Meta:
        verbose_name = "Unidade"
        verbose_name_plural = "Unidades"
        ordering = ["identificador"]
        indexes = [
            # O índice que sustenta toda consulta de saldo. `custodia_desde`
            # entra junto porque a alocação é FIFO por essa coluna (ISC-RF-25).
            models.Index(
                fields=["custodia_atual", "modelo", "custodia_desde"],
                name="iscas_unid_cust_mod",
            ),
        ]

    def __str__(self):
        return self.identificador

    @property
    def tem_reserva_ativa(self) -> bool:
        return self.reservas.filter(liberada_em__isnull=True).exists()


class Movimentacao(LogModel):
    """Cabeçalho do lançamento — o "o quê, quem, quando e por quê".

    Um lote de 500 iscas é UM cabeçalho e 500 linhas: o cabeçalho carrega o
    significado da operação (autor, momento, justificativa, documento de
    origem); as linhas carregam a identidade.

    Append-only (herda de LogModel: `save()` em instância persistida levanta
    erro, `delete()` idem). Correção é por estorno (ISC-ADR-16).
    """

    tipo = models.CharField(
        max_length=25, choices=TipoMovimentacao.choices, verbose_name="Tipo"
    )
    origem = models.ForeignKey(
        "iscas.Custodia",
        on_delete=models.PROTECT,
        related_name="movimentacoes_saida",
        verbose_name="Origem",
    )
    destino = models.ForeignKey(
        "iscas.Custodia",
        on_delete=models.PROTECT,
        related_name="movimentacoes_entrada",
        verbose_name="Destino",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimentacoes_iscas",
        verbose_name="Autor",
    )
    # `ocorrido_em` é o momento real do fato, informado pelo operador;
    # `created_at` (de LogModel) é o momento do registro. A diferença entre os
    # dois é a defasagem operacional — medida, não escondida.
    ocorrido_em = models.DateTimeField(verbose_name="Ocorrido em")
    justificativa = models.TextField(blank=True, verbose_name="Justificativa")
    motivo_baixa = models.CharField(
        max_length=20,
        choices=MotivoBaixa.choices,
        blank=True,
        verbose_name="Motivo da baixa",
    )
    nota_fiscal = models.CharField(max_length=50, blank=True, verbose_name="Nota fiscal")
    lote = models.CharField(max_length=50, blank=True, verbose_name="Lote")
    solicitacao = models.ForeignKey(
        "iscas.Solicitacao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimentacoes",
        verbose_name="Solicitação",
    )
    atribuicao = models.ForeignKey(
        "iscas.Atribuicao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimentacoes",
        verbose_name="Atribuição",
    )
    estorno_de = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="estornos",
        verbose_name="Estorno de",
    )

    class Meta:
        verbose_name = "Movimentação"
        verbose_name_plural = "Movimentações"
        ordering = ["-ocorrido_em", "-id"]
        indexes = [
            models.Index(fields=["-ocorrido_em"], name="iscas_mov_ocorrido"),
            models.Index(fields=["tipo", "-ocorrido_em"], name="iscas_mov_tipo_data"),
            models.Index(fields=["origem", "-ocorrido_em"], name="iscas_mov_origem"),
            models.Index(fields=["destino", "-ocorrido_em"], name="iscas_mov_destino"),
        ]
        constraints = [
            # Baixa exige motivo; quem não é baixa não tem motivo de baixa.
            models.CheckConstraint(
                condition=(
                    Q(tipo=TipoMovimentacao.BAIXA) & ~Q(motivo_baixa="")
                    | ~Q(tipo=TipoMovimentacao.BAIXA) & Q(motivo_baixa="")
                ),
                name="iscas_mov_baixa_exige_motivo",
            ),
            # Estorno referencia o original; os demais tipos, não.
            models.CheckConstraint(
                condition=(
                    Q(tipo=TipoMovimentacao.ESTORNO, estorno_de__isnull=False)
                    | ~Q(tipo=TipoMovimentacao.ESTORNO) & Q(estorno_de__isnull=True)
                ),
                name="iscas_mov_estorno_referencia",
            ),
            models.CheckConstraint(
                condition=~Q(origem=models.F("destino")),
                name="iscas_mov_origem_difere_destino",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.origem} → {self.destino}"

    @property
    def quantidade(self) -> int:
        return self.linhas.count()

    @property
    def foi_estornada(self) -> bool:
        return self.estornos.exists()

    @property
    def estorno(self):
        """A movimentação que estornou esta, ou None.

        Permite o extrato mostrar o par (original ↔ estorno) junto, em vez de
        deixar o operador procurar o número na lista.
        """
        return self.estornos.first()

    @property
    def identificadores(self):
        """Identificadores das unidades movimentadas, em ordem.

        Usa `linhas.all()` para aproveitar o prefetch do selector — `values_list`
        dispararia uma consulta por movimentação exibida.
        """
        return sorted(linha.unidade.identificador for linha in self.linhas.all())

    @property
    def eh_saida_definitiva(self) -> bool:
        """A movimentação tirou equipamento do estoque para sempre?

        BAIXA sempre; ENTREGA só quando o modelo é descartável. É o que o
        extrato sinaliza em vermelho — o operador precisa distinguir "saiu e
        não volta" de "mudou de lugar".
        """
        from iscas.enums import TipoModelo

        if self.tipo == TipoMovimentacao.BAIXA:
            return True
        if self.tipo != TipoMovimentacao.ENTREGA:
            return False
        return all(
            linha.unidade.modelo.tipo == TipoModelo.DESCARTAVEL
            for linha in self.linhas.all()
        )


class MovimentacaoUnidade(LogModel):
    """Linha do lançamento: qual unidade participou de qual movimentação."""

    movimentacao = models.ForeignKey(
        "iscas.Movimentacao",
        on_delete=models.PROTECT,
        related_name="linhas",
        verbose_name="Movimentação",
    )
    unidade = models.ForeignKey(
        "iscas.Unidade",
        on_delete=models.PROTECT,
        related_name="movimentacoes",
        verbose_name="Unidade",
    )

    class Meta:
        verbose_name = "Linha de movimentação"
        verbose_name_plural = "Linhas de movimentação"
        constraints = [
            models.UniqueConstraint(
                fields=["movimentacao", "unidade"], name="iscas_movunid_unica"
            ),
        ]
        indexes = [
            # Extrato por unidade: "por onde esta isca passou" (ISC-RF-10).
            models.Index(fields=["unidade", "movimentacao"], name="iscas_movunid_extrato"),
        ]

    def __str__(self):
        return f"{self.unidade} em {self.movimentacao_id}"
