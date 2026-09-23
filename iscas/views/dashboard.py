"""Painel operacional (ISC-RF-38)."""
from django.shortcuts import render

from iscas import selectors
from iscas.enums import Capacidade
from iscas.permissions import exige


@exige(Capacidade.VER_PAINEL)
def painel(request):
    """Visão geral: unidades por estado, pendências e alertas."""
    return render(request, "iscas/painel.html", selectors.metricas_painel())
