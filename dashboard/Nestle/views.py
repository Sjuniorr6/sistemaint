from django.urls import reverse_lazy, path
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from .models import GridInternacional as GridInternacionalModel, clientesNestle, ValorMensalCliente
from .forms import GridInternacionalForm, ValorMensalForm
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
import datetime
from django.core.mail import EmailMessage
import pandas as pd
from io import BytesIO
from django.core.serializers import serialize
import json
from decimal import Decimal
import math

# Create your views here.

@method_decorator(csrf_exempt, name='dispatch')
class GridInternacional(ListView):
    model = GridInternacionalModel
    template_name = 'grid_internacional_list.html'
    context_object_name = 'object_list'

    def get_queryset(self):
        queryset = super().get_queryset()
        cliente = self.request.GET.get('cliente')
        container = self.request.GET.get('container')
        status_operacao = self.request.GET.get('status_operacao')
        ids = self.request.GET.get('ids')
        sem_dados = self.request.GET.get('sem_dados')

        if ids:
            id_list = [i.strip() for i in ids.replace('\n', ',').replace(';', ',').split(',') if i.strip()]
            queryset = super().get_queryset()
            queryset = [obj for obj in queryset if str(obj.id_planilha) in id_list]
            # Ordenar por id_planilha e por data_insercao (ou data_envio, ou data.min)
            queryset = sorted(
                queryset,
                key=lambda obj: (
                    str(obj.id_planilha),
                    obj.data_insercao or obj.data_envio or datetime.date.min
                )
            )
            return queryset

        if sem_dados:
            queryset = [obj for obj in queryset if (not obj.destino or not obj.bl or not obj.container or not obj.local) and obj.get_status_automatico() != 'Reversa Finalizada']
            return queryset

        if cliente:
            queryset = queryset.filter(cliente__icontains=cliente)
        if container:
            queryset = queryset.filter(container__icontains=container)
        queryset = list(queryset)
        
        # Excluir registros com golden_sat preenchido e com status 'Reversa Finalizada' do grid principal
        # Mas manter os registros com status 'Danificado'
        queryset = [obj for obj in queryset if (not obj.golden_sat and obj.get_status_automatico() != 'Reversa Finalizada') or obj.get_status_automatico() == 'Danificado']
        
        # Filtro de status agora usa status automático (reforçado)
        if status_operacao:
            queryset = [obj for obj in queryset if obj.get_status_automatico() == status_operacao]
        
        # Ordenar por id_planilha para agrupar registros iguais
        queryset = sorted(queryset, key=lambda obj: str(obj.id_planilha))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clientes'] = clientesNestle.objects.all().order_by('cliente')
        
        # Adicionar contagem de equipamentos e quantidade do cliente
        cliente_nome = self.request.GET.get('cliente')
        if cliente_nome:
            # Pegar todos os registros do cliente
            qs = list(GridInternacionalModel.objects.filter(cliente__icontains=cliente_nome))
            # Contar equipamentos (excluindo Reversa Finalizada, mas incluindo Extraviado)
            equipamentos_count = len([
                obj for obj in qs
                if obj.get_status_automatico() != 'Reversa Finalizada' or obj.get_status_automatico() == 'Extraviado'
            ])
            context['equipamentos_count'] = equipamentos_count
            
            # Buscar quantidade do cliente
            cliente_obj = clientesNestle.objects.filter(cliente__icontains=cliente_nome).first()
            context['quantidade_cliente'] = cliente_obj.quantidade if cliente_obj else None
            
            # Calcular diferença
            if cliente_obj and cliente_obj.quantidade is not None:
                context['diferenca_qtd'] = equipamentos_count - cliente_obj.quantidade
            else:
                context['diferenca_qtd'] = None
        else:
            context['equipamentos_count'] = None
            context['quantidade_cliente'] = None
            context['diferenca_qtd'] = None

        # Contagem de registros filtrados (após todos os filtros)
        queryset_filtrado = self.get_queryset()
        context['total_filtrado'] = len(queryset_filtrado)

        # Contagem de status dos registros filtrados
        status_counts_filtrados = {}
        for obj in queryset_filtrado:
            status = obj.get_status_automatico()
            status_counts_filtrados[status] = status_counts_filtrados.get(status, 0) + 1
        context['status_counts_filtrados'] = status_counts_filtrados

        # Contagem por status para o cliente filtrado (usando apenas registros mais recentes)
        status_counts = {s: 0 for s in [
            'Reversa Finalizada',
            'Em reversa para o Brasil',
            'Retirado, Ag. Envio',
            'Em viagem',
            'No destino',
            'Estoque Cliente',
            'Danificado',
            'Extraviado',
            'Estoque Golden',
        ]}
        if cliente_nome:
            qs = list(GridInternacionalModel.objects.filter(cliente__icontains=cliente_nome))
            for obj in qs:
                status = obj.get_status_automatico()
                if status in status_counts:
                    status_counts[status] += 1
        context['status_counts'] = status_counts

        # Cálculo correto dos SLAs para cada registro filtrado
        sla_labels = [
            ('sla_insercao', lambda o: (o.data_insercao, o.data_envio)),
            ('sla_viagem', lambda o: (o.data_chegada_destino, o.data_insercao)),
            ('sla_retirada', lambda o: (o.data_retirada, o.data_chegada_destino)),
            ('sla_envio_brasil', lambda o: (o.data_envio_brasil, o.data_retirada)),
            ('sla_chegada_brasil', lambda o: (o.data_brasil, o.data_envio_brasil)),
            ('sla_porto_nacional', lambda o: (o.data_chegada_porto, o.data_insercao)),
            ('sla_embarque', lambda o: (o.data_embarque_maritimo, o.data_chegada_porto)),
            ('sla_maritimo', lambda o: (o.data_desembarque_maritimo, o.data_embarque_maritimo)),
            ('sla_terrestre_internacional', lambda o: (o.data_chegada_destino, o.data_desembarque_maritimo)),
            ('sla_terrestre', lambda o: (o.data_chegada_destino, o.data_desembarque_maritimo)),
            ('sla_internacional', lambda o: (o.data_retirada, o.data_chegada_destino)),
            ('sla_liberacao', lambda o: (o.liberacao, o.data_brasil)),
        ]
        sla_medias_grid = {}
        sla_valores_por_registro = []
        for obj in queryset_filtrado:
            sla_dict = {}
            for sla, func in sla_labels:
                d1, d2 = func(obj)
                if d1 and d2:
                    diff = (d1 - d2).days
                    sla_dict[sla] = diff if diff >= 0 else None
                else:
                    sla_dict[sla] = None
            sla_valores_por_registro.append(sla_dict)
        # Calcular médias para cada SLA
        for sla, _ in sla_labels:
            valores = [sla_dict[sla] for sla_dict in sla_valores_por_registro if sla_dict[sla] is not None]
            sla_medias_grid[sla] = int(round(sum(valores)/len(valores))) if valores else None
        # SLA Operação: soma das médias de todos os SLAs exibidos
        sla_operacao_keys = [
            'sla_insercao',
            'sla_retirada',
            'sla_envio_brasil',
            'sla_chegada_brasil',
            'sla_terrestre',
            'sla_envio_brasil',
            'sla_chegada_brasil',
            'sla_terrestre',
            'sla_internacional',
        ]
        sla_medias_grid['sla_operacao'] = sum([sla_medias_grid.get(k, 0) for k in sla_operacao_keys if sla_medias_grid.get(k) is not None])
        context['sla_medias_grid'] = sla_medias_grid

        # Após calcular cada média, dividir por 3 e arredondar para baixo apenas para os dois últimos SLAs
        for key in ['sla_terrestre_internacional', 'sla_terrestre']:
            if sla_medias_grid.get(key) is not None:
                sla_medias_grid[key] = math.floor(sla_medias_grid[key] / 3)

        print('==== DEBUG SLA OPERAÇÃO ===')
        print('Valores usados na soma do SLA de Operação:')
        for k in sla_operacao_keys:
            print(f'{k}:', sla_medias_grid.get(k))
        print('Soma final:', sum([sla_medias_grid[k] for k in sla_operacao_keys if sla_medias_grid.get(k) is not None and sla_medias_grid.get(k) != '-']))

        # Após calcular as médias e ajustar os dois SLAs, faça a soma total usando os valores já ajustados
        sla_soma_total = sum([
            sla_medias_grid.get('sla_insercao') or 0,
            sla_medias_grid.get('sla_retirada') or 0,
            sla_medias_grid.get('sla_envio_brasil') or 0,
            sla_medias_grid.get('sla_chegada_brasil') or 0,
            sla_medias_grid.get('sla_porto_nacional') or 0,
            sla_medias_grid.get('sla_embarque') or 0,
            sla_medias_grid.get('sla_maritimo') or 0,
            sla_medias_grid.get('sla_terrestre_internacional') or 0,
            sla_medias_grid.get('sla_terrestre') or 0,
            sla_medias_grid.get('sla_internacional') or 0,
            sla_medias_grid.get('sla_liberacao') or 0,
        ])
        sla_medias_grid['sla_soma_total'] = sla_soma_total

        return context

    def post(self, request, *args, **kwargs):
        ids_mass = request.POST.get('ids_mass')
        novo_status = request.POST.get('novo_status')
        if ids_mass and novo_status:
            id_list = [i.strip() for i in ids_mass.replace('\n', ',').replace(';', ',').split(',') if i.strip()]
            objs = GridInternacionalModel.objects.filter(id_planilha__in=id_list)
            for obj in objs:
                obj.status_operacao = novo_status
                obj.save()
        return self.get(request, *args, **kwargs)

class GridInternacionalFinalizados(ListView):
    model = GridInternacionalModel
    template_name = 'grid_internacional_finalizados.html'
    context_object_name = 'object_list'

    def get_queryset(self):
        # Retornar apenas os objetos cujo status automático é 'Reversa Finalizada'
        return [obj for obj in GridInternacionalModel.objects.all() if obj.get_status_automatico() == "Reversa Finalizada"]

class GridInternacionalCreate(CreateView):
    model = GridInternacionalModel
    template_name = 'grid_internacional_form.html'
    fields = '__all__'
    success_url = reverse_lazy('grid_internacional_list')

class GridInternacionalUpdate(UpdateView):
    model = GridInternacionalModel
    template_name = 'grid_internacional_form.html'
    fields = '__all__'
    success_url = reverse_lazy('grid_internacional_list')

@method_decorator(csrf_exempt, name='dispatch')
class GridInternacionalDelete(DeleteView):
    model = GridInternacionalModel
    template_name = 'grid_internacional_confirm_delete.html'
    success_url = reverse_lazy('grid_internacional_list')

    def dispatch(self, request, *args, **kwargs):
        if request.method.lower() == 'delete':
            return self.delete(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        print("CHAMOU DELETE VIEW")
        try:
            self.object = self.get_object()
            print("OBJETO:", self.object)
            self.object.delete()
            print("DELETADO!")
            return JsonResponse({'success': True})
        except Exception as e:
            print("ERRO AO DELETAR:", e)
            return JsonResponse({'success': False, 'error': str(e)})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

class GridInternacionalDetail(DetailView):
    model = GridInternacionalModel
    template_name = 'grid_internacional_detail.html'
    context_object_name = 'object'

@csrf_exempt
@require_POST
def grid_internacional_quick_edit(request):
    try:
        field = request.POST.get('field')
        value = request.POST.get('value')
        pk = request.POST.get('pk')

        if not all([field, pk]):
            return JsonResponse({'success': False, 'error': 'Dados incompletos'})

        obj = GridInternacionalModel.objects.get(pk=pk)

        # Se for campo de data, converta para o formato correto
        if field.startswith('data_') or field in ['liberacao', 'coleta', 'golden_sat', 'data_envoice']:
            try:
                value = datetime.datetime.strptime(value, '%Y-%m-%d').date()
            except Exception as e:
                return JsonResponse({'success': False, 'error': 'Data inválida'})

        setattr(obj, field, value)
        obj.save()

        # Se status foi alterado para 'Reversa Finalizada', criar novo registro com mesmo id_planilha
        if field == 'get_status_automatico' and value == 'Reversa Finalizada':
            GridInternacionalModel.objects.create(id_planilha=obj.id_planilha)

        # Formatar valor para exibição
        if field.startswith('data_') or field in ['liberacao', 'coleta', 'golden_sat', 'data_envoice']:
            display_value = value.strftime('%d/%m/%Y')
        else:
            display_value = value

        badge_class = ''
        if field == 'get_status_automatico':
            if value == 'Reversa Finalizada':
                badge_class = 'bg-success'
            elif value == 'Em Viagem':
                badge_class = 'bg-warning'
            elif value == 'Estoque Cliente':
                badge_class = 'bg-info'
            elif value == 'Estoque Golden':
                badge_class = 'bg-primary'
            elif value == 'Extraviado':
                badge_class = 'bg-danger'
            elif value == 'Retirado, Ag. Envio':
                badge_class = 'bg-secondary'
            elif value == 'Aguardando Envio':
                badge_class = 'bg-warning'
            elif value == 'Em reversa para o Brasil':
                badge_class = 'bg-info'
            elif value == 'No destino':
                badge_class = 'bg-secondary'
            else:
                badge_class = 'bg-secondary'

        # Retornar todos os SLAs recalculados
        sla_fields = [
            'sla_insercao', 'sla_viagem', 'sla_retirada', 'sla_envio_brasil', 'sla_chegada_brasil',
            'sla_operacao', 'sla_terrestre', 'sla_maritimo',
            'sla_terminal_internacional', 'sla_terrestre_internacional', 'sla_internacional'
        ]
        sla_data = {f: getattr(obj, f) for f in sla_fields}
        return JsonResponse({'success': True, 'value': display_value, 'badge_class': badge_class, **sla_data})

    except GridInternacionalModel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Registro não encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

class clientesNestleCreate(CreateView):
    model = clientesNestle
    template_name = 'clientes_nestle_form.html'
    fields = '__all__'
    success_url = reverse_lazy('clientes_nestle_create')


class clientesNestleUpdate(UpdateView):
    model = clientesNestle
    template_name = 'clientes_nestle_form.html'
    fields = '__all__'
    success_url = reverse_lazy('clientes_nestle_create')

class ClienteListView(LoginRequiredMixin, ListView):
    model = clientesNestle
    template_name = 'clientes_list.html'
    context_object_name = 'clientes'
    ordering = ['cliente']

class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = clientesNestle
    template_name = 'clientes_form.html'
    fields = ['cliente', 'cnpj', 'endereco', 'quantidade', 'valor', 'local']
    success_url = reverse_lazy('clientes_nestle_list')

class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = clientesNestle
    template_name = 'clientes_form.html'
    fields = ['cliente', 'cnpj', 'endereco', 'quantidade', 'valor', 'local']
    success_url = reverse_lazy('clientes_nestle_list')

class ClienteDeleteView(LoginRequiredMixin, DeleteView):
    model = clientesNestle
    template_name = 'clientes_confirm_delete.html'
    success_url = reverse_lazy('clientes_nestle_list')

@csrf_exempt
def grid_internacional_send_email(request):
    if request.method == 'POST':
        # Pega os filtros do POST
        cliente = request.POST.get('cliente')
        container = request.POST.get('container')
        status_operacao = request.POST.get('status_operacao')
        ids = request.POST.get('ids')

        # Monta o queryset igual ao get_queryset
        queryset = GridInternacionalModel.objects.all()
        if ids:
            id_list = [i.strip() for i in ids.replace('\n', ',').replace(';', ',').split(',') if i.strip()]
            queryset = queryset.filter(id_planilha__in=id_list)
        if cliente:
            queryset = queryset.filter(cliente__icontains=cliente)
        if container:
            queryset = queryset.filter(container__icontains=container)
        if status_operacao:
            queryset = [obj for obj in queryset if obj.get_status_automatico() == status_operacao]

        # Exporta todos os campos do modelo
        campos = [
            'id_planilha', 'requisicao', 'cliente', 'local_de_entrega', 'modelo', 'ccid',
            'sla_insercao', 'data_insercao', 'destino', 'bl', 'container', 'sla_viagem',
            'data_chegada_destino', 'sla_retirada', 'data_retirada', 'sla_envio_brasil',
            'data_envio_brasil', 'sla_chegada_brasil', 'data_brasil', 'status_operacao',
            'sla_operacao', 'reposicao', 'observacao', 'data_chegada_porto', 'data_embarque_maritimo',
            'data_desembarque_maritimo', 'data_envoice', 'data_chegada_terminal', 'data_saida_terminal',
            'sla_porto_nacional', 'sla_terrestre', 'sla_maritimo', 'sla_terminal_internacional',
            'sla_terrestre_internacional', 'local', 'status_container', 'data_desembarque',
            'sla_internacional', 'rf_invoice', 'coleta', 'liberacao', 'golden_sat', 'sla_embarque'
        ]
        data = []
        for obj in queryset:
            row = {campo: getattr(obj, campo, None) for campo in campos}
            # Adiciona o status automático calculado
            row['status_automatico'] = obj.get_status_automatico()
            data.append(row)
        df = pd.DataFrame(data)

        # Salva em memória
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)

        # Envia email
        email = EmailMessage(
            subject='Planilha Grid Internacional',
            body='Segue em anexo a planilha solicitada.',
            from_email=None,
            to=['inteligencia@grupogoldensat.com.br', 'inteligencia6@grupogoldensat.com.br', 'julio.cesar@grupogoldensat.com.br'],
        )
        email.attach('grid_internacional.xlsx', output.read(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        email.send()

        # Redireciona de volta para a página anterior com os mesmos filtros
        redirect_url = reverse_lazy('grid_internacional_list')
        if cliente:
            redirect_url += f'?cliente={cliente}'
        if container:
            redirect_url += f'&container={container}'
        if status_operacao:
            redirect_url += f'&status_operacao={status_operacao}'
        if ids:
            redirect_url += f'&ids={ids}'
        
        return redirect(redirect_url)

    return redirect('grid_internacional_list')

def grid_internacional_api(request):
    """
    API endpoint that returns all GridInternacional data as JSON
    """
    try:
        # Get all objects from GridInternacional model
        queryset = GridInternacionalModel.objects.all()
        
        # Convert queryset to list of dictionaries with all fields
        data = []
        for obj in queryset:
            item = {
                'id': obj.id,
                'data_envio': obj.data_envio.strftime('%Y-%m-%d') if obj.data_envio else None,
                'requisicao': obj.requisicao,
                'cliente': obj.cliente,
                'local_de_entrega': obj.local_de_entrega,
                'modelo': obj.modelo,
                'id_planilha': obj.id_planilha,
                'ccid': obj.ccid,
                'sla_insercao': obj.sla_insercao,
                'data_insercao': obj.data_insercao.strftime('%Y-%m-%d') if obj.data_insercao else None,
                'destino': obj.destino,
                'bl': obj.bl,
                'container': obj.container,
                'sla_viagem': obj.sla_viagem,
                'data_chegada_destino': obj.data_chegada_destino.strftime('%Y-%m-%d') if obj.data_chegada_destino else None,
                'sla_retirada': obj.sla_retirada,
                'data_retirada': obj.data_retirada.strftime('%Y-%m-%d') if obj.data_retirada else None,
                'sla_envio_brasil': obj.sla_envio_brasil,
                'data_envio_brasil': obj.data_envio_brasil.strftime('%Y-%m-%d') if obj.data_envio_brasil else None,
                'sla_chegada_brasil': obj.sla_chegada_brasil,
                'data_brasil': obj.data_brasil.strftime('%Y-%m-%d') if obj.data_brasil else None,
                'status_operacao': obj.status_operacao,
                'sla_operacao': obj.sla_operacao,
                'reposicao': obj.reposicao,
                'observacao': obj.observacao,
                'data_chegada_porto': obj.data_chegada_porto.strftime('%Y-%m-%d') if obj.data_chegada_porto else None,
                'data_embarque_maritimo': obj.data_embarque_maritimo.strftime('%Y-%m-%d') if obj.data_embarque_maritimo else None,
                'data_desembarque_maritimo': obj.data_desembarque_maritimo.strftime('%Y-%m-%d') if obj.data_desembarque_maritimo else None,
                'data_envoice': obj.data_envoice.strftime('%Y-%m-%d') if obj.data_envoice else None,
                'data_chegada_terminal': obj.data_chegada_terminal.strftime('%Y-%m-%d') if obj.data_chegada_terminal else None,
                'data_saida_terminal': obj.data_saida_terminal.strftime('%Y-%m-%d') if obj.data_saida_terminal else None,
                'sla_terrestre': obj.sla_terrestre,
                'sla_maritimo': obj.sla_maritimo,
                'sla_terminal_internacional': obj.sla_terminal_internacional,
                'sla_terrestre_internacional': obj.sla_terrestre_internacional,
                'local': obj.local,
                'status_container': obj.status_container,
                'data_desembarque': obj.data_desembarque.strftime('%Y-%m-%d') if obj.data_desembarque else None,
                'sla_internacional': obj.sla_internacional,
                'rf_invoice': obj.rf_invoice,
                'coleta': obj.coleta.strftime('%Y-%m-%d') if obj.coleta else None,
                'liberacao': obj.liberacao.strftime('%Y-%m-%d') if obj.liberacao else None,
                'golden_sat': obj.golden_sat.strftime('%Y-%m-%d') if obj.golden_sat else None,
                'status_automatico': obj.get_status_automatico()
            }
            data.append(item)
        
        return JsonResponse({
            'status': 'success',
            'data': data
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@csrf_exempt
def grid_internacional_json(request):
    """
    Endpoint que retorna todos os dados do GridInternacional em formato JSON,
    incluindo contagens automáticas por status e médias de SLA por cliente.
    """
    try:
        queryset = GridInternacionalModel.objects.all()
        clientes = clientesNestle.objects.all()
        status_labels = [
            'Em Contrato', 'Em Estoque', 'Em Viagem', 'No Destino',
            'Menos de 75 dias', 'Mais de 75 dias', 'Retirado Ag. Envio',
            'Em Reversa Para o Brasil', 'Reversa Finalizada', 'Resumo Para Envio'
        ]
        sla_labels = [
            'sla_insercao', 'sla_terrestre', 'sla_porto_nacional', 'sla_maritimo',
            'sla_terminal_internacional', 'sla_terrestre_internacional', 'sla_retirada', 'sla_embarque'
        ]
        sla_nomes = {
            'sla_insercao': 'Inserção do Equipamento (dias)',
            'sla_terrestre': 'Tráfego Rodoviário Nacional (dias)',
            'sla_porto_nacional': 'Espera no Porto Nacional (dias)',
            'sla_maritimo': 'Tempo de Viagem Marítima (dias)',
            'sla_terminal_internacional': 'Terminal de Contêiner Internacional (dias)',
            'sla_terrestre_internacional': 'Transporte Terrestre Internacional (dias)',
            'sla_retirada': 'Remoção do Equipamento no Destino (dias)',
            'sla_embarque': 'SLA Embarque (dias)'
        }

        clientes_info = []
        totais = {label: 0 for label in status_labels}
        sla_media_por_etapa = {sla: [] for sla in sla_labels}

        for cliente in clientes:
            registros_final = queryset.filter(cliente__iexact=cliente.cliente.strip())

            status_count = {label: 0 for label in status_labels}
            for label in status_labels:
                if label == 'Menos de 75 dias':
                    status_count[label] = len([r for r in registros_final if r.sla_internacional not in [None, '', ' '] and str(r.sla_internacional).isdigit() and int(r.sla_internacional) < 75])
                elif label == 'Mais de 75 dias':
                    status_count[label] = len([r for r in registros_final if r.sla_internacional not in [None, '', ' '] and str(r.sla_internacional).isdigit() and int(r.sla_internacional) >= 75])
                else:
                    status_count[label] = len([r for r in registros_final if r.get_status_automatico() == label])
                totais[label] += status_count[label]

            sla_media_cliente = {}
            for sla in sla_labels:
                valores = [int(getattr(r, sla)) for r in registros_final if getattr(r, sla, None) not in [None, '', ' '] and str(getattr(r, sla)).isdigit()]
                sla_media_cliente[sla] = sum(valores) / len(valores) if valores else 0
                sla_media_por_etapa[sla].extend(valores)

            clientes_info.append({
                'nome': cliente.cliente,
                'status_count': status_count,
                'sla_media_cliente': sla_media_cliente,
            })

        sla_medias_etapas = {label: [] for label in sla_labels}
        for reg in GridInternacionalModel.objects.all():
            if reg.get_status_automatico() == "Reversa Finalizada":
                continue
            for sla in sla_labels:
                valor = getattr(reg, sla, None)
                if valor not in [None, '', ' '] and str(valor).isdigit():
                    sla_medias_etapas[sla].append(int(valor))
        sla_media_por_etapa = {sla: (sum(sla_medias_etapas[sla])/len(sla_medias_etapas[sla]) if sla_medias_etapas[sla] else 0) for sla in sla_labels}

        # Dados brutos
        data = []
        for obj in queryset:
            item = {
                'id': obj.id,
                'data_envio': obj.data_envio.strftime('%Y-%m-%d') if obj.data_envio else None,
                'requisicao': obj.requisicao,
                'cliente': obj.cliente,
                'local_de_entrega': obj.local_de_entrega,
                'modelo': obj.modelo,
                'id_planilha': obj.id_planilha,
                'ccid': obj.ccid,
                'sla_insercao': obj.sla_insercao,
                'data_insercao': obj.data_insercao.strftime('%Y-%m-%d') if obj.data_insercao else None,
                'destino': obj.destino,
                'bl': obj.bl,
                'container': obj.container,
                'sla_viagem': obj.sla_viagem,
                'data_chegada_destino': obj.data_chegada_destino.strftime('%Y-%m-%d') if obj.data_chegada_destino else None,
                'sla_retirada': obj.sla_retirada,
                'data_retirada': obj.data_retirada.strftime('%Y-%m-%d') if obj.data_retirada else None,
                'sla_envio_brasil': obj.sla_envio_brasil,
                'data_envio_brasil': obj.data_envio_brasil.strftime('%Y-%m-%d') if obj.data_envio_brasil else None,
                'sla_chegada_brasil': obj.sla_chegada_brasil,
                'data_brasil': obj.data_brasil.strftime('%Y-%m-%d') if obj.data_brasil else None,
                'status_operacao': obj.status_operacao,
                'sla_operacao': obj.sla_operacao,
                'reposicao': obj.reposicao,
                'observacao': obj.observacao,
                'data_chegada_porto': obj.data_chegada_porto.strftime('%Y-%m-%d') if obj.data_chegada_porto else None,
                'data_embarque_maritimo': obj.data_embarque_maritimo.strftime('%Y-%m-%d') if obj.data_embarque_maritimo else None,
                'data_desembarque_maritimo': obj.data_desembarque_maritimo.strftime('%Y-%m-%d') if obj.data_desembarque_maritimo else None,
                'data_envoice': obj.data_envoice,
                'data_chegada_terminal': obj.data_chegada_terminal.strftime('%Y-%m-%d') if obj.data_chegada_terminal else None,
                'data_saida_terminal': obj.data_saida_terminal.strftime('%Y-%m-%d') if obj.data_saida_terminal else None,
                'sla_terrestre': obj.sla_terrestre,
                'sla_maritimo': obj.sla_maritimo,
                'sla_terminal_internacional': obj.sla_terminal_internacional,
                'sla_terrestre_internacional': obj.sla_terrestre_internacional,
                'local': obj.local,
                'status_container': obj.status_container,
                'data_desembarque': obj.data_desembarque.strftime('%Y-%m-%d') if obj.data_desembarque else None,
                'sla_internacional': obj.sla_internacional,
                'rf_invoice': obj.rf_invoice,
                'coleta': obj.coleta.strftime('%Y-%m-%d') if obj.coleta else None,
                'liberacao': obj.liberacao.strftime('%Y-%m-%d') if obj.liberacao else None,
                'golden_sat': obj.golden_sat.strftime('%Y-%m-%d') if obj.golden_sat else None,
                'status_automatico': obj.get_status_automatico()
            }
            data.append(item)

        return JsonResponse({
            'status': 'success',
            'data': data,
            'clientes_info': clientes_info,
            'totais': totais,
            'sla_nomes': sla_nomes,
            'sla_media_geral': sla_media_por_etapa,
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

def clientes_sla_view(request):
    clientes = clientesNestle.objects.all()
    status_labels = [
        'Em Contrato', 'Em Estoque', 'Em Viagem', 'No Destino',
        'Menos de 75 dias', 'Mais de 75 dias', 'Retirado Ag. Envio',
        'Em Reversa Para o Brasil', 'Reversa Finalizada', 'Resumo Para Envio'
    ]
    sla_labels = [
        'sla_insercao', 'sla_terrestre', 'sla_porto_nacional', 'sla_maritimo',
        'sla_terminal_internacional', 'sla_terrestre_internacional', 'sla_retirada', 'sla_embarque'
    ]
    sla_nomes = {
        'sla_insercao': 'Inserção do Equipamento (dias)',
        'sla_terrestre': 'Tráfego Rodoviário Nacional (dias)',
        'sla_porto_nacional': 'Espera no Porto Nacional (dias)',
        'sla_maritimo': 'Tempo de Viagem Marítima (dias)',
        'sla_terminal_internacional': 'Terminal de Contêiner Internacional (dias)',
        'sla_terrestre_internacional': 'Transporte Terrestre Internacional (dias)',
        'sla_retirada': 'Remoção do Equipamento no Destino (dias)',
        'sla_embarque': 'SLA Embarque (dias)'
    }

    # Cálculo das médias das SLAs conforme solicitado
    sla_medias_etapas = {label: [] for label in sla_labels}
    for reg in GridInternacionalModel.objects.all():
        if reg.get_status_automatico() == "Reversa Finalizada":
            continue
        for sla in sla_labels:
            valor = getattr(reg, sla, None)
            if valor not in [None, '', ' '] and str(valor).isdigit():
                sla_medias_etapas[sla].append(int(valor))
    sla_media_por_etapa = {sla: (sum(sla_medias_etapas[sla])/len(sla_medias_etapas[sla]) if sla_medias_etapas[sla] else 0) for sla in sla_labels}

    clientes_info = []
    totais = {label: 0 for label in status_labels}
    sla_medias = {label: [] for label in sla_labels}

    for cliente in clientes:
        registros_final = GridInternacionalModel.objects.filter(cliente__iexact=cliente.cliente.strip())
        status_count = {label: 0 for label in status_labels}
        sla_somas = {label: [] for label in sla_labels}

        for reg in registros_final:
            status = reg.get_status_automatico()
            if status == 'Estoque Cliente':
                status_count['Em Estoque'] += 1
            elif status == 'Em viagem':
                status_count['Em Viagem'] += 1
            elif status == 'No destino':
                status_count['No Destino'] += 1
            elif status == 'Retirado, Ag. Envio':
                status_count['Retirado Ag. Envio'] += 1
            elif status == 'Em reversa para o Brasil':
                status_count['Em Reversa Para o Brasil'] += 1
            elif status == 'Reversa Finalizada':
                status_count['Reversa Finalizada'] += 1
            elif status == 'Contrato':
                status_count['Em Contrato'] += 1
            try:
                sla_int = int(reg.sla_internacional) if reg.sla_internacional not in [None, '', ' '] else None
            except:
                sla_int = None
            if sla_int is not None:
                if sla_int < 75:
                    status_count['Menos de 75 dias'] += 1
                else:
                    status_count['Mais de 75 dias'] += 1
            if hasattr(reg, 'resumo_para_envio') and reg.resumo_para_envio:
                status_count['Resumo Para Envio'] += 1
            # Só contabiliza SLAs se NÃO for Reversa Finalizada
            if status != 'Reversa Finalizada':
                for sla in sla_labels:
                    valor = getattr(reg, sla, None)
                    if valor not in [None, '', ' '] and str(valor).isdigit():
                        sla_somas[sla].append(int(valor))
                        sla_medias[sla].append(int(valor))
        for label in status_labels:
            totais[label] += status_count[label]
        sla_media_cliente = {sla: (sum(sla_somas[sla])/len(sla_somas[sla]) if sla_somas[sla] else 0) for sla in sla_labels}
        clientes_info.append({
            'nome': cliente.cliente,
            'status_count': status_count,
            'sla_media_cliente': sla_media_cliente,
        })
    sla_media_geral = {sla: (sum(sla_medias[sla])/len(sla_medias[sla]) if sla_medias[sla] else 0) for sla in sla_labels}

    return render(request, 'clientes_sla.html', {
        'clientes_info': clientes_info,
        'status_labels': status_labels,
        'totais': totais,
        'sla_labels': sla_labels,
        'sla_nomes': sla_nomes,
        'sla_media_geral': sla_media_geral,
        'sla_media_por_etapa': sla_media_por_etapa,
    })

class ValoresMensaisView(ListView):
    template_name = 'valores_mensais.html'
    context_object_name = 'valores'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ano_atual = datetime.datetime.now().year
        ano = self.request.GET.get('ano', ano_atual)
        
        # Buscar todos os valores mensais para o ano selecionado
        valores = ValorMensalCliente.objects.filter(ano=ano)
        print(f"\n=== DEBUG VALORES MENSAlS ===")
        print(f"Ano selecionado: {ano}")
        print(f"Total de registros encontrados: {valores.count()}")
        for valor in valores:
            print(f"Registro: cliente_id={valor.cliente_id}, mes={valor.mes}, valor={valor.valor}, enviado={valor.enviado}")
        
        context['ano'] = ano
        context['meses'] = ValorMensalCliente.MESES_CHOICES
        context['clientes'] = clientesNestle.objects.all()
        context['valores'] = valores  # Adicionar os valores ao contexto
        return context

    def get_queryset(self):
        ano = self.request.GET.get('ano', datetime.datetime.now().year)
        return ValorMensalCliente.objects.filter(ano=ano)

@login_required
def atualizar_valor_mensal(request):
    print("\n=== INÍCIO DO DEBUG ===")
    print(f"Método da requisição: {request.method}")
    print(f"Headers: {request.headers}")
    print(f"POST data: {request.POST}")
    
    if request.method == 'POST':
        try:
            # Log dos dados recebidos
            print("\nDados recebidos do POST:")
            print(f"cliente_id: {request.POST.get('cliente_id')}")
            print(f"mes: {request.POST.get('mes')}")
            print(f"ano: {request.POST.get('ano')}")
            print(f"valor: {request.POST.get('valor')}")
            print(f"enviado: {request.POST.get('enviado')}")

            cliente_id = request.POST.get('cliente_id')
            mes = request.POST.get('mes')
            ano = request.POST.get('ano')
            valor = request.POST.get('valor')
            enviado = request.POST.get('enviado') == 'true'

            # Validar dados
            if not all([cliente_id, mes, ano]):
                print("\nErro: Dados incompletos")
                print(f"cliente_id presente: {bool(cliente_id)}")
                print(f"mes presente: {bool(mes)}")
                print(f"ano presente: {bool(ano)}")
                return JsonResponse({
                    'success': False,
                    'error': 'Dados incompletos'
                })

            # Converter valor para Decimal
            try:
                valor = Decimal(valor) if valor else None
                print(f"\nValor convertido para Decimal: {valor}")
            except (TypeError, ValueError) as e:
                print(f"\nErro ao converter valor: {str(e)}")
                valor = None

            # Converter ano para inteiro
            try:
                ano = int(ano)
                print(f"\nAno convertido para inteiro: {ano}")
            except (TypeError, ValueError) as e:
                print(f"\nErro ao converter ano: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'Ano inválido'
                })

            # Buscar ou criar o registro
            print(f"\nBuscando registro:")
            print(f"cliente_id={cliente_id}")
            print(f"mes={mes}")
            print(f"ano={ano}")
            
            try:
                valor_mensal, created = ValorMensalCliente.objects.get_or_create(
                    cliente_id=cliente_id,
                    mes=mes,
                    ano=ano,
                    defaults={
                        'valor': valor,
                        'enviado': enviado,
                        'data_envio': datetime.datetime.now() if enviado else None
                    }
                )
                print(f"\nOperação realizada com sucesso:")
                print(f"Registro criado: {created}")
                print(f"ID do registro: {valor_mensal.id}")
            except Exception as e:
                print(f"\nErro ao buscar/criar registro: {str(e)}")
                raise

            # Se o registro já existia, atualizar
            if not created:
                print("\nAtualizando registro existente")
                try:
                    valor_mensal.valor = valor
                    valor_mensal.enviado = enviado
                    if enviado and not valor_mensal.data_envio:
                        valor_mensal.data_envio = datetime.datetime.now()
                    valor_mensal.save()
                    print(f"Registro atualizado com sucesso:")
                    print(f"valor={valor_mensal.valor}")
                    print(f"enviado={valor_mensal.enviado}")
                    print(f"data_envio={valor_mensal.data_envio}")
                except Exception as e:
                    print(f"\nErro ao atualizar registro: {str(e)}")
                    raise
            else:
                print(f"\nNovo registro criado:")
                print(f"valor={valor_mensal.valor}")
                print(f"enviado={valor_mensal.enviado}")
                print(f"data_envio={valor_mensal.data_envio}")

            response_data = {
                'success': True,
                'valor': str(valor_mensal.valor) if valor_mensal.valor else '',
                'enviado': valor_mensal.enviado
            }
            print(f"\nResposta enviada: {response_data}")
            return JsonResponse(response_data)

        except Exception as e:
            print(f"\nErro ao salvar valor mensal: {str(e)}")
            print(f"Tipo do erro: {type(e)}")
            import traceback
            print(f"Traceback completo:\n{traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': f'Erro ao salvar: {str(e)}'
            })

    print("\n=== FIM DO DEBUG ===\n")
    return JsonResponse({
        'success': False,
        'error': 'Método não permitido'
    })

def grid_internacional_sla_resumo(request):
    """
    Endpoint que retorna em JSON os valores de médias dos SLAs exibidos na tabela de resumo do grid internacional.
    """
    queryset = list(GridInternacionalModel.objects.all())
    queryset = [obj for obj in queryset if not obj.golden_sat and obj.get_status_automatico() != 'Reversa Finalizada']

    sla_labels = [
        ('sla_insercao', lambda o: (o.data_insercao, o.data_envio)),
        ('sla_retirada', lambda o: (o.data_retirada, o.data_chegada_destino)),
        ('sla_envio_brasil', lambda o: (o.data_envio_brasil, o.data_retirada)),
        ('sla_chegada_brasil', lambda o: (o.data_brasil, o.data_envio_brasil)),
        ('sla_porto_nacional', lambda o: (o.data_chegada_porto, o.data_insercao)),
        ('sla_embarque', lambda o: (o.data_embarque_maritimo, o.data_chegada_porto)),
        ('sla_maritimo', lambda o: (o.data_desembarque_maritimo, o.data_embarque_maritimo)),
        ('sla_terrestre_internacional', lambda o: (o.data_chegada_destino, o.data_desembarque_maritimo)),
        ('sla_terrestre', lambda o: (o.data_chegada_destino, o.data_desembarque_maritimo)),
        ('sla_internacional', lambda o: (o.data_retirada, o.data_chegada_destino)),
        ('sla_liberacao', lambda o: (o.liberacao, o.data_brasil)),
    ]
    sla_medias_grid = {}
    sla_valores_por_registro = []
    for obj in queryset:
        sla_dict = {}
        for sla, func in sla_labels:
            d1, d2 = func(obj)
            if d1 and d2:
                diff = (d1 - d2).days
                sla_dict[sla] = diff if diff >= 0 else None
            else:
                sla_dict[sla] = None
        sla_valores_por_registro.append(sla_dict)
    for sla, _ in sla_labels:
        valores = [sla_dict[sla] for sla_dict in sla_valores_por_registro if sla_dict[sla] is not None]
        sla_medias_grid[sla] = int(round(sum(valores)/len(valores))) if valores else None
    # Ajuste: dividir por 3 e arredondar para baixo para os dois SLAs
    for key in ['sla_terrestre_internacional', 'sla_terrestre']:
        if sla_medias_grid.get(key) is not None:
            sla_medias_grid[key] = math.floor(sla_medias_grid[key] / 3)
    # Após calcular as médias e ajustar os dois SLAs, faça a soma total usando os valores já ajustados
    sla_soma_total = sum([
        sla_medias_grid.get('sla_insercao') or 0,
        sla_medias_grid.get('sla_retirada') or 0,
        sla_medias_grid.get('sla_envio_brasil') or 0,
        sla_medias_grid.get('sla_chegada_brasil') or 0,
        sla_medias_grid.get('sla_porto_nacional') or 0,
        sla_medias_grid.get('sla_embarque') or 0,
        sla_medias_grid.get('sla_maritimo') or 0,
        sla_medias_grid.get('sla_terrestre_internacional') or 0,
        sla_medias_grid.get('sla_terrestre') or 0,
        sla_medias_grid.get('sla_internacional') or 0,
        sla_medias_grid.get('sla_liberacao') or 0,
    ])
    sla_medias_grid['sla_soma_total'] = sla_soma_total
    return JsonResponse(sla_medias_grid)

@csrf_exempt
def clientes_nestle_json(request):
    """
    Endpoint que retorna todos os dados dos clientes Nestle em formato JSON.
    """
    try:
        # Buscar todos os clientes
        clientes = clientesNestle.objects.all()
        
        # Converter para lista de dicionários
        data = []
        for cliente in clientes:
            item = {
                'id': cliente.id,
                'cliente': cliente.cliente,
                'cnpj': cliente.cnpj,
                'endereco': cliente.endereco,
                'quantidade': cliente.quantidade,
                'valor': str(cliente.valor) if cliente.valor else None,
                'local': cliente.local,
            }
            data.append(item)
        
        return JsonResponse({
            'status': 'success',
            'data': data,
            'total': len(data)
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)








