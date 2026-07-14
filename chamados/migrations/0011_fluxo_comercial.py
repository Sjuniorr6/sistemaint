# Fluxo Comercial: novo estado COMERCIAL + ação ENCAMINHAR_COMERCIAL (choices).
# O grupo COMERCIAL já existe no sistema (não é criado aqui); um get_or_create
# defensivo garante que ele exista mesmo num banco montado do zero.
from django.db import migrations, models


def _garantir_grupo_comercial(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="COMERCIAL")


def _noop(apps, schema_editor):
    # Não removemos o grupo COMERCIAL: ele é pré-existente e usado por outros apps.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('chamados', '0010_fluxo_laboratorio'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(_garantir_grupo_comercial, _noop),
        migrations.AlterField(
            model_name='chamado',
            name='status',
            field=models.CharField(choices=[('ABERTO', 'Aberto'), ('ENCAMINHADO', 'Encaminhado'), ('EXPEDICAO', 'Expedição'), ('LABORATORIO', 'Laboratório'), ('COMERCIAL', 'Comercial'), ('BLOQUEADO', 'Bloqueado'), ('RESOLVIDO', 'Resolvido')], db_index=True, default='ABERTO', max_length=20, verbose_name='Status'),
        ),
        migrations.AlterField(
            model_name='chamadoevento',
            name='acao',
            field=models.CharField(choices=[('ABRIR', 'Abrir'), ('ENCAMINHAR', 'Encaminhar'), ('ENCAMINHAR_EXPEDICAO', 'Encaminhar para expedição'), ('MARCAR_CHEGADA', 'Marcar chegada'), ('ENCAMINHAR_COMERCIAL', 'Encaminhar para comercial'), ('FINALIZAR', 'Finalizar'), ('RESOLVER', 'Resolver'), ('BLOQUEAR', 'Bloquear'), ('REABRIR', 'Reabrir')], max_length=20, verbose_name='Ação'),
        ),
        migrations.AlterField(
            model_name='chamadoevento',
            name='estado_destino',
            field=models.CharField(choices=[('ABERTO', 'Aberto'), ('ENCAMINHADO', 'Encaminhado'), ('EXPEDICAO', 'Expedição'), ('LABORATORIO', 'Laboratório'), ('COMERCIAL', 'Comercial'), ('BLOQUEADO', 'Bloqueado'), ('RESOLVIDO', 'Resolvido')], max_length=20, verbose_name='Estado de destino'),
        ),
        migrations.AlterField(
            model_name='chamadoevento',
            name='estado_origem',
            field=models.CharField(blank=True, choices=[('ABERTO', 'Aberto'), ('ENCAMINHADO', 'Encaminhado'), ('EXPEDICAO', 'Expedição'), ('LABORATORIO', 'Laboratório'), ('COMERCIAL', 'Comercial'), ('BLOQUEADO', 'Bloqueado'), ('RESOLVIDO', 'Resolvido')], max_length=20, null=True, verbose_name='Estado de origem'),
        ),
    ]
