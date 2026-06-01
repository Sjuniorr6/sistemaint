from django.utils import timezone
from .models import (
    TarefaModeloAdministrativa,
    ExecucaoTarefaAdministrativa,
    LeituraComentario,
    BlocoSemanal,
    FuncionarioAdministrativo,
)


def get_semana_atual():
    hoje = timezone.now().date()
    semana_iso = hoje.isocalendar()[1]
    ano = hoje.year
    return semana_iso, ano


def get_dia_atual():
    hoje = timezone.now().date()
    mapa = {
        0: 'segunda',
        1: 'terca',
        2: 'quarta',
        3: 'quinta',
        4: 'sexta',
        5: 'segunda',
        6: 'segunda',
    }
    return mapa[hoje.weekday()]


def get_execucoes_da_semana(semana_iso, ano, user=None):
    """
    Retorna todas as execuções da semana agrupadas por dia e período.
    Se user informado, anota quantos comentários não lidos cada execução tem.
    """
    execucoes = ExecucaoTarefaAdministrativa.objects.filter(
        semana_iso=semana_iso,
        ano=ano,
        oculta=False,
    ).select_related(
        'tarefa_modelo',
        'tarefa_modelo__responsavel',
        'tarefa_modelo__categoria',
        'responsavel_avulso',
        'concluido_por',
        'atualizado_por',
    ).prefetch_related(
        'comentarios',
        'comentarios__autor',
        'comentarios__leituras',
    ).order_by('tarefa_modelo__ordem')

    dias = ['segunda', 'terca', 'quarta', 'quinta', 'sexta']
    periodos = ['manha', 'tarde']

    resultado = {
        dia: {periodo: [] for periodo in periodos}
        for dia in dias
    }

    for execucao in execucoes:
        dia     = execucao.dia_key
        periodo = execucao.periodo_key

        # Anota comentários não lidos
        if user:
            lidos_ids = execucao.comentarios.filter(
                leituras__usuario=user
            ).values_list('id', flat=True)
            execucao.nao_lidos = execucao.comentarios.exclude(
                id__in=lidos_ids
            ).exclude(autor=user).count()
        else:
            execucao.nao_lidos = 0

        if dia in resultado and periodo in resultado[dia]:
            resultado[dia][periodo].append(execucao)

    return resultado


def get_blocos_da_semana(semana_iso, ano):
    from .models import TipoBloco, ItemBlocoSemanal
    from django.db.models import Prefetch
    ORDEM = {
        TipoBloco.NAO_ESQUECER: 0,
        TipoBloco.QUINZENAL:    1,
        TipoBloco.MENSAL:       2,
    }
    # Só traz itens visíveis (oculta=False). Itens soft-deleted continuam no
    # banco para o copiador respeitar as exclusões, mas não aparecem no painel.
    itens_visiveis = ItemBlocoSemanal.objects.filter(oculta=False)
    blocos = list(BlocoSemanal.objects.filter(
        semana_iso=semana_iso,
        ano=ano,
    ).prefetch_related(
        Prefetch('itens', queryset=itens_visiveis)
    ))
    blocos.sort(key=lambda b: ORDEM.get(b.tipo, 99))
    return blocos


def get_funcionarios_ativos():
    return FuncionarioAdministrativo.objects.filter(
        ativo=True
    ).select_related('usuario').order_by('nome')


def get_resumo_semana(semana_iso, ano):
    execucoes = ExecucaoTarefaAdministrativa.objects.filter(
        semana_iso=semana_iso,
        ano=ano,
        oculta=False,
    ).exclude(status='cancelada')

    total = execucoes.count()
    if total == 0:
        return {'total': 0, 'concluidas': 0, 'percentual': 0}

    concluidas = execucoes.filter(is_done=True).count()
    percentual = round((concluidas / total) * 100)

    return {
        'total':      total,
        'concluidas': concluidas,
        'percentual': percentual,
    }