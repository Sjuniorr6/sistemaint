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

        # 👤 USUÁRIO CRIADOR DO TICKET
        form.instance.usuario = user

        # 🔐 PRIORIDADE: ticket nasce SEM prioridade definida ('avaliar').
        # A prioridade é atribuída depois, na triagem do Kanban.
        form.instance.prioridade = 'avaliar'

        # ⏰ PRAZO AUTOMÁTICO (48 HORAS)
        form.instance.data_limite = timezone.now().date() + timedelta(days=2)

           # 🆕 NOVO: Definir status inicial como "avaliar" (em vez de "tarefas a fazer")
        form.instance.status = 'avaliar'

        
        # 🆕 NOVO: Direcionar ao kanban com base na escolha do usuário (assumindo que o formulário tem um campo 'kanban_tipo')
        # Substitua 'kanban_tipo' pelo nome exato do campo no seu formulário/modelo
        kanban_escolha = form.cleaned_data.get('kanban_tipo')  # Ex.: 'desenvolvimento' ou 'inteligencia'
        if kanban_escolha:
            form.instance.kanban_tipo = kanban_escolha  # Ajuste conforme o campo do modelo


        return super().form_valid(form)

      
    
class ticketListView(LoginRequiredMixin, ListView):
    model = TarefaInteligencia
    template_name = 'ticket_list.html'
    context_object_name = 'tickets'
    ordering = ['-data_criacao', '-id']

    def get_queryset(self):
        # Tickets concluídos permanecem na central com visual de "Concluído"
        # (badge verde + mensagem) — não são mais removidos da lista.
        qs = super().get_queryset().filter(usuario=self.request.user)

        for ticket in qs:
            ticket.is_diretoriamaster = ticket.usuario.groups.filter(
                name='diretoriamaster'
            ).exists()

        return qs
    

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