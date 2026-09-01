"""Painel operacional (ISC-RF-38)."""
from django.shortcuts import render

from iscas import selectors
from iscas.permissions import exige_operador


@exige_operador
def painel(request):
    """Visão geral: unidades por estado, pendências e alertas."""
    return render(request, "iscas/painel.html", selectors.metricas_painel())
