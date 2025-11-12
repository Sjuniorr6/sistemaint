from typing import Any
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from . import models, forms
from .forms  import EstoqueantenistarForm
from django.urls import reverse_lazy
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from registrodemanutencao.models import registrodemanutencao
from requisicao.models import Requisicoes,estoque_antenista
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from django.db.models import Q
from django.conf import settings


from registrodemanutencao.forms import FormulariosUpdateForm
from django.core.mail import send_mail
from django.contrib.auth.mixins import PermissionRequiredMixin,LoginRequiredMixin

from django.shortcuts import render, redirect
from django.forms import inlineformset_factory

from .forms import ControleForm
#------------------------------------------------------
class RequisicoesViews(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = Requisicoes
    template_name = "requisicoes.html"
    context_object_name = 'requisicoes'
    paginate_by = 12
    permission_required = "requisicao.view_requisicoes"
    
    def get_queryset(self):
        return Requisicoes.objects.filter(status__in=['Pendente'])
    


from django.http import JsonResponse
from .models import Clientes


def get_cliente_data(request, cliente_id):
    cliente = Clientes.objects.get(id=cliente_id)
    data = {
        'cnpj': cliente.cnpj,
        'inicio_de_contrato': cliente.inicio_de_contrato,
        'vigencia': cliente.vigencia,
        'contrato': cliente.tipo_contrato,
       
    }
    return JsonResponse(data) 
import logging
from django.contrib import messages
from django.db import transaction
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from .models import Requisicoes, estoque_antenista
from .forms import RequisicaoForm

logger = logging.getLogger(__name__)
class RequisicaoCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = Requisicoes
    template_name = 'requisicao_create.html'
    form_class = RequisicaoForm
    success_url = reverse_lazy('requisicoes')
    permission_required = "requisicao.add_requisicoes"

    def get_queryset(self):
        return Requisicoes.objects.all().order_by('id')

    def form_valid(self, form):
        motivo = form.cleaned_data.get('motivo')
        antenista = form.cleaned_data.get('antenista')
        tipo_produto = form.cleaned_data.get('tipo_produto')
        numero_de_equipamentos = form.cleaned_data.get('numero_de_equipamentos')

        logger.info("Formulário válido: %s", form.is_valid())
        logger.info("Dados do formulário: %s", form.cleaned_data)

        if motivo in ['Isca FAST', 'Estoque Antenista'] and antenista and tipo_produto and numero_de_equipamentos:
            try:
                with transaction.atomic():
                    requisicao = form.save(commit=False)
                    quantidade_requisitada = int(numero_de_equipamentos)
                    antenista_estoque, created = estoque_antenista.objects.get_or_create(
                        nome=antenista, 
                        tipo_produto=tipo_produto, 
                        defaults={'quantidade': 0}
                    )
                    
                    if antenista_estoque.quantidade is None:
                        antenista_estoque.quantidade = 0

                    if motivo == 'Isca FAST':
                        if antenista_estoque.quantidade >= quantidade_requisitada:
                            antenista_estoque.quantidade -= quantidade_requisitada
                        else:
                            messages.error(self.request, f"O antenista {antenista} não tem quantidade suficiente no estoque para o produto {tipo_produto}. Quantidade disponível: {antenista_estoque.quantidade}, quantidade requisitada: {quantidade_requisitada}.")
                            return self.form_invalid(form)
                    elif motivo == 'Estoque Antenista':
                        antenista_estoque.quantidade += quantidade_requisitada
                    
                    antenista_estoque.save()
                    requisicao.save()
                    return super().form_valid(form)
            except Exception as e:
                logger.error("Erro ao processar a requisição: %s", e)
                messages.error(self.request, "Ocorreu um erro ao processar a requisição.")
                return self.form_invalid(form)
        else:
            return super().form_valid(form)
    

    
class RequisicaoDetailView(PermissionRequiredMixin,LoginRequiredMixin,DetailView):
    model = models.Requisicoes
    template_name = 'requisicao_detail.html'
    permission_required="requisicao.view_requisicoes"


class RequisicaoUpdateView(PermissionRequiredMixin,LoginRequiredMixin,UpdateView):
    model = Requisicoes
    form_class = forms.RequisicaoForm
    template_name = 'requisicao_update.html'
    context_object_name = 'requisicao'
    success_url = reverse_lazy('requisicao_list')
    permission_required="requisicao.change_requisicoes"
class Requisicao2UpdateView(PermissionRequiredMixin,LoginRequiredMixin,UpdateView):
    model = Requisicoes
    form_class = forms.RequisicaoForm
    template_name = 'requisicao_update.html'
    context_object_name = 'requisicao'
    success_url = reverse_lazy('requisicao_list')
    permission_required="requisicao.change_requisicoes"

  

class requisicoesDeleteView(PermissionRequiredMixin,LoginRequiredMixin,DeleteView):
    model = Requisicoes
    template_name = "requisicao_delete.html"
    success_url = reverse_lazy('expedicaoListViews')
    permission_required = "requisicao.delete_requisicoes"

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.delete()
        return HttpResponseRedirect(success_url)
#------------------------------------------------------

#------------------------------------------------------
class configuracaodeleteview(PermissionRequiredMixin,LoginRequiredMixin,DeleteView):
    model = models.Requisicoes
    template_name = 'configuracao_delete.html'
    success_url = reverse_lazy('acompanhamento_requisicao')
    permission_required="requisicao.delete_requisicoes"

from django.forms import modelformset_factory
from .models import  ControleModel


class ControleModel(PermissionRequiredMixin, LoginRequiredMixin, CreateView):

    model = ControleModel
    form_class = ControleForm
    template_name = 't42_form.html'
    success_url = reverse_lazy('t42_view')
    permission_required = 't42.add_t42model'

    def form_valid(self, form):
        response = super().form_valid(form)
        total_forms = int(self.request.POST.get('total_forms', 0))

        for i in range(total_forms):
            id_equipamento = self.request.POST.get(f'id_equipamento-{i}-id_equipamento')
            iccid_equipamento = self.request.POST.get(f'iccid_equipamento-{i}-iccid_equipamento')
           
            if id_equipamento and iccid_equipamento :
                ControleModel.objects.create(
                    nome=self.object.nome,
                    id_equipamento=id_equipamento,
                    iccid_equipamento=iccid_equipamento,
                   
                )

        return response

from django.views.generic import CreateView, ListView
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.urls import reverse_lazy
from .models import ControleModel
from .forms import ControleForm

class ControleCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = ControleModel
    template_name = 'controle.html'
    form_class = ControleForm
    success_url = reverse_lazy('controleList')
    permission_required = "requisicao.view_requisicoes"

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        return super().form_valid(form)


class ControleListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = ControleModel
    template_name = 'controle_list.html'
    context_object_name = 'controles'
    permission_required = "requisicao.view_requisicoes"






class ConfiguracaoListView(PermissionRequiredMixin,LoginRequiredMixin,ListView):
    template_name = 'configuracao_list.html'
    context_object_name = 'equipamentos'
    permission_required= "requisicao.view_requisicoes"
    
    
    def get_queryset(self):
        # Obter parâmetro de filtro por ID
        id_filtro = self.request.GET.get('id_filtro')
        
        requisicoes_queryset = Requisicoes.objects.filter(status__in=['Aprovado pelo CEO']).exclude(tipo_produto__nome__in=['GS310','GS340','GS390','GS8310 (4G)','PLUG AND PLAY'])
        manutencao_queryset = registrodemanutencao.objects.filter(status__in=['Aprovado Inteligência', 'Aprovado pela Diretoria', 'Aprovado pelo CEO']).exclude(tipo_produto__nome__in=['GS310','GS340','GS390','GS8310 (4G)','PLUG AND PLAY'])
        
        # Aplicar filtro por ID se fornecido
        if id_filtro:
            try:
                id_valor = int(id_filtro)
                requisicoes_queryset = requisicoes_queryset.filter(id=id_valor)
                manutencao_queryset = manutencao_queryset.filter(id=id_valor)
            except ValueError:
                # Se o ID não for um número válido, retornar queryset vazio
                return []
        
        # Combine os querysets
        combined_queryset = list(requisicoes_queryset) + list(manutencao_queryset)
        
        return combined_queryset


class ConfiguracaoUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Requisicoes
    form_class = forms.requisicaoFormup
    template_name = 'configuracao_update.html'
    context_object_name = 'equipamento'
    success_url = reverse_lazy('ConfiguracaoListView')
    permission_required = "requisicao.change_requisicoes"

class ConfiguracaoUpdateView2(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = registrodemanutencao
    form_class = FormulariosUpdateForm
    template_name = 'configuracao_update.html'
    context_object_name = 'equipamento'
    success_url = reverse_lazy('ConfiguracaoListView')
    permission_required = "requisicao.change_requisicoes"
  

 #------------------------------------------------------   


class tecnicoListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    template_name = 'setor_tecnico.html'
    context_object_name = 'equipamentos'
    permission_required = "requisicao.view_requisicoes"
    
    def get_queryset(self):
        valores_tipo_produto = ['GS310', 'GS340', 'GS390', 'GS8310 (4G)','PLUG AND PLAY']
        requisicao_queryset = Requisicoes.objects.filter(tipo_produto__nome__in=valores_tipo_produto)
        return requisicao_queryset


class tecnicoUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Requisicoes
    form_class = forms.requisicaoFormup
    template_name = 'setor_tecnico_update.html'
    context_object_name = 'equipamento'
    success_url = reverse_lazy('tecnicoListView')
    permission_required = "requisicao.change_requisicoes"

    def form_valid(self, form):
        # Salvar o formulário primeiro
        response = super().form_valid(form)
        
        # Obter os valores dos campos
        id_equipamentos = form.cleaned_data.get('id_equipamentos', '')
        iccid = form.cleaned_data.get('iccid', '')
        
        if id_equipamentos and iccid:
            try:
                # Separar os valores por espaços (qualquer quantidade de espaços)
                ids = [id.strip() for id in id_equipamentos.split() if id.strip()]
                iccids = [iccid_val.strip() for iccid_val in iccid.split() if iccid_val.strip()]
                
                # Vincular os valores correspondentes
                for i, (equip_id, iccid_val) in enumerate(zip(ids, iccids), 1):
                    if i <= 10:  # Limite de 10 equipamentos conforme o modelo
                        field_name = f'iccid_equipamento{i}'
                        if hasattr(self.object, field_name):
                            setattr(self.object, field_name, iccid_val)
                
                # Salvar as alterações
                self.object.save()
                
                # Log de sucesso
                print(f"Vinculação automática realizada: {len(ids)} equipamentos vinculados com ICCIDs")
                
            except Exception as e:
                print(f"Erro ao vincular equipamentos com ICCIDs: {e}")
        
        return response


#------------------------------------------------------



from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView
from .models import Requisicoes  # Certifique-se de que o modelo Requisicoes está importado

class ceoListViews(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = Requisicoes
    template_name = "ceo_list.html"
    context_object_name = 'ceo_list'
    paginate_by = 10
    permission_required = "requisicao.view_requisicoes"

    def get_queryset(self):
        return Requisicoes.objects.filter(status__in=['Pendente', 'Aprovado pela Diretoria'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_pendente'] = Requisicoes.objects.filter(status='Pendente').count()
        context['total_aprovado_ceo'] = Requisicoes.objects.filter(status='Aprovado pelo CEO').count()
        context['total_configurado'] = Requisicoes.objects.filter(status='Configurado').count()
        
        # Verificando requisições que não foram alteradas nas últimas 24 horas, excluindo 'Enviado para o Cliente'
        threshold_time = timezone.now() - timedelta(hours=24)
        context['requisições_sem_alteracao'] = Requisicoes.objects.filter(
            data_alteracao__lt=threshold_time
        ).exclude(status='Enviado para o Cliente')
        
        # Contando requisições sem alteração
        context['count_requisicoes_sem_alteracao'] = context['requisições_sem_alteracao'].count()
        
        # Verificando requisições com data_entrega a menos de 48 horas
        threshold_delivery_time = timezone.now() + timedelta(hours=48)
        context['requisições_proximas_entrega'] = Requisicoes.objects.filter(
            data_entrega__lte=threshold_delivery_time
        )

        # Contando requisições próximas da entrega
        context['count_requisicoes_proximas_entrega'] = context['requisições_proximas_entrega'].count()
        
        # Adicionando dias restantes até a entrega
        for item in context['ceo_list']:
            if item.data_entrega:
                dias_restantes = (item.data_entrega - timezone.now().date()).days
                item.dias_restantes = dias_restantes  # Armazena a contagem de dias restantes no objeto
                item.dias_restantes_inclusivo = dias_restantes + 1  # Adiciona 1 e armazena

        return context
class ceodetailview(PermissionRequiredMixin,LoginRequiredMixin,DetailView):
    model = Requisicoes
    template_name = 'ceo_detail.html'
    permission_required="requisicao.view_requisicoes"


class CeoEntradaDetailView(PermissionRequiredMixin,LoginRequiredMixin,DetailView):
    model = registrodemanutencao
    template_name = 'ceo_detalheentrada.html'
    context_object_name = 'manutencoes'
    permission_required="requisicao.view_requisicoes"
#------------------------------------------------------


#------------------------------------------------------


class diretoriaListViews(PermissionRequiredMixin,LoginRequiredMixin,ListView):
    template_name = "diretoria_list.html"
    context_object_name = 'diretoria_list'
    permission_required="requisicao.view_requisicoes"
    
    def get_queryset(self):
        requisicoes_queryset = Requisicoes.objects.filter(status__in=['', ''])
        manutencao_queryset = registrodemanutencao.objects.filter(status='Manutenção')
        
        # Combine os querysets
        combined_queryset = list(requisicoes_queryset) + list(manutencao_queryset)
        
        return combined_queryset
#------------------------------------------------------


from django.views.generic import ListView
from formacompanhamento.models import Formacompanhamento  # Substitua 'Financeiro' pelo nome do seu modelo

class FinanceiroListViews(ListView):
    template_name = "financeiro_list.html"  # Substitua pelo nome do seu template
    context_object_name = 'financeiro_list'
    paginate_by = 10

    def get_queryset(self):
        return Formacompanhamento.objects.all()  # Defina o queryset aqui
    









#------------------------------------------------------
class expedicaoListViews(PermissionRequiredMixin,LoginRequiredMixin,ListView):
    model = Requisicoes
    template_name = "expedicao_list.html"
    context_object_name = 'expedicao_list'
    permission_required="requisicao.view_requisicoes"
    
    def get_queryset(self):
        nome = self.request.GET.get('nome')
        
        # Primeiro, busca as requisições
        requisicoes_queryset = Requisicoes.objects.filter(status__in=['Configurado'])
        if nome:
            requisicoes_queryset = requisicoes_queryset.filter(nome__nome__icontains=nome)
        
        # Depois, busca as manutenções
        manutencao_queryset = registrodemanutencao.objects.filter(status__in=['Configurado'])
        if nome:
            manutencao_queryset = manutencao_queryset.filter(nome__nome__icontains=nome)
        
        # Combina os querysets
        combined_queryset = list(requisicoes_queryset) + list(manutencao_queryset)
        
        return combined_queryset
#------------------------------------------------------
#------------------------------------------------------
class historicoListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = Requisicoes
    template_name = "historico_list.html"
    context_object_name = 'historico_list'
    paginate_by = 12
    permission_required = "requisicao.view_requisicoes"
    
    def get_queryset(self):
        queryset = Requisicoes.objects.all().order_by('-id')
        nome = self.request.GET.get('nome')
        status = self.request.GET.get('status')
        id_filtro = self.request.GET.get('id_filtro')

        if nome:
            queryset = queryset.filter(nome__nome__icontains=nome)

        if status:
            queryset = queryset.filter(status__icontains=status)
            
        if id_filtro:
            try:
                id_valor = int(id_filtro)
                queryset = queryset.filter(id=id_valor)
            except ValueError:
                # Se o ID não for um número válido, retornar queryset vazio
                return Requisicoes.objects.none()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Preserva os parâmetros GET para a paginação
        context['nome_filter'] = self.request.GET.get('nome', '')
        context['status_filter'] = self.request.GET.get('status', '')
        return context

#------------------------------------------------------
#------------------------------------------------------





#------------------------------------------------------
def aprovar_requisicao(request, id):
    registro = get_object_or_404(Requisicoes, id=id)
    registro.status = 'Aprovado pela Diretoria'
    registro.save()
    return redirect('#')

def reprovar_requisicao(request, id):
    registro = get_object_or_404(Requisicoes, id=id)
    registro.status = 'Reprovado pela Diretoria'
    registro.save()
    return redirect('#')
#------------------------------------------------------

def aprovar_FINANCEIRO(request, id):
    registro = get_object_or_404(Formacompanhamento, id=id)
    registro.status = 'PAGO'
    registro.save()
    return redirect('FinanceiroListViews')





#------------------------------------------------------
def reprovar_ceo(request, id):
    registro = get_object_or_404(Requisicoes, id=id)
    registro.status = 'Reprovado pelo CEO'
    registro.save()
    
    return redirect('ceoListViews')


def aprovar_ceo(request, id):
    registro = get_object_or_404(Requisicoes, id=id)
    registro.status = 'Aprovado pelo CEO'
    registro.save()
    subject = f"Requisicao Aprovada: {registro.id}"
    message = f"A manutenção {registro.id} foi aprovada com sucesso. {registro.nome} Status: {registro.status} criar Requisição"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = ['sjuniorr6@gmail.com']
    
    try:
        send_mail(subject, message, from_email, recipient_list)
        print("Email enviado com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
    
    

    return redirect('ceoListViews')
    
    
#------------------------------------------------------


#------------------------------------------------------
from django.http import HttpResponse
def configurado_expedicao(request, id):
    registro = get_object_or_404(Requisicoes, id=id)
    registro.status = 'Configurado'
    registro.save()
    return redirect('ConfiguracaoListView')

def expedicao_expedido(request, id):
    registro = get_object_or_404(Requisicoes, id=id)
    registro.status = 'Enviado para o Cliente'
    registro.save()
    return redirect('expedicaoListViews')

def expedicao_expedido2(request, id):
    registro = get_object_or_404(registrodemanutencao, id=id)
    registro.status = 'Enviado para o Cliente'
    registro.save()
    return redirect('expedicaoListViews')


def expedir_requisicao(request, id):
    registro = get_object_or_404(Requisicoes, id=id)
    # Alterar o status do registro para "Configurado"
    registro.status = 'Configurado'
    registro.save()
    subject = f"Requisicao Expedida: ID:  {registro.id} "
    message = f"Requisição realizada e expedida com sucesso. ID:  {registro.id} Quality, por favor realizar a auditoria de espelhamento. Atenciosamente, Departamento de Inteligência"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = ['gerencia@grupogoldensat.com.br','supervisao@grupogoldensat.com.br','coordenacao.plantao@grupogoldensat.com.br','quality@grupogoldensat.com.br','sjuniorr6@Gmail.com']
    
    
    try:
        send_mail(subject, message, from_email, recipient_list)
        print("Email enviado com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
    return redirect('ConfiguracaoListView')
def expedir_requisicaotec(request, id):
    registro = get_object_or_404(Requisicoes, id=id)
    # Alterar o status do registro para "Configurado"
    registro.status = 'Configurado'
    registro.save()
    return redirect('tecnicoListView')

def expedir_manutencao(request, id):
    registro = get_object_or_404(registrodemanutencao, id=id)
    # Alterar o status do registro para "Configurado"
    registro.status = 'Configurado'
    registro.save()
    return redirect('ConfiguracaoListView')






def configurado_manutencao(request, id):
    registro = get_object_or_404(registrodemanutencao, id=id)
    registro.status = 'Configurado'
    registro.save()
    return redirect('ConfiguracaoListView')


def expedicao_expedido_manutencao(request, id):
    registro = get_object_or_404(registrodemanutencao, id=id)
    registro.status = 'Enviado para o Cliente'
    registro.save()
    return redirect('expedicaoListViews')


#------------------------------------------------------
# View para aprovar uma requisição pela diretoria
#------------------------------------------------------
def Reprovar_diretoria(request, id):
    registro = get_object_or_404(registrodemanutencao, id=id)
    registro.status = 'Reprovado pela Diretoria'
    registro.save()
    return redirect('diretoriaListViews')
   

# View para reprovar uma requisição pela diretoria
def Aprovar_diretoria(request, id):
    registro = get_object_or_404(registrodemanutencao, id=id)
    registro.status = 'Aprovado pela Diretoria'  # Corrigido para "Aprovado pela Diretoria"
    registro.save()

    subject = f"Manutenção Aprovada: {registro.id}"
    message = f"A manutenção {registro.id} foi aprovada com sucesso. {registro.nome} Status: {registro.status} criar Requisição"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = ['sjuniorr6@gmail.com']
    
    try:
        send_mail(subject, message, from_email, recipient_list)
        print("Email enviado com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
    
    

    return redirect('diretoriaListViews')


# protocolo de requisicao
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.flowables import Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import os

def gerar_pdf_requisicao(requisicao):
    # Caminho para salvar o PDF
    pdf_path = os.path.join(settings.MEDIA_ROOT, f'requisicao-{requisicao.id}.pdf')
    
    # Criar documento PDF com margem superior ajustada
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=20, bottomMargin=20, leftMargin=20, rightMargin=20)  # Ajuste de margens
    elements = []

    # Estilos
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    normal_style = styles["Normal"]

    # Caminho para a imagem do logo (ajuste o caminho conforme necessário)
    imagem_esquerda_path = os.path.join(settings.MEDIA_ROOT, 'imagens_registros/SIDNEISIDNEISIDNEI.png')

    # Criar a imagem do logo
    logo = Image(imagem_esquerda_path, width=100, height=100)  # Ajustar o tamanho do logo
    
    # Usar o estilo do título e ajustar a centralização
    title_paragraph = Paragraph("<b>Protocolo de Requisição</b>", title_style)
    title_paragraph.alignment = 1  # Alinhar o título ao centro

    # Adicionar logo e título em elementos
    elements.append(logo)
    elements.append(title_paragraph)
    elements.append(Spacer(1, 10))  # Reduzido o espaçamento após o título

    # Tabela com os dados
    table_data = [
        [Paragraph("<b>Nome:</b>", normal_style), requisicao.nome],
        [Paragraph("<b>Protocolo:</b>", normal_style), requisicao.id],
        [Paragraph("<b>Endereço:</b>", normal_style), Paragraph(requisicao.endereco, normal_style)],  # Usando Paragraph para quebra automática
        [Paragraph("<b>Contrato:</b>", normal_style), requisicao.contrato],
        [Paragraph("<b>CNPJ:</b>", normal_style), requisicao.cnpj],
        [Paragraph("<b>Data:</b>", normal_style), requisicao.data.strftime("%d/%m/%Y") if requisicao.data else "N/A"],
        [Paragraph("<b>Motivo:</b>", normal_style), requisicao.motivo],
        [Paragraph("<b>Taxa de Envio:</b>", normal_style), requisicao.taxa_envio],
        [Paragraph("<b>Comercial:</b>", normal_style), requisicao.comercial],
        [Paragraph("<b>Tipo de Produto:</b>", normal_style), requisicao.tipo_produto],
        [Paragraph("<b>Carregador:</b>", normal_style), requisicao.carregador],
        [Paragraph("<b>Cabo:</b>", normal_style), requisicao.cabo],
        [Paragraph("<b>TP:</b>", normal_style), requisicao.TP],
        [Paragraph("<b>Envio:</b>", normal_style), requisicao.envio],
        [Paragraph("<b>Quantidade:</b>", normal_style), requisicao.numero_de_equipamentos],
        [Paragraph("<b>Valor Unitário:</b>", normal_style), requisicao.valor_unitario],
        [Paragraph("<b>Customização:</b>", normal_style), requisicao.tipo_customizacao],
        [Paragraph("<b>Observações:</b>", normal_style), Paragraph(requisicao.observacoes, normal_style)],  # Usando Paragraph para quebra automática
    ]

    # Criar uma tabela com duas colunas
    table = Table(table_data, colWidths=[200, 300])  # Ajuste para as colunas
    table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                               ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                               ('FONTSIZE', (0, 0), (-1, -1), 8),  # Fonte ajustada
                               ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('TOPPADDING', (0, 0), (-1, -1), 5),  # Ajuste de padding superior
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 5),  # Ajuste de padding inferior
                               ('LEFTPADDING', (0, 0), (-1, -1), 5),  # Ajuste de padding lateral
                               ('RIGHTPADDING', (0, 0), (-1, -1), 5),  # Ajuste de padding lateral
                              ]))
    
# Adicionar a frase no final de forma destacada
    highlight_style = ParagraphStyle(
    name="HighlightedText",
    parent=styles["Normal"],
    fontSize=12,
    alignment=1,  # Centraliza o texto
    fontName="Helvetica-Bold",
    spaceBefore=2,  # Espaço antes da frase
    textColor=colors.red  # Cor vermelha para destacar
)

    highlight_paragraph = Paragraph("<b>NÃO ENVIAR ESSE PROTOCOLO AO CLIENTE</b>", highlight_style)
    elements.append(highlight_paragraph)  # Adiciona a frase ao PDF

# Adiciona um espaçamento final
    elements.append(Spacer(1, 20))

    elements.append(table)  # Adiciona a tabela ao PDF
    elements.append(Spacer(1, 20))  # Espaço após a tabela

    # Adicionar quebra de página caso o conteúdo ocupe mais de uma página
    elements.append(PageBreak())

    # Salvar PDF
    doc.build(elements)
    return pdf_path



# protocolo de saida
from django.shortcuts import get_object_or_404
from .models import Requisicoes
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import os
from django.conf import settings
from textwrap import wrap
from reportlab.pdfbase.pdfmetrics import stringWidth


# Função para truncar texto dinamicamente para caber no espaço
def truncate_text_to_fit(text, max_width, font_name="Helvetica", font_size=10):
    if not text:
        return "Não Informado"
    while stringWidth(text, font_name, font_size) > max_width:
        text = text[:-1]
    return text + "..." if len(text) > 3 else text


def wrap_text(text, max_length=40):
    if not text:
        return "Não Informado"
    return "\n".join(wrap(str(text), max_length))


from reportlab.lib.colors import HexColor

# protocolo de saida

import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
  # Substitua "your_app" pelo nome do seu app

def gerar_pdf_saida(request, id):
    requisicao = get_object_or_404(Requisicoes, id=id)

    # Configuração inicial do PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        bottomMargin=30 * mm
    )
    elements = []

    # Estilos de texto
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Header",
        fontSize=14,
        alignment=1,  # Centralizado
        spaceAfter=10,
        fontName="Helvetica-Bold"
    ))
    styles.add(ParagraphStyle(
        name="Body",
        fontSize=9,
        alignment=0,  # Alinhado à esquerda
        spaceAfter=6,
        fontName="Helvetica"
    ))
    styles.add(ParagraphStyle(
        name="Footer",
        fontSize=8,
        alignment=1,  # Centralizado
        spaceBefore=20,
        fontName="Helvetica"
    ))
    styles.add(ParagraphStyle(
        name="TableHeader",
        fontSize=9,
        alignment=0,
        fontName="Helvetica-Bold"
    ))
    styles.add(ParagraphStyle(
        name="TableBody",
        fontSize=9,
        alignment=0,
        fontName="Helvetica"
    ))

    # Define o tom de amarelo mais suave
    soft_yellow = HexColor("#FFFACD")

    # Cabeçalho com logotipo e QR Code
    try:
        logo_path = os.path.join(settings.MEDIA_ROOT, 'imagens_registros/SIDNEISIDNEISIDNEI.png')
        qr_code_path = os.path.join(settings.MEDIA_ROOT, 'imagens_registros/qrcode.png')

        logo = Image(logo_path, width=60, height=60)
        qr_code = Image(qr_code_path, width=60, height=60)

        header_table = Table([
            [
                logo,
                Paragraph("<b>PROTOCOLO DE ENTREGA DE EQUIPAMENTOS</b>", styles["Header"]),
                qr_code
            ]
        ], colWidths=[80 * mm, 330 * mm, 80 * mm])
        header_table.setStyle(TableStyle([
            ("SPAN", (1, 0), (1, 0)),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        elements.append(header_table)
    except FileNotFoundError:
        elements.append(Paragraph("<b>PROTOCOLO DE ENTREGA DE EQUIPAMENTOS</b>", styles["Header"]))

    elements.append(Spacer(1, 10))

    # Função para texto formatado
    def para(text, style_name="TableBody"):
        return Paragraph(text, styles[style_name])

    # Informações principais
    fields = [
        [para("<b>Nº PEDIDO:</b>", "TableHeader"), para(str(requisicao.id))],
        [para("<b>DATA:</b>", "TableHeader"), para(requisicao.data.strftime("%d/%m/%Y") if requisicao.data else "N/A")],
        [para("<b>ENDEREÇO:</b>", "TableHeader"), para(str(requisicao.endereco) if requisicao.endereco else "N/A")],
        [para("<b>FORMA DE ENVIO:</b>", "TableHeader"), para(str(requisicao.envio) if requisicao.envio else "N/A")],
        [para("<b>CLIENTE:</b>", "TableHeader"), para(str(requisicao.nome) if requisicao.nome else "N/A")],
        [para("<b>QTD:</b>", "TableHeader"), para(str(requisicao.numero_de_equipamentos) if requisicao.numero_de_equipamentos else "Não Informado")],
        [para("<b>COMERCIAL:</b>", "TableHeader"), para(str(requisicao.comercial) if requisicao.comercial else "Não Informado")],
        [para("<b>CARREGADOR:</b>", "TableHeader"), para(str(requisicao.carregador) if requisicao.carregador else "Não Informado")],
        [para("<b>TIPO DE PRODUTO:</b>", "TableHeader"), para(str(requisicao.tipo_produto) if requisicao.tipo_produto else "Não Informado")],
        [para("<b>TP:</b>", "TableHeader"), para(str(requisicao.TP) if requisicao.TP else "Não Informado")],
        [para("<b>AOS CUIDADOS:</b>", "TableHeader"), para(str(requisicao.aos_cuidados) if requisicao.aos_cuidados else "Não Informado")],
        [para("<b>CUSTOMIZAÇÃO:</b>", "TableHeader"), para(str(requisicao.tipo_customizacao) if requisicao.tipo_customizacao else "Não Informado")],
        [para("<b>Tipo de Contrato:</b>", "TableHeader"), para(str(requisicao.contrato) if requisicao.contrato else "Não Informado")],


    ]

    table = Table(fields, colWidths=[50 * mm, 120 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (0, -1), soft_yellow),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 10))

    # IDs dos Equipamentos
    if requisicao.id_equipamentos:
        equipamentos = requisicao.id_equipamentos.split()
    else:
        equipamentos = ["Não Informado"]

    id_rows = [equipamentos[i:i + 5] for i in range(0, len(equipamentos), 5)]

    elements.append(Paragraph("<b>ID - EQUIPAMENTOS:</b>", styles["Body"]))

    for row in id_rows:
        row_table = Table([row], colWidths=[40 * mm] * 5)
        row_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
        ]))
        elements.append(row_table)
        elements.append(Spacer(1, 5))

    # Rodapé
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(50, 40, "NOME:")
        canvas.drawString(220, 40, "ASS.:")
        canvas.drawString(380, 40, "CPF:")
        canvas.drawString(500, 40, "DATA E HORA:")
        canvas.restoreState()

    # Geração do PDF
    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="protocolo_saida_{id}.pdf"'
    buffer.close()
    return response



def enviar_email_com_pdf(request, id):
    requisicao = get_object_or_404(Requisicoes, id=id)
    pdf_path = gerar_pdf_requisicao(requisicao)
    
    subject = f"Requisição Criada: {requisicao.id}"
    message = f"A requisição {requisicao.id} foi criada com sucesso. Segue PDF para tratativa."
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = ['sjuniorr6@gmail.com']
    
    email = EmailMessage(subject, message, from_email, recipient_list)
    email.attach_file(pdf_path)
    
    try:
        email.send()
        print("Email enviado com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
    
    return redirect('requisicoesListView')


from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from .models import Requisicoes

def download_pdf_requisicao(request, id):
    requisicao = get_object_or_404(Requisicoes, id=id)
    pdf_path = gerar_pdf_requisicao(requisicao)
    
    with open(pdf_path, 'rb') as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="requisicao-{requisicao.id}.pdf"'


        return response
from django.db import transaction
from django.db.models import F
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from .models import estoque_antenista
from .forms import EstoqueantenistarForm
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.shortcuts import redirect
class RegistrarEstoqueantenistaView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = estoque_antenista
    form_class = EstoqueantenistarForm
    template_name = 'estoque_antenista.html'
    success_url = reverse_lazy('RegistrarEstoqueantenistaView')
    permission_required = 'tuper.add_estoque_tuper'

    def form_valid(self, form):
        nome = form.cleaned_data['nome']
        tipo_produto = form.cleaned_data['tipo_produto']
        quantidade = form.cleaned_data['quantidade'] // 2  # Retira metade do valor adicionado
        endereco = form.cleaned_data['endereco']

        with transaction.atomic():
            estoques = estoque_antenista.objects.filter(nome=nome, tipo_produto=tipo_produto)
            if estoques.exists():
                estoque = estoques.order_by('-quantidade').first()
                estoque.quantidade = F('quantidade') + quantidade
                estoque.endereco = endereco
                estoque.save(update_fields=['quantidade', 'endereco'])
            else:
                estoque = estoque_antenista(nome=nome, tipo_produto=tipo_produto, quantidade=quantidade, endereco=endereco)
                estoque.save()

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        estoques = estoque_antenista.objects.all()
        estoque_dict = {}

        for estoque in estoques:
            key = (estoque.nome, estoque.tipo_produto)
            if key in estoque_dict:
                estoque_dict[key].quantidade += estoque.quantidade
            else:
                estoque_dict[key] = estoque

        for key, estoque in estoque_dict.items():
            estoque.save()
            estoque_antenista.objects.filter(nome=key[0], tipo_produto=key[1]).exclude(id=estoque.id).delete()

        context['estoques'] = list(estoque_dict.values())
        return context


@permission_required('requisicao.change_estoque_antenista', raise_exception=True)
def zerar_estoque_antenista(request):
    """Zera (define para 0) a quantidade de todos os registros de estoque_antenista.

    Esta ação exige permissão `requisicao.change_estoque_antenista` e deve ser chamada via POST.
    """
    if request.method == 'POST':
        estoque_antenista.objects.update(quantidade=0)
        messages.success(request, 'Quantidade em estoque zerada para todos os registros.')
    else:
        messages.error(request, 'Requisição inválida. Use POST para zerar o estoque.')
    return redirect('RegistrarEstoqueantenistaView')

from .models import antenista_CARD
from .forms import antenista_Form
class AntenistaCreateView(CreateView):
    model = antenista_CARD
    form_class = antenista_Form
    template_name = 'antenista_form.html'  # Substitua pelo caminho correto do seu template
    success_url = reverse_lazy('lista_antenistas')  # Ajuste para sua rota desejada

    def form_valid(self, form):
        # Envia o e-mail após salvar o registro
        response = super().form_valid(form)  # Salva o registro

        # Configuração do e-mail
        send_mail(
            subject='Projeto Fast - Novo Registro',
            message='Um novo registro foi criado no sistema. Comercial favor tratar',
            from_email = settings.DEFAULT_FROM_EMAIL,
            recipient_list = ['sjuniorr6@Gmail.com','comercial@grupogoldensat.com.br'],
            fail_silently=False,  # Define como True para evitar erros visíveis ao usuário
        )

        return response




from django.views.generic.list import ListView
from django.http import HttpResponse
import openpyxl
from openpyxl.utils import get_column_letter

class AntenistaListView(ListView):
    model = antenista_CARD
    template_name = 'antenista_list.html'
    context_object_name = 'antenistas'


def export_antenistas_excel(request):
    """Exporta todos os registros de antenista_CARD para um arquivo Excel (.xlsx)."""
    # Query todos os registros
    antenistas = antenista_CARD.objects.all()

    # Cria workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Antenistas'

    # Cabeçalhos (mesma ordem da tabela)
    headers = [
        'Nome', 'Tipo de Produto', 'Telefone', 'Cliente', 'Quantidade', 'Equipamentos',
        'Solicitante', 'Valor Total', 'Valor Prestador', 'Valor Isca', 'Valor Cliente', 'Lucro',
        'Contrato', 'Status', 'Data de Criação'
    ]
    ws.append(headers)

    # Preenche linhas
    for a in antenistas:
        row = [
            str(a.nome) if a.nome is not None else '',
            str(a.tipo_produto) if a.tipo_produto is not None else '',
            a.telefone or '',
            a.cliente or '',
            a.quantidade if a.quantidade is not None else '',
            a.equipamentos or '',
            a.solicitante or '',
            float(a.valor_total) if a.valor_total is not None else 0,
            float(a.valor_prestador) if a.valor_prestador is not None else 0,
            float(a.valor_isca) if a.valor_isca is not None else 0,
            float(a.valor_cliente) if a.valor_cliente is not None else 0,
            float(a.lucro) if a.lucro is not None else 0,
            a.contrato or '',
            a.status or '',
            a.data_criacao.strftime('%d/%m/%Y') if a.data_criacao else '',
        ]
        ws.append(row)

    # Ajusta largura das colunas
    for i, column_cells in enumerate(ws.columns, 1):
        length = max((len(str(cell.value)) for cell in column_cells), default=0)
        ws.column_dimensions[get_column_letter(i)].width = min(max(length + 2, 10), 50)

    # Prepara resposta
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=antenistas.xlsx'
    wb.save(response)
    return response
    
    
    # requisicao/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import antenista_CARD



def atualizar_status_atualizado(request, pk):
    antenista = get_object_or_404(antenista_CARD, pk=pk)
    if request.method == 'POST':
        if antenista.status != 'Atualizado':
            antenista.status = 'Atualizado'
            antenista.save()
            messages.success(request, f"Status de {antenista.nome} atualizado para 'Atualizado'.")
        else:
            messages.info(request, f"O status de {antenista.nome} já está 'Atualizado'.")
        return redirect('lista_antenistas')
    else:
        messages.error(request, "Método HTTP inválido.")
        return redirect('lista_antenistas')







from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import UpdateView
from .models import  Requisicoes
from .forms import RequisicaoForm  # Supondo que você tenha um form para Requisicao

class RequisicaoUpdateView(UpdateView):
    model = Requisicoes
    form_class = RequisicaoForm  # Você pode usar um ModelForm ou o form padrão
    template_name = 'requisicao_update.html'
    success_url = reverse_lazy('requisicoes_list')  # Redireciona para a lista após a atualização

    def form_valid(self, form):
        form.instance.data_alteracao = timezone.now()
        return super().form_valid(form)
