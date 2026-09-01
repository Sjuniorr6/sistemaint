"""Cadastros base do Iscas Fast: Agente, Cliente, Deposito, ModeloEquipamento.

Nenhum destes tem campo de saldo — saldo é sempre derivado do livro-razão
(ISC-RN-01). Agente e Cliente são entidades de domínio, não usuários: não têm
credencial e não acessam o sistema (ISC-RN-15).

`iscas.Cliente` é cadastro próprio do app (ISC-ADR-17, confirmado contra o
código do GSInt): o `acompanhamento.Clientes` existente não tem endereço
estruturado nem coordenadas, e a fronteira de migração do ISC-ADR-01 depende de
não criar FK para outros apps.
"""
from django.core.exceptions import ValidationError
from django.db import models

from iscas import crypto
from iscas.enums import GeoOrigem, TipoDocumento, TipoModelo, UF_CHOICES
from iscas.models.base import BaseModel, EnderecoGeoMixin


class Deposito(BaseModel, EnderecoGeoMixin):
    """Ponto de estoque da matriz.

    Modelado como entidade desde o MVP mesmo existindo um único registro: o
    custo de criar a tabela agora é zero, e o de refatorar depois — quando
    surgir o segundo ponto de estoque — não é.
    """

    nome = models.CharField(max_length=120, verbose_name="Nome")

    class Meta:
        verbose_name = "Depósito"
        verbose_name_plural = "Depósitos"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Agente(BaseModel, EnderecoGeoMixin):
    """Pessoa que mantém iscas em posse e entrega ao cliente.

    Não tem login (ISC-RN-15). O saldo dele é uma consulta ao livro, nunca um
    campo aqui (ISC-RN-01). O CPF fica cifrado, com hash UNIQUE para unicidade
    (ISC-ADR-14) — atribua via a property `cpf`, que mantém os dois campos
    coerentes.
    """

    nome = models.CharField(max_length=150, verbose_name="Nome")
    cpf_cifrado = models.TextField(blank=True, verbose_name="CPF (cifrado)")
    cpf_hash = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="CPF (hash)",
        help_text="SHA-256 com pepper; garante unicidade sem decifrar.",
    )
    telefone = models.CharField(max_length=30, verbose_name="Telefone")
    email = models.EmailField(max_length=254, blank=True, verbose_name="E-mail")
    observacao = models.TextField(blank=True, verbose_name="Observação")

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"
        ordering = ["nome"]
        indexes = [
            # Sustenta o pré-filtro por bounding box da busca por proximidade
            # (ISC-ADR-09). Sem PostGIS, é este B-tree que faz o trabalho.
            models.Index(fields=["latitude", "longitude"], name="iscas_agente_latlng"),
            models.Index(fields=["is_active", "nome"], name="iscas_agente_ativo_nome"),
        ]

    def __str__(self):
        return self.nome

    # — CPF: a property é a interface; os campos são armazenamento —

    @property
    def cpf(self) -> str:
        """CPF em claro. Uso restrito à ficha do agente (ISC-RN-16)."""
        return crypto.decifrar_cpf(self.cpf_cifrado)

    @cpf.setter
    def cpf(self, valor: str):
        """Cifra e recalcula o hash — os dois campos nunca divergem."""
        self.cpf_cifrado = crypto.cifrar_cpf(valor)
        self.cpf_hash = crypto.hash_cpf(valor)

    @property
    def cpf_mascarado(self) -> str:
        """O que listagens e templates podem exibir (ISC-RN-16)."""
        return crypto.mascarar_cpf(self.cpf)

    def clean(self):
        super().clean()
        if self.cpf_cifrado and not crypto.cpf_valido(self.cpf):
            raise ValidationError({"cpf": "CPF inválido."})


class Cliente(BaseModel, EnderecoGeoMixin):
    """Empresa ou pessoa que solicita iscas.

    O endereço dele é o ponto de referência da busca por proximidade. Não tem
    login (ISC-RN-15).
    """

    nome_razao_social = models.CharField(max_length=200, verbose_name="Nome / Razão social")
    documento = models.CharField(max_length=20, blank=True, verbose_name="Documento")
    tipo_documento = models.CharField(
        max_length=4,
        choices=TipoDocumento.choices,
        default=TipoDocumento.CNPJ,
        verbose_name="Tipo de documento",
    )
    contato_nome = models.CharField(max_length=120, blank=True, verbose_name="Contato")
    telefone = models.CharField(max_length=30, blank=True, verbose_name="Telefone")
    email = models.EmailField(max_length=254, blank=True, verbose_name="E-mail")
    comercial_responsavel = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Comercial responsável",
        help_text="Quem atende esta conta no comercial da Golden Sat.",
    )
    observacao = models.TextField(blank=True, verbose_name="Observação")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nome_razao_social"]
        indexes = [
            models.Index(fields=["latitude", "longitude"], name="iscas_cliente_latlng"),
            models.Index(fields=["is_active", "nome_razao_social"], name="iscas_cli_ativo_nome"),
        ]

    def __str__(self):
        return self.nome_razao_social

    @property
    def documento_mascarado(self) -> str:
        """Documento parcial para listagens (ISC-RN-16 aplicado ao cliente)."""
        numeros = crypto.normalizar_cpf(self.documento)
        if not numeros:
            return ""
        if len(numeros) <= 4:
            return "*" * len(numeros)
        return f"{'*' * (len(numeros) - 4)}{numeros[-4:]}"


class ModeloEquipamento(BaseModel):
    """Modelo de isca. O `tipo` define se a unidade volta ao estoque.

    O tipo é imutável depois que existir movimentação de qualquer unidade do
    modelo (ISC-RN-04): mudá-lo retroativamente reescreveria o significado do
    histórico já gravado. A guarda real está na service layer, que enxerga o
    livro-razão; aqui fica o `clean()` para o /admin e os forms.
    """

    nome = models.CharField(max_length=150, verbose_name="Nome")
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    fabricante = models.CharField(max_length=120, blank=True, verbose_name="Fabricante")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    tipo = models.CharField(
        max_length=20, choices=TipoModelo.choices, verbose_name="Tipo"
    )

    class Meta:
        verbose_name = "Modelo de equipamento"
        verbose_name_plural = "Modelos de equipamento"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.codigo})"

    @property
    def eh_retornavel(self) -> bool:
        return self.tipo == TipoModelo.RETORNAVEL

    def tem_movimentacao(self) -> bool:
        """Existe unidade deste modelo com lançamento no livro? (ISC-RN-04)"""
        from iscas.models.custodia import MovimentacaoUnidade

        return MovimentacaoUnidade.objects.filter(unidade__modelo=self).exists()

    def clean(self):
        super().clean()
        if not self.pk:
            return
        anterior = (
            type(self).todos.filter(pk=self.pk).values_list("tipo", flat=True).first()
        )
        if anterior and anterior != self.tipo and self.tem_movimentacao():
            raise ValidationError(
                {
                    "tipo": (
                        "O tipo não pode mudar: já existem unidades deste modelo "
                        "com movimentação registrada (ISC-RN-04)."
                    )
                }
            )
