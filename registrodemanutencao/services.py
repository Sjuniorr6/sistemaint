# registrodemanutencao/services.py

from .models import registro_manutencao_backup

def criar_backup_manutencao(manutencao, usuario):

    registro_manutencao_backup.objects.create(
        manutencao_original_id=manutencao.id,

        nome=manutencao.nome,
        cliente_id_snapshot=manutencao.nome.id if manutencao.nome else None,
        cliente_nome_snapshot=str(manutencao.nome) if manutencao.nome else None,

        tipo_entrada=manutencao.tipo_entrada,

        tipo_produto=manutencao.tipo_produto,
        produto_id_snapshot=manutencao.tipo_produto.id if manutencao.tipo_produto else None,
        produto_nome_snapshot=str(manutencao.tipo_produto) if manutencao.tipo_produto else None,

        motivo=manutencao.motivo,
        tipo_customizacao=manutencao.tipo_customizacao,
        recebimento=manutencao.recebimento,
        entregue_por_retirado_por=manutencao.entregue_por_retirado_por,

        id_equipamentos=manutencao.id_equipamentos,
        quantidade=manutencao.quantidade,

        tipo_contrato=manutencao.tipo_contrato,
        customizacaoo=manutencao.customizacaoo,
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
