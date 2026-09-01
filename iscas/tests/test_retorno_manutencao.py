"""Retorno da manutenção ao estoque, por seleção de unidades.

A tela pedia os identificadores digitados à mão — o que só funcionava se o
operador os tivesse anotado no envio. Agora um TomSelect lista o que está em
manutenção, e o seletor governa o destino: depósito ou agente.
"""
import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, SituacaoUnidade
from iscas.forms import RetornoManutencaoForm
from iscas.models.custodia import Movimentacao, Unidade
from iscas.services import transferencia as transferencia_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


@pytest.fixture
def em_manutencao(deposito, unidades_no_deposito, operador):
    """4 unidades enviadas ao conserto, prontas para voltar."""
    escolhidas = unidades_no_deposito[:4]
    transferencia_service.enviar_para_manutencao(
        origem=deposito, autor=operador, unidades=escolhidas,
        justificativa="Não ligam",
    )
    return escolhidas


def _post(unidades, **extra):
    dados = {
        "tipo_origem": "DEPOSITO",
        "origem_deposito": "",
        "origem_agente": "",
        "unidades": [str(u.pk) for u in unidades],
        "justificativa": "",
    }
    dados.update(extra)
    return dados


class TestSeletorDeDestino:
    def test_devolve_ao_deposito(self, deposito, em_manutencao):
        form = RetornoManutencaoForm(
            _post(em_manutencao[:2], origem_deposito=deposito.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["destino"] == deposito

    def test_devolve_ao_agente(self, agente, em_manutencao):
        """A peça consertada pode ir direto para um agente."""
        form = RetornoManutencaoForm(
            _post(em_manutencao[:2], tipo_origem="AGENTE", origem_agente=agente.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["destino"] == agente

    def test_deposito_sem_escolher_qual(self, em_manutencao):
        form = RetornoManutencaoForm(_post(em_manutencao[:1]))

        assert not form.is_valid()
        assert "origem_deposito" in form.errors

    def test_agente_sem_escolher_qual(self, em_manutencao):
        form = RetornoManutencaoForm(_post(em_manutencao[:1], tipo_origem="AGENTE"))

        assert not form.is_valid()
        assert "origem_agente" in form.errors


class TestSelecaoDeUnidades:
    def test_exige_ao_menos_uma(self, deposito, em_manutencao):
        form = RetornoManutencaoForm(_post([], origem_deposito=deposito.pk))

        assert not form.is_valid()
        assert "unidades" in form.errors

    def test_recusa_unidade_que_nao_esta_em_manutencao(
        self, deposito, unidades_no_deposito, em_manutencao
    ):
        """As últimas nunca foram enviadas ao conserto."""
        form = RetornoManutencaoForm(
            _post(unidades_no_deposito[8:9], origem_deposito=deposito.pk)
        )
        assert not form.is_valid()
        assert "unidades" in form.errors

    def test_nao_pede_mais_identificadores_digitados(self):
        """O campo virou seletor: o widget não é mais textarea."""
        from django import forms as django_forms

        widget = RetornoManutencaoForm().fields["unidades"].widget
        assert isinstance(widget, django_forms.SelectMultiple)


class TestEndpointDeManutencao:
    def test_lista_o_que_esta_em_manutencao(
        self, client, operador_logado, em_manutencao
    ):
        resposta = client.get(
            reverse("iscas:api_unidades_custodia"), {"tipo": "MANUTENCAO"}
        )
        dados = json.loads(resposta.content)

        assert len(dados["unidades"]) == 4
        identificadores = {u["identificador"] for u in dados["unidades"]}
        assert identificadores == {u.identificador for u in em_manutencao}

    def test_nao_pede_id(self, client, operador_logado, em_manutencao):
        """MANUTENCAO é conta singleton — não há entidade para informar."""
        resposta = client.get(
            reverse("iscas:api_unidades_custodia"), {"tipo": "MANUTENCAO"}
        )
        assert resposta.status_code == 200

    def test_vazio_quando_nada_em_conserto(
        self, client, operador_logado, unidades_no_deposito
    ):
        resposta = client.get(
            reverse("iscas:api_unidades_custodia"), {"tipo": "MANUTENCAO"}
        )
        assert json.loads(resposta.content)["unidades"] == []

    def test_rotulo_traz_identificador_e_modelo(
        self, client, operador_logado, em_manutencao
    ):
        dados = json.loads(
            client.get(
                reverse("iscas:api_unidades_custodia"), {"tipo": "MANUTENCAO"}
            ).content
        )
        assert "—" in dados["unidades"][0]["rotulo"]


class TestRetornoPelaTela:
    def test_devolve_as_escolhidas_ao_deposito(
        self, client, operador_logado, deposito, em_manutencao
    ):
        escolhidas = em_manutencao[:2]

        resposta = client.post(
            reverse("iscas:manutencao_retorno"),
            _post(escolhidas, origem_deposito=deposito.pk),
        )
        assert resposta.status_code == 302

        for unidade in escolhidas:
            anotada = Unidade.objects.com_situacao().get(pk=unidade.pk)
            assert anotada.situacao == SituacaoUnidade.EM_DEPOSITO

        # As demais continuam no conserto.
        for unidade in em_manutencao[2:]:
            anotada = Unidade.objects.com_situacao().get(pk=unidade.pk)
            assert anotada.situacao == SituacaoUnidade.EM_MANUTENCAO

    def test_devolve_ao_agente(self, client, operador_logado, agente, em_manutencao):
        from iscas.services.saldo import saldo_em_custodia

        client.post(
            reverse("iscas:manutencao_retorno"),
            _post(em_manutencao[:3], tipo_origem="AGENTE", origem_agente=agente.pk),
        )
        assert saldo_em_custodia(agente) == 3

    def test_registra_observacao_e_autor(
        self, client, operador_logado, deposito, em_manutencao, operador
    ):
        client.post(
            reverse("iscas:manutencao_retorno"),
            _post(em_manutencao[:1], origem_deposito=deposito.pk,
                  justificativa="Placa substituída em garantia — OS 5512"),
        )
        movimentacao = Movimentacao.objects.filter(
            tipo="RETORNO_MANUTENCAO"
        ).latest("id")

        assert "OS 5512" in movimentacao.justificativa
        assert movimentacao.autor_id == operador.pk

    def test_volta_ao_saldo_disponivel(
        self, client, operador_logado, deposito, em_manutencao
    ):
        """Manutenção é reversível: a unidade volta a ser alocável."""
        from iscas.services.saldo import saldo_disponivel

        antes = saldo_disponivel(deposito)
        client.post(
            reverse("iscas:manutencao_retorno"),
            _post(em_manutencao, origem_deposito=deposito.pk),
        )
        assert saldo_disponivel(deposito) == antes + 4

    def test_erro_de_campo_vira_mensagem(
        self, client, operador_logado, em_manutencao
    ):
        resposta = client.post(
            reverse("iscas:manutencao_retorno"),
            _post(em_manutencao[:1]),  # sem escolher o depósito
            follow=True,
        )
        mensagens = [str(m) for m in resposta.context["messages"]]
        assert any("depósito" in m.lower() for m in mensagens), mensagens


class TestTela:
    def test_tem_tomselect_e_seletor(self, client, operador_logado, em_manutencao):
        conteudo = client.get(reverse("iscas:manutencao_retorno")).content.decode()

        assert "tom-select" in conteudo
        assert 'id="id_tipo_origem"' in conteudo
        assert 'id="id_unidades"' in conteudo
        assert "tipo=MANUTENCAO" in conteudo

    def test_lista_lateral_mostra_o_que_esta_em_conserto(
        self, client, operador_logado, em_manutencao
    ):
        conteudo = client.get(reverse("iscas:manutencao_retorno")).content.decode()

        for unidade in em_manutencao:
            assert unidade.identificador in conteudo

    def test_avisa_quando_nada_em_manutencao(
        self, client, operador_logado, unidades_no_deposito
    ):
        conteudo = client.get(reverse("iscas:manutencao_retorno")).content.decode()

        assert "Nada em manutenção" in conteudo

    def test_tem_selecionar_todas(self, client, operador_logado, em_manutencao):
        """Um lote inteiro costuma voltar do conserto de uma vez."""
        conteudo = client.get(reverse("iscas:manutencao_retorno")).content.decode()
        assert "selecionarTodas" in conteudo

    def test_javascript_valido(self, client, operador_logado, em_manutencao):
        import os
        import re
        import shutil
        import subprocess
        import tempfile

        node = shutil.which("node")
        if not node:
            pytest.skip("node não disponível")

        html = client.get(reverse("iscas:manutencao_retorno")).content.decode()
        codigo = "\n".join(
            b for b in re.findall(r"<script[^>]*>(.*?)</script>", html, re.S) if b.strip()
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as arquivo:
            arquivo.write(codigo)
            caminho = arquivo.name
        try:
            resultado = subprocess.run(
                [node, "--check", caminho], capture_output=True, text=True
            )
            assert resultado.returncode == 0, resultado.stderr[:600]
        finally:
            os.unlink(caminho)


class TestCicloCompletoPelaTela:
    def test_envia_e_devolve_a_outro_destino(
        self, client, operador_logado, deposito, agente, unidades_no_deposito
    ):
        """Sai do depósito, volta para o agente — caminho legítimo."""
        from iscas.services.saldo import saldo_em_custodia

        escolhidas = unidades_no_deposito[:3]
        client.post(
            reverse("iscas:manutencao"),
            {
                "tipo_origem": "DEPOSITO",
                "origem_deposito": deposito.pk,
                "origem_agente": "",
                "unidades": [str(u.pk) for u in escolhidas],
                "justificativa": "Defeito na bateria",
            },
        )
        assert saldo_em_custodia(deposito) == 7

        client.post(
            reverse("iscas:manutencao_retorno"),
            _post(escolhidas, tipo_origem="AGENTE", origem_agente=agente.pk),
        )
        assert saldo_em_custodia(agente) == 3
        assert saldo_em_custodia(deposito) == 7
