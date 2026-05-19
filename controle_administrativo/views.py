from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
import zoneinfo

from .models import (
    ExecucaoTarefaAdministrativa,
    ComentarioTarefa,
    FuncionarioAdministrativo,
    StatusExecucao,
    TarefaDivisao,
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
    gerar_blocos_semana,
    criar_tarefa_avulsa,
    criar_tarefa_recorrente,
    marcar_comentarios_lidos,
    excluir_execucao,
    adicionar_item_bloco,
    toggle_item_bloco,
    excluir_item_bloco,
    adicionar_comentario_item_bloco,
    atualizar_item_bloco,
    adicionar_tarefa_divisao,
    editar_tarefa_divisao,
    excluir_tarefa_divisao,
)


@login_required
def painel(request):
    semana_iso, ano = get_semana_atual()
    gerar_execucoes_semana(semana_iso, ano)
    gerar_blocos_semana(semana_iso, ano, request.user)

    execucoes    = get_execucoes_da_semana(semana_iso, ano, user=request.user)
    blocos       = get_blocos_da_semana(semana_iso, ano)
    funcionarios = get_funcionarios_ativos()
    resumo       = get_resumo_semana(semana_iso, ano)
    dia_atual    = get_dia_atual()

    # Tarefas da divisão por funcionário — lista de dicts para o template
    funcionarios_com_tarefas = []
    for func in funcionarios:
        tarefas = list(TarefaDivisao.objects.filter(
            funcionario=func,
            semana_iso=semana_iso,
            ano=ano,
        ).order_by('ordem', 'criado_em'))
        funcionarios_com_tarefas.append({
            'funcionario': func,
            'tarefas_divisao': tarefas,
        })

    context = {
        'execucoes':               execucoes,
        'blocos':                  blocos,
        'funcionarios':            funcionarios,
        'funcionarios_com_tarefas': funcionarios_com_tarefas,
        'resumo':                  resumo,
        'dia_atual':               dia_atual,
        'semana_iso':              semana_iso,
        'ano':                     ano,
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
    execucao = get_object_or_404(ExecucaoTarefaAdministrativa, id=execucao_id)
    execucao.is_done = not execucao.is_done

    if execucao.is_done:
        execucao.status        = StatusExecucao.CONCLUIDA
        execucao.concluido_por = request.user
        execucao.concluido_em  = timezone.now()
    else:
        execucao.status        = StatusExecucao.PENDENTE
        execucao.concluido_por = None
        execucao.concluido_em  = None

    execucao.atualizado_por = request.user
    execucao.save()

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
        'success':   True,
        'id':        comentario.id,
        'autor':     comentario.autor.get_full_name() or comentario.autor.username,
        'conteudo':  comentario.conteudo,
        'criado_em': timezone.localtime(comentario.criado_em).strftime('%d/%m/%Y às %H:%M'),
    })


@login_required
def detalhe_execucao(request, execucao_id):
    execucao = get_object_or_404(
        ExecucaoTarefaAdministrativa.objects.select_related(
            'tarefa_modelo',
            'tarefa_modelo__responsavel',
            'tarefa_modelo__categoria',
            'responsavel_avulso',
            'concluido_por',
            'atualizado_por',
        ).prefetch_related('comentarios', 'comentarios__autor'),
        id=execucao_id
    )

    marcar_comentarios_lidos(execucao, request.user)

    comentarios = [
        {
            'id':        c.id,
            'autor':     c.autor.get_full_name() or c.autor.username if c.autor else 'Desconhecido',
            'conteudo':  c.conteudo,
            'criado_em': timezone.localtime(c.criado_em).strftime('%d/%m/%Y às %H:%M'),
            'is_done':   c.is_done,
        }
        for c in execucao.comentarios.all()
    ]

    return JsonResponse({
        'success':        True,
        'id':             execucao.id,
        'titulo':         execucao.titulo_display,
        'descricao':      execucao.descricao_display,
        'responsavel':    execucao.responsavel_display,
        'dia':            execucao.dia_display,
        'periodo':        execucao.periodo_display,
        'status':         execucao.get_status_display(),
        'is_done':        execucao.is_done,
        'is_avulsa':      execucao.is_avulsa,
        'prazo':          execucao.prazo.strftime('%d/%m/%Y') if execucao.prazo else None,
        'concluido_por':  execucao.concluido_por.get_full_name() or execucao.concluido_por.username if execucao.concluido_por else None,
        'concluido_em':   timezone.localtime(execucao.concluido_em).strftime('%d/%m/%Y às %H:%M') if execucao.concluido_em else None,
        'atualizado_por': execucao.atualizado_por.get_full_name() or execucao.atualizado_por.username if execucao.atualizado_por else None,
        'atualizado_em':  timezone.localtime(execucao.atualizado_em).strftime('%d/%m/%Y às %H:%M') if execucao.atualizado_em else None,
        'comentarios':    comentarios,
    })


@login_required
@require_POST
def criar_tarefa(request):
    titulo         = request.POST.get('titulo', '').strip()
    dia            = request.POST.get('dia', '').strip()
    periodo        = request.POST.get('periodo', '').strip()
    responsavel_id = request.POST.get('responsavel_id', '').strip()
    descricao      = request.POST.get('descricao', '').strip()
    tipo           = request.POST.get('tipo', 'avulsa').strip()

    if not all([titulo, dia, periodo, responsavel_id]):
        return JsonResponse({'success': False, 'error': 'Preencha todos os campos obrigatórios.'})

    semana_iso, ano = get_semana_atual()

    try:
        if tipo == 'recorrente':
            criar_tarefa_recorrente(
                titulo=titulo, dia=dia, periodo=periodo,
                responsavel_id=responsavel_id, descricao=descricao,
                semana_iso=semana_iso, ano=ano,
            )
        else:
            criar_tarefa_avulsa(
                semana_iso=semana_iso, ano=ano, titulo=titulo,
                dia=dia, periodo=periodo, responsavel_id=responsavel_id,
                descricao=descricao,
            )
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': True})


@login_required
@require_POST
def excluir_tarefa(request, execucao_id):
    try:
        excluir_execucao(execucao_id, request.user)
        semana_iso, ano = get_semana_atual()
        resumo = get_resumo_semana(semana_iso, ano)
        return JsonResponse({
            'success':    True,
            'percentual': resumo['percentual'],
            'concluidas': resumo['concluidas'],
            'total':      resumo['total'],
        })
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def adicionar_item_bloco_view(request, bloco_id):
    conteudo = request.POST.get('conteudo', '').strip()
    is_fixo  = request.POST.get('is_fixo', 'false') == 'true'
    try:
        item = adicionar_item_bloco(bloco_id, conteudo, is_fixo, user=request.user)
        return JsonResponse({
            'success':  True,
            'id':       item.id,
            'conteudo': item.conteudo,
            'is_fixo':  item.is_fixo,
            'is_done':  item.is_done,
        })
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def toggle_item_bloco_view(request, item_id):
    try:
        item = toggle_item_bloco(item_id)
        return JsonResponse({'success': True, 'is_done': item.is_done})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def excluir_item_bloco_view(request, item_id):
    try:
        excluir_item_bloco(item_id)
        return JsonResponse({'success': True})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def detalhe_item_bloco(request, item_id):
    from .models import ItemBlocoSemanal
    try:
        item = ItemBlocoSemanal.objects.select_related(
            'responsavel', 'criado_por'
        ).prefetch_related('comentarios', 'comentarios__autor').get(id=item_id)
    except ItemBlocoSemanal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Item não encontrado.'})

    comentarios = [
        {
            'id':        c.id,
            'autor':     c.autor.get_full_name() or c.autor.username if c.autor else 'Desconhecido',
            'conteudo':  c.conteudo,
            'criado_em': timezone.localtime(c.criado_em).strftime('%d/%m/%Y às %H:%M'),
        }
        for c in item.comentarios.all()
    ]

    return JsonResponse({
        'success':          True,
        'id':               item.id,
        'conteudo':         item.conteudo,
        'is_fixo':          item.is_fixo,
        'is_done':          item.is_done,
        'prazo':            item.prazo.strftime('%Y-%m-%d') if item.prazo else '',
        'prazo_fmt':        item.prazo.strftime('%d/%m/%Y') if item.prazo else '—',
        'responsavel_id':   item.responsavel.id if item.responsavel else '',
        'responsavel_nome': item.responsavel.nome if item.responsavel else '—',
        'criado_por':       item.criado_por.get_full_name() or item.criado_por.username if item.criado_por else '—',
        'criado_em':        timezone.localtime(item.criado_em).strftime('%d/%m/%Y às %H:%M'),
        'comentarios':      comentarios,
    })


@login_required
@require_POST
def atualizar_item_bloco_view(request, item_id):
    conteudo       = request.POST.get('conteudo', '').strip() or None
    responsavel_id = request.POST.get('responsavel_id', None)
    prazo          = request.POST.get('prazo', None)
    is_fixo_str    = request.POST.get('is_fixo', None)
    is_fixo        = (is_fixo_str == 'true') if is_fixo_str is not None else None

    try:
        item = atualizar_item_bloco(item_id, conteudo, responsavel_id, prazo, is_fixo)
        return JsonResponse({'success': True, 'conteudo': item.conteudo, 'is_fixo': item.is_fixo})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def adicionar_comentario_item_bloco_view(request, item_id):
    conteudo = request.POST.get('conteudo', '').strip()
    try:
        comentario = adicionar_comentario_item_bloco(item_id, conteudo, request.user)
        return JsonResponse({
            'success':   True,
            'id':        comentario.id,
            'autor':     comentario.autor.get_full_name() or comentario.autor.username,
            'conteudo':  comentario.conteudo,
            'criado_em': timezone.localtime(comentario.criado_em).strftime('%d/%m/%Y às %H:%M'),
        })
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def adicionar_tarefa_divisao_view(request, funcionario_id):
    conteudo = request.POST.get('conteudo', '').strip()
    semana_iso, ano = get_semana_atual()
    try:
        tarefa = adicionar_tarefa_divisao(funcionario_id, semana_iso, ano, conteudo)
        return JsonResponse({'success': True, 'id': tarefa.id, 'conteudo': tarefa.conteudo})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def editar_tarefa_divisao_view(request, tarefa_id):
    conteudo = request.POST.get('conteudo', '').strip()
    try:
        tarefa = editar_tarefa_divisao(tarefa_id, conteudo)
        return JsonResponse({'success': True, 'conteudo': tarefa.conteudo})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def excluir_tarefa_divisao_view(request, tarefa_id):
    try:
        excluir_tarefa_divisao(tarefa_id)
        return JsonResponse({'success': True})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})