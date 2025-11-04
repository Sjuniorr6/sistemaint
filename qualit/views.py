from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView
from django.urls import reverse_lazy
from .models import Qualit
from .forms import QualitForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from requisicao.models import Requisicoes
from django.http import HttpResponse
from io import BytesIO
import pandas as pd
from django.db.models import Q

class QualitCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = Qualit
    form_class = QualitForm
    template_name = 'criar_qualit.html'
    success_url = reverse_lazy('criar_qualit')
    permission_required = 'qualit.add_qualit'  # Substitua 'qualit' pelo nome do seu aplicativo

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        return super().form_valid(form)

    def form_invalid(self, form):
        print(form.errors)  # Adicione esta linha para imprimir os erros do formulário
        return super().form_invalid(form)

class QualitListView(LoginRequiredMixin, ListView):
    model = Requisicoes
    template_name = 'listar_qualits.html'
    context_object_name = 'qualits'
    # permission_required = 'requisicao.view_requisicoes'  # Comentado temporariamente para teste

    def get_queryset(self):
        queryset = super().get_queryset()

        # Recupera os parâmetros da URL
        ID = self.request.GET.get('ID')
        ICCID_NOVO = self.request.GET.get('ICCID_NOVO')
        CLIENTE = self.request.GET.get('CLIENTE')

        # Filtros dinâmicos para o modelo Requisicoes
        if ID or ICCID_NOVO or CLIENTE:
            filters = Q()
            if ID:
                # Buscar no campo id_equipamentos
                filters &= Q(id_equipamentos__icontains=ID.strip())
            if ICCID_NOVO:
                # Buscar no campo iccid
                filters &= Q(iccid__icontains=ICCID_NOVO.strip())
            if CLIENTE:
                # Buscar no nome do cliente
                filters &= Q(nome__nome__icontains=CLIENTE.strip())
            
            queryset = queryset.filter(filters)
        else:
            # Retorna todos os registros se nenhum parâmetro for passado
            queryset = queryset.all()

        return queryset

@login_required
def exportar_qualits_excel(request):
    """Exporta os dados filtrados para Excel"""
    # Recupera os parâmetros da URL (mesmos filtros da listagem)
    ID = request.GET.get('ID')
    ICCID_NOVO = request.GET.get('ICCID_NOVO')
    CLIENTE = request.GET.get('CLIENTE')
    
    # Aplica os mesmos filtros da listagem
    queryset = Requisicoes.objects.all()
    
    if ID or ICCID_NOVO or CLIENTE:
        filters = Q()
        if ID:
            filters &= Q(id_equipamentos__icontains=ID.strip())
        if ICCID_NOVO:
            filters &= Q(iccid__icontains=ICCID_NOVO.strip())
        if CLIENTE:
            filters &= Q(nome__nome__icontains=CLIENTE.strip())
        queryset = queryset.filter(filters)
    
    # Prepara os dados para o Excel
    data = []
    for qualit in queryset:
        # Dados base que serão repetidos para cada equipamento
        base_data = {
            'ID Requisição': qualit.id,
            'Cliente': qualit.nome.nome if qualit.nome else 'N/A',
            'Contrato': qualit.contrato if qualit.contrato else 'N/A',
            'Comercial': qualit.comercial if qualit.comercial else 'N/A',
            'Status': qualit.status if qualit.status else 'N/A',
            'Data Alteração': qualit.data_alteracao.strftime('%d/%m/%Y %H:%M') if qualit.data_alteracao else 'N/A',
            'Endereço': qualit.endereco if qualit.endereco else 'N/A',
            'CNPJ': qualit.cnpj if qualit.cnpj else 'N/A',
            'Nº Equipamentos': qualit.numero_de_equipamentos if qualit.numero_de_equipamentos else 'N/A',
            'Data': qualit.data.strftime('%d/%m/%Y %H:%M') if qualit.data else 'N/A',
            'Data Entrega': qualit.data_entrega.strftime('%d/%m/%Y') if qualit.data_entrega else 'N/A',
        }
        
        # Separa os IDs e ICCIDs por espaços (como no código existente)
        ids = []
        iccids = []
        
        if qualit.id_equipamentos:
            ids = [id.strip() for id in qualit.id_equipamentos.split() if id.strip()]
        
        if qualit.iccid:
            iccids = [iccid_val.strip() for iccid_val in qualit.iccid.split() if iccid_val.strip()]
        
        # Determina o número máximo de linhas (maior entre IDs e ICCIDs)
        max_lines = max(len(ids), len(iccids)) if (ids or iccids) else 1
        
        # Se não houver IDs nem ICCIDs, cria uma linha com N/A
        if max_lines == 0:
            row = base_data.copy()
            row['ID Equipamentos'] = 'N/A'
            row['ICCID'] = 'N/A'
            data.append(row)
        else:
            # Cria uma linha para cada equipamento
            for i in range(max_lines):
                row = base_data.copy()
                row['ID Equipamentos'] = ids[i] if i < len(ids) else 'N/A'
                row['ICCID'] = iccids[i] if i < len(iccids) else 'N/A'
                data.append(row)
    
    # Cria o DataFrame
    df = pd.DataFrame(data)
    
    # Cria o arquivo Excel em memória
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    
    # Cria a resposta HTTP
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="qualits_export.xlsx"'
    
    return response
