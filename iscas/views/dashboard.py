"""Painel operacional (ISC-RF-38)."""
from django.shortcuts import render

from iscas import selectors
from iscas.enums import Capacidade
from iscas.permissions import exige, pode
from iscas.views.mapa import contexto_do_mapa


@exige(Capacidade.VER_PAINEL)
def painel(request):
    """Visão geral: unidades por estado, pendências e alertas."""
    contexto = selectors.metricas_painel()
    if pode(request.user, Capacidade.VER_MAPA):
        contexto.update(contexto_do_mapa(request))
    return render(request, "iscas/painel.html", contexto)
