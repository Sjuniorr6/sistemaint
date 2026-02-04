# acompanhamentos/api/views.py
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from acompanhamentos.models import registroacompanhamento

def api_missao_detail(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido"}, status=405)

    missao = get_object_or_404(
        registroacompanhamento.objects.prefetch_related("agentes__agente"),
        pk=id
    )

    agente_nome = ""
    
    if hasattr(missao, "agentes"):
        agente_principal = missao.agentes.filter(tipo_agente="principal").first()
        
        if agente_principal and agente_principal.agente:
            agente_nome = getattr(agente_principal.agente, "nome", "") or str(agente_principal.agente)
        else:
            primeiro_agente = missao.agentes.first()
            if primeiro_agente and primeiro_agente.agente:
                agente_nome = getattr(primeiro_agente.agente, "nome", "") or str(primeiro_agente.agente)

    data = {
        "id": str(missao.pk),
        "origem": getattr(missao, "origem", "") or "",
        "agente": agente_nome,
    }

    return JsonResponse(data, status=200)