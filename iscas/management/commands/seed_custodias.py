"""Garante as contas de custódia de todas as entidades (ISC-ADR-03).

As contas nascem por signal junto com Agente/Cliente/Depósito, e os singletons
vêm por migration de dados. Este command é a rede de segurança: dados
importados por fixture, criados com `bulk_create` (que não dispara signal) ou
migrados de outro sistema podem ficar sem conta.

Uso:
    python manage.py seed_custodias
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from iscas.enums import TipoCustodia
from iscas.models.cadastro import Agente, Cliente, Deposito
from iscas.models.custodia import Custodia

SINGLETONS = [
    (TipoCustodia.EXTERNO, "Origem externa: fornecedor, compra, sistema irmão."),
    (TipoCustodia.MANUTENCAO, "Equipamento em manutenção — fora do saldo, ciclo reversível."),
    (TipoCustodia.BAIXA, "Perda, avaria ou obsolescência — custódia terminal."),
]


class Command(BaseCommand):
    help = "Cria as contas de custódia que estiverem faltando."

    @transaction.atomic
    def handle(self, *args, **options):
        criadas = 0

        for tipo, descricao in SINGLETONS:
            _, novo = Custodia.todos.get_or_create(
                tipo=tipo, defaults={"descricao": descricao}
            )
            if novo:
                criadas += 1
                self.stdout.write(f"  conta singleton {tipo} criada.")

        for Modelo, campo, tipo in (
            (Agente, "agente", TipoCustodia.AGENTE),
            (Cliente, "cliente", TipoCustodia.CLIENTE),
            (Deposito, "deposito", TipoCustodia.DEPOSITO),
        ):
            sem_conta = Modelo.todos.filter(custodia__isnull=True)
            for entidade in sem_conta:
                Custodia.todos.create(**{campo: entidade, "tipo": tipo})
                criadas += 1
                self.stdout.write(f"  conta de {campo} {entidade.pk} criada.")

        if criadas:
            self.stdout.write(self.style.SUCCESS(f"{criadas} conta(s) criada(s)."))
        else:
            self.stdout.write(self.style.SUCCESS("Todas as contas já existem."))
