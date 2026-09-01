"""Dados de contato e entrega na abertura da solicitação.

Escolher o cliente preenche CNPJ, e-mail, telefone, comercial responsável e
endereço. Os valores são editáveis e ficam gravados NA SOLICITAÇÃO — o cadastro
do cliente não é tocado. É o que permite entregar numa obra sem perder o
endereço principal, e mantém o histórico honesto: cada solicitação registra
para onde a entrega foi de fato.
"""
import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES
from iscas.models.operacao import Solicitacao
from iscas.services import solicitacao as solicitacao_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


@pytest.fixture
def cliente_completo(cliente):
    """Cliente com todos os campos de contato preenchidos."""
    cliente.documento = "11222333000181"
    cliente.email = "compras@transportes.com.br"
    cliente.contato_nome = "Ana Souza"
    cliente.telefone = "1133334444"
    cliente.comercial_responsavel = "Carlos Vendas"
    cliente.save()
    return cliente


def _post(cliente, modelo, **extra):
    dados = {
        "cliente": cliente.pk,
        "documento": cliente.documento,
        "email": cliente.email,
        "contato_nome": cliente.contato_nome,
        "telefone": cliente.telefone,
        "comercial_responsavel": cliente.comercial_responsavel,
        "entrega_logradouro": cliente.logradouro,
        "entrega_numero": cliente.numero,
        "entrega_complemento": cliente.complemento,
        "entrega_bairro": cliente.bairro,
        "entrega_cidade": cliente.cidade,
        "entrega_uf": cliente.uf,
        "entrega_cep": cliente.cep,
        "prazo_desejado": "",
        "observacao": "",
        f"quantidade_{modelo.pk}": "5",
    }
    dados.update(extra)
    return dados


class TestEndpointDadosDoCliente:
    def test_devolve_contato_e_endereco(
        self, client, operador_logado, cliente_completo
    ):
        resposta = client.get(
            reverse("iscas:api_dados_cliente", args=[cliente_completo.pk])
        )
        dados = json.loads(resposta.content)

        assert dados["nome"] == cliente_completo.nome_razao_social
        assert dados["documento"] == "11222333000181"
        assert dados["email"] == "compras@transportes.com.br"
        assert dados["contato_nome"] == "Ana Souza"
        assert dados["telefone"] == "1133334444"
        assert dados["comercial_responsavel"] == "Carlos Vendas"
        assert dados["endereco"]["logradouro"] == cliente_completo.logradouro
        assert dados["endereco"]["cidade"] == cliente_completo.cidade

    def test_sinaliza_coordenada(self, client, operador_logado, cliente_completo):
        dados = json.loads(
            client.get(
                reverse("iscas:api_dados_cliente", args=[cliente_completo.pk])
            ).content
        )
        assert dados["tem_coordenada"] is True

    def test_exige_operador(self, client, cliente_completo):
        resposta = client.get(
            reverse("iscas:api_dados_cliente", args=[cliente_completo.pk])
        )
        assert resposta.status_code == 302

    def test_cliente_inexistente(self, client, operador_logado):
        assert (
            client.get(reverse("iscas:api_dados_cliente", args=[99999])).status_code
            == 404
        )


class TestCopiaDoCadastro:
    """`dados_de_entrega` resolve o que veio da tela contra o cadastro."""

    def test_copia_tudo_quando_nada_informado(self, cliente_completo):
        resolvidos = solicitacao_service.dados_de_entrega(cliente_completo)

        assert resolvidos["documento"] == "11222333000181"
        assert resolvidos["telefone"] == "1133334444"
        assert resolvidos["comercial_responsavel"] == "Carlos Vendas"
        assert resolvidos["entrega_logradouro"] == cliente_completo.logradouro
        assert resolvidos["entrega_cidade"] == cliente_completo.cidade

    def test_informado_vence_o_cadastro(self, cliente_completo):
        resolvidos = solicitacao_service.dados_de_entrega(
            cliente_completo,
            {"entrega_logradouro": "Rua da Obra", "telefone": "11999998888"},
        )

        assert resolvidos["entrega_logradouro"] == "Rua da Obra"
        assert resolvidos["telefone"] == "11999998888"
        # O que não veio continua vindo do cadastro.
        assert resolvidos["documento"] == "11222333000181"

    def test_vazio_cai_para_o_cadastro(self, cliente_completo):
        """String vazia não é "apagar" — é "não informei"."""
        resolvidos = solicitacao_service.dados_de_entrega(
            cliente_completo, {"telefone": ""}
        )
        assert resolvidos["telefone"] == "1133334444"

    def test_nome_do_cliente_nao_e_copiado(self, cliente_completo):
        """A identidade vem sempre da FK — sem duas versões do mesmo nome."""
        resolvidos = solicitacao_service.dados_de_entrega(cliente_completo)
        assert "nome" not in resolvidos
        assert "nome_razao_social" not in resolvidos


class TestAberturaPelaTela:
    def test_grava_os_dados_do_cadastro(
        self, client, operador_logado, cliente_completo, modelo_descartavel
    ):
        resposta = client.post(
            reverse("iscas:solicitacao_criar"),
            _post(cliente_completo, modelo_descartavel),
        )
        assert resposta.status_code == 302

        solicitacao = Solicitacao.objects.latest("id")
        assert solicitacao.documento == "11222333000181"
        assert solicitacao.email == "compras@transportes.com.br"
        assert solicitacao.telefone == "1133334444"
        assert solicitacao.comercial_responsavel == "Carlos Vendas"
        assert solicitacao.entrega_cidade == cliente_completo.cidade

    def test_endereco_editado_vale_so_para_a_solicitacao(
        self, client, operador_logado, cliente_completo, modelo_descartavel
    ):
        """O caso da obra: entrega em outro lugar, cadastro intocado."""
        logradouro_original = cliente_completo.logradouro

        client.post(
            reverse("iscas:solicitacao_criar"),
            _post(
                cliente_completo, modelo_descartavel,
                entrega_logradouro="Rua da Obra",
                entrega_numero="500",
                entrega_bairro="Distrito Industrial",
            ),
        )

        solicitacao = Solicitacao.objects.latest("id")
        cliente_completo.refresh_from_db()

        assert solicitacao.entrega_logradouro == "Rua da Obra"
        assert cliente_completo.logradouro == logradouro_original

    def test_contato_editado_nao_altera_o_cadastro(
        self, client, operador_logado, cliente_completo, modelo_descartavel
    ):
        client.post(
            reverse("iscas:solicitacao_criar"),
            _post(
                cliente_completo, modelo_descartavel,
                telefone="11912345678", contato_nome="Pedro (obra)",
            ),
        )

        solicitacao = Solicitacao.objects.latest("id")
        cliente_completo.refresh_from_db()

        assert solicitacao.telefone == "11912345678"
        assert solicitacao.contato_nome == "Pedro (obra)"
        assert cliente_completo.telefone == "1133334444"
        assert cliente_completo.contato_nome == "Ana Souza"

    def test_endereco_de_entrega_e_obrigatorio(
        self, client, operador_logado, cliente_completo, modelo_descartavel
    ):
        """Sem endereço o agente não sabe onde entregar."""
        resposta = client.post(
            reverse("iscas:solicitacao_criar"),
            _post(
                cliente_completo, modelo_descartavel,
                entrega_logradouro="", entrega_cidade="", entrega_uf="",
            ),
        )
        assert resposta.status_code == 200
        assert not Solicitacao.objects.exists()


class TestEnderecoDeEntrega:
    def test_monta_a_linha_completa(
        self, cliente_completo, modelo_descartavel, operador
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente_completo,
            itens=[(modelo_descartavel, 2)],
            autor=operador,
            entrega_logradouro="Rua da Obra",
            entrega_numero="500",
            entrega_bairro="Distrito",
            entrega_cidade="Campinas",
            entrega_uf="SP",
            entrega_cep="13000-000",
        )
        endereco = solicitacao.endereco_entrega

        assert "Rua da Obra" in endereco
        assert "500" in endereco
        assert "Campinas - SP" in endereco

    def test_sinaliza_endereco_diferente(
        self, cliente_completo, modelo_descartavel, operador
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente_completo,
            itens=[(modelo_descartavel, 2)],
            autor=operador,
            entrega_logradouro="Rua da Obra",
            entrega_numero="500",
        )
        assert solicitacao.entrega_em_outro_endereco

    def test_mesmo_endereco_nao_sinaliza(
        self, cliente_completo, modelo_descartavel, operador
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente_completo, itens=[(modelo_descartavel, 2)], autor=operador
        )
        assert not solicitacao.entrega_em_outro_endereco

    def test_solicitacao_antiga_cai_para_o_cadastro(
        self, cliente_completo, modelo_descartavel, operador
    ):
        """Abertas antes destes campos existirem não podem ficar sem endereço."""
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente_completo, itens=[(modelo_descartavel, 1)], autor=operador
        )
        Solicitacao.objects.filter(pk=solicitacao.pk).update(entrega_logradouro="")
        solicitacao.refresh_from_db()

        assert solicitacao.endereco_entrega == cliente_completo.endereco_completo
        assert not solicitacao.entrega_em_outro_endereco


class TestMensagemDeWhatsApp:
    def test_usa_o_endereco_de_entrega(
        self, cliente_completo, agente, unidades_com_agente,
        modelo_descartavel, operador,
    ):
        """O agente precisa ir para onde a entrega é, não para o cadastro."""
        from iscas.services import mensagem as mensagem_service

        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente_completo,
            itens=[(modelo_descartavel, 2)],
            autor=operador,
            entrega_logradouro="Rua da Obra",
            entrega_numero="500",
            entrega_cidade="Campinas",
            entrega_uf="SP",
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        texto = mensagem_service.montar_texto_atribuicao(atribuicao)

        assert "Rua da Obra" in texto
        assert cliente_completo.logradouro not in texto

    def test_usa_o_contato_da_solicitacao(
        self, cliente_completo, agente, unidades_com_agente,
        modelo_descartavel, operador,
    ):
        from iscas.services import mensagem as mensagem_service

        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente_completo,
            itens=[(modelo_descartavel, 2)],
            autor=operador,
            contato_nome="Pedro (obra)",
            telefone="11912345678",
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        texto = mensagem_service.montar_texto_atribuicao(atribuicao)

        assert "Pedro (obra)" in texto
        assert "11912345678" in texto


class TestTelas:
    def test_form_tem_os_campos_pedidos(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:solicitacao_criar")).content.decode()

        for campo in [
            "id_cliente", "id_documento", "id_email", "id_telefone",
            "id_comercial_responsavel", "id_entrega_logradouro",
            "id_entrega_cidade", "id_entrega_uf",
        ]:
            assert campo in conteudo, campo

    def test_form_carrega_dados_do_cliente(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:solicitacao_criar")).content.decode()

        assert "carregarCliente" in conteudo
        assert "/iscas/api/cliente/" in conteudo

    def test_detalhe_mostra_os_dados_da_entrega(
        self, client, operador_logado, cliente_completo, modelo_descartavel, operador
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente_completo,
            itens=[(modelo_descartavel, 2)],
            autor=operador,
            entrega_logradouro="Rua da Obra",
            entrega_numero="500",
        )
        conteudo = client.get(
            reverse("iscas:solicitacao_detalhe", args=[solicitacao.pk])
        ).content.decode()

        assert "Rua da Obra" in conteudo
        assert "Carlos Vendas" in conteudo
        assert "endereço diferente do cadastro" in conteudo

    def test_cadastro_de_cliente_tem_comercial(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:cliente_criar")).content.decode()
        assert "id_comercial_responsavel" in conteudo

    def test_javascript_valido(self, client, operador_logado):
        import os
        import re
        import shutil
        import subprocess
        import tempfile

        node = shutil.which("node")
        if not node:
            pytest.skip("node não disponível")

        html = client.get(reverse("iscas:solicitacao_criar")).content.decode()
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
