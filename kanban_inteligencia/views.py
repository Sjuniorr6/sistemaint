from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Case, When, IntegerField
from django.utils import timezone
from .models import TarefaInteligencia
import json


@login_required
def home(request):
    """
    Kanban de Inteligência
    """
    # Tickets destinados ao T.I não pertencem a este board — aparecem apenas
    # no Kanban TI (inbox) e na central de tickets.
    tarefas = TarefaInteligencia.objects.exclude(destinado='TI')

    # Filtrar por 'destinado' se parâmetro GET for passado
    destinado_filter = request.GET.get('destinado')
    if destinado_filter and destinado_filter != 'all':
        tarefas = tarefas.filter(destinado=destinado_filter)

    def order_by_prioridade(queryset):
        return queryset.annotate(
            prioridade_order=Case(
                When(prioridade='alta', then=4),
                When(prioridade='media', then=3),
                When(prioridade='baixa', then=2),
                When(prioridade='avaliar', then=1),
                default=0,
                output_field=IntegerField()
            )
        ).order_by('-prioridade_order')

    avaliar = order_by_prioridade(tarefas.filter(status='avaliar'))
    a_fazer = order_by_prioridade(tarefas.filter(status='a_fazer'))
    em_progresso = order_by_prioridade(tarefas.filter(status='em_progresso'))
    validacao = order_by_prioridade(tarefas.filter(status='validacao'))
    concluido = order_by_prioridade(tarefas.filter(status='concluido'))
    
    # Estatísticas
    total_tarefas = tarefas.count()
    total_concluidas = concluido.count()
    total_em_progresso = em_progresso.count()
    total_avaliar = avaliar.count()
    total_atrasadas = sum(1 for t in tarefas if t.esta_atrasada)
    taxa_conclusao = round((total_concluidas / total_tarefas * 100) if total_tarefas > 0 else 0)
    
    context = {
        'avaliar': avaliar,
        'a_fazer': a_fazer,
        'em_progresso': em_progresso,
        'validacao': validacao,
        'concluido': concluido,
        'responsavel_choices': TarefaInteligencia.RESPONSAVEL_CHOICES,
        'stats': {
            'total_tarefas': total_tarefas,
            'avaliar': total_avaliar,
            'concluidas': total_concluidas,
            'em_progresso': total_em_progresso,
            'atrasadas': total_atrasadas,
            'taxa_conclusao': taxa_conclusao,
        },
        'destinado_filter': destinado_filter or 'all',  # Para saber qual filtro está ativo
    }
    
    return render(request, 'kanban_inteligencia/home.html', context)

@login_required
@require_POST
def adicionar_tarefa(request):
    try:
        tarefa = TarefaInteligencia.objects.create(
            titulo=request.POST.get('titulo'),
            descricao=request.POST.get('descricao', ''),
            data_limite=request.POST.get('data_limite') or None,
            destinado=request.POST.get('destinado', 'inteligencia'),
            responsavel=request.POST.get('responsavel')or None,
            responsavel_cor=request.POST.get('responsavel_cor', 'azul'),
            cor=request.POST.get('cor', 'azul'),
            prioridade=request.POST.get('prioridade', 'media'),
            imagem=request.FILES.get('imagem')  # 👈 AQUI ESTÁ O UPLOAD
            
        )

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def obter_tarefa(request, tarefa_id):
    """
    Retorna dados de uma tarefa específica
    """
    try:
        tarefa = TarefaInteligencia.objects.get(id=tarefa_id)
        
        return JsonResponse({
            'success': True,
            'tarefa': {
                'id': tarefa.id,
                'titulo': tarefa.titulo,
                'descricao': tarefa.descricao,
                'status': tarefa.status,
                'data_limite': tarefa.data_limite.strftime('%Y-%m-%d') if tarefa.data_limite else '',
                'imagem_url': tarefa.imagem.url if tarefa.imagem else None,
                'destinado': tarefa.destinado or '',
                'responsavel': tarefa.responsavel or '',
                'responsavel_label': tarefa.get_responsavel_display() if tarefa.responsavel else '',
                'responsavel_cor': tarefa.responsavel_cor,
                'criador': (tarefa.usuario.get_full_name() or tarefa.usuario.username) if tarefa.usuario else '',
                'cor': tarefa.cor,
                'prioridade': tarefa.prioridade,
                'data_criacao': tarefa.data_criacao.strftime('%d/%m/%Y'),
                'mensagem_status': tarefa.mensagem_status or '',
            }
        })
    except TarefaInteligencia.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tarefa não encontrada'}, status=404)


@login_required
@require_POST
def atualizar_tarefa(request, tarefa_id):
    try:
        tarefa = TarefaInteligencia.objects.get(id=tarefa_id)

        tarefa.titulo = request.POST.get('titulo', tarefa.titulo)
        tarefa.descricao = request.POST.get('descricao', tarefa.descricao)
        tarefa.status = request.POST.get('status', tarefa.status)
        tarefa.prioridade = request.POST.get('prioridade', tarefa.prioridade)
        tarefa.destinado = request.POST.get('destinado', tarefa.destinado)
        tarefa.responsavel = request.POST.get('responsavel') or None
        tarefa.responsavel_cor = request.POST.get('responsavel_cor', tarefa.responsavel_cor)
        tarefa.cor = request.POST.get('cor', tarefa.cor)

        data_limite = request.POST.get('data_limite')
        tarefa.data_limite = data_limite or None

        # 🆕 CONTROLE DE CONCLUSÃO
        if tarefa.status == 'concluido':
            # Quando concluir:
            if not tarefa.data_conclusao:
                tarefa.data_conclusao = timezone.now().date()
            # 🔥 ZERA O PRAZO
            tarefa.data_limite = None
            tarefa.mensagem_status = 'Ticket concluído.'
        else:
            # Se voltar para outro status:
            tarefa.data_conclusao = None
            # Se voltou, restaura o prazo (se tiver sido preenchido)
            if data_limite:
                tarefa.data_limite = data_limite
            if tarefa.status == 'a_fazer':
                tarefa.mensagem_status = 'Ticket avaliado'
            elif tarefa.status in ('em_progresso', 'validacao'):
                tarefa.mensagem_status = 'Ticket em andamento'

        # ATUALIZA IMAGEM SE ENVIAR
        if request.FILES.get('imagem'):
            tarefa.imagem = request.FILES.get('imagem')

        tarefa.save()

        return JsonResponse({'success': True})

    except TarefaInteligencia.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tarefa não encontrada'}, status=404)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

# @login_required
# @require_POST
# def atualizar_status(request, tarefa_id):
#     tarefa = TarefaInteligencia.objects.get(id=tarefa_id)
#     tarefa.status = request.POST.get('status')
#     tarefa.save()
#     return JsonResponse({'success': True})

@login_required
@require_POST
def atualizar_status(request, tarefa_id):
    tarefa = TarefaInteligencia.objects.get(id=tarefa_id)
    novo_status = request.POST.get('status')

    tarefa.status = novo_status

    # 🆕 CONTROLE DE CONCLUSÃO
    if novo_status == 'concluido':
        if not tarefa.data_conclusao:
            tarefa.data_conclusao = timezone.now().date()
        # 🔥 ZERA O PRAZO
        tarefa.data_limite = None
        tarefa.mensagem_status = 'Ticket concluído.'
    else:
        tarefa.data_conclusao = None
        # Mantém o prazo como estava

        # Mesma dinâmica do Kanban TI: a mudança de coluna atualiza o status;
        # o prazo é definido editando o card (data_limite), não em popup.
        if novo_status == 'a_fazer':
            # Prazo definido no popup ao mover o card.
            prazo_data = request.POST.get('data_limite')
            if prazo_data:
                tarefa.data_limite = prazo_data
            tarefa.mensagem_status = 'Ticket avaliado'
        elif novo_status in ('em_progresso', 'validacao'):
            # Prazo definido no popup ao mover o card.
            prazo_data = request.POST.get('data_limite')
            if prazo_data:
                tarefa.data_limite = prazo_data
            tarefa.mensagem_status = 'Ticket em andamento'

    tarefa.save()

    # 🔥 SLA REAL (em dias)
    sla_dias = None
    if tarefa.data_conclusao:
        sla_dias = (tarefa.data_conclusao - tarefa.data_criacao).days

    return JsonResponse({
        'success': True,
        'status': tarefa.status,
        'data_conclusao': tarefa.data_conclusao.strftime('%d/%m/%Y') if tarefa.data_conclusao else None,
        'sla_dias': sla_dias
    })


@login_required
@require_POST
def deletar_tarefa(request, tarefa_id):
    """
    Deleta uma tarefa
    """
    try:
        tarefa = TarefaInteligencia.objects.get(id=tarefa_id)
        tarefa.delete()
        
        return JsonResponse({'success': True})
    except TarefaInteligencia.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tarefa não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
