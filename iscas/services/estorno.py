"""Estorno: correção por contra-lançamento, nunca por edição (ISC-ADR-16).

O erro é informação. Auditoria precisa ver o que foi lançado, quando se
percebeu e quem corrigiu — por isso o registro original permanece intacto e o
estorno é uma nova linha que o referencia.

O estorno inverte origem e destino do lançamento original, devolvendo as
unidades à custódia anterior. É o único caminho legítimo para tirar uma unidade
de situação terminal: desfazer o lançamento que a colocou lá.
"""
from django.db import transaction

from iscas.enums import TipoMovimentacao
from iscas.models.custodia import Unidade
from iscas.services.custodia import registrar_movimentacao
from iscas.services.exceptions import EstornoInvalido


def _validar(movimentacao, unidades):
    if movimentacao.tipo == TipoMovimentacao.ESTORNO:
        raise EstornoInvalido(
            "Um estorno não pode ser estornado. Para desfazer, lance a "
            "movimentação correta."
        )
    if movimentacao.foi_estornada:
        raise EstornoInvalido(
            f"A movimentação #{movimentacao.pk} já foi estornada."
        )
    # Cada unidade só pode voltar se ainda estiver onde o lançamento a deixou.
    # Se ela já se moveu depois, estornar aqui inventaria uma posse que não
    # existe — o operador precisa desfazer na ordem inversa.
    fora_do_lugar = [
        u for u in unidades if u.custodia_atual_id != movimentacao.destino_id
    ]
    if fora_do_lugar:
        exemplos = ", ".join(u.identificador for u in fora_do_lugar[:5])
        raise EstornoInvalido(
            f"{len(fora_do_lugar)} unidade(s) já foram movimentadas depois deste "
            f"lançamento e não estão mais em {movimentacao.destino}: {exemplos}"
            f"{'…' if len(fora_do_lugar) > 5 else ''}. "
            "Estorne primeiro as movimentações mais recentes."
        )


@transaction.atomic
def estornar(*, movimentacao, autor, justificativa, ocorrido_em=None):
    """Gera o contra-lançamento da movimentação (ISC-RF-14).

    O original não é tocado: continua byte a byte como foi gravado. O estorno é
    um novo registro, do tipo ESTORNO, com `estorno_de` apontando para ele.

    Returns:
        A `Movimentacao` de estorno.
    """
    if not (justificativa or "").strip():
        raise EstornoInvalido("O estorno exige justificativa (ISC-ADR-16).")

    unidades = list(
        Unidade.objects.select_related("custodia_atual", "modelo").filter(
            movimentacoes__movimentacao=movimentacao
        )
    )
    if not unidades:
        raise EstornoInvalido(
            f"A movimentação #{movimentacao.pk} não tem unidades para estornar."
        )

    _validar(movimentacao, unidades)

    return registrar_movimentacao(
        tipo=TipoMovimentacao.ESTORNO,
        # Invertidos: as unidades voltam de onde foram parar para onde estavam.
        origem=movimentacao.destino,
        destino=movimentacao.origem,
        unidades=unidades,
        autor=autor,
        ocorrido_em=ocorrido_em,
        justificativa=justificativa,
        estorno_de=movimentacao,
        # Estornar uma baixa ou uma entrega de descartável exige tirar a
        # unidade de situação terminal — é exatamente o que o estorno faz.
        permitir_terminal=True,
    )
