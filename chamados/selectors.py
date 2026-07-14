"""Camada de leitura (queries e filtros) do app Chamados.

As views consomem os dados a partir daqui — nunca fazem query direta ao model.
Os indicadores do painel (RF-08, ADR-011) são derivados do estado corrente e do
log de eventos do dia, sem contadores mantidos à mão (RN-05).
"""
from django.utils import timezone

from chamados.enums import Acao, Status
from chamados.models import Chamado


def listar_chamados(status=None, responsavel_inteligencia=None):
    """Fila de chamados, do mais recente ao mais antigo (RF-07).

    Filtros opcionais e composáveis. `select_related` em responsavel/aberto_por/
    responsavel_inteligencia porque a tabela exibe esses nomes por linha (evita
    N+1 na renderização). NÃO aplica visibilidade por papel — isso é feito por
    `chamados_visiveis_para`, que restringe o queryset ANTES destes filtros.
    """
    qs = Chamado.objects.select_related(
        "cliente", "modelo_equipamento", "responsavel", "aberto_por",
        "responsavel_inteligencia"
    ).order_by("-aberto_em")
    if status is not None:
        qs = qs.filter(status=status)
    if responsavel_inteligencia is not None:
        qs = qs.filter(responsavel_inteligencia=responsavel_inteligencia)
    return qs


def chamados_visiveis_para(user):
    """Queryset de chamados que `user` pode ENXERGAR (fronteira de visibilidade).

    - Quality e superuser: veem todos os chamados (abrem e acompanham tudo).
    - Inteligência: vê SOMENTE os encaminhados a ela própria
      (responsavel_inteligencia == user) — nunca os de quality nem os de outros
      colegas de inteligência.

    Aplicado na camada de dados (não só na UI): é o mesmo queryset que a fila e o
    `get_object_or_404` do detalhe usam, então a proteção não depende do template.
    """
    from django.db.models import Q

    from chamados.permissions import (
        is_comercial,
        is_expedicao,
        is_laboratorio,
        is_quality,
    )

    qs = Chamado.objects.select_related(
        "cliente", "modelo_equipamento", "responsavel", "aberto_por",
        "responsavel_inteligencia"
    ).order_by("-aberto_em")
    if is_quality(user):  # cobre superuser (is_quality já o inclui)
        return qs

    # Inteligência vê os encaminhados a ela; Expedição vê a fila EXPEDICAO;
    # Laboratório, a LABORATORIO; Comercial, a COMERCIAL. Um usuário de vários
    # grupos vê a união dos conjuntos.
    filtro = Q(responsavel_inteligencia=user)
    if is_expedicao(user):
        filtro |= Q(status=Status.EXPEDICAO)
    if is_laboratorio(user):
        filtro |= Q(status=Status.LABORATORIO)
    if is_comercial(user):
        filtro |= Q(status=Status.COMERCIAL)
    return qs.filter(filtro)


def metricas_painel():
    """Os três indicadores do painel (RF-08, ADR-011), derivados do log/estado.

    Fila Ativa e Encaminhados são contagens do estado corrente (cache consistente
    com o último evento). Resolvidos Hoje conta eventos de transição PARA
    RESOLVIDO na data corrente (não o campo status, para não contar resolvidos de
    outros dias) — fonte única no log (RN-05).
    """
    from chamados.models import ChamadoEvento

    hoje = timezone.localdate()
    resolvidos_hoje = (
        ChamadoEvento.objects.filter(
            estado_destino=Status.RESOLVIDO,
            acao__in=[Acao.FINALIZAR, Acao.RESOLVER],
            criado_em__date=hoje,
        )
        .values("chamado")
        .distinct()
        .count()
    )
    return {
        "fila_ativa": Chamado.objects.filter(status=Status.ABERTO).count(),
        "encaminhados": Chamado.objects.filter(status=Status.ENCAMINHADO).count(),
        "resolvidos_hoje": resolvidos_hoje,
    }


def acoes_disponiveis(user, chamado):
    """Ações que a UI deve oferecer para (user, chamado) — RF-07, RF-21.

    Espelha a máquina de estados + posse, mas é só reflexo de UI; a autorização
    real está no service (RN-18). Devolve uma lista de valores de Acao.
    """
    from chamados.permissions import pode_agir
    from chamados.services import TRANSICOES

    if not pode_agir(user, chamado):
        return []

    disponiveis = []
    for acao, transicao in TRANSICOES.items():
        if chamado.status in transicao.origens:
            disponiveis.append(acao)
    return disponiveis
