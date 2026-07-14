# Conversão de Chamado.modelo_equipamento (texto) → FK(produto.Produto).
#
# Mesma estratégia em 3 fases da FK de cliente, para não perder nem mis-vincular
# os chamados existentes:
#   1) adiciona a FK `modelo_fk` (nullable, temporária);
#   2) data migration: casa o NOME antigo com um Produto existente (case-insensitive,
#      trim) e, se não houver, CRIA um Produto com aquele nome — os chamados atuais
#      só têm o placeholder "(não informado)", que vira um Produto único;
#   3) dropa o CharField, renomeia `modelo_fk` → `modelo_equipamento` e o torna
#      obrigatório (não-nulo, PROTECT).
import django.db.models.deletion
from django.db import migrations, models


def _preencher_fk(apps, schema_editor):
    Chamado = apps.get_model("chamados", "Chamado")
    Produto = apps.get_model("produto", "Produto")

    for chamado in Chamado.objects.all():
        nome = (chamado.modelo_equipamento or "").strip() or "(não informado)"
        produto = Produto.objects.filter(nome__iexact=nome).order_by("id").first()
        if produto is None:
            produto = Produto.objects.create(nome=nome)
        chamado.modelo_fk = produto
        chamado.save(update_fields=["modelo_fk"])


def _reverter(apps, schema_editor):
    Chamado = apps.get_model("chamados", "Chamado")
    for chamado in Chamado.objects.select_related("modelo_fk").all():
        chamado.modelo_equipamento = chamado.modelo_fk.nome if chamado.modelo_fk else ""
        chamado.save(update_fields=["modelo_equipamento"])


class Migration(migrations.Migration):

    dependencies = [
        ("produto", "0001_initial"),
        ("chamados", "0006_modelo_equipamento"),
    ]

    operations = [
        migrations.AddField(
            model_name="chamado",
            name="modelo_fk",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="chamados",
                to="produto.produto",
                verbose_name="Modelo do equipamento",
            ),
        ),
        migrations.RunPython(_preencher_fk, _reverter),
        migrations.RemoveField(model_name="chamado", name="modelo_equipamento"),
        migrations.RenameField(
            model_name="chamado",
            old_name="modelo_fk",
            new_name="modelo_equipamento",
        ),
        migrations.AlterField(
            model_name="chamado",
            name="modelo_equipamento",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="chamados",
                to="produto.produto",
                verbose_name="Modelo do equipamento",
            ),
        ),
    ]
