from django.shortcuts import render
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from . import models, forms
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

class ClienteListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = models.Clientes
    template_name = "cliente_list.html"
    context_object_name = 'cliente'
    paginate_by = 20
    permission_required = "acompanhamento.view_clientes"
    
    def get_queryset(self):
        queryset = super().get_queryset()
        nome = self.request.GET.get('nome')
        if nome:
            queryset = queryset.filter(nome__icontains=nome)
        return queryset

class ClienteCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = models.Clientes
    template_name = 'cliente_create.html'
    form_class = forms.ClienteForm
    success_url = reverse_lazy('cliente_list')
    permission_required = "acompanhamento.add_clientes"

class ClienteDetailView(PermissionRequiredMixin, LoginRequiredMixin, DetailView):
    model = models.Clientes
    template_name = 'cliente_detail.html'
    context_object_name = 'cliente'
    permission_required = "acompanhamento.view_clientes"

class ClienteUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = models.Clientes
    template_name = 'cliente_update.html'
    form_class = forms.ClienteForm
    success_url = reverse_lazy('cliente_list')
    permission_required = "acompanhamento.change_clientes"

class ClienteDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = models.Clientes
    template_name = 'cliente_delete.html'
    success_url = reverse_lazy('cliente_list')
    permission_required = "acompanhamento.delete_clientes"

@login_required
def home_view(request):
    return render(request, 'home.html')

@login_required
def acompanhamento_cliente(request):
    return render(request, 'acompanhamento_cliente.html')

@login_required
def acompanhamento_relatorio(request):
    return render(request, 'acompanhamento_relatorio.html')

@login_required
def acompanhamento_requisicao(request):
    return render(request, 'acompanhamento_requisicao.html')

@login_required
def acompanhamento_desempenho(request):
    return render(request, 'acompanhamento_desempenho.html')
