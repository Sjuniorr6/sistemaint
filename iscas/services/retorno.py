"""Retorno de unidade retornável em posse de cliente (ISC-RF-32, ISC-RN-06).

Só modelo RETORNAVEL retorna. Descartável entregue está em estado terminal e o
service recusa a tentativa, inclusive por id direto (ISC-RN-05) — a guarda vale
mesmo quando a UI não oferece o caminho.
"""
from django.db import transaction

from iscas.enums import TipoCustodia, TipoModelo, TipoMovimentacao
from iscas.models.custodia import Unidade
from iscas.services.custodia import custodia_de, registrar_movimentacao
from iscas.services.exceptions import MovimentacaoInvalida, UnidadeTerminal

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
def registrar_retorno(
    *, unidades, destino, autor, ocorrido_em=None, justificativa=""
):
    """Traz unidades retornáveis de volta do cliente (ISC-RF-32).

    Args:
        destino: `Deposito` ou `Agente` que recebe as unidades de volta.
    """
    unidades = list(
        Unidade.objects.select_related("modelo", "custodia_atual").filter(
            pk__in=[u.pk for u in unidades]
        )
    )
    if not unidades:
        raise MovimentacaoInvalida("Informe ao menos uma unidade para retorno.")

    conta_destino = custodia_de(destino)
    if conta_destino.tipo not in _DESTINOS_VALIDOS:
        raise MovimentacaoInvalida(
            "O retorno destina a Depósito ou Agente (ISC-RF-32)."
        )

    descartaveis = [u for u in unidades if u.modelo.tipo != TipoModelo.RETORNAVEL]
    if descartaveis:
        exemplos = ", ".join(u.identificador for u in descartaveis[:5])
        raise UnidadeTerminal(
            f"{len(descartaveis)} unidade(s) são de modelo descartável e não "
            f"retornam ao estoque (ISC-RN-05): {exemplos}"
            f"{'…' if len(descartaveis) > 5 else ''}"
        )

    # Todas precisam estar com o MESMO cliente: um lançamento tem uma origem só.
    origens = {u.custodia_atual_id for u in unidades}
    if len(origens) > 1:
        raise MovimentacaoInvalida(
            "As unidades estão com clientes diferentes; registre um retorno por "
            "cliente."
        )
    origem = unidades[0].custodia_atual
    if origem.tipo != TipoCustodia.CLIENTE:
        raise MovimentacaoInvalida(
            f"As unidades não estão em posse de cliente (estão em {origem})."
        )

    return registrar_movimentacao(
        tipo=TipoMovimentacao.RETORNO,
        origem=origem,
        destino=conta_destino,
        unidades=unidades,
        autor=autor,
        ocorrido_em=ocorrido_em,
        justificativa=justificativa,
    )
