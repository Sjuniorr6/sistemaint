"""Auditoria: o log append-only e o middleware que o alimenta (ISC-RN-19).

O teste que carrega mais peso aqui é o do CPF: o middleware lê `request.POST`,
e o formulário de agente traz CPF em texto puro. A garantia é que o registro
guarda a CHAVE (`cpf`) e nunca o VALOR — allowlist, não denylist, para que o
campo sensível que alguém adicionar amanhã não vaze por default.
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import ProtectedError
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES, Capacidade
from iscas.models.operacao import RegistroAuditoria

pytestmark = pytest.mark.django_db


def _registro(**extra):
    dados = {
        "acao": "cliente_criar",
        "capacidade": Capacidade.CADASTRAR_CLIENTE,
        "caminho": "/iscas/clientes/novo/",
        "status_http": 302,
    }
    dados.update(extra)
    return RegistroAuditoria.objects.create(**dados)


class TestModel:
    """É livro, não caderno: escreve uma vez e não se apaga (ISC-RN-17)."""

    def test_persiste(self, operador):
        registro = _registro(autor=operador)
        assert RegistroAuditoria.objects.count() == 1
        assert registro.created_at is not None

    # sabotagem: herdar models.Model em vez de LogModel → vermelho
    def test_nao_aceita_update(self, operador):
        registro = _registro(autor=operador)
        registro.acao = "outra_coisa"
        with pytest.raises(ValueError):
            registro.save()

    def test_nao_aceita_delete(self, operador):
        with pytest.raises(ValueError):
            _registro(autor=operador).delete()

    def test_autor_e_protegido(self, operador):
        _registro(autor=operador)
        with pytest.raises(ProtectedError):
            operador.delete()

    def test_ordena_do_mais_recente(self, operador):
        primeiro = _registro(autor=operador, acao="a")
        segundo = _registro(autor=operador, acao="b")
        assert list(RegistroAuditoria.objects.all()) == [segundo, primeiro]

    def test_campos_guarda_lista_json(self, operador):
        registro = _registro(autor=operador, campos=["nome", "cpf"])
        registro.refresh_from_db()
        assert registro.campos == ["nome", "cpf"]


class TestMiddlewareGrava:
    def test_post_bem_sucedido_gera_registro(self, client, operador_logado, cliente):
        url = reverse("iscas:cliente_editar", args=[cliente.pk])
        client.post(url, {
            "nome": "Cliente Renomeado", "documento": "", "email": "",
            "contato_nome": "", "telefone": "", "comercial_responsavel": "",
            "logradouro": "", "numero": "", "complemento": "", "bairro": "",
            "cidade": "", "uf": "", "cep": "",
        })

        registro = RegistroAuditoria.objects.get()
        assert registro.autor == operador_logado
        assert registro.acao == "cliente_editar"
        assert registro.capacidade == Capacidade.CADASTRAR_CLIENTE
        assert registro.alvo == {"pk": cliente.pk}

    def test_alvo_traz_os_kwargs_da_url(
        self, client, operador_logado, solicitacao_simples
    ):
        url = reverse("iscas:solicitacao_excluir", args=[solicitacao_simples.pk])
        client.post(url, {"motivo": "engano"})

        assert RegistroAuditoria.objects.get().alvo == {"pk": solicitacao_simples.pk}


class TestMiddlewareNaoGrava:
    # sabotagem: remover a guarda de método → vermelho
    def test_get_nao_gera_registro(self, client, operador_logado):
        client.get(reverse("iscas:painel"))
        assert RegistroAuditoria.objects.count() == 0

    # sabotagem: remover a guarda de app_name → vermelho
    def test_post_fora_do_iscas_nao_gera_registro(self, client, operador_logado):
        client.post("/admin/login/", {"username": "x", "password": "y"})
        assert RegistroAuditoria.objects.count() == 0

    def test_anonimo_nao_gera_registro(self, client, cliente):
        client.post(reverse("iscas:cliente_editar", args=[cliente.pk]), {})
        assert RegistroAuditoria.objects.count() == 0

    # sabotagem: remover a guarda de status → vermelho
    def test_post_negado_nao_gera_registro(self, client, comercial_logado, cliente):
        resposta = client.post(reverse("iscas:cliente_desativar", args=[cliente.pk]))

        assert resposta.status_code == 403
        assert RegistroAuditoria.objects.count() == 0


class TestDadoSensivel:
    """A razão de o middleware gravar chaves e nunca valores."""

    CPF = "39053344705"

    def _postar_agente(self, client):
        return client.post(reverse("iscas:agente_criar"), {
            "nome": "Agente Auditado", "cpf": self.CPF, "telefone": "11999998888",
            "logradouro": "Rua Teste", "numero": "10", "complemento": "",
            "bairro": "Centro", "cidade": "Sao Paulo", "uf": "SP", "cep": "01001000",
            "latitude_ajustada": "-23.550520", "longitude_ajustada": "-46.633308",
            "pin_movido": "1",
        })

    # sabotagem: gravar request.POST.dict() em vez das chaves → vermelho
    def test_o_cpf_nao_aparece_em_lugar_nenhum_do_registro(
        self, client, operador_logado
    ):
        self._postar_agente(client)
        registro = RegistroAuditoria.objects.get()

        inteiro = " ".join(
            str(getattr(registro, campo.name))
            for campo in RegistroAuditoria._meta.get_fields()
            if hasattr(registro, campo.name)
        )

        assert self.CPF not in inteiro
        assert "390.533.447-05" not in inteiro
        assert "***.533.447-**" not in inteiro

    def test_a_chave_cpf_aparece_em_campos(self, client, operador_logado):
        """O par do teste acima: sabe-se QUE o CPF foi mexido, não QUAL."""
        self._postar_agente(client)

        assert "cpf" in RegistroAuditoria.objects.get().campos

    def test_o_documento_do_cliente_nao_vaza(self, client, operador_logado):
        documento = "12345678000199"
        client.post(reverse("iscas:cliente_criar"), {
            "nome": "Cliente Auditado", "documento": documento, "email": "",
            "contato_nome": "", "telefone": "", "comercial_responsavel": "",
            "logradouro": "", "numero": "", "complemento": "", "bairro": "",
            "cidade": "", "uf": "", "cep": "",
        })
        registro = RegistroAuditoria.objects.get()

        assert documento not in str(registro.campos)
        assert documento not in str(registro.alvo)
        assert "documento" in registro.campos

    def test_csrf_nunca_aparece(self, client, operador_logado, cliente):
        client.post(reverse("iscas:cliente_editar", args=[cliente.pk]), {"nome": "X"})

        assert "csrfmiddlewaretoken" not in RegistroAuditoria.objects.get().campos


class TestResiliencia:
    def test_falha_ao_gravar_nao_derruba_a_requisicao(
        self, client, operador_logado, cliente, monkeypatch
    ):
        """Perder o registro é ruim; perder a operação do usuário é pior.

        Compara com a resposta do MESMO POST sem sabotagem: afirmar um status
        fixo esconderia o caso em que os dois caminhos passam a dar erro.
        """
        url = reverse("iscas:cliente_editar", args=[cliente.pk])
        dados = {
            "nome": "Segue Vivo", "documento": "", "email": "",
            "contato_nome": "", "telefone": "", "comercial_responsavel": "",
            "logradouro": "", "numero": "", "complemento": "", "bairro": "",
            "cidade": "", "uf": "", "cep": "",
        }
        esperado = client.post(url, dados).status_code
        assert esperado < 500

        def explodir(*args, **kwargs):
            raise RuntimeError("banco travado")

        monkeypatch.setattr(RegistroAuditoria.objects, "create", explodir)

        assert client.post(url, dados).status_code == esperado


class TestTela:
    """A tela é restrita ao grupo total — é ela que expõe o que os outros fazem."""

    def test_operador_total_ve(self, client, operador_logado):
        assert client.get(reverse("iscas:auditoria")).status_code == 200

    # sabotagem: dar VER_AUDITORIA a outro papel → vermelho
    @pytest.mark.parametrize("papel", ["operador_fast_logado", "comercial_logado"])
    def test_papeis_restritos_levam_403(self, request, client, papel):
        request.getfixturevalue(papel)
        assert client.get(reverse("iscas:auditoria")).status_code == 403

    def test_anonimo_vai_para_o_login(self, client):
        assert client.get(reverse("iscas:auditoria")).status_code == 302

    def test_lista_o_que_os_outros_papeis_fizeram(
        self, client, comercial_logado, cliente, operador, django_user_model
    ):
        """O caso de uso da tela: o gestor vê a ação do comercial."""
        client.post(reverse("iscas:cliente_criar"), {
            "nome": "Cliente do Comercial", "documento": "", "email": "",
            "contato_nome": "", "telefone": "", "comercial_responsavel": "",
            "logradouro": "", "numero": "", "complemento": "", "bairro": "",
            "cidade": "", "uf": "", "cep": "",
        })
        client.logout()

        grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
        operador.groups.add(grupo)
        client.force_login(operador)
        conteudo = client.get(reverse("iscas:auditoria")).content.decode()

        assert "comercial" in conteudo
        assert "cliente_criar" in conteudo

    def test_filtro_por_autor_restringe(self, client, operador_logado, cliente):
        """Afere o CONJUNTO paginado, não o HTML: os selects de filtro citam
        todas as ações existentes, então busca em página inteira sempre casa."""
        outro = get_user_model().objects.create_user(username="outro", password="x")
        _registro(autor=operador_logado, acao="acao_do_operador")
        _registro(autor=outro, acao="acao_do_outro")

        resposta = client.get(reverse("iscas:auditoria"), {"autor": outro.pk})

        assert [r.acao for r in resposta.context["pagina"]] == ["acao_do_outro"]

    def test_filtro_por_capacidade_restringe(self, client, operador_logado):
        _registro(autor=operador_logado, acao="do_cadastro",
                  capacidade=Capacidade.CADASTRAR_CLIENTE)
        _registro(autor=operador_logado, acao="do_estoque",
                  capacidade=Capacidade.MOVIMENTAR_ESTOQUE)

        resposta = client.get(
            reverse("iscas:auditoria"), {"capacidade": Capacidade.MOVIMENTAR_ESTOQUE}
        )

        assert [r.acao for r in resposta.context["pagina"]] == ["do_estoque"]

    def test_paginacao_preserva_o_filtro(self, client, operador_logado):
        """Sem isso, ir para a página 2 devolve a lista inteira."""
        for i in range(55):
            _registro(autor=operador_logado, capacidade=Capacidade.MOVIMENTAR_ESTOQUE)

        resposta = client.get(
            reverse("iscas:auditoria"), {"capacidade": Capacidade.MOVIMENTAR_ESTOQUE}
        )
        conteudo = resposta.content.decode()

        # Afere o LINK emitido, não o resultado da página 2: a view filtra pela
        # querystring, então pedir a página 2 já filtrada passaria mesmo com o
        # filtro sumindo do link.
        assert resposta.context["pagina"].paginator.num_pages == 2
        assert "?capacidade=MOVIMENTAR_ESTOQUE&page=2" in conteudo

    def test_contagem_de_queries_nao_cresce_com_os_registros(
        self, client, operador_logado
    ):
        """select_related no autor: a tabela nao pode fazer 1 query por linha.

        Autores DIFERENTES entre as duas medicoes de proposito — com um autor
        so, prefetch e nao-prefetch custam igual e o teste passaria sem o
        select_related.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        url = reverse("iscas:auditoria")
        for _ in range(3):
            _registro(autor=operador_logado)
        with CaptureQueriesContext(connection) as poucas:
            client.get(url)

        for i in range(30):
            outro = get_user_model().objects.create_user(
                username=f"autor-{i}", password="x"
            )
            _registro(autor=outro)
        with CaptureQueriesContext(connection) as muitas:
            client.get(url)

        assert len(muitas) == len(poucas)
