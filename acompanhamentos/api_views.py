from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import registroacompanhamento

def api_missao_detalhe(request, pk):
    acompanhamento = get_object_or_404(registroacompanhamento, pk=pk)

    agente_principal = acompanhamento.agentes.filter(
        tipo_agente="principal"
    ).select_related("agente").first()

    data = {
        "id": acompanhamento.id,
        "status": acompanhamento.status_acompanhamento,
        "origem": acompanhamento.origem,
        "destino": acompanhamento.destino,
        "tipo_servico": str(acompanhamento.tipo_servico),
        "criado_em": acompanhamento.criado_em.isoformat(),

        "agente": {
            "id": agente_principal.agente.id if agente_principal else None,
            "nome": agente_principal.agente.nome if agente_principal else None,
        } if agente_principal else None,

        "cliente": {
            "id": acompanhamento.cliente.id,
            "nome": acompanhamento.cliente.nome
        } if acompanhamento.cliente else None,
    }

    return JsonResponse(data)
