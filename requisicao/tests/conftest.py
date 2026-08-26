"""Fixtures da suíte do app `requisicao`."""
import pytest


def pytest_configure(config):
    """Desfaz, só em teste, a colisão de coluna do app `qualit`.

    `qualit.Qualit` declara um campo `ID` que, no SQLite, colide com a PK `id`
    (nomes de coluna são case-insensitive) e derruba a criação do banco de
    testes para QUALQUER app do projeto. Bug pré-existente do GSInt; a correção
    definitiva é a mesma mudança no model, com migration.
    """
    import django

    django.setup()

    from django.apps import apps

    modelo = apps.get_model("qualit", "Qualit")
    campo = modelo._meta.get_field("ID")
    if campo.db_column is None:
        campo.db_column = "id_qualit_texto"
        campo.column = "id_qualit_texto"
