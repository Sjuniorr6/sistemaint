"""Formulário de entrada de estoque, simplificado.

A tela oferecia três modos de informar as unidades (lista, faixa sequencial,
geração interna) com os campos de todos eles visíveis ao mesmo tempo, e dois
selects de destino em que só um podia ser preenchido. Ficou: colagem de
identificadores e um seletor que revela o destino certo.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES
from iscas.forms import EntradaLoteForm
from iscas.models.custodia import Unidade

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


def _dados(modelo, **extra):
    base = {
        "modelo": modelo.pk,
        "identificadores": "A001\nA002\nA003",
        "tipo_destino": "DEPOSITO",
        "destino_deposito": "",
        "destino_agente": "",
        "nota_fiscal": "",
        "lote": "",
        "ocorrido_em": "",
    }
    base.update(extra)
    return base


class TestCamposRemovidos:
    """Os campos que saíram não podem voltar por descuido."""

    @pytest.mark.parametrize("campo", ["modo", "prefixo", "numero_inicial"])
    def test_campo_nao_existe_mais(self, campo):
        assert campo not in EntradaLoteForm().fields

    def test_tela_nao_mostra_os_campos(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:entrada")).content.decode()

        assert "Como informar as unidades" not in conteudo
        assert 'id="id_prefixo"' not in conteudo
        assert 'id="id_numero_inicial"' not in conteudo

    def test_identificadores_agora_e_obrigatorio(self, modelo_descartavel, deposito):
        """Sem os outros modos, não há caminho alternativo para informar unidades."""
        form = EntradaLoteForm(
            _dados(modelo_descartavel, identificadores="", destino_deposito=deposito.pk)
        )
        assert not form.is_valid()
        assert "identificadores" in form.errors


class TestSeletorDeDestino:
    def test_destino_deposito(self, modelo_descartavel, deposito):
        form = EntradaLoteForm(
            _dados(modelo_descartavel, tipo_destino="DEPOSITO",
                   destino_deposito=deposito.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["destino"] == deposito

    def test_destino_agente(self, modelo_descartavel, agente):
        form = EntradaLoteForm(
            _dados(modelo_descartavel, tipo_destino="AGENTE",
                   destino_agente=agente.pk)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["destino"] == agente

    def test_deposito_escolhido_sem_selecionar_qual(self, modelo_descartavel):
        form = EntradaLoteForm(_dados(modelo_descartavel, tipo_destino="DEPOSITO"))

        assert not form.is_valid()
        assert "destino_deposito" in form.errors

    def test_agente_escolhido_sem_selecionar_qual(self, modelo_descartavel):
        form = EntradaLoteForm(_dados(modelo_descartavel, tipo_destino="AGENTE"))

        assert not form.is_valid()
        assert "destino_agente" in form.errors

    def test_campo_do_outro_tipo_e_ignorado(
        self, modelo_descartavel, deposito, agente
    ):
        """Escolhendo AGENTE, um depósito preenchido não interfere.

        A tela esconde o campo, mas um valor remanescente do POST não pode
        mudar o destino escolhido.
        """
        form = EntradaLoteForm(
            _dados(
                modelo_descartavel, tipo_destino="AGENTE",
                destino_agente=agente.pk, destino_deposito=deposito.pk,
            )
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["destino"] == agente


class TestIdentificadores:
    def test_um_por_linha(self, modelo_descartavel, deposito):
        form = EntradaLoteForm(
            _dados(modelo_descartavel, destino_deposito=deposito.pk,
                   identificadores="X1\nX2\nX3")
        )
        assert form.is_valid()
        assert form.cleaned_data["lista_identificadores"] == ["X1", "X2", "X3"]

    def test_id_puro_sem_prefixo(self, modelo_descartavel, deposito):
        """Números crus são identificadores válidos — nada é acrescentado."""
        form = EntradaLoteForm(
            _dados(modelo_descartavel, destino_deposito=deposito.pk,
                   identificadores="1001\n1002")
        )
        assert form.is_valid()
        assert form.cleaned_data["lista_identificadores"] == ["1001", "1002"]

    def test_quantidade_vem_da_lista(self, modelo_descartavel, deposito):
        form = EntradaLoteForm(
            _dados(modelo_descartavel, destino_deposito=deposito.pk,
                   identificadores="A\nB\nC\nD")
        )
        assert form.is_valid()
        assert form.cleaned_data["quantidade"] == 4

    def test_nunca_gera_identificador_interno(self, modelo_descartavel, deposito):
        form = EntradaLoteForm(
            _dados(modelo_descartavel, destino_deposito=deposito.pk)
        )
        assert form.is_valid()
        assert form.cleaned_data["gerar_internos"] is False


class TestPelaTela:
    def test_entrada_no_deposito(
        self, client, operador_logado, modelo_descartavel, deposito
    ):
        resposta = client.post(
            reverse("iscas:entrada"),
            _dados(modelo_descartavel, tipo_destino="DEPOSITO",
                   destino_deposito=deposito.pk, nota_fiscal="NF-1"),
        )
        assert resposta.status_code == 302

        unidades = Unidade.objects.filter(identificador__in=["A001", "A002", "A003"])
        assert unidades.count() == 3
        assert all(not u.identificador_gerado for u in unidades)

    def test_entrada_no_agente(
        self, client, operador_logado, modelo_descartavel, agente
    ):
        from iscas.services.saldo import saldo_em_custodia

        client.post(
            reverse("iscas:entrada"),
            _dados(modelo_descartavel, tipo_destino="AGENTE",
                   destino_agente=agente.pk),
        )
        assert saldo_em_custodia(agente, modelo=modelo_descartavel) == 3

    def test_identificador_repetido_e_recusado(
        self, client, operador_logado, modelo_descartavel, deposito,
        unidades_no_deposito,
    ):
        """`D001` já existe pela fixture."""
        client.post(
            reverse("iscas:entrada"),
            _dados(modelo_descartavel, destino_deposito=deposito.pk,
                   identificadores="D001"),
        )
        assert Unidade.objects.filter(identificador="D001").count() == 1

    def test_tela_tem_o_seletor_e_o_javascript(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:entrada")).content.decode()

        assert 'id="id_tipo_destino"' in conteudo
        assert "entradaEstoque" in conteudo
        assert "x-show=\"tipo === 'DEPOSITO'\"" in conteudo
        assert "x-show=\"tipo === 'AGENTE'\"" in conteudo

    def test_javascript_da_tela_e_valido(self, client, operador_logado):
        import os
        import re
        import shutil
        import subprocess
        import tempfile

        node = shutil.which("node")
        if not node:
            pytest.skip("node não disponível")

        html = client.get(reverse("iscas:entrada")).content.decode()
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
