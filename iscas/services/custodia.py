"""Ponto de escrita único do livro-razão (ISC-ADR-02, ISC-ADR-04).

`registrar_movimentacao()` é a ÚNICA função autorizada a criar `Movimentacao` /
`MovimentacaoUnidade` e a atualizar os ponteiros de projeção da `Unidade`. Todos
os demais services — entrada, transferência, baixa, entrega, retorno,
manutenção, estorno — passam por aqui; nenhum escreve nesses models direto.

É um gargalo deliberado. A alternativa seria depender de disciplina distribuída
pelo código: cada service lembrando de atualizar `custodia_atual`, de gravar o
momento, de não mover unidade terminal. Um esquecimento em qualquer um deles
corrompe o saldo de todo mundo. Com o gargalo, as invariantes são verificadas
num lugar só, e um teste de arquitetura garante que ninguém contorne
(`tests/test_arquitetura.py`).
"""
from django.db import transaction
from django.utils import timezone

from iscas.enums import (
    CUSTODIAS_SINGLETON,
    MotivoBaixa,
    TipoCustodia,
    TipoModelo,
    TipoMovimentacao,
)
from iscas.models.custodia import Custodia, Movimentacao, MovimentacaoUnidade, Unidade
from iscas.services.exceptions import MovimentacaoInvalida, UnidadeTerminal

#: Tipos de lançamento que exigem justificativa textual (ISC-RN-13).
_EXIGEM_JUSTIFICATIVA = {TipoMovimentacao.BAIXA, TipoMovimentacao.ESTORNO}


def custodia_singleton(tipo):
    """Devolve a conta singleton (EXTERNO, MANUTENCAO ou BAIXA)."""
    if tipo not in CUSTODIAS_SINGLETON:
        raise MovimentacaoInvalida(f"{tipo} não é uma custódia singleton.")
    try:
        return Custodia.todos.get(tipo=tipo)
    except Custodia.DoesNotExist as exc:
        raise MovimentacaoInvalida(
            f"Custódia singleton {tipo} não existe. "
            "Rode as migrations do app iscas (0002_custodias_singleton)."
        ) from exc


def custodia_de(entidade):
    """Conta de um Agente, Cliente ou Depósito, criando-a se faltar.

    A conta normalmente nasce por signal junto com a entidade. Quando não
    nasceu — dado importado por fixture, criado com `bulk_create` (que não
    dispara signal) ou migrado de outro sistema — criamos aqui, em vez de
    derrubar a página.

    A criação é segura porque a conta é **vazia por construção**: uma custódia
    recém-criada não tem nenhuma unidade apontando para ela, então o saldo
    derivado é zero e nada no livro-razão muda. É reparo de cadastro, não de
    estoque — o oposto de mascarar um problema de saldo.
    """
    from iscas.models.cadastro import Agente, Cliente, Deposito

    if isinstance(entidade, Custodia):
        return entidade

    config = {
        Agente: ("agente", TipoCustodia.AGENTE),
        Cliente: ("cliente", TipoCustodia.CLIENTE),
        Deposito: ("deposito", TipoCustodia.DEPOSITO),
    }.get(type(entidade))

    if config is None:
        raise MovimentacaoInvalida(
            f"{type(entidade).__name__} não possui conta de custódia."
        )

    campo, tipo = config
    custodia, _ = Custodia.todos.get_or_create(
        **{campo: entidade}, defaults={"tipo": tipo}
    )
    return custodia


def _validar_origem(unidades, origem, *, permitir_terminal=False):
    """Toda unidade precisa estar na origem declarada e não ser terminal.

    A checagem de custódia é o que impede um lançamento de "mover" uma unidade
    que na verdade está em outro lugar — o erro que silenciosamente duplicaria
    estoque.
    """
    fora = [u for u in unidades if u.custodia_atual_id != origem.pk]
    if fora:
        exemplos = ", ".join(u.identificador for u in fora[:5])
        raise MovimentacaoInvalida(
            f"{len(fora)} unidade(s) não estão em {origem}: {exemplos}"
            f"{'…' if len(fora) > 5 else ''}"
        )
    if permitir_terminal:
        return
    terminais = [u for u in unidades if _eh_terminal(u)]
    if terminais:
        exemplos = ", ".join(u.identificador for u in terminais[:5])
        raise UnidadeTerminal(
            f"{len(terminais)} unidade(s) em situação terminal não podem ser "
            f"movimentadas (ISC-RN-05): {exemplos}{'…' if len(terminais) > 5 else ''}"
        )


def _eh_terminal(unidade) -> bool:
    """CONSUMIDA (descartável com cliente) ou BAIXADA — não há saída."""
    tipo_custodia = unidade.custodia_atual.tipo
    if tipo_custodia == TipoCustodia.BAIXA:
        return True
    return (
        tipo_custodia == TipoCustodia.CLIENTE
        and unidade.modelo.tipo == TipoModelo.DESCARTAVEL
    )


@transaction.atomic
def registrar_movimentacao(
    *,
    tipo,
    origem,
    destino,
    unidades,
    autor,
    ocorrido_em=None,
    justificativa="",
    motivo_baixa="",
    nota_fiscal="",
    lote="",
    solicitacao=None,
    atribuicao=None,
    estorno_de=None,
    permitir_terminal=False,
):
    """Grava um lançamento e atualiza os ponteiros das unidades. Atômico.

    Args:
        tipo: `TipoMovimentacao`.
        origem/destino: `Custodia`, ou entidade (Agente/Cliente/Deposito).
        unidades: iterável de `Unidade`. Não pode ser vazio — lançamento sem
            linha não significa nada e ainda inflaria o extrato.
        autor: usuário responsável. Sempre explícito: services nunca leem
            `request` (ARCHITECTURE, "Service Layer").
        ocorrido_em: momento real do fato. Default: agora. A diferença para
            `created_at` é a defasagem operacional, medida de propósito.
        permitir_terminal: só o estorno usa — é o único caminho legítimo para
            tirar uma unidade de situação terminal, desfazendo o lançamento que
            a colocou lá.

    Returns:
        A `Movimentacao` criada.
    """
    origem = custodia_de(origem)
    destino = custodia_de(destino)
    unidades = list(unidades)

    if not unidades:
        raise MovimentacaoInvalida("Movimentação exige ao menos uma unidade.")
    if origem.pk == destino.pk:
        raise MovimentacaoInvalida(
            f"Origem e destino são a mesma custódia ({origem}); nada mudaria de posse."
        )
    if tipo in _EXIGEM_JUSTIFICATIVA and not justificativa.strip():
        raise MovimentacaoInvalida(
            f"Movimentação do tipo {tipo} exige justificativa (ISC-RN-13)."
        )
    if tipo == TipoMovimentacao.BAIXA and motivo_baixa not in MotivoBaixa.values:
        raise MovimentacaoInvalida("Baixa exige motivo válido (ISC-RN-13).")
    if motivo_baixa and tipo != TipoMovimentacao.BAIXA:
        raise MovimentacaoInvalida("Motivo de baixa só se aplica a lançamento de baixa.")
    if tipo == TipoMovimentacao.ESTORNO and estorno_de is None:
        raise MovimentacaoInvalida("Estorno precisa referenciar a movimentação original.")
    if estorno_de is not None and tipo != TipoMovimentacao.ESTORNO:
        raise MovimentacaoInvalida("`estorno_de` só se aplica a lançamento de estorno.")

    # Relê as unidades travadas e já com os relacionados que a validação usa.
    # No PostgreSQL `select_for_update` trava as linhas até o fim da transação;
    # no SQLite deste projeto ele é ignorado pelo Django — a serialização vem
    # do lock de escrita do próprio banco. Ver `services/reserva.py`.
    ids = [u.pk for u in unidades]
    unidades = list(
        Unidade.objects.select_for_update()
        .select_related("custodia_atual", "modelo")
        .filter(pk__in=ids)
    )
    if len(unidades) != len(set(ids)):
        raise MovimentacaoInvalida("Alguma unidade informada não existe mais.")

    _validar_origem(unidades, origem, permitir_terminal=permitir_terminal)

    momento = ocorrido_em or timezone.now()

    movimentacao = Movimentacao.objects.create(
        tipo=tipo,
        origem=origem,
        destino=destino,
        autor=autor,
        ocorrido_em=momento,
        justificativa=justificativa,
        motivo_baixa=motivo_baixa,
        nota_fiscal=nota_fiscal,
        lote=lote,
        solicitacao=solicitacao,
        atribuicao=atribuicao,
        estorno_de=estorno_de,
    )

    MovimentacaoUnidade.objects.bulk_create(
        [
            MovimentacaoUnidade(movimentacao=movimentacao, unidade=unidade)
            for unidade in unidades
        ]
    )

    # Ponteiros de projeção, na MESMA transação do lançamento (ISC-ADR-04).
    # Se isto falhar, o lançamento também reverte — nunca fica livro sem
    # projeção nem projeção sem livro.
    Unidade.objects.filter(pk__in=[u.pk for u in unidades]).update(
        custodia_atual=destino,
        custodia_desde=momento,
        ultima_movimentacao=movimentacao,
        updated_at=timezone.now(),
    )

    return movimentacao


@transaction.atomic
def criar_unidades(*, modelo, identificadores, custodia_inicial, gerados=False):
    """Cria unidades ainda SEM lançamento, prontas para a movimentação de entrada.

    Uso restrito ao service de entrada: a unidade nasce apontando para a
    custódia de origem do lançamento (tipicamente EXTERNO) e é
    `registrar_movimentacao()` que a move para o destino real. Assim toda
    unidade que existe no sistema tem lançamento de entrada — não há unidade
    que apareça no estoque sem constar no livro.
    """
    agora = timezone.now()
    unidades = [
        Unidade(
            modelo=modelo,
            identificador=identificador,
            identificador_gerado=gerados,
            custodia_atual=custodia_inicial,
            custodia_desde=agora,
        )
        for identificador in identificadores
    ]
    return Unidade.objects.bulk_create(unidades)
