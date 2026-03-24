from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("acompanhamentos", "0034_registroacompanhamento_destino_2_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="registroacompanhamento",
            name="origem_2",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="registroacompanhamento",
            name="origem_3",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="registroacompanhamento",
            name="raio_cerca_2",
            field=models.PositiveIntegerField(
                blank=True,
                default=60,
                null=True,
                verbose_name="Raio da Cerca 2 (metros)",
            ),
        ),
        migrations.AddField(
            model_name="registroacompanhamento",
            name="raio_cerca_3",
            field=models.PositiveIntegerField(
                blank=True,
                default=60,
                null=True,
                verbose_name="Raio da Cerca 3 (metros)",
            ),
        ),
    ]
