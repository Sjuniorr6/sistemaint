"""Camada de leitura (queries e filtros) do controle_acionamentos.

As views consomem os dados a partir daqui — nunca fazem query direta ao model.
"""
from controle_acionamentos.models import Acionamento, FranquiaAgente


def listar_acionamentos(cliente=None, agente=None, data_de=None, data_ate=None,
                        com_franquia=None):
    """DD-014/M3 — lista base de acionamentos, do mais recente ao mais antigo.

    Aceita um filtro opcional por cliente (AC-06.1, DD-015/M4): quando `cliente`
    é informado, restringe a listagem àquele cliente; None devolve todos.

    DD-016/M5 (AC-08.1): filtro opcional por agente. Os filtros são composáveis
    (aplicados em cascata sobre o mesmo queryset) e a ordenação DESC por
    data_hora_solicitado é aplicada independentemente deles.

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
    if data_de is not None:
        qs = qs.filter(data_hora_solicitado__date__gte=data_de)
    if data_ate is not None:
        qs = qs.filter(data_hora_solicitado__date__lte=data_ate)
    if com_franquia is not None:
        qs = qs.filter(franquia_agente__isnull=not com_franquia)
    return qs


def listar_franquias_por_cliente(cliente):
    """DD-015/M4 (AC-06.3) — alimenta o select de franquias do vínculo em lote:
    só as franquias do cliente filtrado, em ordem alfabética por nome.

    Ordering EXPLÍCITO aqui (regra da casa: nunca Meta.ordering). É um dropdown
    de escolha humana, não uma listagem cronológica — por isso ordena por nome,
    e não por data como o listar_acionamentos.
    """
    return FranquiaAgente.objects.filter(cliente=cliente).order_by("nome")
