# selectors.py
# Queries otimizadas para leitura — sem lógica de negócio.
# Views buscam dados daqui, nunca diretamente dos models.

from django.utils import timezone
from .models import (
    TarefaModeloAdministrativa,
    ExecucaoTarefaAdministrativa,
    BlocoSemanal,
    FuncionarioAdministrativo,
)


def get_semana_atual():
    """Retorna a semana ISO e ano atuais."""
    hoje = timezone.now().date()
    semana_iso = hoje.isocalendar()[1]
    ano = hoje.year
    return semana_iso, ano


def get_dia_atual():
    """Retorna o dia da semana atual no formato dos choices."""
    hoje = timezone.now().date()
    mapa = {
        0: 'segunda',
        1: 'terca',
        2: 'quarta',
        3: 'quinta',
        4: 'sexta',
        5: 'segunda',  # sábado → mostra segunda (próximo dia útil)
        6: 'segunda',  # domingo → mostra segunda (próximo dia útil)
    }
    return mapa[hoje.weekday()]


def get_execucoes_da_semana(semana_iso, ano):
    """
    Retorna todas as execuções da semana agrupadas por dia e período.
    Estrutura retornada:
    {
        'segunda': {'manha': [...], 'tarde': [...]},
        'terca':   {'manha': [...], 'tarde': [...]},
        ...
    }
    """
    execucoes = ExecucaoTarefaAdministrativa.objects.filter(
        semana_iso=semana_iso,
        ano=ano,
    ).select_related(
        'tarefa_modelo',
        'tarefa_modelo__responsavel',
        'tarefa_modelo__categoria',
        'concluido_por',
        'atualizado_por',
    ).prefetch_related(
        'comentarios',
        'comentarios__autor',
    ).order_by(
        'tarefa_modelo__ordem'
    )

    dias = ['segunda', 'terca', 'quarta', 'quinta', 'sexta']
    periodos = ['manha', 'tarde']

    resultado = {
        dia: {periodo: [] for periodo in periodos}
        for dia in dias
    }

    for execucao in execucoes:
        dia = execucao.tarefa_modelo.dia_da_semana
        periodo = execucao.tarefa_modelo.periodo
        if dia in resultado and periodo in resultado[dia]:
            resultado[dia][periodo].append(execucao)

    return resultado


def get_blocos_da_semana(semana_iso, ano):
    """Retorna os blocos especiais da semana com seus itens."""
    return BlocoSemanal.objects.filter(
        semana_iso=semana_iso,
        ano=ano,
    ).prefetch_related('itens').order_by('tipo')


def get_funcionarios_ativos():
    """Retorna todos os funcionários ativos."""
    return FuncionarioAdministrativo.objects.filter(
        ativo=True
    ).select_related('usuario').order_by('nome')


def get_resumo_semana(semana_iso, ano):
    """
    Calcula o percentual geral de conclusão da semana.
    Retorna dict com total, concluidas e percentual.
    """
    execucoes = ExecucaoTarefaAdministrativa.objects.filter(
        semana_iso=semana_iso,
        ano=ano,
    )
    total = execucoes.count()
    if total == 0:
        return {'total': 0, 'concluidas': 0, 'percentual': 0}

    concluidas = execucoes.filter(is_done=True).count()
    percentual = round((concluidas / total) * 100)

    return {
        'total': total,
        'concluidas': concluidas,
        'percentual': percentual,
    }