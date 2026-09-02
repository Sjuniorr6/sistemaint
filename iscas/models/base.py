"""Bases compartilhadas pelos models do Iscas Fast.

O GSInt não tem um `core.BaseModel` (o ARCHITECTURE presumia um que não
existe). Seguimos o padrão da casa — `models.Model` com PK inteira, como o app
Chamados — acrescentando o soft-delete que o ISC-ADR-15 exige. As bases vivem
dentro do app para respeitar a fronteira de migração do ISC-ADR-01: o Iscas
Fast não depende de nenhum app do GSInt além da autenticação.

`LogModel` é a contraparte: registros de log (Movimentacao,
MovimentacaoUnidade, SolicitacaoEvento) NÃO têm soft-delete nem updated_at —
são append-only e imutáveis (ISC-RN-17, ISC-ADR-15).
"""
from django.db import models


class ActiveManager(models.Manager):
    """Manager que esconde os registros desativados por padrão.

    `objects` filtra `is_active=True`; `todos` enxerga tudo — necessário para
    o /admin, para relatórios históricos e para as FKs que apontam para um
    cadastro já desativado (um agente inativo mantém saldo e histórico,
    ISC-RN-18).
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class BaseModel(models.Model):
    """Cadastro com timestamps e soft-delete (ISC-ADR-15).

    Usado por Agente, Cliente, Deposito, ModeloEquipamento e Custodia.
    Deleção real não é oferecida: `desativar()` marca `is_active=False`.
    """

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")

    # `objects` filtra ativos; `todos` é a via de escape explícita. A ordem
    # importa: o primeiro manager declarado vira `_default_manager`, usado pelo
    # /admin e por related managers.
    objects = ActiveManager()
    todos = models.Manager()

    class Meta:
        abstract = True

    def desativar(self, *, salvar=True):
        """Soft-delete. Regras de bloqueio ficam na service layer."""
        self.is_active = False
        if salvar:
            self.save(update_fields=["is_active", "updated_at"])

    def reativar(self, *, salvar=True):
        self.is_active = True
        if salvar:
            self.save(update_fields=["is_active", "updated_at"])


class LogModel(models.Model):
    """Registro de log: append-only, imutável, sem soft-delete (ISC-RN-17).

    Só `created_at`. Não há `updated_at` porque não há update: `save()` numa
    instância já persistida é rejeitado. Correção de lançamento errado se faz
    por estorno (ISC-ADR-16), nunca por edição.
    """

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Registrado em")

    objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Bloqueia update: log só aceita inserção.

        A guarda é aqui, no model, e não só na service layer, porque o custo de
        um update silencioso num livro-razão é reescrever todo saldo derivado
        dele. `_state.adding` distingue insert de update de forma confiável,
        inclusive quando a PK foi atribuída à mão.
        """
        if not self._state.adding:
            raise ValueError(
                f"{type(self).__name__} é append-only (ISC-RN-17): "
                "registro já persistido não pode ser alterado. "
                "Para corrigir um lançamento, use um estorno."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(
            f"{type(self).__name__} é append-only (ISC-RN-17): "
            "registro de log não pode ser apagado."
        )


class EnderecoGeoMixin(models.Model):
    """Endereço estruturado + coordenadas, comum a Agente, Cliente e Depósito.

    As coordenadas são nuláveis de propósito: falha de geocodificação não pode
    impedir o cadastro (ISC-RF-02). O par nulo sinaliza pendência — o registro
    fica fora da busca por proximidade, mas visível na listagem com alerta
    (ISC-RN-12).
    """

    # Todos em branco por padrão: quem exige endereço é o formulário, não o
    # armazenamento. Cliente pode ser cadastrado sem endereço (a entrega vai
    # para onde a solicitação disser); agente e depósito seguem obrigatórios
    # pelos forms deles, porque sem endereço saem da busca por proximidade.
    logradouro = models.CharField(max_length=200, blank=True, verbose_name="Logradouro")
    numero = models.CharField(max_length=20, blank=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, blank=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, blank=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, blank=True, verbose_name="Cidade")
    uf = models.CharField(max_length=2, blank=True, verbose_name="UF")
    cep = models.CharField(max_length=9, blank=True, verbose_name="CEP")

    # Decimal, não Float: coordenada é dado de identificação, e erro de
    # arredondamento binário em ponto flutuante desloca o pin.
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Latitude"
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Longitude"
    )
    geo_origem = models.CharField(
        max_length=20,
        default="PENDENTE",
        verbose_name="Origem da coordenada",
    )
    geocodificado_em = models.DateTimeField(
        null=True, blank=True, verbose_name="Geocodificado em"
    )

    class Meta:
        abstract = True

    @property
    def tem_coordenada(self) -> bool:
        """Participa da busca por proximidade? (ISC-RN-12)"""
        return self.latitude is not None and self.longitude is not None

    @property
    def tem_endereco(self) -> bool:
        """Há endereço preenchido? Cliente sem endereço é caso legítimo."""
        return bool(self.logradouro or self.cidade or self.cep)

    @property
    def endereco_completo(self) -> str:
        """Uma linha, para exibição e para o texto de WhatsApp.

        Para geocodificar use `endereco_para_geocodificacao` — este aqui traz
        campos que atrapalham o provedor.
        """
        partes = [self.logradouro]
        if self.numero:
            partes.append(self.numero)
        if self.complemento:
            partes.append(self.complemento)
        if self.bairro:
            partes.append(self.bairro)
        if self.cidade:
            partes.append(f"{self.cidade} - {self.uf}" if self.uf else self.cidade)
        elif self.uf:
            partes.append(self.uf)
        if self.cep:
            partes.append(f"CEP {self.cep}")
        return ", ".join(p for p in partes if p)

    @property
    def endereco_para_geocodificacao(self) -> str:
        """Endereço enxuto, do jeito que o Nominatim entende.

        Difere do `endereco_completo` em duas omissões deliberadas, ambas
        verificadas contra o serviço real:

        - **CEP**: anexar "CEP 01310-100" faz a busca voltar VAZIA, mesmo para
          endereços óbvios. O Nominatim trata o texto livre como parte do
          logradouro e não casa com nada.
        - **Complemento**: "de 612 a 1510 - lado par" e afins são ruído; o
          provedor não tem esse nível de detalhe e a string extra só atrapalha.

        O número permanece — é ele que tira o pin do centroide da rua e o põe
        na porta certa.
        """
        partes = [self.logradouro]
        if self.numero:
            partes.append(self.numero)
        if self.bairro:
            partes.append(self.bairro)
        if self.cidade:
            partes.append(f"{self.cidade} - {self.uf}" if self.uf else self.cidade)
        return ", ".join(p for p in partes if p)
