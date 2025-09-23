from django.views.generic import ListView, CreateView
from requisicao.models import Requisicoes, Produto, Clientes
from django.shortcuts import get_object_or_404, redirect
from . import models, forms
from .models import Formulario
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from itertools import chain
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
from faturamento.models import Faturamento
# Removido import de Clientes pois não é mais necessário   

class FaturamentoListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = Requisicoes
    template_name = "faturamento_list.html"
    context_object_name = 'requisicoes'
    paginate_by = 6
    
    permission_required = 'faturamento.view_formulario'  # Substitua 'faturamento' pelo nome do seu aplicativo

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.exclude(status='Reprovado pelo CEO')

        # Aplicar ordenação
        ordenacao = self.request.GET.get('ordenacao')
        if ordenacao:
            queryset = queryset.order_by(ordenacao)
        else:
            queryset = queryset.order_by('-id')  # Ordenação padrão por ID em ordem decrescente

        # Obter parâmetros dos filtros
        data = self.request.GET.get('data')
        data_inicio = self.request.GET.get('data_inicio')
        data_fim = self.request.GET.get('data_fim')
        status_faturamento = self.request.GET.get('status_faturamento_filtro')
        cliente = self.request.GET.get('cliente_filtro')
        motivo = self.request.GET.get('motivo_filtro')
        tipo_produto = self.request.GET.get('tipo_produto_filtro')
        contrato_tipo = self.request.GET.get('contrato_tipo_filtro')
        fatura_tipo = self.request.GET.get('fatura_tipo_filtro')
        status = self.request.GET.get('status')
        comercial = self.request.GET.get('comercial')
        cnpj = self.request.GET.get('cnpj')
        busca = self.request.GET.get('busca')

        # Aplicar filtros de data sem usar lookups __date (evita UDF no SQLite)
        from datetime import datetime, time, timedelta
        from django.utils import timezone

        def to_aware(dt):
            try:
                # Só torna aware se USE_TZ estiver ativo e dt for naive
                if timezone.is_naive(dt) and timezone.is_aware(timezone.now()):
                    return timezone.make_aware(dt, timezone.get_current_timezone())
            except Exception:
                pass
            return dt

        if data:
            try:
                d = datetime.strptime(data, '%Y-%m-%d').date()
                start_dt = to_aware(datetime.combine(d, time.min))
                end_dt = to_aware(datetime.combine(d + timedelta(days=1), time.min))
                queryset = queryset.filter(data__gte=start_dt, data__lt=end_dt)
            except ValueError:
                pass
        elif data_inicio and data_fim:
            try:
                di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                start_dt = to_aware(datetime.combine(di, time.min))
                end_dt = to_aware(datetime.combine(df + timedelta(days=1), time.min))
                queryset = queryset.filter(data__gte=start_dt, data__lt=end_dt)
            except ValueError:
                pass
        elif data_inicio:
            try:
                di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                start_dt = to_aware(datetime.combine(di, time.min))
                queryset = queryset.filter(data__gte=start_dt)
            except ValueError:
                pass
        elif data_fim:
            try:
                df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                end_dt = to_aware(datetime.combine(df + timedelta(days=1), time.min))
                queryset = queryset.filter(data__lt=end_dt)
            except ValueError:
                pass

        if status_faturamento:
            queryset = queryset.filter(status_faturamento=status_faturamento)

        if cliente:
            queryset = queryset.filter(nome_id=cliente)

        if motivo:
            queryset = queryset.filter(motivo=motivo)

        if tipo_produto:
            queryset = queryset.filter(tipo_produto_id=tipo_produto)

        if contrato_tipo:
            queryset = queryset.filter(contrato=contrato_tipo)

        if fatura_tipo:
            queryset = queryset.filter(tipo_fatura=fatura_tipo)

        if status:
            queryset = queryset.filter(status=status)

        if comercial:
            queryset = queryset.filter(comercial=comercial)

        if cnpj:
            queryset = queryset.filter(cnpj__icontains=cnpj)

        if busca:
            queryset = queryset.filter(nome__nome__icontains=busca)

        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_faturamento_choices'] = Requisicoes._meta.get_field('status_faturamento').choices
        # Removido clientes_choices pois não é mais necessário
        context['motivo_choices'] = Requisicoes._meta.get_field('motivo').choices
        context['tipo_produto_choices'] = Produto.objects.all()
        context['contrato_tipo_choices'] = Requisicoes._meta.get_field('contrato').choices
        context['fatura_tipo_choices'] = Requisicoes._meta.get_field('tipo_fatura').choices
        context['status_choices'] = Requisicoes._meta.get_field('status').choices
        context['comercial_choices'] = Requisicoes._meta.get_field('comercial').choices
        
        # Manter os filtros aplicados no contexto para a paginação
        context['filtros_aplicados'] = {
            'data': self.request.GET.get('data', ''),
            'data_inicio': self.request.GET.get('data_inicio', ''),
            'data_fim': self.request.GET.get('data_fim', ''),
            'status_faturamento_filtro': self.request.GET.get('status_faturamento_filtro', ''),
            'cliente_filtro': self.request.GET.get('cliente_filtro', ''),
            'motivo_filtro': self.request.GET.get('motivo_filtro', ''),
            'tipo_produto_filtro': self.request.GET.get('tipo_produto_filtro', ''),
            'contrato_tipo_filtro': self.request.GET.get('contrato_tipo_filtro', ''),
            'fatura_tipo_filtro': self.request.GET.get('fatura_tipo_filtro', ''),
            'status': self.request.GET.get('status', ''),
            'comercial': self.request.GET.get('comercial', ''),
            'cnpj': self.request.GET.get('cnpj', ''),
            'busca': self.request.GET.get('busca', ''),
            'ordenacao': self.request.GET.get('ordenacao', ''),
        }
        
        # Adicionar os valores atuais dos filtros para preservar no formulário
        context['current_filters'] = self.request.GET
        
        return context

def update_status_faturamento(request, id):
    if request.method == 'POST':
        requisicao = get_object_or_404(Requisicoes, id=id)
        status_faturamento = request.POST.get('status_faturamento')
        requisicao.status_faturamento = status_faturamento
        requisicao.save()
        return JsonResponse({'status': 'success', 'message': 'Status atualizado com sucesso'})
    return JsonResponse({'status': 'error', 'message': 'Método não permitido'}, status=405)


class contratosListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = Requisicoes
    template_name = "contrato_list.html"
    context_object_name = 'contratos_list'
    paginate_by = 10
    permission_required = 'faturamento.view_formulario'  # Substitua 'faturamento' pelo nome do seu aplicativo

class formularioCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = Formulario
    template_name = 'Formulario_contratos.html'
    form_class = forms.FormularioForm
    success_url = reverse_lazy('formulario_create')
    permission_required = 'faturamento.add_formulario'  # Substitua 'faturamento' pelo nome do seu aplicativo

from formacompanhamento.models import Formacompanhamento
class FinanceirohListViews(ListView):
    model = Formacompanhamento  # Defina o modelo aqui
    template_name = "historicodeacionamento.html"  # Substitua pelo nome do seu template
    context_object_name = 'financeiro_list'
    paginate_by = 10


from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse



def atualizar_observacoes(request, id):
    registro = get_object_or_404(Requisicoes, id=id)
    if request.method == 'POST':
        observacoes = request.POST.get('observacoes')
        registro.observacoes = observacoes
        registro.save()
        
        # Manter os filtros aplicados no redirecionamento
        params = request.GET.copy()
        if params:
            return redirect(f"{reverse('faturamento_list')}?{params.urlencode()}")
        return redirect('faturamento_list')
    

from django.shortcuts import render

import requests
from django.shortcuts import render
import requests
from django.shortcuts import render
from django.utils.dateparse import parse_datetime
# faturamento/views.py

import requests
from django.shortcuts import render
from django.utils.dateparse import parse_datetime

def external_vouchers_list(request):
    url = 'https://gsvouchers.com.br/api/vouchers/'
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        vouchers = resp.json()
        for v in vouchers:
            # Converte a data de criação
            if iso := v.get('data'):
                v['data'] = parse_datetime(iso)
            # Converte a data de alteração
            if iso2 := v.get('updated_at'):
                v['updated_at'] = parse_datetime(iso2)
            # Calcula o saldo = gasto - 40
            try:
                gasto = float(v.get('valor') or 0)
                v['saldo'] = gasto - 40.0
            except (TypeError, ValueError):
                v['saldo'] = None
    except requests.RequestException:
        vouchers = []

    return render(request, 'external_vouchers_list.html', {
        'vouchers': vouchers
    })




from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

class FaturamentoInterativoView(TemplateView):
    template_name = 'faturamento_interativo.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ordenar das mais recentes para as mais antigas (por data de faturamento, depois por ID)
        faturamentos_list = Faturamento.objects.all().order_by('-faturamento', '-id')
        
        # Configurar paginação
        paginator = Paginator(faturamentos_list, 50)  # 50 registros por página
        page = self.request.GET.get('page')
        
        try:
            faturamentos = paginator.page(page)
        except PageNotAnInteger:
            faturamentos = paginator.page(1)
        except EmptyPage:
            faturamentos = paginator.page(paginator.num_pages)
        
        context['faturamentos'] = faturamentos
        context['paginator'] = paginator
        # Removido context['clientes'] pois não é mais necessário
        return context

@method_decorator(csrf_exempt, name='dispatch')
class FaturamentoSaveView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            row_id = data.get('row_id')
            faturamento_data = data.get('data', {})
            
            print(f"Dados recebidos: {faturamento_data}")
            print(f"Row ID: {row_id}")
            
            # Processar campos especiais - cliente é um campo de texto livre
            if 'cliente' in faturamento_data and faturamento_data['cliente']:
                print(f"Cliente digitado: {faturamento_data['cliente']}")
                # O cliente já é uma string, não precisa de processamento especial
            
            # Converter campos vazios para None e processar datas
            print(f"Processando campos antes da conversão: {faturamento_data}")
            
            # Criar um novo dicionário com os campos mapeados corretamente
            processed_data = {}
            
            for field, value in faturamento_data.items():
                # Tratar campos vazios primeiro
                if value == '' or value is None:
                    processed_data[field] = None
                    print(f"Campo {field} convertido para None")
                    continue
                
                # Mapear campos especiais
                mapped_field = field
                if field == 'vecimento':
                    mapped_field = 'vecimento_documento'
                elif field == 'documento':
                    mapped_field = 'tipo_documento'
                
                # Processar campos de data
                if mapped_field in ['faturamento', 'emissao', 'reajuste', 'vecimento_documento', 'data_pgto']:
                    try:
                        from datetime import datetime
                        processed_data[mapped_field] = datetime.strptime(value, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        processed_data[mapped_field] = None
                
                # Processar campos decimais
                elif mapped_field in ['valor_bruto', 'coluna1', 'valor_liquido', 'juros', 'valor_pago']:
                    try:
                        from decimal import Decimal
                        processed_data[mapped_field] = Decimal(str(value))
                    except (ValueError, TypeError):
                        processed_data[mapped_field] = None
                
                # Para todos os outros campos, manter o valor como está
                else:
                    processed_data[mapped_field] = value
            
            # Substituir o dicionário original pelo processado
            faturamento_data = processed_data
            
            print(f"Dados finais após processamento: {faturamento_data}")
            
            # Verificar se é uma atualização ou criação
            if isinstance(row_id, int) and row_id > 0:
                # Tentar atualizar registro existente
                try:
                    faturamento = Faturamento.objects.get(id=row_id)
                    print(f"Atualizando registro existente ID: {row_id}")
                    
                    # Atualizar registro existente campo por campo
                    for field, value in faturamento_data.items():
                        if hasattr(faturamento, field):
                            try:
                                setattr(faturamento, field, value)
                                print(f"Campo {field} atualizado para: {value}")
                            except Exception as field_error:
                                print(f"Erro ao atualizar campo {field}: {field_error}")
                                raise field_error
                    
                    faturamento.save()
                    print("Registro existente atualizado com sucesso!")
                    
                except Faturamento.DoesNotExist:
                    # Se não encontrou o registro, criar um novo
                    print(f"Registro ID {row_id} não encontrado, criando novo registro")
                    try:
                        faturamento = Faturamento.objects.create(**faturamento_data)
                        print("Novo registro criado com sucesso!")
                    except Exception as create_error:
                        print(f"Erro específico ao criar: {create_error}")
                        print(f"Dados finais: {faturamento_data}")
                        raise create_error
            else:
                # Criar novo registro (quando row_id é None, 0, ou string vazia)
                print(f"Criando novo registro sem ID com dados: {faturamento_data}")
                try:
                    faturamento = Faturamento.objects.create(**faturamento_data)
                    print("Novo registro criado com sucesso!")
                except Exception as create_error:
                    print(f"Erro específico ao criar: {create_error}")
                    print(f"Dados finais: {faturamento_data}")
                    raise create_error
            
            return JsonResponse({
                'success': True,
                'message': 'Registro salvo com sucesso',
                'id': faturamento.id
            })
            
        except Exception as e:
            print(f"Erro ao salvar faturamento: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class FaturamentoGetDataView(View):
    def get(self, request, *args, **kwargs):
        try:
            from django.db import connection
            
            # Configurar paginação
            page = request.GET.get('page', 1)
            per_page = request.GET.get('per_page', 50)  # 50 registros por página por padrão
            
            try:
                page = int(page)
                per_page = int(per_page)
            except (ValueError, TypeError):
                page = 1
                per_page = 50
            
            # Calcular offset
            offset = (page - 1) * per_page
            
            # Usar raw SQL para evitar problemas de conversão de decimal
            with connection.cursor() as cursor:
                # Obter filtros
                cliente_filter = request.GET.get('cliente', '').strip()
                comercial_filter = request.GET.get('comercial', '').strip()
                nome_fantasia_filter = request.GET.get('nome_fantasia', '').strip()
                sistema_omie_filter = request.GET.get('sistema_omie', '').strip()
                empresa_filter = request.GET.get('empresa', '').strip()
                email_filter = request.GET.get('email', '').strip()
                forma_pagamento_filter = request.GET.get('forma_pagamento', '').strip()
                data_inicio = request.GET.get('data_inicio', '').strip()
                data_fim = request.GET.get('data_fim', '').strip()
                tipo_data = request.GET.get('tipo_data', 'faturamento').strip()  # 'faturamento' ou 'emissao'
                
                # Construir condições WHERE
                where_conditions = []
                count_params = []
                
                if cliente_filter:
                    where_conditions.append("(cliente LIKE %s OR nome_fantasia LIKE %s)")
                    count_params.extend([f'%{cliente_filter}%', f'%{cliente_filter}%'])
                
                if comercial_filter:
                    where_conditions.append("comercial LIKE %s")
                    count_params.append(f'%{comercial_filter}%')
                
                if nome_fantasia_filter:
                    where_conditions.append("nome_fantasia LIKE %s")
                    count_params.append(f'%{nome_fantasia_filter}%')
                
                if sistema_omie_filter:
                    where_conditions.append("sistema_omie LIKE %s")
                    count_params.append(f'%{sistema_omie_filter}%')
                
                if empresa_filter:
                    where_conditions.append("empresa LIKE %s")
                    count_params.append(f'%{empresa_filter}%')
                
                if email_filter:
                    where_conditions.append("email LIKE %s")
                    count_params.append(f'%{email_filter}%')
                
                if forma_pagamento_filter:
                    where_conditions.append("forma_pagamento LIKE %s")
                    count_params.append(f'%{forma_pagamento_filter}%')
                
                # Filtro de data
                if data_inicio and data_fim:
                    if tipo_data == 'emissao':
                        where_conditions.append("emissao BETWEEN %s AND %s")
                    else:  # faturamento
                        where_conditions.append("faturamento BETWEEN %s AND %s")
                    count_params.extend([data_inicio, data_fim])
                
                # Obter parâmetro de ordenação
                ordenacao = request.GET.get('ordenacao', 'faturamento_desc').strip()
                
                # Contar total de registros com filtros
                count_query = "SELECT COUNT(*) FROM faturamento_faturamento"
                if where_conditions:
                    count_query += " WHERE " + " AND ".join(where_conditions)
                
                cursor.execute(count_query, count_params)
                total_count = cursor.fetchone()[0]
                
                                # Calcular total de páginas
                total_pages = (total_count + per_page - 1) // per_page
                
                # Construir a query base
                base_query = """
                    SELECT id, faturamento, emissao, reajustado, reajuste, contrato, tempo, 
                           comercial, n_contrato, sistema_omie, empresa, cliente, nome_fantasia, 
                           email, tipo_servico, descricao, forma_pagamento, vecimento_documento as vecimento, 
                           tipo_documento as documento, valor_bruto, coluna1, valor_liquido, juros, data_pgto, 
                           valor_pago, status2, situacao
                    FROM faturamento_faturamento 
                """
                
                # Construir condições WHERE para a query principal
                where_conditions = []
                params = []
                
                if cliente_filter:
                    where_conditions.append("(cliente LIKE %s OR nome_fantasia LIKE %s)")
                    params.extend([f'%{cliente_filter}%', f'%{cliente_filter}%'])
                
                if comercial_filter:
                    where_conditions.append("comercial LIKE %s")
                    params.append(f'%{comercial_filter}%')
                
                if nome_fantasia_filter:
                    where_conditions.append("nome_fantasia LIKE %s")
                    params.append(f'%{nome_fantasia_filter}%')
                
                if sistema_omie_filter:
                    where_conditions.append("sistema_omie LIKE %s")
                    params.append(f'%{sistema_omie_filter}%')
                
                if empresa_filter:
                    where_conditions.append("empresa LIKE %s")
                    params.append(f'%{empresa_filter}%')
                
                if email_filter:
                    where_conditions.append("email LIKE %s")
                    params.append(f'%{email_filter}%')
                
                if forma_pagamento_filter:
                    where_conditions.append("forma_pagamento LIKE %s")
                    params.append(f'%{forma_pagamento_filter}%')
                
                # Filtro de data
                if data_inicio and data_fim:
                    if tipo_data == 'emissao':
                        where_conditions.append("emissao BETWEEN %s AND %s")
                    else:  # faturamento
                        where_conditions.append("faturamento BETWEEN %s AND %s")
                    params.extend([data_inicio, data_fim])
                
                # Query final com ordenação e paginação
                where_clause = ""
                if where_conditions:
                    where_clause = " WHERE " + " AND ".join(where_conditions)
                
                # Definir ordenação baseada no parâmetro
                order_clause = "ORDER BY faturamento DESC, id DESC"  # Padrão
                
                if ordenacao == 'faturamento_desc':
                    order_clause = "ORDER BY faturamento DESC, id DESC"
                elif ordenacao == 'faturamento_asc':
                    order_clause = "ORDER BY faturamento ASC, id ASC"
                elif ordenacao == 'emissao_desc':
                    order_clause = "ORDER BY emissao DESC, id DESC"
                elif ordenacao == 'emissao_asc':
                    order_clause = "ORDER BY emissao ASC, id ASC"
                elif ordenacao == 'cliente_asc':
                    order_clause = "ORDER BY cliente ASC, id ASC"
                elif ordenacao == 'cliente_desc':
                    order_clause = "ORDER BY cliente DESC, id DESC"
                elif ordenacao == 'valor_desc':
                    order_clause = "ORDER BY valor_bruto DESC, id DESC"
                elif ordenacao == 'valor_asc':
                    order_clause = "ORDER BY valor_bruto ASC, id ASC"
                elif ordenacao == 'id_desc':
                    order_clause = "ORDER BY id DESC"
                elif ordenacao == 'id_asc':
                    order_clause = "ORDER BY id ASC"
                
                final_query = base_query + where_clause + " " + order_clause + " LIMIT %s OFFSET %s"
                params.extend([per_page, offset])
                
                # Executar query com filtros
                cursor.execute(final_query, params)
                
                faturamentos_raw = cursor.fetchall()
            
            data = []
            
            # Função auxiliar para converter valores decimais com segurança
            def safe_float(value):
                if value is None:
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
            
            # Função auxiliar para converter datas com segurança
            def safe_date(value):
                if value is None:
                    return None
                try:
                    return value.isoformat()
                except:
                    return None
            
            for faturamento_raw in faturamentos_raw:
                try:
                    faturamento_data = {
                        'id': faturamento_raw[0],
                        'faturamento': safe_date(faturamento_raw[1]),
                        'emissao': safe_date(faturamento_raw[2]),
                        'reajustado': faturamento_raw[3],
                        'reajuste': safe_date(faturamento_raw[4]),
                        'contrato': faturamento_raw[5],
                        'tempo': faturamento_raw[6],
                        'comercial': faturamento_raw[7],
                        'n_contrato': faturamento_raw[8],
                        'sistema_omie': faturamento_raw[9],
                        'empresa': faturamento_raw[10],
                        'cliente': faturamento_raw[11] if faturamento_raw[11] else '',
                        'cliente_id': None,  # Não temos mais ID do cliente
                        'nome_fantasia': faturamento_raw[12],
                        'email': faturamento_raw[13],
                        'tipo_servico': faturamento_raw[14],
                        'descricao': faturamento_raw[15],
                        'forma_pagamento': faturamento_raw[16],
                        'vecimento': safe_date(faturamento_raw[17]),
                        'documento': faturamento_raw[18],
                        'valor_bruto': safe_float(faturamento_raw[19]),
                        'coluna1': safe_float(faturamento_raw[20]),
                        'valor_liquido': safe_float(faturamento_raw[21]),
                        'juros': safe_float(faturamento_raw[22]),
                        'data_pgto': safe_date(faturamento_raw[23]),
                        'valor_pago': safe_float(faturamento_raw[24]),
                        'status2': faturamento_raw[25],
                        'situacao': faturamento_raw[26],
                    }
                    data.append(faturamento_data)
                except Exception as e:
                    # Se houver erro ao processar um registro, pular para o próximo
                    continue
            
            return JsonResponse({
                'success': True,
                'faturamentos': data,
                'pagination': {
                    'current_page': page,
                    'total_pages': total_pages,
                    'total_records': total_count,
                    'has_previous': page > 1,
                    'has_next': page < total_pages,
                    'previous_page_number': page - 1 if page > 1 else None,
                    'next_page_number': page + 1 if page < total_pages else None,
                    'per_page': per_page
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class FaturamentoGetClientesView(View):
    def get(self, request, *args, **kwargs):
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Buscar todos os clientes únicos
                cursor.execute("""
                    SELECT DISTINCT cliente 
                    FROM faturamento_faturamento 
                    WHERE cliente IS NOT NULL 
                    AND cliente != '' 
                    AND cliente != 'cliente'
                    ORDER BY cliente
                """)
                
                clientes = [row[0] for row in cursor.fetchall()]
                
                return JsonResponse({
                    'success': True,
                    'clientes': clientes
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class FaturamentoGetComerciaisView(View):
    def get(self, request, *args, **kwargs):
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Buscar todos os comerciais únicos
                cursor.execute("""
                    SELECT DISTINCT comercial 
                    FROM faturamento_faturamento 
                    WHERE comercial IS NOT NULL 
                    AND comercial != '' 
                    AND comercial != 'comercial'
                    ORDER BY comercial
                """)
                
                comerciais = [row[0] for row in cursor.fetchall()]
                
                return JsonResponse({
                    'success': True,
                    'comerciais': comerciais
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class FaturamentoGetNomesFantasiaView(View):
    def get(self, request, *args, **kwargs):
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Buscar todos os nomes fantasia únicos
                cursor.execute("""
                    SELECT DISTINCT nome_fantasia 
                    FROM faturamento_faturamento 
                    WHERE nome_fantasia IS NOT NULL 
                    AND nome_fantasia != '' 
                    AND nome_fantasia != 'nome_fantasia'
                    ORDER BY nome_fantasia
                """)
                
                nomes_fantasia = [row[0] for row in cursor.fetchall()]
                
                return JsonResponse({
                    'success': True,
                    'nomes_fantasia': nomes_fantasia
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class FaturamentoGetSistemasOmieView(View):
    def get(self, request, *args, **kwargs):
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Buscar todos os sistemas omie únicos
                cursor.execute("""
                    SELECT DISTINCT sistema_omie 
                    FROM faturamento_faturamento 
                    WHERE sistema_omie IS NOT NULL 
                    AND sistema_omie != '' 
                    AND sistema_omie != 'sistema_omie'
                    ORDER BY sistema_omie
                """)
                
                sistemas_omie = [row[0] for row in cursor.fetchall()]
                
                return JsonResponse({
                    'success': True,
                    'sistemas_omie': sistemas_omie
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class FaturamentoGetEmpresasView(View):
    def get(self, request, *args, **kwargs):
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Buscar todas as empresas únicas
                cursor.execute("""
                    SELECT DISTINCT empresa 
                    FROM faturamento_faturamento 
                    WHERE empresa IS NOT NULL 
                    AND empresa != '' 
                    AND empresa != 'empresa'
                    ORDER BY empresa
                """)
                
                empresas = [row[0] for row in cursor.fetchall()]
                
                return JsonResponse({
                    'success': True,
                    'empresas': empresas
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class FaturamentoGetEmailsView(View):
    def get(self, request, *args, **kwargs):
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Buscar todos os emails únicos
                cursor.execute("""
                    SELECT DISTINCT email 
                    FROM faturamento_faturamento 
                    WHERE email IS NOT NULL 
                    AND email != '' 
                    AND email != 'email'
                    ORDER BY email
                """)
                
                emails = [row[0] for row in cursor.fetchall()]
                
                return JsonResponse({
                    'success': True,
                    'emails': emails
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class FaturamentoGetFormasPagamentoView(View):
    def get(self, request, *args, **kwargs):
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Buscar todas as formas de pagamento únicas
                cursor.execute("""
                    SELECT DISTINCT forma_pagamento 
                    FROM faturamento_faturamento 
                    WHERE forma_pagamento IS NOT NULL 
                    AND forma_pagamento != '' 
                    AND forma_pagamento != 'forma_pagamento'
                    ORDER BY forma_pagamento
                """)
                
                formas_pagamento = [row[0] for row in cursor.fetchall()]
                
                return JsonResponse({
                    'success': True,
                    'formas_pagamento': formas_pagamento
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class FaturamentoDeleteView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            row_id = data.get('row_id')
            
            if row_id:
                try:
                    faturamento = Faturamento.objects.get(id=row_id)
                    faturamento.delete()
                    return JsonResponse({
                        'success': True,
                        'message': 'Registro deletado com sucesso'
                    })
                except Faturamento.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Registro não encontrado'
                    }, status=404)
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'ID do registro não fornecido'
                }, status=400)
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400) 

@method_decorator(csrf_exempt, name='dispatch')
class FaturamentoGetNextIdView(View):
    def get(self, request, *args, **kwargs):
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Obter o próximo ID disponível
                cursor.execute("""
                    SELECT COALESCE(MAX(id), 0) + 1 as next_id
                    FROM faturamento_faturamento
                """)
                
                result = cursor.fetchone()
                next_id = result[0] if result else 1
                
                return JsonResponse({
                    'success': True,
                    'next_id': next_id
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch') 
class FaturamentoGetMultipleIdsView(View):
    def get(self, request, *args, **kwargs):
        try:
            count = int(request.GET.get('count', 1))
            if count < 1 or count > 100:
                return JsonResponse({
                    'success': False,
                    'error': 'Quantidade deve ser entre 1 e 100'
                }, status=400)
            
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Obter o maior ID atual
                cursor.execute("SELECT COALESCE(MAX(id), 0) FROM faturamento_faturamento")
                result = cursor.fetchone()
                max_id = result[0] if result else 0
                
                # Gerar IDs sequenciais a partir do próximo disponível
                ids = []
                for i in range(1, count + 1):
                    ids.append(max_id + i)
                
                return JsonResponse({
                    'success': True,
                    'ids': ids
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400) 