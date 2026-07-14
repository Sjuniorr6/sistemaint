# Adiciona os campos de "Contato feito por" (quem acionou o Quality e por qual
# canal) aos fatos de abertura do Chamado.
#
# contato_nome e contato_meio são não-nulos e sem default no model (obrigatórios
# na abertura). Para os chamados JÁ existentes usamos um default one-off via
# `preserve_default=False`: os registros antigos recebem um placeholder, mas o
# campo continua exigindo valor nas novas aberturas. telefone/email são blank.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chamados", "0004_cliente_para_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="chamado",
            name="contato_nome",
            field=models.CharField(
                default="(não informado)",
                max_length=120,
                verbose_name="Contato — nome",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="chamado",
            name="contato_telefone",
            field=models.CharField(
                blank=True, max_length=30, verbose_name="Contato — telefone"
            ),
        ),
        migrations.AddField(
            model_name="chamado",
            name="contato_email",
            field=models.EmailField(
                blank=True, max_length=254, verbose_name="Contato — email"
            ),
        ),
        migrations.AddField(
            model_name="chamado",
            name="contato_meio",
            field=models.CharField(
                choices=[
                    ("TELEFONE", "Telefone"),
                    ("EMAIL", "Email"),
                    ("WHATSAPP", "WhatsApp"),
                ],
                default="TELEFONE",
                max_length=20,
                verbose_name="Meio de comunicação",
            ),
            preserve_default=False,
        ),
    ]
