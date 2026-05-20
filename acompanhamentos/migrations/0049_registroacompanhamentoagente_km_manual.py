from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('acompanhamentos', '0048_remove_plate_validation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='registroacompanhamentoagente',
            name='km_inicio_manual',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='registroacompanhamentoagente',
            name='km_final_manual',
            field=models.BooleanField(default=False),
        ),
    ]
