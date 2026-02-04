# acompanhamentos/utils_missao.py
from urllib.parse import urlencode
from django.conf import settings

def gerar_link_app_missao(acompanhamento):
    """
    Gera o LINK WEB que será enviado/aberto no navegador.
    Esse link (missao.html) redireciona para o deep link do app.
    """

    # base_url = getattr(settings, "AGENTTRACKER_WEB_BASE_URL", "https://intgoldensat.com.br")
    base_url = getattr(settings, "AGENTTRACKER_WEB_BASE_URL", "http://127.0.0.1:8000")

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

    return f"{base_url}/static/missao.html?{urlencode(params)}"
