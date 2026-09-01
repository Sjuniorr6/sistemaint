"""Alocação e liberação de reservas — a seção crítica do sistema.

Duas solicitações simultâneas sobre o mesmo agente não podem alocar a mesma
unidade (ISC-RN-07). `alocar_unidades()` é o ponto único de reserva.

## Sobre o banco

O ARCHITECTURE original especifica PostgreSQL e apoia a primeira garantia em
`select_for_update(skip_locked=True)`. **Este projeto roda SQLite**, onde o
Django ignora silenciosamente `skip_locked` (não levanta erro — simplesmente
não trava) e não existe lock em nível de linha. A garantia foi deslocada:

1. **Índice único parcial** em `AtribuicaoUnidade` (`unidade` UNIQUE onde
   `liberada_em IS NULL`) — é a garantia PRINCIPAL aqui, imposta pelo banco.
   Funciona em SQLite. Mesmo com bug de aplicação, dupla reserva ativa é
   impossível: o INSERT falha com `IntegrityError`.
2. **Transação atômica com verificação de contagem dentro dela** — se a seleção
   rendeu menos unidades que o pedido, tudo reverte com `SaldoInsuficiente`.
   Nunca há reserva parcial silenciosa.
3. **Retry com espera** sobre `IntegrityError` e sobre o `OperationalError` de
   lock. O primeiro é a colisão lógica (duas transações escolheram a mesma
   unidade); o segundo é característico do SQLite, que serializa escritas no
   banco INTEIRO e recusa a transação perdedora com "database is locked". Sem
   tratar os dois, uma disputa de saldo vaza erro bruto de banco para o
   operador — e o retry é o que substitui o comportamento de fila que o
   `skip_locked` daria no PostgreSQL.

`select_for_update()` continua na query: é inócuo no SQLite e volta a fazer
efeito no dia em que o GSInt migrar para PostgreSQL. Nesse dia, acrescentar
`skip_locked=True` aqui torna o retry de lock desnecessário — a troca está
isolada nesta função.
"""
import random
import time

from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from iscas.models.custodia import Unidade
from iscas.models.operacao import AtribuicaoUnidade
from iscas.services.custodia import custodia_de
from iscas.services.exceptions import SaldoInsuficiente, UnidadeIndisponivel

#: Tentativas de alocação antes de desistir. Cada retry relê o saldo; a colisão
#: só acontece sob concorrência real, e cinco rodadas cobrem folgadamente o
#: volume projetado (200 solicitações/mês).
_MAX_TENTATIVAS = 5

#: Espera base entre tentativas, com backoff e jitter. O jitter evita que duas
#: transações que colidiram voltem a colidir no mesmo instante.
_ESPERA_BASE_SEGUNDOS = 0.05


def _eh_lock_de_banco(exc) -> bool:
    """Distingue "banco ocupado" de erro de programação em SQL.

    Só o primeiro justifica retry: um erro de sintaxe ou coluna inexistente
    também chega como `OperationalError`, e insistir nele seria mascarar bug.
    """
    mensagem = str(exc).lower()
    return "locked" in mensagem or "busy" in mensagem


def _aguardar(tentativa):
    time.sleep(_ESPERA_BASE_SEGUNDOS * (2**tentativa) * (0.5 + random.random()))


def _candidatas(custodia, modelo, quantidade):
    """Unidades alocáveis, em ordem FIFO de entrada em custódia (ISC-RF-25)."""
    return list(
        Unidade.objects.select_for_update()
        .filter(custodia_atual=custodia, modelo=modelo)
        .exclude(
            Exists(
                AtribuicaoUnidade.objects.filter(
                    unidade=OuterRef("pk"), liberada_em__isnull=True
                )
            )
        )
        .order_by("custodia_desde", "pk")[:quantidade]
    )


def alocar_unidades(*, agente, modelo, quantidade, atribuicao, unidades=None):
    """Reserva `quantidade` unidades do agente para a atribuição.

    Args:
        unidades: quando informado, reserva exatamente estas unidades em vez de
            escolher por FIFO — é o "permitindo ao operador escolher unidades
            específicas" do ISC-RF-25.

    Returns:
        Lista das `Unidade` reservadas.

    Raises:
        SaldoInsuficiente: o agente não tem disponível o bastante.
        UnidadeIndisponivel: uma unidade escolhida à mão não está disponível.
    """
    if quantidade < 1:
        raise SaldoInsuficiente("Quantidade a reservar precisa ser positiva.")

    custodia = custodia_de(agente)

    if unidades is not None:
        return _alocar_especificas(
            custodia=custodia,
            modelo=modelo,
            unidades=list(unidades),
            quantidade=quantidade,
            atribuicao=atribuicao,
        )

    ultimo_erro = None
    for tentativa in range(_MAX_TENTATIVAS):
        try:
            with transaction.atomic():
                escolhidas = _candidatas(custodia, modelo, quantidade)
                if len(escolhidas) < quantidade:
                    # Dentro da transação: se rendeu menos que o pedido, nada
                    # é reservado. Sem reserva parcial silenciosa.
                    raise SaldoInsuficiente(
                        f"{agente} tem {len(escolhidas)} unidade(s) disponível(is) "
                        f"de {modelo}, mas foram pedidas {quantidade}."
                    )
                AtribuicaoUnidade.objects.bulk_create(
                    [
                        AtribuicaoUnidade(atribuicao=atribuicao, unidade=unidade)
                        for unidade in escolhidas
                    ]
                )
                return escolhidas
        except IntegrityError as exc:
            # O índice único parcial pegou: outra transação reservou uma destas
            # unidades no intervalo. Relê o saldo e tenta as próximas.
            ultimo_erro = exc
            _aguardar(tentativa)
        except OperationalError as exc:
            # SQLite serializa escritas no banco inteiro; a transação perdedora
            # leva "database is locked". Esperar e repetir é o tratamento certo.
            if not _eh_lock_de_banco(exc):
                raise
            ultimo_erro = exc
            _aguardar(tentativa)

    raise SaldoInsuficiente(
        f"Não foi possível reservar {quantidade} unidade(s) de {modelo} com "
        f"{agente} após {_MAX_TENTATIVAS} tentativas — o saldo está sendo "
        "disputado por outra operação. Tente novamente."
    ) from ultimo_erro


def _alocar_especificas(*, custodia, modelo, unidades, quantidade, atribuicao):
    """Reserva unidades escolhidas à mão pelo operador (ISC-RF-25)."""
    if len(unidades) != quantidade:
        raise SaldoInsuficiente(
            f"Foram escolhidas {len(unidades)} unidade(s), mas a quantidade "
            f"pedida é {quantidade}."
        )
    ids = [u.pk for u in unidades]
    with transaction.atomic():
        travadas = list(
            Unidade.objects.select_for_update()
            .filter(pk__in=ids, custodia_atual=custodia, modelo=modelo)
            .exclude(
                Exists(
                    AtribuicaoUnidade.objects.filter(
                        unidade=OuterRef("pk"), liberada_em__isnull=True
                    )
                )
            )
        )
        if len(travadas) != len(set(ids)):
            indisponiveis = set(ids) - {u.pk for u in travadas}
            raise UnidadeIndisponivel(
                f"{len(indisponiveis)} unidade(s) escolhida(s) não estão "
                "disponíveis nesta custódia (reservadas, em outro modelo ou "
                "movimentadas nesse intervalo)."
            )
        try:
            AtribuicaoUnidade.objects.bulk_create(
                [
                    AtribuicaoUnidade(atribuicao=atribuicao, unidade=unidade)
                    for unidade in travadas
                ]
            )
        except IntegrityError as exc:
            raise UnidadeIndisponivel(
                "Uma das unidades escolhidas acabou de ser reservada por outra "
                "operação."
            ) from exc
        return travadas


def liberar_reservas(atribuicao, *, momento=None) -> int:
    """Libera todas as reservas ativas da atribuição (ISC-RN-09).

    Liberar é preencher `liberada_em`, nunca deletar — o histórico de reservas
    canceladas permanece auditável (ISC-ADR-06). Não gera lançamento: nada
    mudou de custódia.

    Returns:
        Quantas reservas foram liberadas.
    """
    return AtribuicaoUnidade.objects.filter(
        atribuicao=atribuicao, liberada_em__isnull=True
    ).update(liberada_em=momento or timezone.now())


def unidades_reservadas(atribuicao):
    """Unidades com reserva ativa desta atribuição."""
    return Unidade.objects.filter(
        reservas__atribuicao=atribuicao, reservas__liberada_em__isnull=True
    ).select_related("modelo", "custodia_atual")
