"""Camada de leitura (queries e filtros) do controle_acionamentos.

As views consomem os dados a partir daqui — nunca fazem query direta ao model.
"""
from decimal import Decimal

from django.db.models import Case, DecimalField, IntegerField, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from controle_acionamentos.models import (
    Acionamento,
    Agente,
    Cliente,
    FranquiaAgente,
    ResponsavelAgente,
    ServicoCliente,
)


def listar_acionamentos(cliente=None, agente=None, responsavel=None,
                        data_de=None, data_ate=None, com_franquia=None):
    """DD-014/M3 — lista base de acionamentos, do mais recente ao mais antigo.

    Aceita um filtro opcional por cliente (AC-06.1, DD-015/M4): quando `cliente`
    é informado, restringe a listagem àquele cliente; None devolve todos.

    DD-016/M5 (AC-08.1): filtro opcional por agente. Os filtros são composáveis
    (aplicados em cascata sobre o mesmo queryset) e a ordenação DESC por
    data_hora_solicitado é aplicada independentemente deles.

    ST2 pós go-live: filtro opcional por responsável (FK responsavel_agente),
    espelho do filtro por agente — mesma filosofia composável.

    DD-016/M5 (AC-08.1): filtro por intervalo de data com fronteiras INCLUSIVAS
    pela parte de DATA (lookup __date) — "até o dia X" inclui qualquer hora do
    dia X. `data_de` e `data_ate` (objetos date) são independentes: passar só um
    dos dois também filtra (limite aberto do outro lado).

    DD-016/M5 (AC-08.1): filtro por status de franquia via booleano de domínio
    ("tem franquia?"): True = só vinculados, False = só sem franquia, None =
    todos. A tradução do vocabulário de tela ("Todos/Com/Sem" → booleano)
    pertence ao form (subtask 2), não aqui.

    select_related em cliente/agente/franquia_agente: o template exibe os três por
    linha; sem o join, seria uma query por FK por linha (N+1) na renderização.
    franquia_agente entrou em DD-032/ST3, quando a listagem passou a exibir a
    franquia por linha (coluna Franquia) — antes só cliente/agente eram exibidos.
    """
    qs = (
        Acionamento.objects
        .select_related("cliente", "agente", "franquia_agente")
        .order_by("-data_hora_solicitado")
    )
    if cliente is not None:
        qs = qs.filter(cliente=cliente)
    if agente is not None:
        qs = qs.filter(agente=agente)
    if responsavel is not None:
        qs = qs.filter(responsavel_agente=responsavel)
    if data_de is not None:
        qs = qs.filter(data_hora_solicitado__date__gte=data_de)
    if data_ate is not None:
        qs = qs.filter(data_hora_solicitado__date__lte=data_ate)
    if com_franquia is not None:
        qs = qs.filter(franquia_agente__isnull=not com_franquia)
    return qs


def listar_acionamentos_para_exportacao(cliente=None, agente=None, responsavel=None,
                                        data_de=None, data_ate=None,
                                        com_franquia=None):
    """Backlog pós-DD-070 item 3 — mesma base da listagem (reaproveita
    listar_acionamentos: filtros idênticos e o select_related de
    cliente/agente/franquia_agente, que a exportação percorre linha a linha —
    N+1 aqui seria multiplicado pelo tamanho do arquivo), trocando SÓ a
    ordenação: a planilha de pagamentos sai em ordem cronológica CRESCENTE de
    data_hora_solicitado (a listagem em tela é DESC).
    """
    return listar_acionamentos(
        cliente=cliente,
        agente=agente,
        responsavel=responsavel,
        data_de=data_de,
        data_ate=data_ate,
        com_franquia=com_franquia,
    ).order_by("data_hora_solicitado")


def listar_duplicatas_para_criacao(cliente, km_inicio, km_final,
                                   data_hora_inicio, data_hora_final):
    """DD-084/ST3 — candidatos a duplicata na CRIAÇÃO de acionamento: os já
    existentes com igualdade EXATA nos 5 campos recebidos, do mais recente ao
    mais antigo por criado_em (ordering explícito, regra da casa).

    A resposta dos operadores na DD-084/ST3 definiu a comparação pelos
    horários de início e fim com igualdade exata, deixando
    data_hora_solicitado de fora.

    select_related("cliente"): quem exibe as duplicatas mostra o cliente de
    cada linha — sem o join seria uma query por item (N+1).
    """
    return (
        Acionamento.objects
        .filter(
            cliente=cliente,
            km_inicio=km_inicio,
            km_final=km_final,
            data_hora_inicio=data_hora_inicio,
            data_hora_final=data_hora_final,
        )
        .select_related("cliente")
        .order_by("-criado_em")
    )


def listar_franquias_por_cliente(cliente):
    """DD-015/M4 (AC-06.3) — alimenta o select de franquias do vínculo em lote:
    só as franquias do cliente filtrado, em ordem alfabética por nome.

    Ordering EXPLÍCITO aqui (regra da casa: nunca Meta.ordering). É um dropdown
    de escolha humana, não uma listagem cronológica — por isso ordena por nome,
    e não por data como o listar_acionamentos.
    """
    return FranquiaAgente.objects.filter(cliente=cliente).order_by("nome")


def listar_servicos_ativos_por_cliente(cliente, incluir_id=None):
    """DD-066/ST1 — serviços ATIVOS de um cliente, na ORDEM DE DEFINIÇÃO dos
    choices de `nome` (a ordem de exibição do negócio, não alfabética), via
    Case/When sobre os valores dos choices.

    A ordem de negócio não é alfabética nem por criação, então não dá para um
    order_by de coluna: anota um índice por serviço via Case/When (na ordem em
    que os choices `Nome` foram definidos no model) e ordena por ele. Derivar a
    ordem de `Nome.values` mantém a fonte única — reordenar/renomear os choices
    reflete aqui sem tocar no selector.

    DD-067/ST4 — `incluir_id` (opcional): quando informado, o serviço de pk
    `incluir_id` entra na lista MESMO desativado (é o serviço já vinculado a um
    acionamento em edição, que o form aceita). O `cliente=cliente` continua sendo
    AND, então um id de outro cliente (ou inexistente) simplesmente não casa e é
    ignorado. O pk único garante que, se o incluído já é ativo, não duplica; e a
    mesma anotação Case/When o coloca na posição natural do catálogo (não no fim).
    """
    ordem = Case(
        *[
            When(nome=nome, then=Value(indice))
            for indice, nome in enumerate(ServicoCliente.Nome.values)
        ],
        output_field=IntegerField(),
    )
    filtro_visibilidade = Q(ativo=True)
    if incluir_id is not None:
        filtro_visibilidade |= Q(pk=incluir_id)
    return (
        ServicoCliente.objects
        .filter(filtro_visibilidade, cliente=cliente)
        .annotate(_ordem=ordem)
        .order_by("_ordem")
    )


def contar_acionamentos_no_mes(hoje=None):
    """DD-032/ST7 — contador do dashboard: acionamentos do mês/ano de `hoje`.

    `data_hora_solicitado` é a data de negócio (a mesma que ordena a listagem).
    `hoje` default = timezone.localdate() (nunca datetime.now() cru); o parâmetro
    existe para injeção de data em teste.
    """
    if hoje is None:
        hoje = timezone.localdate()
    return Acionamento.objects.filter(
        data_hora_solicitado__year=hoje.year,
        data_hora_solicitado__month=hoje.month,
    ).count()


def contar_sem_franquia():
    """DD-032/ST7 — contador do dashboard: acionamentos sem franquia vinculada.

    Sem recorte temporal: são os candidatos ao vínculo em lote, independente do mês.
    """
    return Acionamento.objects.filter(franquia_agente__isnull=True).count()


def contar_clientes():
    """DD-050/ST5 — contador da fileira de cadastros: total de Clientes."""
    return Cliente.objects.count()


def contar_agentes():
    """DD-050/ST5 — contador da fileira de cadastros: total de Agentes."""
    return Agente.objects.count()


def contar_responsaveis():
    """DD-050/ST5 — contador da fileira de cadastros: total de Responsáveis."""
    return ResponsavelAgente.objects.count()


def contar_franquias():
    """DD-050/ST5 — contador da fileira de cadastros: total de Franquias."""
    return FranquiaAgente.objects.count()


def somar_valor_agente_no_mes(hoje=None):
    """DD-048 — contador do dashboard: soma de valor_agente no mês/ano de `hoje`.

    Mesmo recorte temporal de contar_acionamentos_no_mes (lookup por
    data_hora_solicitado__year/__month). `hoje` default = timezone.localdate()
    (nunca datetime.now() cru); o parâmetro existe para injeção de data em teste.

    Coalesce sobre o Sum garante Decimal("0") para mês vazio (aggregate de Sum
    devolveria None). Value com output_field=DecimalField mantém o tipo Decimal.
    """
    if hoje is None:
        hoje = timezone.localdate()
    agregado = Acionamento.objects.filter(
        data_hora_solicitado__year=hoje.year,
        data_hora_solicitado__month=hoje.month,
    ).aggregate(
        total=Coalesce(
            Sum("valor_agente"),
            Value(Decimal("0"), output_field=DecimalField()),
        )
    )
    return agregado["total"]


def somar_valor_cliente_no_mes(hoje=None):
    """DD-070/ST5 — contador do dashboard: soma de valor_cliente no mês/ano de
    `hoje`, espelho fiel do somar_valor_agente_no_mes (mesmo recorte temporal,
    mesmo Coalesce para Decimal("0") em mês vazio). Legado ainda sem backfill é
    NULL e fica fora da soma, como o pendente do agente.
    """
    if hoje is None:
        hoje = timezone.localdate()
    agregado = Acionamento.objects.filter(
        data_hora_solicitado__year=hoje.year,
        data_hora_solicitado__month=hoje.month,
    ).aggregate(
        total=Coalesce(
            Sum("valor_cliente"),
            Value(Decimal("0"), output_field=DecimalField()),
        )
    )
    return agregado["total"]


def listar_historico_do_acionamento(acionamento):
    """DD-049/ST4 — históricos de um acionamento, mais recente primeiro
    (Meta.ordering do model), com o editor pré-carregado para o template
    (select_related evita N+1 ao exibir quem editou por linha).

    A query parte da instância via related_name="historico" — não precisa
    importar o model AcionamentoHistorico aqui.
    """
    return acionamento.historico.select_related("editado_por").all()


def mapear_franquias_por_pk(pks):
    """Backlog DD-070 1c — dict pk -> nome das franquias pedidas, em UMA query
    (in_bulk). Pk inexistente na coleção simplesmente não aparece no dict —
    quem consome (formatar_valor_trilha) cai no fallback cru.

    Alimenta a apresentação da trilha no detalhe: troca o pk gravado no
    histórico pelo nome da franquia. Coleção vazia nem toca o banco (in_bulk
    devolve {} direto).
    """
    return {
        pk: franquia.nome
        for pk, franquia in FranquiaAgente.objects.in_bulk(pks).items()
    }
