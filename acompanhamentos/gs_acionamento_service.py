import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class GSAcionamentoService:
    """Serviço para comunicar com o GS Acionamento (callback reverso)."""

    def __init__(self):
        self.base_url = getattr(settings, 'GS_ACIONAMENTO_URL', None)
        self.token = getattr(settings, 'GS_ACIONAMENTO_TOKEN', None)
        self.timeout = 30

    def _get_headers(self):
        return {
            'Authorization': f'Token {self.token}',
            'Content-Type': 'application/json'
        }

    def _post(self, endpoint, data):
        if not self.base_url or not self.token:
            logger.warning("GS Acionamento não configurado. Pulando callback.")
            return None

        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.post(
                url,
                json=data,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            print(f"[GS Callback] STATUS: {response.status_code}")
            print(f"[GS Callback] RESPOSTA: {response.text}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao notificar GS Acionamento: {e}")
            return None

    def _is_status_cancelado(self, status_requisicao):
        if not status_requisicao:
            return False
        return str(status_requisicao).strip().lower() in {"cancelado", "cancelada", "canceladas"}

    def notificar_acompanhamento_criado(self, requisicao_solicitacao, agente_principal):
        """
        Notifica o GS Acionamento que um acompanhamento foi criado.

        Args:
            requisicao_solicitacao: RequisicaoSolicitacao do INT
            agente_principal: registroacompanhamentoagente (agente principal do acompanhamento)
        """
        if not requisicao_solicitacao.id_externo:
            logger.warning(
                f"RequisicaoSolicitacao #{requisicao_solicitacao.pk} sem id_externo. "
                "Não é possível notificar GS."
            )
            return None

        # Nome do agente
        agente_nome = ""
        if agente_principal and agente_principal.agente:
            agente_nome = agente_principal.agente.nome or ""

        # Placa do agente
        placa_agente = ""
        if agente_principal:
            placa_agente = agente_principal.placa_agente or ""

        data = {
            'id_externo': requisicao_solicitacao.id_externo,  # PK do AgenteVeiculo no GS
            'status_requisicao': 'agendada',
            'agente': agente_nome,
            'placa_agente': placa_agente,
        }

        result = self._post('/api/callback/acompanhamento-criado/', data)
        if result and result.get('success'):
            logger.info(
                f"GS Acionamento notificado: AgenteVeiculo #{requisicao_solicitacao.id_externo} "
                f"→ agendada, agente={agente_nome}"
            )
        return result

    def notificar_status_requisicao(self, requisicao_solicitacao, *, status_requisicao, agente_principal=None, extra_payload=None):
        if not requisicao_solicitacao or not requisicao_solicitacao.id_externo:
            logger.warning(
                "RequisicaoSolicitacao sem id_externo. Não é possível notificar mudança de status no GS."
            )
            return None

        agente_nome = ""
        if agente_principal and getattr(agente_principal, "agente", None):
            agente_nome = getattr(agente_principal.agente, "nome", "") or ""

        placa_agente = ""
        if agente_principal:
            placa_agente = getattr(agente_principal, "placa_agente", "") or ""

        payload = {
            "id_externo": requisicao_solicitacao.id_externo,
            "status_requisicao": status_requisicao,
            "agente": agente_nome,
            "placa_agente": placa_agente,
        }

        if self._is_status_cancelado(status_requisicao):
            valor_cancelamento = getattr(requisicao_solicitacao, "valor_cancelamento", None)
            taxa_cancelamento_percentual = getattr(requisicao_solicitacao, "taxa_cancelamento_percentual", None)

            if valor_cancelamento is not None:
                payload["valor_cancelamento"] = str(valor_cancelamento)

            if taxa_cancelamento_percentual is not None:
                payload["taxa_cancelamento_percentual"] = int(taxa_cancelamento_percentual)

        if extra_payload:
            payload.update(extra_payload)

        result = self._post("/api/callback/acompanhamento-criado/", payload)
        if result and result.get("success"):
            logger.info(
                f"GS Acionamento notificado: id_externo={requisicao_solicitacao.id_externo} → {status_requisicao}"
            )
        return result

gs_acionamento = GSAcionamentoService()