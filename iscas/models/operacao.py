"""Solicitação, Atribuição e a reserva de unidades.

Diferente da situação da unidade (derivada, ISC-ADR-07), o status de
`Solicitacao` e `Atribuicao` é workflow de primeira classe: tem atores, guardas
e transições inválidas. Fica armazenado, mutável apenas por
`services.solicitacao.transitar()`, com evento no log (ISC-ADR-08).

`AtribuicaoUnidade` é a reserva. Não existe campo "reservado" em lugar nenhum:
a reserva É a existência da linha com `liberada_em IS NULL` (ISC-ADR-06).
"""
from django.conf import settings
from django.db import models
from django.db.models import Q

from iscas.enums import StatusAtribuicao, StatusSolicitacao
from iscas.models.base import BaseModel, LogModel


class Solicitacao(BaseModel):
    """Pedido de um cliente, atendido por uma ou mais atribuições (ISC-RN-10)."""

    cliente = models.ForeignKey(
        "iscas.Cliente",
        on_delete=models.PROTECT,
        related_name="solicitacoes",
        verbose_name="Cliente",
    )
    status = models.CharField(
        max_length=20,
        choices=StatusSolicitacao.choices,
        default=StatusSolicitacao.ABERTA,
        verbose_name="Status",
    )
    aberta_em = models.DateTimeField(verbose_name="Aberta em")
    aberta_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="solicitacoes_iscas",
        verbose_name="Aberta por",
    )
    prazo_desejado = models.DateField(null=True, blank=True, verbose_name="Prazo desejado")
    observacao = models.TextField(blank=True, verbose_name="Observação")
    motivo_cancelamento = models.TextField(blank=True, verbose_name="Motivo do cancelamento")

    # — Dados de contato e entrega, copiados do cliente na abertura —
    #
    # São uma CÓPIA, não uma leitura do cadastro: a entrega pode ir para um
    # endereço eventual (obra, filial) sem sobrescrever o endereço principal
    # do cliente, e a solicitação antiga continua mostrando para onde foi de
    # fato mesmo que o cadastro mude depois. O nome do cliente não é copiado —
    # esse vem sempre da FK, para não haver duas versões da mesma identidade.
    documento = models.CharField(max_length=20, blank=True, verbose_name="CNPJ / CPF")
    email = models.EmailField(max_length=254, blank=True, verbose_name="E-mail")
    contato_nome = models.CharField(max_length=120, blank=True, verbose_name="Contato")
    telefone = models.CharField(max_length=30, blank=True, verbose_name="Telefone")
    comercial_responsavel = models.CharField(
        max_length=120, blank=True, verbose_name="Comercial responsável"
    )
    entrega_logradouro = models.CharField(max_length=200, blank=True, verbose_name="Logradouro")
    entrega_numero = models.CharField(max_length=20, blank=True, verbose_name="Número")
    entrega_complemento = models.CharField(max_length=100, blank=True, verbose_name="Complemento")
    entrega_bairro = models.CharField(max_length=100, blank=True, verbose_name="Bairro")
    entrega_cidade = models.CharField(max_length=100, blank=True, verbose_name="Cidade")
    entrega_uf = models.CharField(max_length=2, blank=True, verbose_name="UF")
    entrega_cep = models.CharField(max_length=9, blank=True, verbose_name="CEP")

    # Coordenada DO PONTO DE ENTREGA, não do cadastro do cliente. É daqui que
    # a busca por proximidade mede a distância: a isca vai para onde a entrega
    # diz, não para onde o cliente tem sede. Sem isto, cliente sem endereço
    # cadastrado — caso agora legítimo — ficaria fora da busca e do mapa mesmo
    # com endereço de entrega preenchido.
    entrega_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Latitude da entrega"
    )
    entrega_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Longitude da entrega"
    )
    entrega_geo_origem = models.CharField(
        max_length=20, default="PENDENTE", verbose_name="Origem da coordenada de entrega"
    )

    class Meta:
        verbose_name = "Solicitação"
        verbose_name_plural = "Solicitações"
        ordering = ["-aberta_em", "-id"]
        indexes = [
            models.Index(fields=["status", "-aberta_em"], name="iscas_sol_status_data"),
            models.Index(fields=["cliente", "-aberta_em"], name="iscas_sol_cliente"),
            # Sustenta o pré-filtro por bounding box quando a origem da busca é
            # o ponto de entrega, do mesmo jeito que o índice do agente.
            models.Index(
                fields=["entrega_latitude", "entrega_longitude"],
                name="iscas_sol_entrega_latlng",
            ),
        ]

    def __str__(self):
        return f"Solicitação #{self.pk} — {self.cliente}"

    @property
    def eh_terminal(self) -> bool:
        return self.status in (StatusSolicitacao.ENTREGUE, StatusSolicitacao.CANCELADA)

    def atribuicoes_ativas(self):
        """Atribuições que ainda seguram reserva ou aguardam entrega."""
        return self.atribuicoes.filter(
            status__in=(StatusAtribuicao.RESERVADA, StatusAtribuicao.EM_ROTA)
        )

    @property
    def endereco_entrega(self) -> str:
        """Endereço de entrega numa linha, para exibição e WhatsApp.

        Cai para o endereço do cadastro quando a solicitação não tem cópia —
        é o caso das abertas antes destes campos existirem. Com o endereço do
        cliente opcional, esse fallback pode ser vazio: a tela mostra o aviso
        em vez de uma linha em branco.
        """
        if not self.entrega_logradouro:
            return self.cliente.endereco_completo or "Endereço de entrega não informado"

        partes = [self.entrega_logradouro]
        if self.entrega_numero:
            partes.append(self.entrega_numero)
        if self.entrega_complemento:
            partes.append(self.entrega_complemento)
        if self.entrega_bairro:
            partes.append(self.entrega_bairro)
        if self.entrega_cidade:
            partes.append(
                f"{self.entrega_cidade} - {self.entrega_uf}"
                if self.entrega_uf
                else self.entrega_cidade
            )
        if self.entrega_cep:
            partes.append(f"CEP {self.entrega_cep}")
        return ", ".join(p for p in partes if p)

    @property
    def entrega_para_geocodificacao(self) -> str:
        """Endereço de entrega enxuto, do jeito que o Nominatim entende.

        Mesmas omissões do `EnderecoGeoMixin.endereco_para_geocodificacao`:
        sem CEP (faz a busca voltar vazia) e sem complemento (é ruído).
        """
        partes = [self.entrega_logradouro]
        if self.entrega_numero:
            partes.append(self.entrega_numero)
        if self.entrega_bairro:
            partes.append(self.entrega_bairro)
        if self.entrega_cidade:
            partes.append(
                f"{self.entrega_cidade} - {self.entrega_uf}"
                if self.entrega_uf
                else self.entrega_cidade
            )
        return ", ".join(p for p in partes if p)

    @property
    def coordenada_de_busca(self):
        """`(latitude, longitude)` de onde medir a distância até os agentes.

        A da entrega vence; a do cadastro do cliente é fallback para as
        solicitações abertas antes destes campos existirem. `None` quando não
        há nenhuma das duas — quem chama avisa o operador em vez de devolver
        "nenhum agente próximo", que mentiria sobre a causa.
        """
        if self.entrega_latitude is not None and self.entrega_longitude is not None:
            return self.entrega_latitude, self.entrega_longitude
        if self.cliente.tem_coordenada:
            return self.cliente.latitude, self.cliente.longitude
        return None

    @property
    def tem_coordenada_de_busca(self) -> bool:
        return self.coordenada_de_busca is not None

    @property
    def entrega_em_outro_endereco(self) -> bool:
        """A entrega vai para lugar diferente do cadastro do cliente?

        A tela sinaliza isso: entrega fora do endereço principal é exceção e
        merece destaque para o operador conferir antes de despachar.
        """
        if not self.entrega_logradouro:
            return False
        # Cliente sem endereço cadastrado: não há com o que comparar, então
        # não há divergência a sinalizar — a entrega é simplesmente o endereço
        # daquela solicitação.
        if not self.cliente.tem_endereco:
            return False
        cadastro = (
            (self.cliente.logradouro or "").strip().lower(),
            (self.cliente.numero or "").strip().lower(),
        )
        atual = (
            self.entrega_logradouro.strip().lower(),
            (self.entrega_numero or "").strip().lower(),
        )
        return cadastro != atual


class ItemSolicitacao(models.Model):
    """Quanto de cada modelo o cliente pediu."""

    solicitacao = models.ForeignKey(
        "iscas.Solicitacao",
        on_delete=models.CASCADE,
        related_name="itens",
        verbose_name="Solicitação",
    )
    modelo = models.ForeignKey(
        "iscas.ModeloEquipamento",
        on_delete=models.PROTECT,
        related_name="itens_solicitacao",
        verbose_name="Modelo",
    )
    quantidade = models.PositiveIntegerField(verbose_name="Quantidade")

    class Meta:
        verbose_name = "Item da solicitação"
        verbose_name_plural = "Itens da solicitação"
        constraints = [
            models.UniqueConstraint(
                fields=["solicitacao", "modelo"], name="iscas_item_modelo_unico"
            ),
            models.CheckConstraint(
                condition=Q(quantidade__gt=0), name="iscas_item_qtd_positiva"
            ),
        ]

    def __str__(self):
        return f"{self.quantidade}× {self.modelo}"


class Atribuicao(BaseModel):
    """Vínculo agente ↔ solicitação, com as unidades reservadas.

    A criação reserva unidades; a confirmação de entrega é que transfere
    custódia (ISC-RN-08). O cancelamento libera as reservas sem gerar
    lançamento — nada mudou de custódia (ISC-RN-09).
    """

    solicitacao = models.ForeignKey(
        "iscas.Solicitacao",
        on_delete=models.PROTECT,
        related_name="atribuicoes",
        verbose_name="Solicitação",
    )
    agente = models.ForeignKey(
        "iscas.Agente",
        on_delete=models.PROTECT,
        related_name="atribuicoes",
        verbose_name="Agente",
    )
    status = models.CharField(
        max_length=20,
        choices=StatusAtribuicao.choices,
        default=StatusAtribuicao.RESERVADA,
        verbose_name="Status",
    )
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="atribuicoes_iscas",
        verbose_name="Criada por",
    )
    em_rota_em = models.DateTimeField(null=True, blank=True, verbose_name="Em rota em")
    entregue_em = models.DateTimeField(null=True, blank=True, verbose_name="Entregue em")
    recebido_por = models.CharField(
        max_length=150, blank=True, verbose_name="Recebido por"
    )
    motivo_cancelamento = models.TextField(blank=True, verbose_name="Motivo do cancelamento")

    class Meta:
        verbose_name = "Atribuição"
        verbose_name_plural = "Atribuições"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["agente", "status"], name="iscas_atrib_agente_status"),
            models.Index(fields=["solicitacao", "status"], name="iscas_atrib_sol_status"),
        ]

    def __str__(self):
        return f"Atribuição #{self.pk} — {self.agente}"

    @property
    def eh_terminal(self) -> bool:
        return self.status in (StatusAtribuicao.ENTREGUE, StatusAtribuicao.CANCELADA)

    def reservas_ativas(self):
        return self.reservas.filter(liberada_em__isnull=True)

    def unidades_reservadas(self):
        from iscas.models.custodia import Unidade

        return Unidade.objects.filter(
            reservas__atribuicao=self, reservas__liberada_em__isnull=True
        )


class AtribuicaoUnidade(models.Model):
    """A reserva de uma unidade por uma atribuição (ISC-ADR-06).

    Liberar é preencher `liberada_em`, NUNCA deletar: o histórico de reservas
    canceladas fica auditável.

    O índice único parcial abaixo é a garantia mais importante do app. No
    PostgreSQL ele é a terceira camada, depois do `select_for_update
    (skip_locked=True)`. Neste projeto, que roda SQLite — onde o Django ignora
    silenciosamente o `skip_locked` e não há lock de linha —, ele é a garantia
    PRINCIPAL de que uma unidade nunca tem duas reservas ativas (ISC-RN-07).
    Ver `services/reserva.py`.
    """

    atribuicao = models.ForeignKey(
        "iscas.Atribuicao",
        on_delete=models.PROTECT,
        related_name="reservas",
        verbose_name="Atribuição",
    )
    unidade = models.ForeignKey(
        "iscas.Unidade",
        on_delete=models.PROTECT,
        related_name="reservas",
        verbose_name="Unidade",
    )
    reservada_em = models.DateTimeField(auto_now_add=True, verbose_name="Reservada em")
    liberada_em = models.DateTimeField(null=True, blank=True, verbose_name="Liberada em")

    class Meta:
        verbose_name = "Reserva de unidade"
        verbose_name_plural = "Reservas de unidade"
        constraints = [
            models.UniqueConstraint(
                fields=["unidade"],
                condition=Q(liberada_em__isnull=True),
                name="iscas_reserva_ativa_unica",
            ),
        ]
        indexes = [
            models.Index(fields=["atribuicao", "liberada_em"], name="iscas_reserva_atrib"),
        ]

    def __str__(self):
        return f"{self.unidade} reservada por #{self.atribuicao_id}"

    @property
    def esta_ativa(self) -> bool:
        return self.liberada_em is None


class SolicitacaoEvento(LogModel):
    """Log append-only das transições de Solicitação e Atribuição (ISC-ADR-08).

    Mesmo padrão do `ChamadoEvento` do app Chamados: toda transição deixa
    rastro de quem, quando e de onde para onde.
    """

    solicitacao = models.ForeignKey(
        "iscas.Solicitacao",
        on_delete=models.PROTECT,
        related_name="eventos",
        verbose_name="Solicitação",
    )
    atribuicao = models.ForeignKey(
        "iscas.Atribuicao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="eventos",
        verbose_name="Atribuição",
    )
    status_anterior = models.CharField(max_length=20, blank=True, verbose_name="Status anterior")
    status_novo = models.CharField(max_length=20, verbose_name="Status novo")
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="eventos_iscas",
        verbose_name="Autor",
    )
    dados = models.JSONField(default=dict, blank=True, verbose_name="Dados")

    class Meta:
        verbose_name = "Evento de solicitação"
        verbose_name_plural = "Eventos de solicitação"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["solicitacao", "-created_at"], name="iscas_evt_sol"),
        ]

    def __str__(self):
        alvo = f"atribuição #{self.atribuicao_id}" if self.atribuicao_id else f"solicitação #{self.solicitacao_id}"
        return f"{alvo}: {self.status_anterior or '—'} → {self.status_novo}"
