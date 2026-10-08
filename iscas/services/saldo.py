"""Saldo derivado — sempre função do estado, nunca campo (ISC-RN-01).

Saldo em custódia sai de uma varredura sobre o índice composto de `Unidade`;
não toca no livro-razão. Saldo disponível desconta as reservas ativas, e a
reserva é a existência da linha em `AtribuicaoUnidade` (ISC-ADR-06) — não há
campo `reservado` em lugar nenhum.
"""
from django.db.models import Count, Exists, OuterRef, Q

from iscas.models.custodia import Unidade
from iscas.models.operacao import AtribuicaoUnidade
from iscas.services.custodia import custodia_de


def _reserva_ativa_subquery():
    return AtribuicaoUnidade.objects.filter(
        unidade=OuterRef("pk"), liberada_em__isnull=True
    )


def unidades_em_custodia(entidade, *, modelo=None):
    """Unidades atualmente na custódia da entidade."""
    qs = Unidade.objects.filter(custodia_atual=custodia_de(entidade))
    if modelo is not None:
        qs = qs.filter(modelo=modelo)
    return qs


def unidades_disponiveis(entidade, *, modelo=None):
    """Em custódia e sem reserva ativa — o que pode ser alocado."""
    return unidades_em_custodia(entidade, modelo=modelo).exclude(
        Exists(_reserva_ativa_subquery())
    )


def unidades_disponiveis_por_tipos(tipos):
    """Unidades sem reserva ativa, de qualquer agente ativo, dos tipos dados.

    Diferente de `unidades_disponiveis()`, que parte de UMA custódia: aqui a
    varredura atravessa agentes. É o que permite perguntar "quem pode atender
    este pedido?" numa consulta só, em vez de contar saldo agente a agente.
    O pedido é por tipo, então qualquer modelo do tipo serve.
    """
    from iscas.enums import TipoCustodia

    return Unidade.objects.filter(
        modelo__tipo__in=list(tipos),
        custodia_atual__tipo=TipoCustodia.AGENTE,
        custodia_atual__agente__is_active=True,
    ).exclude(Exists(_reserva_ativa_subquery()))


def saldo_em_custodia(entidade, *, modelo=None) -> int:
    return unidades_em_custodia(entidade, modelo=modelo).count()


def saldo_disponivel(entidade, *, modelo=None) -> int:
    """Saldo em custódia menos reservas ativas (ISC-RN-07)."""
    return unidades_disponiveis(entidade, modelo=modelo).count()


def saldo_reservado(entidade, *, modelo=None) -> int:
    return (
        unidades_em_custodia(entidade, modelo=modelo)
        .filter(Exists(_reserva_ativa_subquery()))
        .count()
    )


def saldo_por_modelo(entidade):
    """Saldo discriminado por modelo: total, disponível e reservado (ISC-RF-15).

    Uma consulta só, agregando com `filter=` — evita a armadilha de N+1 que
    apareceria ao iterar modelos e contar um a um.
    """
    return (
        unidades_em_custodia(entidade)
        .values("modelo", "modelo__nome", "modelo__codigo", "modelo__tipo")
        .annotate(
            total=Count("id"),
            reservado=Count("id", filter=Q(Exists(_reserva_ativa_subquery()))),
            disponivel=Count("id", filter=~Q(Exists(_reserva_ativa_subquery()))),
        )
        .order_by("modelo__nome")
    )


def saldo_por_modelo_em_lote(custodias):
    """Saldo por modelo de VÁRIAS custódias, em uma consulta (ISC-RF-15).

    Mesma semântica de `saldo_por_modelo()`, mas agregando de uma vez. O painel
    de saldos lista todos os depósitos e agentes; chamar `saldo_por_modelo()`
    num laço custa uma consulta por custódia — N+1 que degrada exatamente
    conforme a operação cresce, que é quando a tela mais importa.

    Args:
        custodias: iterável de objetos `Custodia`.

    Returns:
        `{custodia_id: [linhas]}`, cada linha no formato de
        `saldo_por_modelo()`. Custódia sem estoque não aparece no dicionário —
        quem chama usa `.get(pk, [])`.
    """
    ids = [c.pk for c in custodias]
    if not ids:
        return {}

    linhas = (
        Unidade.objects.filter(custodia_atual_id__in=ids)
        .values(
            "custodia_atual_id",
            "modelo",
            "modelo__nome",
            "modelo__codigo",
            "modelo__tipo",
        )
        .annotate(
            total=Count("id"),
            reservado=Count("id", filter=Q(Exists(_reserva_ativa_subquery()))),
            disponivel=Count("id", filter=~Q(Exists(_reserva_ativa_subquery()))),
        )
        .order_by("modelo__nome")
    )

    agrupado = {}
    for linha in linhas:
        agrupado.setdefault(linha["custodia_atual_id"], []).append(linha)
    return agrupado


def anexar_identificadores(custodias, saldos_por_custodia):
    """Põe em cada linha de saldo os IDs das unidades daquele modelo.

    Uma consulta para todas as custódias, separada de
    `saldo_por_modelo_em_lote` de propósito: o mapa e as listagens usam o
    saldo sem precisar de IDs, e não devem pagar por eles.

    Cada linha ganha `unidades`: lista de `{"identificador", "reservada"}`.
    Reservada continua com o agente, mas presa a uma solicitação.
    """
    ids = [c.pk for c in custodias]
    if not ids:
        return saldos_por_custodia

    por_chave = {}
    for custodia_id, modelo_id, identificador, reservada in (
        Unidade.objects.filter(custodia_atual_id__in=ids)
        .annotate(reservada=Exists(_reserva_ativa_subquery()))
        .order_by("identificador")
        .values_list("custodia_atual_id", "modelo_id", "identificador", "reservada")
    ):
        por_chave.setdefault((custodia_id, modelo_id), []).append(
            {"identificador": identificador, "reservada": reservada}
        )

    for custodia_id, linhas in saldos_por_custodia.items():
        for linha in linhas:
            linha["unidades"] = por_chave.get((custodia_id, linha["modelo"]), [])
    return saldos_por_custodia


def tem_saldo(entidade) -> bool:
    """Há qualquer unidade em custódia? Usado ao desativar agente (ISC-RN-18)."""
    return unidades_em_custodia(entidade).exists()
