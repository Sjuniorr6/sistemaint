"""Transferência entre custódias internas e ciclo de manutenção.

Depósito ↔ Agente e Agente ↔ Agente (ISC-RF-11); envio e retorno de manutenção
(ISC-RF-13, ISC-RN-14). Tudo passa por `registrar_movimentacao()`.
"""
from django.db import transaction

from iscas.enums import TipoCustodia, TipoMovimentacao
from iscas.services.custodia import (
    custodia_de,
    custodia_singleton,
    registrar_movimentacao,
)
from iscas.services.exceptions import MovimentacaoInvalida, UnidadeIndisponivel
from iscas.services.saldo import unidades_disponiveis

#: Transferência interna só entre estas custódias — cliente recebe por ENTREGA,
#: manutenção por ENVIO_MANUTENCAO, cada uma com seu service.
_CUSTODIAS_INTERNAS = (TipoCustodia.DEPOSITO, TipoCustodia.AGENTE)


def selecionar_disponiveis(*, origem, modelo, quantidade):
    """Escolhe `quantidade` unidades disponíveis na origem, em ordem FIFO.

    Recusa quando o saldo não cobre — a mensagem diz quanto há, porque o
    operador precisa saber se transfere menos ou procura outra origem.
    """
    unidades = list(
        unidades_disponiveis(origem, modelo=modelo).order_by("custodia_desde", "pk")[
            :quantidade
        ]
    )
    if len(unidades) < quantidade:
        raise UnidadeIndisponivel(
            f"{origem} tem {len(unidades)} unidade(s) disponível(is) de {modelo}, "
            f"mas foram pedidas {quantidade}."
        )
    return unidades


@transaction.atomic
def transferir(
    *,
    origem,
    destino,
    autor,
    modelo=None,
    quantidade=None,
    unidades=None,
    ocorrido_em=None,
    justificativa="",
):
    """Move unidades entre Depósito e Agente, ou entre Agentes (ISC-RF-11).

    Args:
        unidades: as unidades específicas a transferir — é como a tela opera.
        modelo/quantidade: alternativa por seleção FIFO, quando as unidades não
            são informadas. Exige os dois juntos.
    """
    conta_origem = custodia_de(origem)
    conta_destino = custodia_de(destino)

    if conta_origem.tipo not in _CUSTODIAS_INTERNAS:
        raise MovimentacaoInvalida(
            "Transferência interna só sai de Depósito ou Agente."
        )
    if conta_destino.tipo not in _CUSTODIAS_INTERNAS:
        raise MovimentacaoInvalida(
            "Transferência interna só destina a Depósito ou Agente. "
            "Entrega ao cliente é confirmada pela atribuição."
        )

    if unidades is None:
        if modelo is None or not quantidade:
            raise MovimentacaoInvalida(
                "Informe as unidades, ou o modelo e a quantidade a transferir."
            )
        unidades = selecionar_disponiveis(
            origem=origem, modelo=modelo, quantidade=quantidade
        )
    else:
        unidades = list(unidades)
        _recusar_reservadas(unidades)

    return registrar_movimentacao(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        origem=conta_origem,
        destino=conta_destino,
        unidades=unidades,
        autor=autor,
        ocorrido_em=ocorrido_em,
        justificativa=justificativa,
    )


def _recusar_reservadas(unidades):
    """Unidade com reserva ativa está comprometida com uma atribuição."""
    reservadas = [u for u in unidades if u.tem_reserva_ativa]
    if reservadas:
        exemplos = ", ".join(u.identificador for u in reservadas[:5])
        raise UnidadeIndisponivel(
            f"{len(reservadas)} unidade(s) têm reserva ativa e não podem ser "
            f"movimentadas: {exemplos}{'…' if len(reservadas) > 5 else ''}. "
            "Cancele a atribuição antes."
        )


@transaction.atomic
def enviar_para_manutencao(
    *,
    origem,
    autor,
    modelo=None,
    quantidade=None,
    unidades=None,
    ocorrido_em=None,
    justificativa="",
):
    """Envia unidades à manutenção — NÃO é baixa (ISC-RN-14).

    A unidade sai do saldo disponível mas o ciclo é reversível: volta ao
    depósito por `retornar_de_manutencao()`.

    Args:
        unidades: as unidades específicas a enviar — é como a tela opera,
            porque a peça que vai para o conserto é concreta.
        modelo/quantidade: alternativa por seleção FIFO, quando as unidades não
            são informadas. Exige os dois juntos.
    """
    if unidades is None:
        if modelo is None or not quantidade:
            raise MovimentacaoInvalida(
                "Informe as unidades, ou o modelo e a quantidade a enviar."
            )
        unidades = selecionar_disponiveis(
            origem=origem, modelo=modelo, quantidade=quantidade
        )
    else:
        unidades = list(unidades)
        _recusar_reservadas(unidades)

    return registrar_movimentacao(
        tipo=TipoMovimentacao.ENVIO_MANUTENCAO,
        origem=custodia_de(origem),
        destino=custodia_singleton(TipoCustodia.MANUTENCAO),
        unidades=unidades,
        autor=autor,
        ocorrido_em=ocorrido_em,
        justificativa=justificativa,
    )


@transaction.atomic
def retornar_de_manutencao(
    *, unidades, destino, autor, ocorrido_em=None, justificativa=""
):
    """Devolve unidades da manutenção ao Depósito (ISC-RF-13)."""
    conta_destino = custodia_de(destino)
    if conta_destino.tipo not in _CUSTODIAS_INTERNAS:
        raise MovimentacaoInvalida(
            "Retorno de manutenção destina a Depósito ou Agente."
        )
    return registrar_movimentacao(
        tipo=TipoMovimentacao.RETORNO_MANUTENCAO,
        origem=custodia_singleton(TipoCustodia.MANUTENCAO),
        destino=conta_destino,
        unidades=list(unidades),
        autor=autor,
        ocorrido_em=ocorrido_em,
        justificativa=justificativa,
    )
