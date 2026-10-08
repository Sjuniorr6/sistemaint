"""Regras de negócio da requisição (camada chamada pelas views)."""
from django.db import transaction


def valor_total_da(requisicao, itens):
    """Valor total da requisição: soma dos modelos (quantidade × valor unitário)
    MAIS a taxa de envio. Regra única para criação, edição e a sobra da
    expedição parcial."""
    return sum(i.valor_total for i in itens) + (requisicao.taxa_envio or 0)


def criar_requisicao(requisicao, itens, chamado=None):
    """Grava a requisição e os seus modelos (itens) numa transação.

    `requisicao`: Requisicoes ainda não salva (dados do cliente, contrato, envio).
    `itens`: ItemRequisicao não salvos, um por modelo.
    `chamado`: quando a requisição de substituição nasce do chamado (Recepção),
    é vinculada a ele na mesma transação — vínculo falho desfaz a requisição.

    Os campos de resumo da requisição são DERIVADOS dos itens — a API dos
    parceiros, o kanban, a expedição parcial e o faturamento leem por eles:
    `numero_de_equipamentos` (total), `valor_total` (ver `valor_total_da`) e, do
    primeiro item, `tipo_produto`, `tipo_customizacao` e `valor_unitario`.

    O e-mail com o PDF do protocolo sai depois do commit: disparado no post_save
    (como antes), o PDF seria gerado sem os itens.
    """
    from requisicao.models import ItemRequisicao
    from requisicao.signals import notificar_requisicao_criada

    primeiro = itens[0]
    with transaction.atomic():
        requisicao.tipo_produto = primeiro.tipo_produto
        requisicao.tipo_customizacao = primeiro.customizacao or None
        requisicao.valor_unitario = primeiro.valor_unitario
        requisicao.numero_de_equipamentos = str(sum(i.quantidade for i in itens))
        requisicao.valor_total = valor_total_da(requisicao, itens)
        requisicao._skip_signals = True
        requisicao.save()
        for item in itens:
            item.requisicao = requisicao
        ItemRequisicao.objects.bulk_create(itens)
        if chamado is not None:
            from chamados.services import vincular_requisicao

            vincular_requisicao(chamado, requisicao)
        transaction.on_commit(lambda: notificar_requisicao_criada(requisicao))
    return requisicao


def resumo_itens(requisicao):
    """Textos dos modelos da requisição para PDFs, e-mails e exportações.

    Requisição antiga sem itens cai no campo único (`tipo_produto`).
    """
    itens = list(requisicao.itens.all())
    if not itens:
        return {
            "produtos": str(requisicao.tipo_produto or ""),
            "customizacoes": requisicao.tipo_customizacao or "",
            "valores": str(requisicao.valor_unitario or ""),
        }
    return {
        "produtos": ", ".join(f"{i.tipo_produto} ({i.quantidade})" for i in itens),
        "customizacoes": ", ".join(dict.fromkeys(i.customizacao for i in itens if i.customizacao)),
        # Um modelo: o valor; vários: "Isca 4G: 10.00, Isca 2G: 8.00".
        "valores": (
            str(itens[0].valor_unitario) if len(itens) == 1
            else ", ".join(f"{i.tipo_produto}: {i.valor_unitario}" for i in itens)
        ),
    }


# ---------------------------------------------------------------------------
# Regras que antes olhavam o produto único da requisição — agora pelos itens
# ---------------------------------------------------------------------------

# Produtos configurados pelo Setor Técnico (não passam pela Configuração/Kanban).
PRODUTOS_SETOR_TECNICO = ["GS310", "GS340", "GS390", "GS8310 (4G)"]
# A lista do Setor Técnico inclui também o PLUG AND PLAY (que, como antes, não
# sai da Configuração/Kanban).
PRODUTOS_LISTA_TECNICO = PRODUTOS_SETOR_TECNICO + ["PLUG AND PLAY"]


def com_algum_item_fora(qs, nomes):
    """Requisições com ALGUM modelo fora de `nomes` (ou sem itens, legado).

    Substitui o `.exclude(tipo_produto__nome__in=nomes)`: uma requisição mista
    (ex.: GS310 + isca 4G) continua na Configuração/Kanban pela parte que é dela.
    """
    from django.db.models import Exists, OuterRef

    from requisicao.models import ItemRequisicao

    itens = ItemRequisicao.objects.filter(requisicao=OuterRef("pk"))
    return qs.filter(
        Exists(itens.exclude(tipo_produto__nome__in=nomes)) | ~Exists(itens)
    )


def com_algum_item_em(qs, nomes):
    """Requisições com ALGUM modelo em `nomes` (substitui `filter(tipo_produto__nome__in=...)`)."""
    from django.db.models import Exists, OuterRef

    from requisicao.models import ItemRequisicao

    return qs.filter(Exists(ItemRequisicao.objects.filter(
        requisicao=OuterRef("pk"), tipo_produto__nome__in=nomes
    )))


def _eh_nome_carregador_cabo(nome):
    nome = (nome or "").strip().upper()
    return "CARREGADOR" in nome and "CABO" in nome


def eh_carregador_cabo(requisicao):
    """True se TODOS os modelos da requisição são CARREGADOR + CABO (esses não
    exigem ID de equipamento no kanban). Sem itens (legado), olha o produto único."""
    itens = list(requisicao.itens.all())
    if not itens:
        produto = requisicao.tipo_produto
        return bool(produto) and _eh_nome_carregador_cabo(produto.nome)
    return all(_eh_nome_carregador_cabo(i.tipo_produto.nome) for i in itens)


def tem_varios_modelos(requisicao):
    return len(requisicao.itens.all()) > 1


def atualizar_quantidades(requisicao, quantidades):
    """Edição: grava a nova quantidade de cada modelo e recalcula o resumo da
    requisição (total de equipamentos e valor total) na mesma transação.

    `quantidades`: {pk do ItemRequisicao: quantidade}. Modelo, customização e
    valor unitário não mudam aqui.
    """
    itens = list(requisicao.itens.all())
    for item in itens:
        if item.pk in quantidades:
            item.quantidade = quantidades[item.pk]
    with transaction.atomic():
        from requisicao.models import ItemRequisicao

        ItemRequisicao.objects.bulk_update(itens, ["quantidade"])
        requisicao.numero_de_equipamentos = str(sum(i.quantidade for i in itens))
        requisicao.valor_total = valor_total_da(requisicao, itens)
        requisicao.save(update_fields=["numero_de_equipamentos", "valor_total"])
    return requisicao
