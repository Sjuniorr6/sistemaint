"""Cria as contas singleton do livro-razão (ISC-ADR-03).

EXTERNO, MANUTENCAO e BAIXA não têm entidade correspondente — existem como
conta e ponto. Sem elas, nenhuma entrada, envio a manutenção ou baixa pode ser
lançada, então nascem com o schema.
"""
from django.db import migrations

SINGLETONS = [
    ("EXTERNO", "Origem externa: fornecedor, compra, sistema irmão."),
    ("MANUTENCAO", "Equipamento em manutenção — fora do saldo, ciclo reversível."),
    ("BAIXA", "Perda, avaria ou obsolescência — custódia terminal."),
]


def criar_singletons(apps, schema_editor):
    Custodia = apps.get_model("iscas", "Custodia")
    for tipo, descricao in SINGLETONS:
        Custodia.objects.get_or_create(
            tipo=tipo, defaults={"descricao": descricao, "is_active": True}
        )


def remover_singletons(apps, schema_editor):
    Custodia = apps.get_model("iscas", "Custodia")
    Custodia.objects.filter(tipo__in=[t for t, _ in SINGLETONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("iscas", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(criar_singletons, remover_singletons),
    ]
