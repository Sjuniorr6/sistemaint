"""Máquina de estados de Solicitação e Atribuição (ISC-ADR-08).

As tabelas de transição são estrutura de dados, não `if`s espalhados: dá para
testá-las exaustivamente de forma parametrizada, e transição inválida levanta
exceção de domínio em vez de falhar em silêncio. Mesmo padrão do app Chamados.

Mutação de status acontece SÓ por `_transitar()`, que grava o
`SolicitacaoEvento` na mesma transação.
"""
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from iscas.enums import (
    GeoOrigem,
    StatusAtribuicao,
    StatusSolicitacao,
    TipoMovimentacao,
)
from iscas.models.operacao import (
    Atribuicao,
    ItemSolicitacao,
    Solicitacao,
    SolicitacaoEvento,
)
from iscas.services import reserva as reserva_service
from iscas.services.custodia import registrar_movimentacao
from iscas.services.exceptions import (
    GeocodificacaoFalhou,
    MovimentacaoInvalida,
    SaldoInsuficiente,
    TransicaoInvalida,
)

# ---------------------------------------------------------------------------
# Tabelas de transição (ISC-ADR-08)
# ---------------------------------------------------------------------------

#: Solicitação: de → conjunto de destinos válidos.
#: `ATRIBUIDA → ABERTA` cobre o cancelamento da última atribuição ativa.
TRANSICOES_SOLICITACAO = {
    StatusSolicitacao.ABERTA: {
        StatusSolicitacao.ATRIBUIDA,
        StatusSolicitacao.CANCELADA,
    },
    StatusSolicitacao.ATRIBUIDA: {
        StatusSolicitacao.ABERTA,
        StatusSolicitacao.EM_ROTA,
        StatusSolicitacao.ENTREGUE,
        StatusSolicitacao.CANCELADA,
    },
    StatusSolicitacao.EM_ROTA: {
        # `ABERTA`: a última atribuição ativa saiu de cena — por entrega
        # parcial ou cancelamento — e a cobertura não fechou. A solicitação
        # volta a ser um pedido sem ninguém atendendo, exatamente como o
        # caminho `ATRIBUIDA → ABERTA`. Sem esta transição, confirmar a entrega
        # de uma atribuição EM_ROTA que não cobre o pedido inteiro estourava
        # `TransicaoInvalida` e travava o fluxo.
        StatusSolicitacao.ABERTA,
        StatusSolicitacao.ATRIBUIDA,
        StatusSolicitacao.ENTREGUE,
        StatusSolicitacao.CANCELADA,
    },
    # Terminais: não admitem saída.
    StatusSolicitacao.ENTREGUE: set(),
    StatusSolicitacao.CANCELADA: set(),
}

#: Atribuição: de → conjunto de destinos válidos.
TRANSICOES_ATRIBUICAO = {
    StatusAtribuicao.RESERVADA: {
        StatusAtribuicao.EM_ROTA,
        StatusAtribuicao.ENTREGUE,
        StatusAtribuicao.CANCELADA,
    },
    StatusAtribuicao.EM_ROTA: {
        StatusAtribuicao.ENTREGUE,
        StatusAtribuicao.CANCELADA,
    },
    StatusAtribuicao.ENTREGUE: set(),
    StatusAtribuicao.CANCELADA: set(),
}


def _transitar(*, solicitacao, novo_status, autor, atribuicao=None, dados=None):
    """Muda o status e grava o evento. Ponto único de mutação."""
    tabela = TRANSICOES_ATRIBUICAO if atribuicao else TRANSICOES_SOLICITACAO
    alvo = atribuicao or solicitacao
    atual = alvo.status

    if novo_status not in tabela.get(atual, set()):
        rotulo = "Atribuição" if atribuicao else "Solicitação"
        raise TransicaoInvalida(
            f"{rotulo}: transição {atual} → {novo_status} não é permitida."
        )

    alvo.status = novo_status
    alvo.save(update_fields=["status", "updated_at"])

    SolicitacaoEvento.objects.create(
        solicitacao=solicitacao,
        atribuicao=atribuicao,
        status_anterior=atual,
        status_novo=novo_status,
        autor=autor,
        dados=dados or {},
    )
    return alvo


# ---------------------------------------------------------------------------
# Solicitação
# ---------------------------------------------------------------------------


#: Campos que a solicitação copia do cliente quando o operador não informa.
#: São dados de CONTATO E ENTREGA — o nome fica de fora de propósito: vem
#: sempre da FK, para não existirem duas versões da mesma identidade.
_CAMPOS_DO_CLIENTE = {
    "documento": "documento",
    "email": "email",
    "contato_nome": "contato_nome",
    "telefone": "telefone",
    "comercial_responsavel": "comercial_responsavel",
    "entrega_logradouro": "logradouro",
    "entrega_numero": "numero",
    "entrega_complemento": "complemento",
    "entrega_bairro": "bairro",
    "entrega_cidade": "cidade",
    "entrega_uf": "uf",
    "entrega_cep": "cep",
}


def dados_de_entrega(cliente, informados=None):
    """Resolve os dados de contato e entrega da solicitação.

    O que o operador informou vence; o resto vem do cadastro do cliente. É o
    que permite entregar numa obra sem sobrescrever o endereço principal, e
    mantém a solicitação completa mesmo quando a tela manda só o que mudou.
    """
    informados = informados or {}
    resolvidos = {}
    for campo, origem in _CAMPOS_DO_CLIENTE.items():
        valor = informados.get(campo)
        if valor in (None, ""):
            valor = getattr(cliente, origem, "") or ""
        resolvidos[campo] = valor
    return resolvidos


def resolver_coordenada_de_entrega(solicitacao, *, pin=None, salvar=True):
    """Resolve a coordenada do ponto de entrega (ISC-RF-02 aplicado à entrega).

    Args:
        pin: `(latitude, longitude)` quando o operador posicionou o pin à mão.
            Vence a geocodificação — ele está olhando o mapa, o provedor não.

    Chamada FORA da transação de abertura: é I/O de rede com timeout, e
    segurar a transação por três segundos à espera do Nominatim trava linhas
    sem necessidade. Falha aqui nunca desfaz a solicitação — ela fica
    `PENDENTE` e o operador ajusta o pin depois.

    Returns:
        True se gravou coordenada.
    """
    from iscas.services.geo import coordenada_valida, geocodificar

    if pin is not None:
        coordenada = coordenada_valida(*pin)
        if coordenada is not None:
            solicitacao.entrega_latitude, solicitacao.entrega_longitude = coordenada
            solicitacao.entrega_geo_origem = GeoOrigem.MANUAL
            if salvar:
                solicitacao.save(
                    update_fields=[
                        "entrega_latitude", "entrega_longitude",
                        "entrega_geo_origem", "updated_at",
                    ]
                )
            return True

    endereco = solicitacao.entrega_para_geocodificacao
    if not endereco:
        return False

    try:
        latitude, longitude = geocodificar(endereco)
    except GeocodificacaoFalhou:
        # Degradação graciosa: a solicitação existe, só não entra na busca por
        # proximidade até alguém posicionar o pin.
        return False

    solicitacao.entrega_latitude = latitude
    solicitacao.entrega_longitude = longitude
    solicitacao.entrega_geo_origem = GeoOrigem.GEOCODIFICADO
    if salvar:
        solicitacao.save(
            update_fields=[
                "entrega_latitude", "entrega_longitude",
                "entrega_geo_origem", "updated_at",
            ]
        )
    return True


@transaction.atomic
def abrir_solicitacao(
    *,
    cliente,
    itens,
    autor,
    observacao="",
    prazo_desejado=None,
    aberta_em=None,
    **dados_entrega,
):
    """Registra a solicitação de um cliente (ISC-RF-22).

    Args:
        itens: lista de `(modelo, quantidade)`.
        **dados_entrega: contato e endereço específicos desta entrega
            (`documento`, `email`, `telefone`, `entrega_logradouro`…). O que
            não vier é copiado do cadastro do cliente.

    A coordenada da entrega NÃO é resolvida aqui: quem chama faz isso com
    `resolver_coordenada_de_entrega`, fora desta transação, porque é I/O de
    rede. Ver a docstring de lá.
    """
    if not itens:
        raise MovimentacaoInvalida("A solicitação precisa de ao menos um item.")

    solicitacao = Solicitacao.objects.create(
        cliente=cliente,
        aberta_em=aberta_em or timezone.now(),
        aberta_por=autor,
        observacao=observacao,
        prazo_desejado=prazo_desejado,
        status=StatusSolicitacao.ABERTA,
        **dados_de_entrega(cliente, dados_entrega),
    )
    for modelo, quantidade in itens:
        if quantidade < 1:
            raise MovimentacaoInvalida(
                f"A quantidade de {modelo} precisa ser positiva."
            )
        ItemSolicitacao.objects.create(
            solicitacao=solicitacao, modelo=modelo, quantidade=quantidade
        )

    SolicitacaoEvento.objects.create(
        solicitacao=solicitacao,
        status_anterior="",
        status_novo=StatusSolicitacao.ABERTA,
        autor=autor,
        dados={"itens": [[m.pk, q] for m, q in itens]},
    )
    return solicitacao


def cobertura(solicitacao):
    """Quanto de cada modelo já está atribuído sobre o pedido (ISC-RF-30).

    Returns:
        Lista de dicts com modelo, solicitado, atribuido e falta.
    """
    from iscas.models.operacao import AtribuicaoUnidade

    reservas = (
        AtribuicaoUnidade.objects.filter(
            atribuicao__solicitacao=solicitacao,
            atribuicao__status__in=(
                StatusAtribuicao.RESERVADA,
                StatusAtribuicao.EM_ROTA,
            ),
            liberada_em__isnull=True,
        )
        .values_list("unidade__modelo_id", flat=True)
    )
    entregues = (
        AtribuicaoUnidade.objects.filter(
            atribuicao__solicitacao=solicitacao,
            atribuicao__status=StatusAtribuicao.ENTREGUE,
        )
        .values_list("unidade__modelo_id", flat=True)
    )

    contagem = {}
    for modelo_id in list(reservas) + list(entregues):
        contagem[modelo_id] = contagem.get(modelo_id, 0) + 1

    resultado = []
    for item in solicitacao.itens.select_related("modelo"):
        atribuido = contagem.get(item.modelo_id, 0)
        resultado.append(
            {
                "modelo": item.modelo,
                "solicitado": item.quantidade,
                "atribuido": atribuido,
                "falta": max(item.quantidade - atribuido, 0),
            }
        )
    return resultado


def cobertura_em_lote(solicitacoes):
    """Cobertura de várias solicitações em duas consultas, não N por item.

    Mesma semântica de `cobertura()`, mas agregando de uma vez: o mapa lista
    todas as solicitações em aberto, e chamar `cobertura()` num laço custa
    ~3 consultas por solicitação — N+1 que degrada conforme a operação cresce.

    Returns:
        `{solicitacao_id: [linhas de cobertura]}`, no formato de `cobertura()`.
    """
    from iscas.models.operacao import AtribuicaoUnidade, ItemSolicitacao

    solicitacoes = list(solicitacoes)
    if not solicitacoes:
        return {}

    ids = [s.pk for s in solicitacoes]

    # Uma consulta para tudo que conta como atribuído: reservas ativas de
    # atribuições vivas + todas as unidades já entregues.
    contagem = {}
    linhas = (
        AtribuicaoUnidade.objects.filter(atribuicao__solicitacao_id__in=ids)
        .filter(
            Q(
                atribuicao__status__in=(
                    StatusAtribuicao.RESERVADA,
                    StatusAtribuicao.EM_ROTA,
                ),
                liberada_em__isnull=True,
            )
            | Q(atribuicao__status=StatusAtribuicao.ENTREGUE)
        )
        .values("atribuicao__solicitacao_id", "unidade__modelo_id")
        .annotate(total=Count("id"))
    )
    for linha in linhas:
        chave = (linha["atribuicao__solicitacao_id"], linha["unidade__modelo_id"])
        contagem[chave] = linha["total"]

    # E uma para os itens pedidos.
    resultado = {pk: [] for pk in ids}
    itens = (
        ItemSolicitacao.objects.filter(solicitacao_id__in=ids)
        .select_related("modelo")
        .order_by("modelo__nome")
    )
    for item in itens:
        atribuido = contagem.get((item.solicitacao_id, item.modelo_id), 0)
        resultado[item.solicitacao_id].append(
            {
                "modelo": item.modelo,
                "solicitado": item.quantidade,
                "atribuido": atribuido,
                "falta": max(item.quantidade - atribuido, 0),
            }
        )
    return resultado


def cobertura_total(solicitacao) -> bool:
    """Todos os itens têm atribuição suficiente?"""
    return all(linha["falta"] == 0 for linha in cobertura(solicitacao))


@transaction.atomic
def cancelar_solicitacao(*, solicitacao, motivo, autor):
    """Cancela a solicitação e libera TODAS as reservas ativas (ISC-RN-09)."""
    if not (motivo or "").strip():
        raise MovimentacaoInvalida("O cancelamento exige motivo (ISC-RN-09).")

    for atribuicao in solicitacao.atribuicoes_ativas():
        _cancelar_atribuicao_sem_recalculo(
            atribuicao=atribuicao,
            motivo=f"Solicitação cancelada: {motivo}",
            autor=autor,
        )

    solicitacao.motivo_cancelamento = motivo
    solicitacao.save(update_fields=["motivo_cancelamento", "updated_at"])
    return _transitar(
        solicitacao=solicitacao,
        novo_status=StatusSolicitacao.CANCELADA,
        autor=autor,
        dados={"motivo": motivo},
    )


@transaction.atomic
def excluir_solicitacao(*, solicitacao, autor, motivo=""):
    """Soft delete: some da operação, permanece no banco (ISC-ADR-15).

    É diferente de cancelar, e a diferença importa:

    - **Cancelar** é evento de negócio — o cliente desistiu, a entrega caiu.
      Libera reservas, exige motivo e a solicitação CONTINUA na lista, com o
      status CANCELADA, porque aconteceu de verdade.
    - **Excluir** é correção de cadastro — duplicata, erro de digitação, teste.
      Ela some da operação porque nunca deveria ter existido.

    Nunca deleta de fato: `is_active=False`. O histórico de eventos aponta para
    a solicitação com `PROTECT`, e a trilha é append-only (ISC-RN-17) — apagar
    a linha arrancaria o passado junto.

    Raises:
        MovimentacaoInvalida: há reserva ativa. Excluir com reserva de pé
            deixaria unidades presas a uma solicitação invisível: some da tela
            e o estoque continua bloqueado, sem ninguém para liberar. Cancele
            primeiro — o cancelamento libera — e então exclua.
    """
    ativas = list(solicitacao.atribuicoes_ativas())
    if ativas:
        nomes = ", ".join(sorted({a.agente.nome for a in ativas}))
        raise MovimentacaoInvalida(
            f"Esta solicitação tem {len(ativas)} atribuição(ões) ativa(s) "
            f"com {nomes}, segurando unidades reservadas. Cancele a "
            "solicitação primeiro — isso devolve as unidades ao saldo — e "
            "só então exclua."
        )

    if not solicitacao.is_active:
        return solicitacao

    solicitacao.desativar()

    # A exclusão entra na trilha como qualquer outra mudança: quem excluiu,
    # quando e por quê. Sem isso, "sumiu da lista" vira mistério.
    SolicitacaoEvento.objects.create(
        solicitacao=solicitacao,
        status_anterior=solicitacao.status,
        status_novo="EXCLUIDA",
        autor=autor,
        dados={"motivo": motivo} if motivo else {},
    )
    return solicitacao


def restaurar_solicitacao(*, solicitacao, autor):
    """Desfaz a exclusão (ISC-ADR-15).

    Soft delete só vale a pena se der para voltar; sem isto, "excluir" é
    irreversível na prática e o operador fica com medo de usar.
    """
    if solicitacao.is_active:
        return solicitacao

    solicitacao.reativar()
    SolicitacaoEvento.objects.create(
        solicitacao=solicitacao,
        status_anterior="EXCLUIDA",
        status_novo=solicitacao.status,
        autor=autor,
    )
    return solicitacao


# ---------------------------------------------------------------------------
# Atribuição
# ---------------------------------------------------------------------------


def _validar_contra_o_pedido(solicitacao, itens):
    """A atribuição não pode ultrapassar o que o cliente pediu.

    Duas regras, ambas do mesmo princípio — o pedido é o contrato:

    1. **Modelo não solicitado é recusado.** Além de entregar o que não foi
       pedido, essas unidades não aparecem na cobertura (que percorre os itens
       da solicitação), então a solicitação nunca fecharia — ficaria com
       estoque preso numa reserva invisível.
    2. **A soma das atribuições não pode exceder a quantidade pedida.** Conta o
       que já está atribuído, para que duas atribuições parciais não passem do
       total por acumulação.
    """
    pedido = {
        item.modelo_id: item.quantidade
        for item in solicitacao.itens.select_related("modelo")
    }
    ja_atribuido = {
        linha["modelo"].pk: linha["atribuido"] for linha in cobertura(solicitacao)
    }

    for modelo, quantidade in itens:
        if modelo.pk not in pedido:
            raise MovimentacaoInvalida(
                f"{modelo} não faz parte desta solicitação. "
                "Edite o pedido do cliente antes de atribuir este modelo."
            )

        disponivel_no_pedido = pedido[modelo.pk] - ja_atribuido.get(modelo.pk, 0)
        if quantidade > disponivel_no_pedido:
            solicitado = pedido[modelo.pk]
            atribuido = ja_atribuido.get(modelo.pk, 0)
            if disponivel_no_pedido <= 0:
                raise MovimentacaoInvalida(
                    f"{modelo} já está totalmente atendido nesta solicitação "
                    f"({atribuido} de {solicitado}). Para enviar mais, aumente "
                    "a quantidade do pedido."
                )
            raise MovimentacaoInvalida(
                f"O cliente pediu {solicitado} de {modelo} e já há {atribuido} "
                f"atribuída(s): cabem no máximo {disponivel_no_pedido}, "
                f"não {quantidade}."
            )


@transaction.atomic
def criar_atribuicao(*, solicitacao, agente, itens, autor, unidades_por_modelo=None):
    """Cria a atribuição e reserva as unidades (ISC-RF-23, ISC-RF-24).

    Args:
        itens: lista de `(modelo, quantidade)` que este agente vai levar.
        unidades_por_modelo: dict `{modelo_id: [Unidade]}` quando o operador
            escolhe unidades específicas (ISC-RF-25).

    A reserva NÃO move custódia: as unidades continuam com o agente, apenas
    ficam indisponíveis para outra solicitação (ISC-RN-07, ISC-RN-08).
    """
    if solicitacao.eh_terminal:
        raise TransicaoInvalida(
            f"A solicitação está {solicitacao.status} e não aceita nova atribuição."
        )
    if not agente.is_active:
        raise MovimentacaoInvalida(
            f"{agente} está desativado e não recebe novas atribuições (ISC-RN-18)."
        )
    if not itens:
        raise MovimentacaoInvalida("A atribuição precisa de ao menos um item.")

    _validar_contra_o_pedido(solicitacao, itens)

    atribuicao = Atribuicao.objects.create(
        solicitacao=solicitacao,
        agente=agente,
        criada_por=autor,
        status=StatusAtribuicao.RESERVADA,
    )

    reservadas = []
    for modelo, quantidade in itens:
        escolhidas = (unidades_por_modelo or {}).get(modelo.pk)
        reservadas.extend(
            reserva_service.alocar_unidades(
                agente=agente,
                modelo=modelo,
                quantidade=quantidade,
                atribuicao=atribuicao,
                unidades=escolhidas,
            )
        )

    SolicitacaoEvento.objects.create(
        solicitacao=solicitacao,
        atribuicao=atribuicao,
        status_anterior="",
        status_novo=StatusAtribuicao.RESERVADA,
        autor=autor,
        dados={
            "agente": agente.pk,
            "unidades": [u.identificador for u in reservadas],
        },
    )

    if solicitacao.status == StatusSolicitacao.ABERTA:
        _transitar(
            solicitacao=solicitacao,
            novo_status=StatusSolicitacao.ATRIBUIDA,
            autor=autor,
        )
    return atribuicao


@transaction.atomic
def marcar_em_rota(*, atribuicao, autor, momento=None):
    """Agente saiu para entregar (ISC-RF-26)."""
    momento = momento or timezone.now()
    atribuicao.em_rota_em = momento
    atribuicao.save(update_fields=["em_rota_em", "updated_at"])

    _transitar(
        solicitacao=atribuicao.solicitacao,
        atribuicao=atribuicao,
        novo_status=StatusAtribuicao.EM_ROTA,
        autor=autor,
    )

    solicitacao = atribuicao.solicitacao
    if solicitacao.status == StatusSolicitacao.ATRIBUIDA:
        _transitar(
            solicitacao=solicitacao,
            novo_status=StatusSolicitacao.EM_ROTA,
            autor=autor,
        )
    return atribuicao


@transaction.atomic
def confirmar_entrega(
    *, atribuicao, autor, entregue_em=None, recebido_por="", justificativa=""
):
    """Transfere a custódia das unidades ao cliente (ISC-RF-27, ISC-RN-08).

    É AQUI que o estoque se move — a atribuição por si só não movimentou nada.
    Numa transação: lançamento de ENTREGA, liberação das reservas (a unidade
    saiu do agente, a reserva perdeu o objeto), transição de status e evento.
    """
    if atribuicao.eh_terminal:
        raise TransicaoInvalida(
            f"A atribuição já está {atribuicao.status}."
        )

    momento = entregue_em or timezone.now()
    unidades = list(reserva_service.unidades_reservadas(atribuicao))
    if not unidades:
        raise SaldoInsuficiente(
            "A atribuição não tem unidades reservadas para entregar."
        )

    movimentacao = registrar_movimentacao(
        tipo=TipoMovimentacao.ENTREGA,
        origem=atribuicao.agente,
        destino=atribuicao.solicitacao.cliente,
        unidades=unidades,
        autor=autor,
        ocorrido_em=momento,
        justificativa=justificativa,
        solicitacao=atribuicao.solicitacao,
        atribuicao=atribuicao,
    )

    # As unidades deixaram a custódia do agente: a reserva sobre elas não tem
    # mais objeto. Liberar aqui mantém "reserva ativa" significando exatamente
    # "unidade com o agente, comprometida com uma atribuição".
    reserva_service.liberar_reservas(atribuicao, momento=momento)

    atribuicao.entregue_em = momento
    atribuicao.recebido_por = recebido_por
    atribuicao.save(update_fields=["entregue_em", "recebido_por", "updated_at"])

    _transitar(
        solicitacao=atribuicao.solicitacao,
        atribuicao=atribuicao,
        novo_status=StatusAtribuicao.ENTREGUE,
        autor=autor,
        dados={
            "movimentacao": movimentacao.pk,
            "recebido_por": recebido_por,
            "unidades": [u.identificador for u in unidades],
        },
    )

    _recalcular_status_solicitacao(solicitacao=atribuicao.solicitacao, autor=autor)
    return movimentacao


def _cancelar_atribuicao_sem_recalculo(*, atribuicao, motivo, autor):
    """Libera as reservas e marca CANCELADA, sem mexer na solicitação."""
    if atribuicao.eh_terminal:
        raise TransicaoInvalida(f"A atribuição já está {atribuicao.status}.")

    liberadas = reserva_service.liberar_reservas(atribuicao)
    atribuicao.motivo_cancelamento = motivo
    atribuicao.save(update_fields=["motivo_cancelamento", "updated_at"])

    return _transitar(
        solicitacao=atribuicao.solicitacao,
        atribuicao=atribuicao,
        novo_status=StatusAtribuicao.CANCELADA,
        autor=autor,
        dados={"motivo": motivo, "reservas_liberadas": liberadas},
    )


@transaction.atomic
def cancelar_atribuicao(*, atribuicao, motivo, autor):
    """Cancela a atribuição e devolve as unidades ao saldo (ISC-RN-09).

    Não gera lançamento: nada mudou de custódia — as unidades nunca saíram do
    agente.
    """
    if not (motivo or "").strip():
        raise MovimentacaoInvalida("O cancelamento exige motivo (ISC-RN-09).")

    _cancelar_atribuicao_sem_recalculo(
        atribuicao=atribuicao, motivo=motivo, autor=autor
    )
    _recalcular_status_solicitacao(solicitacao=atribuicao.solicitacao, autor=autor)
    return atribuicao


def _recalcular_status_solicitacao(*, solicitacao, autor):
    """Ajusta o status da solicitação ao estado das suas atribuições.

    ENTREGUE exige as duas condições do ISC-RN-10: todas as atribuições ativas
    entregues E cobertura total. Uma solicitação de 20 com uma entrega de 12
    continua ATRIBUIDA — o resto ainda falta.
    """
    solicitacao.refresh_from_db()
    if solicitacao.eh_terminal:
        return solicitacao

    ativas = solicitacao.atribuicoes_ativas()
    entregues = solicitacao.atribuicoes.filter(status=StatusAtribuicao.ENTREGUE)

    if not ativas.exists():
        if entregues.exists() and cobertura_total(solicitacao):
            return _transitar(
                solicitacao=solicitacao,
                novo_status=StatusSolicitacao.ENTREGUE,
                autor=autor,
            )
        # Sem atribuição ativa e sem cobertura: voltou a ser um pedido em aberto.
        if solicitacao.status != StatusSolicitacao.ABERTA:
            return _transitar(
                solicitacao=solicitacao,
                novo_status=StatusSolicitacao.ABERTA,
                autor=autor,
            )
        return solicitacao

    # Ainda há atribuição ativa: EM_ROTA se alguma saiu, senão ATRIBUIDA.
    alguma_em_rota = ativas.filter(status=StatusAtribuicao.EM_ROTA).exists()
    desejado = (
        StatusSolicitacao.EM_ROTA if alguma_em_rota else StatusSolicitacao.ATRIBUIDA
    )
    if solicitacao.status != desejado:
        return _transitar(
            solicitacao=solicitacao, novo_status=desejado, autor=autor
        )
    return solicitacao
