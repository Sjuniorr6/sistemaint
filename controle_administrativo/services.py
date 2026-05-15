from .models import (
    TarefaModeloAdministrativa,
    ExecucaoTarefaAdministrativa,
    StatusExecucao,
)


def gerar_execucoes_semana(semana_iso, ano):
    """
    Gera as ExecucaoTarefaAdministrativa para todas as
    TarefaModeloAdministrativa ativas na semana/ano informados.

    Idempotente: se a execução já existe, não cria outra.
    Chamado automaticamente toda vez que o painel é aberto.
    """
    tarefas_ativas = TarefaModeloAdministrativa.objects.filter(ativo=True)

    for tarefa in tarefas_ativas:
        ExecucaoTarefaAdministrativa.objects.get_or_create(
            tarefa_modelo=tarefa,
            semana_iso=semana_iso,
            ano=ano,
            defaults={
                'status': StatusExecucao.PENDENTE,
                'is_done': False,
            }
        )