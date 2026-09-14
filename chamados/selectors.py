"""Camada de leitura (queries e filtros) do app Chamados.

As views consomem os dados a partir daqui — nunca fazem query direta ao model.
Os indicadores do painel (RF-08, ADR-011) são derivados do estado corrente e do
log de eventos do dia, sem contadores mantidos à mão (RN-05).
"""
from django.utils import timezone

from chamados.enums import Acao, Setor, Status
from chamados.models import Chamado


def listar_chamados(status=None, responsavel_inteligencia=None):
    """Fila de chamados, do mais recente ao mais antigo (RF-07).

    Filtros opcionais e composáveis. `select_related` em responsavel/aberto_por/
    responsavel_inteligencia porque a tabela exibe esses nomes por linha (evita
    N+1 na renderização). NÃO aplica visibilidade por papel — isso é feito por
    `chamados_visiveis_para`, que restringe o queryset ANTES destes filtros.
    """
    qs = Chamado.objects.select_related(
        "cliente", "modelo_equipamento", "responsavel", "aberto_por",
        "responsavel_inteligencia"
    ).order_by("-aberto_em")
    if status is not None:
        qs = qs.filter(status=status)
    if responsavel_inteligencia is not None:
        qs = qs.filter(responsavel_inteligencia=responsavel_inteligencia)
    return qs


def chamados_visiveis_para(user):
    """Queryset de chamados que `user` pode ENXERGAR (fronteira de visibilidade).

    - Quality e superuser: veem todos os chamados (abrem e acompanham tudo).
    - Inteligência: vê SOMENTE os encaminhados a ela própria
      (responsavel_inteligencia == user) — nunca os de quality nem os de outros
      colegas de inteligência.

    Aplicado na camada de dados (não só na UI): é o mesmo queryset que a fila e o
    `get_object_or_404` do detalhe usam, então a proteção não depende do template.
    """
    from django.db.models import Q

    from chamados.permissions import (
        is_comercial,
        is_expedicao,
        is_financeiro,
        is_laboratorio,
        is_quality,
    )

    qs = Chamado.objects.select_related(
        "cliente", "modelo_equipamento", "responsavel", "aberto_por",
        "responsavel_inteligencia"
    ).order_by("-aberto_em")
    if is_quality(user):  # cobre superuser (is_quality já o inclui)
        return qs

    # Inteligência vê os encaminhados a ela; Expedição vê a fila EXPEDICAO;
    # Laboratório, a LABORATORIO; Comercial, a COMERCIAL. Um usuário de vários
    # grupos vê a união dos conjuntos.
    filtro = Q(responsavel_inteligencia=user)
    if is_expedicao(user):
        filtro |= Q(status=Status.EXPEDICAO)
    if is_laboratorio(user):
        filtro |= Q(status=Status.LABORATORIO)
    if is_comercial(user):
        filtro |= Q(status=Status.COMERCIAL)
    if is_financeiro(user):
        filtro |= Q(status=Status.FINANCEIRO)
    return qs.filter(filtro)


def manutencoes_para_vinculo():
    """Manutenções que o Laboratório pode vincular ao chamado.

    Espelha o queryset da tela "Registro das entradas"
    (registrodemanutencao.views.entradasListView): mesmos status em andamento e o
    mesmo corte de data, do mais recente para o mais antigo.
    """
    from datetime import date

    from registrodemanutencao.models import registrodemanutencao

    return (
        registrodemanutencao.objects.filter(
            status__in=[
                "Pendente",
                "Manutenção",
                "Aguardando Aprovação",
                "Aprovado pela Diretoria",
                "Reprovado pela Inteligência",
            ],
            # __date evita comparar DateTimeField com date naive (USE_TZ ativo).
            data_criacao__date__gte=date(2026, 1, 1),
        )
        .select_related("nome")  # empresa exibida no rótulo do select
        .order_by("-id")
    )


def metricas_painel():
    """Os três indicadores do painel (RF-08, ADR-011), derivados do log/estado.

    Fila Ativa e Encaminhados são contagens do estado corrente (cache consistente
    com o último evento). Resolvidos Hoje conta eventos de transição PARA
    RESOLVIDO na data corrente (não o campo status, para não contar resolvidos de
    outros dias) — fonte única no log (RN-05).
    """
    from chamados.models import ChamadoEvento

    hoje = timezone.localdate()
    resolvidos_hoje = (
        ChamadoEvento.objects.filter(
            estado_destino=Status.RESOLVIDO,
            acao__in=[Acao.FINALIZAR, Acao.RESOLVER],
            criado_em__date=hoje,
        )
        .values("chamado")
        .distinct()
        .count()
    )
    return {
        "fila_ativa": Chamado.objects.filter(status=Status.ABERTO).count(),
        "encaminhados": Chamado.objects.filter(status=Status.ENCAMINHADO).count(),
        "resolvidos_hoje": resolvidos_hoje,
    }


def acoes_disponiveis(user, chamado):
    """Ações que a UI deve oferecer para (user, chamado) — RF-07, RF-21.

    Espelha a máquina de estados + posse, mas é só reflexo de UI; a autorização
    real está no service (RN-18). Devolve uma lista de valores de Acao.

    Enquanto o setor não tiver ACEITO a tratativa, a única ação oferecida é o
    próprio aceite (marco inicial do SLA) — o service impõe a mesma regra.
    """
    from chamados.permissions import pode_agir
    from chamados.services import TRANSICOES, passagem_aberta

    if not pode_agir(user, chamado):
        return []

    passagem = passagem_aberta(chamado)
    if passagem is not None and not passagem.esta_aceita:
        return [Acao.ACEITAR_TRATATIVA]

    disponiveis = []
    for acao, transicao in TRANSICOES.items():
        if chamado.status in transicao.origens:
            disponiveis.append(acao)

    # Registrar contato não é transição (não muda status): é oferecido enquanto o
    # chamado está na Expedição, ao lado do "Marcar chegada".
    if chamado.status == Status.EXPEDICAO:
        disponiveis.append(Acao.REGISTRAR_CONTATO)
    return disponiveis


# ---------------------------------------------------------------------------
# Linha do tempo por setor + filtro por período (fila e exportação)
# ---------------------------------------------------------------------------

# Cada setor vira uma coluna "entrou em" na fila. O nome da anotação é
# `entrada_<setor em minúsculo>` — a ordem aqui é a do fluxo e a das colunas.
SETORES_TIMELINE = [
    Setor.QUALITY,
    Setor.INTELIGENCIA,
    Setor.EXPEDICAO,
    Setor.LABORATORIO,
    Setor.COMERCIAL,
    Setor.FINANCEIRO,
]


def campo_entrada(setor) -> str:
    """Nome da anotação que guarda a entrada do chamado naquele setor."""
    return f"entrada_{str(setor).lower()}"


def anotar_entradas_por_setor(qs):
    """Anota, por chamado, QUANDO ele entrou em cada setor (linha do tempo).

    Uma `Subquery` correlata por setor, pegando o `chegou_em` da PRIMEIRA
    passagem naquele setor (mandamento 2: nunca `prefetch_related` da relação
    inteira + `.first()` por item — isso carregaria todas as passagens e ainda
    geraria N+1). A contagem de queries fica CONSTANTE, independente do número
    de linhas.

    Primeira passagem, e não a última: o que a operação pergunta é "quando este
    chamado deu entrada na expedição", e o marco é a entrada original — um
    chamado que volta ao setor depois não deve reescrever a data de entrada.
    """
    from django.db.models import OuterRef, Subquery

    from chamados.models import PassagemSetor

    anotacoes = {}
    for setor in SETORES_TIMELINE:
        passagens = (
            PassagemSetor.objects.filter(chamado=OuterRef("pk"), setor=setor)
            .order_by("chegou_em", "id")
            .values("chegou_em")[:1]
        )
        anotacoes[campo_entrada(setor)] = Subquery(passagens)
    return qs.annotate(**anotacoes)


def filtrar_fila(qs, setor=None, data_de=None, data_ate=None):
    """Aplica o filtro de período sobre a linha do tempo (RF-07 + exportação).

    Com `setor`, o recorte é pela ENTRADA NAQUELE SETOR: "quantos chamados
    entraram na expedição entre tal e tal data" — inclui os que já saíram de lá
    (passaram) e os que continuam no setor, porque a pergunta é sobre a entrada,
    não sobre o status atual.

    Sem `setor`, o período recorta a ABERTURA do chamado, que é a leitura
    natural de "chamados abertos de tal data até tal data".

    As duas pontas são inclusivas e comparadas por `__date`, para não misturar
    date naive com DateTimeField aware (USE_TZ ligado).
    """
    campo = f"{campo_entrada(setor)}__date" if setor else "aberto_em__date"
    if data_de is not None:
        qs = qs.filter(**{f"{campo}__gte": data_de})
    if data_ate is not None:
        qs = qs.filter(**{f"{campo}__lte": data_ate})
    # Sem período, filtrar por setor ainda significa "passou por este setor".
    if setor and data_de is None and data_ate is None:
        qs = qs.filter(**{f"{campo_entrada(setor)}__isnull": False})
    return qs


def listar_fila(user, setor=None, data_de=None, data_ate=None):
    """Fila visível ao usuário, com a linha do tempo anotada e o período aplicado.

    Fonte única da tela e da exportação — as duas chamam exatamente isto, então
    o Excel sai com as MESMAS linhas que a tela mostra.
    """
    qs = anotar_entradas_por_setor(chamados_visiveis_para(user))
    return filtrar_fila(qs, setor=setor, data_de=data_de, data_ate=data_ate)
