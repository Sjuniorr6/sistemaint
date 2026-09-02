"""Consultas de leitura para views e endpoints JSON.

Services escrevem; selectors leem. A serialização do GeoJSON mora aqui porque
não há DRF no projeto (ISC-ADR-12) — é um dicionário montado à mão, com teste
de formato.
"""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from iscas.enums import (
    SituacaoUnidade,
    StatusAtribuicao,
    StatusSolicitacao,
    TipoCustodia,
    TipoModelo,
)
from iscas.models.cadastro import Agente, Cliente, Deposito, ModeloEquipamento
from iscas.models.config import ConfiguracaoIscas
from iscas.models.custodia import Movimentacao, Unidade
from iscas.models.operacao import Atribuicao, Solicitacao
from iscas.services.saldo import saldo_disponivel, saldo_por_modelo


# ---------------------------------------------------------------------------
# Mapa (ISC-RF-16)
# ---------------------------------------------------------------------------


def agentes_geojson(*, modelo=None):
    """GeoJSON dos agentes ativos com coordenada válida.

    O popup precisa de nome, telefone e saldo disponível por modelo — por isso
    o saldo entra nas properties, e não numa segunda chamada por marcador.
    """
    agentes = Agente.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).order_by("nome")

    features = []
    for agente in agentes:
        saldos = [
            {
                "modelo": linha["modelo__nome"],
                "codigo": linha["modelo__codigo"],
                "tipo": linha["modelo__tipo"],
                "total": linha["total"],
                "disponivel": linha["disponivel"],
                "reservado": linha["reservado"],
            }
            for linha in saldo_por_modelo(agente)
        ]
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    # GeoJSON é [longitude, latitude] — nesta ordem.
                    "type": "Point",
                    "coordinates": [float(agente.longitude), float(agente.latitude)],
                },
                "properties": {
                    "id": agente.pk,
                    "nome": agente.nome,
                    "telefone": agente.telefone,
                    "cidade": agente.cidade,
                    "uf": agente.uf,
                    "geo_origem": agente.geo_origem,
                    "saldos": saldos,
                    "disponivel_modelo": (
                        saldo_disponivel(agente, modelo=modelo) if modelo else None
                    ),
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def solicitacoes_geojson():
    """GeoJSON das solicitações em aberto, para o mapa mostrar a demanda.

    "Em aberto" = tudo que ainda não terminou (ABERTA, ATRIBUIDA, EM_ROTA):
    é o trabalho pendente do operador. Uma solicitação ATRIBUIDA mas com
    cobertura parcial continua precisando de atenção tanto quanto uma ABERTA,
    e o popup mostra o quanto falta.

    Cliente sem coordenada fica de fora — pelo mesmo motivo do agente
    (ISC-RN-12): não há onde desenhar. A contagem vem à parte para o mapa
    sinalizar, em vez de sumir em silêncio.
    """
    from iscas.services.solicitacao import cobertura_em_lote

    solicitacoes = list(
        Solicitacao.objects.filter(
            status__in=(
                StatusSolicitacao.ABERTA,
                StatusSolicitacao.ATRIBUIDA,
                StatusSolicitacao.EM_ROTA,
            )
        )
        .select_related("cliente")
        .prefetch_related("atribuicoes__agente")
        .order_by("aberta_em")
    )

    # Cobertura de todas de uma vez: chamar `cobertura()` por solicitação
    # custaria ~3 consultas cada, e o mapa carrega a lista inteira.
    coberturas = cobertura_em_lote(solicitacoes)

    features = []
    sem_coordenada = 0

    for solicitacao in solicitacoes:
        cliente = solicitacao.cliente
        # O pin fica no PONTO DE ENTREGA, não na sede do cliente: o mapa
        # mostra para onde a isca vai. Cliente sem endereço cadastrado — caso
        # legítimo — continua no mapa pela coordenada da entrega.
        origem = solicitacao.coordenada_de_busca
        if origem is None:
            sem_coordenada += 1
            continue

        linhas = coberturas.get(solicitacao.pk, [])
        falta_total = sum(linha["falta"] for linha in linhas)

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(origem[1]), float(origem[0])],
                },
                "properties": {
                    "id": solicitacao.pk,
                    "status": solicitacao.status,
                    "status_display": solicitacao.get_status_display(),
                    "cliente": cliente.nome_razao_social,
                    "cliente_id": cliente.pk,
                    "endereco": solicitacao.endereco_entrega,
                    "telefone": solicitacao.telefone or cliente.telefone,
                    "aberta_em": solicitacao.aberta_em.strftime("%d/%m/%Y %H:%M"),
                    "prazo": (
                        solicitacao.prazo_desejado.strftime("%d/%m/%Y")
                        if solicitacao.prazo_desejado
                        else None
                    ),
                    "observacao": solicitacao.observacao,
                    # `falta` é o que decide a cor do marcador: descoberta
                    # (vermelho) exige ação; coberta (azul) só aguarda entrega.
                    "falta_total": falta_total,
                    "descoberta": falta_total > 0,
                    "itens": [
                        {
                            "modelo": linha["modelo"].nome,
                            "codigo": linha["modelo"].codigo,
                            "solicitado": linha["solicitado"],
                            "atribuido": linha["atribuido"],
                            "falta": linha["falta"],
                        }
                        for linha in linhas
                    ],
                    "agentes": [
                        atribuicao.agente.nome
                        for atribuicao in solicitacao.atribuicoes.all()
                        if atribuicao.status
                        in (StatusAtribuicao.RESERVADA, StatusAtribuicao.EM_ROTA)
                    ],
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "sem_coordenada": sem_coordenada,
    }


def cliente_geojson(cliente):
    """Ponto do cliente, para destacar no mapa (ISC-RF-19)."""
    if not cliente.tem_coordenada:
        return None
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(cliente.longitude), float(cliente.latitude)],
        },
        "properties": {
            "id": cliente.pk,
            "nome": cliente.nome_razao_social,
            "endereco": cliente.endereco_completo,
            "telefone": cliente.telefone,
        },
    }


# ---------------------------------------------------------------------------
# Listagens
# ---------------------------------------------------------------------------


def unidades_filtradas(
    *, modelo=None, situacao=None, custodia=None, identificador=None, agente=None
):
    """Unidades com a situação anotada, aplicando os filtros informados."""
    qs = (
        Unidade.objects.com_situacao()
        .select_related("modelo", "custodia_atual", "custodia_atual__agente",
                        "custodia_atual__cliente", "custodia_atual__deposito")
        .order_by("identificador")
    )
    if modelo:
        qs = qs.filter(modelo=modelo)
    if custodia:
        qs = qs.filter(custodia_atual=custodia)
    if agente:
        qs = qs.filter(custodia_atual__agente=agente)
    if identificador:
        qs = qs.filter(identificador__icontains=identificador)
    if situacao:
        # `situacao` é annotation, então o filtro vem depois dela — o ORM
        # resolve isso num HAVING sobre o CASE.
        qs = qs.filter(situacao=situacao)
    return qs


def extrato_movimentacoes(
    *,
    inicio=None,
    fim=None,
    agente=None,
    cliente=None,
    modelo=None,
    tipo=None,
    identificador=None,
):
    """Extrato filtrável (ISC-RF-34). Filtros são combináveis."""
    qs = (
        Movimentacao.objects.select_related(
            "origem", "destino", "autor", "estorno_de",
            "origem__agente", "origem__cliente", "origem__deposito",
            "destino__agente", "destino__cliente", "destino__deposito",
        )
        # `linhas__unidade` alimenta a lista de identificadores no cartão; sem
        # o prefetch seriam duas consultas por movimentação exibida.
        .prefetch_related("linhas__unidade__modelo", "estornos")
        .annotate(quantidade_linhas=Count("linhas", distinct=True))
        .order_by("-ocorrido_em", "-id")
    )
    if inicio:
        qs = qs.filter(ocorrido_em__date__gte=inicio)
    if fim:
        qs = qs.filter(ocorrido_em__date__lte=fim)
    if tipo:
        qs = qs.filter(tipo=tipo)
    if agente:
        qs = qs.filter(Q(origem__agente=agente) | Q(destino__agente=agente))
    if cliente:
        qs = qs.filter(Q(origem__cliente=cliente) | Q(destino__cliente=cliente))
    if modelo:
        qs = qs.filter(linhas__unidade__modelo=modelo).distinct()
    if identificador:
        qs = qs.filter(
            linhas__unidade__identificador__icontains=identificador
        ).distinct()
    return qs


def historico_unidade(unidade):
    """Por onde a unidade passou (ISC-RF-10)."""
    return (
        Movimentacao.objects.filter(linhas__unidade=unidade)
        .select_related("origem", "destino", "autor", "estorno_de")
        .order_by("ocorrido_em", "id")
    )


def solicitacoes_filtradas(*, status=None, cliente=None, busca="", excluidas=False):
    """Listagem de solicitações, já com o necessário para renderizar a linha.

    Args:
        excluidas: quando True, devolve SÓ as excluídas (a lixeira). O padrão
            é o oposto — excluída não aparece na operação (ISC-ADR-15).
        busca: casa com o id da solicitação ou o nome do cliente.

    O `prefetch_related` de itens é o que mantém a listagem em número
    constante de consultas: sem ele, cada linha da tabela dispara uma query
    para montar os badges de modelo — 25 linhas, 25 consultas.
    """
    # `todos` e não `objects`: o manager padrão já filtra `is_active=True`, e
    # a lixeira precisa enxergar justamente o que ele esconde.
    qs = (
        Solicitacao.todos.select_related("cliente", "aberta_por")
        .prefetch_related("itens__modelo", "atribuicoes__agente")
        .filter(is_active=not excluidas)
        .order_by("-aberta_em", "-id")
    )
    if status:
        qs = qs.filter(status=status)
    if cliente:
        qs = qs.filter(cliente=cliente)
    if busca:
        filtro = Q(cliente__nome_razao_social__icontains=busca)
        # Busca por "#12" ou "12" cai no id; qualquer outra coisa é nome.
        digitos = busca.lstrip("#").strip()
        if digitos.isdigit():
            filtro = filtro | Q(pk=int(digitos))
        qs = qs.filter(filtro)
    return qs


def modelos_em_falta(solicitacao):
    """Modelos da solicitação que ainda não estão cobertos (ISC-RF-30).

    Retorna `[(modelo, falta)]` na ordem dos itens do pedido. É o contrato do
    que ainda pode ser atribuído: quem escolhe o agente e quem escolhe as
    unidades partem desta mesma lista.
    """
    from iscas.services.solicitacao import cobertura

    return [
        (linha["modelo"], linha["falta"])
        for linha in cobertura(solicitacao)
        if linha["falta"] > 0
    ]


def agentes_que_atendem(solicitacao):
    """Agentes com ao menos uma unidade disponível de algum modelo em falta.

    Sem esse filtro a tela lista o cadastro inteiro, e o operador só descobre
    que o agente não tem o equipamento depois de submeter — o erro chega do
    service, tarde demais. Agente sem nenhuma unidade útil para ESTE pedido
    não é opção e some do select.

    Vale registrar o que a regra NÃO é: não se exige que o agente cubra o
    pedido inteiro, nem um modelo inteiro. Atendimento parcial, completado por
    outro agente, é o funcionamento normal (ISC-RN-10) — exigir cobertura total
    aqui esconderia agentes legítimos.

    Duas consultas, independentemente do número de agentes.
    """
    from iscas.services.saldo import unidades_disponiveis_por_modelos

    faltantes = [modelo.pk for modelo, _ in modelos_em_falta(solicitacao)]
    if not faltantes:
        return Agente.objects.none()

    return Agente.objects.filter(
        pk__in=unidades_disponiveis_por_modelos(faltantes).values(
            "custodia_atual__agente_id"
        )
    ).order_by("nome")


def unidades_uteis_por_modelo(*, agente, solicitacao):
    """O que ESTE agente pode contribuir para ESTE pedido.

    Returns:
        Lista de `(modelo, falta, queryset de unidades disponíveis)`, só para
        os modelos em que o agente tem ao menos uma unidade livre. Modelo que
        falta no pedido mas que o agente não tem fica de fora — oferecer um
        select vazio só confunde.

    É a fonte única da tela de escolha e da validação do agente: as duas
    respondem à mesma pergunta e não podem divergir.
    """
    from iscas.services.saldo import unidades_disponiveis

    resultado = []
    for modelo, falta in modelos_em_falta(solicitacao):
        disponiveis = unidades_disponiveis(agente, modelo=modelo).select_related(
            "modelo"
        ).order_by("custodia_desde", "identificador")
        if disponiveis.exists():
            resultado.append((modelo, falta, disponiveis))
    return resultado


# ---------------------------------------------------------------------------
# Dashboard (ISC-RF-38)
# ---------------------------------------------------------------------------


def metricas_painel():
    """Números do painel operacional, calculados na leitura (ISC-ADR-13).

    Sem Celery no MVP, nada é empurrado: o dashboard calcula ao abrir. No
    volume projetado (100k lançamentos em dois anos) isso é barato.
    """
    config = ConfiguracaoIscas.carregar()
    agora = timezone.now()

    por_situacao = {}
    for linha in (
        Unidade.objects.com_situacao().values("situacao").annotate(total=Count("id"))
    ):
        por_situacao[linha["situacao"]] = linha["total"]

    limite_retornavel = agora - timedelta(days=config.dias_alerta_retornavel)
    retornaveis_atrasados = Unidade.objects.filter(
        custodia_atual__tipo=TipoCustodia.CLIENTE,
        modelo__tipo=TipoModelo.RETORNAVEL,
        custodia_desde__lt=limite_retornavel,
    ).count()

    limite_rota = agora - timedelta(hours=config.horas_alerta_em_rota)
    em_rota_paradas = Atribuicao.objects.filter(
        status=StatusAtribuicao.EM_ROTA, em_rota_em__lt=limite_rota
    ).select_related("agente", "solicitacao__cliente")

    agentes_com_saldo_baixo = [
        {"agente": agente, "disponivel": disponivel}
        for agente in Agente.objects.all()
        if (disponivel := saldo_disponivel(agente)) < config.saldo_minimo_alerta
    ]

    return {
        "config": config,
        "por_situacao": por_situacao,
        # Sem depósito não há como registrar entrada de equipamento novo nem
        # receber retornável de volta: o painel sinaliza a lacuna de cadastro.
        "sem_deposito": not Deposito.objects.exists(),
        "total_em_campo": por_situacao.get(SituacaoUnidade.COM_AGENTE, 0)
        + por_situacao.get(SituacaoUnidade.RESERVADA, 0)
        + por_situacao.get(SituacaoUnidade.EM_ROTA, 0),
        "total_em_deposito": por_situacao.get(SituacaoUnidade.EM_DEPOSITO, 0),
        "retornaveis_com_cliente": por_situacao.get(SituacaoUnidade.COM_CLIENTE, 0),
        "retornaveis_atrasados": retornaveis_atrasados,
        "solicitacoes_abertas": Solicitacao.objects.filter(
            status__in=(
                StatusSolicitacao.ABERTA,
                StatusSolicitacao.ATRIBUIDA,
                StatusSolicitacao.EM_ROTA,
            )
        ).count(),
        "em_rota_paradas": em_rota_paradas,
        "agentes_saldo_baixo": agentes_com_saldo_baixo,
        "agentes_sem_coordenada": Agente.objects.filter(
            Q(latitude__isnull=True) | Q(longitude__isnull=True)
        ),
    }


def historico_agente(agente):
    """Consolidado por agente (ISC-RF-35)."""
    from iscas.services.custodia import custodia_de

    conta = custodia_de(agente)
    return {
        "agente": agente,
        "saldos": list(saldo_por_modelo(agente)),
        "recebidas": Movimentacao.objects.filter(destino=conta).count(),
        "enviadas": Movimentacao.objects.filter(origem=conta).count(),
        "movimentacoes": Movimentacao.objects.filter(
            Q(origem=conta) | Q(destino=conta)
        )
        .select_related("origem", "destino", "autor")
        .annotate(quantidade_linhas=Count("linhas"))
        .order_by("-ocorrido_em", "-id"),
    }


def historico_cliente(cliente):
    """Consolidado por cliente (ISC-RF-36)."""
    from iscas.services.custodia import custodia_de
    from iscas.services.retorno import retornaveis_em_posse

    conta = custodia_de(cliente)
    return {
        "cliente": cliente,
        "recebidas": Movimentacao.objects.filter(destino=conta).count(),
        "retornaveis_em_posse": retornaveis_em_posse(cliente=cliente),
        "retornos": Movimentacao.objects.filter(origem=conta).count(),
        "movimentacoes": Movimentacao.objects.filter(
            Q(origem=conta) | Q(destino=conta)
        )
        .select_related("origem", "destino", "autor")
        .annotate(quantidade_linhas=Count("linhas"))
        .order_by("-ocorrido_em", "-id"),
    }
