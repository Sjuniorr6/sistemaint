from django.urls import reverse_lazy, path
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from .models import GridInternacional as GridInternacionalModel, clientesNestle, ValorMensalCliente, Carga
from .forms import GridInternacionalForm, ValorMensalForm, CargaForm
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
from django.views import View
import requests
import time
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

        # Excluir equipamentos com cliente "prysmian" (case insensitive)
        queryset = queryset.exclude(cliente__icontains='prysmian')

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
        
        # DEBUG: Contar registros antes do filtro
        registros_antes_filtro = len(queryset)
        registros_com_liberacao_antes = len([obj for obj in queryset if obj.liberacao and obj.data_brasil])
        print(f"DEBUG: Registros antes do filtro: {registros_antes_filtro}")
        print(f"DEBUG: Registros com liberacao antes do filtro: {registros_com_liberacao_antes}")
        
        # Excluir registros com golden_sat preenchido e com status 'Reversa Finalizada' do grid principal
        # Mas manter os registros com status 'Danificado'
        queryset = [obj for obj in queryset if (not obj.golden_sat and obj.get_status_automatico() != 'Reversa Finalizada') or obj.get_status_automatico() == 'Danificado']
        
        # DEBUG: Contar registros após o filtro
        registros_apos_filtro = len(queryset)
        registros_com_liberacao_apos = len([obj for obj in queryset if obj.liberacao and obj.data_brasil])
        print(f"DEBUG: Registros após filtro: {registros_apos_filtro}")
        print(f"DEBUG: Registros com liberacao após filtro: {registros_com_liberacao_apos}")
        
        # Filtro de status agora usa status automático (reforçado)
        if status_operacao:
            queryset = [obj for obj in queryset if obj.get_status_automatico() == status_operacao]
        
        # Ordenar por id_planilha para agrupar registros iguais
        queryset = sorted(queryset, key=lambda obj: str(obj.id_planilha))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clientes'] = clientesNestle.objects.all().order_by('cliente')
        
        # DEBUG: Verificar registros no banco com liberacao e data_brasil
        todos_registros = GridInternacionalModel.objects.all()
        registros_com_liberacao_banco = 0
        registros_com_data_brasil_banco = 0
        registros_com_ambos_banco = 0
        
        for obj in todos_registros:
            if obj.liberacao:
                registros_com_liberacao_banco += 1
            if obj.data_brasil:
                registros_com_data_brasil_banco += 1
            if obj.liberacao and obj.data_brasil:
                registros_com_ambos_banco += 1
                print(f"DEBUG: Registro com ambas datas - ID: {obj.id}, liberacao: {obj.liberacao}, data_brasil: {obj.data_brasil}, golden_sat: {obj.golden_sat}, status: {obj.get_status_automatico()}")
        
        print(f"DEBUG: Total registros no banco: {todos_registros.count()}")
        print(f"DEBUG: Registros com liberacao: {registros_com_liberacao_banco}")
        print(f"DEBUG: Registros com data_brasil: {registros_com_data_brasil_banco}")
        print(f"DEBUG: Registros com ambas: {registros_com_ambos_banco}")
        
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
        
        # DEBUG: Verificar registros filtrados
        print(f"DEBUG: Registros após filtros: {len(queryset_filtrado)}")
        
        # Verificar quantos registros filtrados têm liberacao e data_brasil
        registros_filtrados_com_liberacao = 0
        for obj in queryset_filtrado:
            if obj.liberacao and obj.data_brasil:
                registros_filtrados_com_liberacao += 1
                print(f"DEBUG: Registro filtrado com ambas datas - ID: {obj.id}, status: {obj.get_status_automatico()}")
        
        print(f"DEBUG: Registros filtrados com liberacao e data_brasil: {registros_filtrados_com_liberacao}")

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
            'Aguardando Liberação RFB',
            'Aguardando Coleta',
            'Aguardando Embarque Internacional',
            'Aguardando Chegada na Base',
            'Fora de Operação',
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
        
        # DEBUG: Contar registros com dados de liberacao
        registros_com_liberacao = 0
        for obj in queryset_filtrado:
            if obj.liberacao and obj.data_brasil:
                registros_com_liberacao += 1
        print(f"DEBUG: Registros com liberacao e data_brasil: {registros_com_liberacao}")
        
        for obj in queryset_filtrado:
            sla_dict = {}
            for sla, func in sla_labels:
                d1, d2 = func(obj)
                if d1 and d2:
                    diff = (d1 - d2).days
                    sla_dict[sla] = diff if diff >= 0 else None
                    # DEBUG: Mostrar cálculo do sla_liberacao
                    if sla == 'sla_liberacao':
                        print(f"DEBUG: SLA Liberacao - obj.id={obj.id}, liberacao={d1}, data_brasil={d2}, diff={diff}")
                else:
                    sla_dict[sla] = None
            sla_valores_por_registro.append(sla_dict)
        # Calcular médias para cada SLA
        for sla, _ in sla_labels:
            valores = [sla_dict[sla] for sla_dict in sla_valores_por_registro if sla_dict[sla] is not None]
            sla_medias_grid[sla] = int(round(sum(valores)/len(valores))) if valores else None
            # DEBUG: Mostrar média do sla_liberacao
            if sla == 'sla_liberacao':
                print(f"DEBUG: Média SLA Liberacao - valores={valores}, média={sla_medias_grid[sla]}")
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
            elif value == 'Fora de Operação':
                badge_class = 'bg-danger'
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


def _get_grid_queryset_filtrado(cliente=None, container=None, status_operacao=None, ids=None, sem_dados=None):
    queryset = GridInternacionalModel.objects.all().exclude(cliente__icontains='prysmian')

    if ids:
        id_list = [i.strip() for i in ids.replace('\n', ',').replace(';', ',').split(',') if i.strip()]
        queryset_ids = [obj for obj in queryset if str(obj.id_planilha) in id_list]
        return sorted(
            queryset_ids,
            key=lambda obj: (
                str(obj.id_planilha),
                obj.data_insercao or obj.data_envio or datetime.date.min
            )
        )

    if sem_dados:
        queryset_sem_dados = [
            obj for obj in queryset
            if (not obj.destino or not obj.bl or not obj.container or not obj.local)
            and obj.get_status_automatico() != 'Reversa Finalizada'
        ]
        return sorted(queryset_sem_dados, key=lambda obj: str(obj.id_planilha))

    if cliente:
        queryset = queryset.filter(cliente__icontains=cliente)
    if container:
        queryset = queryset.filter(container__icontains=container)

    queryset = list(queryset)
    queryset = [
        obj for obj in queryset
        if (not obj.golden_sat and obj.get_status_automatico() != 'Reversa Finalizada')
        or obj.get_status_automatico() == 'Danificado'
    ]

    if status_operacao:
        queryset = [obj for obj in queryset if obj.get_status_automatico() == status_operacao]

    return sorted(queryset, key=lambda obj: str(obj.id_planilha))


def grid_internacional_export_excel(request):
    cliente = request.GET.get('cliente')
    container = request.GET.get('container')
    ids = request.GET.get('ids')
    sem_dados = request.GET.get('sem_dados')
    status_operacao = request.GET.get('export_status')

    queryset = _get_grid_queryset_filtrado(
        cliente=cliente,
        container=container,
        status_operacao=status_operacao,
        ids=ids,
        sem_dados=sem_dados,
    )

    def fmt_date(value):
        return value.strftime('%d/%m/%Y') if value else ''

    data = []
    for obj in queryset:
        sla_liberacao = ''
        if obj.liberacao and obj.data_brasil:
            sla_liberacao = (obj.liberacao - obj.data_brasil).days

        data.append({
            'ID': obj.id_planilha,
            'Requisição': obj.requisicao,
            'Cliente': obj.cliente,
            'Local Entrega': obj.local_de_entrega,
            'Modelo': obj.modelo,
            'Destino': obj.destino,
            'BL': obj.bl,
            'Container': obj.container,
            'Local': obj.local,
            'Status Operação': obj.get_status_automatico(),
            'Entrega': fmt_date(obj.data_envio),
            'Inserção': fmt_date(obj.data_insercao),
            'Porto Brasil': fmt_date(obj.data_chegada_porto),
            'Embarque Marítimo': fmt_date(obj.data_embarque_maritimo),
            'Desembarque Marítimo': fmt_date(obj.data_desembarque_maritimo),
            'Chegada Destino': fmt_date(obj.data_chegada_destino),
            'Retirada': fmt_date(obj.data_retirada),
            'Invoice': fmt_date(obj.data_envoice),
            'RF Invoice': obj.rf_invoice,
            'Coleta': fmt_date(obj.coleta),
            'Envio Brasil': fmt_date(obj.data_envio_brasil),
            'Data Brasil': fmt_date(obj.data_brasil),
            'Liberacao': fmt_date(obj.liberacao),
            'GoldenSat': fmt_date(obj.golden_sat),
            'SLA Liberação': sla_liberacao,
            'Observação': obj.observacao,
        })

    colunas_ordenadas = [
        'ID', 'Requisição', 'Cliente', 'Local Entrega', 'Modelo', 'Destino', 'BL', 'Container', 'Local',
        'Status Operação', 'Entrega', 'Inserção', 'Porto Brasil', 'Embarque Marítimo', 'Desembarque Marítimo',
        'Chegada Destino', 'Retirada', 'Invoice', 'RF Invoice', 'Coleta', 'Envio Brasil', 'Data Brasil',
        'Liberacao', 'GoldenSat', 'SLA Liberação', 'Observação'
    ]

    df = pd.DataFrame(data, columns=colunas_ordenadas)
    output = BytesIO()
    df.to_excel(output, index=False, sheet_name='Grid Internacional')
    output.seek(0)

    status_nome = status_operacao if status_operacao else 'todos_status'
    status_nome = status_nome.replace(' ', '_').replace('/', '_')
    nome_arquivo = f'grid_internacional_{status_nome}.xlsx'

    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return response

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
            to=['inteligencia@grupogoldensat.com.br', 'inteligencia6@grupogoldensat.com.br', 'julio.cesar@grupogoldensat.com.br', 'sjuniorr6@gmail.com'],
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
            'Em Reversa Para o Brasil', 'Reversa Finalizada', 'Resumo Para Envio', 'Fora de Operação'
        ]
        
        # Lista completa de SLAs disponíveis
        sla_labels = [
            'sla_insercao', 'sla_terrestre', 'sla_porto_nacional', 'sla_maritimo',
            'sla_terminal_internacional', 'sla_terrestre_internacional', 'sla_retirada', 'sla_embarque',
            'sla_envio_brasil', 'sla_chegada_brasil', 'sla_internacional', 'sla_liberacao'
        ]
        
        sla_nomes = {
            'sla_insercao': 'Inserção do Equipamento (dias)',
            'sla_terrestre': 'Tráfego Rodoviário Nacional (dias)',
            'sla_porto_nacional': 'Espera no Porto Nacional (dias)',
            'sla_maritimo': 'Tempo de Viagem Marítima (dias)',
            'sla_terminal_internacional': 'Terminal de Contêiner Internacional (dias)',
            'sla_terrestre_internacional': 'Transporte Terrestre Internacional (dias)',
            'sla_retirada': 'Remoção do Equipamento no Destino (dias)',
            'sla_embarque': 'SLA Embarque (dias)',
            'sla_envio_brasil': 'SLA Envio Brasil (dias)',
            'sla_chegada_brasil': 'SLA Chegada Brasil (dias)',
            'sla_internacional': 'SLA Internacional (dias)',
            'sla_liberacao': 'SLA Liberação (dias)'
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

            # Cálculo detalhado de SLAs por cliente
            sla_media_cliente = {}
            sla_detalhado_cliente = {}
            
            for sla in sla_labels:
                valores = []
                for r in registros_final:
                    valor = getattr(r, sla, None)
                    if valor not in [None, '', ' '] and str(valor).isdigit():
                        valores.append(int(valor))
                
                if valores:
                    sla_media_cliente[sla] = round(sum(valores) / len(valores), 2)
                    sla_detalhado_cliente[sla] = {
                        'media': round(sum(valores) / len(valores), 2),
                        'minimo': min(valores),
                        'maximo': max(valores),
                        'total_registros': len(valores),
                        'valores': valores[:10]  # Primeiros 10 valores para exemplo
                    }
                else:
                    sla_media_cliente[sla] = 0
                    sla_detalhado_cliente[sla] = {
                        'media': 0,
                        'minimo': 0,
                        'maximo': 0,
                        'total_registros': 0,
                        'valores': []
                    }
                
                sla_media_por_etapa[sla].extend(valores)

            clientes_info.append({
                'nome': cliente.cliente,
                'id': cliente.id,
                'cnpj': cliente.cnpj,
                'quantidade_contratada': cliente.quantidade,
                'valor_contrato': str(cliente.valor) if cliente.valor else None,
                'local': cliente.local,
                'status_count': status_count,
                'sla_media_cliente': sla_media_cliente,
                'sla_detalhado': sla_detalhado_cliente,
                'total_equipamentos': len(registros_final),
                'equipamentos_ativos': len([r for r in registros_final if r.get_status_automatico() != 'Reversa Finalizada'])
            })

        # Cálculo de médias gerais
        sla_medias_etapas = {label: [] for label in sla_labels}
        for reg in GridInternacionalModel.objects.all():
            if reg.get_status_automatico() == "Reversa Finalizada":
                continue
            for sla in sla_labels:
                valor = getattr(reg, sla, None)
                if valor not in [None, '', ' '] and str(valor).isdigit():
                    sla_medias_etapas[sla].append(int(valor))
        
        sla_media_por_etapa = {}
        for sla in sla_labels:
            valores = sla_medias_etapas[sla]
            if valores:
                sla_media_por_etapa[sla] = {
                    'media': round(sum(valores) / len(valores), 2),
                    'minimo': min(valores),
                    'maximo': max(valores),
                    'total_registros': len(valores)
                }
            else:
                sla_media_por_etapa[sla] = {
                    'media': 0,
                    'minimo': 0,
                    'maximo': 0,
                    'total_registros': 0
                }

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
            'resumo_geral': {
                'total_clientes': len(clientes),
                'total_equipamentos': len(queryset),
                'equipamentos_ativos': len([obj for obj in queryset if obj.get_status_automatico() != 'Reversa Finalizada']),
                'equipamentos_finalizados': len([obj for obj in queryset if obj.get_status_automatico() == 'Reversa Finalizada'])
            }
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@csrf_exempt
def sla_por_cliente_json(request):
    """
    Endpoint específico para retornar SLAs detalhados por cliente
    """
    try:
        cliente_id = request.GET.get('cliente_id')
        cliente_nome = request.GET.get('cliente_nome')
        
        # Definir todos os SLAs disponíveis
        sla_labels = [
            'sla_insercao', 'sla_terrestre', 'sla_porto_nacional', 'sla_maritimo',
            'sla_terminal_internacional', 'sla_terrestre_internacional', 'sla_retirada', 'sla_embarque',
            'sla_envio_brasil', 'sla_chegada_brasil', 'sla_internacional', 'sla_liberacao'
        ]
        
        sla_nomes = {
            'sla_insercao': 'Inserção do Equipamento (dias)',
            'sla_terrestre': 'Tráfego Rodoviário Nacional (dias)',
            'sla_porto_nacional': 'Espera no Porto Nacional (dias)',
            'sla_maritimo': 'Tempo de Viagem Marítima (dias)',
            'sla_terminal_internacional': 'Terminal de Contêiner Internacional (dias)',
            'sla_terrestre_internacional': 'Transporte Terrestre Internacional (dias)',
            'sla_retirada': 'Remoção do Equipamento no Destino (dias)',
            'sla_embarque': 'SLA Embarque (dias)',
            'sla_envio_brasil': 'SLA Envio Brasil (dias)',
            'sla_chegada_brasil': 'SLA Chegada Brasil (dias)',
            'sla_internacional': 'SLA Internacional (dias)',
            'sla_liberacao': 'SLA Liberação (dias)'
        }
        
        # Filtrar por cliente se especificado
        if cliente_id:
            cliente = clientesNestle.objects.get(id=cliente_id)
            registros = GridInternacionalModel.objects.filter(cliente__iexact=cliente.cliente.strip())
        elif cliente_nome:
            registros = GridInternacionalModel.objects.filter(cliente__icontains=cliente_nome)
        else:
            # Retornar dados de todos os clientes
            clientes = clientesNestle.objects.all()
            resultado = {}
            
            for cliente in clientes:
                registros_cliente = GridInternacionalModel.objects.filter(cliente__iexact=cliente.cliente.strip())
                sla_detalhado = {}
                
                for sla in sla_labels:
                    valores = []
                    for r in registros_cliente:
                        valor = getattr(r, sla, None)
                        if valor not in [None, '', ' '] and str(valor).isdigit():
                            valores.append(int(valor))
                    
                    if valores:
                        sla_detalhado[sla] = {
                            'nome': sla_nomes[sla],
                            'media': round(sum(valores) / len(valores), 2),
                            'minimo': min(valores),
                            'maximo': max(valores),
                            'total_registros': len(valores),
                            'valores': valores,
                            'desvio_padrao': round((sum((x - (sum(valores) / len(valores))) ** 2 for x in valores) / len(valores)) ** 0.5, 2) if len(valores) > 1 else 0
                        }
                    else:
                        sla_detalhado[sla] = {
                            'nome': sla_nomes[sla],
                            'media': 0,
                            'minimo': 0,
                            'maximo': 0,
                            'total_registros': 0,
                            'valores': [],
                            'desvio_padrao': 0
                        }
                
                resultado[cliente.cliente] = {
                    'cliente_id': cliente.id,
                    'cliente_nome': cliente.cliente,
                    'cnpj': cliente.cnpj,
                    'quantidade_contratada': cliente.quantidade,
                    'valor_contrato': str(cliente.valor) if cliente.valor else None,
                    'local': cliente.local,
                    'total_equipamentos': len(registros_cliente),
                    'equipamentos_ativos': len([r for r in registros_cliente if r.get_status_automatico() != 'Reversa Finalizada']),
                    'slas': sla_detalhado,
                    'resumo_slas': {
                        'sla_mais_alto': max(sla_detalhado.items(), key=lambda x: x[1]['media'] if x[1]['media'] > 0 else 0)[0] if any(sla['media'] > 0 for sla in sla_detalhado.values()) else None,
                        'sla_mais_baixo': min(sla_detalhado.items(), key=lambda x: x[1]['media'] if x[1]['media'] > 0 else float('inf'))[0] if any(sla['media'] > 0 for sla in sla_detalhado.values()) else None,
                        'total_slas_calculados': sum(1 for sla in sla_detalhado.values() if sla['total_registros'] > 0)
                    }
                }
            
            return JsonResponse({
                'status': 'success',
                'data': resultado,
                'total_clientes': len(clientes)
            })
        
        # Se foi especificado um cliente específico
        if cliente_id or cliente_nome:
            if cliente_id:
                cliente = clientesNestle.objects.get(id=cliente_id)
            else:
                cliente = clientesNestle.objects.filter(cliente__icontains=cliente_nome).first()
            
            if not cliente:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Cliente não encontrado'
                }, status=404)
            
            sla_detalhado = {}
            
            for sla in sla_labels:
                valores = []
                for r in registros:
                    valor = getattr(r, sla, None)
                    if valor not in [None, '', ' '] and str(valor).isdigit():
                        valores.append(int(valor))
                
                if valores:
                    sla_detalhado[sla] = {
                        'nome': sla_nomes[sla],
                        'media': round(sum(valores) / len(valores), 2),
                        'minimo': min(valores),
                        'maximo': max(valores),
                        'total_registros': len(valores),
                        'valores': valores,
                        'desvio_padrao': round((sum((x - (sum(valores) / len(valores))) ** 2 for x in valores) / len(valores)) ** 0.5, 2) if len(valores) > 1 else 0
                    }
                else:
                    sla_detalhado[sla] = {
                        'nome': sla_nomes[sla],
                        'media': 0,
                        'minimo': 0,
                        'maximo': 0,
                        'total_registros': 0,
                        'valores': [],
                        'desvio_padrao': 0
                    }
            
            return JsonResponse({
                'status': 'success',
                'cliente': {
                    'cliente_id': cliente.id,
                    'cliente_nome': cliente.cliente,
                    'cnpj': cliente.cnpj,
                    'quantidade_contratada': cliente.quantidade,
                    'valor_contrato': str(cliente.valor) if cliente.valor else None,
                    'local': cliente.local,
                    'total_equipamentos': len(registros),
                    'equipamentos_ativos': len([r for r in registros if r.get_status_automatico() != 'Reversa Finalizada']),
                    'slas': sla_detalhado,
                    'resumo_slas': {
                        'sla_mais_alto': max(sla_detalhado.items(), key=lambda x: x[1]['media'] if x[1]['media'] > 0 else 0)[0] if any(sla['media'] > 0 for sla in sla_detalhado.values()) else None,
                        'sla_mais_baixo': min(sla_detalhado.items(), key=lambda x: x[1]['media'] if x[1]['media'] > 0 else float('inf'))[0] if any(sla['media'] > 0 for sla in sla_detalhado.values()) else None,
                        'total_slas_calculados': sum(1 for sla in sla_detalhado.values() if sla['total_registros'] > 0)
                    }
                }
            })
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@csrf_exempt
def sla_simples_por_cliente_json(request):
    """
    Endpoint simples que retorna apenas os SLAs por cliente
    """
    try:
        # Definir todos os SLAs disponíveis
        sla_labels = [
            'sla_insercao', 'sla_terrestre', 'sla_porto_nacional', 'sla_maritimo',
            'sla_terminal_internacional', 'sla_terrestre_internacional', 'sla_retirada', 'sla_embarque',
            'sla_envio_brasil', 'sla_chegada_brasil', 'sla_internacional', 'sla_liberacao'
        ]
        
        # Buscar todos os clientes
        clientes = clientesNestle.objects.all()
        resultado = {}
        
        for cliente in clientes:
            # Buscar registros do cliente
            registros_cliente = GridInternacionalModel.objects.filter(cliente__iexact=cliente.cliente.strip())
            
            # Calcular SLAs para este cliente
            slas_cliente = {}
            
            for sla in sla_labels:
                valores = []
                for r in registros_cliente:
                    valor = getattr(r, sla, None)
                    if valor not in [None, '', ' '] and str(valor).isdigit():
                        valores.append(int(valor))
                
                if valores:
                    slas_cliente[sla] = {
                        'media': round(sum(valores) / len(valores), 2),
                        'minimo': min(valores),
                        'maximo': max(valores),
                        'total_registros': len(valores)
                    }
                else:
                    slas_cliente[sla] = {
                        'media': 0,
                        'minimo': 0,
                        'maximo': 0,
                        'total_registros': 0
                    }
            
            # Adicionar ao resultado
            resultado[cliente.cliente] = slas_cliente
        
        return JsonResponse({
            'status': 'success',
            'slas_por_cliente': resultado
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
        'Em Reversa Para o Brasil', 'Reversa Finalizada', 'Resumo Para Envio', 'Fora de Operação'
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
        context['ano_atual'] = ano  # Passar o ano selecionado como ano_atual para o template
        context['meses'] = ValorMensalCliente.MESES_CHOICES
        context['clientes'] = clientesNestle.objects.all()
        context['valores'] = valores  # Adicionar os valores ao contexto

        # Adicionar dicionário de códigos de rastreio por cliente/ano
        codigos_rastreio = {}
        for cliente in context['clientes']:
            registro = valores.filter(cliente=cliente).order_by('-mes').first()
            codigos_rastreio[cliente.id] = registro.codigo_rastreio if registro and registro.codigo_rastreio else ''
        context['codigos_rastreio'] = codigos_rastreio

        return context

    def get_queryset(self):
        ano = self.request.GET.get('ano', datetime.datetime.now().year)
        return ValorMensalCliente.objects.filter(ano=ano)

@login_required
def atualizar_valor_mensal(request):
    if request.method == 'POST':
        try:
            cliente_id = request.POST.get('cliente_id')
            mes = request.POST.get('mes')
            ano = request.POST.get('ano')
            valor = request.POST.get('valor')
            enviado = request.POST.get('enviado') == 'true'
            codigo_rastreio = request.POST.get('codigo_rastreio', '').strip()
            aplicar_para_todos = request.POST.get('aplicar_para_todos') == 'true'

            if not all([cliente_id, mes, ano]):
                return JsonResponse({
                    'success': False,
                    'error': 'Dados incompletos'
                })

            try:
                valor = Decimal(valor) if valor else None
            except (TypeError, ValueError):
                valor = None

            try:
                ano = int(ano)
            except (TypeError, ValueError):
                return JsonResponse({
                    'success': False,
                    'error': 'Ano inválido'
                })

            if aplicar_para_todos:
                ValorMensalCliente.objects.filter(cliente_id=cliente_id, ano=ano).update(codigo_rastreio=codigo_rastreio)

            try:
                valor_mensal, created = ValorMensalCliente.objects.get_or_create(
                    cliente_id=cliente_id,
                    mes=mes,
                    ano=ano,
                    defaults={
                        'valor': valor,
                        'enviado': enviado,
                        'codigo_rastreio': codigo_rastreio if codigo_rastreio else None,
                        'data_envio': datetime.datetime.now() if enviado else None
                    }
                )
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Erro ao salvar: {str(e)}'
                })

            if not created:
                try:
                    valor_mensal.valor = valor
                    valor_mensal.enviado = enviado
                    valor_mensal.codigo_rastreio = codigo_rastreio if codigo_rastreio else None
                    if enviado and not valor_mensal.data_envio:
                        valor_mensal.data_envio = datetime.datetime.now()
                    valor_mensal.save()
                except Exception as e:
                    return JsonResponse({
                        'success': False,
                        'error': f'Erro ao salvar: {str(e)}'
                    })

            response_data = {
                'success': True,
                'valor': str(valor_mensal.valor) if valor_mensal.valor else '',
                'enviado': valor_mensal.enviado,
                'codigo_rastreio': valor_mensal.codigo_rastreio or ''
            }
            return JsonResponse(response_data)

        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'error': f'Erro ao salvar: {str(e)}'
            })

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


class CargaListView(ListView):
    """
    View para listar cotações de carga
    """
    model = Carga
    template_name = 'carga_list.html'
    context_object_name = 'cotacoes'
    ordering = ['-data']
    
    def get_queryset(self):
        """
        Filtra o queryset para excluir cotações com status 'Reprovada'
        """
        return Carga.objects.exclude(status='Reprovada').order_by('-data')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Adiciona o formulário para nova cotação
        context['form'] = CargaForm()
        
        # Calcula resumos para cotações aprovadas
        cotacoes_aprovadas = self.get_queryset().filter(status='Aprovada')
        if cotacoes_aprovadas.exists():
            context['resumo_total_pago'] = sum(c.total for c in cotacoes_aprovadas)
            context['resumo_total_equipamentos'] = sum(c.qtd_equipamento for c in cotacoes_aprovadas)
            context['resumo_media_por_equipamento'] = context['resumo_total_pago'] / context['resumo_total_equipamentos'] if context['resumo_total_equipamentos'] > 0 else 0
        
        return context

class CargaCreateView(CreateView):
    """
    View para criar nova cotação de carga
    """
    model = Carga
    form_class = CargaForm
    template_name = 'carga_list.html'
    success_url = reverse_lazy('carga-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Adiciona o formulário para nova cotação
        context['form'] = self.get_form()
        
        # Calcula resumos para cotações aprovadas
        cotacoes_aprovadas = Carga.objects.filter(status='Aprovada')
        if cotacoes_aprovadas.exists():
            context['resumo_total_pago'] = sum(c.total for c in cotacoes_aprovadas)
            context['resumo_total_equipamentos'] = sum(c.qtd_equipamento for c in cotacoes_aprovadas)
            context['resumo_media_por_equipamento'] = context['resumo_total_pago'] / context['resumo_total_equipamentos']
        else:
            context['resumo_total_pago'] = 0
            context['resumo_total_equipamentos'] = 0
            context['resumo_media_por_equipamento'] = 0
        
        # Adiciona todas as cotações
        context['cotacoes'] = Carga.objects.all().order_by('-data')
        
        return context

    def form_valid(self, form):
        """
        Sobrescreve o método form_valid para adicionar validações customizadas
        """
        try:
            print("=== DEBUG: Iniciando form_valid ===")
            print(f"Form data: {form.cleaned_data}")
            
            # Salva o formulário
            response = super().form_valid(form)
            
            print(f"=== DEBUG: Objeto salvo com ID: {self.object.id} ===")
            
            # Adiciona mensagem de sucesso
            from django.contrib import messages
            messages.success(self.request, 'Cotação criada com sucesso!')
            
            return response
        except Exception as e:
            print(f"=== DEBUG: Erro no form_valid: {e} ===")
            # Em caso de erro, adiciona mensagem de erro
            from django.contrib import messages
            messages.error(self.request, f'Erro ao criar cotação: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        """
        Sobrescreve o método form_invalid para debug
        """
        print("=== DEBUG: Formulário inválido ===")
        print(f"Form errors: {form.errors}")
        return super().form_invalid(form)

@csrf_exempt
def carga_aprovar_reprovar(request, pk, status):
    """
    View para aprovar ou reprovar uma cotação
    """
    if request.method == 'POST':
        try:
            cotacao = Carga.objects.get(id=pk)
            cotacao.status = status
            cotacao.save()
            return redirect('carga-list')
        except Carga.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Cotação não encontrada'})
    
    return redirect('carga-list')

@csrf_exempt
def atualizar_cotacao_ajax(request):
    """
    View AJAX para atualizar campos de cotação dinamicamente
    """
    if request.method == 'POST':
        try:
            import json
            from django.http import JsonResponse
            data = json.loads(request.body.decode('utf-8'))
            cotacao_id = data.get('cotacao_id')
            campo = data.get('campo')
            valor = data.get('valor')
            
            # Só permite alterar campos de moeda
            campos_moeda = [
                'honorarios_moeda',
                'frete_rodoviario_moeda',
                'licenca_importacao_moeda',
                'taxa_siscomex_moeda',
                'taxa_armazenagem_moeda',
                'frete_all_in_moeda',
            ]
            
            if campo not in campos_moeda:
                return JsonResponse({'success': False, 'error': 'Campo não permitido'})
            
            cotacao = Carga.objects.get(id=cotacao_id)
            setattr(cotacao, campo, valor)
            cotacao.save()
            
            return JsonResponse({
                'success': True,
                'frete_all_in_eur_brl': float(cotacao.frete_all_in_eur_brl or 0),
                'frete_all_in_usd_brl': float(cotacao.frete_all_in_usd_brl or 0),
                'honorarios_brl': float(cotacao.honorarios_brl or 0),
                'frete_rodoviario_brl': float(cotacao.frete_rodoviario_brl or 0),
                'licenca_importacao_brl': float(cotacao.licenca_importacao_brl or 0),
                'taxa_siscomex_brl': float(cotacao.taxa_siscomex_brl or 0),
                'taxa_armazenagem_brl': float(cotacao.taxa_armazenagem_brl or 0),
                'total': float(cotacao.total or 0),
                'valor_por_equip': float(cotacao.valor_por_equip or 0),
            })
            
        except Carga.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Cotação não encontrada'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@csrf_exempt
def asset_convertido(request):
    """
    Endpoint que consulta a API externa e retorna dados dos assets com coordenadas
    """
    try:
        import requests
        import json
        from django.http import JsonResponse
        
        print("=== INICIANDO ASSET CONVERTIDO ===")
        
        # URL da API externa
        api_url = "https://gscontroller.com.br/api/get_assetscontrols_data/"
        
        print(f"Consultando API: {api_url}")
        
        # Fazer requisição para a API externa
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()  # Levanta exceção se status não for 200
        
        print(f"Resposta da API recebida. Status: {response.status_code}")
        
        # Parsear dados da API
        data = response.json()
        
        print(f"Tipo de dados recebidos: {type(data)}")
        
        # Verificar se data é uma lista ou se precisa extrair FObject
        if isinstance(data, dict) and 'FObject' in data:
            assets_data = data['FObject']
            print(f"Extraindo FObject. Total de assets: {len(assets_data)}")
        elif isinstance(data, list):
            assets_data = data
            print(f"Dados são uma lista. Total de assets: {len(assets_data)}")
        else:
            print(f"Formato inesperado: {type(data)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Formato de dados inesperado da API'
            }, status=500)
        
        # Lista para armazenar dados processados
        assets_processados = []
        
        # Processar TODOS os assets (sem limitação)
        print(f"Processando {len(assets_data)} assets...")
        
        for i, asset in enumerate(assets_data):
            try:
                # Criar uma cópia do asset para não modificar o original
                asset_copy = dict(asset) if isinstance(asset, dict) else {}
                
                # Extrair coordenadas - verificar diferentes possíveis nomes de campos
                lat = asset_copy.get('FLatitude') or asset_copy.get('lat') or asset_copy.get('latitude')
                lng = asset_copy.get('FLongitude') or asset_copy.get('lng') or asset_copy.get('longitude')
                
                # Adicionar informações de coordenadas
                asset_copy['coordenadas'] = {
                    'lat': lat,
                    'lng': lng,
                    'tem_coordenadas': bool(lat and lng)
                }
                
                # Adicionar informações básicas do asset
                asset_copy['info_basica'] = {
                    'vehicle_name': asset_copy.get('FVehicleName'),
                    'asset_id': asset_copy.get('FAssetID'),
                    'speed': asset_copy.get('FSpeed'),
                    'battery': asset_copy.get('FBattery'),
                    'temperature': asset_copy.get('FTemperature1'),
                    'humidity': asset_copy.get('FHumidity1'),
                    'gps_time': asset_copy.get('FGPSTime'),
                    'online': asset_copy.get('FOnline')
                }
                
                # Remover campos desnecessários para reduzir o tamanho da resposta
                campos_para_remover = [
                    'FExpandProto', 'SubAssets', 'FGPSTimestamp', 'FRecvTimestamp',
                    'FTemperature2', 'FTemperature3', 'FTemperature4', 'FTemperature5', 'FTemperature6',
                    'FHumidity2', 'FHumidity3', 'FHumidity4', 'FHumidity5', 'FHumidity6',
                    'FFuelValue1', 'FFuelValue2', 'FFuelValue3'
                ]
                
                for campo in campos_para_remover:
                    asset_copy.pop(campo, None)
                
                assets_processados.append(asset_copy)
                
                # Log a cada 10 assets processados
                if (i + 1) % 10 == 0:
                    print(f"Processados {i + 1}/{len(assets_data)} assets...")
                
            except Exception as e:
                print(f"Erro ao processar asset {i}: {str(e)}")
                # Adicionar asset com erro
                asset_copy = dict(asset) if isinstance(asset, dict) else {}
                asset_copy['erro_processamento'] = str(e)
                assets_processados.append(asset_copy)
        
        print("=== FINALIZANDO PROCESSAMENTO ===")
        
        # Estatísticas
        total_assets = len(assets_processados)
        com_coordenadas = len([a for a in assets_processados if a.get('coordenadas', {}).get('tem_coordenadas')])
        online = len([a for a in assets_processados if a.get('info_basica', {}).get('online') == 1])
        
        # Retornar dados processados
        return JsonResponse({
            'status': 'success',
            'total_assets': total_assets,
            'assets': assets_processados,
            'resumo': {
                'total_assets': total_assets,
                'com_coordenadas': com_coordenadas,
                'sem_coordenadas': total_assets - com_coordenadas,
                'online': online,
                'offline': total_assets - online
            },
            'mensagem': 'Dados carregados com sucesso. Todos os assets foram processados.'
        })
        
    except requests.exceptions.RequestException as e:
        print(f"Erro de requisição: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao consultar API externa: {str(e)}'
        }, status=500)
    except json.JSONDecodeError as e:
        print(f"Erro de JSON: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao decodificar resposta da API: {str(e)}'
        }, status=500)
    except Exception as e:
        print(f"Erro inesperado: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro inesperado: {str(e)}'
        }, status=500)

@csrf_exempt
def asset_convertido_com_enderecos(request):
    """
    Endpoint que consulta a API externa e converte coordenadas lat/lng em endereços
    Versão otimizada com processamento em lotes
    """
    try:
        import requests
        import json
        import time
        from django.http import JsonResponse
        
        print("=== INICIANDO CONVERSÃO DE COORDENADAS OTIMIZADA ===")
        
        # URL da API externa
        api_url = "https://gscontroller.com.br/api/get_assetscontrols_data/"
        
        # Fazer requisição para a API externa com retry logic
        max_retries = 3
        timeout = 60  # Aumentado para 60 segundos
        
        for attempt in range(max_retries):
            try:
                print(f"Tentativa {attempt + 1}/{max_retries} de conectar com a API...")
                response = requests.get(api_url, timeout=timeout)
                response.raise_for_status()
                print("Conexão com API estabelecida com sucesso!")
                break
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"Timeout na tentativa {attempt + 1}. Tentando novamente...")
                    time.sleep(2)  # Pausa antes de tentar novamente
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'API externa não respondeu após múltiplas tentativas. Tente novamente em alguns minutos.'
                    }, status=503)
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"Erro na tentativa {attempt + 1}: {str(e)}. Tentando novamente...")
                    time.sleep(2)
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Erro ao conectar com API externa após {max_retries} tentativas: {str(e)}'
                    }, status=503)
        
        # Parsear dados da API
        data = response.json()
        
        # Verificar se data é uma lista ou se precisa extrair FObject
        if isinstance(data, dict) and 'FObject' in data:
            assets_data = data['FObject']
        elif isinstance(data, list):
            assets_data = data
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Formato de dados inesperado da API'
            }, status=500)
        
        # Mapeamento manual de coordenadas para cidades conhecidas (CACHE LOCAL)
        coordenadas_conhecidas = {
            # Fortaleza, CE
            (-3.8715467, -38.6118471): "Fortaleza, CE, Brasil",
            (-3.8759642, -38.6108298): "Fortaleza, CE, Brasil",
            (-3.866656, -38.612863): "Fortaleza, CE, Brasil",
            (-3.7318616, -38.5266694): "Fortaleza, CE, Brasil",
            
            # São Paulo, SP
            (-23.6353703, -46.5154297): "São Paulo, SP, Brasil",
            (-23.6396175, -46.5141551): "São Paulo, SP, Brasil",
            (-23.6323341, -46.5137985): "São Paulo, SP, Brasil",
            (-23.6354743, -46.5150922): "São Paulo, SP, Brasil",
            (-23.5505199, -46.6333094): "São Paulo, SP, Brasil",
            
            # Argentina
            (-26.8664083, -65.1825128): "Tucumán, Argentina",
            (-32.8646586, -61.1383562): "Rosário, Santa Fe, Argentina",
            (-32.8552509, -61.143353): "Rosário, Santa Fe, Argentina",
            
            # Outras localizações conhecidas
            (-3.1190275, -60.0217314): "Manaus, AM, Brasil",
            (-30.0346471, -51.2176584): "Porto Alegre, RS, Brasil",
            (-12.9715987, -38.5010949): "Salvador, BA, Brasil",
            (-15.7942287, -47.8821658): "Brasília, DF, Brasil",
            (-19.919054, -43.937644): "Belo Horizonte, MG, Brasil",
            (-25.4289541, -49.267137): "Curitiba, PR, Brasil",
            (-8.047562, -34.877003): "Recife, PE, Brasil",
            (-5.7944787, -35.211): "Natal, RN, Brasil",
        }
        
        # Lista para armazenar dados convertidos
        assets_convertidos = []
        
        # Processar TODOS os assets
        assets_para_processar = assets_data
        total_assets = len(assets_para_processar)
        print(f"Processando {total_assets} assets para conversão...")
        
        # Contadores para estatísticas
        conversoes_cache = 0
        conversoes_nominatim = 0
        sem_coordenadas = 0
        erros = 0
        
        # Processar cada asset
        for i, asset in enumerate(assets_para_processar):
            try:
                # Log de progresso a cada 10 assets
                if (i + 1) % 10 == 0 or i == 0:
                    print(f"Processando asset {i+1}/{total_assets} - {(i+1)/total_assets*100:.1f}%")
                
                # Criar uma cópia do asset
                asset_copy = dict(asset) if isinstance(asset, dict) else {}
                
                # Extrair coordenadas
                lat = asset_copy.get('FLatitude') or asset_copy.get('lat') or asset_copy.get('latitude')
                lng = asset_copy.get('FLongitude') or asset_copy.get('lng') or asset_copy.get('longitude')
                
                # Se não tiver coordenadas, pular
                if not lat or not lng:
                    asset_copy['endereco_convertido'] = None
                    asset_copy['erro_conversao'] = 'Coordenadas não disponíveis'
                    assets_convertidos.append(asset_copy)
                    sem_coordenadas += 1
                    continue
                
                # Tentar conversão
                endereco_encontrado = None
                erro_conversao = None
                metodo_conversao = None
                
                try:
                    lat_float = float(lat)
                    lng_float = float(lng)
                    
                    # 1. PRIMEIRO: Tentar cache local (mais rápido)
                    for (known_lat, known_lng), endereco in coordenadas_conhecidas.items():
                        if abs(lat_float - known_lat) < 0.1 and abs(lng_float - known_lng) < 0.1:
                            endereco_encontrado = endereco
                            metodo_conversao = "cache_local"
                            conversoes_cache += 1
                            break
                    
                    # 2. SEGUNDO: Se não encontrar no cache, tentar Nominatim (apenas para os primeiros 20)
                    if not endereco_encontrado and i < 20:  # Limitar a 20 requisições externas
                        try:
                            headers = {
                                'User-Agent': 'GoldenSat-AssetTracker/1.0 (https://intgoldensat.com.br)'
                            }
                            
                            reverse_geocode_url = "https://nominatim.openstreetmap.org/reverse"
                            params = {
                                'lat': lat,
                                'lon': lng,
                                'format': 'json',
                                'addressdetails': 1,
                                'accept-language': 'pt-BR'
                            }
                            
                            geo_response = requests.get(reverse_geocode_url, params=params, headers=headers, timeout=5)
                            
                            if geo_response.status_code == 200:
                                geo_data = geo_response.json()
                                address = geo_data.get('address', {})
                                
                                # Montar endereço completo
                                endereco_partes = []
                                if address.get('road'):
                                    endereco_partes.append(address['road'])
                                if address.get('house_number'):
                                    endereco_partes.append(address['house_number'])
                                if address.get('suburb'):
                                    endereco_partes.append(address['suburb'])
                                if address.get('city'):
                                    endereco_partes.append(address['city'])
                                if address.get('state'):
                                    endereco_partes.append(address['state'])
                                if address.get('postcode'):
                                    endereco_partes.append(address['postcode'])
                                if address.get('country'):
                                    endereco_partes.append(address['country'])
                                
                                endereco_encontrado = ', '.join(endereco_partes) if endereco_partes else geo_data.get('display_name', 'Endereço não encontrado')
                                metodo_conversao = "nominatim"
                                conversoes_nominatim += 1
                            else:
                                erro_conversao = f'Erro na conversão: Status {geo_response.status_code}'
                                erros += 1
                                
                        except Exception as e:
                            erro_conversao = f'Erro ao converter coordenadas: {str(e)}'
                            erros += 1
                    
                    # 3. Se não conseguiu converter, marcar como não convertido
                    if not endereco_encontrado and not erro_conversao:
                        erro_conversao = 'Coordenadas fora da área mapeada'
                        erros += 1
                    
                except Exception as e:
                    erro_conversao = f'Erro ao processar coordenadas: {str(e)}'
                    erros += 1
                
                # Adicionar dados convertidos ao asset
                if endereco_encontrado:
                    asset_copy['endereco_convertido'] = {
                        'endereco_completo': endereco_encontrado,
                        'coordenadas_originais': {
                            'lat': lat,
                            'lng': lng
                        },
                        'metodo_conversao': metodo_conversao
                    }
                    asset_copy['erro_conversao'] = None
                else:
                    asset_copy['endereco_convertido'] = None
                    asset_copy['erro_conversao'] = erro_conversao
                
                assets_convertidos.append(asset_copy)
                
                # Pausa mínima entre requisições (apenas para Nominatim)
                if metodo_conversao == "nominatim":
                    time.sleep(0.2)
                
            except Exception as e:
                asset_copy = dict(asset) if isinstance(asset, dict) else {}
                asset_copy['endereco_convertido'] = None
                asset_copy['erro_conversao'] = f'Erro ao processar asset: {str(e)}'
                assets_convertidos.append(asset_copy)
                erros += 1
                print(f"Erro ao processar asset: {str(e)}")
        
        print("=== FINALIZANDO CONVERSÃO ===")
        print(f"Estatísticas:")
        print(f"- Total de assets: {total_assets}")
        print(f"- Conversões por cache: {conversoes_cache}")
        print(f"- Conversões por Nominatim: {conversoes_nominatim}")
        print(f"- Sem coordenadas: {sem_coordenadas}")
        print(f"- Erros: {erros}")
        
        # Retornar dados convertidos
        return JsonResponse({
            'status': 'success',
            'total_assets': len(assets_convertidos),
            'assets_convertidos': assets_convertidos,
            'resumo': {
                'com_endereco': len([a for a in assets_convertidos if a.get('endereco_convertido')]),
                'sem_endereco': len([a for a in assets_convertidos if not a.get('endereco_convertido')]),
                'com_erro': len([a for a in assets_convertidos if a.get('erro_conversao')]),
                'estatisticas_detalhadas': {
                    'conversoes_cache': conversoes_cache,
                    'conversoes_nominatim': conversoes_nominatim,
                    'sem_coordenadas': sem_coordenadas,
                    'erros': erros
                }
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Erro inesperado: {str(e)}'
        }, status=500)

@csrf_exempt
def mongol_assets(request):
    """
    Endpoint para buscar dados da API Mongol sem conversão de coordenadas
    """
    try:
        print("=== INICIANDO BUSCA NA API MONGOL ===")
        
        # URL da API Mongol
        mongol_url = "https://mongol.brono.com/mongol/api.php"
        params = {
            'commandname': 'get_last_transmits',
            'user': 'wimc_u_nestle',
            'pass': 'Inte@20xx',
            'format': 'json1'
        }
        
        # Configurar headers e timeout
        headers = {
            'User-Agent': 'GoldenSat-MongolTracker/1.0 (https://intgoldensat.com.br)'
        }
        
        print(f"Fazendo requisição para: {mongol_url}")
        print(f"Parâmetros: {params}")
        
        # Fazer requisição com retry e timeout aumentado
        max_retries = 3
        timeout = 30
        
        for attempt in range(max_retries):
            try:
                print(f"Tentativa {attempt + 1}/{max_retries}")
                response = requests.get(mongol_url, params=params, headers=headers, timeout=timeout)
                
                if response.status_code == 200:
                    print(f"Resposta recebida com sucesso! Status: {response.status_code}")
                    print(f"Tamanho da resposta: {len(response.content)} bytes")
                    
                    # Tentar fazer parse do JSON
                    try:
                        assets_data = response.json()
                        print(f"Dados parseados com sucesso! Total de assets: {len(assets_data)}")
                        
                        # Retornar dados sem conversão
                        return JsonResponse({
                            'status': 'success',
                            'total_assets': len(assets_data),
                            'assets': assets_data,
                            'fonte': 'API Mongol',
                            'timestamp': time.time()
                        })
                        
                    except json.JSONDecodeError as json_error:
                        print(f"Erro ao fazer parse do JSON: {json_error}")
                        print(f"Primeiros 500 caracteres da resposta: {response.text[:500]}")
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Erro ao fazer parse do JSON: {str(json_error)}'
                        }, status=500)
                
                else:
                    print(f"Erro na requisição: Status {response.status_code}")
                    print(f"Resposta: {response.text[:500]}")
                    
                    if attempt < max_retries - 1:
                        print(f"Aguardando 5 segundos antes da próxima tentativa...")
                        time.sleep(5)
                    else:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Erro na API Mongol: Status {response.status_code}'
                        }, status=response.status_code)
                        
            except requests.exceptions.Timeout:
                print(f"Timeout na tentativa {attempt + 1}")
                if attempt < max_retries - 1:
                    print(f"Aguardando 10 segundos antes da próxima tentativa...")
                    time.sleep(10)
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Timeout na requisição para a API Mongol'
                    }, status=408)
                    
            except requests.exceptions.RequestException as e:
                print(f"Erro de requisição na tentativa {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    print(f"Aguardando 5 segundos antes da próxima tentativa...")
                    time.sleep(5)
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Erro de conexão: {str(e)}'
                    }, status=500)
        
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro inesperado: {str(e)}'
        }, status=500)


@csrf_exempt
def mongol_assets_com_enderecos(request):
    """
    Endpoint para buscar dados da API Mongol e converter coordenadas em endereços
    """
    try:
        print("=== INICIANDO BUSCA E CONVERSÃO DA API MONGOL ===")
        
        # Primeiro, buscar dados da API Mongol
        mongol_url = "https://mongol.brono.com/mongol/api.php"
        params = {
            'commandname': 'get_last_transmits',
            'user': 'wimc_u_nestle',
            'pass': 'Inte@20xx',
            'format': 'json1'
        }
        
        headers = {
            'User-Agent': 'GoldenSat-MongolTracker/1.0 (https://intgoldensat.com.br)'
        }
        
        print(f"Fazendo requisição para: {mongol_url}")
        
        # Fazer requisição com retry
        max_retries = 3
        timeout = 30
        
        for attempt in range(max_retries):
            try:
                print(f"Tentativa {attempt + 1}/{max_retries}")
                response = requests.get(mongol_url, params=params, headers=headers, timeout=timeout)
                
                if response.status_code == 200:
                    print(f"Resposta recebida com sucesso! Status: {response.status_code}")
                    
                    try:
                        assets_data = response.json()
                        print(f"Dados parseados com sucesso! Total de assets: {len(assets_data)}")
                        break
                        
                    except json.JSONDecodeError as json_error:
                        print(f"Erro ao fazer parse do JSON: {json_error}")
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Erro ao fazer parse do JSON: {str(json_error)}'
                        }, status=500)
                
                else:
                    print(f"Erro na requisição: Status {response.status_code}")
                    
                    if attempt < max_retries - 1:
                        print(f"Aguardando 5 segundos antes da próxima tentativa...")
                        time.sleep(5)
                    else:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Erro na API Mongol: Status {response.status_code}'
                        }, status=response.status_code)
                        
            except requests.exceptions.Timeout:
                print(f"Timeout na tentativa {attempt + 1}")
                if attempt < max_retries - 1:
                    print(f"Aguardando 10 segundos antes da próxima tentativa...")
                    time.sleep(10)
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Timeout na requisição para a API Mongol'
                    }, status=408)
                    
            except requests.exceptions.RequestException as e:
                print(f"Erro de requisição na tentativa {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    print(f"Aguardando 5 segundos antes da próxima tentativa...")
                    time.sleep(5)
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Erro de conexão: {str(e)}'
                    }, status=500)
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Falha ao buscar dados da API Mongol após todas as tentativas'
            }, status=500)
        
        # Cache de coordenadas conhecidas para conversão rápida
        coordenadas_conhecidas = {
            # Brasil - São Paulo
            (-23.9321, -46.3506): "São Paulo, SP, Brasil",
            (-23.9219, -46.3508): "São Paulo, SP, Brasil",
            (-23.6338, -46.5194): "São Paulo, SP, Brasil",
            (-23.8316, -46.3688): "São Paulo, SP, Brasil",
            (-23.6363, -46.5127): "São Paulo, SP, Brasil",
            
            # Brasil - Minas Gerais
            (-19.0018, -46.2446): "Uberlândia, MG, Brasil",
            
            # Europa - Suíça
            (46.6796, 6.9029): "Genebra, Suíça",
            (47.5545, 7.6416): "Basileia, Suíça",
            (46.8027, 7.1533): "Berna, Suíça",
            (46.6807, 6.9037): "Genebra, Suíça",
            
            # Europa - França
            (49.5533, 5.8265): "Nancy, França",
            
            # Europa - Marrocos
            (35.8668, -5.5363): "Tânger, Marrocos",
            
            # Europa - Bélgica
            (51.2641, 4.4138): "Antuérpia, Bélgica",
            (51.2849, 4.3787): "Antuérpia, Bélgica",
            
            # Europa - Alemanha
            (53.1011, 8.7718): "Bremen, Alemanha",
            (53.1012, 8.7717): "Bremen, Alemanha",
            (53.1211, 8.7324): "Bremen, Alemanha",
            
            # Europa - Holanda
            (51.3532, 4.2592): "Roterdã, Holanda",
            
            # Outras localizações conhecidas
            (0, 0): "Coordenadas inválidas",
        }
        
        # Lista para armazenar dados convertidos
        assets_convertidos = []
        
        # Processar TODOS os assets
        assets_para_processar = assets_data
        total_assets = len(assets_para_processar)
        print(f"Processando {total_assets} assets para conversão...")
        
        # Contadores para estatísticas
        conversoes_cache = 0
        conversoes_nominatim = 0
        sem_coordenadas = 0
        erros = 0
        
        # Processar cada asset
        for i, asset in enumerate(assets_para_processar):
            try:
                # Log de progresso a cada 10 assets
                if (i + 1) % 10 == 0 or i == 0:
                    print(f"Processando asset {i+1}/{total_assets} - {(i+1)/total_assets*100:.1f}%")
                
                # Criar uma cópia do asset
                asset_copy = dict(asset) if isinstance(asset, dict) else {}
                
                # Extrair coordenadas (formato da API Mongol)
                lat = asset_copy.get('latitude')
                lng = asset_copy.get('longitude')
                
                # Se não tiver coordenadas ou coordenadas inválidas, pular
                if not lat or not lng or (lat == 0 and lng == 0):
                    asset_copy['endereco_convertido'] = None
                    asset_copy['erro_conversao'] = 'Coordenadas não disponíveis ou inválidas'
                    assets_convertidos.append(asset_copy)
                    sem_coordenadas += 1
                    continue
                
                # Tentar conversão
                endereco_encontrado = None
                erro_conversao = None
                metodo_conversao = None
                
                try:
                    lat_float = float(lat)
                    lng_float = float(lng)
                    
                    # 1. PRIMEIRO: Tentar cache local (mais rápido)
                    for (known_lat, known_lng), endereco in coordenadas_conhecidas.items():
                        if abs(lat_float - known_lat) < 0.1 and abs(lng_float - known_lng) < 0.1:
                            endereco_encontrado = endereco
                            metodo_conversao = "cache_local"
                            conversoes_cache += 1
                            break
                    
                    # 2. SEGUNDO: Se não encontrar no cache, tentar Nominatim (apenas para os primeiros 20)
                    if not endereco_encontrado and i < 20:  # Limitar a 20 requisições externas
                        try:
                            headers = {
                                'User-Agent': 'GoldenSat-MongolTracker/1.0 (https://intgoldensat.com.br)'
                            }
                            
                            reverse_geocode_url = "https://nominatim.openstreetmap.org/reverse"
                            params = {
                                'lat': lat,
                                'lon': lng,
                                'format': 'json',
                                'addressdetails': 1,
                                'accept-language': 'pt-BR'
                            }
                            
                            geo_response = requests.get(reverse_geocode_url, params=params, headers=headers, timeout=5)
                            
                            if geo_response.status_code == 200:
                                geo_data = geo_response.json()
                                address = geo_data.get('address', {})
                                
                                # Montar endereço completo
                                endereco_partes = []
                                if address.get('road'):
                                    endereco_partes.append(address['road'])
                                if address.get('house_number'):
                                    endereco_partes.append(address['house_number'])
                                if address.get('suburb'):
                                    endereco_partes.append(address['suburb'])
                                if address.get('city'):
                                    endereco_partes.append(address['city'])
                                if address.get('state'):
                                    endereco_partes.append(address['state'])
                                if address.get('postcode'):
                                    endereco_partes.append(address['postcode'])
                                if address.get('country'):
                                    endereco_partes.append(address['country'])
                                
                                endereco_encontrado = ', '.join(endereco_partes) if endereco_partes else geo_data.get('display_name', 'Endereço não encontrado')
                                metodo_conversao = "nominatim"
                                conversoes_nominatim += 1
                            else:
                                erro_conversao = f'Erro na conversão: Status {geo_response.status_code}'
                                erros += 1
                                
                        except Exception as e:
                            erro_conversao = f'Erro ao converter coordenadas: {str(e)}'
                            erros += 1
                    
                    # 3. Se não conseguiu converter, marcar como não convertido
                    if not endereco_encontrado and not erro_conversao:
                        erro_conversao = 'Coordenadas fora da área mapeada'
                        erros += 1
                    
                except Exception as e:
                    erro_conversao = f'Erro ao processar coordenadas: {str(e)}'
                    erros += 1
                
                # Adicionar dados convertidos ao asset
                if endereco_encontrado:
                    asset_copy['endereco_convertido'] = {
                        'endereco_completo': endereco_encontrado,
                        'coordenadas_originais': {
                            'lat': lat,
                            'lng': lng
                        },
                        'metodo_conversao': metodo_conversao
                    }
                    asset_copy['erro_conversao'] = None
                else:
                    asset_copy['endereco_convertido'] = None
                    asset_copy['erro_conversao'] = erro_conversao
                
                assets_convertidos.append(asset_copy)
                
                # Pausa mínima entre requisições (apenas para Nominatim)
                if metodo_conversao == "nominatim":
                    time.sleep(0.2)
                
            except Exception as e:
                asset_copy = dict(asset) if isinstance(asset, dict) else {}
                asset_copy['endereco_convertido'] = None
                asset_copy['erro_conversao'] = f'Erro ao processar asset: {str(e)}'
                assets_convertidos.append(asset_copy)
                erros += 1
                print(f"Erro ao processar asset: {str(e)}")
        
        print("=== FINALIZANDO CONVERSÃO MONGOL ===")
        print(f"Estatísticas:")
        print(f"- Total de assets: {total_assets}")
        print(f"- Conversões por cache: {conversoes_cache}")
        print(f"- Conversões por Nominatim: {conversoes_nominatim}")
        print(f"- Sem coordenadas: {sem_coordenadas}")
        print(f"- Erros: {erros}")
        
        # Retornar dados convertidos
        return JsonResponse({
            'status': 'success',
            'total_assets': len(assets_convertidos),
            'assets_convertidos': assets_convertidos,
            'fonte': 'API Mongol',
            'timestamp': time.time(),
            'resumo': {
                'com_endereco': len([a for a in assets_convertidos if a.get('endereco_convertido')]),
                'sem_endereco': len([a for a in assets_convertidos if not a.get('endereco_convertido')]),
                'com_erro': len([a for a in assets_convertidos if a.get('erro_conversao')]),
                'estatisticas_detalhadas': {
                    'conversoes_cache': conversoes_cache,
                    'conversoes_nominatim': conversoes_nominatim,
                    'sem_coordenadas': sem_coordenadas,
                    'erros': erros
                }
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Erro inesperado: {str(e)}'
        }, status=500)

@csrf_exempt
def mongol_test_view(request):
    """
    View para renderizar a página de teste da API Mongol
    """
    return render(request, 'mongol_test.html')

@csrf_exempt
def assets_unificado(request):
    """
    Endpoint unificado que busca dados de ambas as APIs (GS Controller e Mongol)
    e retorna um resultado consolidado
    """
    try:
        print("=== INICIANDO BUSCA UNIFICADA ===")
        
        # Configurações comuns
        headers = {
            'User-Agent': 'GoldenSat-UnifiedTracker/1.0 (https://intgoldensat.com.br)'
        }
        max_retries = 3
        timeout = 30
        
        # Dicionário para armazenar resultados
        resultados = {
            'gs_controller': {'status': 'error', 'data': None, 'error': None},
            'mongol': {'status': 'error', 'data': None, 'error': None}
        }
        
        # 1. BUSCAR DADOS DA API GS CONTROLLER
        print("1. Buscando dados da API GS Controller...")
        gs_url = "https://gscontroller.com.br/api/get_assetscontrols_data/"
        gs_params = {
            'user': 'wimc_u_nestle',
            'pass': 'Inte@20xx'
        }
        
        for attempt in range(max_retries):
            try:
                print(f"   Tentativa {attempt + 1}/{max_retries} - GS Controller")
                response = requests.get(gs_url, params=gs_params, headers=headers, timeout=timeout)
                
                if response.status_code == 200:
                    gs_data = response.json()
                    resultados['gs_controller'] = {
                        'status': 'success',
                        'data': gs_data,
                        'error': None
                    }
                    print(f"   ✅ GS Controller: {len(gs_data)} assets encontrados")
                    break
                else:
                    print(f"   ❌ GS Controller: Status {response.status_code}")
                    if attempt == max_retries - 1:
                        resultados['gs_controller']['error'] = f'Status {response.status_code}'
                        
            except requests.exceptions.Timeout:
                print(f"   ⏰ Timeout na tentativa {attempt + 1} - GS Controller")
                if attempt == max_retries - 1:
                    resultados['gs_controller']['error'] = 'Timeout'
            except Exception as e:
                print(f"   ❌ Erro na tentativa {attempt + 1} - GS Controller: {e}")
                if attempt == max_retries - 1:
                    resultados['gs_controller']['error'] = str(e)
        
        # 2. BUSCAR DADOS DA API MONGOL
        print("2. Buscando dados da API Mongol...")
        mongol_url = "https://mongol.brono.com/mongol/api.php"
        mongol_params = {
            'commandname': 'get_last_transmits',
            'user': 'wimc_u_nestle',
            'pass': 'Inte@20xx',
            'format': 'json1'
        }
        
        for attempt in range(max_retries):
            try:
                print(f"   Tentativa {attempt + 1}/{max_retries} - Mongol")
                response = requests.get(mongol_url, params=mongol_params, headers=headers, timeout=timeout)
                
                if response.status_code == 200:
                    mongol_data = response.json()
                    resultados['mongol'] = {
                        'status': 'success',
                        'data': mongol_data,
                        'error': None
                    }
                    print(f"   ✅ Mongol: {len(mongol_data)} assets encontrados")
                    break
                else:
                    print(f"   ❌ Mongol: Status {response.status_code}")
                    if attempt == max_retries - 1:
                        resultados['mongol']['error'] = f'Status {response.status_code}'
                        
            except requests.exceptions.Timeout:
                print(f"   ⏰ Timeout na tentativa {attempt + 1} - Mongol")
                if attempt == max_retries - 1:
                    resultados['mongol']['error'] = 'Timeout'
            except Exception as e:
                print(f"   ❌ Erro na tentativa {attempt + 1} - Mongol: {e}")
                if attempt == max_retries - 1:
                    resultados['mongol']['error'] = str(e)
        
        # 3. PROCESSAR E CONSOLIDAR DADOS
        print("3. Processando e consolidando dados...")
        
        # Cache de coordenadas conhecidas para conversão
        coordenadas_conhecidas = {
            # Brasil - Fortaleza
            (-3.8715467, -38.6118471): "Fortaleza, CE, Brasil",
            (-3.866656, -38.612863): "Fortaleza, CE, Brasil",
            (-3.7318616, -38.5266694): "Fortaleza, CE, Brasil",
            
            # São Paulo, SP
            (-23.6353703, -46.5154297): "São Paulo, SP, Brasil",
            (-23.6396175, -46.5141551): "São Paulo, SP, Brasil",
            (-23.6323341, -46.5137985): "São Paulo, SP, Brasil",
            (-23.6354743, -46.5150922): "São Paulo, SP, Brasil",
            (-23.5505199, -46.6333094): "São Paulo, SP, Brasil",
            
            # Brasil - Minas Gerais
            (-19.0018, -46.2446): "Uberlândia, MG, Brasil",
            
            # Europa - Suíça
            (46.6796, 6.9029): "Genebra, Suíça",
            (47.5545, 7.6416): "Basileia, Suíça",
            (46.8027, 7.1533): "Berna, Suíça",
            (46.6807, 6.9037): "Genebra, Suíça",
            
            # Europa - França
            (49.5533, 5.8265): "Nancy, França",
            
            # Europa - Marrocos
            (35.8668, -5.5363): "Tânger, Marrocos",
            
            # Europa - Bélgica
            (51.2641, 4.4138): "Antuérpia, Bélgica",
            (51.2849, 4.3787): "Antuérpia, Bélgica",
            
            # Europa - Alemanha
            (53.1011, 8.7718): "Bremen, Alemanha",
            (53.1012, 8.7717): "Bremen, Alemanha",
            (53.1211, 8.7324): "Bremen, Alemanha",
            
            # Europa - Holanda
            (51.3532, 4.2592): "Roterdã, Holanda",
            
            # Outras localizações conhecidas
            (-3.1190275, -60.0217314): "Manaus, AM, Brasil",
            (-30.0346471, -51.2176584): "Porto Alegre, RS, Brasil",
            (-12.9715987, -38.5010949): "Salvador, BA, Brasil",
            (-15.7942287, -47.8821658): "Brasília, DF, Brasil",
            (-19.919054, -43.937644): "Belo Horizonte, MG, Brasil",
            (-25.4289541, -49.267137): "Curitiba, PR, Brasil",
            (-8.047562, -34.877003): "Recife, PE, Brasil",
            (-5.7944787, -35.211): "Natal, RN, Brasil",
        }
        
        # Lista consolidada de assets
        assets_consolidados = []
        estatisticas = {
            'gs_controller': {'total': 0, 'com_endereco': 0, 'sem_endereco': 0, 'erros': 0},
            'mongol': {'total': 0, 'com_endereco': 0, 'sem_endereco': 0, 'erros': 0},
            'conversoes_cache': 0,
            'conversoes_nominatim': 0
        }
        
        # Processar dados do GS Controller
        print(f"   Status GS Controller: {resultados['gs_controller']['status']}")
        print(f"   Dados GS Controller: {resultados['gs_controller']['data'] is not None}")
        if resultados['gs_controller']['data']:
            # Corrigir: se vier como dict com FObject, usar FObject
            gs_data = resultados['gs_controller']['data']
            if isinstance(gs_data, dict) and 'FObject' in gs_data:
                gs_assets = gs_data['FObject']
            else:
                gs_assets = gs_data
            print(f"   Tamanho dados GS Controller: {len(gs_assets)}")
        
        if resultados['gs_controller']['status'] == 'success' and resultados['gs_controller']['data']:
            print(f"   Processando {len(gs_assets)} assets do GS Controller...")
            
            for i, asset in enumerate(gs_assets):
                try:
                    asset_copy = dict(asset)
                    
                    # Extrair coordenadas (formato GS Controller)
                    lat = asset_copy.get('FLatitude') or asset_copy.get('lat')
                    lng = asset_copy.get('FLongitude') or asset_copy.get('lng')
                    
                    # Tentar conversão
                    endereco_encontrado = None
                    metodo_conversao = None
                    
                    if lat and lng:
                        try:
                            lat_float = float(lat)
                            lng_float = float(lng)
                            
                            # Tentar cache local
                            for (known_lat, known_lng), endereco in coordenadas_conhecidas.items():
                                if abs(lat_float - known_lat) < 0.1 and abs(lng_float - known_lng) < 0.1:
                                    endereco_encontrado = endereco
                                    metodo_conversao = "cache_local"
                                    estatisticas['conversoes_cache'] += 1
                                    break
                            
                            # Tentar Nominatim (limitado a 10 requisições por API)
                            if not endereco_encontrado and i < 10:
                                try:
                                    reverse_geocode_url = "https://nominatim.openstreetmap.org/reverse"
                                    params = {
                                        'lat': lat,
                                        'lon': lng,
                                        'format': 'json',
                                        'addressdetails': 1,
                                        'accept-language': 'pt-BR'
                                    }
                                    
                                    geo_response = requests.get(reverse_geocode_url, params=params, headers=headers, timeout=5)
                                    
                                    if geo_response.status_code == 200:
                                        geo_data = geo_response.json()
                                        address = geo_data.get('address', {})
                                        
                                        endereco_partes = []
                                        if address.get('road'):
                                            endereco_partes.append(address['road'])
                                        if address.get('house_number'):
                                            endereco_partes.append(address['house_number'])
                                        if address.get('suburb'):
                                            endereco_partes.append(address['suburb'])
                                        if address.get('city'):
                                            endereco_partes.append(address['city'])
                                        if address.get('state'):
                                            endereco_partes.append(address['state'])
                                        if address.get('postcode'):
                                            endereco_partes.append(address['postcode'])
                                        if address.get('country'):
                                            endereco_partes.append(address['country'])
                                        
                                        endereco_encontrado = ', '.join(endereco_partes) if endereco_partes else geo_data.get('display_name', 'Endereço não encontrado')
                                        metodo_conversao = "nominatim"
                                        estatisticas['conversoes_nominatim'] += 1
                                        
                                        time.sleep(0.2)  # Pausa entre requisições
                                        
                                except Exception as e:
                                    print(f"   Erro Nominatim GS Controller: {e}")
                            
                        except Exception as e:
                            print(f"   Erro ao processar coordenadas GS Controller: {e}")
                    
                    # Adicionar dados convertidos
                    if endereco_encontrado:
                        asset_copy['endereco_convertido'] = {
                            'endereco_completo': endereco_encontrado,
                            'coordenadas_originais': {'lat': lat, 'lng': lng},
                            'metodo_conversao': metodo_conversao
                        }
                        estatisticas['gs_controller']['com_endereco'] += 1
                    else:
                        asset_copy['endereco_convertido'] = None
                        estatisticas['gs_controller']['sem_endereco'] += 1
                    
                    asset_copy['fonte_api'] = 'GS Controller'
                    assets_consolidados.append(asset_copy)
                    estatisticas['gs_controller']['total'] += 1
                    
                    # Debug: mostrar alguns assets processados
                    if estatisticas['gs_controller']['total'] <= 3:
                        print(f"      Asset GS Controller {estatisticas['gs_controller']['total']}: {asset_copy.get('FVehicleName', 'Sem nome')} - {asset_copy.get('fonte_api')}")
                    
                except Exception as e:
                    print(f"   Erro ao processar asset GS Controller: {e}")
                    estatisticas['gs_controller']['erros'] += 1
        
        # Processar dados do Mongol
        print(f"   Status Mongol: {resultados['mongol']['status']}")
        print(f"   Dados Mongol: {resultados['mongol']['data'] is not None}")
        if resultados['mongol']['data']:
            print(f"   Tamanho dados Mongol: {len(resultados['mongol']['data'])}")
        
        if resultados['mongol']['status'] == 'success' and resultados['mongol']['data']:
            print(f"   Processando {len(resultados['mongol']['data'])} assets do Mongol...")
            
            for i, asset in enumerate(resultados['mongol']['data']):
                try:
                    asset_copy = dict(asset)
                    
                    # Extrair coordenadas (formato Mongol)
                    lat = asset_copy.get('latitude')
                    lng = asset_copy.get('longitude')
                    
                    # Tentar conversão
                    endereco_encontrado = None
                    metodo_conversao = None
                    
                    if lat and lng and not (lat == 0 and lng == 0):
                        try:
                            lat_float = float(lat)
                            lng_float = float(lng)
                            
                            # Tentar cache local
                            for (known_lat, known_lng), endereco in coordenadas_conhecidas.items():
                                if abs(lat_float - known_lat) < 0.1 and abs(lng_float - known_lng) < 0.1:
                                    endereco_encontrado = endereco
                                    metodo_conversao = "cache_local"
                                    estatisticas['conversoes_cache'] += 1
                                    break
                            
                            # Tentar Nominatim (limitado a 10 requisições por API)
                            if not endereco_encontrado and i < 10:
                                try:
                                    reverse_geocode_url = "https://nominatim.openstreetmap.org/reverse"
                                    params = {
                                        'lat': lat,
                                        'lon': lng,
                                        'format': 'json',
                                        'addressdetails': 1,
                                        'accept-language': 'pt-BR'
                                    }
                                    
                                    geo_response = requests.get(reverse_geocode_url, params=params, headers=headers, timeout=5)
                                    
                                    if geo_response.status_code == 200:
                                        geo_data = geo_response.json()
                                        address = geo_data.get('address', {})
                                        
                                        endereco_partes = []
                                        if address.get('road'):
                                            endereco_partes.append(address['road'])
                                        if address.get('house_number'):
                                            endereco_partes.append(address['house_number'])
                                        if address.get('suburb'):
                                            endereco_partes.append(address['suburb'])
                                        if address.get('city'):
                                            endereco_partes.append(address['city'])
                                        if address.get('state'):
                                            endereco_partes.append(address['state'])
                                        if address.get('postcode'):
                                            endereco_partes.append(address['postcode'])
                                        if address.get('country'):
                                            endereco_partes.append(address['country'])
                                        
                                        endereco_encontrado = ', '.join(endereco_partes) if endereco_partes else geo_data.get('display_name', 'Endereço não encontrado')
                                        metodo_conversao = "nominatim"
                                        estatisticas['conversoes_nominatim'] += 1
                                        
                                        time.sleep(0.2)  # Pausa entre requisições
                                        
                                except Exception as e:
                                    print(f"   Erro Nominatim Mongol: {e}")
                            
                        except Exception as e:
                            print(f"   Erro ao processar coordenadas Mongol: {e}")
                    
                    # Adicionar dados convertidos
                    if endereco_encontrado:
                        asset_copy['endereco_convertido'] = {
                            'endereco_completo': endereco_encontrado,
                            'coordenadas_originais': {'lat': lat, 'lng': lng},
                            'metodo_conversao': metodo_conversao
                        }
                        estatisticas['mongol']['com_endereco'] += 1
                    else:
                        asset_copy['endereco_convertido'] = None
                        estatisticas['mongol']['sem_endereco'] += 1
                    
                    asset_copy['fonte_api'] = 'Mongol'
                    assets_consolidados.append(asset_copy)
                    estatisticas['mongol']['total'] += 1
                    
                    # Debug: mostrar alguns assets processados
                    if estatisticas['mongol']['total'] <= 3:
                        print(f"      Asset Mongol {estatisticas['mongol']['total']}: {asset_copy.get('vehicle_name', 'Sem nome')} - {asset_copy.get('fonte_api')}")
                    
                except Exception as e:
                    print(f"   Erro ao processar asset Mongol: {e}")
                    estatisticas['mongol']['erros'] += 1
        
        print("=== FINALIZANDO PROCESSAMENTO UNIFICADO ===")
        print(f"Estatísticas:")
        print(f"- GS Controller: {estatisticas['gs_controller']['total']} assets")
        print(f"- Mongol: {estatisticas['mongol']['total']} assets")
        print(f"- Total consolidado: {len(assets_consolidados)} assets")
        print(f"- Conversões por cache: {estatisticas['conversoes_cache']}")
        print(f"- Conversões por Nominatim: {estatisticas['conversoes_nominatim']}")
        
        # Retornar resultado consolidado
        return JsonResponse({
            'status': 'success',
            'timestamp': time.time(),
            'resumo_apis': {
                'gs_controller': {
                    'status': resultados['gs_controller']['status'],
                    'total_assets': estatisticas['gs_controller']['total'],
                    'com_endereco': estatisticas['gs_controller']['com_endereco'],
                    'sem_endereco': estatisticas['gs_controller']['sem_endereco'],
                    'erros': estatisticas['gs_controller']['erros'],
                    'error': resultados['gs_controller']['error']
                },
                'mongol': {
                    'status': resultados['mongol']['status'],
                    'total_assets': estatisticas['mongol']['total'],
                    'com_endereco': estatisticas['mongol']['com_endereco'],
                    'sem_endereco': estatisticas['mongol']['sem_endereco'],
                    'erros': estatisticas['mongol']['erros'],
                    'error': resultados['mongol']['error']
                }
            },
            'total_assets_consolidados': len(assets_consolidados),
            'assets_consolidados': assets_consolidados,
            'estatisticas_conversao': {
                'conversoes_cache': estatisticas['conversoes_cache'],
                'conversoes_nominatim': estatisticas['conversoes_nominatim']
            }
        })
        
    except Exception as e:
        print(f"Erro inesperado no endpoint unificado: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro inesperado: {str(e)}'
        }, status=500)

@csrf_exempt
def assets_unificado_test_view(request):
    """
    View para renderizar a página de teste do endpoint unificado
    """
    return render(request, 'assets_unificado_test.html')

@csrf_exempt
def debug_gs_controller_raw(request):
    """
    Endpoint para debug - retorna dados brutos da API GS Controller
    """
    try:
        print("=== DEBUG: Buscando dados brutos da API GS Controller ===")
        
        headers = {
            'User-Agent': 'GoldenSat-Debug/1.0 (https://intgoldensat.com.br)'
        }
        
        gs_url = "https://gscontroller.com.br/api/get_assetscontrols_data/"
        gs_params = {
            'user': 'wimc_u_nestle',
            'pass': 'Inte@20xx'
        }
        
        response = requests.get(gs_url, params=gs_params, headers=headers, timeout=30)
        
        print(f"Status da resposta: {response.status_code}")
        print(f"Headers da resposta: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Tipo de dados retornado: {type(data)}")
                print(f"Tamanho dos dados: {len(data) if isinstance(data, (list, dict)) else 'N/A'}")
                
                if isinstance(data, list) and len(data) > 0:
                    print(f"Primeiro item: {data[0]}")
                    print(f"Chaves do primeiro item: {list(data[0].keys()) if isinstance(data[0], dict) else 'N/A'}")
                
                return JsonResponse({
                    'status': 'success',
                    'response_status': response.status_code,
                    'data_type': str(type(data)),
                    'data_length': len(data) if isinstance(data, (list, dict)) else None,
                    'sample_data': data[:3] if isinstance(data, list) and len(data) > 0 else data,
                    'raw_response': response.text[:1000]  # Primeiros 1000 caracteres
                })
                
            except json.JSONDecodeError as e:
                print(f"Erro ao fazer parse do JSON: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'Erro JSON: {str(e)}',
                    'raw_response': response.text[:1000]
                })
        else:
            print(f"Erro na requisição: {response.status_code}")
            return JsonResponse({
                'status': 'error',
                'message': f'Status {response.status_code}',
                'raw_response': response.text[:1000]
            })
            
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro: {str(e)}'
        }, status=500)

