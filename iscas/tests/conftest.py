"""Fixtures dos testes do Iscas Fast.

Sem factory-boy: a lib não está no projeto e o app não justifica adicioná-la.
Fixtures simples de pytest dão conta e deixam explícito o que cada teste monta.
"""
import pytest
from django.contrib.auth import get_user_model


def pytest_configure(config):
    """Desfaz, só em teste, a colisão de coluna do app `qualit`.

    `qualit.Qualit` declara um campo `ID` que, no SQLite, colide com a PK `id`
    (nomes de coluna são case-insensitive) e derruba a criação do banco de
    testes com `duplicate column name: ID` — para QUALQUER app do projeto, não
    só este. É bug pré-existente do GSInt; o banco de produção foi criado antes
    do campo existir, então só aparece ao montar o schema do zero.

    Aqui damos a ele um `db_column` distinto antes do banco ser criado. Não
    altera o código do qualit nem o banco de produção; a correção definitiva
    seria a mesma mudança no model, com migration.
    """
    import django

    django.setup()

    from django.apps import apps

    modelo = apps.get_model("qualit", "Qualit")
    campo = modelo._meta.get_field("ID")
    if campo.db_column is None:
        campo.db_column = "id_qualit_texto"
        campo.column = "id_qualit_texto"

from iscas.enums import TipoCustodia, TipoModelo
from iscas.models.cadastro import Agente, Cliente, Deposito, ModeloEquipamento
from iscas.models.custodia import Custodia
from iscas.services import entrada as entrada_service


@pytest.fixture
def operador(db):
    return get_user_model().objects.create_user(
        username="operador", password="x", email="op@grupogoldensat.com.br"
    )


@pytest.fixture
def deposito(db):
    return Deposito.objects.create(
        nome="Depósito Matriz",
        logradouro="Rua Central",
        numero="100",
        cidade="São Paulo",
        uf="SP",
        latitude="-23.550520",
        longitude="-46.633308",
    )


@pytest.fixture
def modelo_descartavel(db):
    return ModeloEquipamento.objects.create(
        nome="Isca Descartável X1",
        codigo="ISC-D-X1",
        tipo=TipoModelo.DESCARTAVEL,
    )


@pytest.fixture
def modelo_retornavel(db):
    return ModeloEquipamento.objects.create(
        nome="Isca Retornável R2",
        codigo="ISC-R-R2",
        tipo=TipoModelo.RETORNAVEL,
    )


def _criar_agente(nome, cpf, lat, lng):
    agente = Agente(
        nome=nome,
        telefone="11999990000",
        logradouro="Rua dos Agentes",
        numero="1",
        cidade="São Paulo",
        uf="SP",
        latitude=lat,
        longitude=lng,
    )
    agente.cpf = cpf
    agente.save()
    return agente


@pytest.fixture
def agente(db):
    # São Paulo — Sé.
    return _criar_agente("Agente Um", "39053344705", "-23.550520", "-46.633308")


@pytest.fixture
def agente2(db):
    # ~10 km a leste do primeiro.
    return _criar_agente("Agente Dois", "11144477735", "-23.550520", "-46.535000")


@pytest.fixture
def agente_sem_coordenada(db):
    agente = Agente(
        nome="Agente Sem Pin",
        telefone="11988880000",
        logradouro="Rua Sem Geo",
        cidade="São Paulo",
        uf="SP",
    )
    agente.cpf = "12345678909"
    agente.save()
    return agente


@pytest.fixture
def cliente(db):
    return Cliente.objects.create(
        nome_razao_social="Cliente Teste LTDA",
        documento="11222333000181",
        contato_nome="Contato",
        telefone="1133334444",
        logradouro="Av. do Cliente",
        numero="500",
        cidade="São Paulo",
        uf="SP",
        latitude="-23.560000",
        longitude="-46.640000",
    )


@pytest.fixture
def custodia_baixa(db):
    return Custodia.todos.get(tipo=TipoCustodia.BAIXA)


@pytest.fixture
def custodia_manutencao(db):
    return Custodia.todos.get(tipo=TipoCustodia.MANUTENCAO)


@pytest.fixture
def unidades_no_deposito(db, modelo_descartavel, deposito, operador):
    """10 unidades descartáveis no depósito, entradas pelo fluxo real."""
    _, unidades = entrada_service.registrar_entrada(
        modelo=modelo_descartavel,
        identificadores=[f"D{i:03d}" for i in range(1, 11)],
        destino=deposito,
        autor=operador,
        nota_fiscal="NF-1",
    )
    return unidades


@pytest.fixture
def unidades_com_agente(db, modelo_descartavel, agente, operador):
    """8 unidades descartáveis já em custódia do agente."""
    _, unidades = entrada_service.registrar_entrada(
        modelo=modelo_descartavel,
        identificadores=[f"A{i:03d}" for i in range(1, 9)],
        destino=agente,
        autor=operador,
    )
    return unidades


@pytest.fixture
def retornaveis_com_agente(db, modelo_retornavel, agente, operador):
    """5 unidades retornáveis com o agente."""
    _, unidades = entrada_service.registrar_entrada(
        modelo=modelo_retornavel,
        identificadores=[f"R{i:03d}" for i in range(1, 6)],
        destino=agente,
        autor=operador,
    )
    return unidades
