import logging
import os
import time

from celery import shared_task

from acompanhamentos.services.monitoramento_service import (
    executar_ciclo_monitoramento,
    processar_fotos_pendentes,
    processar_geofence,
)
from acompanhamentos.api.views_supabase_photos_process import process_one_photo_id

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    rate_limit=os.getenv("CELERY_PHOTO_SINGLE_RATE_LIMIT", "120/m"),
)
def processar_foto_task(self, photo_id: str, force: bool = False):
    started = time.monotonic()
    payload, status_code = process_one_photo_id(photo_id, force=force)

    result = {
        "task_id": self.request.id,
        "queue": "monitoramento.photos",
        "photo_id": photo_id,
        "force": bool(force),
        "status_code": status_code,
        "success": bool(payload.get("success")),
        "message": payload.get("message") or payload.get("error") or "",
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    if not result["success"]:
        logger.warning(
            "task=processar_foto_task task_id=%s status=fail photo_id=%s http_status=%s error=%s duration=%s",
            result["task_id"],
            photo_id,
            status_code,
            result["message"],
            result["duration_seconds"],
        )
    else:
        logger.info(
            "task=processar_foto_task task_id=%s status=ok photo_id=%s http_status=%s duration=%s",
            result["task_id"],
            photo_id,
            status_code,
            result["duration_seconds"],
        )

    return {**result, "payload": payload}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    rate_limit=os.getenv("CELERY_PHOTOS_RATE_LIMIT", "30/m"),
)
def processar_fotos_pendentes_task(self, photo_limit: int | None = None):
    started = time.monotonic()
    limit = max(1, int(photo_limit or _env_int("MONITORAMENTO_PHOTO_LIMIT", 20)))

    summary = processar_fotos_pendentes(photo_limit=limit)
    payload = {
        "task_id": self.request.id,
        "queue": "monitoramento.photos",
        "photo_limit": limit,
        "status": "ok",
        **summary,
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    logger.info(
        "task=processar_fotos_pendentes_task task_id=%s status=ok photos_ok=%s photos_fail=%s duration=%s",
        payload["task_id"],
        payload["photos_ok"],
        payload["photos_fail"],
        payload["duration_seconds"],
    )
    return payload


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    rate_limit=os.getenv("CELERY_GEOFENCE_RATE_LIMIT", "60/m"),
)
def processar_geofence_task(self, mission_limit: int | None = None):
    started = time.monotonic()
    limit = max(1, int(mission_limit or _env_int("MONITORAMENTO_MISSION_LIMIT", 500)))

    summary = processar_geofence(mission_limit=limit)
    payload = {
        "task_id": self.request.id,
        "queue": "monitoramento.geofence",
        "mission_limit": limit,
        "status": "ok",
        **summary,
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    logger.info(
        "task=processar_geofence_task task_id=%s status=ok missions_checked=%s missions_changed=%s missions_fail=%s duration=%s",
        payload["task_id"],
        payload["missions_checked"],
        payload["missions_changed"],
        payload["missions_fail"],
        payload["duration_seconds"],
    )
    return payload


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    rate_limit=os.getenv("CELERY_ORQUESTRADOR_RATE_LIMIT", "120/m"),
)
def ciclo_monitoramento_task(self, photo_limit: int | None = None, mission_limit: int | None = None, dispatch_only: bool = True):
    started = time.monotonic()
    p_limit = max(1, int(photo_limit or _env_int("MONITORAMENTO_PHOTO_LIMIT", 20)))
    m_limit = max(1, int(mission_limit or _env_int("MONITORAMENTO_MISSION_LIMIT", 500)))

    if dispatch_only:
        photos_async = processar_fotos_pendentes_task.delay(photo_limit=p_limit)
        geofence_async = processar_geofence_task.delay(mission_limit=m_limit)
        payload = {
            "task_id": self.request.id,
            "queue": "monitoramento.orquestrador",
            "status": "enqueued",
            "photo_limit": p_limit,
            "mission_limit": m_limit,
            "photos_task_id": photos_async.id,
            "geofence_task_id": geofence_async.id,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        logger.info(
            "task=ciclo_monitoramento_task task_id=%s status=enqueued photos_task_id=%s geofence_task_id=%s duration=%s",
            payload["task_id"],
            payload["photos_task_id"],
            payload["geofence_task_id"],
            payload["duration_seconds"],
        )
        return payload

    summary = executar_ciclo_monitoramento(photo_limit=p_limit, mission_limit=m_limit)
    payload = {
        "task_id": self.request.id,
        "queue": "monitoramento.orquestrador",
        "status": "ok",
        "photo_limit": p_limit,
        "mission_limit": m_limit,
        **summary,
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    logger.info(
        "task=ciclo_monitoramento_task task_id=%s status=ok photos_ok=%s photos_fail=%s missions_changed=%s missions_fail=%s duration=%s",
        payload["task_id"],
        payload["photos"]["photos_ok"],
        payload["photos"]["photos_fail"],
        payload["geofence"]["missions_changed"],
        payload["geofence"]["missions_fail"],
        payload["duration_seconds"],
    )
    return payload
