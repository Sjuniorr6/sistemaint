# Fluxo Expedição: novo estado EXPEDICAO + ação ENCAMINHAR_EXPEDICAO (choices) e
# criação do grupo `expedicao` (fila compartilhada). Os usuários são adicionados
# ao grupo depois, pelo admin.
from django.db import migrations, models


def _criar_grupo_expedicao(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="expedicao")


def _remover_grupo_expedicao(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="expedicao").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('chamados', '0008_numero_equipamento_maior'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(_criar_grupo_expedicao, _remover_grupo_expedicao),
        migrations.AlterField(
            model_name='chamado',
            name='status',
            field=models.CharField(choices=[('ABERTO', 'Aberto'), ('ENCAMINHADO', 'Encaminhado'), ('EXPEDICAO', 'Expedição'), ('BLOQUEADO', 'Bloqueado'), ('RESOLVIDO', 'Resolvido')], db_index=True, default='ABERTO', max_length=20, verbose_name='Status'),
        ),
        migrations.AlterField(
            model_name='chamadoevento',
            name='acao',
            field=models.CharField(choices=[('ABRIR', 'Abrir'), ('ENCAMINHAR', 'Encaminhar'), ('ENCAMINHAR_EXPEDICAO', 'Encaminhar para expedição'), ('FINALIZAR', 'Finalizar'), ('RESOLVER', 'Resolver'), ('BLOQUEAR', 'Bloquear'), ('REABRIR', 'Reabrir')], max_length=20, verbose_name='Ação'),
        ),
        migrations.AlterField(
            model_name='chamadoevento',
            name='estado_destino',
            field=models.CharField(choices=[('ABERTO', 'Aberto'), ('ENCAMINHADO', 'Encaminhado'), ('EXPEDICAO', 'Expedição'), ('BLOQUEADO', 'Bloqueado'), ('RESOLVIDO', 'Resolvido')], max_length=20, verbose_name='Estado de destino'),
        ),
        migrations.AlterField(
            model_name='chamadoevento',
            name='estado_origem',
            field=models.CharField(blank=True, choices=[('ABERTO', 'Aberto'), ('ENCAMINHADO', 'Encaminhado'), ('EXPEDICAO', 'Expedição'), ('BLOQUEADO', 'Bloqueado'), ('RESOLVIDO', 'Resolvido')], max_length=20, null=True, verbose_name='Estado de origem'),
        ),
    ]
