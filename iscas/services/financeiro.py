"""Quanto uma solicitação rendeu e quanto custou (ISC-RF-39).

Receita é o valor cobrado do cliente, gravado na abertura; custo é a soma do
que os agentes cobraram. Retirada na base não tem custo de agente — o cliente
foi buscar.

Service, e não property no model: uma property que somasse
`self.atribuicoes.all()` seria N+1 garantido na listagem. O par
`totais_da_solicitacao`/`totais_em_lote` espelha `cobertura`/`cobertura_em_lote`,
que é o padrão já estabelecido para isso no app.

**Risco aceito:** estes valores são comerciais, não PII nem credencial. A
visibilidade é imposta na view (que não os coloca no contexto de quem não pode
ver), não por cifragem nem row-level security — mesmo patamar do resto do app,
cujo risco de acesso por shell/admin já está documentado em `permissions.py`.
"""
from decimal import Decimal

from django.db.models import Case, IntegerField, Sum, When

from iscas.enums import StatusAtribuicao

#: Atribuições que contam no custo. CANCELADA fica de fora: o agente não
#: entregou, logo não há o que pagar — incluí-la inflaria o custo com trabalho
#: que não aconteceu.
_STATUS_QUE_CUSTAM = (
    StatusAtribuicao.RESERVADA,
    StatusAtribuicao.EM_ROTA,
    StatusAtribuicao.ENTREGUE,
)


def totais_da_solicitacao(solicitacao) -> dict:
    """Receita, custo e margem de uma solicitação.

    Returns:
        dict com `valor_cliente`, `custo_agentes`, `margem` e
        `tem_custo_incompleto`.

    Semântica que importa:

    - `margem` é `None` — nunca zero — quando não há valor do cliente. Zero é
      um valor de negócio (cortesia); `None` é ausência de informação, e
      confundir os dois faz um relatório mentir.
    - Atribuição de agente sem valor informado soma zero, **mas levanta**
      `tem_custo_incompleto`. Somar zero calado transforma a margem numa
      afirmação que ninguém conferiu.
    - Margem negativa é legítima e reportada: o agente cobrou mais do que o
      cliente pagou é um alerta real do negócio, não um erro de cálculo.
    """
    atribuicoes = list(
        solicitacao.atribuicoes.filter(status__in=_STATUS_QUE_CUSTAM)
    )
    return _montar(solicitacao.valor_cliente, atribuicoes)


def totais_em_lote(solicitacoes) -> dict:
    """O mesmo que `totais_da_solicitacao`, para várias, em consulta única.

    Returns:
        `{solicitacao_id: dict}`, com a mesma forma da função acima.
    """
    from iscas.models.operacao import Atribuicao

    solicitacoes = list(solicitacoes)
    ids = [s.pk for s in solicitacoes]
    if not ids:
        return {}

    # Uma consulta para todas: soma o custo e conta as atribuições de agente
    # sem valor, que é o que alimenta `tem_custo_incompleto`.
    agregados = {
        linha["solicitacao_id"]: linha
        for linha in (
            Atribuicao.objects.filter(
                solicitacao_id__in=ids, status__in=_STATUS_QUE_CUSTAM
            )
            .values("solicitacao_id")
            .annotate(
                custo=Sum("valor_agente"),
                # 1 para cada atribuição de agente sem valor; 0 no resto.
                # Retirada na base não conta: ela legitimamente não tem valor.
                sem_valor=Sum(
                    Case(
                        When(
                            valor_agente__isnull=True,
                            agente__isnull=False,
                            then=1,
                        ),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
            )
        )
    }

    resultado = {}
    for solicitacao in solicitacoes:
        linha = agregados.get(solicitacao.pk, {})
        custo = linha.get("custo") or Decimal("0.00")
        margem = (
            solicitacao.valor_cliente - custo
            if solicitacao.valor_cliente is not None
            else None
        )
        resultado[solicitacao.pk] = {
            "valor_cliente": solicitacao.valor_cliente,
            "custo_agentes": custo,
            "margem": margem,
            "tem_custo_incompleto": bool(linha.get("sem_valor")),
        }
    return resultado


def _montar(valor_cliente, atribuicoes) -> dict:
    custo = Decimal("0.00")
    incompleto = False
    for atribuicao in atribuicoes:
        if atribuicao.valor_agente is not None:
            custo += atribuicao.valor_agente
        elif not atribuicao.eh_retirada_base:
            # Retirada na base legitimamente não tem valor; agente sem valor é
            # informação que falta.
            incompleto = True

    return {
        "valor_cliente": valor_cliente,
        "custo_agentes": custo,
        "margem": valor_cliente - custo if valor_cliente is not None else None,
        "tem_custo_incompleto": incompleto,
    }
