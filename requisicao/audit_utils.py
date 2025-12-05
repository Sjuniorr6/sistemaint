"""
Utilitários para facilitar o registro de logs de auditoria
"""
from .audit_models import AuditLog, CampoAlterado


def registrar_criacao(objeto, usuario, request=None):
    """Registra a criação de uma requisição ou manutenção"""
    return AuditLog.registrar(
        objeto=objeto,
        acao='criacao' if hasattr(objeto, 'comercial') else 'manutencao_criacao',
        usuario=usuario,
        status_novo=objeto.status if hasattr(objeto, 'status') else None,
        observacao=f"ID: {objeto.id}",
        request=request
    )


def registrar_aprovacao(objeto, usuario, request=None):
    """Registra aprovação de requisição ou manutenção"""
    return AuditLog.registrar(
        objeto=objeto,
        acao='aprovacao' if hasattr(objeto, 'comercial') else 'manutencao_aprovacao',
        usuario=usuario,
        status_anterior=objeto.status if hasattr(objeto, 'status') else None,
        status_novo='Aprovado',
        request=request
    )


def registrar_reprovacao(objeto, usuario, motivo=None, request=None):
    """Registra reprovação de requisição ou manutenção"""
    return AuditLog.registrar(
        objeto=objeto,
        acao='reprovacao' if hasattr(objeto, 'comercial') else 'manutencao_reprovacao',
        usuario=usuario,
        status_anterior=objeto.status if hasattr(objeto, 'status') else None,
        status_novo='Reprovado',
        observacao=motivo,
        request=request
    )


def registrar_atribuicao(objeto, usuario, responsavel_nome, request=None):
    """Registra atribuição de responsável"""
    return AuditLog.registrar(
        objeto=objeto,
        acao='atribuicao' if hasattr(objeto, 'comercial') else 'manutencao_atribuicao',
        usuario=usuario,
        detalhes={'responsavel_atribuido': responsavel_nome},
        observacao=f"Responsável atribuído: {responsavel_nome}",
        request=request
    )


def registrar_mudanca_status(objeto, usuario, status_anterior, status_novo, request=None):
    """Registra mudança de status (incluindo movimentações no Kanban)"""
    acao = 'status_change'
    if hasattr(objeto, 'comercial'):  # É requisição
        if 'kanban' in str(status_novo).lower() or status_novo in ['recebido', 'em_progresso', 'auditoria']:
            acao = 'kanban_movido'
    else:  # É manutenção
        acao = 'manutencao_status'
    
    return AuditLog.registrar(
        objeto=objeto,
        acao=acao,
        usuario=usuario,
        status_anterior=status_anterior,
        status_novo=status_novo,
        request=request
    )


def registrar_expedicao(objeto, usuario, tipo='total', quantidade=None, ids_auditados=None, request=None):
    """Registra expedição (total ou parcial)"""
    detalhes = {'tipo_expedicao': tipo}
    if quantidade:
        detalhes['quantidade_expedida'] = quantidade
    if ids_auditados:
        detalhes['ids_auditados'] = ids_auditados
    
    acao = 'expedicao_parcial' if tipo == 'parcial' else 'expedicao'
    if not hasattr(objeto, 'comercial'):
        acao = 'manutencao_expedicao'
    
    return AuditLog.registrar(
        objeto=objeto,
        acao=acao,
        usuario=usuario,
        status_anterior=objeto.status if hasattr(objeto, 'status') else None,
        status_novo='Configurado',
        detalhes=detalhes,
        request=request
    )


def registrar_envio_cliente(objeto, usuario, request=None):
    """Registra envio ao cliente (recepção)"""
    return AuditLog.registrar(
        objeto=objeto,
        acao='envio_cliente',
        usuario=usuario,
        status_anterior=objeto.status if hasattr(objeto, 'status') else None,
        status_novo='Enviado para o Cliente',
        request=request
    )


def registrar_edicao(objeto, usuario, campos_alterados, request=None):
    """
    Registra edição com detalhes dos campos alterados
    
    Args:
        objeto: Instância editada
        usuario: Usuário que fez a edição
        campos_alterados: Lista de dicts com 'campo', 'anterior', 'novo'
        request: Request object
    """
    log = AuditLog.registrar(
        objeto=objeto,
        acao='edicao' if hasattr(objeto, 'comercial') else 'manutencao_edicao',
        usuario=usuario,
        detalhes={'total_campos_alterados': len(campos_alterados)},
        observacao=f"{len(campos_alterados)} campo(s) alterado(s)",
        request=request
    )
    
    # Registra cada campo alterado
    for campo in campos_alterados:
        CampoAlterado.objects.create(
            audit_log=log,
            nome_campo=campo['campo'],
            valor_anterior=str(campo.get('anterior', '')),
            valor_novo=str(campo.get('novo', ''))
        )
    
    return log


def registrar_exclusao(objeto, usuario, motivo=None, request=None):
    """Registra exclusão de requisição ou manutenção"""
    detalhes = {
        'id_excluido': objeto.id,
        'dados_basicos': {
            'status': objeto.status if hasattr(objeto, 'status') else None,
        }
    }
    
    # Adiciona dados específicos dependendo do tipo
    if hasattr(objeto, 'comercial'):  # Requisição
        detalhes['dados_basicos'].update({
            'cliente': str(objeto.nome) if hasattr(objeto, 'nome') else None,
            'comercial': str(objeto.comercial) if hasattr(objeto, 'comercial') else None,
        })
    
    return AuditLog.registrar(
        objeto=objeto,
        acao='exclusao' if hasattr(objeto, 'comercial') else 'manutencao_exclusao',
        usuario=usuario,
        detalhes=detalhes,
        observacao=motivo,
        request=request
    )


def registrar_ids_incluidos(objeto, usuario, ids_incluidos, request=None):
    """Registra inclusão de IDs de equipamentos"""
    return AuditLog.registrar(
        objeto=objeto,
        acao='ids_incluidos',
        usuario=usuario,
        detalhes={'ids': ids_incluidos},
        observacao=f"IDs incluídos: {ids_incluidos}",
        request=request
    )


def obter_logs(objeto):
    """Retorna todos os logs de auditoria de um objeto"""
    from django.contrib.contenttypes.models import ContentType
    content_type = ContentType.objects.get_for_model(objeto)
    return AuditLog.objects.filter(
        content_type=content_type,
        object_id=objeto.id
    ).select_related('usuario').prefetch_related('campos_alterados')


def obter_ultimo_log(objeto, acao=None):
    """Retorna o último log de auditoria de um objeto, opcionalmente filtrado por ação"""
    logs = obter_logs(objeto)
    if acao:
        logs = logs.filter(acao=acao)
    return logs.first()
