# api/views_supabase_mission_ops.py
"""
Endpoints de operação do ciclo de vida da missão (Supabase + Django sync).

Fluxo completo:
  pendente
    → missao_aceita            (agente aceita pelo deeplink)
    → no_local                 (geofence: agente entrou no raio da origem)
    → odometro_inicio_verificado  (IA valida foto início — via photos_process)
    → teste_panico             (agente clica botão pânico para teste)
    → teste_panico_verificado  (central resolve o pânico-teste)
    → em_andamento             (agente clica "iniciar missão")
    → odometro_final_verificado   (IA valida foto final — via photos_process)
    → concluido                (agente clica "finalizar")
"""

import json
import uuid
import logging
from math import radians, cos, sin, asin, sqrt
from datetime import datetime, timezone as dt_tz

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from .supabase_client import get_supabase, reset_supabase
from acompanhamentos.models import registroacompanhamento

import time
import logging
from .supabase_client import get_supabase, reset_supabase
from datetime import datetime, timezone as dt_timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# Constantes de status
# ══════════════════════════════════════════════════════════
STATUS_PENDENTE = "pendente"
STATUS_MISSAO_ACEITA = "missao_aceita"
STATUS_NO_LOCAL = "no_local"
STATUS_PLACA_INICIO_OK = "placa_inicio_verificada"
STATUS_ODO_INICIO_OK = "odometro_inicio_verificado"
STATUS_TESTE_PANICO = "teste_panico"
STATUS_TESTE_PANICO_VERIFICADO = "teste_panico_verificado"
STATUS_EM_ANDAMENTO = "em_andamento"
STATUS_ODO_FINAL_OK = "odometro_final_verificado"
STATUS_PLACA_FINAL_OK = "placa_final_verificada"
STATUS_CONCLUIDO = "concluido"


# ══════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════
def _ok(payload, status=200):
    return JsonResponse({"success": True, **payload}, status=status)


def _err(msg, status=400, details=None):
    body = {"success": False, "error": msg}
    if details:
        body["details"] = details
    return JsonResponse(body, status=status)


def _now_iso():
    return datetime.now(dt_timezone.utc).isoformat()

def _actor_from_request(request):
    try:
        u = getattr(request, "user", None)
        if u and u.is_authenticated:
            full = (u.get_full_name() or "").strip()
            return full or u.username or str(u.id)
    except Exception:
        pass
    return "anonymous"


def haversine(lat1, lon1, lat2, lon2):
    """Distância em metros entre dois pontos."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371000 * 2 * asin(sqrt(a))


# ══════════════════════════════════════════════════════════
# Supabase helpers com retry automático
# ══════════════════════════════════════════════════════════
def _sb_execute(fn, max_retries=5):
    """
    Executa uma função que usa o Supabase client com retry.
    Ideal para páginas com polling (mapa) que fazem várias requisições seguidas.
    
    IMPORTANTE: Separa erros retentáveis (conexão, socket Windows) de não-retentáveis (schema, validation).
    Isso evita loops infinitos em erros de aplicação, mas permite recovery de erros de rede.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            sb = get_supabase(force_new=(attempt > 0))
            return fn(sb)

        except Exception as e:
            err = str(e).lower()

            # ⚠️ ERROS QUE NÃO DEVEM FAZER RETRY (são erros de aplicação, não de conexão)
            non_retryable = any(k in err for k in [
                "undefined column",      # Schema error
                "column",                # Schema/field error
                "does not exist",        # Schema error
                "syntax error",          # SQL syntax error
                "violates",              # Constraint violation
                "constraint",            # Database constraint
                "foreign key",           # FK error
                "404",                   # Not found
                "401",                   # Unauthorized
                "403",                   # Forbidden
            ])

            if non_retryable:
                logger.error("Non-retryable error (attempt %d): %s", attempt + 1, err)
                raise e from last_exc

            # ✅ ERROS QUE PODEM FAZER RETRY (conexão e socket Windows)
            is_retryable = any(k in err for k in [
                "winerror 10035",        # Windows socket "would block" - RETENTÁVEL
                "connectionstate.closed",
                "localprotocolerror",
                "connection reset",
                "broken pipe",
                "recv_data",
                "server disconnected",
                "timeout",
                "timed out",
                "http2",
                "stream",
                "ssl",
                "429",                   # Rate limit
                "too many requests",
                "readError",             # httpx ReadError (socket timeout)
            ])

            if is_retryable and attempt < max_retries:
                wait_sec = 0.25 * (2 ** attempt)  # Backoff exponencial: 0.25s, 0.5s, 1s, 2s, 4s
                logger.warning(
                    "Supabase error - retrying (attempt %d/%d, wait %.2fs): %s", 
                    attempt + 1, max_retries, wait_sec, err
                )
                reset_supabase()
                last_exc = e
                time.sleep(wait_sec)
                continue

            # Erro desconhecido não-retentável
            logger.warning("Unknown error (no retry, attempt %d): %s", attempt + 1, err)
            raise e from last_exc


def _get_mission(sb, mission_id):
    res = (
        sb.table("missions_control")
        .select("*")
        .eq("id", mission_id)
        .maybe_single()
        .execute()
    )
    return res.data


def _update_supabase_status(sb, mission_id, new_status):
    sb.table("missions_control").update({
        "status": new_status,
        "updated_at": _now_iso(),
    }).eq("id", mission_id).execute()


def _sync_django_status(mission_id, new_status):
    """Sincroniza o status_acompanhamento no Django."""
    try:
        mission_uuid = uuid.UUID(mission_id)
    except ValueError:
        return False

    updated = registroacompanhamento.objects.filter(
        supabase_mission_id=mission_uuid
    ).update(status_acompanhamento=new_status)
    return updated > 0


def _get_django_acompanhamento(mission_id):
    """Busca o acompanhamento Django pelo UUID do Supabase."""
    try:
        mission_uuid = uuid.UUID(mission_id)
    except ValueError:
        return None
    return registroacompanhamento.objects.filter(
        supabase_mission_id=mission_uuid
    ).first()

def _update_django_botao_panico(mission_id, value: bool) -> bool:
    try:
        mission_uuid = uuid.UUID(mission_id)
    except ValueError:
        logger.warning(f"UUID inválido para botao_panico: {mission_id}")
        return False

    updated = registroacompanhamento.objects.filter(
        supabase_mission_id=mission_uuid
    ).update(botao_panico=value)
    
    return updated > 0


def _transition(mission_id, expected_current, new_status):
    """
    Executa uma transição de status validando o status atual.
    Atualiza Supabase + Django. Com retry automático.
    """
    def _do(sb):
        mission = _get_mission(sb, mission_id)
        if not mission:
            return _err("Missão não encontrada no Supabase", status=404)

        current = (mission.get("status") or "").strip()

        if current != expected_current:
            return _err(
                f"Transição inválida: status atual é '{current}', esperado '{expected_current}'",
                status=409,
                details={
                    "current_status": current,
                    "expected_status": expected_current,
                    "requested_status": new_status,
                }
            )

        _update_supabase_status(sb, mission_id, new_status)
        django_synced = _sync_django_status(mission_id, new_status)

        return _ok({
            "mission_id": mission_id,
            "previous_status": current,
            "new_status": new_status,
            "django_synced": django_synced,
            "updated_at": _now_iso(),
        })

    return _sb_execute(_do)


# ══════════════════════════════════════════════════════════
# 1) ACEITAR MISSÃO: pendente → missao_aceita
# ══════════════════════════════════════════════════════════
@csrf_exempt
@require_POST
def sb_mission_accept(request, mission_id):
    return _transition(mission_id, STATUS_PENDENTE, STATUS_MISSAO_ACEITA)


# ══════════════════════════════════════════════════════════
# 2) SALVAR LOCALIZAÇÃO + GEOFENCE
#    missao_aceita + dentro do raio → no_local
# ══════════════════════════════════════════════════════════
# views_supabase_mission_ops.py (apenas o miolo do sb_mission_location)

@csrf_exempt
@require_POST
def sb_mission_location(request, mission_id):
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return _err("JSON inválido", status=400)

    lat = body.get("latitude") or body.get("lat")
    lng = body.get("longitude") or body.get("lng")

    if lat is None or lng is None:
        return _err("latitude e longitude são obrigatórios", status=400)

    lat = float(lat)
    lng = float(lng)

    def _do(sb):
        # 1) Salvar tracking no Supabase
        tracking_payload = {
            "mission_id": mission_id,
            "lat": lat,
            "lng": lng,
            "accuracy": body.get("accuracy"),
            "speed": body.get("speed"),
            "heading": body.get("heading"),
            "timestamp": _now_iso(),
        }

        res = sb.table("mission_tracking").insert(tracking_payload).execute()
        row = (res.data or [{}])[0] if res.data else {}

        # 2) Buscar status atual da missão no Supabase
        mission = _get_mission(sb, mission_id)
        if not mission:
            return _err("Missão não encontrada", status=404)

        current_status = (mission.get("status") or "").strip()

        # 3) Geofence: preferir Supabase (agent_data.geofence)
        geofence_result = None
        status_changed = False
        new_status = None

        agent_data = mission.get("agent_data") or {}
        gf = agent_data.get("geofence") or {}

        lat_orig = gf.get("latitude")
        lng_orig = gf.get("longitude")
        raio = gf.get("raio")

        # fallback: se ainda não tiver geofence no Supabase, usa Django (compatibilidade)
        if (lat_orig is None or lng_orig is None) and current_status == STATUS_MISSAO_ACEITA:
            acomp = _get_django_acompanhamento(mission_id)
            if acomp and acomp.latitude_origem and acomp.longitude_origem:
                lat_orig = float(acomp.latitude_origem)
                lng_orig = float(acomp.longitude_origem)
                raio = int(acomp.raio_cerca or 60)

        if lat_orig is not None and lng_orig is not None:
            lat_orig = float(lat_orig)
            lng_orig = float(lng_orig)
            raio = int(raio or 60)

            distancia = haversine(lat, lng, lat_orig, lng_orig)

            geofence_result = {
                "distance_meters": round(distancia, 2),
                "radius_meters": raio,
                "inside": distancia <= raio,
                "origin_lat": lat_orig,
                "origin_lng": lng_orig,
            }

            # ✅ regra principal: entrou na cerca_origem com missão aceita -> no_local
            if current_status == STATUS_MISSAO_ACEITA and distancia <= raio:
                _update_supabase_status(sb, mission_id, STATUS_NO_LOCAL)
                _sync_django_status(mission_id, STATUS_NO_LOCAL)  # opcional: manter telas Django consistentes
                new_status = STATUS_NO_LOCAL
                status_changed = True

            # (Opcional – igual seu código antigo): se saiu da cerca e estava no_local -> em_andamento
            elif current_status == STATUS_NO_LOCAL and distancia > raio:
                _update_supabase_status(sb, mission_id, STATUS_EM_ANDAMENTO)
                _sync_django_status(mission_id, STATUS_EM_ANDAMENTO)
                new_status = STATUS_EM_ANDAMENTO
                status_changed = True

        return _ok({
            "mission_id": mission_id,
            "tracking_id": row.get("id"),
            "timestamp": tracking_payload["timestamp"],
            "current_status": new_status or current_status,
            "status_changed": status_changed,
            "geofence": geofence_result,
        })

    return _sb_execute(_do)



# ══════════════════════════════════════════════════════════
# 3) ACIONAR PÂNICO (TESTE): odometro_inicio_verificado → teste_panico
# ══════════════════════════════════════════════════════════
@csrf_exempt
@require_POST
def sb_mission_panic_test(request, mission_id):
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    lat = body.get("latitude") or body.get("lat")
    lng = body.get("longitude") or body.get("lng")

    def _do(sb):
        mission = _get_mission(sb, mission_id)
        if not mission:
            return _err("Missão não encontrada", status=404)

        current = (mission.get("status") or "").strip()
        if current != STATUS_ODO_INICIO_OK:
            return _err(
                f"Pânico-teste requer status '{STATUS_ODO_INICIO_OK}', atual: '{current}'",
                status=409,
            )

        panic_payload = {
            "mission_id": mission_id,
            "lat": lat,
            "lng": lng,
            "acknowledged": False,
            "timestamp": _now_iso(),
            "test_mode": True, 
        }
        panic_res = sb.table("panic_alerts").insert(panic_payload).execute()
        panic_row = (panic_res.data or [{}])[0] if panic_res.data else {}

        _update_supabase_status(sb, mission_id, STATUS_TESTE_PANICO)
        django_synced = _sync_django_status(mission_id, STATUS_TESTE_PANICO)

        return _ok({
            "mission_id": mission_id,
            "previous_status": current,
            "new_status": STATUS_TESTE_PANICO,
            "panic_alert": panic_row,
            "django_synced": django_synced,
        })

    return _sb_execute(_do)


# ══════════════════════════════════════════════════════════
# 4) RESOLVER PÂNICO (TESTE): teste_panico → teste_panico_verificado
# ══════════════════════════════════════════════════════════
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib.auth.decorators import login_required

# api/views_supabase_mission_ops.py
# FUNÇÃO CORRIGIDA - sb_mission_panic_resolve
# 
# Substitua a função existente (linhas 388-478) por esta versão
# 
# MUDANÇAS PRINCIPAIS:
# 1. Remove o filtro .eq("acknowledged", False) - agora busca o pânico mais recente independente do status
# 2. Adiciona lógica para verificar se já foi acknowledged (idempotência)
# 3. Se já foi acknowledged, apenas promove o status da missão
# 4. Isso resolve o problema de execução parcial devido a retry do _sb_execute

@csrf_exempt
@require_POST
def sb_mission_panic_resolve(request, mission_id):
    """
    POST /api/supabase/mission/<mission_id>/panic-resolve/

    Regras:
    - Só promove status quando a missão estiver em "teste_panico"
    - Busca o pânico de teste mais recente (test_mode=true)
    - Se já estiver acknowledged, apenas promove o status (idempotência)
    - Ao resolver, grava acknowledged_at e acknowledged_by
    - Depois promove mission.status -> teste_panico_verificado
    - Também tenta sincronizar no Django
    
    CORREÇÃO: Esta versão resolve o problema de execução parcial quando há retry
    de conexão no _sb_execute. Agora a função é idempotente e não falha se o
    pânico já foi marcado como acknowledged.
    """
    def _do(sb):
        username = request.user.get_username() or str(request.user.pk)
        now_iso = _now_iso()

        # 1) Busca missão
        mission_res = (
            sb.table("missions_control")
            .select("id,status,agent_data")
            .eq("id", mission_id)
            .limit(1)
            .execute()
        )
        mission = (mission_res.data or [None])[0]
        if not mission:
            return _err("Missão não encontrada", status=404)

        current_status = mission.get("status")
        if current_status != "teste_panico":
            return _err(
                "A missão não está em teste de pânico. Promoção bloqueada.",
                status=409,
                details={"current_status": current_status}
            )

        # 2) Procura o pânico de TESTE mais recente (independente de estar acknowledged)
        #    ⚠️ MUDANÇA PRINCIPAL: Remove o filtro .eq("acknowledged", False)
        #    Isso garante idempotência se a request foi executada parcialmente
        test_panic_query = (
            sb.table("panic_alerts")
            .select("id,acknowledged,test_mode,acknowledged_at,acknowledged_by")
            .eq("mission_id", mission_id)
            .eq("test_mode", True)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        test_panic_row = (test_panic_query.data or [None])[0]
        
        if not test_panic_row:
            return _err(
                "Não existe pânico de teste para esta missão.",
                status=409
            )

        test_panic_id = test_panic_row.get("id")
        already_acknowledged = test_panic_row.get("acknowledged", False)

        # 3) Se ainda não foi acknowledged, marca agora
        if not already_acknowledged:
            sb.table("panic_alerts").update({
                "acknowledged": True,
                "acknowledged_at": now_iso,
                "acknowledged_by": username,
            }).eq("id", test_panic_id).execute()
            
            ack_info = {
                "acknowledged_at": now_iso,
                "acknowledged_by": username,
            }
        else:
            # ⚠️ IDEMPOTÊNCIA: Já foi acknowledged anteriormente
            # Apenas reutiliza os dados existentes
            ack_info = {
                "acknowledged_at": test_panic_row.get("acknowledged_at"),
                "acknowledged_by": test_panic_row.get("acknowledged_by"),
            }

        # 4) Promove status da missão (sempre executa, mesmo se já estava acknowledged)
        #    ⚠️ CRÍTICO: Esta linha SEMPRE executa, garantindo que o status mude
        new_status = "teste_panico_verificado"
        
        # ⚠️ IMPORTANTE: postgrest-py não suporta .select() após .update()
        # Fazer o update simples e depois validar com um SELECT
        try:
            update_res = (
                sb.table("missions_control")
                .update({"status": new_status})
                .eq("id", mission_id)
                .execute()
            )
            
            # Validar que o UPDATE funcionou fazendo um SELECT
            verify_res = (
                sb.table("missions_control")
                .select("id,status")
                .eq("id", mission_id)
                .limit(1)
                .execute()
            )
            
            verified_rows = verify_res.data or []
            
            if not verified_rows:
                logger.error(
                    f"[CRITICAL] Missão não encontrada após update: mission_id={mission_id}"
                )
                return _err(
                    "Falha ao verificar atualização da missão",
                    status=500,
                    details={"mission_id": mission_id}
                )
            
            verified_status = verified_rows[0].get("status")
            
            if verified_status != new_status:
                logger.error(
                    f"[CRITICAL] Status não foi atualizado: "
                    f"mission_id={mission_id}, "
                    f"expected={new_status}, "
                    f"actual={verified_status}"
                )
                return _err(
                    "Status da missão não foi alterado",
                    status=500,
                    details={
                        "mission_id": mission_id,
                        "expected_status": new_status,
                        "actual_status": verified_status,
                        "hint": "Verifique RLS policies ou constraints em missions_control"
                    }
                )
            
            logger.info(
                f"[SUCCESS] missions_control atualizado: "
                f"mission_id={mission_id}, "
                f"status → {new_status}"
            )
            
        except Exception as e:
            logger.error(f"[CRITICAL] Erro ao atualizar missions_control: {e}")
            raise

        # 5) Tenta sincronizar no Django (status + botao_panico)
        django_botao_panico_updated = False
        try:
            _sync_django_status(mission_id, new_status)
            
            # ✅ NOVO: Atualiza botao_panico = True no Django
            django_botao_panico_updated = _update_django_botao_panico(mission_id, True)
            if django_botao_panico_updated:
                logger.info(f"[SUCCESS] botao_panico=True para mission_id={mission_id}")
            else:
                logger.warning(f"[WARN] Não foi possível atualizar botao_panico para mission_id={mission_id}")
                
        except Exception as e:
            logger.warning(f"Django sync falhou: {e}")
            pass

        return _ok({
            "message": "Teste de pânico confirmado e missão promovida",
            "mission_id": mission_id,
            "new_status": new_status,
            "test_panic_id": test_panic_id,
            "was_already_acknowledged": already_acknowledged,
            "botao_panico_updated": django_botao_panico_updated,
            **ack_info,
        })

    try:
        return _sb_execute(_do)
    except Exception as e:
        return _err("Erro ao promover status", status=500, details=str(e))

# ══════════════════════════════════════════════════════════
# 5) INICIAR MISSÃO: teste_panico_verificado → em_andamento
# ══════════════════════════════════════════════════════════
@csrf_exempt
@require_POST
def sb_mission_start(request, mission_id):
    return _transition(mission_id, STATUS_TESTE_PANICO_VERIFICADO, STATUS_EM_ANDAMENTO)


# ══════════════════════════════════════════════════════════
# 6) CONCLUIR MISSÃO: odometro_final_verificado → concluido
# ══════════════════════════════════════════════════════════
@csrf_exempt
@require_POST
def sb_mission_finish(request, mission_id):
    return _transition(mission_id, STATUS_ODO_FINAL_OK, STATUS_CONCLUIDO)


# ══════════════════════════════════════════════════════════
# PÂNICO REAL (durante em_andamento, não muda status)
# ══════════════════════════════════════════════════════════
@csrf_exempt
@require_POST
def sb_mission_panic_real(request, mission_id):
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    lat = body.get("latitude") or body.get("lat")
    lng = body.get("longitude") or body.get("lng")

    def _do(sb):
        panic_payload = {
            "mission_id": mission_id,
            "lat": lat,
            "lng": lng,
            "acknowledged": False,
            "timestamp": _now_iso(),
        }
        res = sb.table("panic_alerts").insert(panic_payload).execute()
        panic_row = (res.data or [{}])[0] if res.data else {}

        return _ok({
            "mission_id": mission_id,
            "panic_alert": panic_row,
        })

    return _sb_execute(_do)


# ══════════════════════════════════════════════════════════
# GET STATUS COMPLETO (para polling do mapa)
# ══════════════════════════════════════════════════════════
@require_GET
def sb_mission_status(request, mission_id):
    def _do(sb):
        mission = _get_mission(sb, mission_id)
        if not mission:
            return _err("Missão não encontrada", status=404)

        # Tracking count
        tracking_res = (
            sb.table("mission_tracking")
            .select("id")
            .eq("mission_id", mission_id)
            .limit(5000)
            .execute()
        )
        tracking_count = len(tracking_res.data) if tracking_res.data else 0

        # Fotos
        photos_res = (
            sb.table("mission_photos")
            .select("*")
            .eq("mission_id", mission_id)
            .execute()
        )
        photos = [
            {
                "id": p.get("id"),
                "type": p.get("type"),
                "processed": p.get("processed"),
                "validation_result": p.get("validation_result"),
            }
            for p in (photos_res.data or [])
        ]

        # Pânicos
        panics_res = (
            sb.table("panic_alerts")
            .select("*")
            .eq("mission_id", mission_id)
            .order("timestamp", desc=True)
            .limit(10)
            .execute()
        )
        panics = [
            {
                "id": p.get("id"),
                "acknowledged": p.get("acknowledged"),
                "timestamp": p.get("timestamp"),
            }
            for p in (panics_res.data or [])
        ]
        panic_active = any(not p.get("acknowledged", True) for p in panics)

        # Geofence info (do Django)
        geofence = None
        acomp = _get_django_acompanhamento(mission_id)
        if acomp and acomp.latitude_origem and acomp.longitude_origem:
            geofence = {
                "latitude": float(acomp.latitude_origem),
                "longitude": float(acomp.longitude_origem),
                "raio": acomp.raio_cerca or 60,
            }

        return _ok({
            "mission_id": mission_id,
            "status": mission.get("status"),
            "agente": mission.get("agente"),
            "origem": mission.get("origem"),
            "updated_at": mission.get("updated_at"),
            "tracking_count": tracking_count,
            "photos": photos,
            "panic_active": panic_active,
            "panics": panics,
            "geofence": geofence,
        })

    try:
        return _sb_execute(_do)
    except Exception as e:
        logger.exception("Erro em sb_mission_status")
        return _err("Falha ao buscar status da missão", status=500, details=str(e))


@csrf_exempt
@require_GET
def sb_mission_geofence_check(request, mission_id):
    """
    Observa a última localização (mission_tracking) e, se estiver dentro do raio,
    atualiza missions_control.status para no_local.

    IMPORTANTE:
    - Não depende do banco Django.
    - Usa geofence salvo em missions_control.agent_data.geofence.
    """

    def _do(sb):
        # 1) Buscar missão (status + geofence)
        mission = _get_mission(sb, mission_id)
        if not mission:
            return _err("Missão não encontrada no Supabase", status=404)

        current_status = (mission.get("status") or "").strip()
        agent_data = mission.get("agent_data") or {}
        geofence = agent_data.get("geofence") or {}

        lat_orig = geofence.get("latitude")
        lng_orig = geofence.get("longitude")
        raio = geofence.get("raio")

        if lat_orig is None or lng_orig is None:
            return _err(
                "Geofence não configurado em agent_data.geofence",
                status=409,
                details={"agent_data": agent_data},
            )

        # Normaliza tipos
        lat_orig = float(lat_orig)
        lng_orig = float(lng_orig)
        raio = float(raio or 60)

        # 2) Buscar último ponto do tracking
        last_res = (
            sb.table("mission_tracking")
            .select("id,lat,lng,timestamp,created_at")
            .eq("mission_id", mission_id)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        last_rows = last_res.data or []
        if not last_rows:
            return _err("Ainda não há tracking para esta missão", status=409)

        last = last_rows[0]
        lat = last.get("lat")
        lng = last.get("lng")
        if lat is None or lng is None:
            return _err("Último tracking está sem lat/lng", status=409, details={"last": last})

        lat = float(lat)
        lng = float(lng)

        # 3) Calcular distância e decidir
        distancia = haversine(lat, lng, lat_orig, lng_orig)
        inside = distancia <= raio

        changed = False
        new_status = current_status

        # Regra: só sobe para no_local se estiver missao_aceita
        if inside and current_status == STATUS_MISSAO_ACEITA:
            _update_supabase_status(sb, mission_id, STATUS_NO_LOCAL)
            _sync_django_status(mission_id, STATUS_NO_LOCAL)  # se existir vínculo no Django, sincroniza
            changed = True
            new_status = STATUS_NO_LOCAL

        return _ok({
            "mission_id": mission_id,
            "current_status": current_status,
            "new_status": new_status,
            "changed": changed,
            "geofence": {
                "latitude": lat_orig,
                "longitude": lng_orig,
                "raio": raio,
            },
            "last_tracking": {
                "id": last.get("id"),
                "lat": lat,
                "lng": lng,
                "timestamp": last.get("timestamp") or last.get("created_at"),
            },
            "distance_meters": round(distancia, 2),
            "inside": inside,
            "checked_at": _now_iso(),
        })

    try:
        return _sb_execute(_do)
    except Exception as e:
        return _err("Falha ao executar geofence-check", status=500, details=str(e))