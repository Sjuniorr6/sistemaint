# Conversão de Chamado.cliente (texto livre) → ForeignKey(acompanhamento.Clientes).
#
# Feita em três fases numa migração só para não perder nem mis-vincular os
# chamados já existentes (RN-03: os fatos de abertura são imutáveis e têm valor
# probatório — o cliente registrado na época não pode virar outro):
#   1) adiciona a FK `cliente_fk` (nullable, temporária);
#   2) data migration: para cada chamado, casa o NOME antigo com um Clientes
#      existente (case-insensitive, trim) e, se não houver, CRIA um Clientes com
#      aquele nome literal — assim nenhum chamado antigo perde seu cliente;
#   3) dropa o CharField `cliente`, renomeia `cliente_fk` → `cliente` e o torna
#      obrigatório (não-nulo, PROTECT).
import django.db.models.deletion
from django.db import migrations, models


def _preencher_fk(apps, schema_editor):
    Chamado = apps.get_model("chamados", "Chamado")
    Clientes = apps.get_model("acompanhamento", "Clientes")

    for chamado in Chamado.objects.all():
        nome = (chamado.cliente or "").strip()
        if not nome:
            # Defensivo: chamado sem cliente não deveria existir (era obrigatório),
            # mas se houver, cai num placeholder explícito em vez de quebrar.
            nome = "(cliente não informado)"

        cliente = (
            Clientes.objects.filter(nome__iexact=nome).order_by("id").first()
        )
        if cliente is None:
            # Preserva o nome literal da abertura como um novo cadastro; endereco/
            # cnpj são não-nulos no model, então recebem string vazia.
            cliente = Clientes.objects.create(nome=nome, endereco="", cnpj="")

        chamado.cliente_fk = cliente
        chamado.save(update_fields=["cliente_fk"])


def _reverter(apps, schema_editor):
    # Volta a FK para o texto do nome do cliente (best-effort na reversão).
    Chamado = apps.get_model("chamados", "Chamado")
    for chamado in Chamado.objects.select_related("cliente_fk").all():
        chamado.cliente = chamado.cliente_fk.nome if chamado.cliente_fk else ""
        chamado.save(update_fields=["cliente"])


class Migration(migrations.Migration):

    dependencies = [
        ("acompanhamento", "0008_alter_clientes_equipamento"),
        ("chamados", "0003_alter_chamado_status_alter_chamadoevento_acao_and_more"),
    ]

    operations = [
        # (1) FK temporária, nullable.
        migrations.AddField(
            model_name="chamado",
            name="cliente_fk",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="chamados",
                to="acompanhamento.clientes",
                verbose_name="Cliente",
            ),
        ),
        # (2) backfill nome antigo → registro de Clientes.
        migrations.RunPython(_preencher_fk, _reverter),
        # (3) troca de coluna: remove o texto, promove a FK ao nome `cliente`.
        migrations.RemoveField(model_name="chamado", name="cliente"),
        migrations.RenameField(
            model_name="chamado", old_name="cliente_fk", new_name="cliente"
        ),
        migrations.AlterField(
            model_name="chamado",
            name="cliente",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="chamados",
                to="acompanhamento.clientes",
                verbose_name="Cliente",
            ),
        ),
    ]
