from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Nestle", "0006_gridinternacional_anexo"),
    ]

    operations = [
        migrations.AddField(
            model_name="gridinternacional",
            name="anexo_danificado",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="nestle/grid_anexos_danificado/",
                verbose_name="Anexo Danificado",
            ),
        ),
    ]
