"""Jornada completa do PRD, ponta a ponta, e o teste de concorrência.

O E2E percorre a "Jornada Principal do Atendimento" do PRD inteira:
abastecimento → transferência → solicitação → busca por proximidade →
atribuição dividida entre dois agentes → rota → entrega → retorno de retornável.

O teste de concorrência usa `TransactionTestCase` com threads e conexões reais
— não a transação de teste, que esconderia o comportamento concorrente.
"""
import threading

import pytest
from django.contrib.auth import get_user_model
from django.db import connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from iscas.enums import (
    SituacaoUnidade,
    StatusAtribuicao,
    StatusSolicitacao,
    TipoModelo,
)
from iscas.models.cadastro import Agente, Cliente, Deposito, ModeloEquipamento
from iscas.models.custodia import Unidade
from iscas.models.operacao import Atribuicao, AtribuicaoUnidade, Solicitacao
from iscas.services import entrada as entrada_service
from iscas.services import geo as geo_service
from iscas.services import reserva as reserva_service
from iscas.services import retorno as retorno_service
from iscas.services import saldo as saldo_service
from iscas.services import solicitacao as solicitacao_service
from iscas.services import transferencia as transferencia_service
from iscas.services.exceptions import SaldoInsuficiente


@pytest.mark.django_db
def test_jornada_completa_do_prd(
    deposito, agente, agente2, cliente, modelo_descartavel, modelo_retornavel, operador
):
    """Os nove passos da Jornada Principal do Atendimento (PRD)."""

    # 1. Abastecimento — entrada de lote no depósito, colando a lista.
    identificadores = entrada_service.parse_identificadores(
        "\n".join(f"E2E{i:03d}" for i in range(1, 21))
    )
    entrada_service.registrar_entrada(
        modelo=modelo_descartavel,
        identificadores=identificadores,
        destino=deposito,
        autor=operador,
        nota_fiscal="NF-E2E",
        lote="LOTE-1",
    )
    assert saldo_service.saldo_em_custodia(deposito, modelo=modelo_descartavel) == 20

    # Transferência para os agentes: 12 e 8.
    transferencia_service.transferir(
        origem=deposito, destino=agente, modelo=modelo_descartavel,
        quantidade=12, autor=operador,
    )
    transferencia_service.transferir(
        origem=deposito, destino=agente2, modelo=modelo_descartavel,
        quantidade=8, autor=operador,
    )
    assert saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel) == 12
    assert saldo_service.saldo_disponivel(agente2, modelo=modelo_descartavel) == 8
    assert saldo_service.saldo_em_custodia(deposito, modelo=modelo_descartavel) == 0

    # 2. Solicitação — o cliente pede 20 iscas.
    solicitacao = solicitacao_service.abrir_solicitacao(
        cliente=cliente,
        itens=[(modelo_descartavel, 20)],
        autor=operador,
        observacao="Entregar na portaria",
    )
    assert solicitacao.status == StatusSolicitacao.ABERTA

    # 3. Busca no mapa — quem está perto e tem saldo?
    candidatos = geo_service.agentes_proximos(
        latitude=cliente.latitude,
        longitude=cliente.longitude,
        raio_km=50,
        modelo=modelo_descartavel,
    )
    assert len(candidatos) == 2
    # Ordenados por distância crescente, com o saldo disponível de cada um.
    assert candidatos[0]["distancia_km"] <= candidatos[1]["distancia_km"]
    assert {c["disponivel"] for c in candidatos} == {12, 8}

    # 4. Atribuição — dividida entre os dois agentes (ISC-RN-10).
    a1 = solicitacao_service.criar_atribuicao(
        solicitacao=solicitacao, agente=agente,
        itens=[(modelo_descartavel, 12)], autor=operador,
    )
    a2 = solicitacao_service.criar_atribuicao(
        solicitacao=solicitacao, agente=agente2,
        itens=[(modelo_descartavel, 8)], autor=operador,
    )
    solicitacao.refresh_from_db()

    assert solicitacao.status == StatusSolicitacao.ATRIBUIDA
    assert solicitacao_service.cobertura_total(solicitacao)
    # Reservadas: continuam com o agente, mas indisponíveis (ISC-RN-07).
    assert saldo_service.saldo_em_custodia(agente, modelo=modelo_descartavel) == 12
    assert saldo_service.saldo_disponivel(agente, modelo=modelo_descartavel) == 0

    # 5. Comunicação — o sistema monta o texto; não envia nada.
    from iscas.services import mensagem as mensagem_service

    texto = mensagem_service.montar_texto_atribuicao(a1)
    assert cliente.nome_razao_social in texto
    assert "12x" in texto

    # 6. Rota.
    solicitacao_service.marcar_em_rota(atribuicao=a1, autor=operador)
    solicitacao.refresh_from_db()
    assert solicitacao.status == StatusSolicitacao.EM_ROTA

    unidade_em_rota = a1.unidades_reservadas().first()
    anotada = Unidade.objects.com_situacao().get(pk=unidade_em_rota.pk)
    assert anotada.situacao == SituacaoUnidade.EM_ROTA

    # 7. Entrega — é aqui que a custódia passa ao cliente (ISC-RN-08).
    solicitacao_service.confirmar_entrega(
        atribuicao=a1, autor=operador, recebido_por="Porteiro"
    )
    solicitacao.refresh_from_db()
    assert solicitacao.status != StatusSolicitacao.ENTREGUE  # ainda falta a2

    solicitacao_service.confirmar_entrega(
        atribuicao=a2, autor=operador, recebido_por="Porteiro"
    )
    solicitacao.refresh_from_db()

    assert solicitacao.status == StatusSolicitacao.ENTREGUE
    assert saldo_service.saldo_em_custodia(agente, modelo=modelo_descartavel) == 0
    assert saldo_service.saldo_em_custodia(agente2, modelo=modelo_descartavel) == 0
    assert saldo_service.saldo_em_custodia(cliente, modelo=modelo_descartavel) == 20

    # 8. Destino — descartável entregue é terminal (ISC-RN-05).
    consumidas = Unidade.objects.com_situacao().filter(
        situacao=SituacaoUnidade.CONSUMIDA
    )
    assert consumidas.count() == 20
    # Descartável não aparece como candidato a retorno.
    assert retorno_service.retornaveis_em_posse(cliente=cliente).count() == 0

    # 9. Retorno — só faz sentido para retornável. Repetimos o ciclo com um.
    entrada_service.registrar_entrada(
        modelo=modelo_retornavel,
        identificadores=[f"RET{i:03d}" for i in range(1, 6)],
        destino=agente,
        autor=operador,
    )
    solicitacao_ret = solicitacao_service.abrir_solicitacao(
        cliente=cliente, itens=[(modelo_retornavel, 5)], autor=operador
    )
    a3 = solicitacao_service.criar_atribuicao(
        solicitacao=solicitacao_ret, agente=agente,
        itens=[(modelo_retornavel, 5)], autor=operador,
    )
    solicitacao_service.confirmar_entrega(atribuicao=a3, autor=operador)

    em_posse = retorno_service.retornaveis_em_posse(cliente=cliente)
    assert em_posse.count() == 5

    retorno_service.registrar_retorno(
        unidades=list(em_posse[:3]), destino=deposito, autor=operador
    )
    assert saldo_service.saldo_em_custodia(deposito, modelo=modelo_retornavel) == 3
    assert retorno_service.retornaveis_em_posse(cliente=cliente).count() == 2

    # O histórico completo sobreviveu à jornada inteira.
    from iscas.selectors import historico_unidade

    assert historico_unidade(em_posse.first()).count() >= 1


class TestConcorrenciaReserva(TransactionTestCase):
    """ISC-RN-07: duas reservas simultâneas nunca alocam a mesma unidade.

    Roda com `TransactionTestCase` e conexões reais — a transação de teste
    normal do pytest-django esconderia o comportamento concorrente.

    Neste projeto (SQLite) a garantia não vem do `select_for_update
    (skip_locked=True)`, que o Django ignora aqui, e sim do índice único parcial
    em `AtribuicaoUnidade` mais o retry do service. O teste vale para os dois
    bancos: verifica o RESULTADO (exatamente uma reserva ativa por unidade),
    não o mecanismo.
    """

    reset_sequences = True

    def setUp(self):
        # `TransactionTestCase` faz TRUNCATE entre testes, o que apaga as
        # custódias singleton criadas pela migration de dados. Recriamos com o
        # command oficial — o mesmo caminho que a produção usaria.
        from django.core.management import call_command

        call_command("seed_custodias", verbosity=0)

        self.operador = get_user_model().objects.create_user(
            username="op_concorrencia", password="x"
        )
        self.modelo = ModeloEquipamento.objects.create(
            nome="Isca Concorrência", codigo="ISC-CONC", tipo=TipoModelo.DESCARTAVEL
        )
        self.agente = Agente(
            nome="Agente Disputado", telefone="11999990000",
            logradouro="Rua Y", cidade="São Paulo", uf="SP",
            latitude="-23.550520", longitude="-46.633308",
        )
        self.agente.cpf = "39053344705"
        self.agente.save()

        self.cliente = Cliente.objects.create(
            nome_razao_social="Cliente Concorrência",
            logradouro="Av. Z", cidade="São Paulo", uf="SP",
            latitude="-23.560000", longitude="-46.640000",
        )

        # Saldo para UMA reserva de 5 unidades — as duas threads disputam.
        entrada_service.registrar_entrada(
            modelo=self.modelo,
            identificadores=[f"C{i:03d}" for i in range(1, 6)],
            destino=self.agente,
            autor=self.operador,
        )

        self.solicitacao = Solicitacao.objects.create(
            cliente=self.cliente, aberta_em=timezone.now(), aberta_por=self.operador
        )

    def test_duas_reservas_simultaneas_apenas_uma_sucede(self):
        """Saldo para uma só: uma vence, a outra levanta SaldoInsuficiente."""
        resultados = {}
        barreira = threading.Barrier(2)

        def reservar(nome):
            try:
                atribuicao = Atribuicao.objects.create(
                    solicitacao=self.solicitacao,
                    agente=self.agente,
                    criada_por=self.operador,
                )
                # As duas threads chegam juntas no ponto crítico.
                barreira.wait(timeout=10)
                reserva_service.alocar_unidades(
                    agente=self.agente,
                    modelo=self.modelo,
                    quantidade=5,
                    atribuicao=atribuicao,
                )
                resultados[nome] = "sucesso"
            except SaldoInsuficiente:
                resultados[nome] = "saldo_insuficiente"
            except Exception as exc:  # noqa: BLE001 — o teste reporta o que veio
                resultados[nome] = f"erro: {type(exc).__name__}: {exc}"
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=reservar, args=(f"t{i}",)) for i in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        sucessos = [v for v in resultados.values() if v == "sucesso"]
        assert len(sucessos) == 1, (
            f"Esperava exatamente uma reserva bem-sucedida, veio: {resultados}"
        )

        # A garantia que importa: nenhuma unidade com duas reservas ativas.
        for unidade in Unidade.objects.all():
            ativas = AtribuicaoUnidade.objects.filter(
                unidade=unidade, liberada_em__isnull=True
            ).count()
            assert ativas <= 1, (
                f"{unidade.identificador} ficou com {ativas} reservas ativas "
                "— dupla alocação (ISC-RN-07)."
            )

        # E o saldo disponível reflete exatamente uma reserva de 5.
        assert saldo_service.saldo_disponivel(self.agente, modelo=self.modelo) == 0
        assert saldo_service.saldo_reservado(self.agente, modelo=self.modelo) == 5

    def test_reservas_parciais_concorrentes_nao_se_sobrepoem(self):
        """Saldo para as duas (3+2 de 5): ambas sucedem, sem sobreposição."""
        resultados = {}
        barreira = threading.Barrier(2)

        def reservar(nome, quantidade):
            try:
                atribuicao = Atribuicao.objects.create(
                    solicitacao=self.solicitacao,
                    agente=self.agente,
                    criada_por=self.operador,
                )
                barreira.wait(timeout=10)
                unidades = reserva_service.alocar_unidades(
                    agente=self.agente,
                    modelo=self.modelo,
                    quantidade=quantidade,
                    atribuicao=atribuicao,
                )
                resultados[nome] = {u.pk for u in unidades}
            except Exception as exc:  # noqa: BLE001
                resultados[nome] = f"erro: {type(exc).__name__}: {exc}"
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=reservar, args=("a", 3)),
            threading.Thread(target=reservar, args=("b", 2)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        conjuntos = [v for v in resultados.values() if isinstance(v, set)]
        assert len(conjuntos) == 2, f"Alguma reserva falhou: {resultados}"
        assert conjuntos[0].isdisjoint(conjuntos[1]), (
            f"As duas reservas pegaram a mesma unidade: {resultados}"
        )

        for unidade in Unidade.objects.all():
            ativas = AtribuicaoUnidade.objects.filter(
                unidade=unidade, liberada_em__isnull=True
            ).count()
            assert ativas <= 1
