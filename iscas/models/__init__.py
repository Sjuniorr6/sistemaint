"""Models do Iscas Fast, organizados por responsabilidade.

O import agregado aqui mantém `from iscas.models import Agente` funcionando e
faz o Django enxergar todos os models do app.
"""
from iscas.models.base import ActiveManager, BaseModel, EnderecoGeoMixin, LogModel
from iscas.models.cadastro import Agente, Cliente, Deposito, ModeloEquipamento
from iscas.models.config import ConfiguracaoIscas, GeocodeCache
from iscas.models.custodia import (
    Custodia,
    Movimentacao,
    MovimentacaoUnidade,
    Unidade,
    UnidadeQuerySet,
)
from iscas.models.operacao import (
    Atribuicao,
    AtribuicaoUnidade,
    ItemSolicitacao,
    Solicitacao,
    SolicitacaoEvento,
)

__all__ = [
    "ActiveManager",
    "Agente",
    "Atribuicao",
    "AtribuicaoUnidade",
    "BaseModel",
    "Cliente",
    "ConfiguracaoIscas",
    "Custodia",
    "Deposito",
    "EnderecoGeoMixin",
    "GeocodeCache",
    "ItemSolicitacao",
    "LogModel",
    "ModeloEquipamento",
    "Movimentacao",
    "MovimentacaoUnidade",
    "Solicitacao",
    "SolicitacaoEvento",
    "Unidade",
    "UnidadeQuerySet",
]
