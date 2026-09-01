"""Baixa por perda, avaria ou obsolescência (ISC-RF-12, ISC-RN-13).

Justificativa textual é obrigatória e o autor fica registrado: baixa sem motivo
é buraco no inventário. A unidade entra em estado terminal.
"""
from django.db import transaction

from iscas.enums import MotivoBaixa, TipoCustodia, TipoMovimentacao
from iscas.services.custodia import (
    custodia_de,
    custodia_singleton,
    registrar_movimentacao,
)
from iscas.services.exceptions import MovimentacaoInvalida
from iscas.services.transferencia import _recusar_reservadas, selecionar_disponiveis


@transaction.atomic
def dar_baixa(
    *,
    origem,
    motivo,
    justificativa,
    autor,
    modelo=None,
    quantidade=None,
    unidades=None,
    ocorrido_em=None,
):
    """Baixa unidades, movendo-as para a custódia terminal BAIXA.

    Args:
        motivo: `MotivoBaixa` (PERDA, AVARIA ou OBSOLESCENCIA).
        justificativa: texto obrigatório (ISC-RN-13).
        unidades: quando omitido, seleciona `quantidade` unidades do `modelo`
            por FIFO.
    """
    if motivo not in MotivoBaixa.values:
        raise MovimentacaoInvalida(f"Motivo de baixa inválido: {motivo}.")
    if not (justificativa or "").strip():
        raise MovimentacaoInvalida(
            "Baixa exige justificativa textual (ISC-RN-13)."
        )

    if unidades is None:
        if modelo is None or not quantidade:
            raise MovimentacaoInvalida(
                "Informe as unidades, ou o modelo e a quantidade a baixar."
            )
        unidades = selecionar_disponiveis(
            origem=origem, modelo=modelo, quantidade=quantidade
        )
    else:
        unidades = list(unidades)
        _recusar_reservadas(unidades)

    return registrar_movimentacao(
        tipo=TipoMovimentacao.BAIXA,
        origem=custodia_de(origem),
        destino=custodia_singleton(TipoCustodia.BAIXA),
        unidades=unidades,
        autor=autor,
        ocorrido_em=ocorrido_em,
        motivo_baixa=motivo,
        justificativa=justificativa,
    )
