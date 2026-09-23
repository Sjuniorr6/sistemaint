"""Choices tipados do app Iscas Fast (PRD, seções de ciclo de vida).

Centraliza os vocabulários de custódia, movimentação, situação da unidade e
estados de Solicitação/Atribuição. Models, services, forms e templates
consultam daqui — nenhuma string solta espalhada pelo código.
"""
from django.db import models

# Grupos Django que autorizam operar o app (ISC-RN-19, ARCHITECTURE "Permissões").
#
# ATENÇÃO: "Operadores Iscas" é PREFIXO de "Operadores Iscas Fast". Todo lookup
# de grupo é por igualdade exata (`filter(name=...)`) — `startswith` ou
# `icontains` daria ao operador restrito o acesso total, em silêncio.
GRUPO_OPERADORES = "Operadores Iscas"
GRUPO_OPERADORES_FAST = "Operadores Iscas Fast"
GRUPO_COMERCIAL_FAST = "Comercial Iscas Fast"

#: Os três papéis, para a migração de dados e os testes iterarem sem repetir.
GRUPOS_ISCAS = (GRUPO_OPERADORES, GRUPO_OPERADORES_FAST, GRUPO_COMERCIAL_FAST)


class Capacidade(models.TextChoices):
    """O que se pode FAZER no app — a unidade de autorização.

    As views declaram capacidade, não papel: o requisito não é hierárquico (o
    Operador Fast dá baixa e manutenção, mas não dá entrada nem transfere), e
    decorator por papel exigiria uma combinação nova a cada view. O mapa
    papel → capacidades vive num dicionário só, em `iscas/permissions.py`.

    O rótulo é exibido na tela de auditoria, então é frase de operador.
    """

    VER_PAINEL = "VER_PAINEL", "Ver painel"
    VER_MAPA = "VER_MAPA", "Ver mapa"
    VER_SOLICITACAO = "VER_SOLICITACAO", "Ver solicitações"
    CRIAR_SOLICITACAO = "CRIAR_SOLICITACAO", "Criar solicitação"
    ATENDER_SOLICITACAO = "ATENDER_SOLICITACAO", "Atender solicitação"
    EXCLUIR_SOLICITACAO = "EXCLUIR_SOLICITACAO", "Excluir solicitação"
    VER_ESTOQUE = "VER_ESTOQUE", "Ver estoque"
    # Separada de BAIXAR_MANUTENCAO porque é exatamente aí que passa a linha do
    # Operador Fast: ele dá baixa e manda para manutenção, mas não dá entrada,
    # não transfere e não estorna.
    MOVIMENTAR_ESTOQUE = "MOVIMENTAR_ESTOQUE", "Movimentar estoque"
    BAIXAR_MANUTENCAO = "BAIXAR_MANUTENCAO", "Dar baixa e manutenção"
    CADASTRAR_CLIENTE = "CADASTRAR_CLIENTE", "Cadastrar cliente"
    CADASTRAR_MODELO = "CADASTRAR_MODELO", "Cadastrar modelo"
    CADASTRAR_AGENTE = "CADASTRAR_AGENTE", "Cadastrar agente"
    CADASTRAR_DEPOSITO = "CADASTRAR_DEPOSITO", "Cadastrar depósito"
    DESATIVAR_CADASTRO = "DESATIVAR_CADASTRO", "Desativar cadastro"
    VER_AUDITORIA = "VER_AUDITORIA", "Ver auditoria"
    # Dinheiro. Separadas porque o Comercial vê o que o cliente paga e o
    # Operador Fast não — ele digita na abertura, mas não consulta depois.
    # A margem não tem capacidade própria: quem tem as duas calcula de cabeça.
    VER_VALOR_CLIENTE = "VER_VALOR_CLIENTE", "Ver valor cobrado do cliente"
    VER_CUSTO_AGENTE = "VER_CUSTO_AGENTE", "Ver custo do agente"
    # CEP e geocodificação: sem isto, as duas telas do Comercial (cadastrar
    # cliente e abrir solicitação) quebram no meio do preenchimento.
    CONSULTAR_APOIO = "CONSULTAR_APOIO", "Consultar CEP e endereço"


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


class OrigemAtribuicao(models.TextChoices):
    """De onde saem as iscas de uma atribuição (ISC-RF-25).

    Uma solicitação pode misturar as duas: parte entregue por agente, parte
    retirada pelo próprio cliente na base. A retirada continua sendo uma
    `Atribuicao` — é o que faz a cobertura contá-la e a solicitação fechar.
    """

    AGENTE = "AGENTE", "Entrega por agente"
    RETIRADA_BASE = "RETIRADA_BASE", "Retirada na base"


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
