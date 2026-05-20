import logging
import time
from typing import Any, Dict

from acompanhamentos.api.supabase_client import get_supabase
from acompanhamentos.api.views_supabase_mission_ops import (
    STATUS_MISSAO_ACEITA,
    run_geofence_check_for_mission,
)
from acompanhamentos.api.views_supabase_photos_process import process_one_photo_id

logger = logging.getLogger(__name__)


def processar_fotos_pendentes(photo_limit: int = 20) -> Dict[str, Any]:
    started = time.monotonic()
    limit = max(1, int(photo_limit))

    summary: Dict[str, Any] = {
        "photos_found": 0,
        "photos_ok": 0,
        "photos_fail": 0,
        "photo_failures": [],
    }

    sb = get_supabase()

    # Fotos ainda não processadas pela IA
    not_processed = (
        sb.table("mission_photos")
        .select("id,mission_id,type,created_at,metadata,validation_result")
        .eq("processed", False)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
        .data
        or []
    )

    # Fotos manuais pré-processadas pelo app (processed=true) que ainda não foram
    # sincronizadas com o Django — identificadas por validation_result sem km salvo
    # no Django (o campo is_manual ou source=manual indica entrada manual).
    # Buscamos as recentes (últimas 24h) para evitar reprocessar missões antigas.
    from datetime import datetime, timezone as dt_timezone, timedelta
    cutoff = (datetime.now(dt_timezone.utc) - timedelta(hours=24)).isoformat()
    manual_preproc = (
        sb.table("mission_photos")
        .select("id,mission_id,type,created_at,metadata,validation_result")
        .eq("processed", True)
        .gte("created_at", cutoff)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
        .data
        or []
    )
    # Filtrar apenas as que são realmente manuais, válidas e ainda não sincronizadas com Django
    manual_pending = [
        p for p in manual_preproc
        if (
            (p.get("metadata") or {}).get("source") == "manual"
            or (p.get("metadata") or {}).get("is_manual") is True
            or (p.get("validation_result") or {}).get("is_manual") is True
        )
        and (p.get("validation_result") or {}).get("valid") is True
        and not (p.get("validation_result") or {}).get("django_synced")
    ]

    # IDs já presentes em not_processed para não duplicar
    not_processed_ids = {p.get("id") for p in not_processed}
    pending = not_processed + [p for p in manual_pending if p.get("id") not in not_processed_ids]

    summary["photos_found"] = len(pending)

    for photo in pending:
        photo_id = photo.get("id")
        mission_id = photo.get("mission_id")
        if not photo_id:
            continue

        payload, status_code = process_one_photo_id(photo_id)
        if payload.get("success"):
            summary["photos_ok"] += 1
            continue

        summary["photos_fail"] += 1
        fail_info = {
            "photo_id": photo_id,
            "mission_id": mission_id,
            "status_code": status_code,
            "error": payload.get("error") or payload.get("message") or "erro_desconhecido",
        }
        summary["photo_failures"].append(fail_info)
        logger.warning(
            "monitoramento.photos fail photo_id=%s mission_id=%s status=%s error=%s",
            photo_id,
            mission_id,
            status_code,
            fail_info["error"],
        )

    summary["duration_seconds"] = round(time.monotonic() - started, 3)
    return summary


def processar_geofence(mission_limit: int = 500) -> Dict[str, Any]:
    started = time.monotonic()
    limit = max(1, int(mission_limit))

    summary: Dict[str, Any] = {
        "missions_found": 0,
        "missions_checked": 0,
        "missions_changed": 0,
        "missions_fail": 0,
        "mission_failures": [],
    }

    sb = get_supabase()
    missions = (
        sb.table("missions_control")
        .select("id,status,updated_at")
        .eq("status", STATUS_MISSAO_ACEITA)
        .order("updated_at", desc=False)
        .limit(limit)
        .execute()
        .data
        or []
    )

    summary["missions_found"] = len(missions)

    for mission in missions:
        mission_id = mission.get("id")
        if not mission_id:
            continue

        summary["missions_checked"] += 1
        result = run_geofence_check_for_mission(mission_id)

        if not result.get("success"):
            summary["missions_fail"] += 1
            fail_info = {
                "mission_id": mission_id,
                "error": result.get("error") or "erro_desconhecido",
            }
            summary["mission_failures"].append(fail_info)
            logger.warning(
                "monitoramento.geofence fail mission_id=%s error=%s",
                mission_id,
                fail_info["error"],
            )
            continue

        if result.get("changed"):
            summary["missions_changed"] += 1

    summary["duration_seconds"] = round(time.monotonic() - started, 3)
    return summary


def executar_ciclo_monitoramento(photo_limit: int = 20, mission_limit: int = 500) -> Dict[str, Any]:
    started = time.monotonic()

    photos = processar_fotos_pendentes(photo_limit=photo_limit)
    geofence = processar_geofence(mission_limit=mission_limit)

    return {
        "photos": photos,
        "geofence": geofence,
        "duration_seconds": round(time.monotonic() - started, 3),
    }
