"""Mapa e busca por proximidade (ISC-RF-16 a ISC-RF-21)."""
from django.shortcuts import get_object_or_404, render

from iscas.forms import BuscaProximidadeForm
from iscas.models.cadastro import Cliente
from iscas.models.config import ConfiguracaoIscas
from iscas.permissions import exige_operador
from iscas.services.geo import (
    agentes_para_solicitacao,
    agentes_proximos,
    agentes_sem_coordenada,
)


@exige_operador
def mapa(request):
    """Mapa com todos os agentes ativos e coordenada válida (ISC-RF-16)."""
    return render(
        request,
        "iscas/mapa.html",
        {
            "config": ConfiguracaoIscas.carregar(),
            "form": BuscaProximidadeForm(),
            "sem_coordenada": agentes_sem_coordenada(),
        },
    )


@exige_operador
def busca_proximidade(request):
    """Resultado da busca — mapa e tabela lateral sincronizados (ISC-RF-20).

    Responde parcial quando vem do HTMX, página completa caso contrário.
    """
    form = BuscaProximidadeForm(request.GET or None)
    resultados = []
    cliente = None
    solicitacao = None

    if form.is_valid():
        dados = form.cleaned_data
        solicitacao = dados.get("solicitacao")
        if solicitacao is not None:
            # O pedido responde por cliente, modelos e quantidades.
            cliente = solicitacao.cliente
            resultados = agentes_para_solicitacao(
                solicitacao=solicitacao, raio_km=dados["raio_km"]
            )
        else:
            # Busca a partir de um ponto do mapa, sem pedido associado.
            resultados = agentes_proximos(
                latitude=dados["latitude"],
                longitude=dados["longitude"],
                raio_km=dados["raio_km"],
            )

    contexto = {
        "form": form,
        "resultados": resultados,
        "cliente": cliente,
        "solicitacao": solicitacao,
        "config": ConfiguracaoIscas.carregar(),
        # Estoque invisível é o pior erro possível aqui: quem está sem
        # coordenada aparece à parte, sinalizado (ISC-RN-12, ISC-RF-21).
        "sem_coordenada": agentes_sem_coordenada(),
    }

    if request.headers.get("HX-Request"):
        return render(request, "iscas/_resultado_proximidade.html", contexto)
    return render(request, "iscas/mapa.html", contexto)
