# api/views_supabase_read.py
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .supabase_client import get_supabase, reset_supabase

import time
import logging
from .supabase_client import get_supabase, reset_supabase

logger = logging.getLogger(__name__)

def _sb_execute(fn, max_retries=5):
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            sb = get_supabase(force_new=(attempt > 0))
            return fn(sb)
        except Exception as e:
            err = str(e).lower()

            # ⚠️ Erros que NÃO devem fazer retry (são erros de aplicação, não de conexão)
            non_retryable = any(k in err for k in [
                "undefined column",      # Schema error
                "column",                # Schema/field error
                "does not exist",        # Schema error
                "winerror",              # Windows socket error
                "10035",                 # Windows "operation would block"
                "syntax error",          # SQL syntax error
                "violates",              # Constraint violation
                "constraint",            # Database constraint
                "foreign key",           # FK error
                "not found",             # Resource doesn't exist
                "404",                   # Not found
                "401",                   # Unauthorized
                "403",                   # Forbidden
            ])

            if non_retryable:
                logger.error("Non-retryable error (attempt %d): %s", attempt + 1, err)
                raise e from last_exc

            is_conn_err = any(k in err for k in [
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
                "429",
                "too many requests",
            ])

            if is_conn_err and attempt < max_retries:
                logger.warning("Supabase conn error (attempt %d/%d): %s", attempt+1, max_retries, err)
                reset_supabase()
                last_exc = e
                time.sleep(0.15 * (attempt + 1))
                continue

            logger.warning("Unknown error (no retry, attempt %d): %s", attempt + 1, err)
            raise e from last_exc



def _ok(payload, status=200):
    return JsonResponse({"success": True, **payload}, status=status, safe=True)


def _err(message, status=500, details=None):
    data = {"success": False, "error": message}
    if details:
        data["details"] = details
    return JsonResponse(data, status=status)


def _to_int(value, default=200, min_value=1, max_value=5000):
    try:
        v = int(value)
    except Exception:
        v = default
    v = max(min_value, min(v, max_value))
    return v


# ==========================================================
# GET /api/supabase/missions_control/
# Retorna todas as missões
# ==========================================================
@require_GET
def sb_missions_control_list(request):
    def _do(sb):
        limit = _to_int(request.GET.get("limit"), default=500)
        order_by = request.GET.get("order_by") or "created_at"
        desc = (request.GET.get("desc") or "true").lower() == "true"

        q = (
            sb.table("missions_control")
            .select("*")
            .order(order_by, desc=desc)
            .limit(limit)
        )

        status = request.GET.get("status")
        if status:
            q = q.eq("status", status)

        mission_id = request.GET.get("id")
        if mission_id:
            q = q.eq("id", mission_id)

        res = q.execute()
        rows = res.data or []

        return _ok({
            "table": "missions_control",
            "count": len(rows),
            "rows": rows,
        })

    try:
        return _sb_execute(_do)
    except Exception as e:
        return _err("Falha ao buscar missions_control no Supabase", details=str(e))


# ==========================================================
# GET /api/supabase/mission_tracking/
# Retorna todas as localizações (tracking)
# ==========================================================
@require_GET
def sb_mission_tracking_list(request):
    def _do(sb):
        limit = _to_int(request.GET.get("limit"), default=2000)
        order_by = request.GET.get("order_by") or "timestamp"
        desc = (request.GET.get("desc") or "false").lower() == "true"

        q = (
            sb.table("mission_tracking")
            .select("*")
            .order(order_by, desc=desc)
            .limit(limit)
        )

        mission_id = request.GET.get("mission_id")
        if mission_id:
            q = q.eq("mission_id", mission_id)

        after = request.GET.get("after")
        before = request.GET.get("before")
        if after:
            q = q.gte("timestamp", after)
        if before:
            q = q.lte("timestamp", before)

        res = q.execute()
        rows = res.data or []

        return _ok({
            "table": "mission_tracking",
            "count": len(rows),
            "rows": rows,
        })

    try:
        return _sb_execute(_do)
    except Exception as e:
        return _err("Falha ao buscar mission_tracking no Supabase", details=str(e))


# ==========================================================
# GET /api/supabase/mission_photos/
# Retorna todas as fotos
# ==========================================================
@require_GET
def sb_mission_photos_list(request):
    def _do(sb):
        limit = _to_int(request.GET.get("limit"), default=1000)
        order_by = request.GET.get("order_by") or "uploaded_at"
        desc = (request.GET.get("desc") or "false").lower() == "true"

        q = (
            sb.table("mission_photos")
            .select("*")
            .order(order_by, desc=desc)
            .limit(limit)
        )

        mission_id = request.GET.get("mission_id")
        if mission_id:
            q = q.eq("mission_id", mission_id)

        photo_type = request.GET.get("type")
        if photo_type:
            q = q.eq("type", photo_type)

        processed = request.GET.get("processed")
        if processed is not None:
            processed_bool = (processed.lower() == "true")
            q = q.eq("processed", processed_bool)

        res = q.execute()
        rows = res.data or []

        return _ok({
            "table": "mission_photos",
            "count": len(rows),
            "rows": rows,
        })

    try:
        return _sb_execute(_do)
    except Exception as e:
        return _err("Falha ao buscar mission_photos no Supabase", details=str(e))


# ==========================================================
# GET /api/supabase/full/?mission_id=<uuid>
# Retorna mission + tracking + photos
# ==========================================================
@require_GET
def sb_mission_full(request):
    def _do(sb):
        mission_id = request.GET.get("mission_id")
        if not mission_id:
            return _err("Parâmetro mission_id é obrigatório", status=400)

        tracking_limit = _to_int(request.GET.get("tracking_limit"), default=2000, min_value=1, max_value=5000)
        photos_limit = _to_int(request.GET.get("photos_limit"), default=500, min_value=1, max_value=2000)

        after = request.GET.get("after")
        before = request.GET.get("before")

        mission_res = (
            sb.table("missions_control")
            .select("*")
            .eq("id", mission_id)
            .maybe_single()
            .execute()
        )
        mission = mission_res.data
        if not mission:
            return _err("Missão não encontrada (missions_control)", status=404)

        tracking_q = (
            sb.table("mission_tracking")
            .select("*")
            .eq("mission_id", mission_id)
            .order("timestamp", desc=False)
            .limit(tracking_limit)
        )
        if after:
            tracking_q = tracking_q.gte("timestamp", after)
        if before:
            tracking_q = tracking_q.lte("timestamp", before)

        tracking_res = tracking_q.execute()
        tracking_rows = tracking_res.data or []

        photos_res = (
            sb.table("mission_photos")
            .select("*")
            .eq("mission_id", mission_id)
            .order("uploaded_at", desc=False)
            .limit(photos_limit)
            .execute()
        )
        photo_rows = photos_res.data or []

        return _ok({
            "endpoint": "supabase_full",
            "mission_id": mission_id,
            "mission": mission,
            "tracking": {
                "count": len(tracking_rows),
                "limit": tracking_limit,
                "after": after,
                "before": before,
                "rows": tracking_rows,
            },
            "photos": {
                "count": len(photo_rows),
                "limit": photos_limit,
                "rows": photo_rows,
            },
        })

    try:
        return _sb_execute(_do)
    except Exception as e:
        return _err("Falha ao buscar FULL no Supabase", status=500, details=str(e))


from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

# ==========================================================
# GET /api/supabase/panic_alerts/?mission_id=<uuid>&limit=500
# ==========================================================
@require_GET
def sb_panic_alerts_list(request):
    def _do(sb):
        limit = _to_int(request.GET.get("limit"), default=500, min_value=1, max_value=5000)
        mission_id = request.GET.get("mission_id")

        q = (
            sb.table("panic_alerts")
            .select("*")
            .order("timestamp", desc=True)
            .limit(limit)
        )

        if mission_id:
            q = q.eq("mission_id", mission_id)

        res = q.execute()
        rows = res.data or []

        panic_active = any((r.get("acknowledged") is False) for r in rows)
        open_panic = next((r for r in rows if r.get("acknowledged") is False), None)

        return _ok({
            "table": "panic_alerts",
            "count": len(rows),
            "panic_active": panic_active,
            "open_panic": open_panic,
            "rows": rows
        })

    try:
        return _sb_execute(_do)
    except Exception as e:
        return _err("Falha ao buscar panic_alerts no Supabase", status=500, details=str(e))


# ==========================================================
# POST /api/supabase/panic_alerts/<panic_id>/ack/
# Marca acknowledged=true
# ==========================================================
from datetime import datetime, timezone as dt_timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

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


from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
@csrf_exempt
@require_POST
@login_required
def sb_panic_ack(request, panic_id):
    """
    POST /api/supabase/panic_alerts/<panic_id>/ack/
    Marca:
      - acknowledged=true
      - acknowledged_at=agora
      - acknowledged_by=user do Django
    """
    def _do(sb):
        username = request.user.get_username() or str(request.user.pk)

        payload = {
            "acknowledged": True,
            "acknowledged_at": timezone.now().isoformat(),
            "acknowledged_by": username,
        }

        res = (
            sb.table("panic_alerts")
            .update(payload)
            .eq("id", panic_id)
            .execute()
        )

        return _ok({
            "message": "Pânico marcado como acknowledged",
            "panic_id": panic_id,
            "acknowledged_by": username,
            "acknowledged_at": payload["acknowledged_at"],
            "updated": res.data or [],
        })

    try:
        return _sb_execute(_do)
    except Exception as e:
        return _err("Falha ao marcar pânico como acknowledged", status=500, details=str(e))
