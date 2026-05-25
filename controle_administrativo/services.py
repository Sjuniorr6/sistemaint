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


def criar_tarefa_avulsa(semana_iso, ano, titulo, dia, periodo, responsavel_id, descricao='', prazo=None):
    """
    Cria uma tarefa que existe apenas nesta semana.
    Não cria TarefaModelo — a execução fica sem vínculo de modelo.
    """
    try:
        responsavel = FuncionarioAdministrativo.objects.get(id=responsavel_id)
    except FuncionarioAdministrativo.DoesNotExist:
        raise ValueError('Responsável não encontrado.')

    execucao = ExecucaoTarefaAdministrativa.objects.create(
        tarefa_modelo      = None,
        is_avulsa          = True,
        titulo_avulso      = titulo,
        descricao_avulsa   = descricao,
        dia_avulso         = dia,
        periodo_avulso     = periodo,
        responsavel_avulso = responsavel,
        semana_iso         = semana_iso,
        ano                = ano,
        status             = StatusExecucao.PENDENTE,
        is_done            = False,
        prazo              = prazo,
    )
    return execucao


def criar_tarefa_recorrente(titulo, dia, periodo, responsavel_id, descricao='', semana_iso=None, ano=None, prazo=None):
    """
    Cria uma TarefaModeloAdministrativa recorrente
    e já gera a execução da semana atual.
    O prazo aplica-se apenas à execução desta semana — nas futuras,
    o usuário pode definir o prazo individualmente.
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

    if semana_iso and ano:
        ExecucaoTarefaAdministrativa.objects.get_or_create(
            tarefa_modelo = tarefa_modelo,
            semana_iso    = semana_iso,
            ano           = ano,
            defaults={
                'status':    StatusExecucao.PENDENTE,
                'is_done':   False,
                'is_avulsa': False,
                'prazo':     prazo,
            }
        )

    return tarefa_modelo


def converter_para_recorrente(execucao_id, user):
    """
    Converte uma tarefa avulsa em recorrente.

    O que faz:
      1. Lê os campos avulsos da execução (título, dia, período, responsável)
      2. Cria um TarefaModeloAdministrativa com esses dados
      3. Vincula a execução atual ao novo modelo (tarefa_modelo = novo_modelo)
      4. Zera os campos avulsos e marca is_avulsa = False

    A partir da próxima semana, gerar_execucoes_semana já cuida do resto.
    Semanas passadas não são afetadas — a execução atual vira a "semana 1" do modelo.
    """
    try:
        execucao = ExecucaoTarefaAdministrativa.objects.select_related(
            'responsavel_avulso'
        ).get(id=execucao_id)
    except ExecucaoTarefaAdministrativa.DoesNotExist:
        raise ValueError('Execução não encontrada.')

    if not execucao.is_avulsa:
        raise ValueError('Esta tarefa já é recorrente.')

    if not execucao.titulo_avulso:
        raise ValueError('A tarefa avulsa não tem título definido.')

    if not execucao.responsavel_avulso:
        raise ValueError('A tarefa avulsa não tem responsável definido.')

    # Cria o modelo recorrente com os dados da execução avulsa
    tarefa_modelo = TarefaModeloAdministrativa.objects.create(
        titulo        = execucao.titulo_avulso,
        descricao     = execucao.descricao_avulsa or '',
        dia_da_semana = execucao.dia_avulso,
        periodo       = execucao.periodo_avulso,
        responsavel   = execucao.responsavel_avulso,
        ativo         = True,
    )

    # Vincula e limpa os campos avulsos na execução atual
    execucao.tarefa_modelo      = tarefa_modelo
    execucao.is_avulsa          = False
    execucao.titulo_avulso      = ''
    execucao.descricao_avulsa   = ''
    execucao.dia_avulso         = ''
    execucao.periodo_avulso     = ''
    execucao.responsavel_avulso = None
    execucao.atualizado_por     = user
    execucao.save()

    return tarefa_modelo

def converter_para_avulsa(execucao_id, user):
    """
    Converte uma tarefa recorrente em avulsa.

    O que faz:
      1. Lê os dados do TarefaModeloAdministrativa vinculado
      2. Copia título, descrição, dia, período e responsável para os campos avulsos
      3. Desvincula a execução do modelo (tarefa_modelo = None)
      4. Marca is_avulsa = True
      5. Desativa o modelo recorrente (ativo = False) — para de gerar nas semanas futuras

    ATENÇÃO — efeitos colaterais:
      - Execuções de SEMANAS PASSADAS continuam vinculadas ao modelo desativado
        (semanas passadas são imutáveis por regra de negócio)
      - Execuções de SEMANAS FUTURAS já geradas continuam existindo até serem
        excluídas manualmente — só novas semanas é que param de gerar a tarefa
    """
    try:
        execucao = ExecucaoTarefaAdministrativa.objects.select_related(
            'tarefa_modelo', 'tarefa_modelo__responsavel'
        ).get(id=execucao_id)
    except ExecucaoTarefaAdministrativa.DoesNotExist:
        raise ValueError('Execução não encontrada.')

    if execucao.is_avulsa:
        raise ValueError('Esta tarefa já é avulsa.')

    if not execucao.tarefa_modelo:
        raise ValueError('Esta execução não tem modelo recorrente vinculado.')

    modelo = execucao.tarefa_modelo

    # Copia os dados do modelo para os campos avulsos da execução
    execucao.titulo_avulso      = modelo.titulo
    execucao.descricao_avulsa   = modelo.descricao or ''
    execucao.dia_avulso         = modelo.dia_da_semana
    execucao.periodo_avulso     = modelo.periodo
    execucao.responsavel_avulso = modelo.responsavel
    execucao.is_avulsa          = True
    execucao.tarefa_modelo      = None
    execucao.atualizado_por     = user
    execucao.save()

    # Desativa o modelo recorrente — para de gerar nas próximas semanas
    modelo.ativo = False
    modelo.save()

    return execucao


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
    try:
        execucao = ExecucaoTarefaAdministrativa.objects.get(id=execucao_id)
    except ExecucaoTarefaAdministrativa.DoesNotExist:
        raise ValueError('Execução não encontrada.')

    hoje         = timezone.now().date()
    semana_atual = hoje.isocalendar()[1]
    ano_atual    = hoje.year

    if execucao.ano < ano_atual or (execucao.ano == ano_atual and execucao.semana_iso < semana_atual):
        raise ValueError('Não é possível excluir tarefas de semanas passadas.')

    if execucao.is_avulsa:
        execucao.delete()
    else:
        execucao.status        = StatusExecucao.CANCELADA
        execucao.atualizado_por = user
        execucao.save()


def _copiar_itens_fixos_bloco(bloco_atual, semana_anterior, ano_anterior):
    """
    Copia itens com is_fixo=True do bloco equivalente da semana anterior
    para o bloco atual. Idempotente — não duplica se o conteúdo já existe.

    Função interna — chamada apenas por gerar_blocos_semana.
    """
    from .models import BlocoSemanal, ItemBlocoSemanal

    # Busca o bloco do mesmo tipo na semana anterior
    try:
        bloco_anterior = BlocoSemanal.objects.get(
            tipo       = bloco_atual.tipo,
            semana_iso = semana_anterior,
            ano        = ano_anterior,
        )
    except BlocoSemanal.DoesNotExist:
        # Semana anterior não tem bloco desse tipo — nada a copiar
        return

    itens_fixos = ItemBlocoSemanal.objects.filter(
        bloco   = bloco_anterior,
        is_fixo = True,
    )

    # Conteúdos que já existem no bloco atual (para idempotência)
    conteudos_existentes = set(
        ItemBlocoSemanal.objects.filter(bloco=bloco_atual).values_list('conteudo', flat=True)
    )

    ultimo = ItemBlocoSemanal.objects.filter(bloco=bloco_atual).order_by('-ordem').first()
    ordem  = (ultimo.ordem + 1) if ultimo else 0

    for item in itens_fixos:
        if item.conteudo in conteudos_existentes:
            continue  # Já existe — não duplica

        ItemBlocoSemanal.objects.create(
            bloco       = bloco_atual,
            conteudo    = item.conteudo,
            is_fixo     = True,
            is_done     = False,          # Reseta — nova semana, novo estado
            ordem       = ordem,
            responsavel = item.responsavel,
            prazo       = None,           # Prazo não propaga — é específico da semana
            criado_por  = item.criado_por,
        )
        conteudos_existentes.add(item.conteudo)
        ordem += 1


def _copiar_tarefas_divisao_fixas(semana_iso, ano):
    """
    Copia TarefaDivisao com is_fixo=True da semana anterior para a semana atual.
    Idempotente — não duplica se conteúdo + funcionário já existir na semana atual.

    Função interna — chamada apenas por gerar_blocos_semana.
    """
    from .models import TarefaDivisao
    import datetime

    # Calcula semana anterior
    data_ref      = datetime.date.fromisocalendar(ano, semana_iso, 1)
    data_anterior = data_ref - datetime.timedelta(weeks=1)
    semana_ant    = data_anterior.isocalendar()[1]
    ano_ant       = data_anterior.isocalendar()[0]

    tarefas_fixas = TarefaDivisao.objects.filter(
        semana_iso = semana_ant,
        ano        = ano_ant,
        is_fixo    = True,
    )

    for tarefa in tarefas_fixas:
        # Idempotência: não duplica se já existe o mesmo conteúdo
        # para o mesmo funcionário na semana atual
        ja_existe = TarefaDivisao.objects.filter(
            funcionario = tarefa.funcionario,
            semana_iso  = semana_iso,
            ano         = ano,
            conteudo    = tarefa.conteudo,
        ).exists()

        if ja_existe:
            continue

        ultimo = TarefaDivisao.objects.filter(
            funcionario = tarefa.funcionario,
            semana_iso  = semana_iso,
            ano         = ano,
        ).order_by('-ordem').first()
        ordem = (ultimo.ordem + 1) if ultimo else 0

        TarefaDivisao.objects.create(
            funcionario = tarefa.funcionario,
            semana_iso  = semana_iso,
            ano         = ano,
            conteudo    = tarefa.conteudo,
            tipo        = tarefa.tipo,
            is_fixo     = True,
            is_done     = False,   # Reseta — nova semana
            prazo       = None,    # Prazo não propaga
            ordem       = ordem,
        )


def gerar_blocos_semana(semana_iso, ano, user):
    """
    Garante que os 3 blocos da semana existem.
    Idempotente — se já existem, não cria novamente.
    Também copia itens fixos da semana anterior para blocos e divisão de tarefas.
    """
    from .models import BlocoSemanal, TipoBloco
    import datetime

    # Calcula semana anterior para buscar itens fixos
    data_ref      = datetime.date.fromisocalendar(ano, semana_iso, 1)
    data_anterior = data_ref - datetime.timedelta(weeks=1)
    semana_ant    = data_anterior.isocalendar()[1]
    ano_ant       = data_anterior.isocalendar()[0]

    for tipo in [TipoBloco.NAO_ESQUECER, TipoBloco.QUINZENAL, TipoBloco.MENSAL]:
        bloco, criado = BlocoSemanal.objects.get_or_create(
            tipo       = tipo,
            semana_iso = semana_iso,
            ano        = ano,
            defaults   = {'criado_por': user}
        )
        # Copia itens fixos apenas quando o bloco acabou de ser criado
        # (se já existia, os itens já foram copiados na primeira chamada)
        if criado:
            _copiar_itens_fixos_bloco(bloco, semana_ant, ano_ant)

    # Copia tarefas da divisão com is_fixo=True da semana anterior
    _copiar_tarefas_divisao_fixas(semana_iso, ano)


def adicionar_item_bloco(bloco_id, conteudo, is_fixo=False, user=None, responsavel_id=None, prazo=None):
    """Adiciona um item a um bloco semanal."""
    from .models import BlocoSemanal, ItemBlocoSemanal, FuncionarioAdministrativo

    try:
        bloco = BlocoSemanal.objects.get(id=bloco_id)
    except BlocoSemanal.DoesNotExist:
        raise ValueError('Bloco não encontrado.')

    if not conteudo.strip():
        raise ValueError('O conteúdo não pode ser vazio.')

    # Resolve responsável (opcional)
    responsavel = None
    if responsavel_id:
        try:
            responsavel = FuncionarioAdministrativo.objects.get(id=responsavel_id)
        except FuncionarioAdministrativo.DoesNotExist:
            raise ValueError('Responsável não encontrado.')

    ultimo = bloco.itens.order_by('-ordem').first()
    ordem  = (ultimo.ordem + 1) if ultimo else 0

    item = ItemBlocoSemanal.objects.create(
        bloco       = bloco,
        conteudo    = conteudo.strip(),
        is_fixo     = is_fixo,
        is_done     = False,
        ordem       = ordem,
        criado_por  = user,
        responsavel = responsavel,
        prazo       = prazo,
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
        item     = item,
        autor    = user,
        conteudo = conteudo.strip(),
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


def adicionar_tarefa_divisao(funcionario_id, semana_iso, ano, conteudo, tipo='semana', is_fixo=False, prazo=None):
    """Adiciona uma tarefa na divisão semanal do funcionário."""
    from .models import TarefaDivisao

    if not conteudo.strip():
        raise ValueError('O conteúdo não pode ser vazio.')

    ultimo = TarefaDivisao.objects.filter(
        funcionario_id = funcionario_id,
        semana_iso     = semana_iso,
        ano            = ano,
    ).order_by('-ordem').first()
    ordem = (ultimo.ordem + 1) if ultimo else 0

    return TarefaDivisao.objects.create(
        funcionario_id = funcionario_id,
        semana_iso     = semana_iso,
        ano            = ano,
        conteudo       = conteudo.strip(),
        tipo           = tipo,
        is_fixo        = is_fixo,
        prazo          = prazo,
        ordem          = ordem,
    )


def editar_tarefa_divisao(tarefa_id, conteudo):
    """Edita o conteúdo de uma tarefa da divisão."""
    from .models import TarefaDivisao

    try:
        tarefa = TarefaDivisao.objects.get(id=tarefa_id)
    except TarefaDivisao.DoesNotExist:
        raise ValueError('Tarefa não encontrada.')

    if not conteudo.strip():
        raise ValueError('O conteúdo não pode ser vazio.')

    tarefa.conteudo = conteudo.strip()
    tarefa.save()
    return tarefa


def excluir_tarefa_divisao(tarefa_id):
    """Exclui uma tarefa da divisão."""
    from .models import TarefaDivisao

    try:
        tarefa = TarefaDivisao.objects.get(id=tarefa_id)
    except TarefaDivisao.DoesNotExist:
        raise ValueError('Tarefa não encontrada.')

    tarefa.delete()


def get_tarefas_divisao(semana_iso, ano):
    """Retorna todas as tarefas da divisão da semana agrupadas por funcionário."""
    from .models import TarefaDivisao

    tarefas = TarefaDivisao.objects.filter(
        semana_iso = semana_iso,
        ano        = ano,
    ).select_related('funcionario').order_by('funcionario', 'ordem')

    resultado = {}
    for tarefa in tarefas:
        fid = tarefa.funcionario.id
        if fid not in resultado:
            resultado[fid] = []
        resultado[fid].append(tarefa)

    return resultado


def marcar_atrasadas(semana_iso_atual, ano_atual):
    """
    Marca como 'atrasada' todas as execuções de semanas anteriores
    que ainda estão pendente ou em_andamento.
    Idempotente — pode ser chamada várias vezes sem efeito duplicado.
    """
    ExecucaoTarefaAdministrativa.objects.filter(
        status__in=[StatusExecucao.PENDENTE, StatusExecucao.EM_ANDAMENTO],
    ).exclude(
        semana_iso = semana_iso_atual,
        ano        = ano_atual,
    ).update(status=StatusExecucao.ATRASADA)


def detalhe_tarefa_divisao(tarefa_id):
    """Retorna dados completos de uma tarefa da divisão."""
    from .models import TarefaDivisao

    try:
        return TarefaDivisao.objects.prefetch_related(
            'comentarios', 'comentarios__autor'
        ).get(id=tarefa_id)
    except TarefaDivisao.DoesNotExist:
        raise ValueError('Tarefa não encontrada.')


def atualizar_tarefa_divisao(tarefa_id, conteudo=None, tipo=None, prazo=None, is_fixo=None):
    """Atualiza dados de uma tarefa da divisão."""
    from .models import TarefaDivisao

    try:
        tarefa = TarefaDivisao.objects.get(id=tarefa_id)
    except TarefaDivisao.DoesNotExist:
        raise ValueError('Tarefa não encontrada.')

    if conteudo is not None:
        tarefa.conteudo = conteudo.strip()
    if tipo is not None:
        tarefa.tipo = tipo
    if prazo is not None:
        tarefa.prazo = prazo if prazo else None
    if is_fixo is not None:
        tarefa.is_fixo = is_fixo
    tarefa.save()
    return tarefa


def adicionar_comentario_tarefa_divisao(tarefa_id, conteudo, user):
    """Adiciona comentário a uma tarefa da divisão."""
    from .models import TarefaDivisao, ComentarioTarefaDivisao

    try:
        tarefa = TarefaDivisao.objects.get(id=tarefa_id)
    except TarefaDivisao.DoesNotExist:
        raise ValueError('Tarefa não encontrada.')

    if not conteudo.strip():
        raise ValueError('Comentário não pode ser vazio.')

    return ComentarioTarefaDivisao.objects.create(
        tarefa   = tarefa,
        autor    = user,
        conteudo = conteudo.strip(),
    )