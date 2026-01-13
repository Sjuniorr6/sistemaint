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
    tarefas = TarefaInteligencia.objects.all()

    def order_by_prioridade(queryset):
        return queryset.annotate(
            prioridade_order=Case(
                When(prioridade='alta', then=3),
                When(prioridade='media', then=2),
                When(prioridade='baixa', then=1),
                default=0,
                output_field=IntegerField()
            )
        ).order_by('-prioridade_order')

    a_fazer = order_by_prioridade(tarefas.filter(status='a_fazer'))
    em_progresso = order_by_prioridade(tarefas.filter(status='em_progresso'))
    validacao = order_by_prioridade(tarefas.filter(status='validacao'))
    concluido = order_by_prioridade(tarefas.filter(status='concluido'))
    
    # Estatísticas
    total_tarefas = tarefas.count()
    total_concluidas = concluido.count()
    total_em_progresso = em_progresso.count()
    total_atrasadas = sum(1 for t in tarefas if t.esta_atrasada)
    taxa_conclusao = round((total_concluidas / total_tarefas * 100) if total_tarefas > 0 else 0)
    
    context = {
        'a_fazer': a_fazer,
        'em_progresso': em_progresso,
        'validacao': validacao,
        'concluido': concluido,
        'stats': {
            'total_tarefas': total_tarefas,
            'concluidas': total_concluidas,
            'em_progresso': total_em_progresso,
            'atrasadas': total_atrasadas,
            'taxa_conclusao': taxa_conclusao,
        }
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
            responsavel=request.POST.get('responsavel', ''),
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
                'responsavel_cor': tarefa.responsavel_cor,
                'cor': tarefa.cor,
                'prioridade': tarefa.prioridade,
                'data_criacao': tarefa.data_criacao.strftime('%d/%m/%Y'),
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
        tarefa.responsavel = request.POST.get('responsavel', tarefa.responsavel)
        tarefa.responsavel_cor = request.POST.get('responsavel_cor', tarefa.responsavel_cor)
        tarefa.cor = request.POST.get('cor', tarefa.cor)

        data_limite = request.POST.get('data_limite')
        tarefa.data_limite = data_limite or None

        # Controle de conclusão
        if tarefa.status == 'concluido' and not tarefa.data_conclusao:
            tarefa.data_conclusao = timezone.now().date()
        elif tarefa.status != 'concluido':
            tarefa.data_conclusao = None

        # 👇 ATUALIZA IMAGEM SE ENVIAR
        if request.FILES.get('imagem'):
            tarefa.imagem = request.FILES.get('imagem')

        tarefa.save()

        return JsonResponse({'success': True})

    except TarefaInteligencia.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tarefa não encontrada'}, status=404)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

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
