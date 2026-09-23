"""Context processor do Iscas Fast.

Deriva a seção ativa da navegação a partir do nome da URL resolvida, em vez de
cada view passar `secao` à mão — uma view nova entra na navegação sem precisar
lembrar disso.
"""
from iscas.enums import Capacidade

#: Prefixo do nome da URL → seção destacada na navegação.
_SECAO_POR_PREFIXO = (
    ("painel_saldo", "saldos"),
    ("painel", "painel"),
    ("mapa", "mapa"),
    ("busca_proximidade", "mapa"),
    ("solicitacao", "solicitacoes"),
    ("atribuicao", "solicitacoes"),
    ("retornaveis", "retornaveis"),
    ("registrar_retorno", "retornaveis"),
    ("unidade", "unidades"),
    ("entrada", "unidades"),
    ("transferencia", "unidades"),
    ("baixa", "unidades"),
    ("manutencao", "unidades"),
    ("agente", "agentes"),
    ("historico_agente", "agentes"),
    ("cliente", "clientes"),
    ("historico_cliente", "clientes"),
    ("deposito", "depositos"),
    ("modelo", "modelos"),
    ("extrato", "extrato"),
    ("auditoria", "auditoria"),
)


def secao_ativa(request):
    """Expõe `secao` para o template de navegação do app."""
    match = getattr(request, "resolver_match", None)
    if not match or match.app_name != "iscas":
        return {}

    nome = match.url_name or ""
    for prefixo, secao in _SECAO_POR_PREFIXO:
        if nome.startswith(prefixo):
            return {"secao": secao}
    return {}


def capacidades_iscas(request):
    """Expõe `cap` para os templates condicionarem menu e botões.

    O botão escondido NÃO é a autorização — quem barra é o decorator `exige`
    na view. Isto existe para não oferecer ao usuário um caminho que vai
    terminar em 403.

    Mesma guarda de `secao_ativa`: fora do app iscas devolve vazio, para não
    pagar a consulta de grupos nas páginas dos outros apps do GSInt.
    """
    match = getattr(request, "resolver_match", None)
    if not match or match.app_name != "iscas":
        return {}

    from iscas.permissions import capacidades_do

    permitidas = capacidades_do(request.user)
    return {"cap": {c.value: (c in permitidas) for c in Capacidade}}
