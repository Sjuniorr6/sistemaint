"""Autorização por capacidade: a matriz papel × capacidade (ISC-RN-19).

A tabela `MATRIZ` abaixo é a especificação do requisito traduzida em código, e é
escrita à mão de propósito: derivá-la de `CAPACIDADES_POR_GRUPO` faria o teste
concordar com qualquer bug que o dicionário de produção tivesse.
"""
import pytest
from django.contrib.auth.models import Group

from iscas.enums import (
    GRUPO_COMERCIAL_FAST,
    GRUPO_OPERADORES,
    GRUPO_OPERADORES_FAST,
    GRUPOS_ISCAS,
    Capacidade,
)

pytestmark = pytest.mark.django_db


#: Papel → capacidades que ele DEVE ter. O complemento é negado.
#: Esta tabela é o requisito do usuário, literal.
MATRIZ = {
    GRUPO_OPERADORES: set(Capacidade),
    GRUPO_OPERADORES_FAST: {
        Capacidade.VER_PAINEL,
        Capacidade.VER_MAPA,
        Capacidade.VER_SOLICITACAO,
        Capacidade.CRIAR_SOLICITACAO,
        Capacidade.ATENDER_SOLICITACAO,
        Capacidade.VER_ESTOQUE,
        Capacidade.BAIXAR_MANUTENCAO,
        Capacidade.CADASTRAR_CLIENTE,
        Capacidade.CADASTRAR_MODELO,
        Capacidade.CONSULTAR_APOIO,
        # Vê o custo do agente; NÃO vê o valor do cliente nem a margem.
        Capacidade.VER_CUSTO_AGENTE,
    },
    GRUPO_COMERCIAL_FAST: {
        Capacidade.VER_PAINEL,
        Capacidade.VER_MAPA,
        Capacidade.VER_SOLICITACAO,
        Capacidade.CRIAR_SOLICITACAO,
        Capacidade.CADASTRAR_CLIENTE,
        Capacidade.CONSULTAR_APOIO,
        # O comercial é quem negocia: vê valor, custo e margem.
        Capacidade.VER_VALOR_CLIENTE,
        Capacidade.VER_CUSTO_AGENTE,
    },
}

#: (papel, capacidade, esperado) para cada célula da matriz.
CELULAS = [
    (papel, capacidade, capacidade in permitidas)
    for papel, permitidas in MATRIZ.items()
    for capacidade in Capacidade
]


@pytest.fixture
def usuario_de_papel(django_user_model):
    """Fabrica um usuário pertencente a exatamente um grupo."""

    def _criar(nome_do_grupo):
        usuario = django_user_model.objects.create_user(
            username=f"u-{nome_do_grupo}", password="x"
        )
        grupo, _ = Group.objects.get_or_create(name=nome_do_grupo)
        usuario.groups.add(grupo)
        return usuario

    return _criar


class TestMatrizDeCapacidades:
    # sabotagem: remover CADASTRAR_MODELO do Operador Fast → vermelho
    @pytest.mark.parametrize("papel,capacidade,esperado", CELULAS)
    def test_cada_celula_da_matriz(
        self, usuario_de_papel, papel, capacidade, esperado
    ):
        from iscas.permissions import pode

        assert pode(usuario_de_papel(papel), capacidade) is esperado

    @pytest.mark.parametrize("capacidade", list(Capacidade))
    def test_anonimo_nao_tem_nenhuma(self, capacidade):
        from django.contrib.auth.models import AnonymousUser

        from iscas.permissions import pode

        assert pode(AnonymousUser(), capacidade) is False

    @pytest.mark.parametrize("capacidade", list(Capacidade))
    def test_superuser_sem_grupo_tem_todas(self, django_user_model, capacidade):
        from iscas.permissions import pode

        raiz = django_user_model.objects.create_superuser(
            username="raiz", password="x", email="raiz@x.com"
        )
        assert pode(raiz, capacidade) is True

    @pytest.mark.parametrize("capacidade", list(Capacidade))
    def test_autenticado_sem_grupo_nao_tem_nenhuma(
        self, django_user_model, capacidade
    ):
        from iscas.permissions import pode

        joao = django_user_model.objects.create_user(username="joao", password="x")
        assert pode(joao, capacidade) is False

    def test_dois_grupos_recebem_a_uniao(self, django_user_model):
        """Quem acumula papéis soma capacidades, não intersecta."""
        from iscas.permissions import capacidades_do

        usuario = django_user_model.objects.create_user(username="dois", password="x")
        for nome in (GRUPO_COMERCIAL_FAST, GRUPO_OPERADORES_FAST):
            grupo, _ = Group.objects.get_or_create(name=nome)
            usuario.groups.add(grupo)

        esperado = MATRIZ[GRUPO_COMERCIAL_FAST] | MATRIZ[GRUPO_OPERADORES_FAST]
        assert capacidades_do(usuario) == esperado


class TestNomeDeGrupoExato:
    """"Operadores Iscas" é PREFIXO de "Operadores Iscas Fast"."""

    # sabotagem: trocar filter(name=...) por name__startswith → vermelho
    def test_operador_fast_nao_passa_por_operador(self, usuario_de_papel):
        from iscas.permissions import is_operador, is_operador_fast

        usuario = usuario_de_papel(GRUPO_OPERADORES_FAST)

        assert is_operador_fast(usuario) is True
        assert is_operador(usuario) is False

    def test_operador_nao_passa_por_operador_fast(self, usuario_de_papel):
        from iscas.permissions import is_operador, is_operador_fast

        usuario = usuario_de_papel(GRUPO_OPERADORES)

        assert is_operador(usuario) is True
        assert is_operador_fast(usuario) is False


class TestConstantes:
    def test_os_tres_grupos_sao_distintos(self):
        assert len(set(GRUPOS_ISCAS)) == 3

    def test_capacidades_sem_valor_duplicado(self):
        valores = [c.value for c in Capacidade]
        assert len(valores) == len(set(valores))


class TestFixturesDePapel:
    """As fixtures do conftest entregam exatamente o papel que prometem.

    Sem isto, um erro na fixture faria os testes de papel exercitarem o papel
    errado e passarem assim mesmo.
    """

    @pytest.mark.parametrize("fixture,papel", [
        ("operador_logado", GRUPO_OPERADORES),
        ("operador_fast_logado", GRUPO_OPERADORES_FAST),
        ("comercial_logado", GRUPO_COMERCIAL_FAST),
    ])
    def test_fixture_bate_com_a_matriz(self, request, fixture, papel):
        from iscas.permissions import capacidades_do

        usuario = request.getfixturevalue(fixture)

        assert capacidades_do(usuario) == MATRIZ[papel]

    def test_usuario_sem_papel_nao_tem_capacidade(self, usuario_sem_papel):
        from iscas.permissions import capacidades_do

        assert capacidades_do(usuario_sem_papel) == set()


class TestDecorator:
    """O decorator carrega a capacidade — contrato que a auditoria lê."""

    def test_grava_a_capacidade_na_funcao(self):
        from iscas.permissions import exige

        @exige(Capacidade.VER_ESTOQUE)
        def alguma_view(request):
            """Doc original."""

        assert alguma_view.capacidade_iscas == Capacidade.VER_ESTOQUE

    def test_preserva_nome_e_doc(self):
        from iscas.permissions import exige

        @exige(Capacidade.VER_ESTOQUE)
        def alguma_view(request):
            """Doc original."""

        assert alguma_view.__name__ == "alguma_view"
        assert alguma_view.__doc__ == "Doc original."
