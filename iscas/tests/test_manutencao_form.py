"""Envio para manutenção por seleção de unidades específicas.

Mesmo padrão da baixa, e pelo mesmo motivo: a peça que vai para o conserto é
concreta. Com FIFO, o operador mandava a isca A e o sistema registrava a B —
e o retorno da manutenção, que se faz por identificador, não fechava.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, SituacaoUnidade
from iscas.forms import ManutencaoForm
from iscas.models.custodia import Movimentacao, Unidade
from iscas.services.exceptions import MovimentacaoInvalida

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


def _post(unidades, **extra):
    dados = {
        "tipo_origem": "DEPOSITO",
        "origem_deposito": "",
        "origem_agente": "",
        "unidades": [str(u.pk) for u in unidades],
        "justificativa": "Não liga; enviada à assistência técnica",
    }
    dados.update(extra)
    return dados


class TestSeletorDeOrigem:
    def test_origem_deposito(self, deposito, unidades_no_deposito):
        form = ManutencaoForm(
            _post(unidades_no_deposito[:2], origem_deposito=deposito.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["origem"] == deposito

    def test_origem_agente(self, agente, unidades_com_agente):
        form = ManutencaoForm(
            _post(unidades_com_agente[:2], tipo_origem="AGENTE",
                  origem_agente=agente.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["origem"] == agente

    def test_deposito_sem_escolher_qual(self, deposito, unidades_no_deposito):
        form = ManutencaoForm(_post(unidades_no_deposito[:1]))

        assert not form.is_valid()
        assert "origem_deposito" in form.errors

    def test_agente_sem_escolher_qual(self, agente, unidades_com_agente):
        form = ManutencaoForm(_post(unidades_com_agente[:1], tipo_origem="AGENTE"))

        assert not form.is_valid()
        assert "origem_agente" in form.errors

    def test_campo_do_outro_tipo_e_ignorado(
        self, deposito, agente, unidades_com_agente
    ):
        form = ManutencaoForm(
            _post(unidades_com_agente[:1], tipo_origem="AGENTE",
                  origem_agente=agente.pk, origem_deposito=deposito.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["origem"] == agente


class TestSelecaoDeUnidades:
    def test_exige_ao_menos_uma(self, deposito):
        form = ManutencaoForm(_post([], origem_deposito=deposito.pk))

        assert not form.is_valid()
        assert "unidades" in form.errors

    def test_recusa_unidade_de_outra_custodia(
        self, deposito, agente, unidades_com_agente
    ):
        form = ManutencaoForm(
            _post(unidades_com_agente[:1], origem_deposito=deposito.pk)
        )
        assert not form.is_valid()
        assert "unidades" in form.errors

    def test_recusa_unidade_reservada(
        self, agente, unidades_com_agente, cliente, modelo_descartavel, operador
    ):
        from iscas.services import solicitacao as solicitacao_service

        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 8)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 8)], autor=operador,
        )

        form = ManutencaoForm(
            _post(unidades_com_agente[:1], tipo_origem="AGENTE",
                  origem_agente=agente.pk)
        )
        assert not form.is_valid()
        assert "unidades" in form.errors

    def test_observacao_e_opcional(self, deposito, unidades_no_deposito):
        """Diferente da baixa, aqui o texto não é obrigatório."""
        form = ManutencaoForm(
            _post(unidades_no_deposito[:1], origem_deposito=deposito.pk,
                  justificativa="")
        )
        assert form.is_valid(), form.errors


class TestCamposRemovidos:
    @pytest.mark.parametrize("campo", ["modelo", "quantidade"])
    def test_campo_nao_existe_mais(self, campo):
        assert campo not in ManutencaoForm().fields

    def test_tela_nao_mostra_quantidade(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:manutencao")).content.decode()

        assert 'id="id_quantidade"' not in conteudo
        assert 'id="id_modelo"' not in conteudo


class TestEnvioPelaTela:
    def test_envia_as_unidades_escolhidas(
        self, client, operador_logado, deposito, unidades_no_deposito
    ):
        """As enviadas são as marcadas, não as primeiras da fila."""
        escolhidas = unidades_no_deposito[4:7]

        resposta = client.post(
            reverse("iscas:manutencao"),
            _post(escolhidas, origem_deposito=deposito.pk),
        )
        assert resposta.status_code == 302

        for unidade in escolhidas:
            anotada = Unidade.objects.com_situacao().get(pk=unidade.pk)
            assert anotada.situacao == SituacaoUnidade.EM_MANUTENCAO

        for unidade in unidades_no_deposito[:4]:
            anotada = Unidade.objects.com_situacao().get(pk=unidade.pk)
            assert anotada.situacao == SituacaoUnidade.EM_DEPOSITO

    def test_registra_observacao_e_autor(
        self, client, operador_logado, deposito, unidades_no_deposito, operador
    ):
        client.post(
            reverse("iscas:manutencao"),
            _post(unidades_no_deposito[:2], origem_deposito=deposito.pk,
                  justificativa="Bateria não carrega — OS 4471"),
        )
        movimentacao = Movimentacao.objects.filter(tipo="ENVIO_MANUTENCAO").latest("id")

        assert "OS 4471" in movimentacao.justificativa
        assert movimentacao.autor_id == operador.pk
        assert movimentacao.linhas.count() == 2

    def test_envio_a_partir_do_agente(
        self, client, operador_logado, agente, unidades_com_agente
    ):
        from iscas.services.saldo import saldo_disponivel

        antes = saldo_disponivel(agente)
        client.post(
            reverse("iscas:manutencao"),
            _post(unidades_com_agente[:3], tipo_origem="AGENTE",
                  origem_agente=agente.pk),
        )
        assert saldo_disponivel(agente) == antes - 3

    def test_erro_de_campo_vira_mensagem(
        self, client, operador_logado, deposito, unidades_no_deposito
    ):
        resposta = client.post(
            reverse("iscas:manutencao"),
            _post(unidades_no_deposito[:1]),  # sem escolher o depósito
            follow=True,
        )
        mensagens = [str(m) for m in resposta.context["messages"]]
        assert any("depósito" in m.lower() for m in mensagens), mensagens


class TestCicloCompleto:
    """Manutenção é reversível — o retorno fecha o ciclo (ISC-RN-14)."""

    def test_envia_e_retorna(
        self, client, operador_logado, deposito, unidades_no_deposito, operador
    ):
        from iscas.services import transferencia as transferencia_service
        from iscas.services.saldo import saldo_em_custodia

        escolhidas = unidades_no_deposito[:3]
        client.post(
            reverse("iscas:manutencao"),
            _post(escolhidas, origem_deposito=deposito.pk),
        )
        assert saldo_em_custodia(deposito) == 7

        transferencia_service.retornar_de_manutencao(
            unidades=escolhidas, destino=deposito, autor=operador
        )
        assert saldo_em_custodia(deposito) == 10

        for unidade in escolhidas:
            anotada = Unidade.objects.com_situacao().get(pk=unidade.pk)
            assert anotada.situacao == SituacaoUnidade.EM_DEPOSITO

    def test_retorno_lista_as_unidades_certas(
        self, client, operador_logado, deposito, unidades_no_deposito
    ):
        """A tela de retorno mostra o que está em manutenção, por identificador."""
        escolhidas = unidades_no_deposito[2:5]
        client.post(
            reverse("iscas:manutencao"),
            _post(escolhidas, origem_deposito=deposito.pk),
        )
        conteudo = client.get(reverse("iscas:manutencao_retorno")).content.decode()

        for unidade in escolhidas:
            assert unidade.identificador in conteudo


class TestServiceSemUnidades:
    """A via por modelo+quantidade continua existindo, mas exige os dois."""

    def test_exige_modelo_e_quantidade(self, deposito, operador):
        from iscas.services import transferencia as transferencia_service

        with pytest.raises(MovimentacaoInvalida, match="modelo e a quantidade"):
            transferencia_service.enviar_para_manutencao(
                origem=deposito, autor=operador
            )

    def test_fifo_continua_funcionando(
        self, deposito, unidades_no_deposito, modelo_descartavel, operador
    ):
        from iscas.services import transferencia as transferencia_service

        movimentacao = transferencia_service.enviar_para_manutencao(
            origem=deposito, autor=operador,
            modelo=modelo_descartavel, quantidade=2,
        )
        assert movimentacao.linhas.count() == 2


class TestTela:
    def test_tem_tomselect_e_seletor(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:manutencao")).content.decode()

        assert "tom-select" in conteudo
        assert 'id="id_tipo_origem"' in conteudo
        assert 'id="id_unidades"' in conteudo
        assert "api/unidades/" in conteudo

    def test_javascript_valido(self, client, operador_logado):
        import os
        import re
        import shutil
        import subprocess
        import tempfile

        node = shutil.which("node")
        if not node:
            pytest.skip("node não disponível")

        html = client.get(reverse("iscas:manutencao")).content.decode()
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
