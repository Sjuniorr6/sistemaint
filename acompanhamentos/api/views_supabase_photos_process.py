# api/views_supabase_photos_process.py
import os
import threading
import uuid
from datetime import datetime, timezone as dt_timezone
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive, make_aware
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .odometer_ai import validate_odometer_with_ai
from .supabase_client import get_supabase
from acompanhamentos.models import registroacompanhamento, registroacompanhamentoagente
from django.views.decorators.http import require_POST, require_GET
import json
import logging
logger = logging.getLogger(__name__)

# ==========================================================
# Helpers de resposta
# ==========================================================
def _ok(payload, status=200):
    return JsonResponse({"success": True, **payload}, status=status)


def _err(message, status=400, details=None):
    data = {"success": False, "error": message}
    if details:
        data["details"] = details
    return JsonResponse(data, status=status)


def _now_iso():
    return datetime.now(dt_timezone.utc).isoformat()

def _sync_django_status(mission_id: str, new_status: str) -> bool:
    try:
        mission_uuid = uuid.UUID(mission_id)
    except ValueError:
        logger.warning(f"UUID inválido para sync django: {mission_id}")
        return False

    updated = registroacompanhamento.objects.filter(
        supabase_mission_id=mission_uuid
    ).update(status_acompanhamento=new_status)

    if updated:
        logger.info(f"Django status_acompanhamento → {new_status} (mission={mission_id})")
    else:
        logger.warning(f"Django sync: nenhum acompanhamento encontrado para mission={mission_id}")

    return updated > 0

def _parse_ts_to_dt(ts_value):
    """
    Converte timestamp ISO/string para datetime aware (UTC), quando possível.
    Se não conseguir, retorna None.
    """
    if not ts_value:
        return None

    # Se já veio datetime
    if isinstance(ts_value, datetime):
        dt = ts_value
        if is_naive(dt):
            dt = make_aware(dt, dt_timezone.utc)
        return dt

    # Se veio string ISO
    if isinstance(ts_value, str):
        dt = parse_datetime(ts_value)
        if dt is None:
            return None
        if is_naive(dt):
            dt = make_aware(dt, dt_timezone.utc)
        return dt

    return None


def _normalize_issues_list(raw_issues):
    """
    Garante que o campo `issues` seja sempre uma lista serializável.
    Evita erro de concatenação quando a origem grava `issues=None`.
    """
    if raw_issues is None:
        return []

    if isinstance(raw_issues, list):
        return [str(item) for item in raw_issues if item is not None]

    if isinstance(raw_issues, tuple):
        return [str(item) for item in raw_issues if item is not None]

    return [str(raw_issues)]


def _append_issue(vr: dict, issue: str) -> None:
    issues = _normalize_issues_list(vr.get("issues"))
    issues.append(issue)
    vr["issues"] = issues


# ==========================================================
# Storage / Temp file
# ==========================================================
def _download_storage_bytes(sb, storage_path: str) -> bytes:
    bucket = settings.SUPABASE_STORAGE_BUCKET
    return sb.storage.from_(bucket).download(storage_path)


def _save_tmp_file(filename: str, content: bytes) -> str:
    abs_dir = settings.MISSION_PHOTOS_TMP_ABS
    os.makedirs(abs_dir, exist_ok=True)

    safe_name = filename.replace("/", "_").replace("\\", "_")
    abs_path = os.path.join(abs_dir, safe_name)

    with open(abs_path, "wb") as f:
        f.write(content)

    return abs_path


def _remove_file_silent(abs_path: str):
    try:
        if abs_path and os.path.exists(abs_path):
            os.remove(abs_path)
    except Exception:
        pass


# ==========================================================
# Regras de transição de status (Supabase missions_control)
# ==========================================================
STATUS_PENDENTE = "pendente"
STATUS_MISSAO_ACEITA = "missao_aceita"
STATUS_NO_LOCAL = "no_local"
STATUS_ODO_INICIO_OK = "odometro_inicio_verificado"
STATUS_TESTE_PANICO = "teste_panico"
STATUS_TESTE_PANICO_OK = "teste_panico_verificado"
STATUS_EM_ANDAMENTO = "em_andamento"
STATUS_ODO_FINAL_OK = "odometro_final_verificado"
STATUS_CONCLUIDO = "concluido"

# Regras de transição atualizadas (v2.6.0)


def _get_mission(sb, mission_id: str) -> dict:
    res = (
        sb.table("missions_control")
        .select("*")
        .eq("id", mission_id)
        .maybe_single()
        .execute()
    )
    return res.data or {}


def _supabase_update_status(sb, mission_id: str, new_status: str) -> None:
    """
    Atualiza apenas o status da missão no Supabase.
    """
    sb.table("missions_control").update({"status": new_status}).eq("id", mission_id).execute()


# ==========================================================
# Django: localizar acompanhamento pelo mission_id do Supabase
# ==========================================================
def _model_has_field(model_cls, field_name: str) -> bool:
    try:
        model_cls._meta.get_field(field_name)
        return True
    except Exception:
        return False




def _find_acompanhamento_by_supabase_mission_id(mission_id: str):
    try:
        mission_uuid = uuid.UUID(mission_id)
    except Exception:
        return None

    return registroacompanhamento.objects.filter(
        supabase_mission_id=mission_uuid
    ).first()


def _get_vinculo_by_mission_id(mission_id: str, for_update: bool = False):
    """
    Busca o vínculo (agente principal) da missão de forma determinística.
    Quando for_update=True, aplica lock transacional no registro do vínculo.
    """
    try:
        mission_uuid = uuid.UUID(mission_id)
    except Exception:
        return None

    qs = registroacompanhamentoagente.objects.filter(
        acompanhamento__supabase_mission_id=mission_uuid
    )

    if for_update:
        qs = qs.select_for_update()

    return qs.filter(tipo_agente="principal").first() or qs.order_by("id").first()


def _get_principal_vinculo(acompanhamento):
    if not acompanhamento:
        return None
    return (
        acompanhamento.agentes.filter(tipo_agente="principal").first()
        or acompanhamento.agentes.first()
    )


def _is_pronta_resposta(acompanhamento, vinculo=None):
    """Retorna True quando o tipo de atendimento é pronta_resposta."""
    try:
        tipo_obj = (getattr(vinculo, "tipo_servico", None) if vinculo else None) or getattr(acompanhamento, "tipo_servico", None)
        tipo_cadastro = (getattr(tipo_obj, "tipo_cadastro", "") or "").strip().lower()
        return tipo_cadastro == "pronta_resposta"
    except Exception:
        return False


def _resolve_km_estimado_referencia(acompanhamento, vinculo=None):
    """
    Decide qual km estimado usar na validação do odômetro final.
    Preferência por tipo de serviço (MOTO/CARRO). Se não for possível inferir,
    usa o maior entre os estimados disponíveis para evitar bloqueio indevido.
    """
    if not acompanhamento:
        return None, None

    km_carro_raw = getattr(acompanhamento, "km_estimado_carro", None)
    km_moto_raw = getattr(acompanhamento, "km_estimado_moto", None)

    try:
        km_carro = float(km_carro_raw) if km_carro_raw is not None else None
    except Exception:
        km_carro = None

    try:
        km_moto = float(km_moto_raw) if km_moto_raw is not None else None
    except Exception:
        km_moto = None

    tipo_codigo = ""
    try:
        tipo_obj = (getattr(vinculo, "tipo_servico", None) if vinculo else None) or getattr(acompanhamento, "tipo_servico", None)
        tipo_codigo = (getattr(tipo_obj, "codigo", "") or "").upper()
    except Exception:
        tipo_codigo = ""

    if "MOTO" in tipo_codigo and km_moto is not None:
        return km_moto, "moto"
    if "CARRO" in tipo_codigo and km_carro is not None:
        return km_carro, "carro"

    if km_moto is not None and km_carro is None:
        return km_moto, "moto"
    if km_carro is not None and km_moto is None:
        return km_carro, "carro"
    if km_carro is not None and km_moto is not None:
        return max(km_carro, km_moto), "fallback_max"

    return None, None


def _parse_int_or_none(value):
    try:
        return int(value)
    except Exception:
        return None


def _get_km_inicio_from_mission_photos(sb, mission_id: str):
    """
    Fallback: lê o odômetro inicial já validado em mission_photos quando
    km_inicio não foi persistido no Django por qualquer inconsistência.
    """
    try:
        rows = (
            sb.table("mission_photos")
            .select("id,created_at,validation_result")
            .eq("mission_id", mission_id)
            .eq("type", "odometro_inicio")
            .eq("processed", True)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
            .data
            or []
        )
    except Exception:
        return None, None

    for row in rows:
        vr = row.get("validation_result") or {}
        if not isinstance(vr, dict):
            continue

        km_inicio = _parse_int_or_none(vr.get("odometer_raw"))
        if km_inicio is not None:
            return km_inicio, row.get("id")

    return None, None


def _maybe_backfill_km_inicio_django(mission_id: str, km_inicio: int, ts_iso, photo_id: str, confidence: float):
    """
    Tenta gravar km_inicio no Django via caminho oficial.
    Não bloqueia o fluxo principal se falhar.
    """
    try:
        acompanhamento = _find_acompanhamento_by_supabase_mission_id(mission_id)
        return _update_django_km(
            acompanhamento=acompanhamento,
            photo_type="odometro_inicio",
            odo_raw=km_inicio,
            ts_iso=ts_iso,
            photo_id=photo_id,
            confidence=confidence,
            mission_id=mission_id,
        )
    except Exception as exc:
        logger.warning(
            "[KM_BACKFILL] mission_id=%s photo_id=%s km_inicio=%s erro=%s",
            mission_id,
            photo_id,
            km_inicio,
            str(exc),
        )
        return {"updated": False, "reason": f"km_inicio_backfill_failed({exc})"}



def _update_django_km(acompanhamento, photo_type: str, odo_raw, ts_iso, photo_id: str, confidence: float, mission_id: str = None, is_manual: bool = False):
    """
    Salva KM no SEU BANCO (Django), preferencialmente no agente principal (registroacompanhamentoagente).
    Não salva no Supabase.

    Campos esperados (baseado no seu model):
    - registroacompanhamentoagente: km_inicio, data_km_inicio, km_final, data_km_final
    
    photo_type: "odometro_inicio" ou "odometro_final"
    """
    if mission_id:
        vinculo = _get_vinculo_by_mission_id(mission_id, for_update=True)
        if not vinculo and acompanhamento:
            vinculo = (
                acompanhamento.agentes.select_for_update().filter(tipo_agente="principal").first()
                or acompanhamento.agentes.select_for_update().order_by("id").first()
            )

        if not vinculo:
            return {
                "updated": False,
                "reason": "no_agente_vinculado_for_mission",
                "mission_id": mission_id,
            }

        acompanhamento = vinculo.acompanhamento
    else:
        if not acompanhamento:
            return {"updated": False, "reason": "acompanhamento_not_found_in_django"}

        vinculo = (
            acompanhamento.agentes.select_for_update().filter(tipo_agente="principal").first()
            or acompanhamento.agentes.select_for_update().order_by("id").first()
        )

    if not vinculo:
        return {"updated": False, "reason": "no_agente_vinculado"}

    dt = _parse_ts_to_dt(ts_iso)

    # Só salva se odômetro veio numérico
    if odo_raw is None:
        return {"updated": False, "reason": "odometer_raw_is_none"}

    # Garante int quando vier string numérica
    try:
        odo_int = int(odo_raw)
    except Exception:
        return {"updated": False, "reason": "odometer_raw_not_int"}

    # Atualiza conforme tipo
    update_fields = []
    if photo_type == "odometro_inicio":
        vinculo.km_inicio = odo_int
        update_fields.append("km_inicio")
        if hasattr(vinculo, "data_km_inicio"):
            vinculo.data_km_inicio = dt
            update_fields.append("data_km_inicio")
        if is_manual and hasattr(vinculo, "km_inicio_manual"):
            vinculo.km_inicio_manual = True
            update_fields.append("km_inicio_manual")

    elif photo_type == "odometro_final":
        vinculo.km_final = odo_int
        update_fields.append("km_final")
        if hasattr(vinculo, "data_km_final"):
            vinculo.data_km_final = dt
            update_fields.append("data_km_final")
        if is_manual and hasattr(vinculo, "km_final_manual"):
            vinculo.km_final_manual = True
            update_fields.append("km_final_manual")

    else:
        return {"updated": False, "reason": f"invalid_photo_type({photo_type})"}

    vinculo.save(update_fields=update_fields)

    logger.info(
        "[KM_SAVE] mission_id=%s acompanhamento_id=%s vinculo_id=%s photo_type=%s odometer_raw=%s photo_id=%s",
        mission_id or str(getattr(acompanhamento, "supabase_mission_id", "")),
        getattr(acompanhamento, "id", None),
        getattr(vinculo, "id", None),
        photo_type,
        odo_int,
        photo_id,
    )

    return {
        "updated": True,
        "mission_id": mission_id or str(getattr(acompanhamento, "supabase_mission_id", "")),
        "acompanhamento_id": getattr(acompanhamento, "id", None),
        "vinculo_id": getattr(vinculo, "id", None),
        "photo_type": photo_type,
        "odometer_raw": odo_int,
        "timestamp": ts_iso,
        "photo_id": photo_id,
        "confidence": confidence,
        "updated_fields": update_fields,
    }


def _update_django_datetime_inicio_fim(acompanhamento, tipo: str, ts_iso=None):
    """
    Grava data/horário de início ou finalização no agente principal.
    
    tipo: "inicio" → data_inicio + horario_inicio
          "finalizacao" → data_finalizacao + horario_finalizacao
    
    Usa o timestamp informado quando disponível; caso contrário, usa o horário atual.
    """
    if not acompanhamento:
        return

    vinculo = (
        acompanhamento.agentes.filter(tipo_agente="principal").first()
        or acompanhamento.agentes.first()
    )
    if not vinculo:
        return

    from django.utils import timezone as dj_tz
    agora = _parse_ts_to_dt(ts_iso)
    if agora is None:
        agora = dj_tz.now()
    agora = dj_tz.localtime(agora)  # converte para timezone local (settings.TIME_ZONE)

    update_fields = []

    if tipo == "inicio":
        if vinculo.data_inicio and vinculo.horario_inicio:
            return
        vinculo.data_inicio = agora.date()
        vinculo.horario_inicio = agora.time()
        update_fields = ["data_inicio", "horario_inicio"]
    elif tipo == "finalizacao":
        if vinculo.data_finalizacao and vinculo.horario_finalizacao:
            return
        vinculo.data_finalizacao = agora.date()
        vinculo.horario_finalizacao = agora.time()
        update_fields = ["data_finalizacao", "horario_finalizacao"]
    else:
        return

    vinculo.save(update_fields=update_fields)


# ==========================================================
# Orquestração: regras finais (status + km/placa)
# ==========================================================
def _apply_photo_rules(sb, mission_id: str, photo_type: str, vr: dict, is_manual: bool = False) -> dict:
    """
    Regras finais:
    - odometro_inicio: status atual precisa ser NO_LOCAL e valid=True -> status=ODO_INICIO_OK + salva km no Django
    - odometro_final: status atual precisa ser EM_ANDAMENTO e valid=True -> status=ODO_FINAL_OK + salva km no Django
    """
    mission = _get_mission(sb, mission_id)
    if not mission:
        return {"updated": False, "reason": "mission_not_found"}

    current_status = (mission.get("status") or "").strip()
    is_valid = bool(vr.get("valid"))
    ts = vr.get("timestamp")
    photo_id = vr.get("_photo_id")
    confidence = float(vr.get("confidence", 0.0))

    # ==================================================
    # ODÔMETRO INÍCIO
    # ==================================================
    if photo_type == "odometro_inicio":
        odo_raw = vr.get("odometer_raw")

        if not is_valid:
            return {
                "updated": False,
                "reason": "odometro_inicio_invalid",
                "current_status": current_status,
                "valid": is_valid,
            }

        # 1) Sempre salva KM no Django se a foto for válida
        with transaction.atomic():
            acompanhamento = _find_acompanhamento_by_supabase_mission_id(mission_id)
            django_info = _update_django_km(
                acompanhamento=acompanhamento,
                photo_type="odometro_inicio",
                odo_raw=odo_raw,
                ts_iso=ts,
                photo_id=photo_id,
                confidence=confidence,
                mission_id=mission_id,
                is_manual=is_manual,
            )
            _update_django_datetime_inicio_fim(acompanhamento, "inicio", ts_iso=ts)

        if not django_info.get("updated"):
            fail_reason = django_info.get("reason", "desconhecido")
            logger.error(
                "[KM_SAVE_FAIL] odometro_inicio mission_id=%s photo_id=%s reason=%s django_info=%s",
                mission_id, photo_id, fail_reason, django_info,
            )
            vr["django_km_error"] = fail_reason
            vr["django_km_info"] = django_info
            sb.table("mission_photos").update({"validation_result": vr}).eq("id", photo_id).execute()
            return {
                "updated": False,
                "reason": "django_km_update_failed",
                "current_status": current_status,
                "django_km_update": django_info,
            }

        # 2) Avança status apenas se estiver no status esperado
        if current_status == STATUS_NO_LOCAL:
            _supabase_update_status(sb, mission_id, STATUS_ODO_INICIO_OK)
            _sync_django_status(mission_id, STATUS_ODO_INICIO_OK)
            new_status = STATUS_ODO_INICIO_OK
        else:
            logger.info(
                "[STATUS_SKIP] odometro_inicio KM salvo mas status não avançou "
                "(status atual=%s, esperado=%s) mission_id=%s",
                current_status, STATUS_NO_LOCAL, mission_id,
            )
            new_status = current_status

        return {
            "updated": True,
            "previous_status": current_status,
            "new_status": new_status,
            "django_km_update": django_info,
        }

    # ==================================================
    # ODÔMETRO FINAL (ATUALIZADO v2.6.0)
    # ==================================================
    elif photo_type == "odometro_final":
        odo_raw = vr.get("odometer_raw")

        if not is_valid:
            return {
                "updated": False,
                "reason": "odometro_final_invalid",
                "current_status": current_status,
                "valid": is_valid,
            }

        acompanhamento = _find_acompanhamento_by_supabase_mission_id(mission_id)
        vinculo = _get_principal_vinculo(acompanhamento)

        km_inicio = getattr(vinculo, "km_inicio", None) if vinculo else None
        try:
            km_final = int(odo_raw)
        except Exception:
            km_final = None

        if km_inicio is None:
            km_inicio_fallback, km_inicio_fallback_photo_id = _get_km_inicio_from_mission_photos(sb, mission_id)
            if km_inicio_fallback is not None:
                km_inicio = km_inicio_fallback
                vr["km_inicio_fallback_from_photo_id"] = km_inicio_fallback_photo_id
                vr["km_inicio_fallback_source"] = "mission_photos.odometro_inicio.validation_result.odometer_raw"

                # Tenta reconciliar persistência no Django para não falhar em fluxos futuros.
                _maybe_backfill_km_inicio_django(
                    mission_id=mission_id,
                    km_inicio=km_inicio_fallback,
                    ts_iso=ts,
                    photo_id=photo_id,
                    confidence=confidence,
                )

        if km_inicio is None or km_final is None:
            vr["valid"] = False
            _append_issue(vr, "km_validacao_indisponivel(km_inicio_ou_km_final_ausente)")
            sb.table("mission_photos").update({"validation_result": vr}).eq("id", photo_id).execute()
            return {
                "updated": False,
                "reason": "km_validation_unavailable",
                "current_status": current_status,
                "km_inicio": km_inicio,
                "km_final": km_final,
            }

        km_total = km_final - int(km_inicio)
        if km_total < 0:
            vr["valid"] = False
            _append_issue(vr, "km_total_negativo(km_final_menor_que_km_inicio)")
            vr["km_total_calculado"] = km_total
            sb.table("mission_photos").update({"validation_result": vr}).eq("id", photo_id).execute()
            return {
                "updated": False,
                "reason": "km_total_negative",
                "current_status": current_status,
                "km_inicio": km_inicio,
                "km_final": km_final,
                "km_total": km_total,
            }

        km_estimado_ref, km_estimado_source = _resolve_km_estimado_referencia(acompanhamento, vinculo)
        vr["km_inicio"] = int(km_inicio)
        vr["km_final"] = km_final
        vr["km_total_calculado"] = km_total
        if km_estimado_ref is None:
            # Sem km estimado cadastrado: mantém validação por consistência
            # (km_total >= 0) e apenas anota warning, sem bloquear o fluxo.
            _append_issue(vr, "km_estimado_ausente_para_validacao")
            vr["km_validacao_estimado_aplicada"] = False
            logger.info(
                "[KM_VALIDACAO] mission_id=%s photo_id=%s total=%s sem_km_estimado (fluxo permitido)",
                mission_id,
                photo_id,
                km_total,
            )
        else:
            tolerancia_km = 1000
            km_maximo_aprovado = float(km_estimado_ref) + tolerancia_km

            vr["km_estimado_referencia"] = float(km_estimado_ref)
            vr["km_estimado_source"] = km_estimado_source
            vr["km_tolerancia"] = tolerancia_km
            vr["km_maximo_aprovado"] = km_maximo_aprovado
            vr["km_validacao_estimado_aplicada"] = True

            # Regra: bloqueia quando passou do estimado + tolerância.
            if km_total > km_maximo_aprovado:
                excedente = km_total - km_maximo_aprovado
                mensagem_rejeicao = (
                    f"A foto foi rejeitada: ultrapassou {excedente:.2f} km do limite permitido "
                    f"(total={km_total}, esperado={float(km_estimado_ref):.2f}, tolerancia={tolerancia_km})."
                )

                logger.warning(
                    "[KM_REJEITADO] mission_id=%s photo_id=%s total=%s estimado=%.2f tolerancia=%s limite=%.2f excedente=%.2f",
                    mission_id,
                    photo_id,
                    km_total,
                    float(km_estimado_ref),
                    tolerancia_km,
                    km_maximo_aprovado,
                    excedente,
                )

                vr["valid"] = False
                _append_issue(
                    vr,
                    f"km_excedido(total={km_total}, estimado={float(km_estimado_ref):.2f}, limite={km_maximo_aprovado:.2f})",
                )
                vr["message"] = mensagem_rejeicao
                vr["km_excedente_tolerancia"] = round(excedente, 2)
                sb.table("mission_photos").update({"validation_result": vr}).eq("id", photo_id).execute()
                return {
                    "updated": False,
                    "reason": "km_total_above_estimated_tolerance",
                    "message": mensagem_rejeicao,
                    "current_status": current_status,
                    "km_total": km_total,
                    "km_estimado": float(km_estimado_ref),
                    "km_tolerancia": tolerancia_km,
                    "km_maximo_aprovado": km_maximo_aprovado,
                    "km_excedente_tolerancia": round(excedente, 2),
                }

        # 1) Sempre salva KM no Django se a foto for válida
        with transaction.atomic():
            django_info = _update_django_km(
                acompanhamento=acompanhamento,
                photo_type="odometro_final",
                odo_raw=odo_raw,
                ts_iso=ts,
                photo_id=photo_id,
                confidence=confidence,
                mission_id=mission_id,
                is_manual=is_manual,
            )

        if not django_info.get("updated"):
            fail_reason = django_info.get("reason", "desconhecido")
            logger.error(
                "[KM_SAVE_FAIL] odometro_final mission_id=%s photo_id=%s reason=%s django_info=%s",
                mission_id, photo_id, fail_reason, django_info,
            )
            vr["django_km_error"] = fail_reason
            vr["django_km_info"] = django_info
            sb.table("mission_photos").update({"validation_result": vr}).eq("id", photo_id).execute()
            return {
                "updated": False,
                "reason": "django_km_update_failed",
                "current_status": current_status,
                "django_km_update": django_info,
            }

        # 2) Avança status apenas se estiver no status esperado
        if current_status == STATUS_EM_ANDAMENTO:
            _supabase_update_status(sb, mission_id, STATUS_ODO_FINAL_OK)
            _sync_django_status(mission_id, STATUS_ODO_FINAL_OK)
            new_status = STATUS_ODO_FINAL_OK
        else:
            logger.info(
                "[STATUS_SKIP] odometro_final KM salvo mas status não avançou "
                "(status atual=%s, esperado=%s) mission_id=%s",
                current_status, STATUS_EM_ANDAMENTO, mission_id,
            )
            new_status = current_status

        return {
            "updated": True,
            "previous_status": current_status,
            "new_status": new_status,
            "django_km_update": django_info,
        }

    return {"updated": False, "reason": f"invalid_photo_type({photo_type})"}

# ==========================================================
# Lock leve (anti-loop) + marcação de erro (anti-pendente infinito)
# ==========================================================

PROCESSING_LOCK_TTL_SECONDS = max(
    30,
    int(getattr(settings, "MISSION_PHOTO_PROCESSING_LOCK_TTL_SECONDS", 120)),
)
_DISPATCH_COOLDOWN_SECONDS = 30
_last_dispatch_failure_ts = None
_DISPATCH_TIMEOUT_SECONDS = max(
    0.2,
    float(getattr(settings, "MISSION_PHOTO_QUEUE_DISPATCH_TIMEOUT_SECONDS", 2.0)),
)


def dispatch_photo_processing(photo_id: str, force: bool = False, timeout_seconds: float = None) -> dict:
    """
    Dispara o processamento assíncrono da foto via Celery.
    Não executa IA dentro do request HTTP.
    """
    global _last_dispatch_failure_ts

    now_ts = datetime.now(dt_timezone.utc).timestamp()
    if _last_dispatch_failure_ts and (now_ts - _last_dispatch_failure_ts) < _DISPATCH_COOLDOWN_SECONDS:
        remaining = round(_DISPATCH_COOLDOWN_SECONDS - (now_ts - _last_dispatch_failure_ts), 2)
        return {
            "enqueued": False,
            "task_id": None,
            "photo_id": photo_id,
            "force": bool(force),
            "error": f"queue_dispatch_cooldown({remaining}s)",
        }

    result_holder = {}

    def _dispatch():
        try:
            from acompanhamentos.tasks import processar_foto_task

            async_result = processar_foto_task.delay(photo_id=photo_id, force=force)
            result_holder["value"] = {
                "enqueued": True,
                "task_id": async_result.id,
                "photo_id": photo_id,
                "force": bool(force),
            }
        except Exception as exc:
            logger.exception(
                "Falha ao enfileirar processamento de foto photo_id=%s force=%s",
                photo_id,
                force,
            )
            result_holder["value"] = {
                "enqueued": False,
                "task_id": None,
                "photo_id": photo_id,
                "force": bool(force),
                "error": str(exc),
            }

    dispatch_thread = threading.Thread(
        target=_dispatch,
        name="mission-photo-dispatch",
        daemon=True,
    )
    dispatch_thread.start()
    dispatch_thread.join(timeout=max(0.2, float(timeout_seconds or _DISPATCH_TIMEOUT_SECONDS)))

    if dispatch_thread.is_alive():
        _last_dispatch_failure_ts = now_ts
        return {
            "enqueued": False,
            "task_id": None,
            "photo_id": photo_id,
            "force": bool(force),
            "error": "queue_dispatch_timeout",
        }

    result = result_holder.get("value") or {
        "enqueued": False,
        "task_id": None,
        "photo_id": photo_id,
        "force": bool(force),
        "error": "queue_dispatch_unknown_error",
    }
    if result.get("enqueued"):
        _last_dispatch_failure_ts = None
    else:
        _last_dispatch_failure_ts = now_ts
    return result


def _is_processing_locked(vr: dict) -> bool:
    """Evita reprocessamento em loop quando polling/UI chamam repetidas vezes."""
    if not isinstance(vr, dict):
        return False

    if vr.get("processing") is not True:
        return False

    started_at = _parse_ts_to_dt(vr.get("started_at"))
    if not started_at:
        return False

    now = datetime.now(dt_timezone.utc)
    elapsed = (now - started_at).total_seconds()
    return elapsed < PROCESSING_LOCK_TTL_SECONDS


def _mark_processing(sb, photo_id: str, current_vr=None) -> dict:
    """Marca a foto como 'em processamento' em validation_result."""
    vr = dict(current_vr or {})
    vr["processing"] = True
    vr["started_at"] = _now_iso()

    sb.table("mission_photos").update({"validation_result": vr}).eq("id", photo_id).execute()
    return vr


def _mark_failed(sb, photo_id: str, mission_id, photo_type, storage_path, err: str) -> dict:
    """Marca a foto como processada com erro (para não ficar pendente infinito)."""
    vr = {
        "valid": False,
        "error": err,
        "processed_at": _now_iso(),
        "processing": False,
        "_photo_id": photo_id,
    }

    sb.table("mission_photos").update({"processed": True, "validation_result": vr}).eq("id", photo_id).execute()

    return {
        "success": False,
        "message": "Falha ao processar foto (marcada como erro)",
        "photo_id": photo_id,
        "mission_id": mission_id,
        "photo_type": photo_type,
        "storage_path": storage_path,
        "validation_result": vr,
    }


def _process_manual_entry(sb, photo: dict):
    """
    Processa uma entrada manual de odômetro (storage_path vazio, is_manual=True).
    Constrói um validation_result sintético com valid=True e confidence=1.0,
    atualiza o Supabase e aplica as regras de status/Django normalmente.
    """
    photo_id = photo.get("id")
    mission_id = photo.get("mission_id")
    photo_type = photo.get("type")
    metadata = photo.get("metadata") or {}
    manual_value = metadata.get("manual_value")

    try:
        manual_int = int(manual_value)
    except (TypeError, ValueError):
        return ({"success": False, "error": f"manual_value inválido: {manual_value}"}, 400)

    formatted = f"{manual_int:,}".replace(",", ".") + " km"

    vr = {
        "valid": True,
        "is_manual": True,
        "odometer_raw": manual_int,
        "odometer_value": formatted,
        "confidence": 1.0,
        "unit": "km",
        "issues": [],
        "display_type": "manual",
        "trip_meter": None,
        "latitude": metadata.get("latitude", 0),
        "longitude": metadata.get("longitude", 0),
        "timestamp": metadata.get("timestamp") or photo.get("uploaded_at") or photo.get("created_at"),
        "processed_at": _now_iso(),
        "processing": False,
        "_photo_id": photo_id,
    }

    sb.table("mission_photos").update({"processed": True, "validation_result": vr}).eq("id", photo_id).execute()

    # Salva KM direto no Django
    django_km_saved = False
    django_km_error = None
    try:
        mission_uuid = uuid.UUID(mission_id)
        vinculo = (
            registroacompanhamentoagente.objects
            .filter(acompanhamento__supabase_mission_id=mission_uuid)
            .filter(tipo_agente="principal")
            .first()
            or registroacompanhamentoagente.objects
            .filter(acompanhamento__supabase_mission_id=mission_uuid)
            .order_by("id")
            .first()
        )
        if vinculo:
            update_fields = []
            if photo_type == "odometro_inicio":
                vinculo.km_inicio = manual_int
                vinculo.km_inicio_manual = True
                update_fields = ["km_inicio", "km_inicio_manual"]
            elif photo_type == "odometro_final":
                vinculo.km_final = manual_int
                vinculo.km_final_manual = True
                update_fields = ["km_final", "km_final_manual"]
            if update_fields:
                vinculo.save(update_fields=update_fields)
                django_km_saved = True
                vr["django_synced"] = True
                sb.table("mission_photos").update({"validation_result": vr}).eq("id", photo_id).execute()
                logger.info("[KM_MANUAL_SAVE_OK] mission_id=%s photo_type=%s km=%s vinculo_id=%s", mission_id, photo_type, manual_int, vinculo.id)
        else:
            django_km_error = "vinculo_nao_encontrado"
            logger.error("[KM_MANUAL_SAVE_FAIL] Vinculo não encontrado mission_id=%s", mission_id)
    except Exception as km_exc:
        django_km_error = str(km_exc)
        logger.exception("[KM_MANUAL_SAVE_FAIL] mission_id=%s photo_id=%s", mission_id, photo_id)

    mission_update_info = _apply_photo_rules(sb=sb, mission_id=mission_id, photo_type=photo_type, vr=vr, is_manual=True)

    return ({
        "success": True,
        "message": "Entrada manual de odômetro processada",
        "photo_id": photo_id,
        "mission_id": mission_id,
        "photo_type": photo_type,
        "validation_result": vr,
        "django_km_saved": django_km_saved,
        "django_km_error": django_km_error,
        "mission_update": mission_update_info,
    }, 200)


def process_one_photo_id(photo_id: str, force: bool = False):
    """
    Processa uma foto por ID (sem depender de request).
    Retorna: (payload_dict, http_status)
    """
    sb = get_supabase()
    tmp_path = None

    mission_id = None
    photo_type = None
    storage_path = None

    try:
        # 1) Buscar a foto no Supabase
        photo_res = (
            sb.table("mission_photos")
            .select("*")
            .eq("id", photo_id)
            .maybe_single()
            .execute()
        )
        photo = photo_res.data
        if not photo:
            return ({"success": False, "error": "Foto não encontrada no Supabase"}, 404)

        mission_id = photo.get("mission_id")
        photo_type = photo.get("type")
        storage_path = photo.get("storage_path")

        # 2) Foto já processada (pelo app ou pela IA) mas Django ainda não sincronizado
        _early_vr = photo.get("validation_result") or {}
        _early_metadata = photo.get("metadata") or {}
        if (
            not force
            and photo.get("processed") is True
            and bool(_early_vr.get("valid"))
            and _early_vr.get("odometer_raw") is not None
            and not _early_vr.get("django_synced")
        ):
            _is_manual = (
                not storage_path
                or _early_vr.get("is_manual") is True
                or _early_metadata.get("is_manual") is True
                or _early_metadata.get("source") == "manual"
            )
            try:
                km_valor = int(_early_vr["odometer_raw"])
                mission_uuid = uuid.UUID(mission_id)
                vinculo = (
                    registroacompanhamentoagente.objects
                    .filter(acompanhamento__supabase_mission_id=mission_uuid)
                    .filter(tipo_agente="principal")
                    .first()
                    or registroacompanhamentoagente.objects
                    .filter(acompanhamento__supabase_mission_id=mission_uuid)
                    .order_by("id").first()
                )
                if vinculo:
                    update_fields = []
                    if photo_type == "odometro_inicio":
                        vinculo.km_inicio = km_valor
                        update_fields.append("km_inicio")
                        if _is_manual:
                            vinculo.km_inicio_manual = True
                            update_fields.append("km_inicio_manual")
                    elif photo_type == "odometro_final":
                        vinculo.km_final = km_valor
                        update_fields.append("km_final")
                        if _is_manual:
                            vinculo.km_final_manual = True
                            update_fields.append("km_final_manual")
                    if update_fields:
                        vinculo.save(update_fields=update_fields)
                        _early_vr["django_synced"] = True
                        sb.table("mission_photos").update({"validation_result": _early_vr}).eq("id", photo_id).execute()
                        logger.info("[SYNC_OK] photo_id=%s mission_id=%s type=%s km=%s manual=%s", photo_id, mission_id, photo_type, km_valor, _is_manual)
                        return ({"success": True, "message": "KM sincronizado com Django", "photo_id": photo_id, "mission_id": mission_id, "photo_type": photo_type, "km_valor": km_valor, "is_manual": _is_manual}, 200)
                    return ({"success": True, "message": "Foto já processada", "photo_id": photo_id}, 200)
                else:
                    logger.error("[SYNC_FAIL] vinculo nao encontrado mission_id=%s", mission_id)
                    return ({"success": False, "error": "vinculo_nao_encontrado", "mission_id": mission_id}, 404)
            except Exception as sync_exc:
                logger.exception("[SYNC_FAIL] photo_id=%s mission_id=%s", photo_id, mission_id)
                return ({"success": False, "error": str(sync_exc)}, 500)

        if not force and photo.get("processed") is True and _early_vr.get("django_synced"):
            return ({"success": True, "message": "Foto já processada e Django sincronizado", "photo_id": photo_id}, 200)
        if has_previous_error:
            logger.info(
                "[PHOTO_REPROCESS] Reprocessando foto com falha anterior photo_id=%s mission_id=%s type=%s error=%s",
                photo_id,
                mission_id,
                photo_type,
                existing_vr.get("error"),
            )

        # 3) Lock leve (se já está processando)
        current_vr = photo.get("validation_result") or {}
        if _is_processing_locked(current_vr):
            return ({
                "success": True,
                "message": "Foto já está em processamento",
                "photo_id": photo_id,
                "mission_id": mission_id,
                "photo_type": photo_type,
                "validation_result": current_vr,
            }, 202)

        # 4) Validar campos
        if not mission_id:
            return ({"success": False, "error": "mission_id vazio em mission_photos"}, 400)
        if photo_type not in ("odometro_inicio", "odometro_final"):
            return ({"success": False, "error": f"type inválido em mission_photos: {photo_type}"}, 400)
        if not storage_path:
            metadata = photo.get("metadata") or {}
            is_manual_flag = (
                metadata.get("is_manual") is True
                or metadata.get("source") == "manual"
            )
            if is_manual_flag and metadata.get("manual_value") is not None:
                return _process_manual_entry(sb, photo)
            return ({"success": False, "error": "storage_path vazio em mission_photos"}, 400)

        # 5) Marcar 'processing' (anti-loop)
        _mark_processing(sb, photo_id, current_vr)

        # 6) Baixar bytes do Storage
        img_bytes = _download_storage_bytes(sb, storage_path)

        # 7) Salvar temporário (opcional)
        tmp_path = _save_tmp_file(storage_path, img_bytes)

        # 8) IA - valida odômetro
        ai_result = validate_odometer_with_ai(img_bytes)
        is_valid = bool(ai_result.get("success", False))

        metadata = photo.get("metadata") or {}
        vr = {
            "valid": bool(is_valid),
            "odometer_value": ai_result.get("odometer_formatted") or str(ai_result.get("odometer", "")),
            "odometer_raw": ai_result.get("odometer"),
            "confidence": float(ai_result.get("confidence", 0.0) or 0.0),
            "timestamp": metadata.get("timestamp") or photo.get("uploaded_at") or photo.get("created_at"),
            "latitude": metadata.get("latitude"),
            "longitude": metadata.get("longitude"),
            "display_type": ai_result.get("display_type", "unknown"),
            "trip_meter": ai_result.get("trip_meter"),
            "unit": ai_result.get("unit", "km"),
            "issues": _normalize_issues_list(ai_result.get("issues")),
            "raw_response": ai_result.get("raw_response"),
            "processed_at": _now_iso(),
            "processing": False,
            "_photo_id": photo_id,
        }

        # 9) Atualizar mission_photos no Supabase
        sb.table("mission_photos").update({"processed": True, "validation_result": vr}).eq("id", photo_id).execute()

        # 10) Salvar KM no Django diretamente, se IA aprovou
        django_km_saved = False
        django_km_error = None
        if is_valid and vr.get("odometer_raw") is not None:
            try:
                km_valor = int(vr["odometer_raw"])
                vinculo = (
                    registroacompanhamentoagente.objects
                    .filter(acompanhamento__supabase_mission_id=uuid.UUID(mission_id))
                    .filter(tipo_agente="principal")
                    .first()
                    or registroacompanhamentoagente.objects
                    .filter(acompanhamento__supabase_mission_id=uuid.UUID(mission_id))
                    .order_by("id")
                    .first()
                )
                if vinculo:
                    update_fields = []
                    if photo_type == "odometro_inicio":
                        vinculo.km_inicio = km_valor
                        update_fields.append("km_inicio")
                    elif photo_type == "odometro_final":
                        vinculo.km_final = km_valor
                        update_fields.append("km_final")
                    if update_fields:
                        vinculo.save(update_fields=update_fields)
                        django_km_saved = True
                        vr["django_synced"] = True
                        sb.table("mission_photos").update({"validation_result": vr}).eq("id", photo_id).execute()
                        logger.info(
                            "[KM_SAVE_OK] mission_id=%s photo_type=%s km=%s vinculo_id=%s",
                            mission_id, photo_type, km_valor, vinculo.id,
                        )
                else:
                    django_km_error = "vinculo_nao_encontrado"
                    logger.error("[KM_SAVE_FAIL] Vinculo não encontrado mission_id=%s", mission_id)
            except Exception as km_exc:
                django_km_error = str(km_exc)
                logger.exception("[KM_SAVE_FAIL] mission_id=%s photo_id=%s", mission_id, photo_id)

        # 11) Avançar status no Supabase + Django
        mission_update_info = _apply_photo_rules(sb=sb, mission_id=mission_id, photo_type=photo_type, vr=vr)

        return ({
            "success": True,
            "message": "Foto processada com sucesso",
            "photo_id": photo_id,
            "mission_id": mission_id,
            "photo_type": photo_type,
            "storage_path": storage_path,
            "validation_result": vr,
            "django_km_saved": django_km_saved,
            "django_km_error": django_km_error,
            "mission_update": mission_update_info,
        }, 200)

    except Exception as e:
        logger.exception("Falha ao processar foto")
        payload = _mark_failed(sb, photo_id, mission_id, photo_type, storage_path, str(e))
        return (payload, 500)

    finally:
        _remove_file_silent(tmp_path)



@csrf_exempt
@require_POST
def sb_process_one_photo(request, photo_id: str):
    force = str(request.GET.get("force") or "").strip().lower() in {"1", "true", "yes"}
    mode = (request.GET.get("mode") or "sync").strip().lower()
    if mode == "async":
        dispatch_info = dispatch_photo_processing(photo_id, force=force)
        status_code = 202 if dispatch_info.get("enqueued") else 503
        payload = {
            "success": bool(dispatch_info.get("enqueued")),
            "message": "Foto enfileirada para processamento assíncrono"
            if dispatch_info.get("enqueued")
            else "Falha ao enfileirar foto para processamento",
            "photo_id": photo_id,
            "dispatch": dispatch_info,
        }
        return JsonResponse(payload, status=status_code)

    payload, status_code = process_one_photo_id(photo_id, force=force)
    return JsonResponse(payload, status=status_code)

@csrf_exempt
@require_GET
def sb_process_pending_photos(request):
    """
    Fallback para DEV/local + redundância em produção.

    GET /api/supabase/mission_photos/process-pending/?mission_id=...&type=final&limit=5&mode=auto

    mode:
    - auto  (padrão): tenta fila assíncrona; se falhar, processa 1 foto em modo síncrono como fallback.
    - async: apenas enfileira (não processa IA no request).
    - sync: processa síncrono (legado/debug).
    """
    sb = get_supabase()

    mission_id = (request.GET.get("mission_id") or "").strip() or None
    photo_type = (request.GET.get("type") or "").strip() or None
    mode = (request.GET.get("mode") or "auto").strip().lower()
    if mode not in {"auto", "async", "sync"}:
        mode = "auto"

    try:
        limit = int(request.GET.get("limit") or 10)
        limit = max(1, min(limit, 50))
    except Exception:
        limit = 10

    try:
        q = sb.table("mission_photos").select("*").eq("processed", False)
        if mission_id:
            q = q.eq("mission_id", mission_id)
        if photo_type:
            q = q.eq("type", photo_type)

        q = q.order("created_at", desc=False).limit(limit)

        photos_res = q.execute()
        pending = photos_res.data or []

        # Além das pendentes, tenta reprocessar fotos já "processed=true"
        # que ficaram com erro ou que têm valid=True mas django_synced ausente (KM não salvo no Django).
        errored = []
        unsynced = []
        if mission_id:
            recent_q = (
                sb.table("mission_photos")
                .select("*")
                .eq("mission_id", mission_id)
                .order("created_at", desc=True)
                .limit(limit)
            )
            if photo_type:
                recent_q = recent_q.eq("type", photo_type)

            recent_rows = recent_q.execute().data or []
            for row in recent_rows:
                if not (row.get("processed") is True):
                    continue
                vr_row = row.get("validation_result") or {}
                if not isinstance(vr_row, dict):
                    continue
                if vr_row.get("error"):
                    errored.append(row)
                elif vr_row.get("valid") is True and not vr_row.get("django_synced"):
                    unsynced.append(row)

        # Deduplica mantendo ordem: pendentes primeiro, depois unsynced, depois errored.
        all_candidates = []
        seen_ids = set()
        for row in (pending + unsynced + errored):
            pid = row.get("id")
            if not pid or pid in seen_ids:
                continue
            seen_ids.add(pid)
            all_candidates.append(row)

        results = []
        ok_count = 0
        fail_count = 0
        enqueued_count = 0
        enqueue_fail_count = 0
        locked_count = 0
        sync_fallback_used = False

        for p in all_candidates:
            pid = p.get("id")
            if not pid:
                continue

            vr = p.get("validation_result") if isinstance(p.get("validation_result"), dict) else {}
            force = bool(vr.get("error"))

            if _is_processing_locked(vr):
                locked_count += 1
                results.append(
                    {
                        "photo_id": pid,
                        "mode": mode,
                        "status": 202,
                        "result": {
                            "success": True,
                            "message": "Foto já está em processamento",
                            "photo_id": pid,
                            "locked": True,
                        },
                    }
                )
                continue

            if mode == "sync":
                payload, st = process_one_photo_id(pid, force=force)
                results.append(
                    {"photo_id": pid, "mode": "sync", "force": force, "status": st, "result": payload}
                )

                if payload.get("success") is True:
                    ok_count += 1
                else:
                    fail_count += 1
                continue

            dispatch_info = dispatch_photo_processing(pid, force=force)
            if dispatch_info.get("enqueued"):
                enqueued_count += 1
                results.append(
                    {
                        "photo_id": pid,
                        "mode": "async",
                        "force": force,
                        "status": 202,
                        "result": {
                            "success": True,
                            "message": "Foto enfileirada para processamento assíncrono",
                            **dispatch_info,
                        },
                    }
                )
                continue

            enqueue_fail_count += 1
            if mode == "async":
                fail_count += 1
                results.append(
                    {
                        "photo_id": pid,
                        "mode": "async",
                        "force": force,
                        "status": 503,
                        "result": {
                            "success": False,
                            "message": "Falha ao enfileirar foto para processamento",
                            **dispatch_info,
                        },
                    }
                )
                continue

            if sync_fallback_used:
                fail_count += 1
                results.append(
                    {
                        "photo_id": pid,
                        "mode": "auto",
                        "force": force,
                        "status": 503,
                        "result": {
                            "success": False,
                            "message": "Fila indisponível; fallback síncrono já usado nesta rodada",
                            **dispatch_info,
                        },
                    }
                )
                continue

            payload, st = process_one_photo_id(pid, force=force)
            sync_fallback_used = True
            results.append(
                {"photo_id": pid, "mode": "auto-sync-fallback", "force": force, "status": st, "result": payload}
            )

            if payload.get("success") is True:
                ok_count += 1
            else:
                fail_count += 1

        return JsonResponse({
            "success": True,
            "message": "Polling completado",
            "filters": {"mission_id": mission_id, "type": photo_type, "limit": limit, "mode": mode},
            "total_pending_found": len(pending),
            "total_unsynced_found": len(unsynced),
            "total_errored_found": len(errored),
            "total_candidates": len(all_candidates),
            "processing_locked_skipped": locked_count,
            "enqueued_async": enqueued_count,
            "enqueue_fail": enqueue_fail_count,
            "processed_ok": ok_count,
            "processed_fail": fail_count,
            "sync_fallback_used": sync_fallback_used,
            "results": results,
        }, status=200)

    except Exception as e:
        logger.exception("Erro no polling de fotos")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_POST
def sb_mission_sync_km(request, mission_id: str):
    """
    Lê as fotos de odômetro aprovadas no Supabase e salva km_inicio/km_final
    diretamente no registroacompanhamentoagente do Django. Simples e direto.

    POST /api/supabase/mission/<mission_id>/sync-km/
    """
    try:
        sb = get_supabase()

        # Busca as fotos de odômetro processadas e válidas para essa missão
        fotos = (
            sb.table("mission_photos")
            .select("id, type, metadata, validation_result")
            .eq("mission_id", mission_id)
            .eq("processed", True)
            .in_("type", ["odometro_inicio", "odometro_final"])
            .execute()
            .data or []
        )

        if not fotos:
            return JsonResponse({"success": False, "error": "Nenhuma foto de odômetro processada encontrada no Supabase para essa missão"}, status=404)

        # Encontra o vinculo (agente) no Django
        try:
            mission_uuid = uuid.UUID(mission_id)
        except ValueError:
            return JsonResponse({"success": False, "error": "mission_id inválido"}, status=400)

        vinculo = (
            registroacompanhamentoagente.objects
            .filter(acompanhamento__supabase_mission_id=mission_uuid)
            .filter(tipo_agente="principal")
            .first()
            or registroacompanhamentoagente.objects
            .filter(acompanhamento__supabase_mission_id=mission_uuid)
            .order_by("id")
            .first()
        )

        if not vinculo:
            return JsonResponse({"success": False, "error": "Nenhum agente vinculado encontrado no Django para essa missão"}, status=404)

        saved = []
        skipped = []

        for foto in fotos:
            vr = foto.get("validation_result") or {}
            metadata = foto.get("metadata") or {}
            photo_type = foto.get("type")
            photo_id = foto.get("id")

            # Só processa se válida
            if not vr.get("valid"):
                skipped.append({"photo_id": photo_id, "type": photo_type, "reason": "valid=false"})
                continue

            odometer_raw = vr.get("odometer_raw")
            if odometer_raw is None:
                skipped.append({"photo_id": photo_id, "type": photo_type, "reason": "odometer_raw ausente"})
                continue

            try:
                km_valor = int(odometer_raw)
            except (TypeError, ValueError):
                skipped.append({"photo_id": photo_id, "type": photo_type, "reason": f"odometer_raw não é número: {odometer_raw}"})
                continue

            is_manual = (
                vr.get("is_manual") is True
                or metadata.get("is_manual") is True
                or metadata.get("source") == "manual"
            )

            update_fields = []
            if photo_type == "odometro_inicio":
                vinculo.km_inicio = km_valor
                update_fields.append("km_inicio")
                if is_manual:
                    vinculo.km_inicio_manual = True
                    update_fields.append("km_inicio_manual")
            elif photo_type == "odometro_final":
                vinculo.km_final = km_valor
                update_fields.append("km_final")
                if is_manual:
                    vinculo.km_final_manual = True
                    update_fields.append("km_final_manual")

            vinculo.save(update_fields=update_fields)

            # Marca django_synced no Supabase
            vr["django_synced"] = True
            sb.table("mission_photos").update({"validation_result": vr}).eq("id", photo_id).execute()

            saved.append({
                "photo_id": photo_id,
                "type": photo_type,
                "km_valor": km_valor,
                "is_manual": is_manual,
                "fields_saved": update_fields,
            })

        return JsonResponse({
            "success": True,
            "mission_id": mission_id,
            "vinculo_id": vinculo.id,
            "km_inicio": vinculo.km_inicio,
            "km_final": vinculo.km_final,
            "km_inicio_manual": vinculo.km_inicio_manual,
            "km_final_manual": vinculo.km_final_manual,
            "saved": saved,
            "skipped": skipped,
        })

    except Exception as e:
        logger.exception("Erro em sync-km mission_id=%s", mission_id)
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_GET
def sb_mission_django_debug(request, mission_id: str):
    """
    Diagnóstico: mostra o estado do Django para uma missão — acompanhamento e agentes vinculados.
    Útil para debugar por que km_inicio/km_final não está sendo salvo.
    """
    try:
        acompanhamento = _find_acompanhamento_by_supabase_mission_id(mission_id)
        if not acompanhamento:
            return JsonResponse({
                "success": False,
                "error": "Nenhum acompanhamento Django encontrado para essa mission_id",
                "mission_id": mission_id,
            }, status=404)

        agentes = list(
            acompanhamento.agentes.values(
                "id", "tipo_agente", "km_inicio", "km_final",
                "km_inicio_manual", "km_final_manual",
                "agente__id", "agente__nome",
            )
        )

        return JsonResponse({
            "success": True,
            "mission_id": mission_id,
            "acompanhamento_id": acompanhamento.id,
            "supabase_mission_id": str(acompanhamento.supabase_mission_id),
            "status_acompanhamento": acompanhamento.status_acompanhamento,
            "total_agentes": len(agentes),
            "agentes": agentes,
        })
    except Exception as e:
        logger.exception("Erro no diagnóstico Django de missão")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
