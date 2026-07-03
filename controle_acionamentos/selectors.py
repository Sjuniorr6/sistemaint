"""Camada de leitura (queries e filtros) do controle_acionamentos.

As views consomem os dados a partir daqui — nunca fazem query direta ao model.
"""
from controle_acionamentos.models import Acionamento


def listar_acionamentos(cliente=None):
    """DD-014/M3 — lista base de acionamentos, do mais recente ao mais antigo.

    Aceita um filtro opcional por cliente (AC-06.1, DD-015/M4): quando `cliente`
    é informado, restringe a listagem àquele cliente; None devolve todos.

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
    return qs
