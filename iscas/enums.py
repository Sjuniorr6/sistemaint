"""Choices tipados do app Iscas Fast (PRD, seções de ciclo de vida).

Centraliza os vocabulários de custódia, movimentação, situação da unidade e
estados de Solicitação/Atribuição. Models, services, forms e templates
consultam daqui — nenhuma string solta espalhada pelo código.
"""
from django.db import models

# Grupo Django que autoriza operar o app (ISC-RN-19, ARCHITECTURE "Permissões").
GRUPO_OPERADORES = "Operadores Iscas"


class TipoModelo(models.TextChoices):
    """Descartável sai do estoque na entrega; retornável volta (ISC-RN-04)."""

    DESCARTAVEL = "DESCARTAVEL", "Descartável"
    RETORNAVEL = "RETORNAVEL", "Retornável"


class TipoCustodia(models.TextChoices):
    """As "contas" do livro-razão (ISC-ADR-03).

    DEPOSITO, AGENTE e CLIENTE têm entidade correspondente; EXTERNO,
    MANUTENCAO e BAIXA são singletons criados por migration de dados.
    """

    EXTERNO = "EXTERNO", "Externo"
    DEPOSITO = "DEPOSITO", "Depósito"
    AGENTE = "AGENTE", "Agente"
    CLIENTE = "CLIENTE", "Cliente"
    MANUTENCAO = "MANUTENCAO", "Manutenção"
    BAIXA = "BAIXA", "Baixa"


#: Custódias singleton — uma instância só, sem entidade vinculada.
CUSTODIAS_SINGLETON = (
    TipoCustodia.EXTERNO,
    TipoCustodia.MANUTENCAO,
    TipoCustodia.BAIXA,
)

#: Custódias que exigem exatamente uma FK preenchida.
CUSTODIAS_CONCRETAS = (
    TipoCustodia.DEPOSITO,
    TipoCustodia.AGENTE,
    TipoCustodia.CLIENTE,
)


class TipoMovimentacao(models.TextChoices):
    """Natureza do lançamento no livro-razão (ISC-RN-02)."""

    ENTRADA = "ENTRADA", "Entrada"
    TRANSFERENCIA = "TRANSFERENCIA", "Transferência"
    ENTREGA = "ENTREGA", "Entrega"
    RETORNO = "RETORNO", "Retorno"
    ENVIO_MANUTENCAO = "ENVIO_MANUTENCAO", "Envio para manutenção"
    RETORNO_MANUTENCAO = "RETORNO_MANUTENCAO", "Retorno de manutenção"
    BAIXA = "BAIXA", "Baixa"
    ESTORNO = "ESTORNO", "Estorno"


class MotivoBaixa(models.TextChoices):
    """Motivos de baixa; todos exigem justificativa textual (ISC-RN-13)."""

    PERDA = "PERDA", "Perda"
    AVARIA = "AVARIA", "Avaria"
    OBSOLESCENCIA = "OBSOLESCENCIA", "Obsolescência"


class SituacaoUnidade(models.TextChoices):
    """Situação da unidade — anotação derivada, NUNCA campo (ISC-ADR-07).

    Existe como vocabulário para filtros e exibição; o valor é calculado por
    `Unidade.objects.com_situacao()` a partir da custódia atual, do tipo do
    modelo e da existência de reserva ativa.
    """

    EM_DEPOSITO = "EM_DEPOSITO", "Em depósito"
    COM_AGENTE = "COM_AGENTE", "Com agente"
    RESERVADA = "RESERVADA", "Reservada"
    EM_ROTA = "EM_ROTA", "Em rota"
    COM_CLIENTE = "COM_CLIENTE", "Com cliente"
    CONSUMIDA = "CONSUMIDA", "Consumida"
    EM_MANUTENCAO = "EM_MANUTENCAO", "Em manutenção"
    BAIXADA = "BAIXADA", "Baixada"


#: Situações terminais: não admitem saída, nunca são origem de lançamento
#: (ISC-RN-05, ISC-RN-13).
SITUACOES_TERMINAIS = (
    SituacaoUnidade.CONSUMIDA,
    SituacaoUnidade.BAIXADA,
)


class StatusSolicitacao(models.TextChoices):
    """Workflow da solicitação — estado armazenado (ISC-ADR-07)."""

    ABERTA = "ABERTA", "Aberta"
    ATRIBUIDA = "ATRIBUIDA", "Atribuída"
    EM_ROTA = "EM_ROTA", "Em rota"
    ENTREGUE = "ENTREGUE", "Entregue"
    CANCELADA = "CANCELADA", "Cancelada"


class StatusAtribuicao(models.TextChoices):
    """Workflow da atribuição, entidade filha da solicitação."""

    RESERVADA = "RESERVADA", "Reservada"
    EM_ROTA = "EM_ROTA", "Em rota"
    ENTREGUE = "ENTREGUE", "Entregue"
    CANCELADA = "CANCELADA", "Cancelada"


class GeoOrigem(models.TextChoices):
    """Procedência das coordenadas (ISC-RF-02, ISC-RF-03).

    MANUAL vence geocodificação automática enquanto o endereço não mudar.
    """

    GEOCODIFICADO = "GEOCODIFICADO", "Geocodificado"
    MANUAL = "MANUAL", "Ajustado manualmente"
    PENDENTE = "PENDENTE", "Pendente"


class TipoDocumento(models.TextChoices):
    """Documento do cliente."""

    CPF = "CPF", "CPF"
    CNPJ = "CNPJ", "CNPJ"


UF_CHOICES = [
    ("AC", "AC"), ("AL", "AL"), ("AP", "AP"), ("AM", "AM"), ("BA", "BA"),
    ("CE", "CE"), ("DF", "DF"), ("ES", "ES"), ("GO", "GO"), ("MA", "MA"),
    ("MT", "MT"), ("MS", "MS"), ("MG", "MG"), ("PA", "PA"), ("PB", "PB"),
    ("PR", "PR"), ("PE", "PE"), ("PI", "PI"), ("RJ", "RJ"), ("RN", "RN"),
    ("RS", "RS"), ("RO", "RO"), ("RR", "RR"), ("SC", "SC"), ("SP", "SP"),
    ("SE", "SE"), ("TO", "TO"),
]
