"""A barra do app e a unica navegacao entre as abas do Iscas Fast.

O menu do topo virou link direto para o painel; se a barra deixar de alcancar
alguma secao, ela fica inacessivel — nao ha mais o dropdown para socorrer.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.context_processors import _SECAO_POR_PREFIXO
from iscas.enums import GRUPO_OPERADORES

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


#: As secoes que a barra precisa alcancar, derivadas do context processor —
#: lista mantida a mao ao lado do codigo vira trabalho dobrado para sempre.
SECOES = sorted({secao for _, secao in _SECAO_POR_PREFIXO})


def test_a_barra_alcanca_todas_as_secoes(client, operador_logado):
    """Cada secao da navegacao tem um caminho a partir da barra.

    Vale tanto para link direto quanto para item do menu Cadastros: o que
    nao pode e a secao existir e nao ter porta.
    """
    conteudo = client.get(reverse("iscas:painel")).content.decode()
    inicio = conteudo.index('<nav class="iscas-nav"')
    barra = conteudo[inicio:conteudo.index("</nav>", inicio)]

    urls_da_barra = {
        "painel": reverse("iscas:painel"),
        "mapa": reverse("iscas:mapa"),
        "solicitacoes": reverse("iscas:solicitacao_lista"),
        "saldos": reverse("iscas:painel_saldo"),
        "unidades": reverse("iscas:unidade_lista"),
        "retornaveis": reverse("iscas:retornaveis"),
        "extrato": reverse("iscas:extrato"),
        "agentes": reverse("iscas:agente_lista"),
        "clientes": reverse("iscas:cliente_lista"),
        "depositos": reverse("iscas:deposito_lista"),
        "modelos": reverse("iscas:modelo_lista"),
    }

    # Nenhuma secao do context processor pode ficar de fora do mapeamento.
    assert set(urls_da_barra) == set(SECOES), (
        f"secoes sem porta na barra: {set(SECOES) - set(urls_da_barra)}"
    )
    for secao, url in urls_da_barra.items():
        assert f'href="{url}"' in barra, f"{secao} nao esta na barra"


@pytest.mark.parametrize("nome_url,secao_esperada", [
    ("iscas:painel", "painel"),
    ("iscas:mapa", "mapa"),
    ("iscas:solicitacao_lista", "solicitacoes"),
    ("iscas:painel_saldo", "saldos"),
    ("iscas:unidade_lista", "unidades"),
    ("iscas:retornaveis", "retornaveis"),
    ("iscas:extrato", "extrato"),
    ("iscas:agente_lista", "agentes"),
    ("iscas:cliente_lista", "clientes"),
    ("iscas:deposito_lista", "depositos"),
    ("iscas:modelo_lista", "modelos"),
])
def test_cada_tela_marca_a_propria_aba(
    client, operador_logado, nome_url, secao_esperada
):
    """Sem o destaque, a barra nao diz onde o operador esta."""
    resposta = client.get(reverse(nome_url))

    assert resposta.status_code == 200
    assert resposta.context["secao"] == secao_esperada


def test_cadastros_destaca_o_menu_agrupado(client, operador_logado):
    """As quatro telas de cadastro vivem num dropdown; ele acende para todas."""
    for nome in ("agente_lista", "cliente_lista", "deposito_lista", "modelo_lista"):
        conteudo = client.get(reverse(f"iscas:{nome}")).content.decode()
        inicio = conteudo.index('<nav class="iscas-nav"')
        barra = conteudo[inicio:conteudo.index("</nav>", inicio)]

        assert "dropdown-toggle ativo" in barra, f"{nome} nao acende Cadastros"


class TestMenuDoTopo:
    def test_iscas_fast_leva_ao_painel_sem_dropdown(self, client, operador_logado):
        """O menu do topo nao duplica mais a navegacao do app.

        Dois menus para os mesmos destinos divergem: o dropdown ja nao tinha
        Saldos nem a lixeira de solicitacoes.
        """
        conteudo = client.get(reverse("iscas:painel")).content.decode()

        assert 'id="dropdownIscas"' not in conteudo
        assert 'aria-labelledby="dropdownIscas"' not in conteudo
        # O item continua existindo, agora como link direto para o painel.
        assert "Iscas Fast" in conteudo
