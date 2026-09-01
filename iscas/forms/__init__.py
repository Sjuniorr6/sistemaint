"""Forms do Iscas Fast.

Forms validam formato e coerência de campo; regra de negócio fica no service
(ARCHITECTURE, "Service Layer"). O que um form NUNCA faz aqui é mover estoque.
"""
from iscas.forms.cadastro import AgenteForm, ClienteForm, DepositoForm, ModeloForm
from iscas.forms.custodia import (
    BaixaForm,
    EntradaLoteForm,
    EstornoForm,
    ManutencaoForm,
    RetornoForm,
    RetornoManutencaoForm,
    TransferenciaForm,
)
from iscas.forms.operacao import (
    AtribuicaoForm,
    BuscaProximidadeForm,
    ConfirmarEntregaForm,
    EscolhaUnidadesForm,
    ExtratoFiltroForm,
    MotivoForm,
    SolicitacaoForm,
)

__all__ = [
    "AgenteForm",
    "AtribuicaoForm",
    "BaixaForm",
    "BuscaProximidadeForm",
    "ClienteForm",
    "ConfirmarEntregaForm",
    "DepositoForm",
    "EntradaLoteForm",
    "EscolhaUnidadesForm",
    "EstornoForm",
    "ExtratoFiltroForm",
    "ManutencaoForm",
    "ModeloForm",
    "MotivoForm",
    "RetornoForm",
    "RetornoManutencaoForm",
    "SolicitacaoForm",
    "TransferenciaForm",
]
