"""A barra mostra a cada papel só o que ele alcança (ISC-RN-19).

Isto não é a autorização — quem barra é o decorator, e `test_acesso_por_papel`
prova isso. Aqui garante-se o outro lado: não oferecer um caminho que terminaria
em 403. Um botão que leva a erro é pior que botão nenhum.
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _barra(client, url_de_partida):
    """O HTML de dentro do <nav> da página — só a navegação."""
    conteudo = client.get(url_de_partida).content.decode()
    inicio = conteudo.index('<nav class="iscas-nav"')
    return conteudo[inicio:conteudo.index("</nav>", inicio)]


#: (papel, rotas que a barra DEVE oferecer, rotas que ela NÃO pode oferecer)
ESPERADO = [
    (
        "comercial_logado",
        ["iscas:painel", "iscas:mapa", "iscas:solicitacao_lista",
         "iscas:cliente_lista", "iscas:solicitacao_criar"],
        ["iscas:painel_saldo", "iscas:unidade_lista", "iscas:retornaveis",
         "iscas:extrato", "iscas:agente_lista", "iscas:deposito_lista",
         "iscas:modelo_lista", "iscas:auditoria"],
    ),
    (
        "operador_fast_logado",
        ["iscas:painel", "iscas:mapa", "iscas:solicitacao_lista",
         "iscas:painel_saldo", "iscas:unidade_lista", "iscas:retornaveis",
         "iscas:extrato", "iscas:cliente_lista", "iscas:modelo_lista",
         "iscas:solicitacao_criar"],
        ["iscas:agente_lista", "iscas:deposito_lista", "iscas:auditoria"],
    ),
    (
        "operador_logado",
        ["iscas:painel", "iscas:mapa", "iscas:solicitacao_lista",
         "iscas:painel_saldo", "iscas:unidade_lista", "iscas:retornaveis",
         "iscas:extrato", "iscas:agente_lista", "iscas:cliente_lista",
         "iscas:deposito_lista", "iscas:modelo_lista", "iscas:auditoria",
         "iscas:solicitacao_criar"],
        [],
    ),
]


class TestBarraPorPapel:
    # sabotagem: remover o {% if cap.VER_ESTOQUE %} da nav → vermelho
    @pytest.mark.parametrize("papel,visiveis,ocultas", ESPERADO)
    def test_a_barra_oferece_so_o_alcancavel(
        self, request, client, papel, visiveis, ocultas
    ):
        request.getfixturevalue(papel)
        barra = _barra(client, reverse("iscas:painel"))

        for rota in visiveis:
            assert f'href="{reverse(rota)}"' in barra, f"{papel}: falta {rota}"
        for rota in ocultas:
            assert f'href="{reverse(rota)}"' not in barra, f"{papel}: sobra {rota}"

    def test_comercial_nao_ve_o_menu_cadastros_com_agente(
        self, client, comercial_logado
    ):
        """Ele cadastra cliente, então o menu existe — mas só com Clientes."""
        barra = _barra(client, reverse("iscas:painel"))

        assert "Cadastros" in barra
        assert f'href="{reverse("iscas:cliente_lista")}"' in barra
        assert f'href="{reverse("iscas:agente_lista")}"' not in barra

    def test_sem_separador_orfao(self, client, comercial_logado):
        """Separador sem grupo depois é traço solto no fim da barra."""
        barra = _barra(client, reverse("iscas:painel"))
        depois_do_ultimo_sep = barra.rsplit("iscas-nav-sep", 1)[-1]

        assert "iscas-nav-link" in depois_do_ultimo_sep


class TestBotoesDeAcao:
    def test_comercial_nao_ve_botao_de_estoque_no_painel(
        self, client, comercial_logado
    ):
        conteudo = client.get(reverse("iscas:painel")).content.decode()

        assert reverse("iscas:entrada") not in conteudo
        assert reverse("iscas:deposito_criar") not in conteudo

    def test_operador_fast_nao_ve_entrada_nem_transferir_nas_unidades(
        self, client, operador_fast_logado
    ):
        conteudo = client.get(reverse("iscas:unidade_lista")).content.decode()

        assert reverse("iscas:entrada") not in conteudo
        assert reverse("iscas:transferencia") not in conteudo

    def test_operador_fast_ve_baixa_e_manutencao(
        self, client, operador_fast_logado
    ):
        """O que define o papel: opera o ciclo, não o abastecimento."""
        conteudo = client.get(reverse("iscas:unidade_lista")).content.decode()

        assert reverse("iscas:baixa") in conteudo
        assert reverse("iscas:manutencao") in conteudo

    def test_operador_fast_nao_ve_excluir_na_lista(
        self, client, operador_fast_logado, solicitacao_simples
    ):
        conteudo = client.get(reverse("iscas:solicitacao_lista")).content.decode()
        url = reverse("iscas:solicitacao_excluir", args=[solicitacao_simples.pk])

        assert url not in conteudo

    def test_operador_fast_ve_atribuir_no_detalhe(
        self, client, operador_fast_logado, solicitacao_simples
    ):
        url = reverse("iscas:solicitacao_detalhe", args=[solicitacao_simples.pk])
        conteudo = client.get(url).content.decode()

        assert reverse(
            "iscas:solicitacao_atribuir", args=[solicitacao_simples.pk]
        ) in conteudo

    def test_comercial_nao_ve_atribuir_nem_excluir_no_detalhe(
        self, client, comercial_logado, solicitacao_simples
    ):
        url = reverse("iscas:solicitacao_detalhe", args=[solicitacao_simples.pk])
        conteudo = client.get(url).content.decode()

        for nome in ("iscas:solicitacao_atribuir", "iscas:solicitacao_excluir",
                     "iscas:solicitacao_cancelar"):
            assert reverse(nome, args=[solicitacao_simples.pk]) not in conteudo


class TestOperadorTotalNaoRegrediu:
    def test_ve_todas_as_acoes_do_detalhe(
        self, client, operador_logado, solicitacao_simples
    ):
        url = reverse("iscas:solicitacao_detalhe", args=[solicitacao_simples.pk])
        conteudo = client.get(url).content.decode()

        for nome in ("iscas:solicitacao_atribuir", "iscas:solicitacao_excluir",
                     "iscas:solicitacao_cancelar"):
            assert reverse(nome, args=[solicitacao_simples.pk]) in conteudo

    def test_ve_todos_os_botoes_das_unidades(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:unidade_lista")).content.decode()

        for nome in ("iscas:entrada", "iscas:transferencia",
                     "iscas:manutencao", "iscas:baixa"):
            assert reverse(nome) in conteudo
