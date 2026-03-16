from django.shortcuts import render, redirect
from .models import TarefaMarketing
from django.db.models import Case, When, IntegerField
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST

def home_marketing(request):
    # LÓGICA PARA SALVAR (Caso o formulário do Modal seja enviado)
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        descricao = request.POST.get('descricao')
        responsavel = request.POST.get('responsavel')
        prioridade = request.POST.get('prioridade')
        data_limite = request.POST.get('data_limite')
        imagem = request.FILES.get('imagem')

        if titulo: # Garantia mínima de que tem um título
            TarefaMarketing.objects.create(
                titulo=titulo,
                descricao=descricao,
                responsavel=responsavel,
                prioridade=prioridade,
                data_limite=data_limite if data_limite else None,
                imagem=imagem,
                status='briefing'
            )
        return redirect('kanban_marketing:home')

    # LÓGICA PARA EXIBIR O KANBAN
    tarefas = TarefaMarketing.objects.all()

    def ordenar_por_prioridade(qs):
        return qs.annotate(
            prioridade_order=Case(
                When(prioridade='alta', then=3),
                When(prioridade='media', then=2),
                When(prioridade='baixa', then=1),
                default=0,
                output_field=IntegerField()
            )
        ).order_by('-prioridade_order')

    def preparar_tarefas(qs):
        tarefas_ordenadas = list(ordenar_por_prioridade(qs))
        for tarefa in tarefas_ordenadas:
            if tarefa.data_limite and tarefa.data_criacao:
                total_dias = (tarefa.data_limite - tarefa.data_criacao).days
                tarefa.total_dias_previstos = max(total_dias, 0)
            else:
                tarefa.total_dias_previstos = None
        return tarefas_ordenadas

    context = {
        'briefing': preparar_tarefas(tarefas.filter(status='briefing')),
        'em_producao': preparar_tarefas(tarefas.filter(status='em_producao')),
        'publicado': preparar_tarefas(tarefas.filter(status='publicado')),
        'concluido': preparar_tarefas(tarefas.filter(status='concluido')),
    }
    
    return render(request, 'kanban_marketing/home.html', context)

# Adicione esta função ao final do arquivo
@require_POST
def atualizar_status_marketing(request, tarefa_id):
    try:
        data = json.loads(request.body)
        novo_status = data.get('status')
        tarefa = TarefaMarketing.objects.get(id=tarefa_id)
        tarefa.status = novo_status
        tarefa.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

# Função para buscar os dados e preencher o modal de edição
def obter_tarefa_marketing(request, tarefa_id):
    try:
        tarefa = TarefaMarketing.objects.get(id=tarefa_id)
        total_dias_previstos = None
        if tarefa.data_limite and tarefa.data_criacao:
            total_dias_previstos = max((tarefa.data_limite - tarefa.data_criacao).days, 0)

        data = {
            'id': tarefa.id,
            'titulo': tarefa.titulo,
            'descricao': tarefa.descricao,
            'responsavel': tarefa.responsavel,
            'responsavel_display': tarefa.get_responsavel_display(),
            'prioridade': tarefa.prioridade,
            'prioridade_display': tarefa.get_prioridade_display(),
            'status': tarefa.status,
            'status_display': tarefa.get_status_display(),
            'data_criacao': tarefa.data_criacao.strftime('%d/%m/%Y') if tarefa.data_criacao else '',
            'data_limite': tarefa.data_limite.strftime('%Y-%m-%d') if tarefa.data_limite else '',
            'data_limite_display': tarefa.data_limite.strftime('%d/%m/%Y') if tarefa.data_limite else '',
            'esta_atrasada': tarefa.esta_atrasada,
            'total_dias_previstos': total_dias_previstos,
            'imagem_url': tarefa.imagem.url if tarefa.imagem else '',
        }
        return JsonResponse(data)
    except TarefaMarketing.DoesNotExist:
        return JsonResponse({'error': 'Tarefa não encontrada'}, status=404)

# Função para salvar a edição
@require_POST
def editar_tarefa_marketing(request, tarefa_id):
    tarefa = TarefaMarketing.objects.get(id=tarefa_id)
    tarefa.titulo = request.POST.get('titulo')
    tarefa.descricao = request.POST.get('descricao')
    tarefa.responsavel = request.POST.get('responsavel')
    tarefa.prioridade = request.POST.get('prioridade')
    imagem = request.FILES.get('imagem')
    
    data_limite = request.POST.get('data_limite')
    tarefa.data_limite = data_limite if data_limite else None

    if imagem:
        tarefa.imagem = imagem
    
    tarefa.save()
    return redirect('kanban_marketing:home')

@require_POST
def toggle_aprovacao_briefing(request, tarefa_id):
    try:
        tarefa = TarefaMarketing.objects.get(id=tarefa_id)
        # Só permite aprovar se ainda estiver em briefing
        if tarefa.status != 'briefing':
            return JsonResponse(
                {'success': False, 'error': 'Tarefa não está mais em briefing.'},
                status=400
            )
        tarefa.briefing_aprovado = not tarefa.briefing_aprovado
        tarefa.save(update_fields=['briefing_aprovado'])
        return JsonResponse({'success': True, 'aprovado': tarefa.briefing_aprovado})
    except TarefaMarketing.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Tarefa não encontrada.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)