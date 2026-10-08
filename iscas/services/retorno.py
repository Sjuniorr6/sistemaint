"""Devolução de iscas em posse de cliente (ISC-RF-32, ISC-RN-06).

Retornável volta ao fim do uso; descartável volta quando apresenta defeito e o
cliente pede substituição. Em ambos os casos a isca sai do cliente por um
lançamento de RETORNO — o único tipo que o livro-razão aceita para tirar uma
descartável do cliente (ISC-RN-05, ver `services.custodia._eh_terminal`).
"""
from django.db import transaction

from iscas.enums import TipoCustodia, TipoModelo, TipoMovimentacao
from iscas.models.custodia import Unidade
from iscas.services.custodia import custodia_de, registrar_movimentacao
from iscas.services.exceptions import MovimentacaoInvalida

_DESTINOS_VALIDOS = (TipoCustodia.DEPOSITO, TipoCustodia.AGENTE)


def retornaveis_em_posse(*, cliente=None):
    """Unidades retornáveis atualmente com clientes (ISC-RF-31).

    `custodia_desde` dá o tempo em posse sem join — é o que alimenta a
    sinalização de retornável parado (ISC-RF-33).
    """
    qs = (
        Unidade.objects.filter(
            custodia_atual__tipo=TipoCustodia.CLIENTE,
            modelo__tipo=TipoModelo.RETORNAVEL,
        )
        .select_related("modelo", "custodia_atual", "custodia_atual__cliente")
        .order_by("custodia_desde")
    )
    if cliente is not None:
        qs = qs.filter(custodia_atual__cliente=cliente)
    return qs


@transaction.atomic
def registrar_devolucao(*, unidades, destino, motivo, autor):
    """Traz iscas de volta do cliente para um depósito ou agente (ISC-RF-32).

    Vale para retornável e para descartável: o cliente devolve a descartável
    que apresentou defeito, para ser substituída (ISC-RN-05).

    Iscas de clientes diferentes viram UM lançamento de RETORNO por cliente —
    lançamento tem uma origem só —, todos nesta transação: se uma isca for
    inválida, nenhuma se move.

    Args:
        unidades: `Unidade`s (ou ids) que voltam. Todas precisam estar com
            algum cliente.
        destino: `Deposito` ou `Agente`.
        motivo: por que o cliente devolveu. Obrigatório; vira a justificativa
            de cada lançamento.

    Returns:
        Lista das `Movimentacao` criadas, uma por cliente.
    """
    if not (motivo or "").strip():
        raise MovimentacaoInvalida("Informe o motivo da devolução.")

    ids = [getattr(u, "pk", u) for u in unidades]
    unidades = list(
        Unidade.objects.select_related("modelo", "custodia_atual").filter(pk__in=ids)
    )
    if not unidades:
        raise MovimentacaoInvalida("Informe ao menos uma isca para devolução.")

    conta_destino = custodia_de(destino)
    if conta_destino.tipo not in _DESTINOS_VALIDOS:
        raise MovimentacaoInvalida("A devolução vai para um depósito ou um agente.")

    fora = [u for u in unidades if u.custodia_atual.tipo != TipoCustodia.CLIENTE]
    if fora:
        exemplos = ", ".join(u.identificador for u in fora[:5])
        raise MovimentacaoInvalida(
            f"{len(fora)} isca(s) não estão com cliente e não podem ser "
            f"devolvidas: {exemplos}{'…' if len(fora) > 5 else ''}"
        )

    por_cliente = {}
    for unidade in unidades:
        por_cliente.setdefault(unidade.custodia_atual_id, []).append(unidade)

    return [
        registrar_movimentacao(
            tipo=TipoMovimentacao.RETORNO,
            origem=grupo[0].custodia_atual,
            destino=conta_destino,
            unidades=grupo,
            autor=autor,
            justificativa=motivo.strip(),
        )
        for grupo in por_cliente.values()
    ]
