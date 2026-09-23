"""Cria os três grupos de papel do Iscas Fast (ISC-RN-19).

Divergência deliberada do molde do app Chamados: **não** associamos objetos
`Permission` do Django. A autorização do Iscas é por NOME DE GRUPO, consultada
em `iscas/permissions.py` — nenhum código do app chama `user.has_perm`.
Pendurar permissions aqui criaria uma segunda fonte de verdade que ninguém lê e
que divergiria da primeira em silêncio.

Idempotente: `Operadores Iscas` já existe em produção com usuários dentro, e o
`get_or_create` apenas o encontra.
"""
from django.db import migrations

from iscas.enums import (
    GRUPO_COMERCIAL_FAST,
    GRUPO_OPERADORES,
    GRUPO_OPERADORES_FAST,
    GRUPOS_ISCAS,
)

#: O grupo total já existe em produção; o reverse não pode tocá-lo.
GRUPOS_NOVOS = (GRUPO_OPERADORES_FAST, GRUPO_COMERCIAL_FAST)


def criar_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nome in GRUPOS_ISCAS:
        Group.objects.get_or_create(name=nome)


def remover_grupos(apps, schema_editor):
    """Remove SÓ os dois grupos novos.

    A assimetria é proposital: `Operadores Iscas` (GRUPO_OPERADORES) é anterior
    a esta migração e tem usuários em produção. Um rollback que o apagasse
    tiraria o acesso de todo mundo ao app — e a migração reversa é justamente o
    que se roda com pressa, quando algo deu errado.
    """
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=GRUPOS_NOVOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("iscas", "0005_alter_modeloequipamento_codigo"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(criar_grupos, remover_grupos),
    ]
