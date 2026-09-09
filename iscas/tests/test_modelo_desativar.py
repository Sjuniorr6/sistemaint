"""Soft-delete de modelo: sai do catálogo, o estoque existente continua (ISC-RN-20)."""
import pytest
from django.contrib.auth.models import Group

from iscas.enums import GRUPO_OPERADORES
from iscas.forms.custodia import EntradaLoteForm
from iscas.models.cadastro import ModeloEquipamento
from iscas.services import cadastro as cadastro_service
from iscas.services import entrada as entrada_service
from iscas.services.exceptions import ModeloDesativado

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


def test_desativado_some_do_catalogo_mas_nao_do_banco(modelo_descartavel):
    cadastro_service.desativar_modelo(modelo_descartavel)

    assert not ModeloEquipamento.objects.filter(pk=modelo_descartavel.pk).exists()
    # Soft-delete: o registro continua, para o histórico das unidades dele.
    assert ModeloEquipamento.todos.filter(pk=modelo_descartavel.pk).exists()


def test_entrada_de_unidade_nova_e_recusada_pelo_service(
    modelo_descartavel, deposito, operador
):
    """A guarda é do service, não só do select: POST com o id ainda chegaria aqui."""
    # sabotagem: trocar `if not modelo.is_active` por `if False` em
    # services/entrada.py -> vermelho
    cadastro_service.desativar_modelo(modelo_descartavel)

    with pytest.raises(ModeloDesativado):
        entrada_service.registrar_entrada(
            modelo=modelo_descartavel,
            identificadores=["X-001"],
            destino=deposito,
            autor=operador,
            nota_fiscal="NF-9",
        )


def test_modelo_desativado_sai_do_select_de_entrada(modelo_descartavel):
    assert modelo_descartavel in EntradaLoteForm().fields["modelo"].queryset

    cadastro_service.desativar_modelo(modelo_descartavel)

    assert modelo_descartavel not in EntradaLoteForm().fields["modelo"].queryset


def test_desativar_com_estoque_nao_e_bloqueado(
    modelo_descartavel, deposito, unidades_no_deposito
):
    """A diferença deliberada em relação a agente e depósito.

    Aqueles levantam `AgenteComSaldo`/`DepositoComSaldo` porque desativá-los
    esconderia estoque que está fisicamente com alguém. Desativar um modelo não
    move nada de lugar, então saldo não bloqueia — é o que permite descontinuar
    um modelo cujas unidades ainda rodam na operação.
    """
    from iscas.services.saldo import saldo_em_custodia

    assert saldo_em_custodia(deposito) == 10

    cadastro_service.desativar_modelo(modelo_descartavel)

    modelo_descartavel.refresh_from_db()
    assert modelo_descartavel.is_active is False


def test_unidades_do_modelo_desativado_continuam_movimentaveis(
    modelo_descartavel, deposito, agente, unidades_no_deposito, operador
):
    """O que sustenta "só para a entrada": transferir uma unidade segue valendo.

    Se a desativação tivesse virado bloqueio de movimentação, esta transferência
    levantaria exceção — é isso que separa "tirei do catálogo" de "congelei o
    estoque".
    """
    from iscas.services import transferencia as transferencia_service

    transferencia_service.transferir(
        unidades=unidades_no_deposito[:3],
        origem=deposito,
        destino=agente,
        autor=operador,
    )

    cadastro_service.desativar_modelo(modelo_descartavel)

    transferencia_service.transferir(
        unidades=unidades_no_deposito[3:5],
        origem=deposito,
        destino=agente,
        autor=operador,
    )

    from iscas.services.saldo import saldo_em_custodia

    assert saldo_em_custodia(agente) == 5


def test_reativar_devolve_o_modelo_ao_catalogo(modelo_descartavel):
    cadastro_service.desativar_modelo(modelo_descartavel)
    cadastro_service.reativar_modelo(modelo_descartavel)

    assert ModeloEquipamento.objects.filter(pk=modelo_descartavel.pk).exists()


class TestTelaDeModelos:
    def test_lista_esconde_desativados_e_a_lixeira_os_mostra(
        self, client, operador_logado, modelo_descartavel, modelo_retornavel
    ):
        # sabotagem: trocar `ModeloEquipamento.objects` por `.todos` no
        # modelo_lista -> vermelho
        cadastro_service.desativar_modelo(modelo_descartavel)

        catalogo = client.get("/iscas/modelos/")
        listados = [linha["modelo"] for linha in catalogo.context["linhas"]]
        assert listados == [modelo_retornavel]

        lixeira = client.get("/iscas/modelos/", {"desativados": "1"})
        assert [linha["modelo"] for linha in lixeira.context["linhas"]] == [
            modelo_descartavel
        ]

    def test_botoes_de_desativar_e_reativar_estao_na_tela(
        self, client, operador_logado, modelo_descartavel
    ):
        """O recurso só existe se houver como acioná-lo: a view já existia sem botão."""
        catalogo = client.get("/iscas/modelos/").content.decode()
        assert f"/iscas/modelos/{modelo_descartavel.pk}/desativar/" in catalogo

        cadastro_service.desativar_modelo(modelo_descartavel)
        lixeira = client.get("/iscas/modelos/", {"desativados": "1"}).content.decode()
        assert f"/iscas/modelos/{modelo_descartavel.pk}/reativar/" in lixeira

    def test_post_desativa_e_reativa(
        self, client, operador_logado, modelo_descartavel
    ):
        client.post(f"/iscas/modelos/{modelo_descartavel.pk}/desativar/")
        modelo_descartavel.refresh_from_db()
        assert modelo_descartavel.is_active is False

        client.post(f"/iscas/modelos/{modelo_descartavel.pk}/reativar/")
        modelo_descartavel.refresh_from_db()
        assert modelo_descartavel.is_active is True
