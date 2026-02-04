def gerar_link_app_missao(acompanhamento, origem="web"):
    base_url = "https://www.intgoldensat.com.br/api"

    agente_nome = ""
    agente_principal = acompanhamento.agentes.filter(tipo_agente="principal").first()
    if agente_principal and agente_principal.agente:
        agente_nome = agente_principal.agente.nome

    return (
        f"{base_url}/missao.html"
        f"?id={acompanhamento.id}"
        f"&origem={acompanhamento.origem}"
        f"&agente={agente_nome}"
        f"&auto=1"
    )
