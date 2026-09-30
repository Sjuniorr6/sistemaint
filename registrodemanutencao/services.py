# registrodemanutencao/services.py

from .models import registro_manutencao_backup

def criar_backup_manutencao(manutencao, usuario):
    # Entradas novas guardam produto/customização/contrato nos itens (que não
    # mudam após a criação); no backup, vão como texto-resumo nos mesmos campos.
    itens = resumo_itens(manutencao)

    registro_manutencao_backup.objects.create(
        manutencao_original_id=manutencao.id,

        nome=manutencao.nome,
        cliente_id_snapshot=manutencao.nome.id if manutencao.nome else None,
        cliente_nome_snapshot=str(manutencao.nome) if manutencao.nome else None,

        tipo_entrada=manutencao.tipo_entrada,

        tipo_produto=manutencao.tipo_produto,
        produto_id_snapshot=manutencao.tipo_produto.id if manutencao.tipo_produto else None,
        produto_nome_snapshot=str(manutencao.tipo_produto) if manutencao.tipo_produto else (itens["produtos"] or None),

        motivo=manutencao.motivo,
        tipo_customizacao=manutencao.tipo_customizacao,
        recebimento=manutencao.recebimento,
        entregue_por_retirado_por=manutencao.entregue_por_retirado_por,

        id_equipamentos=manutencao.id_equipamentos,
        quantidade=manutencao.quantidade,

        tipo_contrato=manutencao.tipo_contrato or itens["contratos"],
        customizacaoo=manutencao.customizacaoo or itens["customizacoes"],
        numero_equipamento=manutencao.numero_equipamento,
        observacoes=manutencao.observacoes,

        tratativa=manutencao.tratativa,

        imagem=manutencao.imagem.name if manutencao.imagem else None,
        imagem2=manutencao.imagem2.name if manutencao.imagem2 else None,

        status=manutencao.status,
        status_tratativa=manutencao.status_tratativa,

        data_criacao_original=manutencao.data_criacao,
        data_devolucao=manutencao.data_devolucao,

        backup_criado_por=usuario
    )


def criar_entrada(entrada, itens, chamado=None):
    """Grava a entrada de equipamento e os seus tipos de produto (itens).

    `entrada`: registrodemanutencao ainda não salvo (dados da entrega).
    `itens`: ItemEntrada não salvos, um por tipo de produto.
    `chamado`: quando a entrada nasce do chamado (Expedição), é vinculada a ele
    na mesma transação — se o vínculo falhar, a entrada não fica órfã.

    Os campos de resumo da entrada são DERIVADOS dos itens: `numero_equipamento`
    (todos os nºs, separados por espaço — as listas filtram e contam por ele) e
    `quantidade` (total). Tipo de produto/customização/contrato ficam nos itens.
    """
    from django.db import transaction

    from .models import ItemEntrada

    with transaction.atomic():
        entrada.numero_equipamento = " ".join(i.numero_equipamento for i in itens)
        entrada.quantidade = sum(i.quantidade for i in itens)
        entrada.save()
        for item in itens:
            item.registro = entrada
        ItemEntrada.objects.bulk_create(itens)
        if chamado is not None:
            from chamados.services import vincular_entrada

            vincular_entrada(chamado, entrada)
    return entrada


def resumo_itens(registro):
    """Textos dos tipos de produto da entrada, para PDFs (laudo e protocolo).

    Valores repetidos entre itens (ex.: mesmo contrato) aparecem uma vez só.
    """
    from xml.sax.saxutils import escape

    itens = list(registro.itens.select_related('tipo_produto'))

    def unicos(valores):
        return ", ".join(dict.fromkeys(v for v in valores if v))

    return {
        "produtos": ", ".join(
            f"{i.tipo_produto or 'Não informado'} ({i.quantidade})" for i in itens
        ),
        "customizacoes": unicos(i.customizacao for i in itens),
        "contratos": unicos(i.tipo_contrato for i in itens),
        # Um produto por linha: "Isca 4G: 111 222" (<br/> = quebra no Paragraph).
        # Partes escapadas: o texto vai direto para um Paragraph do reportlab.
        "numeros_por_produto": "<br/>".join(
            f"{escape(str(i.tipo_produto or 'Não informado'))}: "
            f"{escape(i.numero_equipamento or '—')}"
            for i in itens
        ),
    }
