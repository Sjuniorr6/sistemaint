from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from acompanhamentos.models import registroacompanhamento, AcompanhamentoLocalizacao
from math import radians, cos, sin, asin, sqrt
import json
import time
from django.conf import settings
from supabase import create_client
from .supabase_client import get_supabase
from datetime import datetime, timezone as dt_tz
import uuid
# from .utils import validate_odometer_with_ai

# ──────────────────────────────────────────────────────────
#                 Haversine
# ──────────────────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    """Distância em metros entre dois pontos."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371000 * 2 * asin(sqrt(a))


# ══════════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════════
def _now_iso():
    return datetime.now(dt_tz.utc).isoformat()


# ──────────────────────────────────────────────────────────
#                 Detail
# ──────────────────────────────────────────────────────────
@csrf_exempt
@require_GET
def api_missao_detail(request, id):
    """Busca dados da missão do Supabase"""
    try:
        mission_uuid = str(id)
        sb = get_supabase()
        
        res = (
            sb.table("missions_control")
            .select("*")
            .eq("id", mission_uuid)
            .maybe_single()
            .execute()
        )
        
        mission = res.data or {}
        
        if not mission:
            return JsonResponse({"error": "Missão não encontrada"}, status=404)
        
        data = {
            "id": str(mission.get("id") or ""),
            "origem": mission.get("origem") or "",
            "agente": mission.get("agente") or "",
            "status": mission.get("status") or "",
        }
        
        return JsonResponse(data, status=200)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ──────────────────────────────────────────────────────────
#          Location (com Geofence) - SUPABASE
# ──────────────────────────────────────────────────────────
@csrf_exempt
@require_POST
def api_missao_location(request, id):
    """
    Salva localização em mission_tracking no Supabase.
    Verifica geofence: se dentro do raio e status == missao_aceita → no_local.
    """
    try:
        mission_uuid = str(id)
        data = json.loads(request.body)
        
        lat = data.get("latitude") or data.get("lat")
        lng = data.get("longitude") or data.get("lng")
        
        if lat is None or lng is None:
            return JsonResponse({
                "success": False,
                "error": "latitude e longitude são obrigatórios"
            }, status=400)
        
        lat = float(lat)
        lng = float(lng)
        
        sb = get_supabase()
        
        # 1) Salvar tracking no Supabase
        tracking_payload = {
            "mission_id": mission_uuid,
            "lat": lat,
            "lng": lng,
            "accuracy": data.get("accuracy"),
            "speed": data.get("speed"),
            "heading": data.get("heading"),
            "timestamp": _now_iso(),
        }
        
        res_tracking = sb.table("mission_tracking").insert(tracking_payload).execute()
        tracking_row = (res_tracking.data or [{}])[0] if res_tracking.data else {}
        
        # 2) Buscar status atual da missão
        mission_res = (
            sb.table("missions_control")
            .select("*")
            .eq("id", mission_uuid)
            .maybe_single()
            .execute()
        )
        mission = mission_res.data or {}
        current_status = (mission.get("status") or "").strip()
        
        # 3) Geofence — só verifica se status é missao_aceita
        geofence_result = None
        status_changed = False
        new_status = None
        
        if current_status == "missao_aceita":
            # Buscar origem do Django (como referência)
            django_acomp = None
            try:
                mission_uuid_obj = uuid.UUID(mission_uuid)
                django_acomp = registroacompanhamento.objects.filter(
                    supabase_mission_id=mission_uuid_obj
                ).first()
            except (ValueError, AttributeError):
                pass
            
            if django_acomp and django_acomp.latitude_origem and django_acomp.longitude_origem:
                lat_orig = float(django_acomp.latitude_origem)
                lng_orig = float(django_acomp.longitude_origem)
                raio = django_acomp.raio_cerca or 60
                
                distancia = haversine(lat, lng, lat_orig, lng_orig)
                
                geofence_result = {
                    "distance_meters": round(distancia, 2),
                    "radius_meters": raio,
                    "inside": distancia <= raio,
                    "origin_lat": lat_orig,
                    "origin_lng": lng_orig,
                }
                
                # Entrou na cerca → no_local
                if distancia <= raio:
                    sb.table("missions_control").update({
                        "status": "no_local",
                        "updated_at": _now_iso(),
                    }).eq("id", mission_uuid).execute()
                    
                    # Sincroniza Django também
                    try:
                        registroacompanhamento.objects.filter(
                            supabase_mission_id=mission_uuid_obj
                        ).update(status_acompanhamento="no_local")
                    except:
                        pass
                    
                    new_status = "no_local"
                    status_changed = True
        
        # 4) Atualizar pânico se necessário
        panic_check = (
            sb.table("mission_alerts")
            .select("id")
            .eq("mission_id", mission_uuid)
            .eq("alert_type", "panic")
            .eq("resolved", False)
            .execute()
        )
        panic_active = bool(panic_check.data)
        
        return JsonResponse({
            "success": True,
            "message": "Localização registrada",
            "location_id": tracking_row.get("id"),
            "panic_active": panic_active,
            "status_acompanhamento": new_status or current_status,
            "status_changed": status_changed,
            "geofence": geofence_result,
        }, status=200)
    
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON inválido"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ──────────────────────────────────────────────────────────
#          Panic - SUPABASE
# ──────────────────────────────────────────────────────────
@csrf_exempt
@require_POST
def api_missao_panic(request, id):
    """Aciona pânico - salva em mission_alerts no Supabase"""
    try:
        mission_uuid = str(id)
        data = json.loads(request.body)
        
        lat = data.get("latitude") or data.get("lat")
        lng = data.get("longitude") or data.get("lng")
        
        sb = get_supabase()
        
        # Salvar alerta no Supabase
        panic_payload = {
            "mission_id": mission_uuid,
            "alert_type": "panic",
            "lat": lat,
            "lng": lng,
            "accuracy": data.get("accuracy"),
            "resolved": False,
            "timestamp": _now_iso(),
        }
        
        res = sb.table("mission_alerts").insert(panic_payload).execute()
        panic_row = (res.data or [{}])[0] if res.data else {}
        
        # Atualizar status da missão para panico ativo
        sb.table("missions_control").update({
            "panic_active": True,
            "updated_at": _now_iso(),
        }).eq("id", mission_uuid).execute()
        
        # Sincronizar com Django
        try:
            mission_uuid_obj = uuid.UUID(mission_uuid)
            registroacompanhamento.objects.filter(
                supabase_mission_id=mission_uuid_obj
            ).update(botao_panico=True)
        except:
            pass
        
        return JsonResponse({
            "success": True,
            "message": "Alerta registrado",
            "panic_id": panic_row.get("id"),
            "panic_active": True
        }, status=200)
    
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON inválido"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ──────────────────────────────────────────────────────────
#          Localizações - SUPABASE
# ──────────────────────────────────────────────────────────
@csrf_exempt
@require_GET
def api_missao_localizacoes(request, id):
    """Busca localizações da missão no Supabase (mission_tracking)"""
    try:
        mission_uuid = str(id)
        sb = get_supabase()
        
        # Buscar tracking
        tracking_res = (
            sb.table("mission_tracking")
            .select("*")
            .eq("mission_id", mission_uuid)
            .order("timestamp", desc=False)
            .limit(5000)
            .execute()
        )
        tracking_rows = tracking_res.data or []
        
        localizacoes = [
            {
                "id": loc.get("id"),
                "latitude": float(loc["lat"]) if loc.get("lat") is not None else None,
                "longitude": float(loc["lng"]) if loc.get("lng") is not None else None,
                "accuracy": loc.get("accuracy"),
                "speed": loc.get("speed"),
                "heading": loc.get("heading"),
                "timestamp": loc.get("timestamp") or loc.get("created_at"),
                "criado_em": loc.get("timestamp") or loc.get("created_at"),
            }
            for loc in tracking_rows
            if loc.get("lat") is not None and loc.get("lng") is not None
        ]
        
        # Buscar alertas de pânico
        panic_res = (
            sb.table("mission_alerts")
            .select("*")
            .eq("mission_id", mission_uuid)
            .eq("alert_type", "panic")
            .order("timestamp", desc=True)
            .execute()
        )
        panic_rows = panic_res.data or []
        
        panic_active = any(not p.get("resolved", False) for p in panic_rows)
        last_open_panic = next((p for p in panic_rows if not p.get("resolved", False)), None)
        last_panic = panic_rows[0] if panic_rows else None
        
        # Buscar mission para pegar origem e geofence
        mission_res = (
            sb.table("missions_control")
            .select("*")
            .eq("id", mission_uuid)
            .maybe_single()
            .execute()
        )
        mission = mission_res.data or {}
        
        # Buscar origin do Django (como referência)
        geofence_data = None
        try:
            mission_uuid_obj = uuid.UUID(mission_uuid)
            django_acomp = registroacompanhamento.objects.filter(
                supabase_mission_id=mission_uuid_obj
            ).first()
            if django_acomp and django_acomp.latitude_origem and django_acomp.longitude_origem:
                geofence_data = {
                    "latitude": float(django_acomp.latitude_origem),
                    "longitude": float(django_acomp.longitude_origem),
                    "raio": django_acomp.raio_cerca or 60,
                }
        except:
            pass
        
        return JsonResponse({
            "success": True,
            "localizacoes": localizacoes,
            "total": len(localizacoes),
            "origem_acompanhamento": mission.get("origem") or "",
            "panic_active": panic_active,
            "open_panic_id": last_open_panic.get("id") if last_open_panic else None,
            "open_panic_at": last_open_panic.get("timestamp") if last_open_panic else None,
            "last_panic_id": last_panic.get("id") if last_panic else None,
            "last_panic_at": last_panic.get("timestamp") if last_panic else None,
            "geofence": geofence_data,
            "status_acompanhamento": mission.get("status") or "",
        }, status=200)
    
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ──────────────────────────────────────────────────────────
#          Resolver Pânico - SUPABASE
# ──────────────────────────────────────────────────────────
@csrf_exempt
@require_POST
def api_resolver_panico(request, localizacao_id):
    """Resolve pânico no Supabase"""
    try:
        sb = get_supabase()
        
        # Buscar alerta
        alert_res = (
            sb.table("mission_alerts")
            .select("*")
            .eq("id", localizacao_id)
            .maybe_single()
            .execute()
        )
        alert = alert_res.data
        
        if not alert:
            return JsonResponse({
                "success": False,
                "error": "Alerta não encontrado"
            }, status=404)
        
        if alert.get("resolved"):
            return JsonResponse({
                "success": False,
                "error": "Este pânico já foi resolvido"
            }, status=400)
        
        mission_id = alert.get("mission_id")
        
        # Marcar como resolvido
        sb.table("mission_alerts").update({
            "resolved": True,
            "resolved_at": _now_iso(),
        }).eq("id", localizacao_id).execute()
        
        # Verificar se ainda há pânicos abertos
        panic_check = (
            sb.table("mission_alerts")
            .select("id")
            .eq("mission_id", mission_id)
            .eq("alert_type", "panic")
            .eq("resolved", False)
            .execute()
        )
        ainda_tem_panic = bool(panic_check.data)
        
        # Atualizar status da missão no Supabase
        if not ainda_tem_panic:
            sb.table("missions_control").update({
                "panic_active": False,
                "updated_at": _now_iso(),
            }).eq("id", mission_id).execute()
        
        # Sincronizar com Django
        try:
            mission_uuid_obj = uuid.UUID(mission_id)
            registroacompanhamento.objects.filter(
                supabase_mission_id=mission_uuid_obj
            ).update(botao_panico=ainda_tem_panic)
        except:
            pass
        
        return JsonResponse({
            "success": True,
            "message": "Pânico marcado como resolvido",
            "resolved_at": _now_iso(),
            "panic_active": ainda_tem_panic
        }, status=200)
    
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ──────────────────────────────────────────────────────────
#          Wait Panic - SUPABASE (Polling)
# ──────────────────────────────────────────────────────────
@csrf_exempt
@require_GET
def api_missao_wait_panic(request, id):
    """Aguarda novo pânico no Supabase (polling com timeout)"""
    mission_uuid = str(id)
    sb = get_supabase()
    
    try:
        after_id = int(request.GET.get("after_id") or 0)
    except ValueError:
        after_id = 0
    
    timeout_seconds = 25
    interval_seconds = 0.8
    end_time = time.time() + timeout_seconds
    
    while time.time() < end_time:
        panic_res = (
            sb.table("mission_alerts")
            .select("*")
            .eq("mission_id", mission_uuid)
            .eq("alert_type", "panic")
            .gt("id", after_id)
            .order("id", desc=False)
            .limit(1)
            .execute()
        )
        
        panic_rows = panic_res.data or []
        if panic_rows:
            panic = panic_rows[0]
            return JsonResponse({
                "success": True,
                "event": "panic_created",
                "panic_id": panic.get("id"),
                "panic_at": panic.get("timestamp"),
                "panic_resolved": panic.get("resolved", False),
            }, status=200)
        
        time.sleep(interval_seconds)
    
    return JsonResponse({"success": True, "timeout": True}, status=200)


# ──────────────────────────────────────────────────────────
#          Panic Status - SUPABASE
# ──────────────────────────────────────────────────────────
@csrf_exempt
@require_GET
def api_missao_panic_status(request, id):
    """Retorna status de pânico da missão no Supabase"""
    try:
        mission_uuid = str(id)
        sb = get_supabase()
        
        panic_res = (
            sb.table("mission_alerts")
            .select("*")
            .eq("mission_id", mission_uuid)
            .eq("alert_type", "panic")
            .eq("resolved", False)
            .order("timestamp", desc=True)
            .execute()
        )
        
        panic_rows = panic_res.data or []
        panic_active = bool(panic_rows)
        last_open_panic = panic_rows[0] if panic_rows else None
        
        return JsonResponse({
            "success": True,
            "panic_active": panic_active,
            "open_panic_id": last_open_panic.get("id") if last_open_panic else None,
            "open_panic_at": last_open_panic.get("timestamp") if last_open_panic else None,
        }, status=200)
    
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ──────────────────────────────────────────────────────────
#               WEBHOOK - PROCESSAMENTO DE FOTOS
# ──────────────────────────────────────────────────────────
@csrf_exempt
@require_POST
def mission_photo_webhook(request):
    """
    Webhook para receber notificações do Supabase quando uma foto é enviada.
    ✅ VERSÃO ATUALIZADA: Usa IA para validar odômetro via views_supabase_photos_process
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Validar autenticação
        auth_header = request.headers.get('Authorization', '')
        expected_auth = f'Bearer {settings.SUPABASE_WEBHOOK_SECRET}'
        
        if auth_header != expected_auth:
            logger.warning(f"Webhook: autenticação falhou. Header: {auth_header[:20]}...")
            return JsonResponse({
                'success': False,
                'error': 'Unauthorized'
            }, status=401)

        # Parse do payload
        data = json.loads(request.body)
        event_type = data.get('type')
        
        if event_type != 'INSERT':
            logger.info(f"Webhook: evento ignorado (type={event_type})")
            return JsonResponse({
                'success': True,
                'message': 'Event type ignored'
            }, status=200)

        # Extrair dados
        record = data.get('record', {})
        photo_id = record.get('id')
        mission_id = record.get('mission_id')
        photo_type = record.get('type')  # 'inicio' ou 'final'
        storage_path = record.get('storage_path')

        if not all([photo_id, mission_id, photo_type, storage_path]):
            logger.error(f"Webhook: campos obrigatórios faltando. photo_id={photo_id}, mission_id={mission_id}, type={photo_type}")
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)

        logger.info(f"🔔 Webhook recebeu photo_id={photo_id}, mission_id={mission_id}, type={photo_type}")

        # ═════════════════════════════════════════════════════════
        # CHAMAR O NOVO ENDPOINT DE PROCESSAMENTO COM IA
        # ═════════════════════════════════════════════════════════
        from .views_supabase_photos_process import process_one_photo_id as process_photo_with_ai

        payload, status_code = process_photo_with_ai(photo_id)
        return JsonResponse(payload, status=status_code)

        
        try:
            # Chamada interna à função de processamento
            class FakeRequest:
                method = 'POST'
                
            fake_req = FakeRequest()
            result = process_photo_with_ai(fake_req, photo_id)
            
            # Extrai dados da resposta JSON
            result_json = json.loads(result.content.decode('utf-8')) if hasattr(result, 'content') else result.data
            
            logger.info(f"✅ Foto processada: {result_json.get('success', False)}")
            
            return JsonResponse(result_json, status=result.status_code if hasattr(result, 'status_code') else 200)
            
        except Exception as e_process:
            logger.error(f"❌ Erro ao processar foto com IA: {str(e_process)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Erro ao processar: {str(e_process)}',
                'photo_id': photo_id
            }, status=500)

    except json.JSONDecodeError as e:
        logger.error(f"Webhook: JSON inválido: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Webhook: erro inesperado: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
