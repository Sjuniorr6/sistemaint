from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('acompanhamentos', '0040_requisicaosolicitacao_aceitou_termos_cancelamento_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='requisicaosolicitacao',
            name='status_requisicao',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
