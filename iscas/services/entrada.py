"""Entrada de equipamento novo no estoque (ISC-RF-07, ISC-RF-08, ISC-RF-09).

A entrada é o lançamento EXTERNO → Depósito/Agente. As unidades nascem na conta
EXTERNO e a movimentação as move para o destino real — assim nenhuma unidade
existe no sistema sem constar no livro.
"""
import re

from django.db import IntegrityError, transaction
from django.utils import timezone

from iscas.enums import TipoCustodia, TipoMovimentacao
from iscas.models.custodia import Unidade
from iscas.services.custodia import (
    criar_unidades,
    custodia_de,
    custodia_singleton,
    registrar_movimentacao,
)
from iscas.services.exceptions import MovimentacaoInvalida

_ESPACOS = re.compile(r"[\s;,]+")


def parse_identificadores(texto: str) -> list[str]:
    """Extrai identificadores de um texto colado (um por linha, ISC-RF-08).

    Aceita separação por quebra de linha, vírgula, ponto-e-vírgula ou espaço —
    o operador cola do Excel, do WhatsApp ou de um e-mail, e o formato varia.
    Preserva a ordem e remove duplicatas dentro da própria colagem.
    """
    if not texto:
        return []
    brutos = [p.strip() for p in _ESPACOS.split(texto) if p.strip()]
    vistos = set()
    unicos = []
    for identificador in brutos:
        if identificador not in vistos:
            vistos.add(identificador)
            unicos.append(identificador)
    return unicos


def gerar_faixa(*, prefixo: str, inicio: int, quantidade: int, digitos: int = 6) -> list[str]:
    """Faixa sequencial com prefixo (ISC-RF-08).

    `gerar_faixa(prefixo="ISC", inicio=1, quantidade=3)` →
    ["ISC000001", "ISC000002", "ISC000003"].
    """
    if quantidade < 1:
        raise MovimentacaoInvalida("A quantidade da faixa precisa ser positiva.")
    return [f"{prefixo}{str(inicio + i).zfill(digitos)}" for i in range(quantidade)]


def gerar_identificadores_internos(*, modelo, quantidade: int) -> list[str]:
    """Identificadores internos para unidades sem número de fábrica (ISC-RF-09).

    Formato `GS-<CODIGO>-<sequencial>`. O sequencial parte do maior já usado
    para aquele modelo, e a unicidade real é imposta pelo UNIQUE de
    `Unidade.identificador` — sob concorrência, a colisão vira `IntegrityError`
    tratado por quem chama.

    Modelo sem código — o campo é opcional — cai para a PK: `GS-M12-000001`.
    Interpolar o código vazio produziria `GS--000001`, que é igual para TODOS
    os modelos sem código e faria as faixas de modelos diferentes colidirem
    entre si no UNIQUE de `identificador`.
    """
    prefixo = f"GS-{modelo.codigo}-" if modelo.codigo else f"GS-M{modelo.pk}-"
    ultimo = (
        Unidade.objects.filter(identificador__startswith=prefixo)
        .order_by("-identificador")
        .values_list("identificador", flat=True)
        .first()
    )
    proximo = 1
    if ultimo:
        sufixo = ultimo[len(prefixo):]
        if sufixo.isdigit():
            proximo = int(sufixo) + 1
    return [f"{prefixo}{str(proximo + i).zfill(6)}" for i in range(quantidade)]


def identificadores_existentes(identificadores) -> list[str]:
    """Quais destes identificadores já estão cadastrados."""
    return list(
        Unidade.objects.filter(identificador__in=identificadores).values_list(
            "identificador", flat=True
        )
    )


@transaction.atomic
def registrar_entrada(
    *,
    modelo,
    identificadores,
    destino,
    autor,
    ocorrido_em=None,
    nota_fiscal="",
    lote="",
    justificativa="",
    gerar_internos=False,
    quantidade=None,
):
    """Cria as unidades e lança a entrada EXTERNO → destino.

    Args:
        identificadores: lista de identificadores de fábrica. Ignorado quando
            `gerar_internos=True`.
        destino: `Deposito` ou `Agente` que recebe as unidades.
        gerar_internos: gera identificadores internos (ISC-RF-09); exige
            `quantidade`.

    Returns:
        `(movimentacao, unidades)`.
    """
    if gerar_internos:
        if not quantidade or quantidade < 1:
            raise MovimentacaoInvalida(
                "Para gerar identificadores internos, informe a quantidade."
            )
        identificadores = gerar_identificadores_internos(
            modelo=modelo, quantidade=quantidade
        )
    else:
        identificadores = list(identificadores)

    if not identificadores:
        raise MovimentacaoInvalida("Informe ao menos um identificador.")

    duplicados_na_lista = len(identificadores) != len(set(identificadores))
    if duplicados_na_lista:
        raise MovimentacaoInvalida(
            "A lista tem identificadores repetidos; cada unidade é única (ISC-RN-03)."
        )

    ja_existem = identificadores_existentes(identificadores)
    if ja_existem:
        amostra = ", ".join(ja_existem[:5])
        raise MovimentacaoInvalida(
            f"{len(ja_existem)} identificador(es) já cadastrado(s): {amostra}"
            f"{'…' if len(ja_existem) > 5 else ''}"
        )

    conta_externa = custodia_singleton(TipoCustodia.EXTERNO)
    conta_destino = custodia_de(destino)

    if conta_destino.tipo not in (TipoCustodia.DEPOSITO, TipoCustodia.AGENTE):
        raise MovimentacaoInvalida(
            "Entrada só pode destinar equipamento a Depósito ou Agente."
        )

    try:
        unidades = criar_unidades(
            modelo=modelo,
            identificadores=identificadores,
            custodia_inicial=conta_externa,
            gerados=gerar_internos,
        )
    except IntegrityError as exc:
        raise MovimentacaoInvalida(
            "Um dos identificadores foi cadastrado por outra operação agora há "
            "pouco. Revise a lista e tente novamente."
        ) from exc

    movimentacao = registrar_movimentacao(
        tipo=TipoMovimentacao.ENTRADA,
        origem=conta_externa,
        destino=conta_destino,
        unidades=unidades,
        autor=autor,
        ocorrido_em=ocorrido_em or timezone.now(),
        justificativa=justificativa,
        nota_fiscal=nota_fiscal,
        lote=lote,
    )
    return movimentacao, unidades
