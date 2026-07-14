"""Cria os grupos `quality` e `inteligencia` e atribui as permissões do app.

A separação de papéis é por Django Groups (ADR-008). Ambos os grupos precisam
de `view_chamado` (todos visualizam, RN-18); `quality` ganha add/change (abre e
trata) e `inteligencia` ganha change (trata os encaminhados). A regra fina de
quem-faz-o-quê é imposta no service; estas permissões só habilitam o acesso e o
menu. Idempotente e reversível.
"""
from django.db import migrations


GRUPOS = {
    "quality": ["view_chamado", "add_chamado", "change_chamado"],
    "inteligencia": ["view_chamado", "change_chamado"],
}


def criar_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    Chamado = apps.get_model("chamados", "Chamado")

    ct = ContentType.objects.get_for_model(Chamado)
    for nome_grupo, codenames in GRUPOS.items():
        grupo, _ = Group.objects.get_or_create(name=nome_grupo)
        perms = Permission.objects.filter(content_type=ct, codename__in=codenames)
        grupo.permissions.add(*perms)


def remover_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=GRUPOS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chamados", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(criar_grupos, remover_grupos),
    ]
