"""Camada de leitura (queries e filtros) do controle_acionamentos.

As views consomem os dados a partir daqui — nunca fazem query direta ao model.
"""
from controle_acionamentos.models import Acionamento, FranquiaAgente


def listar_acionamentos(cliente=None, agente=None):
    """DD-014/M3 — lista base de acionamentos, do mais recente ao mais antigo.

    Aceita um filtro opcional por cliente (AC-06.1, DD-015/M4): quando `cliente`
    é informado, restringe a listagem àquele cliente; None devolve todos.

    DD-016/M5 (AC-08.1): filtro opcional por agente. Os filtros são composáveis
    (aplicados em cascata sobre o mesmo queryset) e a ordenação DESC por
    data_hora_solicitado é aplicada independentemente deles.

    select_related em cliente/agente: o template exibe esses dois por linha;
    sem o join, seria uma query por FK por linha (N+1) na renderização.
    """
    qs = (
        Acionamento.objects
        .select_related("cliente", "agente")
        .order_by("-data_hora_solicitado")
    )
    if cliente is not None:
        qs = qs.filter(cliente=cliente)
    if agente is not None:
        qs = qs.filter(agente=agente)
    return qs


def listar_franquias_por_cliente(cliente):
    """DD-015/M4 (AC-06.3) — alimenta o select de franquias do vínculo em lote:
    só as franquias do cliente filtrado, em ordem alfabética por nome.

    Ordering EXPLÍCITO aqui (regra da casa: nunca Meta.ordering). É um dropdown
    de escolha humana, não uma listagem cronológica — por isso ordena por nome,
    e não por data como o listar_acionamentos.
    """
    return FranquiaAgente.objects.filter(cliente=cliente).order_by("nome")
