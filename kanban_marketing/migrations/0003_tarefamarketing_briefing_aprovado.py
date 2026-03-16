from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kanban_marketing', '0002_alter_tarefamarketing_responsavel'),
    ]

    operations = [
        migrations.AddField(
            model_name='tarefamarketing',
            name='briefing_aprovado',
            field=models.BooleanField(default=False, verbose_name='Briefing Aprovado'),
        ),
    ]
