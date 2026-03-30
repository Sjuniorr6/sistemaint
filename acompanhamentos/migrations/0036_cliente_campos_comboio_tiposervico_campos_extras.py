from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("acompanhamentos", "0035_registroacompanhamento_raio_cerca_2_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="max_veiculos_comboio",
            field=models.PositiveIntegerField(
                default=1,
                validators=[MinValueValidator(1)],
                verbose_name="Máximo de veículos em comboio",
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="permite_comboio",
            field=models.BooleanField(default=False, verbose_name="Permite comboio"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="reutilizar_franquia",
            field=models.BooleanField(default=False, verbose_name="Reutilizar franquia"),
        ),
        migrations.AddField(
            model_name="tiposervico",
            name="lat_destino",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="tiposervico",
            name="lat_origem",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="tiposervico",
            name="long_destino",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="tiposervico",
            name="long_origem",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="tiposervico",
            name="nome_variacao",
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name="Nome da variação"),
        ),
    ]
