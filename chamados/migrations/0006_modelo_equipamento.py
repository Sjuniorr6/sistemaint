# Adiciona `modelo_equipamento` (obrigatório) aos fatos de abertura do Chamado.
#
# Campo não-nulo e sem default no model. Para os chamados JÁ existentes usamos um
# default one-off via `preserve_default=False`: os registros antigos recebem um
# placeholder, mas o campo continua exigindo valor nas novas aberturas.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chamados", "0005_campos_contato"),
    ]

    operations = [
        migrations.AddField(
            model_name="chamado",
            name="modelo_equipamento",
            field=models.CharField(
                default="(não informado)",
                max_length=120,
                verbose_name="Modelo do equipamento",
            ),
            preserve_default=False,
        ),
    ]
