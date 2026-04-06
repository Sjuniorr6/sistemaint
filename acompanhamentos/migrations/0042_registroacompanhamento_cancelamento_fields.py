from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('acompanhamentos', '0041_requisicaosolicitacao_status_requisicao'),
    ]

    operations = [
        migrations.AddField(
            model_name='registroacompanhamento',
            name='aceitou_termos_cancelamento',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='registroacompanhamento',
            name='cancelado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='registroacompanhamento',
            name='justificativa_cancelamento',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='registroacompanhamento',
            name='motivos_cancelamento',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='registroacompanhamento',
            name='status_requisicao',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='registroacompanhamento',
            name='taxa_cancelamento_percentual',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='registroacompanhamento',
            name='usuario_aceitou_termos_cancelamento',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
    ]
