import uuid
import logging
from django.utils import timezone
from datetime import datetime, timedelta
from .api.supabase_client import get_supabase
from urllib.parse import urlencode
from django.conf import settings
logger = logging.getLogger(__name__)
# acompanhamentos/utils.py

def gerar_link_app_missao(acompanhamento, request=None):
    """
    Gera o LINK WEB (missao.html) com querystring contendo o UUID/ID.
    Em produção, evita depender de redirects (http->https) para não perder ?uuid=...
    """

    # 1) Base URL preferencial via settings (ideal em produção)
    base_url = (getattr(settings, "AGENTTRACKER_WEB_BASE_URL", "") or "").strip().rstrip("/")

    # 2) Fallback: se tiver request, monta automaticamente (pega scheme/host reais)
    if not base_url and request is not None:
        base_url = request.build_absolute_uri("/").rstrip("/")

    # 3) Fallback final (evita quebrar)
    if not base_url:
        base_url = "https://intgoldensat.com.br"

    # Origem
    origem = getattr(acompanhamento, "origem", "") or ""

    # Agente (principal -> fallback)
    agente_nome = ""
    if hasattr(acompanhamento, "agentes"):
        agente_principal = (
            acompanhamento.agentes
            .filter(tipo_agente="principal")
            .select_related("agente")
            .first()
        )
        if agente_principal and agente_principal.agente:
            agente_nome = getattr(agente_principal.agente, "nome", "") or str(agente_principal.agente)

        if not agente_nome:
            first_ag = acompanhamento.agentes.select_related("agente").first()
            if first_ag and first_ag.agente:
                agente_nome = getattr(first_ag.agente, "nome", "") or str(first_ag.agente)

    # Usa UUID do Supabase se existir, senão o PK
    mission_id = str(acompanhamento.supabase_mission_id) if getattr(acompanhamento, "supabase_mission_id", None) else str(acompanhamento.pk)
    param_key = "id" if getattr(acompanhamento, "supabase_mission_id", None) else "id"

    params = {
        param_key: mission_id,
        "origem": origem,
        "agente": agente_nome,
        "auto": "1",
    }

    # Usa STATIC_URL para não “fixar” /static/ se você mudar isso no futuro
    static_url = (getattr(settings, "STATIC_URL", "/static/") or "/static/").strip()
    if not static_url.startswith("/"):
        static_url = "/" + static_url
    if not static_url.endswith("/"):
        static_url += "/"

    return f"{base_url}{static_url}missao.html?{urlencode(params)}"

def _as_aware(dt: datetime) -> datetime:
    """
    Garante datetime timezone-aware (pro ISO não sair sem fuso e virar bagunça no front).
    """
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt

def sync_acompanhamento_to_supabase(acompanhamento):
    try:
        sb = get_supabase()

        # 1) Garantir UUID local
        if not getattr(acompanhamento, "supabase_mission_id", None):
            acompanhamento.supabase_mission_id = uuid.uuid4()
            acompanhamento.save(update_fields=["supabase_mission_id"])

        mission_id = str(acompanhamento.supabase_mission_id)

        # 2) Agente principal (fallback seguro)
        agente_principal = (
            acompanhamento.agentes
            .filter(tipo_agente="principal")
            .select_related("agente", "franquia")
            .first()
            or acompanhamento.agentes.select_related("agente", "franquia").first()
        )

        agente_nome = ""
        if agente_principal and agente_principal.agente:
            agente_nome = (getattr(agente_principal.agente, "nome", "") or "").strip()
        if not agente_nome:
            agente_nome = "Não atribuído"  # NOT NULL no Supabase

        # ✅ Geofence (cerca_origem) enviada para o Supabase
        geofence = None
        if (
            getattr(acompanhamento, "latitude_origem", None) is not None
            and getattr(acompanhamento, "longitude_origem", None) is not None
        ):
            geofence = {
                "latitude": float(acompanhamento.latitude_origem),
                "longitude": float(acompanhamento.longitude_origem),
                "raio": int(getattr(acompanhamento, "raio_cerca", None) or 60),
            }

        # -----------------------------
        # ✅ NOVO: franquia_horas + inicio + fim previsto
        # -----------------------------
        franquia_horas = None
        franquia_inicio_dt = None
        franquia_fim_previsto_dt = None

        if agente_principal:
            # franquia_horas vem da franquia vinculada ao agente deste acompanhamento
            if getattr(agente_principal, "franquia", None) and agente_principal.franquia.franquia_horas is not None:
                # franquia_horas no seu model é PositiveIntegerField (horas inteiras)
                franquia_horas = float(agente_principal.franquia.franquia_horas)

            # "horário previsto pra início": vou usar data_solicitada + horario_solicitado
            data_solic = getattr(agente_principal, "data_solicitada", None)
            hora_solic = getattr(agente_principal, "horario_solicitado", None)

            if data_solic and hora_solic:
                franquia_inicio_dt = _as_aware(datetime.combine(data_solic, hora_solic))

                # fim previsto = inicio + franquia_horas
                if franquia_horas is not None:
                    franquia_fim_previsto_dt = franquia_inicio_dt + timedelta(hours=franquia_horas)

        agent_data = {
            "acompanhamento_id": acompanhamento.id,
            "criado_em": (getattr(acompanhamento, "criado_em", None) or timezone.now()).isoformat(),
            "agente_nome": agente_nome,

            # ✅ NOVOS CAMPOS (do jeito que você pediu)
            "franquia_horas": franquia_horas,  # number | null
            "franquia_inicio": franquia_inicio_dt.isoformat() if franquia_inicio_dt else None,
            "franquia_fim_previsto": franquia_fim_previsto_dt.isoformat() if franquia_fim_previsto_dt else None,
        }

        if agente_principal:
            agent_data.update({
                "placa_agente": str(getattr(agente_principal, "placa_agente", "") or ""),
                "motorista": str(getattr(agente_principal, "motorista", "") or ""),
                "numero_motorista": str(getattr(agente_principal, "numero_motorista", "") or ""),
                "placa_motorista": str(getattr(agente_principal, "placa_motorista", "") or ""),
            })

            # (opcional, mas ajuda no debug e no front)
            if getattr(agente_principal, "franquia", None):
                agent_data["franquia_nome"] = str(getattr(agente_principal.franquia, "nome", "") or "")
                agent_data["franquia_id"] = int(agente_principal.franquia.id)

        # ✅ anexa geofence no agent_data
        if geofence:
            agent_data["geofence"] = geofence

        payload = {
            "id": mission_id,
            "status": (getattr(acompanhamento, "status_acompanhamento", None) or "pendente"),
            "origem": (acompanhamento.origem or ""),
            "agente": agente_nome,
            "agent_data": agent_data,
            "updated_at": timezone.now().isoformat(),
        }

        sb.table("missions_control").upsert(payload, on_conflict="id").execute()
        return True, mission_id, None

    except Exception as e:
        logger.exception("Erro ao sincronizar missão no Supabase")
        return False, None, str(e)

def update_supabase_mission_status(mission_id: str, new_status: str) -> bool:
    try:
        sb = get_supabase()
        sb.table("missions_control").update({
            "status": new_status,
            "updated_at": timezone.now().isoformat(),
        }).eq("id", mission_id).execute()
        return True
    except Exception:
        logger.exception("Erro ao atualizar status no Supabase")
        return False

def delete_supabase_mission(mission_id):
    """
    Remove uma missão do Supabase (útil para rollback).
    """
    try:
        sb = get_supabase()
        sb.table("missions_control").delete().eq("id", str(mission_id)).execute()
        logger.info(f"Missão {mission_id} removida do Supabase")
        return True
    except Exception as e:
        logger.error(f"Erro ao remover missão do Supabase: {str(e)}")
        return False