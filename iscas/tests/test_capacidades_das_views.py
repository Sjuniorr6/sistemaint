"""Toda rota do app declara a capacidade que exige (ISC-RN-19).

Dois testes carregam o peso:

- **Cobertura** — varre `urls.py` e exige `capacidade_iscas` em cada callback.
  É a rede que faz uma view nova SEM decorator quebrar a suíte, em vez de nascer
  aberta a qualquer autenticado. Mesmo espírito do `test_arquitetura.py`.
- **Tabela literal** — rota → capacidade esperada, escrita à mão. Duplicar o
  mapa é proposital: o teste precisa discordar quando a produção muda sozinha.
"""
import pytest
from django.urls import reverse

from iscas import urls as iscas_urls
from iscas.enums import Capacidade

pytestmark = pytest.mark.django_db


#: Nome da rota → capacidade que ela exige. A especificação, em tabela.
CAPACIDADE_ESPERADA = {
    "painel": Capacidade.VER_PAINEL,

    "mapa": Capacidade.VER_MAPA,
    "busca_proximidade": Capacidade.VER_MAPA,

    "agente_lista": Capacidade.CADASTRAR_AGENTE,
    # Única tela com CPF completo (ISC-RN-16) — fica no papel mais restrito.
    "agente_detalhe": Capacidade.CADASTRAR_AGENTE,
    "agente_criar": Capacidade.CADASTRAR_AGENTE,
    "agente_editar": Capacidade.CADASTRAR_AGENTE,
    "agente_ajustar_pin": Capacidade.CADASTRAR_AGENTE,
    "agente_desativar": Capacidade.DESATIVAR_CADASTRO,
    "agente_reativar": Capacidade.DESATIVAR_CADASTRO,

    "cliente_lista": Capacidade.CADASTRAR_CLIENTE,
    "cliente_detalhe": Capacidade.CADASTRAR_CLIENTE,
    "cliente_criar": Capacidade.CADASTRAR_CLIENTE,
    "cliente_editar": Capacidade.CADASTRAR_CLIENTE,
    "cliente_ajustar_pin": Capacidade.CADASTRAR_CLIENTE,
    "cliente_desativar": Capacidade.DESATIVAR_CADASTRO,

    "deposito_lista": Capacidade.CADASTRAR_DEPOSITO,
    "deposito_criar": Capacidade.CADASTRAR_DEPOSITO,
    "deposito_editar": Capacidade.CADASTRAR_DEPOSITO,
    "deposito_desativar": Capacidade.DESATIVAR_CADASTRO,

    "modelo_lista": Capacidade.CADASTRAR_MODELO,
    "modelo_criar": Capacidade.CADASTRAR_MODELO,
    "modelo_editar": Capacidade.CADASTRAR_MODELO,
    "modelo_desativar": Capacidade.DESATIVAR_CADASTRO,
    "modelo_reativar": Capacidade.DESATIVAR_CADASTRO,

    "unidade_lista": Capacidade.VER_ESTOQUE,
    "unidade_detalhe": Capacidade.VER_ESTOQUE,
    "painel_saldo": Capacidade.VER_ESTOQUE,
    "retornaveis": Capacidade.VER_ESTOQUE,
    "entrada": Capacidade.MOVIMENTAR_ESTOQUE,
    "transferencia": Capacidade.MOVIMENTAR_ESTOQUE,
    "estornar": Capacidade.MOVIMENTAR_ESTOQUE,
    "baixa": Capacidade.BAIXAR_MANUTENCAO,
    "manutencao": Capacidade.BAIXAR_MANUTENCAO,
    "manutencao_retorno": Capacidade.BAIXAR_MANUTENCAO,
    "registrar_retorno": Capacidade.BAIXAR_MANUTENCAO,

    "solicitacao_lista": Capacidade.VER_SOLICITACAO,
    "solicitacao_detalhe": Capacidade.VER_SOLICITACAO,
    "atribuicao_mensagem": Capacidade.VER_SOLICITACAO,
    "solicitacao_criar": Capacidade.CRIAR_SOLICITACAO,
    "solicitacao_ajustar_pin": Capacidade.CRIAR_SOLICITACAO,
    "solicitacao_atribuir": Capacidade.ATENDER_SOLICITACAO,
    "solicitacao_cancelar": Capacidade.ATENDER_SOLICITACAO,
    "atribuicao_rota": Capacidade.ATENDER_SOLICITACAO,
    "atribuicao_entregar": Capacidade.ATENDER_SOLICITACAO,
    "atribuicao_cancelar": Capacidade.ATENDER_SOLICITACAO,
    "solicitacao_excluir": Capacidade.EXCLUIR_SOLICITACAO,
    "solicitacao_restaurar": Capacidade.EXCLUIR_SOLICITACAO,

    "extrato": Capacidade.VER_ESTOQUE,
    "extrato_csv": Capacidade.VER_ESTOQUE,
    "historico_agente": Capacidade.VER_ESTOQUE,
    "historico_cliente": Capacidade.VER_ESTOQUE,

    "api_agentes": Capacidade.VER_MAPA,
    "api_solicitacoes": Capacidade.VER_MAPA,
    "api_proximidade": Capacidade.VER_MAPA,
    # Popup do marcador: negar deixaria o mapa do comercial quebrado.
    "api_saldo_agente": Capacidade.VER_MAPA,
    "api_unidades_custodia": Capacidade.VER_ESTOQUE,
    "api_cep": Capacidade.CONSULTAR_APOIO,
    "api_geocodificar": Capacidade.CONSULTAR_APOIO,
    "api_geocodificar_reverso": Capacidade.CONSULTAR_APOIO,
    "api_dados_cliente": Capacidade.CONSULTAR_APOIO,

    "auditoria": Capacidade.VER_AUDITORIA,

    "notificacao_lista": Capacidade.CADASTRAR_NOTIFICACAO,
    "notificacao_criar": Capacidade.CADASTRAR_NOTIFICACAO,
    "notificacao_editar": Capacidade.CADASTRAR_NOTIFICACAO,
    "notificacao_desativar": Capacidade.CADASTRAR_NOTIFICACAO,
    "notificacao_reativar": Capacidade.CADASTRAR_NOTIFICACAO,
}


def _rotas_do_app():
    """(nome, callback) de cada rota declarada em iscas/urls.py."""
    return [(p.name, p.callback) for p in iscas_urls.urlpatterns]


class TestCobertura:
    """Nenhuma rota escapa da autorização."""

    # sabotagem: tirar @exige de qualquer view → vermelho
    @pytest.mark.parametrize("nome,callback", _rotas_do_app())
    def test_toda_rota_declara_capacidade(self, nome, callback):
        assert hasattr(callback, "capacidade_iscas"), (
            f"a rota 'iscas:{nome}' não declara capacidade — sem o decorator "
            f"@exige(...) ela nasce aberta a qualquer autenticado."
        )

    def test_a_tabela_do_teste_cobre_todas_as_rotas(self):
        """A especificação não pode ficar para trás do código."""
        declaradas = {nome for nome, _ in _rotas_do_app()}
        faltando = declaradas - set(CAPACIDADE_ESPERADA)

        assert not faltando, f"rotas sem capacidade esperada na tabela: {faltando}"


class TestTabela:
    # sabotagem: trocar a capacidade de `entrada` para BAIXAR_MANUTENCAO → vermelho
    @pytest.mark.parametrize("nome,callback", _rotas_do_app())
    def test_capacidade_bate_com_a_especificacao(self, nome, callback):
        assert callback.capacidade_iscas == CAPACIDADE_ESPERADA[nome]
