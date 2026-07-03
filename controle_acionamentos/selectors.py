"""Camada de leitura (queries e filtros) do controle_acionamentos.

As views consomem os dados a partir daqui — nunca fazem query direta ao model.
"""
from controle_acionamentos.models import Acionamento


def listar_acionamentos():
    """DD-014/M3 — lista base de acionamentos, do mais recente ao mais antigo."""
    return Acionamento.objects.order_by("-data_hora_solicitado")
