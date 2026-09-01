"""Transferência entre custódias internas, por seleção de unidades.

Fecha o conjunto: entrada, baixa, manutenção, retorno e agora transferência
seguem o mesmo padrão — seletor de tipo revelando o select certo, e TomSelect
com as unidades da origem.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, SituacaoUnidade
from iscas.forms import TransferenciaForm
from iscas.models.custodia import Movimentacao, Unidade
from iscas.services.exceptions import MovimentacaoInvalida
from iscas.services.saldo import saldo_em_custodia

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
        "tipo_destino": "AGENTE",
        "destino_deposito": "",
        "destino_agente": "",
        "unidades": [str(u.pk) for u in unidades],
        "justificativa": "",
    }
    dados.update(extra)
    return dados


class TestSeletores:
    def test_deposito_para_agente(
        self, deposito, agente, unidades_no_deposito
    ):
        form = TransferenciaForm(
            _post(unidades_no_deposito[:3], origem_deposito=deposito.pk,
                  destino_agente=agente.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["origem"] == deposito
        assert form.cleaned_data["destino"] == agente

    def test_agente_para_deposito(self, deposito, agente, unidades_com_agente):
        form = TransferenciaForm(
            _post(unidades_com_agente[:2], tipo_origem="AGENTE",
                  origem_agente=agente.pk, tipo_destino="DEPOSITO",
                  destino_deposito=deposito.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["origem"] == agente
        assert form.cleaned_data["destino"] == deposito

    def test_agente_para_agente(self, agente, agente2, unidades_com_agente):
        """Redistribuir de quem tem sobra para quem tem falta."""
        form = TransferenciaForm(
            _post(unidades_com_agente[:2], tipo_origem="AGENTE",
                  origem_agente=agente.pk, tipo_destino="AGENTE",
                  destino_agente=agente2.pk)
        )
        assert form.is_valid(), form.errors

    def test_origem_sem_escolher_qual(self, agente, unidades_no_deposito):
        form = TransferenciaForm(
            _post(unidades_no_deposito[:1], destino_agente=agente.pk)
        )
        assert not form.is_valid()
        assert "origem_deposito" in form.errors

    def test_destino_sem_escolher_qual(self, deposito, unidades_no_deposito):
        form = TransferenciaForm(
            _post(unidades_no_deposito[:1], origem_deposito=deposito.pk)
        )
        assert not form.is_valid()
        assert "destino_agente" in form.errors

    def test_origem_igual_ao_destino(self, deposito, unidades_no_deposito):
        form = TransferenciaForm(
            _post(unidades_no_deposito[:1], origem_deposito=deposito.pk,
                  tipo_destino="DEPOSITO", destino_deposito=deposito.pk)
        )
        assert not form.is_valid()
        assert any("mesmo lugar" in str(e) for e in form.errors.values())

    def test_campos_do_outro_tipo_sao_ignorados(
        self, deposito, agente, agente2, unidades_com_agente
    ):
        """Valores remanescentes dos selects escondidos não interferem."""
        form = TransferenciaForm(
            _post(unidades_com_agente[:1],
                  tipo_origem="AGENTE", origem_agente=agente.pk,
                  origem_deposito=deposito.pk,
                  tipo_destino="AGENTE", destino_agente=agente2.pk,
                  destino_deposito=deposito.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["origem"] == agente
        assert form.cleaned_data["destino"] == agente2


class TestSelecaoDeUnidades:
    def test_exige_ao_menos_uma(self, deposito, agente):
        form = TransferenciaForm(
            _post([], origem_deposito=deposito.pk, destino_agente=agente.pk)
        )
        assert not form.is_valid()
        assert "unidades" in form.errors

    def test_unidades_vem_da_origem(
        self, deposito, agente, unidades_com_agente
    ):
        """Unidade do agente não pode ser transferida informando o depósito."""
        form = TransferenciaForm(
            _post(unidades_com_agente[:1], origem_deposito=deposito.pk,
                  destino_agente=agente.pk)
        )
        assert not form.is_valid()
        assert "unidades" in form.errors

    def test_recusa_unidade_reservada(
        self, agente, deposito, unidades_com_agente, cliente,
        modelo_descartavel, operador,
    ):
        from iscas.services import solicitacao as solicitacao_service

        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 8)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 8)], autor=operador,
        )

        form = TransferenciaForm(
            _post(unidades_com_agente[:1], tipo_origem="AGENTE",
                  origem_agente=agente.pk, tipo_destino="DEPOSITO",
                  destino_deposito=deposito.pk)
        )
        assert not form.is_valid()
        assert "unidades" in form.errors


class TestCamposRemovidos:
    @pytest.mark.parametrize("campo", ["modelo", "quantidade"])
    def test_campo_nao_existe_mais(self, campo):
        assert campo not in TransferenciaForm().fields

    def test_tela_nao_mostra_quantidade(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:transferencia")).content.decode()

        assert 'id="id_quantidade"' not in conteudo
        assert 'id="id_modelo"' not in conteudo


class TestTransferenciaPelaTela:
    def test_transfere_as_escolhidas(
        self, client, operador_logado, deposito, agente, unidades_no_deposito
    ):
        """As transferidas são as marcadas, não as primeiras da fila."""
        escolhidas = unidades_no_deposito[6:9]

        resposta = client.post(
            reverse("iscas:transferencia"),
            _post(escolhidas, origem_deposito=deposito.pk, destino_agente=agente.pk),
        )
        assert resposta.status_code == 302

        for unidade in escolhidas:
            anotada = Unidade.objects.com_situacao().get(pk=unidade.pk)
            assert anotada.situacao == SituacaoUnidade.COM_AGENTE

        for unidade in unidades_no_deposito[:6]:
            anotada = Unidade.objects.com_situacao().get(pk=unidade.pk)
            assert anotada.situacao == SituacaoUnidade.EM_DEPOSITO

    def test_saldo_move_sem_mudar_o_total(
        self, client, operador_logado, deposito, agente, unidades_no_deposito
    ):
        """Transferência é neutra: o total do sistema não muda."""
        total_antes = Unidade.objects.count()

        client.post(
            reverse("iscas:transferencia"),
            _post(unidades_no_deposito[:4], origem_deposito=deposito.pk,
                  destino_agente=agente.pk),
        )

        assert saldo_em_custodia(deposito) == 6
        assert saldo_em_custodia(agente) == 4
        assert Unidade.objects.count() == total_antes

    def test_agente_para_agente_pela_tela(
        self, client, operador_logado, agente, agente2, unidades_com_agente
    ):
        client.post(
            reverse("iscas:transferencia"),
            _post(unidades_com_agente[:3], tipo_origem="AGENTE",
                  origem_agente=agente.pk, tipo_destino="AGENTE",
                  destino_agente=agente2.pk),
        )
        assert saldo_em_custodia(agente) == 5
        assert saldo_em_custodia(agente2) == 3

    def test_registra_observacao_e_autor(
        self, client, operador_logado, deposito, agente,
        unidades_no_deposito, operador,
    ):
        client.post(
            reverse("iscas:transferencia"),
            _post(unidades_no_deposito[:2], origem_deposito=deposito.pk,
                  destino_agente=agente.pk,
                  justificativa="Reposição semanal da rota sul"),
        )
        movimentacao = Movimentacao.objects.filter(tipo="TRANSFERENCIA").latest("id")

        assert "rota sul" in movimentacao.justificativa
        assert movimentacao.autor_id == operador.pk
        assert movimentacao.linhas.count() == 2

    def test_erro_de_campo_vira_mensagem(
        self, client, operador_logado, deposito, unidades_no_deposito
    ):
        resposta = client.post(
            reverse("iscas:transferencia"),
            _post(unidades_no_deposito[:1], origem_deposito=deposito.pk),
            follow=True,
        )
        mensagens = [str(m) for m in resposta.context["messages"]]
        assert any("agente" in m.lower() for m in mensagens), mensagens


class TestServiceSemUnidades:
    """A via por modelo+quantidade continua existindo para uso programático."""

    def test_exige_modelo_e_quantidade(self, deposito, agente, operador):
        from iscas.services import transferencia as transferencia_service

        with pytest.raises(MovimentacaoInvalida, match="modelo e a quantidade"):
            transferencia_service.transferir(
                origem=deposito, destino=agente, autor=operador
            )

    def test_fifo_continua_funcionando(
        self, deposito, agente, unidades_no_deposito, modelo_descartavel, operador
    ):
        from iscas.services import transferencia as transferencia_service

        movimentacao = transferencia_service.transferir(
            origem=deposito, destino=agente, autor=operador,
            modelo=modelo_descartavel, quantidade=3,
        )
        assert movimentacao.linhas.count() == 3


class TestTela:
    def test_tem_os_dois_seletores(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:transferencia")).content.decode()

        assert 'id="id_tipo_origem"' in conteudo
        assert 'id="id_tipo_destino"' in conteudo
        assert "tom-select" in conteudo
        assert "api/unidades/" in conteudo

    def test_lista_vem_da_origem(self, client, operador_logado):
        """O fetch usa `tipoOrigem`, não o destino."""
        conteudo = client.get(reverse("iscas:transferencia")).content.decode()
        assert "tipo=${this.tipoOrigem}" in conteudo

    def test_javascript_valido(self, client, operador_logado):
        import os
        import re
        import shutil
        import subprocess
        import tempfile

        node = shutil.which("node")
        if not node:
            pytest.skip("node não disponível")

        html = client.get(reverse("iscas:transferencia")).content.decode()
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
