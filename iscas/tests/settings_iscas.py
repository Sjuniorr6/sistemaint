"""Settings de teste do app Iscas Fast.

Existe por dois bugs pré-existentes do GSInt, alheios a este app, que impedem
o banco de testes de subir:

1. `qualit/models.py` declara um campo `ID` que colide com a PK `id` — no
   SQLite nomes de coluna são case-insensitive, e a criação da tabela falha com
   `duplicate column name: ID`. O `db.sqlite3` de produção foi criado antes
   desse campo existir, então o problema só aparece ao montar o schema do zero.
2. As migrations de `requisicao` criam `requisicao_auditlog` duas vezes
   (`table already exists`).

Nenhum dos dois pode simplesmente sair do INSTALLED_APPS: `templates/base.html`
inclui `components/_header.html`, que carrega a templatetag `user_groups`
(definida em `requisicao`) e resolve `{% url %}` para rotas de vários apps —
tirar qualquer um quebraria toda página do Iscas Fast com NoReverseMatch.

A saída é `MIGRATION_MODULES = None` para ambos, o que faz o Django criar as
tabelas direto do schema dos models, e um `db_column` explícito no campo `ID`
do qualit apenas em teste, desfazendo a colisão. Nada disso altera o
comportamento do Iscas Fast, que não depende de nenhum app do GSInt além da
autenticação (ISC-ADR-01).

Uso:
    pytest iscas -c iscas/tests/pytest.ini
"""
import tempfile
from pathlib import Path

from app.settings import *  # noqa: F401,F403
from app.settings import DATABASES

#: Migrations quebradas: o Django monta as tabelas a partir dos models.
MIGRATION_MODULES = {"qualit": None, "requisicao": None}

ROOT_URLCONF = "app.urls"

# Banco de testes em ARQUIVO, não no `:memory:` que o Django usa por padrão
# com SQLite. O teste de concorrência da reserva abre conexões em threads
# separadas; em memória, cada conexão veria um banco diferente e o teste
# passaria sem exercitar nada. Em arquivo, o comportamento é o de produção,
# incluindo o lock de escrita que o `timeout` abaixo aguarda.
DATABASES = {
    **DATABASES,
    "default": {
        **DATABASES["default"],
        "OPTIONS": {"timeout": 30},
        "TEST": {
            "NAME": str(Path(tempfile.gettempdir()) / "iscas_test.sqlite3"),
        },
    },
}

# Chaves determinísticas: os testes de CPF precisam de cifra estável, e não
# queremos depender do .env da máquina de quem roda.
ISCAS_CPF_KEY = "HmijgLNfLb8WGEqzRtYYsRq5H6ErOVGTFAt7lEQTx0Q="
ISCAS_CPF_PEPPER = "pepper-de-teste-iscas-fast"

# Nenhum teste deve chamar o Nominatim de verdade.
ISCAS_NOMINATIM_URL = "http://localhost:1/geocode-desligado-em-teste"
ISCAS_GEOCODE_TIMEOUT = 0.01

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
