import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Case, When, IntegerField
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import TarefaTI


# ===== UTILITÁRIOS =====

def order_by_prioridade(queryset):
    """Ordena queryset por prioridade (alta > média > baixa)"""
    return queryset.annotate(
        prioridade_order=Case(
            When(prioridade='alta', then=3),
            When(prioridade='media', then=2),
            When(prioridade='baixa', then=1),
            default=0,
            output_field=IntegerField()
        )
    ).order_by('-prioridade_order')


def aplicar_conclusao(tarefa, status):
    """
    Aplica lógica de conclusão/reabertura de tarefa.
    - Se concluído: define data_conclusao e zera prazo
    - Se reaberto: limpa data_conclusao
    """
    if status == 'concluido':
        if not tarefa.data_conclusao:
            tarefa.data_conclusao = timezone.now().date()
        tarefa.data_limite = None
    else:
        tarefa.data_conclusao = None


def json_error(message, status=400):
    """Retorna JsonResponse de erro padronizado"""
    return JsonResponse({'success': False, 'error': message}, status=status)


def json_success(**kwargs):
    """Retorna JsonResponse de sucesso padronizado"""
    return JsonResponse({'success': True, **kwargs})


# ===== VIEWS =====

@login_required
def home(request):
    tarefas = TarefaTI.objects.all()

    destinado_filter = request.GET.get('destinado')
    if destinado_filter and destinado_filter != 'all':
        tarefas = tarefas.filter(destinado=destinado_filter)

    a_fazer = order_by_prioridade(tarefas.filter(status='a_fazer'))
    em_progresso = order_by_prioridade(tarefas.filter(status='em_progresso'))
    validacao = order_by_prioridade(tarefas.filter(status='validacao'))
    concluido = order_by_prioridade(tarefas.filter(status='concluido'))

    total_tarefas = tarefas.count()
    total_concluidas = concluido.count()
    taxa_conclusao = round((total_concluidas / total_tarefas * 100) if total_tarefas > 0 else 0)

    context = {
        'a_fazer': a_fazer,
        'em_progresso': em_progresso,
        'validacao': validacao,
        'concluido': concluido,
        'responsavel_choices': TarefaTI.RESPONSAVEL_CHOICES,
        'stats': {
            'total_tarefas': total_tarefas,
            'concluidas': total_concluidas,
            'em_progresso': em_progresso.count(),
            'atrasadas': sum(1 for t in tarefas if t.esta_atrasada),
            'taxa_conclusao': taxa_conclusao,
        },
        'destinado_filter': destinado_filter or 'all',
    }

    return render(request, 'kanban_TI/home.html', context)


@login_required
@require_POST
def adicionar_tarefa(request):
    try:
        TarefaTI.objects.create(
            titulo=request.POST.get('titulo'),
            descricao=request.POST.get('descricao', ''),
            data_limite=request.POST.get('data_limite') or None,
            responsavel=request.POST.get('responsavel') or None,
            responsavel_cor=request.POST.get('responsavel_cor', 'azul'),
            cor=request.POST.get('cor', 'azul'),
            prioridade=request.POST.get('prioridade', 'media'),
            imagem=request.FILES.get('imagem'),
        )
        return json_success()

    except Exception as e:
        return json_error(str(e))


@login_required
def obter_tarefa(request, tarefa_id):
    try:
        tarefa = TarefaTI.objects.get(id=tarefa_id)

        return json_success(tarefa={
            'id': tarefa.id,
            'titulo': tarefa.titulo,
            'descricao': tarefa.descricao,
            'status': tarefa.status,
            'data_limite': tarefa.data_limite.strftime('%Y-%m-%d') if tarefa.data_limite else '',
            'data_criacao': tarefa.data_criacao.strftime('%d/%m/%Y'),
            'data_conclusao': tarefa.data_conclusao.strftime('%d/%m/%Y') if tarefa.data_conclusao else None,
            'esta_atrasada': tarefa.esta_atrasada,
            'imagem_url': tarefa.imagem.url if tarefa.imagem else None,
            'responsavel': tarefa.responsavel or '',
            'responsavel_label': tarefa.get_responsavel_display() if tarefa.responsavel else '',
            'responsavel_cor': tarefa.responsavel_cor,
            'cor': tarefa.cor,
            'prioridade': tarefa.prioridade,
        })

    except TarefaTI.DoesNotExist:
        return json_error('Tarefa não encontrada', status=404)


@login_required
@require_POST
def atualizar_tarefa(request, tarefa_id):
    try:
        tarefa = TarefaTI.objects.get(id=tarefa_id)

        tarefa.titulo = request.POST.get('titulo', tarefa.titulo)
        tarefa.descricao = request.POST.get('descricao', tarefa.descricao)
        tarefa.status = request.POST.get('status', tarefa.status)
        tarefa.prioridade = request.POST.get('prioridade', tarefa.prioridade)
        tarefa.responsavel = request.POST.get('responsavel') or None
        tarefa.responsavel_cor = request.POST.get('responsavel_cor', tarefa.responsavel_cor)
        tarefa.cor = request.POST.get('cor', tarefa.cor)

        data_limite = request.POST.get('data_limite')
        if tarefa.status != 'concluido' and data_limite:
            tarefa.data_limite = data_limite

        aplicar_conclusao(tarefa, tarefa.status)

        if request.FILES.get('imagem'):
            tarefa.imagem = request.FILES.get('imagem')

        tarefa.save()
        return json_success()

    except TarefaTI.DoesNotExist:
        return json_error('Tarefa não encontrada', status=404)

    except Exception as e:
        return json_error(str(e))


@login_required
@require_POST
def atualizar_status(request, tarefa_id):
    try:
        tarefa = TarefaTI.objects.get(id=tarefa_id)
        novo_status = request.POST.get('status')

        tarefa.status = novo_status
        aplicar_conclusao(tarefa, novo_status)
        tarefa.save()

        sla_dias = None
        if tarefa.data_conclusao:
            sla_dias = (tarefa.data_conclusao - tarefa.data_criacao).days

        return json_success(
            status=tarefa.status,
            data_conclusao=tarefa.data_conclusao.strftime('%d/%m/%Y') if tarefa.data_conclusao else None,
            sla_dias=sla_dias
        )

    except TarefaTI.DoesNotExist:
        return json_error('Tarefa não encontrada', status=404)

    except Exception as e:
        return json_error(str(e))


@login_required
@require_POST
def deletar_tarefa(request, tarefa_id):
    try:
        tarefa = TarefaTI.objects.get(id=tarefa_id)
        tarefa.delete()
        return json_success()

    except TarefaTI.DoesNotExist:
        return json_error('Tarefa não encontrada', status=404)

    except Exception as e:
        return json_error(str(e))
    
@login_required
def exportar_tarefas(request):

    tarefas = TarefaTI.objects.all().order_by('-data_criacao')

    STATUS_ROTULOS = {
        'a_fazer': 'A Fazer',
        'em_progresso': 'Em Progresso',
        'validacao': 'Aguardando Validação',
        'concluido': 'Concluído',
    }

    PRIORIDADE_ROTULOS = {
        'baixa': 'Baixa',
        'media': 'Média',
        'alta': 'Alta',
    }

    estilo_cabecalho_fonte = Font(name='Arial', bold=True, color='FFFFFF', size=11)
    estilo_cabecalho_fundo = PatternFill('solid', fgColor='1B1F2E')
    estilo_cabecalho_alinhamento = Alignment(horizontal='center', vertical='center', wrap_text=True)

    estilo_dado_fonte = Font(name='Arial', size=10, color='222222')
    estilo_dado_alinhamento = Alignment(vertical='center', wrap_text=True)

    estilo_borda = Border(
        left=Side(style='thin', color='DDDDDD'),
        right=Side(style='thin', color='DDDDDD'),
        top=Side(style='thin', color='DDDDDD'),
        bottom=Side(style='thin', color='DDDDDD'),
    )

    cores_status = {
        'a_fazer':      PatternFill('solid', fgColor='D6EAF8'),
        'em_progresso': PatternFill('solid', fgColor='FEF5E7'),
        'validacao':    PatternFill('solid', fgColor='FADBD8'),
        'concluido':    PatternFill('solid', fgColor='D5F5E3'),
    }

    cores_prioridade = {
        'baixa': PatternFill('solid', fgColor='D5F5E3'),
        'media': PatternFill('solid', fgColor='FEF5E7'),
        'alta':  PatternFill('solid', fgColor='FADBD8'),
    }

    wb = Workbook()
    ws = wb.active
    ws.title = 'Chamados TI'
    ws.sheet_view.showGridLines = False

    colunas = [
        'Nº Chamado', 'Título', 'Descrição', 'Status',
        'Responsável', 'Prioridade', 'Data de Abertura',
        'Data de Conclusão', 'SLA (dias)',
    ]

    ws.row_dimensions[1].height = 28

    for col_idx, nome in enumerate(colunas, start=1):
        celula = ws.cell(row=1, column=col_idx, value=nome)
        celula.font = estilo_cabecalho_fonte
        celula.fill = estilo_cabecalho_fundo
        celula.alignment = estilo_cabecalho_alinhamento
        celula.border = estilo_borda

    for linha, tarefa in enumerate(tarefas, start=2):

        if tarefa.data_conclusao:
            sla = (tarefa.data_conclusao - tarefa.data_criacao).days
        else:
            sla = '—'

        valores = [
            f'INT-{tarefa.id:03d}',
            tarefa.titulo,
            tarefa.descricao or '—',
            STATUS_ROTULOS.get(tarefa.status, tarefa.status),
            tarefa.get_responsavel_display() if tarefa.responsavel else '—',
            PRIORIDADE_ROTULOS.get(tarefa.prioridade, tarefa.prioridade),
            tarefa.data_criacao.strftime('%d/%m/%Y') if tarefa.data_criacao else '—',
            tarefa.data_conclusao.strftime('%d/%m/%Y') if tarefa.data_conclusao else '—',
            sla,
        ]

        for col_idx, valor in enumerate(valores, start=1):
            celula = ws.cell(row=linha, column=col_idx, value=valor)
            celula.font = estilo_dado_fonte
            celula.alignment = estilo_dado_alinhamento
            celula.border = estilo_borda

        ws.cell(row=linha, column=4).fill = cores_status.get(tarefa.status)

        ws.cell(row=linha, column=6).fill = cores_prioridade.get(tarefa.prioridade)

        if linha % 2 == 0:
            fundo_linha = PatternFill('solid', fgColor='F4F6F7')
            for col_idx in range(1, len(colunas) + 1):
                celula = ws.cell(row=linha, column=col_idx)
                if col_idx not in (4, 6):
                    celula.fill = fundo_linha

    larguras = {'A': 14, 'B': 38, 'C': 48, 'D': 24, 'E': 18, 'F': 15, 'G': 20, 'H': 20, 'I': 14}
    for letra, largura in larguras.items():
        ws.column_dimensions[letra].width = largura

    ws.freeze_panes = 'A2'

    resumo = wb.create_sheet('Resumo')

    resumo['A1'] = 'Resumo dos Chamados'
    resumo['A1'].font = Font(name='Arial', bold=True, size=14, color='FFFFFF')
    resumo['A1'].fill = PatternFill('solid', fgColor='1B1F2E')
    resumo.merge_cells('A1:B1')
    resumo.row_dimensions[1].height = 30

    dados_resumo = [
        ('Total de Chamados',        tarefas.count()),
        ('A Fazer',                  tarefas.filter(status='a_fazer').count()),
        ('Em Progresso',             tarefas.filter(status='em_progresso').count()),
        ('Aguardando Validação',    tarefas.filter(status='validacao').count()),
        ('Concluídos',               tarefas.filter(status='concluido').count()),
        ('Atrasados',                sum(1 for t in tarefas if t.esta_atrasada)),
    ]

    for i, (rotulo, valor) in enumerate(dados_resumo, start=2):
        resumo.cell(row=i, column=1, value=rotulo).font = Font(name='Arial', bold=True, size=10)
        resumo.cell(row=i, column=1).border = estilo_borda
        resumo.cell(row=i, column=2, value=valor).font = Font(name='Arial', size=10)
        resumo.cell(row=i, column=2).border = estilo_borda

    resumo.column_dimensions['A'].width = 28
    resumo.column_dimensions['B'].width = 14

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    nome_arquivo = f"Chamados_TI_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'

    return response