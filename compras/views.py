from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.db.models import Sum, Count, Q
from .models import CadastroTipoProduto, EntradaProduto, RecebimentoChip, EntregaChip
from .forms import CadastroTipoProdutoForm, EntradaProdutoForm, FiltroEntradaProdutoForm, RecebimentoChipForm

# Create your views here.

def index(request):
    """View principal do app compras"""
    # Buscar estatísticas para o dashboard
    total_produtos = CadastroTipoProduto.objects.count()
    total_entradas = EntradaProduto.objects.count()
    produtos_recentes = CadastroTipoProduto.objects.all()[:5]  # Últimos 5 produtos
    entradas_recentes = EntradaProduto.objects.select_related('codigo_produto').all()[:5]  # Últimas 5 entradas
    
    return render(request, 'compras/index.html', {
        'total_produtos': total_produtos,
        'total_entradas': total_entradas,
        'produtos_recentes': produtos_recentes,
        'entradas_recentes': entradas_recentes,
    })

def cadastro_tipo_produto(request):
    """View para cadastro de tipo de produto"""
    if request.method == 'POST':
        form = CadastroTipoProdutoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produto cadastrado com sucesso!')
            return redirect('compras:cadastro_tipo_produto')
    else:
        form = CadastroTipoProdutoForm()
    
    produtos = CadastroTipoProduto.objects.all()
    return render(request, 'compras/cadastro_tipo_produto.html', {
        'form': form,
        'produtos': produtos
    })

def entrada_produto(request):
    """View para entrada de produto"""
    if request.method == 'POST':
        form = EntradaProdutoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Entrada de produto registrada com sucesso!')
            return redirect('compras:entrada_produto')
    else:
        form = EntradaProdutoForm()
    
    # Filtro de equipamentos
    filtro_form = FiltroEntradaProdutoForm(request.GET)
    entradas = EntradaProduto.objects.select_related('codigo_produto').all()
    
    # Aplicar filtro se fornecido
    if filtro_form.is_valid() and filtro_form.cleaned_data.get('id_equipamento'):
        id_equipamento = filtro_form.cleaned_data['id_equipamento']
        entradas = entradas.filter(id_equipamento__icontains=id_equipamento)
    
    return render(request, 'compras/entrada_produto.html', {
        'form': form,
        'filtro_form': filtro_form,
        'entradas': entradas
    })

def recebimento_chip(request):
    """View para controle de recebimento de chips"""
    if request.method == 'POST':
        form = RecebimentoChipForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Recebimento de chip registrado com sucesso!')
            return redirect('compras:recebimento_chip')
    else:
        form = RecebimentoChipForm()
    
    # Buscar todos os recebimentos ordenados por data de cadastro
    recebimentos = RecebimentoChip.objects.all()
    
    # Estatísticas por operadora
    stats_operadora = RecebimentoChip.objects.values('operadora').annotate(
        total_chips=Sum('quantidade'),
        total_entregue=Sum('quantidade_entregue'),
        total_lotes=Count('id')
    ).order_by('-total_chips')
    
    # Calcular chips restantes para cada operadora
    for stat in stats_operadora:
        stat['chips_restantes'] = stat['total_chips'] - (stat['total_entregue'] or 0)
        if stat['total_chips'] > 0:
            stat['percentual_entregue'] = round((stat['total_entregue'] or 0) / stat['total_chips'] * 100, 1)
        else:
            stat['percentual_entregue'] = 0
    
    # Estatísticas gerais
    total_chips = RecebimentoChip.objects.aggregate(Sum('quantidade'))['quantidade__sum'] or 0
    total_entregue = RecebimentoChip.objects.aggregate(Sum('quantidade_entregue'))['quantidade_entregue__sum'] or 0
    total_restante = total_chips - total_entregue
    
    # Histórico de entregas (últimas 20)
    historico_entregas = EntregaChip.objects.select_related('recebimento').order_by('-data_entrega')[:20]
    
    return render(request, 'compras/recebimento_chip.html', {
        'form': form,
        'recebimentos': recebimentos,
        'stats_operadora': stats_operadora,
        'total_chips': total_chips,
        'total_entregue': total_entregue,
        'total_restante': total_restante,
        'historico_entregas': historico_entregas,
    })

def editar_recebimento_chip(request, pk):
    """View para editar campos opcionais do recebimento de chip"""
    recebimento = get_object_or_404(RecebimentoChip, pk=pk)
    
    if request.method == 'POST':
        # Atualizar apenas os campos opcionais
        data_envio = request.POST.get('data_envio_configuracao')
        nome_recebedor = request.POST.get('nome_recebedor')
        
        if data_envio:
            recebimento.data_envio_configuracao = data_envio
        if nome_recebedor:
            recebimento.nome_recebedor = nome_recebedor
        
        recebimento.save()
        messages.success(request, 'Recebimento atualizado com sucesso!')
        return redirect('compras:recebimento_chip')
    
    # Para requisições GET/AJAX, retornar dados em JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = {
            'id': recebimento.id,
            'operadora': recebimento.operadora,
            'quantidade': recebimento.quantidade,
            'data_envio_configuracao': recebimento.data_envio_configuracao.strftime('%Y-%m-%d') if recebimento.data_envio_configuracao else '',
            'nome_recebedor': recebimento.nome_recebedor or '',
        }
        return JsonResponse(data)
    
    return redirect('compras:recebimento_chip')

def registrar_entrega_chip(request, pk):
    """View para registrar entrega de chips por operadora"""
    if request.method == 'POST':
        operadora = request.POST.get('operadora', '').strip()
        quantidade = int(request.POST.get('quantidade_entrega', 0))
        responsavel = request.POST.get('responsavel_entrega', '').strip()
        observacao = request.POST.get('observacao_entrega', '').strip()
        
        # Buscar total disponível da operadora
        recebimentos_operadora = RecebimentoChip.objects.filter(operadora=operadora)
        total_disponivel = sum(r.quantidade_restante for r in recebimentos_operadora)
        
        # Validar quantidade
        if quantidade <= 0:
            messages.error(request, 'Quantidade inválida!')
            return redirect('compras:recebimento_chip')
        
        if quantidade > total_disponivel:
            messages.error(request, f'Quantidade excede o disponível ({total_disponivel} chips)!')
            return redirect('compras:recebimento_chip')
        
        if not responsavel:
            messages.error(request, 'Nome do responsável é obrigatório!')
            return redirect('compras:recebimento_chip')
        
        # Distribuir a entrega pelos lotes (FIFO - primeiro a entrar, primeiro a sair)
        quantidade_restante = quantidade
        for recebimento in recebimentos_operadora.order_by('data_chegada_golden'):
            if quantidade_restante <= 0:
                break
                
            disponivel_lote = recebimento.quantidade_restante
            if disponivel_lote > 0:
                quantidade_deste_lote = min(quantidade_restante, disponivel_lote)
                
                # Criar registro de entrega
                EntregaChip.objects.create(
                    recebimento=recebimento,
                    quantidade_entregue=quantidade_deste_lote,
                    responsavel=responsavel,
                    observacao=observacao
                )
                
                # Atualizar quantidade entregue do recebimento
                recebimento.quantidade_entregue += quantidade_deste_lote
                recebimento.save()
                
                quantidade_restante -= quantidade_deste_lote
        
        messages.success(request, f'{quantidade} chips de {operadora} entregues com sucesso para {responsavel}!')
        return redirect('compras:recebimento_chip')
    
    return redirect('compras:recebimento_chip')

def deletar_recebimento_chip(request, pk):
    """View para deletar um recebimento de chip"""
    recebimento = get_object_or_404(RecebimentoChip, pk=pk)
    
    if request.method == 'POST':
        # Verificar se há entregas associadas
        entregas = EntregaChip.objects.filter(recebimento=recebimento)
        
        # Deletar entregas primeiro (cascade)
        entregas.delete()
        
        # Deletar o recebimento
        operadora = recebimento.operadora
        recebimento.delete()
        
        messages.success(request, f'Recebimento de {operadora} deletado com sucesso!')
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)
