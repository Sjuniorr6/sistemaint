from django.utils import timezone
from .models import (
    TarefaModeloAdministrativa,
    ExecucaoTarefaAdministrativa,
    ComentarioTarefa,
    LeituraComentario,
    FuncionarioAdministrativo,
    StatusExecucao,
)


def gerar_execucoes_semana(semana_iso, ano):
    """
    Gera ExecucaoTarefaAdministrativa para todas as
    TarefaModeloAdministrativa ativas na semana/ano informados.
    Idempotente — não duplica se já existir.
    """
    tarefas_ativas = TarefaModeloAdministrativa.objects.filter(ativo=True)

    for tarefa in tarefas_ativas:
        ExecucaoTarefaAdministrativa.objects.get_or_create(
            tarefa_modelo=tarefa,
            semana_iso=semana_iso,
            ano=ano,
            defaults={
                'status':    StatusExecucao.PENDENTE,
                'is_done':   False,
                'is_avulsa': False,
            }
        )


def criar_tarefa_avulsa(semana_iso, ano, titulo, dia, periodo, responsavel_id, descricao=''):
    """
    Cria uma tarefa que existe apenas nesta semana.
    Não cria TarefaModelo — a execução fica sem vínculo de modelo.
    """
    try:
        responsavel = FuncionarioAdministrativo.objects.get(id=responsavel_id)
    except FuncionarioAdministrativo.DoesNotExist:
        raise ValueError('Responsável não encontrado.')

    execucao = ExecucaoTarefaAdministrativa.objects.create(
        tarefa_modelo    = None,
        is_avulsa        = True,
        titulo_avulso    = titulo,
        descricao_avulsa = descricao,
        dia_avulso       = dia,
        periodo_avulso   = periodo,
        responsavel_avulso = responsavel,
        semana_iso       = semana_iso,
        ano              = ano,
        status           = StatusExecucao.PENDENTE,
        is_done          = False,
    )
    return execucao


def criar_tarefa_recorrente(titulo, dia, periodo, responsavel_id, descricao='', semana_iso=None, ano=None):
    """
    Cria uma TarefaModeloAdministrativa recorrente
    e já gera a execução da semana atual.
    """
    try:
        responsavel = FuncionarioAdministrativo.objects.get(id=responsavel_id)
    except FuncionarioAdministrativo.DoesNotExist:
        raise ValueError('Responsável não encontrado.')

    tarefa_modelo = TarefaModeloAdministrativa.objects.create(
        titulo        = titulo,
        descricao     = descricao,
        dia_da_semana = dia,
        periodo       = periodo,
        responsavel   = responsavel,
        ativo         = True,
    )

    # Gera a execução da semana atual se informada
    if semana_iso and ano:
        ExecucaoTarefaAdministrativa.objects.get_or_create(
            tarefa_modelo = tarefa_modelo,
            semana_iso    = semana_iso,
            ano           = ano,
            defaults={
                'status':    StatusExecucao.PENDENTE,
                'is_done':   False,
                'is_avulsa': False,
            }
        )

    return tarefa_modelo


def marcar_comentarios_lidos(execucao, user):
    """
    Marca todos os comentários de uma execução como lidos pelo user.
    Chamado quando o modal de detalhes é aberto.
    """
    comentarios = ComentarioTarefa.objects.filter(execucao=execucao)
    for comentario in comentarios:
        LeituraComentario.objects.get_or_create(
            comentario=comentario,
            usuario=user,
        )


def excluir_execucao(execucao_id, user):
    """
    Exclui uma execução de tarefa.
    - Tarefas avulsas: delete físico.
    - Tarefas recorrentes: apenas cancela (status=cancelada).
    Semanas passadas são imutáveis — não permite exclusão.
    """
    from django.utils import timezone

    try:
        execucao = ExecucaoTarefaAdministrativa.objects.get(id=execucao_id)
    except ExecucaoTarefaAdministrativa.DoesNotExist:
        raise ValueError('Execução não encontrada.')

    hoje = timezone.now().date()
    semana_atual = hoje.isocalendar()[1]
    ano_atual    = hoje.year

    # Bloqueia exclusão de semanas passadas
    if execucao.ano < ano_atual or (execucao.ano == ano_atual and execucao.semana_iso < semana_atual):
        raise ValueError('Não é possível excluir tarefas de semanas passadas.')

    if execucao.is_avulsa:
        execucao.delete()
    else:
        execucao.status = StatusExecucao.CANCELADA
        execucao.atualizado_por = user
        execucao.save()

def gerar_blocos_semana(semana_iso, ano, user):
    """
    Garante que os 3 blocos da semana existem.
    Idempotente — se já existem, não cria novamente.
    """
    from .models import BlocoSemanal, TipoBloco

    for tipo in [TipoBloco.NAO_ESQUECER, TipoBloco.DIARIO, TipoBloco.OBSERVACAO]:
        BlocoSemanal.objects.get_or_create(
            tipo=tipo,
            semana_iso=semana_iso,
            ano=ano,
            defaults={'criado_por': user}
        )


def adicionar_item_bloco(bloco_id, conteudo, is_fixo=False, user=None):
    """Adiciona um item a um bloco semanal."""
    from .models import BlocoSemanal, ItemBlocoSemanal

    try:
        bloco = BlocoSemanal.objects.get(id=bloco_id)
    except BlocoSemanal.DoesNotExist:
        raise ValueError('Bloco não encontrado.')

    if not conteudo.strip():
        raise ValueError('O conteúdo não pode ser vazio.')

    ultimo = bloco.itens.order_by('-ordem').first()
    ordem  = (ultimo.ordem + 1) if ultimo else 0

    item = ItemBlocoSemanal.objects.create(
        bloco    = bloco,
        conteudo = conteudo.strip(),
        is_fixo  = is_fixo,
        is_done  = False,
        ordem    = ordem,
        criado_por = user,
    )
    return item


def toggle_item_bloco(item_id):
    """Marca ou desmarca um item do bloco como concluído."""
    from .models import ItemBlocoSemanal

    try:
        item = ItemBlocoSemanal.objects.get(id=item_id)
    except ItemBlocoSemanal.DoesNotExist:
        raise ValueError('Item não encontrado.')

    item.is_done = not item.is_done
    item.save()
    return item


def excluir_item_bloco(item_id):
    """Exclui um item de um bloco semanal."""
    from .models import ItemBlocoSemanal

    try:
        item = ItemBlocoSemanal.objects.get(id=item_id)
    except ItemBlocoSemanal.DoesNotExist:
        raise ValueError('Item não encontrado.')

    item.delete()

def adicionar_comentario_item_bloco(item_id, conteudo, user):
    """Adiciona comentário a um item do bloco."""
    from .models import ItemBlocoSemanal, ComentarioItemBloco

    try:
        item = ItemBlocoSemanal.objects.get(id=item_id)
    except ItemBlocoSemanal.DoesNotExist:
        raise ValueError('Item não encontrado.')

    if not conteudo.strip():
        raise ValueError('Comentário não pode ser vazio.')

    comentario = ComentarioItemBloco.objects.create(
        item=item,
        autor=user,
        conteudo=conteudo.strip(),
    )
    return comentario


def atualizar_item_bloco(item_id, conteudo=None, responsavel_id=None, prazo=None, is_fixo=None):
    """Atualiza dados de um item do bloco."""
    from .models import ItemBlocoSemanal, FuncionarioAdministrativo

    try:
        item = ItemBlocoSemanal.objects.get(id=item_id)
    except ItemBlocoSemanal.DoesNotExist:
        raise ValueError('Item não encontrado.')

    if conteudo is not None:
        item.conteudo = conteudo.strip()

    if responsavel_id is not None:
        if responsavel_id == '':
            item.responsavel = None
        else:
            try:
                item.responsavel = FuncionarioAdministrativo.objects.get(id=responsavel_id)
            except FuncionarioAdministrativo.DoesNotExist:
                raise ValueError('Responsável não encontrado.')

    if prazo is not None:
        item.prazo = prazo if prazo else None

    if is_fixo is not None:
        item.is_fixo = is_fixo

    item.save()
    return item