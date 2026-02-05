from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone

from acompanhamentos.models import registroacompanhamento, AcompanhamentoLocalizacao

import json
import time


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
    try:
        missao = get_object_or_404(registroacompanhamento, pk=id)
        data = json.loads(request.body)

        agente_principal = missao.agentes.filter(tipo_agente="principal").first()

        loc = AcompanhamentoLocalizacao.objects.create(
            acompanhamento=missao,
            agente=agente_principal.agente if agente_principal else None,
            usuario=None,
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            accuracy=data.get("accuracy"),
            origem=missao.origem,
            is_panic=False,
            panic_resolved=False,
            resolved_by=None,
            resolved_at=None,
        )

        panic_active = AcompanhamentoLocalizacao.objects.filter(
            acompanhamento=missao,
            is_panic=True,
            panic_resolved=False
        ).exists()

        if missao.botao_panico != panic_active:
            missao.botao_panico = panic_active
            missao.save(update_fields=["botao_panico"])

        return JsonResponse({
            "success": True,
            "message": "Localização registrada",
            "location_id": loc.id,
            "panic_active": panic_active,
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON inválido"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_POST
def api_missao_panic(request, id):
    try:
        missao = get_object_or_404(registroacompanhamento, pk=id)
        data = json.loads(request.body)

        agente_principal = missao.agentes.filter(tipo_agente="principal").first()

        panic_event = AcompanhamentoLocalizacao.objects.create(
            acompanhamento=missao,
            agente=agente_principal.agente if agente_principal else None,
            usuario=None,
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            accuracy=data.get("accuracy"),
            is_panic=True,
            panic_resolved=False,
            resolved_by=None,
            resolved_at=None,
            origem=missao.origem
        )

        if not missao.botao_panico:
            missao.botao_panico = True
            missao.save(update_fields=["botao_panico"])

        return JsonResponse({
            "success": True,
            "message": "Alerta registrado",
            "panic_id": panic_event.id,
            "panic_active": True
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON inválido"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_GET
def api_missao_localizacoes(request, id):
    try:
        missao = get_object_or_404(registroacompanhamento, pk=id)

        qs = (
            AcompanhamentoLocalizacao.objects
            .filter(acompanhamento=missao)
            .order_by("criado_em")
        )

        localizacoes = [
            {
                "id": loc.id,
                "latitude": float(loc.latitude) if loc.latitude is not None else None,
                "longitude": float(loc.longitude) if loc.longitude is not None else None,
                "is_panic": bool(loc.is_panic),
                "panic_resolved": bool(loc.panic_resolved),
                "criado_em": loc.criado_em.strftime("%d/%m/%Y %H:%M:%S") if loc.criado_em else None,
                "origem": loc.origem or "",
                "resolved_at": loc.resolved_at.strftime("%d/%m/%Y %H:%M:%S") if loc.resolved_at else None,
                "resolved_by": loc.resolved_by.get_full_name() if loc.resolved_by else None
            }
            for loc in qs
        ]

        panic_active = AcompanhamentoLocalizacao.objects.filter(
            acompanhamento=missao,
            is_panic=True,
            panic_resolved=False
        ).exists()

        last_open_panic = (
            AcompanhamentoLocalizacao.objects
            .filter(acompanhamento=missao, is_panic=True, panic_resolved=False)
            .order_by("-criado_em")
            .first()
        )

        last_panic = (
            AcompanhamentoLocalizacao.objects
            .filter(acompanhamento=missao, is_panic=True)
            .order_by("-criado_em")
            .first()
        )

        return JsonResponse({
            "success": True,
            "localizacoes": localizacoes,
            "total": len(localizacoes),
            "origem_acompanhamento": missao.origem,

            "panic_active": panic_active,

            "open_panic_id": last_open_panic.id if last_open_panic else None,
            "open_panic_at": last_open_panic.criado_em.strftime("%d/%m/%Y %H:%M:%S") if last_open_panic else None,

            "last_panic_id": last_panic.id if last_panic else None,
            "last_panic_at": last_panic.criado_em.strftime("%d/%m/%Y %H:%M:%S") if last_panic else None,
        }, status=200)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_POST
def api_resolver_panico(request, localizacao_id):
    try:
        localizacao = get_object_or_404(AcompanhamentoLocalizacao, pk=localizacao_id)

        if not localizacao.is_panic:
            return JsonResponse({"success": False, "error": "Esta localização não é um alerta de pânico"}, status=400)

        if localizacao.panic_resolved:
            return JsonResponse({"success": False, "error": "Este pânico já foi resolvido"}, status=400)

        localizacao.panic_resolved = True
        localizacao.resolved_at = timezone.now()

        if request.user and request.user.is_authenticated:
            localizacao.resolved_by = request.user

        localizacao.save(update_fields=["panic_resolved", "resolved_at", "resolved_by"])

        missao = localizacao.acompanhamento
        ainda_existe_panic_aberto = AcompanhamentoLocalizacao.objects.filter(
            acompanhamento=missao,
            is_panic=True,
            panic_resolved=False
        ).exists()

        if not ainda_existe_panic_aberto and missao.botao_panico:
            missao.botao_panico = False
            missao.save(update_fields=["botao_panico"])

        return JsonResponse({
            "success": True,
            "message": "Pânico marcado como resolvido",
            "resolved_at": localizacao.resolved_at.strftime("%d/%m/%Y %H:%M:%S"),
            "resolved_by": localizacao.resolved_by.get_full_name() if localizacao.resolved_by else "Operador",
            "panic_active": ainda_existe_panic_aberto
        }, status=200)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_GET
def api_missao_wait_panic(request, id):
    missao = get_object_or_404(registroacompanhamento, pk=id)

    try:
        after_id = int(request.GET.get("after_id") or 0)
    except ValueError:
        after_id = 0

    timeout_seconds = 25
    interval_seconds = 0.8
    end_time = time.time() + timeout_seconds

    while time.time() < end_time:
        panic = (
            AcompanhamentoLocalizacao.objects
            .filter(acompanhamento=missao, is_panic=True, id__gt=after_id)
            .order_by("id")
            .first()
        )

        if panic:
            return JsonResponse({
                "success": True,
                "event": "panic_created",
                "panic_id": panic.id,
                "panic_at": panic.criado_em.strftime("%d/%m/%Y %H:%M:%S"),
                "panic_resolved": panic.panic_resolved,
            }, status=200)

        time.sleep(interval_seconds)

    return JsonResponse({"success": True, "timeout": True}, status=200)


@require_GET
def api_missao_panic_status(request, id):
    missao = get_object_or_404(registroacompanhamento, pk=id)

    panic_active = AcompanhamentoLocalizacao.objects.filter(
        acompanhamento=missao,
        is_panic=True,
        panic_resolved=False
    ).exists()

    last_open_panic = (
        AcompanhamentoLocalizacao.objects
        .filter(acompanhamento=missao, is_panic=True, panic_resolved=False)
        .order_by("-id")
        .first()
    )

    return JsonResponse({
        "success": True,
        "panic_active": panic_active,
        "open_panic_id": last_open_panic.id if last_open_panic else None,
        "open_panic_at": last_open_panic.criado_em.strftime("%d/%m/%Y %H:%M:%S") if last_open_panic else None,
    }, status=200)
