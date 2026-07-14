# Fluxo Laboratório: novo estado LABORATORIO + ação MARCAR_CHEGADA (choices) e
# criação do grupo `laboratorio` (fila compartilhada que recebe os equipamentos
# que chegaram à base). Usuários adicionados depois, pelo admin.
from django.db import migrations, models


def _criar_grupo_laboratorio(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="laboratorio")


def _remover_grupo_laboratorio(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="laboratorio").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('chamados', '0009_fluxo_expedicao'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(_criar_grupo_laboratorio, _remover_grupo_laboratorio),
        migrations.AlterField(
            model_name='chamado',
            name='status',
            field=models.CharField(choices=[('ABERTO', 'Aberto'), ('ENCAMINHADO', 'Encaminhado'), ('EXPEDICAO', 'Expedição'), ('LABORATORIO', 'Laboratório'), ('BLOQUEADO', 'Bloqueado'), ('RESOLVIDO', 'Resolvido')], db_index=True, default='ABERTO', max_length=20, verbose_name='Status'),
        ),
        migrations.AlterField(
            model_name='chamadoevento',
            name='acao',
            field=models.CharField(choices=[('ABRIR', 'Abrir'), ('ENCAMINHAR', 'Encaminhar'), ('ENCAMINHAR_EXPEDICAO', 'Encaminhar para expedição'), ('MARCAR_CHEGADA', 'Marcar chegada'), ('FINALIZAR', 'Finalizar'), ('RESOLVER', 'Resolver'), ('BLOQUEAR', 'Bloquear'), ('REABRIR', 'Reabrir')], max_length=20, verbose_name='Ação'),
        ),
        migrations.AlterField(
            model_name='chamadoevento',
            name='estado_destino',
            field=models.CharField(choices=[('ABERTO', 'Aberto'), ('ENCAMINHADO', 'Encaminhado'), ('EXPEDICAO', 'Expedição'), ('LABORATORIO', 'Laboratório'), ('BLOQUEADO', 'Bloqueado'), ('RESOLVIDO', 'Resolvido')], max_length=20, verbose_name='Estado de destino'),
        ),
        migrations.AlterField(
            model_name='chamadoevento',
            name='estado_origem',
            field=models.CharField(blank=True, choices=[('ABERTO', 'Aberto'), ('ENCAMINHADO', 'Encaminhado'), ('EXPEDICAO', 'Expedição'), ('LABORATORIO', 'Laboratório'), ('BLOQUEADO', 'Bloqueado'), ('RESOLVIDO', 'Resolvido')], max_length=20, null=True, verbose_name='Estado de origem'),
        ),
    ]
