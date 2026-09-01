"""Testes que sustentam as decisões arquiteturais do app.

Dois testes carregam peso desproporcional:

- **Ponto de escrita único** — verifica que nenhum módulo fora de
  `services/custodia.py` escreve no livro-razão. É o que torna o gargalo do
  ISC-ADR-02 uma garantia, e não uma convenção que alguém esquece.
- **Reconciliação** — reconstrói os ponteiros de projeção a partir do livro e
  compara com o que está gravado. É o teste que sustenta o desvio consciente do
  ISC-ADR-04 ("derivado nunca é campo"): o ponteiro é cache, e cache precisa
  ser demonstravelmente reconstruível.
"""
import ast
import pathlib

import pytest

from iscas.enums import MotivoBaixa, TipoCustodia, TipoMovimentacao
from iscas.models.custodia import Movimentacao, MovimentacaoUnidade, Unidade
from iscas.services import baixa as baixa_service
from iscas.services import custodia as custodia_service
from iscas.services import solicitacao as solicitacao_service
from iscas.services import transferencia as transferencia_service

APP_DIR = pathlib.Path(__file__).resolve().parent.parent

#: Só estes módulos podem escrever no livro-razão. `models/` declara os models;
#: `services/custodia.py` é o ponto de escrita; migrations manipulam schema e
#: dados por natureza; os testes precisam poder montar cenários.
_AUTORIZADOS_A_ESCREVER = {
    "services/custodia.py",
    "models/custodia.py",
    "models/__init__.py",
}

_MODELS_DO_LIVRO = {"Movimentacao", "MovimentacaoUnidade"}

#: Chamadas que criam ou alteram registros.
_METODOS_DE_ESCRITA = {
    "create", "bulk_create", "get_or_create", "update_or_create",
    "update", "bulk_update", "delete", "save",
}


def _modulos_do_app():
    for caminho in APP_DIR.rglob("*.py"):
        relativo = caminho.relative_to(APP_DIR).as_posix()
        if relativo.startswith(("migrations/", "tests/")):
            continue
        yield relativo, caminho


class TestPontoDeEscritaUnico:
    """ISC-ADR-02: 100% das escritas do livro passam por um lugar só."""

    def test_nenhum_modulo_externo_escreve_no_livro(self):
        infratores = []

        for relativo, caminho in _modulos_do_app():
            if relativo in _AUTORIZADOS_A_ESCREVER:
                continue

            arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))

            for no in ast.walk(arvore):
                if not isinstance(no, ast.Call):
                    continue
                funcao = no.func
                if not isinstance(funcao, ast.Attribute):
                    continue
                if funcao.attr not in _METODOS_DE_ESCRITA:
                    continue

                # Procura `Movimentacao...<metodo>()` na cadeia de atributos.
                base = funcao.value
                while isinstance(base, (ast.Attribute, ast.Call)):
                    base = base.func if isinstance(base, ast.Call) else base.value
                if isinstance(base, ast.Name) and base.id in _MODELS_DO_LIVRO:
                    infratores.append(f"{relativo}:{no.lineno} → {base.id}.{funcao.attr}()")

        assert not infratores, (
            "Escrita no livro-razão fora de services/custodia.py "
            "(ISC-ADR-02):\n  " + "\n  ".join(infratores)
        )

    def test_registrar_movimentacao_e_a_unica_porta(self):
        """Todo service que move estoque chama o ponto único."""
        import inspect

        from iscas.services import entrada, estorno, retorno

        for modulo in (entrada, transferencia_service, baixa_service, retorno, estorno):
            fonte = inspect.getsource(modulo)
            assert "registrar_movimentacao" in fonte, (
                f"{modulo.__name__} move estoque sem passar pelo ponto de escrita único."
            )


@pytest.mark.django_db
class TestReconciliacao:
    """ISC-ADR-04: os ponteiros são reconstrutíveis a partir do livro."""

    def _reconstruir(self):
        """Recalcula (custodia, desde, ultima_mov) de cada unidade pelo log.

        A custódia atual de uma unidade é o destino do último lançamento dela —
        exatamente o que o ponteiro deveria estar guardando.
        """
        reconstruido = {}
        linhas = (
            MovimentacaoUnidade.objects.select_related("movimentacao")
            .order_by("movimentacao__ocorrido_em", "movimentacao_id")
        )
        for linha in linhas:
            movimentacao = linha.movimentacao
            reconstruido[linha.unidade_id] = (
                movimentacao.destino_id,
                movimentacao.ocorrido_em,
                movimentacao.pk,
            )
        return reconstruido

    def _comparar(self):
        esperado = self._reconstruir()
        divergencias = []
        for unidade in Unidade.objects.all():
            atual = (
                unidade.custodia_atual_id,
                unidade.custodia_desde,
                unidade.ultima_movimentacao_id,
            )
            if unidade.pk in esperado and esperado[unidade.pk] != atual:
                divergencias.append(
                    f"{unidade.identificador}: gravado={atual} "
                    f"reconstruído={esperado[unidade.pk]}"
                )
        return divergencias

    def test_ponteiros_batem_apos_jornada_completa(
        self, deposito, agente, agente2, cliente, modelo_descartavel,
        modelo_retornavel, operador,
    ):
        """A jornada do PRD inteira, ponto a ponto, e então reconcilia."""
        from iscas.services import entrada as entrada_service
        from iscas.services import estorno as estorno_service
        from iscas.services import retorno as retorno_service

        # 1. Abastecimento
        entrada_service.registrar_entrada(
            modelo=modelo_descartavel,
            identificadores=[f"J{i:03d}" for i in range(1, 21)],
            destino=deposito, autor=operador, nota_fiscal="NF-100",
        )
        entrada_service.registrar_entrada(
            modelo=modelo_retornavel,
            identificadores=[f"K{i:03d}" for i in range(1, 11)],
            destino=deposito, autor=operador,
        )
        transferencia_service.transferir(
            origem=deposito, destino=agente, modelo=modelo_descartavel,
            quantidade=12, autor=operador,
        )
        transferencia_service.transferir(
            origem=deposito, destino=agente2, modelo=modelo_descartavel,
            quantidade=8, autor=operador,
        )
        transferencia_service.transferir(
            origem=deposito, destino=agente, modelo=modelo_retornavel,
            quantidade=5, autor=operador,
        )

        # 2-4. Solicitação dividida entre dois agentes
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 20)], autor=operador
        )
        a1 = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 12)], autor=operador,
        )
        a2 = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente2,
            itens=[(modelo_descartavel, 8)], autor=operador,
        )

        # 6-7. Rota e entrega
        solicitacao_service.marcar_em_rota(atribuicao=a1, autor=operador)
        solicitacao_service.confirmar_entrega(
            atribuicao=a1, autor=operador, recebido_por="Recepção"
        )
        solicitacao_service.confirmar_entrega(
            atribuicao=a2, autor=operador, recebido_por="Recepção"
        )

        # 9. Retornáveis: entrega e retorno
        solicitacao_ret = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_retornavel, 5)], autor=operador
        )
        a3 = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao_ret, agente=agente,
            itens=[(modelo_retornavel, 5)], autor=operador,
        )
        solicitacao_service.confirmar_entrega(atribuicao=a3, autor=operador)
        retornadas = list(retorno_service.retornaveis_em_posse(cliente=cliente)[:3])
        retorno_service.registrar_retorno(
            unidades=retornadas, destino=deposito, autor=operador
        )

        # Baixa, manutenção e estorno — os caminhos menos trilhados.
        baixa_service.dar_baixa(
            origem=deposito, motivo=MotivoBaixa.AVARIA, justificativa="Trincada",
            autor=operador, modelo=modelo_retornavel, quantidade=1,
        )
        envio = transferencia_service.enviar_para_manutencao(
            origem=deposito, modelo=modelo_retornavel, quantidade=1, autor=operador
        )
        transferencia_service.retornar_de_manutencao(
            unidades=[linha.unidade for linha in envio.linhas.all()],
            destino=deposito, autor=operador,
        )
        transferido = transferencia_service.transferir(
            origem=deposito, destino=agente2, modelo=modelo_retornavel,
            quantidade=1, autor=operador,
        )
        estorno_service.estornar(
            movimentacao=transferido, autor=operador, justificativa="Engano"
        )

        divergencias = self._comparar()
        assert not divergencias, (
            "Ponteiros de projeção divergem do livro-razão (ISC-ADR-04):\n  "
            + "\n  ".join(divergencias)
        )

    def test_recomputar_custodias_corrige_ponteiro_corrompido(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        """O command reconstrói o cache — é a mitigação prometida no ADR."""
        from django.core.management import call_command

        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito, destino=agente,
            unidades=unidades_no_deposito[:3], autor=operador,
        )

        # Corrompe o ponteiro à mão, simulando o desastre que o ADR teme.
        conta_deposito = custodia_service.custodia_de(deposito)
        Unidade.objects.filter(pk=unidades_no_deposito[0].pk).update(
            custodia_atual=conta_deposito
        )
        assert self._comparar()

        call_command("recomputar_custodias", verbosity=0)

        assert not self._comparar()
