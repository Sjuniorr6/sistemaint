"""Exceções de domínio do Iscas Fast.

Todas herdam de `IscasError`, o que permite às views tratarem falha de regra de
negócio sem confundi-la com erro de programação.
"""


class IscasError(Exception):
    """Base de toda falha de regra de negócio do app."""


class SaldoInsuficiente(IscasError):
    """Não há unidades disponíveis o bastante para a operação (ISC-RN-07)."""


class UnidadeIndisponivel(IscasError):
    """A unidade está reservada, ou em custódia diferente da esperada."""


class UnidadeTerminal(IscasError):
    """A unidade está em situação terminal e não pode ser origem (ISC-RN-05)."""


class TransicaoInvalida(IscasError):
    """A transição de status pedida não existe na tabela (ISC-ADR-08)."""


class MovimentacaoInvalida(IscasError):
    """O lançamento fere uma invariante do livro-razão (ISC-RN-02)."""


class EstornoInvalido(IscasError):
    """A movimentação não pode ser estornada (ISC-ADR-16)."""


class AgenteComSaldo(IscasError):
    """Desativar agente com saldo em custódia é bloqueado (ISC-RN-18)."""


class DepositoComSaldo(IscasError):
    """Desativar depósito com estoque é bloqueado.

    Mesmo princípio do `AgenteComSaldo`: desativação não pode evaporar
    estoque. O equipamento precisa ser transferido antes.
    """


class TipoModeloImutavel(IscasError):
    """O tipo do modelo já tem histórico e não pode mudar (ISC-RN-04)."""


class GeocodificacaoFalhou(IscasError):
    """O serviço de geocodificação não respondeu ou não achou o endereço.

    Nunca bloqueia o salvamento do cadastro (ISC-RF-02) — quem chama trata e
    grava com `geo_origem=PENDENTE`.
    """
