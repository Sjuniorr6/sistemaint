"""Settings da suíte do app `requisicao`.

Reaproveita a receita de `iscas/tests/settings_iscas.py`, que existe por dois
bugs pré-existentes do GSInt que impedem o banco de testes de subir:

1. `qualit/models.py` declara um campo `ID` que colide com a PK `id` — no
   SQLite nomes de coluna são case-insensitive, e a criação da tabela falha
   com `duplicate column name: ID`.
2. As migrations de `requisicao` criam `requisicao_auditlog` duas vezes
   (`table already exists`).

Nenhum dos dois pode sair do INSTALLED_APPS: `templates/base.html` inclui
`components/_header.html`, que carrega a templatetag `user_groups` (definida
em `requisicao`) e resolve `{% url %}` para rotas de vários apps.

Uso:
    pytest requisicao -c requisicao/tests/pytest.ini
"""
from app.settings import *  # noqa: F401,F403

#: Migrations quebradas: o Django monta as tabelas a partir dos models.
MIGRATION_MODULES = {"qualit": None, "requisicao": None}

ROOT_URLCONF = "app.urls"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
