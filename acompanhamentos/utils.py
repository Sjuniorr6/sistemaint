import uuid
import logging
from django.utils import timezone
from .api.supabase_client import get_supabase
from urllib.parse import urlencode
from django.conf import settings

def gerar_link_app_missao(acompanhamento):
    """
    Gera o LINK WEB que será enviado/aberto no navegador.
    Esse link (missao.html) redireciona para o deep link do app.
    """

    base_url = getattr(settings, "AGENTTRACKER_WEB_BASE_URL", "https://intgoldensat.com.br")
    # base_url = getattr(settings, "AGENTTRACKER_WEB_BASE_URL", "http://127.0.0.1:8000")

    # Origem (local/cidade) -> use seu campo real (item.origem)
    origem = getattr(acompanhamento, "origem", "") or ""

    # Agente -> pega o "principal" se existir, senão qualquer um
    agente_nome = ""
    agente_principal = None

    if hasattr(acompanhamento, "agentes"):
        agente_principal = acompanhamento.agentes.filter(tipo_agente="principal").select_related("agente").first()
        if agente_principal and agente_principal.agente:
            agente_nome = getattr(agente_principal.agente, "nome", "") or str(agente_principal.agente)

        if not agente_nome:
            first_ag = acompanhamento.agentes.select_related("agente").first()
            if first_ag and first_ag.agente:
                agente_nome = getattr(first_ag.agente, "nome", "") or str(first_ag.agente)

    params = {
        "id": str(acompanhamento.pk),     # IMPORTANTE: aqui o ID que o app usará
        "origem": origem,
        "agente": agente_nome,
        "auto": "1",
    }

    # ← MUDOU AQUI: adiciona /static/
    return f"{base_url}/static/missao.html?{urlencode(params)}"

# acompanhamentos/utils.py
from .api.supabase_client import get_supabase
from django.utils import timezone
import logging


logger = logging.getLogger(__name__)

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
            .select_related("agente")
            .first()
            or acompanhamento.agentes.select_related("agente").first()
        )

        agente_nome = ""
        if agente_principal and agente_principal.agente:
            agente_nome = (getattr(agente_principal.agente, "nome", "") or "").strip()

        # ✅ NUNCA deixar vazio, porque no Supabase é NOT NULL
        if not agente_nome:
            agente_nome = "Não atribuído"

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

        agent_data = {
            "acompanhamento_id": acompanhamento.id,
            "criado_em": (getattr(acompanhamento, "criado_em", None) or timezone.now()).isoformat(),
            "agente_nome": agente_nome,
        }

        if agente_principal:
            agent_data.update({
                "placa_agente": str(getattr(agente_principal, "placa_agente", "") or ""),
                "motorista": str(getattr(agente_principal, "motorista", "") or ""),
                "placa_motorista": str(getattr(agente_principal, "placa_motorista", "") or ""),
            })

        # ✅ anexa geofence no agent_data
        if geofence:
            agent_data["geofence"] = geofence

        payload = {
            "id": mission_id,
            "status": (acompanhamento.status or "pendente"),
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



import logging
from django.utils import timezone
from .api.supabase_client import get_supabase

logger = logging.getLogger(__name__)

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