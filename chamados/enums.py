"""Choices tipados do app Chamados (PRD, seção "Ciclo de Vida do Chamado").

Centraliza os vocabulários de categoria, estado e ação num lugar só — models,
services, forms e templates consultam daqui, nunca repetem strings soltas.
"""
from django.db import models


class Categoria(models.TextChoices):
    """Categorias fixas do chamado (RF-04)."""

    HARDWARE = "HARDWARE", "Hardware"
    CONECTIVIDADE = "CONECTIVIDADE", "Conectividade"
    CHIP_SIM = "CHIP_SIM", "Chip / SIM"
    SOFTWARE = "SOFTWARE", "Software"
    INSTALACAO = "INSTALACAO", "Instalação"
    OUTROS = "OUTROS", "Outros"


class MeioContato(models.TextChoices):
    """Meio pelo qual a pessoa fez contato com o Quality (dado de abertura)."""

    TELEFONE = "TELEFONE", "Telefone"
    EMAIL = "EMAIL", "Email"
    WHATSAPP = "WHATSAPP", "WhatsApp"


class CustoEquipamento(models.TextChoices):
    """Custo do equipamento, definido pelo Comercial ao finalizar o chamado."""

    COM_CUSTO = "COM_CUSTO", "Com custo"
    SEM_CUSTO = "SEM_CUSTO", "Sem custo"


class DestinoEquipamento(models.TextChoices):
    """O que o Comercial decide para o equipamento ao realizar a tratativa."""

    SUBSTITUICAO = "SUBSTITUICAO", "Substituição"
    DEVOLUCAO = "DEVOLUCAO", "Devolução"


class Status(models.TextChoices):
    """Estados do chamado. ABERTO é o default na criação (RN-08)."""

    ABERTO = "ABERTO", "Aberto"
    ENCAMINHADO = "ENCAMINHADO", "Encaminhado"
    EXPEDICAO = "EXPEDICAO", "Expedição"
    LABORATORIO = "LABORATORIO", "Laboratório"
    COMERCIAL = "COMERCIAL", "Comercial"
    FINANCEIRO = "FINANCEIRO", "Financeiro"
    # Depois do Comercial: Recepção (substituição → requisição), Configuração e a
    # volta para a Expedição para o ENVIO ao cliente.
    RECEPCAO = "RECEPCAO", "Recepção"
    CONFIGURACAO = "CONFIGURACAO", "Configuração"
    ENVIO = "ENVIO", "Envio (Expedição)"
    BLOQUEADO = "BLOQUEADO", "Bloqueado"
    RESOLVIDO = "RESOLVIDO", "Resolvido"


class Setor(models.TextChoices):
    """Setor que detém o chamado — usado nas passagens que medem o SLA.

    Mapeia 1:1 com os status de trabalho (ver `setor_do_status` em services.py):
    ABERTO→QUALITY, ENCAMINHADO→INTELIGENCIA, e os demais homônimos.
    """

    QUALITY = "QUALITY", "Quality"
    INTELIGENCIA = "INTELIGENCIA", "Inteligência"
    EXPEDICAO = "EXPEDICAO", "Expedição"
    LABORATORIO = "LABORATORIO", "Laboratório"
    COMERCIAL = "COMERCIAL", "Comercial"
    FINANCEIRO = "FINANCEIRO", "Financeiro"
    RECEPCAO = "RECEPCAO", "Recepção"
    CONFIGURACAO = "CONFIGURACAO", "Configuração"


class Acao(models.TextChoices):
    """Ações que provocam transição de estado (cada uma vira um ChamadoEvento)."""

    ABRIR = "ABRIR", "Abrir"
    # Aceite do setor: NÃO muda o status, só carimba o início da tratativa (SLA).
    ACEITAR_TRATATIVA = "ACEITAR_TRATATIVA", "Aceitar tratativa"
    ENCAMINHAR = "ENCAMINHAR", "Encaminhar"
    # Encaminhamento da Inteligência para a Expedição (equipamento em manutenção).
    ENCAMINHAR_EXPEDICAO = "ENCAMINHAR_EXPEDICAO", "Encaminhar para expedição"
    # Expedição confirma que os equipamentos chegaram na base → vai ao Laboratório.
    MARCAR_CHEGADA = "MARCAR_CHEGADA", "Marcar chegada"
    # Registro de tentativa de contato com o cliente (não muda o status).
    REGISTRAR_CONTATO = "REGISTRAR_CONTATO", "Registrar contato"
    # Laboratório dá a tratativa no equipamento e encaminha para o Comercial.
    ENCAMINHAR_COMERCIAL = "ENCAMINHAR_COMERCIAL", "Encaminhar para comercial"
    # Comercial finaliza: tratativa + custo (com/sem) por equipamento. Destino
    # condicional — RESOLVIDO (sem custo) ou FINANCEIRO (havendo custo).
    FINALIZAR_COMERCIAL = "FINALIZAR_COMERCIAL", "Finalizar chamado"
    # Financeiro registra valor + NF e encerra o chamado.
    FATURAR = "FATURAR", "Faturado"
    # Recepção (com a requisição de substituição criada) → Configuração.
    ENCAMINHAR_CONFIGURACAO = "ENCAMINHAR_CONFIGURACAO", "Encaminhar para configuração"
    # Configuração → Expedição (envio ao cliente), com observação obrigatória.
    ENCAMINHAR_ENVIO = "ENCAMINHAR_ENVIO", "Encaminhar para expedição"
    # Expedição informa método, data e rastreio do envio → Financeiro.
    REGISTRAR_ENVIO = "REGISTRAR_ENVIO", "Registrar envio"
    # Financeiro encerra chamado SEM custo (só confirma; com custo é FATURAR).
    CONFIRMAR_ENCERRAMENTO = "CONFIRMAR_ENCERRAMENTO", "Confirmar encerramento"
    FINALIZAR = "FINALIZAR", "Finalizar"
    RESOLVER = "RESOLVER", "Resolver"
    BLOQUEAR = "BLOQUEAR", "Bloquear"
    REABRIR = "REABRIR", "Reabrir"


# Nomes dos Django Groups que separam os papéis (ADR-008, RN-01/RN-16..18).
GRUPO_QUALITY = "quality"
GRUPO_INTELIGENCIA = "inteligencia"
GRUPO_EXPEDICAO = "expedicao"
GRUPO_LABORATORIO = "laboratorio"
# Reaproveita o grupo COMERCIAL já existente no sistema (maiúsculo, diferente do
# padrão minúsculo dos demais papéis do app).
GRUPO_COMERCIAL = "COMERCIAL"
GRUPO_FINANCEIRO = "financeiro"
GRUPO_RECEPCAO = "recepcao"
# Reaproveita o grupo CONFIGURACAO já existente (time de configuração das
# requisições), como o COMERCIAL.
GRUPO_CONFIGURACAO = "CONFIGURACAO"
