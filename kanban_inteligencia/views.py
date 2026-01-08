from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import TarefaInteligencia
import json


@login_required
def home(request):
    """
    Kanban de Inteligência
    """
    tarefas = TarefaInteligencia.objects.all()
    
    a_fazer = tarefas.filter(status='a_fazer')
    em_progresso = tarefas.filter(status='em_progresso')
    validacao = tarefas.filter(status='validacao')
    concluido = tarefas.filter(status='concluido')
    
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
    """
    Adiciona nova tarefa via AJAX
    """
    try:
        data = json.loads(request.body)
        
        data_limite = data.get('data_limite', None)
        if data_limite == '':
            data_limite = None
        
        tarefa = TarefaInteligencia.objects.create(
            titulo=data.get('titulo'),
            descricao=data.get('descricao', ''),
            data_limite=data_limite,
            responsavel=data.get('responsavel', ''),
            responsavel_cor=data.get('responsavel_cor', 'azul'),
            cor=data.get('cor', 'azul'),
            prioridade=data.get('prioridade', False)
        )
        
        return JsonResponse({
            'success': True,
            'tarefa': {
                'id': tarefa.id,
                'titulo': tarefa.titulo,
                'descricao': tarefa.descricao,
                'data_criacao': tarefa.data_criacao.strftime('%d/%m/%Y'),
                'responsavel': tarefa.responsavel or '',
                'responsavel_cor': tarefa.responsavel_cor,
            }
        })
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
    """
    Atualiza uma tarefa existente
    """
    try:
        from django.utils import timezone
        data = json.loads(request.body)
        tarefa = TarefaInteligencia.objects.get(id=tarefa_id)
        
        # Atualizar campos apenas se fornecidos
        if 'titulo' in data:
            tarefa.titulo = data.get('titulo', tarefa.titulo)
        if 'descricao' in data:
            tarefa.descricao = data.get('descricao', tarefa.descricao)
        
        # Atualizar status e data_conclusao
        if 'status' in data:
            novo_status = data.get('status', tarefa.status)
            if novo_status == 'concluido' and tarefa.status != 'concluido':
                tarefa.data_conclusao = timezone.now().date()
            elif novo_status != 'concluido':
                tarefa.data_conclusao = None
            tarefa.status = novo_status
        
        if 'prioridade' in data:
            tarefa.prioridade = data.get('prioridade', tarefa.prioridade)
        
        # Atualizar responsavel
        if 'responsavel' in data:
            tarefa.responsavel = data.get('responsavel', '')
        
        # Atualizar responsavel_cor
        if 'responsavel_cor' in data:
            tarefa.responsavel_cor = data.get('responsavel_cor', 'azul')
        
        # Atualizar cor
        if 'cor' in data:
            tarefa.cor = data.get('cor', 'azul')
        
        # Atualizar data_limite
        if 'data_limite' in data:
            data_limite = data.get('data_limite')
            if data_limite == '' or data_limite is None:
                tarefa.data_limite = None
            else:
                tarefa.data_limite = data_limite
        
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
