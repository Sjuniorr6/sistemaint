"""Pedido por tipo: `ItemSolicitacao.tipo`, preenchido a partir do modelo.

Não reescreve quantidade nem preço: linhas antigas ficam com o modelo e o
unitário que tinham, e só ganham o tipo. Três passos porque o campo nasce
NOT NULL sobre linhas que já existem.
"""
import django.db.models.deletion
from django.db import migrations, models


def preencher_tipo(apps, schema_editor):
    ItemSolicitacao = apps.get_model("iscas", "ItemSolicitacao")
    ModeloEquipamento = apps.get_model("iscas", "ModeloEquipamento")
    for tipo in ModeloEquipamento.objects.values_list("tipo", flat=True).distinct():
        ItemSolicitacao.objects.filter(
            modelo__tipo=tipo, tipo__isnull=True
        ).update(tipo=tipo)


class Migration(migrations.Migration):

    dependencies = [
        ("iscas", "0014_atribuicao_valor_pedagio"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemsolicitacao",
            name="tipo",
            field=models.CharField(
                choices=[("DESCARTAVEL", "Descartável"), ("RETORNAVEL", "Retornável")],
                max_length=20, null=True, verbose_name="Tipo",
            ),
        ),
        migrations.RunPython(preencher_tipo, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="itemsolicitacao",
            name="tipo",
            field=models.CharField(
                choices=[("DESCARTAVEL", "Descartável"), ("RETORNAVEL", "Retornável")],
                db_index=True, max_length=20, verbose_name="Tipo",
            ),
        ),
        migrations.AlterField(
            model_name="itemsolicitacao",
            name="modelo",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="itens_solicitacao",
                to="iscas.modeloequipamento",
                verbose_name="Modelo (pedidos antigos)",
            ),
        ),
        migrations.AddConstraint(
            model_name="itemsolicitacao",
            constraint=models.UniqueConstraint(
                condition=models.Q(("modelo__isnull", True)),
                fields=("solicitacao", "tipo"),
                name="iscas_item_tipo_unico",
            ),
        ),
    ]
