from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import (
    ExecucaoTarefaAdministrativa,
    ComentarioTarefa,
    StatusExecucao,
)
from .selectors import (
    get_semana_atual,
    get_dia_atual,
    get_execucoes_da_semana,
    get_blocos_da_semana,
    get_funcionarios_ativos,
    get_resumo_semana,
)
from .services import (
    gerar_execucoes_semana,
)


@login_required
def painel(request):
    """
    View principal do SCA.
    Exibe o painel da semana atual com todas as tarefas,
    blocos especiais e barra de progresso.
    """
    semana_iso, ano = get_semana_atual()

    # Garante que as execuções da semana existem
    gerar_execucoes_semana(semana_iso, ano)

    execucoes     = get_execucoes_da_semana(semana_iso, ano)
    blocos        = get_blocos_da_semana(semana_iso, ano)
    funcionarios  = get_funcionarios_ativos()
    resumo        = get_resumo_semana(semana_iso, ano)
    dia_atual     = get_dia_atual()

    context = {
        'execucoes':    execucoes,
        'blocos':       blocos,
        'funcionarios': funcionarios,
        'resumo':       resumo,
        'dia_atual':    dia_atual,
        'semana_iso':   semana_iso,
        'ano':          ano,
        'dias': [
            ('segunda', 'Segunda-feira'),
            ('terca',   'Terça-feira'),
            ('quarta',  'Quarta-feira'),
            ('quinta',  'Quinta-feira'),
            ('sexta',   'Sexta-feira'),
        ],
    }

    return render(request, 'controle_administrativo/painel.html', context)


@login_required
@require_POST
def toggle_execucao(request, execucao_id):
    """
    Marca ou desmarca uma execução como concluída.
    Chamado via AJAX quando o usuário clica no checkbox.
    """
    execucao = get_object_or_404(ExecucaoTarefaAdministrativa, id=execucao_id)

    execucao.is_done = not execucao.is_done

    if execucao.is_done:
        execucao.status       = StatusExecucao.CONCLUIDA
        execucao.concluido_por = request.user
        execucao.concluido_em  = timezone.now()
    else:
        execucao.status       = StatusExecucao.PENDENTE
        execucao.concluido_por = None
        execucao.concluido_em  = None

    execucao.atualizado_por = request.user
    execucao.save()

    # Recalcula resumo para atualizar a barra de progresso
    semana_iso, ano = get_semana_atual()
    resumo = get_resumo_semana(semana_iso, ano)

    return JsonResponse({
        'success':    True,
        'is_done':    execucao.is_done,
        'status':     execucao.status,
        'percentual': resumo['percentual'],
        'concluidas': resumo['concluidas'],
        'total':      resumo['total'],
    })


@login_required
@require_POST
def adicionar_comentario(request, execucao_id):
    """
    Adiciona um comentário a uma execução.
    Chamado via AJAX pelo modal de detalhes da tarefa.
    """
    execucao = get_object_or_404(ExecucaoTarefaAdministrativa, id=execucao_id)
    conteudo = request.POST.get('conteudo', '').strip()

    if not conteudo:
        return JsonResponse({'success': False, 'error': 'Comentário não pode ser vazio.'})

    comentario = ComentarioTarefa.objects.create(
        execucao=execucao,
        autor=request.user,
        conteudo=conteudo,
    )

    return JsonResponse({
        'success':    True,
        'id':         comentario.id,
        'autor':      comentario.autor.get_full_name() or comentario.autor.username,
        'conteudo':   comentario.conteudo,
        'criado_em':  comentario.criado_em.strftime('%d/%m/%Y às %H:%M'),
    })


@login_required
def detalhe_execucao(request, execucao_id):
    """
    Retorna os dados completos de uma execução para o modal.
    Chamado via AJAX quando o usuário clica no card da tarefa.
    """
    execucao = get_object_or_404(
        ExecucaoTarefaAdministrativa.objects.select_related(
            'tarefa_modelo',
            'tarefa_modelo__responsavel',
            'tarefa_modelo__categoria',
            'concluido_por',
            'atualizado_por',
        ).prefetch_related('comentarios', 'comentarios__autor'),
        id=execucao_id
    )

    comentarios = [
        {
            'id':        c.id,
            'autor':     c.autor.get_full_name() or c.autor.username if c.autor else 'Desconhecido',
            'conteudo':  c.conteudo,
            'criado_em': c.criado_em.strftime('%d/%m/%Y às %H:%M'),
            'is_done':   c.is_done,
        }
        for c in execucao.comentarios.all()
    ]

    return JsonResponse({
        'success': True,
        'id':          execucao.id,
        'titulo':      execucao.tarefa_modelo.titulo,
        'descricao':   execucao.tarefa_modelo.descricao,
        'responsavel': execucao.tarefa_modelo.responsavel.nome,
        'dia':         execucao.tarefa_modelo.get_dia_da_semana_display(),
        'periodo':     execucao.tarefa_modelo.get_periodo_display(),
        'status':      execucao.get_status_display(),
        'is_done':     execucao.is_done,
        'prazo':       execucao.prazo.strftime('%d/%m/%Y') if execucao.prazo else None,
        'concluido_por': execucao.concluido_por.get_full_name() or execucao.concluido_por.username if execucao.concluido_por else None,
        'concluido_em':  execucao.concluido_em.strftime('%d/%m/%Y às %H:%M') if execucao.concluido_em else None,
        'atualizado_por': execucao.atualizado_por.get_full_name() or execucao.atualizado_por.username if execucao.atualizado_por else None,
        'atualizado_em':  execucao.atualizado_em.strftime('%d/%m/%Y às %H:%M') if execucao.atualizado_em else None,
        'comentarios': comentarios,
    })