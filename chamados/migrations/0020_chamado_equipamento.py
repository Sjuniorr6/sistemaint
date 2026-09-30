# Um modelo POR equipamento: cria ChamadoEquipamento (nº + modelo) e copia os
# chamados existentes para ela. Até aqui o chamado tinha um único
# `modelo_equipamento` para todos os números de `numero_equipamento`
# ("EQ-1, EQ-2"), então cada número vira uma linha com esse modelo.
# A remoção de `Chamado.modelo_equipamento` fica na 0021, depois do backfill.
import django.db.models.deletion
from django.db import migrations, models


def _backfill(apps, schema_editor):
    Chamado = apps.get_model("chamados", "Chamado")
    ChamadoEquipamento = apps.get_model("chamados", "ChamadoEquipamento")

    ja_migrados = set(
        ChamadoEquipamento.objects.values_list("chamado_id", flat=True).distinct()
    )
    linhas = []
    for chamado_id, bruto, modelo_id in Chamado.objects.values_list(
        "id", "numero_equipamento", "modelo_equipamento_id"
    ).iterator():
        if chamado_id in ja_migrados:
            continue  # idempotente
        vistos = set()
        for numero in (parte.strip() for parte in (bruto or "").split(",")):
            # Número repetido no mesmo chamado violaria a UniqueConstraint.
            if numero and numero not in vistos:
                vistos.add(numero)
                linhas.append(
                    ChamadoEquipamento(
                        chamado_id=chamado_id, numero=numero, modelo_id=modelo_id
                    )
                )
    ChamadoEquipamento.objects.bulk_create(linhas, batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("chamados", "0019_fluxo_financeiro"),
        ("produto", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChamadoEquipamento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero", models.CharField(max_length=60, verbose_name="Nº do equipamento")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                (
                    "chamado",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="equipamentos",
                        to="chamados.chamado",
                        verbose_name="Chamado",
                    ),
                ),
                (
                    "modelo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="equipamentos_chamado",
                        to="produto.produto",
                        verbose_name="Modelo do equipamento",
                    ),
                ),
            ],
            options={
                "verbose_name": "Equipamento do chamado",
                "verbose_name_plural": "Equipamentos do chamado",
                "ordering": ["id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("chamado", "numero"),
                        name="chamado_equipamento_numero_unico",
                    )
                ],
            },
        ),
        migrations.RunPython(_backfill, migrations.RunPython.noop),
    ]
