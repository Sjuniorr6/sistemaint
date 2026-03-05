# acompanhamentos/gs_sync_utils.py

import logging
from decimal import Decimal
from .models import registroacompanhamento, RequisicaoSolicitacao
from .gs_acionamento_service import gs_acionamento

logger = logging.getLogger(__name__)

# Status que devem ser propagados para o GS Acionamento
GS_STATUS_MAP = {
    "em_andamento": "em_andamento",
    "concluido": "concluido",
}


def notificar_gs_verificado(acomp_id):
    """
    Chamada quando o operador marca o acompanhamento como 'verificado'
    (apos preencher o pedagio).

    Recalcula os valores dos agentes (agora COM pedagio) e envia
    o callback para o GS Acionamento com status_requisicao='concluido'
    + todos os dados de conclusao.
    """
    try:
        acomp = (
            registroacompanhamento.objects
            .select_related("cliente", "tipo_servico")
            .get(pk=acomp_id)
        )
    except registroacompanhamento.DoesNotExist:
        logger.warning(f"[GS Sync] notificar_gs_verificado: acomp #{acomp_id} nao encontrado")
        return

    # Buscar RequisicaoSolicitacao vinculada
    req = _encontrar_requisicao_vinculada(acomp)
    if not req or not req.id_externo:
        logger.warning(
            f"[GS Sync] notificar_gs_verificado: acomp #{acomp_id} "
            f"sem RequisicaoSolicitacao com id_externo"
        )
        return

    # Agente principal
    ag_principal = (
        acomp.agentes
        .filter(tipo_agente="principal")
        .select_related("agente", "franquia")
        .first()
    )

    if not ag_principal:
        logger.warning(f"[GS Sync] notificar_gs_verificado: acomp #{acomp_id} sem agente principal")
        return

    # ── Recalcular valor_agente de TODOS os agentes (agora com pedagio) ──
    for ag in acomp.agentes.select_related("franquia").exclude(tipo_agente="carona"):
        ag.recalcular_franquia_e_valores()
        ag.save(update_fields=[
            "km_excedente", "horario_excedente", "valor_agente"
        ])

    # ── Recalcular valor_contrato e lucro_total do acompanhamento ──
    acomp.refresh_from_db()
    acomp.recalcular_financeiro()

    # ── Recarregar agente principal (com valores atualizados) ──
    ag_principal.refresh_from_db()

    # ── Montar payload de conclusao (mesma estrutura do _build_concluido_payload) ──
    extra_payload = _build_concluido_payload(acomp, ag_principal)

    # Adicionar pedagio explicitamente
    extra_payload["pedagio"] = str(ag_principal.pedagio or Decimal("0.00"))

    try:
        gs_acionamento.notificar_status_requisicao(
            req,
            status_requisicao="concluido",  # GS recebe como concluido
            agente_principal=ag_principal,
            extra_payload=extra_payload,
        )
        logger.info(
            f"[GS Sync] Verificado -> GS notificado: acomp #{acomp_id} "
            f"(id_externo={req.id_externo}, "
            f"total={extra_payload.get('total')}, "
            f"pedagio={extra_payload.get('pedagio')})"
        )
    except Exception as e:
        logger.warning(f"[GS Sync] Erro ao notificar GS (verificado) acomp #{acomp_id}: {e}")


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


def _calcular_franquia_restante(ag_principal):
    if not ag_principal:
        return None

    franquia = ag_principal.franquia
    if not franquia or franquia.franquia_horas is None:
        return None

    franquia_segundos = franquia.franquia_horas * 3600

    horario_total = ag_principal.horario_total
    if not horario_total:
        return None

    segundos_utilizados = int(horario_total.total_seconds())
    segundos_restantes = franquia_segundos - segundos_utilizados

    if segundos_restantes <= 0:
        return None

    # ── Cálculo correto: horas e minutos inteiros ──
    horas_restantes_int = segundos_restantes // 3600
    minutos_restantes_int = (segundos_restantes % 3600) // 60

    # Formatação legível: "1h 48min"
    if horas_restantes_int > 0 and minutos_restantes_int > 0:
        formatado = f"{horas_restantes_int}h {minutos_restantes_int}min"
    elif horas_restantes_int > 0:
        formatado = f"{horas_restantes_int}h"
    else:
        formatado = f"{minutos_restantes_int}min"

    agente_nome = ""
    if ag_principal.agente:
        agente_nome = getattr(ag_principal.agente, "nome", "") or str(ag_principal.agente)

    placa_agente = ag_principal.placa_agente or ""
    motorista = ag_principal.motorista or ""
    placa_motorista = ag_principal.placa_motorista or ""

    return {
        "franquia_horas_total": int(franquia.franquia_horas),
        "segundos_restantes": segundos_restantes,
        "horas_restantes_int": horas_restantes_int,
        "minutos_restantes_int": minutos_restantes_int,
        "formatado": formatado,  # "1h 48min"
        "agente_disponivel": True,
        "agente_nome": agente_nome,
        "agente_placa": placa_agente,
        "motorista": motorista,
        "placa_motorista": placa_motorista,
        "franquia_nome": franquia.nome or "",
        "franquia_id": franquia.id,
        "franquia_km": franquia.franquia_km,
    }

def _garantir_horario_total_se_der(ag):
    if not ag:
        return

    if ag.horario_total:
        return

    if not (ag.data_solicitada and ag.horario_solicitado and ag.data_finalizacao and ag.horario_finalizacao):
        return

    try:
        ag.horario_total = ag.calcular_horario_total()
        ag.horario_excedente = ag.calcular_horario_excedente()
        ag.save(update_fields=["horario_total", "horario_excedente"])
    except Exception as e:
        logger.warning(f"[GS Sync] Falha ao calcular horario_total para agente #{ag.pk}: {e}")


def _build_reuso_payload(ag_principal):
    _garantir_horario_total_se_der(ag_principal)

    franquia_restante = _calcular_franquia_restante(ag_principal)

    return {
        "agente_disponivel_reuso": bool(franquia_restante),
        "franquia_restante": franquia_restante,  # pode ser None
    }

def _build_concluido_payload(acomp, ag_principal):
    """Monta o extra_payload com métricas de conclusão + franquia restante."""
    def _time_iso(t):
        return t.isoformat() if t else None

    def _date_iso(d):
        return d.isoformat() if d else None

    def _duration_seconds(td):
        return int(td.total_seconds()) if td else None

    payload = {
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
        "total": str(acomp.valor_contrato or Decimal("0.00")),
    }

    # =============================================
    # NOVO: Franquia restante do agente
    # =============================================
    franquia_restante = _calcular_franquia_restante(ag_principal)
    if franquia_restante:
        payload["franquia_restante"] = franquia_restante

    return payload

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

    extra_payload = None
    if new_status == "concluido" and ag_principal:
        extra_payload = _build_reuso_payload(ag_principal)

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