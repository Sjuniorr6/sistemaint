"""Mapa e busca por proximidade (ISC-RF-16 a ISC-RF-21)."""
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from iscas.forms import BuscaProximidadeForm
from iscas.models.cadastro import Cliente
from iscas.models.config import ConfiguracaoIscas
from iscas.enums import Capacidade
from iscas.permissions import exige
from iscas.services.geo import (
    agentes_para_solicitacao,
    agentes_proximos,
    agentes_sem_coordenada,
)


def contexto_do_mapa(request) -> dict:
    """O que o mapa operacional do painel precisa (ISC-RF-16).

    `?solicitacao=` vem do botão da tela da solicitação: o select já chega
    escolhido e o mapa busca sozinho. Fora do queryset, o select ignora.
    """
    sugerida = request.GET.get("solicitacao", "")
    initial = {"solicitacao": int(sugerida)} if sugerida.isdigit() else {}
    return {
        "form": BuscaProximidadeForm(initial=initial),
        "sem_coordenada": agentes_sem_coordenada(),
    }


def _para_o_painel(request):
    """O mapa mora no painel; links antigos para /mapa/ continuam valendo."""
    destino = reverse("iscas:painel")
    if request.GET.get("solicitacao", "").isdigit():
        destino += f"?solicitacao={request.GET['solicitacao']}"
    return redirect(destino + "#mapa-operacional")


@exige(Capacidade.VER_MAPA)
def mapa(request):
    """Rota antiga do mapa: redireciona para o painel."""
    return _para_o_painel(request)


@exige(Capacidade.VER_MAPA)
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
                solicitacao=solicitacao, raio_km=dados["raio_km"],
                minimo_disponivel=dados.get("minimo_disponivel"),
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
    return _para_o_painel(request)
