# acompanhamentos/signals.py

from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from decimal import Decimal  # ✅ FALTAVA (você usa Decimal no payload)

from .models import registroacompanhamento
from .gs_acionamento_service import gs_acionamento
import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=registroacompanhamento)
def _acomp_pre_save_guardar_status_antigo(sender, instance, **kwargs):
    if not instance.pk:
        instance._status_acomp_old = None
        return

    old = (
        sender.objects
        .filter(pk=instance.pk)
        .values_list("status_acompanhamento", flat=True)
        .first()
    )
    instance._status_acomp_old = old


@receiver(post_save, sender=registroacompanhamento)
def _acomp_post_save_notificar_gs(sender, instance, created, **kwargs):
    old_status = getattr(instance, "_status_acomp_old", None)
    new_status = instance.status_acompanhamento

    if old_status == new_status:
        return

    req = getattr(instance, "requisicao_solicitacao", None)
    if not req or not getattr(req, "id_externo", None):
        logger.warning(
            f"[GS] Acompanhamento #{instance.pk} mudou status para '{new_status}', "
            f"mas não tem requisicao_solicitacao ou req.id_externo."
        )
        return

    def _time_iso(t):
        return t.isoformat() if t else None

    def _date_iso(d):
        return d.isoformat() if d else None

    def _duration_seconds(td):
        return int(td.total_seconds()) if td else None

    def _enviar(status_requisicao, extra_payload=None):
        try:
            ag_principal = (
                instance.agentes
                .filter(tipo_agente="principal")
                .select_related("agente")
                .first()
            )

            gs_acionamento.notificar_status_requisicao(
                req,
                status_requisicao=status_requisicao,
                agente_principal=ag_principal,
                extra_payload=extra_payload
            )

            logger.info(
                f"[GS] Notificado {status_requisicao}: acomp=#{instance.pk} req.id_externo={req.id_externo}"
            )
        except Exception as e:
            logger.exception(
                f"[GS] Erro ao notificar '{status_requisicao}' (acomp=#{instance.pk}, req.id_externo={getattr(req,'id_externo',None)}): {e}"
            )

    def _on_commit():
        # ✅ EM ANDAMENTO
        if new_status == "em_andamento":
            _enviar("em_andamento")
            return

        # ✅ CONCLUÍDO: RECALCULA ANTES (é isso que você quer)
        if new_status == "verificado":
            try:
                # Força recalcular km_total/horario_total/excedentes/valor_agente
                # (porque isso roda no registroacompanhamentoagente.save())
                for ag in instance.agentes.select_related("franquia").all():
                    ag.save()
            except Exception as e:
                logger.exception(f"[FRANQUIA] Erro ao recalcular agentes do acomp #{instance.pk}: {e}")

            ag_principal = (
                instance.agentes
                .filter(tipo_agente="principal")
                .select_related("agente")
                .first()
            )

            if not ag_principal:
                logger.warning(f"[GS] Acomp #{instance.pk} concluído, mas sem agente principal.")
                _enviar("concluido")
                return

            extra = {
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

                "total": str(instance.total_valor_agentes or Decimal("0.00")),
            }

            _enviar("concluido", extra_payload=extra)

    transaction.on_commit(_on_commit)