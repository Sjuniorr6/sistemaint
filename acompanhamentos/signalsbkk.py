# acompanhamentos/signals.py

from django.db import transaction  # controla on_commit (não chama API antes de commitar)
from django.db.models.signals import pre_save, post_save  # sinais antes/depois do save
from django.dispatch import receiver  # decorator pra registrar os sinais

from .models import registroacompanhamento  # model que tem status_acompanhamento
from .gs_acionamento_service import gs_acionamento  # service que chama o GS
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=registroacompanhamento)
def _acomp_pre_save_guardar_status_antigo(sender, instance, **kwargs):
    """
    Guarda o status antigo antes de salvar, pra conseguir detectar mudança real.
    Sem isso, no post_save você só enxerga o valor novo (porque já salvou).
    """
    # Se não existe PK ainda, é criação: não tem "antes"
    if not instance.pk:
        instance._status_acomp_old = None
        return

    # Busca só o campo que interessa (mais leve)
    old = (
        sender.objects
        .filter(pk=instance.pk)
        .values_list("status_acompanhamento", flat=True)
        .first()
    )

    # Armazena no próprio objeto em memória (só pra esse ciclo de request)
    instance._status_acomp_old = old


@receiver(post_save, sender=registroacompanhamento)
def _acomp_post_save_notificar_gs(sender, instance, created, **kwargs):
    old_status = getattr(instance, "_status_acomp_old", None)
    new_status = instance.status_acompanhamento

    # Só dispara quando realmente mudou
    if old_status == new_status:
        return

    # Precisa do vínculo com a RequisicaoSolicitacao (id_externo do GS)
    req = getattr(instance, "requisicao_solicitacao", None)
    if not req or not getattr(req, "id_externo", None):
        logger.warning(
            f"[GS] Acompanhamento #{instance.pk} mudou status para '{new_status}', "
            f"mas não tem requisicao_solicitacao ou req.id_externo."
        )
        return

    def _time_iso(t):
        return t.isoformat() if t else None  # "HH:MM:SS"

    def _date_iso(d):
        return d.isoformat() if d else None  # "YYYY-MM-DD"

    def _duration_seconds(td):
        return int(td.total_seconds()) if td else None  # envia em segundos (int)

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

    # Roda depois do commit
    def _on_commit():
        # ✅ EM ANDAMENTO (igual você já queria)
        if new_status == "em_andamento":
            _enviar("em_andamento")
            return

        # ✅ CONCLUÍDO + CAMPOS
        if new_status == "concluido":
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

                # DurationField: manda em segundos (GS converte pra timedelta)
                "horario_total": _duration_seconds(ag_principal.horario_total),
                "horario_excedente": _duration_seconds(ag_principal.horario_excedente),

                # Decimal: manda como string
                "total": str((instance.total_valor_agentes or Decimal("0.00"))),
            }

            _enviar("concluido", extra_payload=extra)

    transaction.on_commit(_on_commit)