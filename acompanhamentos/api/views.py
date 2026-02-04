# acompanhamentos/api/views.py
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from acompanhamentos.models import registroacompanhamento, AcompanhamentoLocalizacao
import json

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


@csrf_exempt
@require_POST
def api_missao_location(request, id):
    """
    Endpoint para receber localização do app a cada 5 segundos
    POST /api/missao/<id>/location/
    """
    try:
        missao = get_object_or_404(registroacompanhamento, pk=id)
        
        # Parse do body JSON
        data = json.loads(request.body)
        
        # Pega o agente principal
        agente_principal = missao.agentes.filter(tipo_agente="principal").first()
        
        # Cria o registro de localização
        AcompanhamentoLocalizacao.objects.create(
            acompanhamento=missao,
            agente=agente_principal.agente if agente_principal else None,
            usuario=None,  # App não tem usuário logado
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            accuracy=data.get("accuracy"),
            origem="app"
        )
        
        # Atualiza status se ainda estiver pendente
        if missao.status_acompanhamento == "pendente":
            missao.status_acompanhamento = "em_andamento"
            missao.save(update_fields=["status_acompanhamento"])
        
        return JsonResponse({
            "success": True,
            "message": "Localização registrada"
        }, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "error": "JSON inválido"
        }, status=400)
        
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)


@csrf_exempt
@require_POST
def api_missao_panic(request, id):
    """
    Endpoint para receber alerta de pânico do app
    POST /api/missao/<id>/panic/
    """
    try:
        missao = get_object_or_404(registroacompanhamento, pk=id)
        
        # Parse do body JSON
        data = json.loads(request.body)
        
        # Pega o agente principal
        agente_principal = missao.agentes.filter(tipo_agente="principal").first()
        
        # Salva a localização do pânico
        AcompanhamentoLocalizacao.objects.create(
            acompanhamento=missao,
            agente=agente_principal.agente if agente_principal else None,
            usuario=None,
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            accuracy=data.get("accuracy"),
            origem="app"
        )
        
        # Ativa o botão de pânico e atualiza status
        missao.botao_panico = True
        missao.status_acompanhamento = "em_andamento"
        missao.save(update_fields=["botao_panico", "status_acompanhamento"])
        
        return JsonResponse({
            "success": True,
            "message": "Alerta registrado"
        }, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "error": "JSON inválido"
        }, status=400)
        
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)