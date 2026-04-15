from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Nestle", "0005_gridinternacional_porta_aberta"),
    ]

    operations = [
        migrations.AddField(
            model_name="gridinternacional",
            name="anexo",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="nestle/grid_anexos/",
                verbose_name="Anexo",
            ),
        ),
    ]
