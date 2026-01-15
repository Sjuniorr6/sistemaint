from typing import Any
from django.views.generic import (
    ListView,
    CreateView,
    DetailView,
    UpdateView,
    DeleteView,
)
from django.shortcuts import render, redirect
from . import models, forms
import logging
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from .forms import FormulariosForm
from .models import registrodefranquia

# ------------------------------------------------------
#                     FRANQUIA
# ------------------------------------------------------
class FranquiaCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = registrodefranquia
    form_class = FormulariosForm
    template_name = "franquia_create.html"
    success_url = reverse_lazy("franquiaList")
    permission_required = "franquia.add_registrodefranquia"

    def get_initial(self):
        initial = super().get_initial()
        user = getattr(self.request, 'user', None)
        if user:
            initial['nome_user'] = user.get_full_name() or user.username
        return initial

    def form_valid(self, form):
        campos_para_validar = [
            'nome', 'valor_acionamento', 'franquia_km', 'franquia_horas',
            'km_excedente', 'valor_km_excedente', 'valor_horas_excedente',
        ]

        dados = form.cleaned_data

        # Verifica se TODOS estão vazios
        todos_vazios = all(
            not dados.get(campo)
            for campo in campos_para_validar
        )

        if todos_vazios:
            return redirect("franquiaCreate")

        instance = form.save(commit=False)

        user = getattr(self.request, 'user', None)
        if user:
            instance.nome_user = user.get_full_name() or user.username

        instance.save()
        return super().form_valid(form)

class FranquiaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = registrodefranquia
    template_name = "franquia_list.html"
    context_object_name = "franquias"
    permission_required = "franquia.view_listfranquia"

    def get_queryset(self):
        queryset = super().get_queryset()

        nome = self.request.GET.get("nome")

        if nome:
            queryset = queryset.filter(nome__icontains=nome)

        return queryset.order_by("-criado_em")

class RegistroFranquiaUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):

    model = registrodefranquia
    form_class = FormulariosForm
    template_name = "franquia_create.html"
    success_url = reverse_lazy("franquiaList")
    permission_required = "franquia.change_registrodefranquia"

    def form_valid(self, form):
        return super().form_valid(form)

