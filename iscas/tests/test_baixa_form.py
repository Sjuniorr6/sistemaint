"""Baixa por seleção de unidades específicas.

Antes era modelo + quantidade, com o sistema escolhendo por FIFO: dava a
quantidade certa mas as unidades erradas. Baixa é sobre iscas concretas — a que
quebrou, a que sumiu — e o identificador é o que torna o lançamento auditável.
"""
import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, MotivoBaixa, SituacaoUnidade
from iscas.forms import BaixaForm
from iscas.models.custodia import Movimentacao, Unidade

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


def _post(unidades, **extra):
    """Monta o POST; `unidades` é lista, como o select múltiplo envia."""
    dados = {
        "tipo_origem": "DEPOSITO",
        "origem_deposito": "",
        "origem_agente": "",
        "unidades": [str(u.pk) for u in unidades],
        "motivo": MotivoBaixa.AVARIA,
        "justificativa": "Carcaça trincada no transporte",
    }
    dados.update(extra)
    return dados


class TestSeletorDeOrigem:
    def test_origem_deposito(self, deposito, unidades_no_deposito):
        form = BaixaForm(
            _post(unidades_no_deposito[:2], tipo_origem="DEPOSITO",
                  origem_deposito=deposito.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["origem"] == deposito

    def test_origem_agente(self, agente, unidades_com_agente):
        form = BaixaForm(
            _post(unidades_com_agente[:2], tipo_origem="AGENTE",
                  origem_agente=agente.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["origem"] == agente

    def test_deposito_sem_escolher_qual(self, deposito, unidades_no_deposito):
        form = BaixaForm(_post(unidades_no_deposito[:1], tipo_origem="DEPOSITO"))

        assert not form.is_valid()
        assert "origem_deposito" in form.errors

    def test_agente_sem_escolher_qual(self, agente, unidades_com_agente):
        form = BaixaForm(_post(unidades_com_agente[:1], tipo_origem="AGENTE"))

        assert not form.is_valid()
        assert "origem_agente" in form.errors

    def test_campo_do_outro_tipo_e_ignorado(
        self, deposito, agente, unidades_com_agente
    ):
        form = BaixaForm(
            _post(unidades_com_agente[:1], tipo_origem="AGENTE",
                  origem_agente=agente.pk, origem_deposito=deposito.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["origem"] == agente


class TestSelecaoDeUnidades:
    def test_exige_ao_menos_uma(self, deposito):
        form = BaixaForm(_post([], origem_deposito=deposito.pk))

        assert not form.is_valid()
        assert "unidades" in form.errors

    def test_recusa_unidade_de_outra_custodia(
        self, deposito, agente, unidades_com_agente
    ):
        """Unidade do agente não pode ser baixada informando o depósito."""
        form = BaixaForm(
            _post(unidades_com_agente[:1], tipo_origem="DEPOSITO",
                  origem_deposito=deposito.pk)
        )
        assert not form.is_valid()
        assert "unidades" in form.errors

    def test_recusa_unidade_reservada(
        self, agente, unidades_com_agente, cliente, modelo_descartavel, operador
    ):
        """Reservada está comprometida com uma solicitação."""
        from iscas.services import solicitacao as solicitacao_service

        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 8)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 8)], autor=operador,
        )

        form = BaixaForm(
            _post(unidades_com_agente[:1], tipo_origem="AGENTE",
                  origem_agente=agente.pk)
        )
        assert not form.is_valid()
        assert "unidades" in form.errors

    def test_resolve_as_unidades_escolhidas(self, deposito, unidades_no_deposito):
        escolhidas = unidades_no_deposito[3:6]
        form = BaixaForm(_post(escolhidas, origem_deposito=deposito.pk))

        assert form.is_valid(), form.errors
        assert {u.pk for u in form.cleaned_data["lista_unidades"]} == {
            u.pk for u in escolhidas
        }


class TestJustificativa:
    def test_exige_texto(self, deposito, unidades_no_deposito):
        form = BaixaForm(
            _post(unidades_no_deposito[:1], origem_deposito=deposito.pk,
                  justificativa="")
        )
        assert not form.is_valid()
        assert "justificativa" in form.errors

    def test_recusa_texto_curto(self, deposito, unidades_no_deposito):
        form = BaixaForm(
            _post(unidades_no_deposito[:1], origem_deposito=deposito.pk,
                  justificativa="oi")
        )
        assert not form.is_valid()


class TestEndpointDeUnidades:
    def test_lista_unidades_do_deposito(
        self, client, operador_logado, deposito, unidades_no_deposito
    ):
        resposta = client.get(
            reverse("iscas:api_unidades_custodia"),
            {"tipo": "DEPOSITO", "id": deposito.pk},
        )
        dados = json.loads(resposta.content)

        assert len(dados["unidades"]) == 10
        primeira = dados["unidades"][0]
        assert "identificador" in primeira
        assert "modelo" in primeira
        assert "—" in primeira["rotulo"]

    def test_lista_unidades_do_agente(
        self, client, operador_logado, agente, unidades_com_agente
    ):
        resposta = client.get(
            reverse("iscas:api_unidades_custodia"),
            {"tipo": "AGENTE", "id": agente.pk},
        )
        assert len(json.loads(resposta.content)["unidades"]) == 8

    def test_omite_reservadas(
        self, client, operador_logado, agente, unidades_com_agente,
        cliente, modelo_descartavel, operador,
    ):
        """Reservada não aparece: o service recusaria e o operador se frustraria."""
        from iscas.services import solicitacao as solicitacao_service

        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )

        resposta = client.get(
            reverse("iscas:api_unidades_custodia"),
            {"tipo": "AGENTE", "id": agente.pk},
        )
        assert len(json.loads(resposta.content)["unidades"]) == 5

    def test_sem_id_devolve_vazio(self, client, operador_logado):
        resposta = client.get(
            reverse("iscas:api_unidades_custodia"), {"tipo": "DEPOSITO"}
        )
        assert json.loads(resposta.content)["unidades"] == []

    def test_tipo_invalido(self, client, operador_logado, deposito):
        resposta = client.get(
            reverse("iscas:api_unidades_custodia"), {"tipo": "XPTO", "id": deposito.pk}
        )
        assert resposta.status_code == 400

    def test_exige_operador(self, client, deposito):
        resposta = client.get(
            reverse("iscas:api_unidades_custodia"),
            {"tipo": "DEPOSITO", "id": deposito.pk},
        )
        assert resposta.status_code == 302


class TestBaixaPelaTela:
    def test_baixa_as_unidades_escolhidas(
        self, client, operador_logado, deposito, unidades_no_deposito
    ):
        """As unidades baixadas são exatamente as marcadas, não as primeiras."""
        escolhidas = unidades_no_deposito[5:8]

        resposta = client.post(
            reverse("iscas:baixa"),
            _post(escolhidas, origem_deposito=deposito.pk,
                  motivo=MotivoBaixa.PERDA,
                  justificativa="Extraviadas no transporte, protocolo 123"),
        )
        assert resposta.status_code == 302

        for unidade in escolhidas:
            anotada = Unidade.objects.com_situacao().get(pk=unidade.pk)
            assert anotada.situacao == SituacaoUnidade.BAIXADA

        # As demais continuam intactas — nada de FIFO pegando as erradas.
        for unidade in unidades_no_deposito[:5]:
            anotada = Unidade.objects.com_situacao().get(pk=unidade.pk)
            assert anotada.situacao == SituacaoUnidade.EM_DEPOSITO

    def test_registra_motivo_autor_e_justificativa(
        self, client, operador_logado, deposito, unidades_no_deposito, operador
    ):
        client.post(
            reverse("iscas:baixa"),
            _post(unidades_no_deposito[:2], origem_deposito=deposito.pk,
                  motivo=MotivoBaixa.OBSOLESCENCIA,
                  justificativa="Modelo descontinuado pelo fabricante"),
        )
        movimentacao = Movimentacao.objects.filter(tipo="BAIXA").latest("id")

        assert movimentacao.motivo_baixa == MotivoBaixa.OBSOLESCENCIA
        assert movimentacao.autor_id == operador.pk
        assert "descontinuado" in movimentacao.justificativa
        assert movimentacao.linhas.count() == 2

    def test_baixa_a_partir_do_agente(
        self, client, operador_logado, agente, unidades_com_agente
    ):
        from iscas.services.saldo import saldo_em_custodia

        client.post(
            reverse("iscas:baixa"),
            _post(unidades_com_agente[:3], tipo_origem="AGENTE",
                  origem_agente=agente.pk),
        )
        assert saldo_em_custodia(agente) == 5

    def test_erro_de_campo_vira_mensagem(
        self, client, operador_logado, deposito, unidades_no_deposito
    ):
        resposta = client.post(
            reverse("iscas:baixa"),
            _post(unidades_no_deposito[:1], origem_deposito=deposito.pk,
                  justificativa="x"),
            follow=True,
        )
        mensagens = [str(m) for m in resposta.context["messages"]]
        assert any("justificativa" in m.lower() for m in mensagens), mensagens


class TestTela:
    def test_tem_tomselect_e_seletor(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:baixa")).content.decode()

        assert "tom-select" in conteudo
        assert 'id="id_tipo_origem"' in conteudo
        assert 'id="id_unidades"' in conteudo
        assert "api/unidades/" in conteudo

    def test_nao_tem_mais_modelo_e_quantidade(self, client, operador_logado):
        """Os campos substituídos não podem voltar."""
        form = BaixaForm()
        assert "modelo" not in form.fields
        assert "quantidade" not in form.fields

    def test_javascript_valido(self, client, operador_logado):
        import os
        import re
        import shutil
        import subprocess
        import tempfile

        node = shutil.which("node")
        if not node:
            pytest.skip("node não disponível")

        html = client.get(reverse("iscas:baixa")).content.decode()
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
