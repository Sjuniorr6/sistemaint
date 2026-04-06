from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('acompanhamentos', '0042_registroacompanhamento_cancelamento_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='requisicaosolicitacao',
            name='valor_cancelamento',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='registroacompanhamento',
            name='valor_cancelamento',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
