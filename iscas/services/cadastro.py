"""Regras de cadastro: criação, geocodificação no salvamento e desativação.

A desativação de agente com saldo é bloqueada aqui, na service layer, e não por
um flag: a verificação é uma consulta de saldo ao livro (ISC-RN-18).
Desativação não pode evaporar estoque.
"""
from django.db import transaction

from iscas.services.exceptions import (
    AgenteComSaldo,
    DepositoComSaldo,
    TipoModeloImutavel,
)
from iscas.services.geo import ajustar_pin, geocodificar_entidade
from iscas.services.saldo import saldo_em_custodia


@transaction.atomic
def salvar_com_geocodificacao(entidade, *, endereco_mudou=True, pin=None):
    """Salva a entidade, resolvendo a coordenada (ISC-RF-02, ISC-RF-03).

    Args:
        pin: `(latitude, longitude)` quando o operador arrastou o pin no mapa
            do formulário. Vence a geocodificação automática — ele está olhando
            o mapa e o serviço, não (ISC-RF-03).
        endereco_mudou: quando False e sem pin, nada é geocodificado. Evita
            bater no Nominatim ao editar só o telefone.

    A geocodificação é síncrona, com timeout curto, e a falha nunca impede o
    salvamento: o cadastro fica `PENDENTE` e é reprocessado depois pelo command
    `geocodificar_pendentes`.
    """
    entidade.save()

    if pin is not None:
        latitude, longitude = pin
        ajustar_pin(entidade, latitude=latitude, longitude=longitude)
    elif endereco_mudou:
        geocodificar_entidade(entidade)

    return entidade


def desativar_agente(agente):
    """Soft-delete do agente, bloqueado se ele ainda segura equipamento.

    ISC-RN-18: o agente desativado mantém saldo e histórico, mas não recebe
    novas atribuições nem aparece no mapa. Desativar com saldo em custódia
    exige transferir as unidades antes — senão o estoque sumiria da operação
    sem sair do livro.
    """
    saldo = saldo_em_custodia(agente)
    if saldo > 0:
        raise AgenteComSaldo(
            f"{agente} ainda tem {saldo} unidade(s) em custódia. "
            "Transfira o equipamento antes de desativar (ISC-RN-18)."
        )
    agente.desativar()
    return agente


def desativar_deposito(deposito):
    """Soft-delete do depósito, bloqueado se ainda houver estoque nele.

    Mesmo princípio do agente (ISC-RN-18): a verificação é uma consulta de
    saldo ao livro, não um flag. Desativar um depósito com equipamento faria
    o estoque sumir da operação sem sair do livro-razão.
    """
    saldo = saldo_em_custodia(deposito)
    if saldo > 0:
        raise DepositoComSaldo(
            f"{deposito} ainda tem {saldo} unidade(s) em estoque. "
            "Transfira o equipamento antes de desativar."
        )
    deposito.desativar()
    return deposito


def desativar_cliente(cliente):
    """Soft-delete do cliente. Retornável em posse não bloqueia — é passivo
    que continua rastreado justamente para ser cobrado."""
    cliente.desativar()
    return cliente


def alterar_modelo(modelo, *, tipo=None, **campos):
    """Edita o modelo, protegendo a imutabilidade do tipo (ISC-RN-04)."""
    if tipo is not None and tipo != modelo.tipo and modelo.tem_movimentacao():
        raise TipoModeloImutavel(
            f"O tipo de {modelo} não pode mudar: já existem unidades deste "
            "modelo com movimentação registrada (ISC-RN-04)."
        )
    if tipo is not None:
        modelo.tipo = tipo
    for campo, valor in campos.items():
        setattr(modelo, campo, valor)
    modelo.save()
    return modelo
