"""Criação automática da conta de custódia junto com a entidade (ISC-ADR-03).

Toda entidade que pode segurar equipamento precisa de uma conta no livro-razão.
Criar as duas coisas juntas é o que garante que não exista agente sem conta —
consequência assumida no ADR ao escolher `Custodia` como entidade em vez de FKs
polimórficas.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from iscas.enums import TipoCustodia
from iscas.models.cadastro import Agente, Cliente, Deposito
from iscas.models.custodia import Custodia


def _garantir_custodia(*, tipo, **vinculo):
    """Cria a conta se ainda não existir. Idempotente."""
    Custodia.todos.get_or_create(defaults={"tipo": tipo}, **vinculo)


@receiver(post_save, sender=Agente, dispatch_uid="iscas_custodia_agente")
def criar_custodia_agente(sender, instance, created, **kwargs):
    if created:
        _garantir_custodia(tipo=TipoCustodia.AGENTE, agente=instance)


@receiver(post_save, sender=Cliente, dispatch_uid="iscas_custodia_cliente")
def criar_custodia_cliente(sender, instance, created, **kwargs):
    if created:
        _garantir_custodia(tipo=TipoCustodia.CLIENTE, cliente=instance)


@receiver(post_save, sender=Deposito, dispatch_uid="iscas_custodia_deposito")
def criar_custodia_deposito(sender, instance, created, **kwargs):
    if created:
        _garantir_custodia(tipo=TipoCustodia.DEPOSITO, deposito=instance)
