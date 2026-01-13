from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from .models import ticketmodel
from django.views.generic import CreateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count

from .models import ticketmodel
from .forms import TicketKanbanForm
from kanban_inteligencia.models import TarefaInteligencia
from django.utils import timezone
from datetime import timedelta  

class ticketCreateView(LoginRequiredMixin, CreateView):
    model = TarefaInteligencia
    form_class = TicketKanbanForm
    template_name = 'ticket.html'
    success_url = reverse_lazy('ticketListView')

    def form_valid(self, form):
        user = self.request.user

        # ---------------------------------
        # 🔐 PRIORIDADE DEFINIDA PELO GRUPO
        # ---------------------------------
        if user.groups.filter(name='diretoriamaster').exists():
            form.instance.prioridade = 'alta'
        else:
            form.instance.prioridade = 'avaliar'  # equivalente a "avaliar"

        # ---------------------------------
        # ⏰ PRAZO AUTOMÁTICO (48 HORAS)
        # ---------------------------------
        form.instance.data_limite = timezone.now().date() + timedelta(days=2)

        # ---------------------------------
        # 👤 RESPONSÁVEL (opcional)
        # ---------------------------------
        # Pode ficar vazio — NÃO setamos nada aqui

        return super().form_valid(form)

        # ---------------------------------
        # Dados automáticos
        # ---------------------------------
        # if not form.instance.responsavel:
        #     form.instance.responsavel = user.get_full_name() or user.username

      
    
class ticketListView(ListView):
    def get_sector_colors(self):
        # Dicionário de cores para cada setor
        return {
            'Diretoria': 'bg-primary',
            'Inteligência': 'bg-info',
            'Faturamento': 'bg-warning',
            'Expedição': 'bg-success',
            'Configuração': 'bg-secondary',
            'Quality': 'bg-dark',
            'Área Técnica': 'bg-danger',
            'Comercial': 'bg-light',
        }
    model = ticketmodel
    template_name = 'ticket_list.html'
    context_object_name = 'ticket'
    paginate_by = 12

    def get_queryset(self):
        queryset = ticketmodel.objects.all().order_by('-id')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['qtd_negado'] = ticketmodel.objects.filter(status='Negado').count()
        context['qtd_atualizado'] = ticketmodel.objects.filter(status='Atualizado').count()
        context['qtd_setor'] = ticketmodel.objects.values('setor').distinct().count()
        context['tickets_por_setor'] = (
            ticketmodel.objects.values('setor')
            .annotate(total=Count('id'))
            .order_by('setor')
        )
        context['sector_colors'] = self.get_sector_colors()
        return context

    

def atualizar_status(request, ticket_id):
    ticket = get_object_or_404(ticketmodel, id=ticket_id)
    if ticket.status == 'Pendente':
        ticket.status = 'Atualizado'
        ticket.save()
    return redirect('ticketListView')

def atualizar_status2(request, ticket_id):
    ticket = get_object_or_404(ticketmodel, id=ticket_id)
    if ticket.status == 'Pendente':
        ticket.status = 'Negado'
        ticket.save()
    return redirect('ticketListView')

from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from .models import ticketmodel

class DevolutivaUpdateView(UpdateView):
    model = ticketmodel
    template_name = 'atualizar_devolutiva.html'
    fields = ['devolutiva']  # Define o campo que será atualizado
    success_url = reverse_lazy('ticketListView')  # Redireciona após salvar

    def form_valid(self, form):
        form.instance.usuario = self.request.user  # Opcional: Atribuir usuário, se necessário
        return super().form_valid(form)