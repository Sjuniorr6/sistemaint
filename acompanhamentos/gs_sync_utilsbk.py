# acompanhamentos/gs_sync_utils.py

import logging
from decimal import Decimal
from .models import registroacompanhamento, RequisicaoSolicitacao
from .gs_acionamento_service import gs_acionamento

logger = logging.getLogger(__name__)

# Status que devem ser propagados para o GS Acionamento
GS_STATUS_MAP = {
    "em_andamento": "em_andamento",
    # "concluido": "concluido",
}


def notificar_gs_mudanca_status(acomp_id, new_status):
    """
    Busca o acompanhamento, encontra a RequisicaoSolicitacao vinculada,
    e notifica o GS Acionamento se o status for relevante.

    Chamada por:
    - sync_status_from_supabase (polling endpoint)
    - _sync_django_status (mission_ops)
    """
    if new_status not in GS_STATUS_MAP:
        return

    gs_status = GS_STATUS_MAP[new_status]

    try:
        acomp = (
            registroacompanhamento.objects
            .select_related("cliente", "tipo_servico")
            .get(pk=acomp_id)
        )
    except registroacompanhamento.DoesNotExist:
        logger.warning(f"[GS Sync] Acomp #{acomp_id} não encontrado")
        return

    # Buscar a RequisicaoSolicitacao vinculada
    req = _encontrar_requisicao_vinculada(acomp)

    if not req or not req.id_externo:
        logger.warning(
            f"[GS Sync] Acomp #{acomp_id} → {new_status}: "
            f"sem RequisicaoSolicitacao com id_externo vinculada"
        )
        return

    # Pegar agente principal
    ag_principal = (
        acomp.agentes
        .filter(tipo_agente="principal")
        .select_related("agente", "franquia")
        .first()
    )

    # Montar extra_payload para concluido
    extra_payload = None
    if new_status == "concluido" and ag_principal:
        extra_payload = _build_concluido_payload(acomp, ag_principal)

    try:
        gs_acionamento.notificar_status_requisicao(
            req,
            status_requisicao=gs_status,
            agente_principal=ag_principal,
            extra_payload=extra_payload,
        )
        logger.info(
            f"[GS Sync] Notificado GS: acomp #{acomp_id} → {gs_status} "
            f"(id_externo={req.id_externo})"
        )
    except Exception as e:
        logger.warning(f"[GS Sync] Erro ao notificar GS para acomp #{acomp_id}: {e}")


def _encontrar_requisicao_vinculada(acomp):
    """
    Encontra a RequisicaoSolicitacao que originou este acompanhamento.
    Busca por cliente + tipo_servico + solicitado=True (mais recente).
    """
    qs = RequisicaoSolicitacao.objects.filter(
        cliente=acomp.cliente,
        solicitado=True,
    ).exclude(id_externo__isnull=True)

    if acomp.tipo_servico:
        req = qs.filter(tipo_servico=acomp.tipo_servico).order_by("-criado_em").first()
        if req:
            return req

    return qs.order_by("-criado_em").first()


def _build_concluido_payload(acomp, ag_principal):
    """Monta o extra_payload com métricas de conclusão."""
    def _time_iso(t):
        return t.isoformat() if t else None

    def _date_iso(d):
        return d.isoformat() if d else None

    def _duration_seconds(td):
        return int(td.total_seconds()) if td else None

    return {
        "km_inicio": ag_principal.km_inicio,
        "km_final": ag_principal.km_final,
        "km_total": ag_principal.km_total,
        "km_excedente": ag_principal.km_excedente,
        "horario_inicio": _time_iso(ag_principal.horario_inicio),
        "horario_finalizacao": _time_iso(ag_principal.horario_finalizacao),
        "data_inicio": _date_iso(ag_principal.data_inicio),
        "data_finalizacao": _date_iso(ag_principal.data_finalizacao),
        "horario_total": _duration_seconds(ag_principal.horario_total),
        "horario_excedente": _duration_seconds(ag_principal.horario_excedente),
        "total": str(acomp.total_valor_agentes or Decimal("0.00")),
    }