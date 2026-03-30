from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("acompanhamentos", "0036_cliente_campos_comboio_tiposervico_campos_extras"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="tiposervico",
            unique_together=set(),
        ),
    ]
