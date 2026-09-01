"""Painel de saldos: uma linha por custodia, detalhe sob demanda (ISC-RF-15)."""
import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES
from iscas.services import entrada as entrada_service
from iscas.services import solicitacao as solicitacao_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


class TestContagemDeConsultas:
    """A tela lista todos os agentes: o custo nao pode crescer com eles.

    Era uma consulta de saldo POR agente — N+1 que degrada exatamente quando a
    operacao cresce, que e quando a tela mais importa.
    """

    def test_contagem_constante_com_mais_agentes(
        self, client, operador_logado, modelo_descartavel, operador, db
    ):
        # sabotagem: trocar saldo_por_modelo_em_lote por saldo_por_modelo
        # num laco na view → vermelho
        from iscas.models.cadastro import Agente

        def criar_agente_com_estoque(indice):
            agente = Agente(
                nome=f"Agente {indice}",
                telefone="11999999999",
                logradouro="Rua X", numero="1", bairro="Centro",
                cidade="São Paulo", uf="SP", cep="01001-000",
            )
            agente.cpf = f"{indice:011d}"
            agente.save()
            entrada_service.registrar_entrada(
                modelo=modelo_descartavel,
                identificadores=[f"P{indice}-{n}" for n in range(3)],
                destino=agente,
                autor=operador,
            )
            return agente

        for i in range(2):
            criar_agente_com_estoque(i)
        client.get(reverse("iscas:painel_saldo"))  # aquece sessão/auth

        with CaptureQueriesContext(connection) as com_2:
            client.get(reverse("iscas:painel_saldo"))

        for i in range(2, 12):
            criar_agente_com_estoque(i)

        with CaptureQueriesContext(connection) as com_12:
            client.get(reverse("iscas:painel_saldo"))

        assert len(com_12) == len(com_2), (
            f"{len(com_2)} consultas com 2 agentes e {len(com_12)} com 12: "
            "o painel de saldos voltou a ter N+1."
        )


class TestConteudo:
    def test_mostra_totais_e_detalhe_por_modelo(
        self, client, operador_logado, agente, unidades_com_agente,
        retornaveis_com_agente, modelo_descartavel, modelo_retornavel,
    ):
        conteudo = client.get(reverse("iscas:painel_saldo")).content.decode()

        assert agente.nome in conteudo
        assert "2 modelo(s)" in conteudo
        # O detalhe por modelo continua na pagina, dentro do collapse.
        assert modelo_descartavel.nome in conteudo
        assert modelo_retornavel.nome in conteudo

    def test_reservado_aparece_separado_do_disponivel(
        self, client, operador_logado, agente, unidades_com_agente,
        cliente, modelo_descartavel, operador,
    ):
        """8 em custodia, 3 reservadas → 5 disponiveis."""
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        bloco = next(
            b
            for b in client.get(reverse("iscas:painel_saldo")).context["agentes"]
            if b["entidade"].pk == agente.pk
        )

        assert bloco["total"] == 8
        assert bloco["disponivel"] == 5
        assert bloco["reservado"] == 3

    def test_zerados_ficam_fora_por_padrao_mas_alcancaveis(
        self, client, operador_logado, agente, agente2, unidades_com_agente
    ):
        """`agente2` nao tem estoque: e ruido numa tela de saldo, mas nao pode
        sumir a ponto do operador achar que saiu do cadastro."""
        padrao = client.get(reverse("iscas:painel_saldo"))
        com_zerados = client.get(reverse("iscas:painel_saldo"), {"sem_saldo": "1"})

        nomes_padrao = [b["entidade"].nome for b in padrao.context["agentes"]]
        nomes_todos = [b["entidade"].nome for b in com_zerados.context["agentes"]]

        assert agente.nome in nomes_padrao
        assert agente2.nome not in nomes_padrao
        assert agente2.nome in nomes_todos

    def test_busca_filtra_por_nome(
        self, client, operador_logado, agente, agente2, unidades_com_agente
    ):
        resposta = client.get(
            reverse("iscas:painel_saldo"), {"q": "Um", "sem_saldo": "1"}
        )
        nomes = [b["entidade"].nome for b in resposta.context["agentes"]]

        assert agente.nome in nomes
        assert agente2.nome not in nomes
