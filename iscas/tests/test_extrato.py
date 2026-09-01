"""Extrato reformulado: cartões em vez de linhas de tabela.

A versão anterior gastava até três linhas de tabela por movimentação (a
principal, a justificativa e o formulário de estorno), o que quebrava o
alinhamento das colunas. Além disso não mostrava quais unidades foram movidas
nem ligava o estorno ao original — o operador tinha que procurar o número.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, MotivoBaixa
from iscas.selectors import extrato_movimentacoes as selectors_extrato
from iscas.services import baixa as baixa_service
from iscas.services import custodia as custodia_service
from iscas.services import estorno as estorno_service
from iscas.services import transferencia as transferencia_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


class TestPropriedadesDoLancamento:
    def test_identificadores_das_unidades(self, unidades_no_deposito, deposito, agente, operador):
        movimentacao = transferencia_service.transferir(
            origem=deposito, destino=agente, autor=operador,
            unidades=unidades_no_deposito[:3],
        )
        assert movimentacao.identificadores == ["D001", "D002", "D003"]

    def test_estorno_aponta_para_quem_o_anulou(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        original = transferencia_service.transferir(
            origem=deposito, destino=agente, autor=operador,
            unidades=unidades_no_deposito[:2],
        )
        contra = estorno_service.estornar(
            movimentacao=original, autor=operador, justificativa="Engano"
        )
        original.refresh_from_db()

        assert original.foi_estornada
        assert original.estorno.pk == contra.pk

    def test_sem_estorno_devolve_none(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        movimentacao = transferencia_service.transferir(
            origem=deposito, destino=agente, autor=operador,
            unidades=unidades_no_deposito[:1],
        )
        assert movimentacao.estorno is None


class TestSaidaDefinitiva:
    """A faixa vermelha marca o que sai e não volta."""

    def test_baixa_e_definitiva(self, deposito, unidades_no_deposito, operador):
        movimentacao = baixa_service.dar_baixa(
            origem=deposito, motivo=MotivoBaixa.PERDA,
            justificativa="Extraviada no transporte", autor=operador,
            unidades=unidades_no_deposito[:1],
        )
        assert movimentacao.eh_saida_definitiva

    def test_entrega_de_descartavel_e_definitiva(
        self, agente, cliente, unidades_com_agente, operador
    ):
        from iscas.enums import TipoMovimentacao

        movimentacao = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.ENTREGA, origem=agente, destino=cliente,
            unidades=unidades_com_agente[:2], autor=operador,
        )
        assert movimentacao.eh_saida_definitiva

    def test_entrega_de_retornavel_nao_e_definitiva(
        self, agente, cliente, retornaveis_com_agente, operador
    ):
        """Retornável entregue continua rastreado — vai voltar."""
        from iscas.enums import TipoMovimentacao

        movimentacao = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.ENTREGA, origem=agente, destino=cliente,
            unidades=retornaveis_com_agente[:2], autor=operador,
        )
        assert not movimentacao.eh_saida_definitiva

    def test_transferencia_nao_e_definitiva(
        self, deposito, agente, unidades_no_deposito, operador
    ):
        movimentacao = transferencia_service.transferir(
            origem=deposito, destino=agente, autor=operador,
            unidades=unidades_no_deposito[:1],
        )
        assert not movimentacao.eh_saida_definitiva


class TestTela:
    def test_mostra_identificadores(
        self, client, operador_logado, deposito, agente,
        unidades_no_deposito, operador,
    ):
        """"Quais iscas foram?" — a pergunta que a tabela não respondia."""
        transferencia_service.transferir(
            origem=deposito, destino=agente, autor=operador,
            unidades=unidades_no_deposito[:3],
        )
        conteudo = client.get(reverse("iscas:extrato")).content.decode()

        for identificador in ["D001", "D002", "D003"]:
            assert identificador in conteudo

    def test_liga_estorno_ao_original(
        self, client, operador_logado, deposito, agente,
        unidades_no_deposito, operador,
    ):
        original = transferencia_service.transferir(
            origem=deposito, destino=agente, autor=operador,
            unidades=unidades_no_deposito[:2],
        )
        estorno_service.estornar(
            movimentacao=original, autor=operador, justificativa="Engano"
        )
        conteudo = client.get(reverse("iscas:extrato")).content.decode()

        assert f"desfaz o lançamento #{original.pk}" in conteudo
        assert "anulada pelo estorno" in conteudo

    def test_justificativa_no_mesmo_cartao(
        self, client, operador_logado, deposito, unidades_no_deposito, operador
    ):
        """Antes virava uma linha de tabela separada, quebrando o alinhamento."""
        baixa_service.dar_baixa(
            origem=deposito, motivo=MotivoBaixa.AVARIA,
            justificativa="Carcaça trincada na queda", autor=operador,
            unidades=unidades_no_deposito[:1],
        )
        conteudo = client.get(reverse("iscas:extrato")).content.decode()

        assert "Carcaça trincada na queda" in conteudo
        # A antiga linha `colspan="7"` some com os cartões.
        assert 'colspan="7"' not in conteudo

    def test_mostra_legenda_das_cores(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:extrato")).content.decode()

        assert "entrou no estoque" in conteudo
        assert "saiu em definitivo" in conteudo

    def test_vazio_orienta_o_operador(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:extrato")).content.decode()

        assert "Nenhuma movimentação registrada" in conteudo
        assert reverse("iscas:entrada") in conteudo

    def test_botao_de_estorno_some_no_ja_estornado(
        self, client, operador_logado, deposito, agente,
        unidades_no_deposito, operador,
    ):
        """Estornado e estorno não oferecem o botão; o restante sim."""
        original = transferencia_service.transferir(
            origem=deposito, destino=agente, autor=operador,
            unidades=unidades_no_deposito[:1],
        )
        contra = estorno_service.estornar(
            movimentacao=original, autor=operador, justificativa="Engano"
        )
        # O botão está desligado na tela (`mostrar_estorno=False` na view), mas
        # a REGRA de quando ele apareceria continua valendo e precisa de guarda
        # — senão, no dia em que for religado, ela volta quebrada em silêncio.
        # Por isso renderizamos o template com a chave ligada.
        conteudo = _extrato_com_estorno_ligado(client)

        # Nem o lançamento anulado nem o próprio estorno podem ser desfeitos.
        assert f'action="/iscas/movimentacoes/{original.pk}/estornar/"' not in conteudo
        assert f'action="/iscas/movimentacoes/{contra.pk}/estornar/"' not in conteudo

        # A entrada que criou as unidades continua estornável — o cenário tem
        # três lançamentos, e só ela deve oferecer o formulário.
        assert conteudo.count("Confirmar estorno") == 1

    def test_botao_esta_desligado_na_tela(
        self, client, operador_logado, deposito, unidades_no_deposito
    ):
        """Estado atual da tela: o estorno não é oferecido ao operador."""
        conteudo = client.get(reverse("iscas:extrato")).content.decode()

        assert "Confirmar estorno" not in conteudo
        assert "Estornar" not in conteudo


def _extrato_com_estorno_ligado(client):
    """Renderiza o extrato como ficaria com o botão religado.

    Pega o contexto real da view e só troca `mostrar_estorno`, para o teste
    exercitar o template de verdade em vez de uma montagem à mão.
    """
    from django.template.loader import render_to_string

    resposta = client.get(reverse("iscas:extrato"))
    # `resposta.context` é um ContextList (vários templates renderizados);
    # as chaves que o extrato usa vêm do contexto da própria view.
    contexto = {
        chave: resposta.context[chave]
        for chave in (
            "form", "pagina", "form_estorno", "querystring", "filtros_ativos"
        )
    }
    contexto["mostrar_estorno"] = True
    return render_to_string("iscas/extrato.html", contexto)


class TestFiltros:
    def test_sinaliza_quando_ha_filtro(
        self, client, operador_logado, deposito, unidades_no_deposito, modelo_descartavel
    ):
        resposta = client.get(
            reverse("iscas:extrato"), {"modelo": modelo_descartavel.pk}
        )
        conteudo = resposta.content.decode()

        assert resposta.context["filtros_ativos"] == 1
        assert "Mostrando resultado filtrado" in conteudo

    def test_sem_filtro_nao_sinaliza(self, client, operador_logado):
        resposta = client.get(reverse("iscas:extrato"))

        assert resposta.context["filtros_ativos"] == 0
        assert "Mostrando resultado filtrado" not in resposta.content.decode()

    def test_querystring_nao_carrega_a_pagina(
        self, client, operador_logado, modelo_descartavel
    ):
        """Sem isso, o link do CSV e da paginação acumulariam `page=`."""
        resposta = client.get(
            reverse("iscas:extrato"), {"modelo": modelo_descartavel.pk, "page": 2}
        )
        assert "page=" not in resposta.context["querystring"]

    def test_filtro_vazio_orienta(
        self, client, operador_logado, unidades_no_deposito, agente
    ):
        resposta = client.get(reverse("iscas:extrato"), {"agente": agente.pk})
        conteudo = resposta.content.decode()

        assert "Nenhum lançamento corresponde aos filtros" in conteudo


class TestDesempenho:
    """O cartão mostra identificadores; sem prefetch cada um custaria consultas."""

    def _consultas_do_selector(self, quantos, deposito, agente, unidades, operador):
        from django.db import connection, reset_queries
        from django.test.utils import override_settings

        from iscas.models.custodia import (
            Movimentacao,
            MovimentacaoUnidade,
            Unidade,
        )

        Unidade.objects.all().update(ultima_movimentacao=None)
        MovimentacaoUnidade.objects.all().delete()
        Movimentacao.objects.all().delete()

        for indice in range(quantos):
            transferencia_service.transferir(
                origem=deposito, destino=agente, autor=operador,
                unidades=unidades[indice : indice + 1],
            )
            transferencia_service.transferir(
                origem=agente, destino=deposito, autor=operador,
                unidades=unidades[indice : indice + 1],
            )

        with override_settings(DEBUG=True):
            reset_queries()
            # Consome o que o template consome de cada lançamento.
            for movimentacao in selectors_extrato():
                _ = movimentacao.identificadores
                _ = movimentacao.foi_estornada
                _ = movimentacao.estorno
                _ = movimentacao.eh_saida_definitiva
                _ = str(movimentacao.origem), str(movimentacao.destino)
                _ = movimentacao.autor.get_username()
            return len(connection.queries)

    def test_custo_nao_cresce_com_o_volume(
        self, deposito, agente, unidades_no_deposito, operador
    ):
        poucos = self._consultas_do_selector(
            2, deposito, agente, unidades_no_deposito, operador
        )
        muitos = self._consultas_do_selector(
            10, deposito, agente, unidades_no_deposito, operador
        )

        assert muitos == poucos, (
            f"N+1: {poucos} consultas para 4 lançamentos e {muitos} para 20."
        )
        assert muitos <= 8, f"{muitos} consultas é mais do que o selector precisa."
