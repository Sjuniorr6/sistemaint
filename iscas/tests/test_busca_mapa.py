"""Busca por agente, cliente ou endereço no mapa.

A busca é client-side para nome de agente e endereço de solicitação — os dois
já chegam no payload do geojson que a página baixa na abertura. O geocodificador
só entra quando nada em memória bate, para o caso comum não pagar rede.
"""
import re

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def html_do_mapa(client, operador_logado):
    return client.get(reverse("iscas:mapa")).content.decode()


class TestCampoDeBusca:
    def test_a_tela_tem_o_campo(self, html_do_mapa):
        assert "Buscar agente, cliente ou endereço" in html_do_mapa

    def test_chama_o_geocodificador_do_app(self, html_do_mapa):
        """Reusa o endpoint que já existe, sem rota nova."""
        assert reverse("iscas:api_geocodificar") in html_do_mapa

    # sabotagem: remover `this.agentes.push(...)` de carregarAgentes → vermelho
    def test_guarda_as_properties_dos_agentes(self, html_do_mapa):
        """Sem guardar, a busca por nome teria de voltar ao servidor."""
        assert "this.agentes.push(" in html_do_mapa

    def test_usa_zoom_de_cluster_para_o_agente(self, html_do_mapa):
        """`setView` cru não abre o popup de marcador agrupado."""
        trecho = html_do_mapa[html_do_mapa.index("focar(id)"):]
        assert "this.cluster.zoomToShowLayer" in trecho[:400]


class TestJavaScriptValido:
    def test_chaves_balanceadas_no_script(self, html_do_mapa):
        """Erro de sintaxe no JS não aparece em teste de view — a página
        renderiza 200 com o mapa morto. Contar delimitadores pega o caso
        grosseiro de bloco não fechado."""
        inicio = html_do_mapa.index("function mapaIscas()")
        fim = html_do_mapa.index("</script>", inicio)
        corpo = html_do_mapa[inicio:fim]
        # Tira strings e comentários, que podem ter chaves soltas.
        limpo = re.sub(r"`[^`]*`|'[^']*'|\"[^\"]*\"|//[^\n]*|/\*.*?\*/", "", corpo, flags=re.S)

        assert limpo.count("{") == limpo.count("}")
        assert limpo.count("(") == limpo.count(")")
        assert limpo.count("[") == limpo.count("]")

    @pytest.mark.parametrize("metodo", [
        "sugerir()", "irPara(sugestao)", "buscarNoMapa()", "normalizar(texto)",
    ])
    def test_metodos_declarados(self, html_do_mapa, metodo):
        assert metodo in html_do_mapa
