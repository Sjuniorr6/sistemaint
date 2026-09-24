"""E-mail avisando que uma solicitação teve toda a cobertura vinculada.

Dispara quando o último equipamento pedido ganha agente (ou depósito) — não na
confirmação de entrega. Quem recebe está em `DestinatarioNotificacao`, cadastrado
por tela: mudar a lista é decisão de operação, não de deploy.

Módulo separado de `mensagem.py` de propósito: aquele monta texto para o
operador copiar e a docstring dele diz que o sistema NÃO envia nada. Aqui envia.

O texto é montado em `montar_texto_entrega`, que não toca em SMTP — é o que
permite testá-lo sozinho.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from iscas.enums import StatusAtribuicao, TipoModelo
from iscas.services import financeiro

logger = logging.getLogger(__name__)

#: Atribuições que já seguram equipamento para a solicitação.
_STATUS_VINCULADOS = (
    StatusAtribuicao.RESERVADA,
    StatusAtribuicao.EM_ROTA,
    StatusAtribuicao.ENTREGUE,
)

_SEPARADOR = "-" * 43


def _moeda(valor) -> str:
    """`1234.5` → `1.234,50`. Formato brasileiro, sem passar por float."""
    inteiro, _, decimal = f"{Decimal(valor):.2f}".partition(".")
    negativo = inteiro.startswith("-")
    digitos = inteiro.lstrip("-")
    grupos = []
    while len(digitos) > 3:
        grupos.insert(0, digitos[-3:])
        digitos = digitos[:-3]
    grupos.insert(0, digitos)
    return ("-" if negativo else "") + ".".join(grupos) + "," + decimal


def _marca(condicao) -> str:
    """`(x)` ou `()`, como no formulário em papel que o e-mail imita."""
    return "(x)" if condicao else "()"


def _unidades_vinculadas(solicitacao):
    """Identificadores presos a esta solicitação, em ordem.

    Mesmo filtro de `cobertura()`: `AtribuicaoUnidade` não é apagada na
    entrega, só ganha `liberada_em` — então a linha continua respondendo por
    qual unidade atendeu o pedido.
    """
    from iscas.models.custodia import Unidade

    return list(
        Unidade.objects.filter(
            reservas__atribuicao__solicitacao=solicitacao,
            reservas__atribuicao__status__in=_STATUS_VINCULADOS,
        )
        .values_list("identificador", flat=True)
        .distinct()
        .order_by("identificador")
    )


def montar_texto_entrega(solicitacao) -> str:
    """Corpo do e-mail, no formato que a operação usa.

    Regra dos campos ausentes: **rótulo fixo fica, valor variável some.**
    "Comercial da conta" aparece mesmo vazio porque é assim no modelo em uso;
    já "Valor isca" some quando a solicitação é anterior ao preço por item, e
    "Contato" some na retirada na base — depósito não tem telefone.
    """
    cliente = solicitacao.cliente
    itens = list(solicitacao.itens.select_related("modelo"))
    tipos = {item.modelo.tipo for item in itens}
    identificadores = _unidades_vinculadas(solicitacao)

    linhas = [
        "Entrega",
        "",
        f"Solicitante: {solicitacao.solicitante_nome}",
        f"Cliente: {cliente.nome_razao_social}",
        f"Comercial da conta (se possuir): {solicitacao.comercial_responsavel}",
        f"CNPJ: {solicitacao.documento}",
        f"EMAIL: {solicitacao.email}",
        f"Telefone para contato: {solicitacao.telefone}",
        f"Descartável: {_marca(TipoModelo.DESCARTAVEL in tipos)} SIM",
        f"Retornável: {_marca(TipoModelo.RETORNAVEL in tipos)} NÃO",
        _SEPARADOR,
        f"Data: {timezone.localdate():%d/%m/%Y}",
        f"Quantidade: {len(identificadores):02d}",
        f"ID: {' / '.join(identificadores)}",
    ]

    # Uma linha por modelo: um preço único mentiria sobre qual item custa
    # quanto quando a solicitação mistura modelos.
    for item in itens:
        linhas.append(f"Modelo: {item.modelo}")
        if item.valor_unitario is not None:
            linhas.append(f"Valor isca: {_moeda(item.valor_unitario)}")

    if solicitacao.valor_cliente is not None:
        linhas.append(f"Valor total: {_moeda(solicitacao.valor_cliente)}")

    # Receita = material + o que se cobra por cada entrega. A linha só aparece
    # quando há frete cobrado: sem ela, repetiria o "Valor total" acima.
    totais = financeiro.totais_da_solicitacao(solicitacao)
    if totais["valor_entregas"]:
        linhas.append(f"Valor da entrega: {_moeda(totais['valor_entregas'])}")
        if totais["receita_total"] is not None:
            linhas.append(
                f"Valor total com entrega: {_moeda(totais['receita_total'])}"
            )

    if solicitacao.observacao:
        linhas += ["", f"obs: {solicitacao.observacao}"]

    for atribuicao in solicitacao.atribuicoes.filter(
        status__in=_STATUS_VINCULADOS
    ).select_related("agente", "deposito"):
        linhas += ["", f"Agente: {atribuicao.origem_nome}"]
        if atribuicao.valor_agente is not None:
            linhas.append(f"Valor frete/agente: {_moeda(atribuicao.valor_agente)}")
        if atribuicao.valor_entrega_cliente is not None:
            linhas.append(
                f"Valor entrega cobrado do cliente: "
                f"{_moeda(atribuicao.valor_entrega_cliente)}"
            )
        # Depósito não tem telefone — acessar `.telefone` ali seria
        # AttributeError em produção.
        if not atribuicao.eh_retirada_base:
            linhas.append(f"Contato: {atribuicao.agente.telefone}")

    return "\n".join(linhas)


def destinatarios_ativos() -> list:
    """E-mails que recebem a notificação agora."""
    from iscas.models.config import DestinatarioNotificacao

    return list(DestinatarioNotificacao.objects.values_list("email", flat=True))


def notificar_cobertura_fechada(solicitacao_id) -> bool:
    """Envia o aviso. Nunca propaga exceção.

    Recebe o `pk` e recarrega: é chamada por `transaction.on_commit`, e o
    objeto em memória foi mutado dentro da transação — recarregar garante que
    o e-mail descreve o que ficou gravado.

    Returns:
        True se enviou.
    """
    from iscas.models.operacao import Solicitacao

    try:
        solicitacao = Solicitacao.todos.get(pk=solicitacao_id)
    except Solicitacao.DoesNotExist:
        logger.warning("[iscas] solicitação %s sumiu antes do e-mail", solicitacao_id)
        return False

    destinatarios = destinatarios_ativos()
    if not destinatarios:
        logger.warning(
            "[iscas] solicitação %s fechou a cobertura, mas não há destinatário "
            "cadastrado para notificar",
            solicitacao_id,
        )
        return False

    try:
        EmailMessage(
            subject=(
                f"Entrega — Solicitação #{solicitacao.pk} — "
                f"{solicitacao.cliente.nome_razao_social}"
            ),
            body=montar_texto_entrega(solicitacao),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[],
            # `bcc`: a lista é interna e não precisa circular entre quem recebe.
            bcc=destinatarios,
        ).send(fail_silently=False)
    except Exception:
        # `except Exception` largo é deliberado: smtplib levanta SMTPException,
        # mas o backend custom do projeto levanta ssl.SSLError, e timeout/DNS
        # levantam OSError/gaierror. Enumerar é convite a deixar uma de fora —
        # e uma de fora derruba a vinculação que o operador acabou de fazer.
        logger.exception(
            "[iscas] falha ao notificar a solicitação %s", solicitacao_id
        )
        return False

    logger.info(
        "[iscas] solicitação %s notificada a %s destinatário(s)",
        solicitacao_id, len(destinatarios),
    )
    return True
