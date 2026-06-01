from django.db import models
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
      6. Marca como oculta=True todas as execuções FUTURAS vinculadas ao modelo
         (semanas futuras já geradas somem do painel mas ficam no banco — soft delete)

    Comportamento esperado:
      - Semanas PASSADAS: continuam vinculadas ao modelo desativado, visíveis no histórico
      - Semana ATUAL: vira avulsa
      - Semanas FUTURAS já geradas: ocultadas (soft delete via oculta=True)
      - Novas semanas (que ainda não foram visitadas): não vão gerar a tarefa
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

    # Desativa o modelo recorrente + oculta execuções futuras
    # (regra centralizada em _desativar_modelo_e_ocultar_futuras)
    _desativar_modelo_e_ocultar_futuras(modelo)

    return execucao


def _desativar_modelo_e_ocultar_futuras(modelo):
    """
    Função privada — centraliza a regra "esta tarefa recorrente nao deve mais existir
    daqui pra frente". Usada quando o usuario exclui ou converte uma recorrente.

    O que faz:
      1. Desativa o modelo recorrente (ativo=False) → para de gerar execuções nas
         próximas semanas que ainda nao foram visitadas
      2. Oculta (oculta=True) todas as execuções FUTURAS já geradas vinculadas ao
         modelo, para que sumam do painel das próximas semanas

    Semanas PASSADAS: nunca tocadas (BR5 — historico imutavel).
    Semana ATUAL: nao tocada por esta funcao — quem chama decide o que fazer com ela.
    """
    hoje         = timezone.now().date()
    semana_atual = hoje.isocalendar()[1]
    ano_atual    = hoje.year

    modelo.ativo = False
    modelo.save()

    ExecucaoTarefaAdministrativa.objects.filter(
        tarefa_modelo=modelo,
    ).filter(
        models.Q(ano__gt=ano_atual) |
        models.Q(ano=ano_atual, semana_iso__gt=semana_atual)
    ).update(oculta=True)


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

        # Recorrente: tambem desativa o modelo + oculta execucoes futuras
        # (mesma regra usada em converter_para_avulsa)
        if execucao.tarefa_modelo:
            _desativar_modelo_e_ocultar_futuras(execucao.tarefa_modelo)


def _copiar_itens_fixos_bloco(bloco_atual, semana_anterior, ano_anterior):
    """
    Copia itens com is_fixo=True do bloco equivalente da semana anterior
    para o bloco atual. Idempotente — não duplica se o conteúdo já existe.

    Respeita soft-delete (espelha _copiar_tarefas_divisao_fixas):
    - Não copia itens de origem que estão ocultos (oculta=True).
    - Não re-copia um item fixo que foi excluído (oculta=True) em qualquer
      semana posterior à de origem.

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
        oculta  = False,   # não copia itens que foram soft-deleted na origem
    )

    # Conteúdos que já existem no bloco atual (para idempotência).
    # Inclui itens ocultos de propósito: se o usuário excluiu um item nesta
    # mesma semana, ele continua no banco com oculta=True e não deve voltar.
    conteudos_existentes = set(
        ItemBlocoSemanal.objects.filter(bloco=bloco_atual).values_list('conteudo', flat=True)
    )

    ultimo = ItemBlocoSemanal.objects.filter(bloco=bloco_atual).order_by('-ordem').first()
    ordem  = (ultimo.ordem + 1) if ultimo else 0

    for item in itens_fixos:
        if item.conteudo in conteudos_existentes:
            continue  # Já existe (visível ou oculto) — não duplica

        # Se este item fixo foi excluído (oculta=True) em QUALQUER semana
        # posterior à de origem, o usuário não quer mais ele — não re-copia.
        foi_excluida = ItemBlocoSemanal.objects.filter(
            bloco__tipo = bloco_atual.tipo,
            conteudo    = item.conteudo,
            is_fixo     = True,
            oculta      = True,
        ).filter(
            models.Q(bloco__ano__gt=ano_anterior) |
            models.Q(bloco__ano=ano_anterior, bloco__semana_iso__gt=semana_anterior)
        ).exists()

        if foi_excluida:
            continue

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
        oculta     = False,   # não copia tarefas que foram soft-deleted
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

        # Verifica se a tarefa fixa equivalente foi excluída em QUALQUER
        # semana >= à anterior que estamos copiando. Isso captura o caso:
        # usuário excluiu na sem 22, vamos copiar da 21 para 22 de novo.
        foi_excluida = TarefaDivisao.objects.filter(
            funcionario = tarefa.funcionario,
            conteudo    = tarefa.conteudo,
            is_fixo     = True,
            oculta      = True,
        ).filter(
            models.Q(ano__gt=tarefa.ano) |
            models.Q(ano=tarefa.ano, semana_iso__gt=tarefa.semana_iso)
        ).exists()

        if foi_excluida:
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
        # Copia os itens fixos SEMPRE — não só quando o bloco nasce.
        # A função é idempotente e respeita soft-delete (oculta), então rodar
        # em toda visita propaga itens recém-fixados para semanas já existentes,
        # sem duplicar e sem ressuscitar itens excluídos de propósito.
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
    """
    Exclui (soft delete) um item de um bloco semanal.

    O que faz:
      1. Marca oculta=True no item da semana onde foi excluído.
      2. Se o item é FIXO, marca oculta=True também em todas as cópias
         FUTURAS (mesmo conteúdo + mesmo tipo de bloco + is_fixo=True) já
         geradas, para que sumam das próximas semanas.

    Semanas passadas: imutáveis — nunca são tocadas (BR5).
    Espelha o comportamento de excluir_tarefa_divisao.
    """
    from .models import ItemBlocoSemanal

    try:
        item = ItemBlocoSemanal.objects.get(id=item_id)
    except ItemBlocoSemanal.DoesNotExist:
        raise ValueError('Item não encontrado.')

    # Marca o item da semana atual como oculto (soft delete)
    item.oculta = True
    item.save()

    # Se é fixo, propaga oculta=True para as semanas FUTURAS já geradas
    if item.is_fixo:
        ItemBlocoSemanal.objects.filter(
            bloco__tipo = item.bloco.tipo,
            conteudo    = item.conteudo,
            is_fixo     = True,
            oculta      = False,
        ).filter(
            models.Q(bloco__ano__gt=item.bloco.ano) |
            models.Q(bloco__ano=item.bloco.ano, bloco__semana_iso__gt=item.bloco.semana_iso)
        ).update(oculta=True)


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
    """
    Exclui (soft delete) uma tarefa da divisão.

    O que faz:
      1. Marca oculta=True na tarefa
      2. Se a tarefa é FIXA, marca oculta=True também em todas as versões
         FUTURAS (mesmo conteúdo + funcionário + is_fixo=True) já geradas
         para evitar que apareçam nas próximas semanas

    Semanas passadas: imutáveis (não são tocadas)
    """
    from .models import TarefaDivisao

    try:
        tarefa = TarefaDivisao.objects.get(id=tarefa_id)
    except TarefaDivisao.DoesNotExist:
        raise ValueError('Tarefa não encontrada.')

    # Marca a tarefa atual como oculta (soft delete)
    tarefa.oculta = True
    tarefa.save()

    # Se é fixa, propaga oculta=True para semanas FUTURAS
    if tarefa.is_fixo:
        TarefaDivisao.objects.filter(
            funcionario = tarefa.funcionario,
            conteudo    = tarefa.conteudo,
            is_fixo     = True,
            oculta      = False,
        ).filter(
            models.Q(ano__gt=tarefa.ano) |
            models.Q(ano=tarefa.ano, semana_iso__gt=tarefa.semana_iso)
        ).update(oculta=True)


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
    Marca como 'atrasada' as execuções pendente/em_andamento que já passaram:
      - Toda execução de SEMANAS PASSADAS (ano menor OU mesmo ano com semana menor)
      - Execuções da SEMANA ATUAL cujo dia já passou (ex: hoje é terça → segunda atrasada)
      - Execuções da SEMANA ATUAL no DIA DE HOJE cujo horário-limite já passou
        (com margem de tolerância de 30 minutos):
          - Se prazo individual definido → usa prazo + 30min
          - Se não tem prazo → manhã: 12:30, tarde: 18:30

    Execuções de SEMANAS FUTURAS nunca são marcadas como atrasadas.
    Idempotente — pode ser chamada várias vezes sem efeito duplicado.
    """
    import datetime

    agora = timezone.now()
    MARGEM = datetime.timedelta(minutes=30)

    # ── 1. Execuções de SEMANAS PASSADAS (ano menor OU mesmo ano com semana menor)
    ExecucaoTarefaAdministrativa.objects.filter(
        status__in=[StatusExecucao.PENDENTE, StatusExecucao.EM_ANDAMENTO],
    ).filter(
        models.Q(ano__lt=ano_atual) |
        models.Q(ano=ano_atual, semana_iso__lt=semana_iso_atual)
    ).update(status=StatusExecucao.ATRASADA)

    # ── 2. Execuções da SEMANA ATUAL — dias anteriores a hoje
    DIAS_ORDEM = {
        'segunda': 0, 'terca': 1, 'quarta': 2, 'quinta': 3, 'sexta': 4,
    }
    hoje_idx = agora.date().weekday()  # 0=segunda, 1=terça, ...

    # Dias da semana que JÁ PASSARAM (idx < hoje_idx)
    dias_passados = [dia for dia, idx in DIAS_ORDEM.items() if idx < hoje_idx]

    if dias_passados:
        ExecucaoTarefaAdministrativa.objects.filter(
            status__in=[StatusExecucao.PENDENTE, StatusExecucao.EM_ANDAMENTO],
            semana_iso=semana_iso_atual,
            ano=ano_atual,
        ).filter(
            models.Q(tarefa_modelo__dia_da_semana__in=dias_passados) |
            models.Q(dia_avulso__in=dias_passados)
        ).update(status=StatusExecucao.ATRASADA)

    # ── 3. Execuções de HOJE — verifica horário-limite individual
    dia_hoje_key = None
    for dia, idx in DIAS_ORDEM.items():
        if idx == hoje_idx:
            dia_hoje_key = dia
            break

    if dia_hoje_key:  # só vale dias úteis (segunda a sexta)
        execucoes_hoje = ExecucaoTarefaAdministrativa.objects.filter(
            status__in=[StatusExecucao.PENDENTE, StatusExecucao.EM_ANDAMENTO],
            semana_iso=semana_iso_atual,
            ano=ano_atual,
        ).filter(
            models.Q(tarefa_modelo__dia_da_semana=dia_hoje_key) |
            models.Q(dia_avulso=dia_hoje_key)
        ).select_related('tarefa_modelo')

        ids_atrasadas = []
        for execucao in execucoes_hoje:
            # Determina o prazo efetivo da execução
            if execucao.prazo:
                # Tem prazo individual definido — usa prazo + margem
                prazo_efetivo = execucao.prazo + MARGEM
            else:
                # Sem prazo individual — usa horário padrão do período
                periodo = execucao.periodo_key  # 'manha' ou 'tarde'
                if periodo == 'manha':
                    hora_limite = datetime.time(12, 30)  # 12:30
                elif periodo == 'tarde':
                    hora_limite = datetime.time(18, 30)  # 18:30
                else:
                    continue  # período desconhecido — pula

                # Combina data de hoje com hora-limite (timezone-aware)
                prazo_efetivo = timezone.make_aware(
                    datetime.datetime.combine(agora.date(), hora_limite)
                )

            if agora > prazo_efetivo:
                ids_atrasadas.append(execucao.id)

        if ids_atrasadas:
            ExecucaoTarefaAdministrativa.objects.filter(
                id__in=ids_atrasadas
            ).update(status=StatusExecucao.ATRASADA)

    # ── 4. DESMARCAR atrasadas que não deveriam estar atrasadas
    # Espelha a lógica dos blocos anteriores, mas no sentido inverso.
    # IMPORTANTE: nunca desmarca atrasadas de semanas passadas (imutáveis por BR5).

    # 4a. Semanas FUTURAS — toda execução atrasada vira pendente
    ExecucaoTarefaAdministrativa.objects.filter(
        status=StatusExecucao.ATRASADA,
    ).filter(
        models.Q(ano__gt=ano_atual) |
        models.Q(ano=ano_atual, semana_iso__gt=semana_iso_atual)
    ).update(status=StatusExecucao.PENDENTE)

    # 4b. Semana ATUAL — dias FUTUROS (depois de hoje) — vira pendente
    dias_futuros = [dia for dia, idx in DIAS_ORDEM.items() if idx > hoje_idx]

    if dias_futuros:
        ExecucaoTarefaAdministrativa.objects.filter(
            status=StatusExecucao.ATRASADA,
            semana_iso=semana_iso_atual,
            ano=ano_atual,
        ).filter(
            models.Q(tarefa_modelo__dia_da_semana__in=dias_futuros) |
            models.Q(dia_avulso__in=dias_futuros)
        ).update(status=StatusExecucao.PENDENTE)

    # 4c. Semana ATUAL — DIA DE HOJE com horário-limite ainda NÃO passou
    if dia_hoje_key:
        execucoes_hoje_atrasadas = ExecucaoTarefaAdministrativa.objects.filter(
            status=StatusExecucao.ATRASADA,
            semana_iso=semana_iso_atual,
            ano=ano_atual,
        ).filter(
            models.Q(tarefa_modelo__dia_da_semana=dia_hoje_key) |
            models.Q(dia_avulso=dia_hoje_key)
        ).select_related('tarefa_modelo')

        ids_desmarcar = []
        for execucao in execucoes_hoje_atrasadas:
            # Recalcula o prazo efetivo
            if execucao.prazo:
                prazo_efetivo = execucao.prazo + MARGEM
            else:
                periodo = execucao.periodo_key
                if periodo == 'manha':
                    hora_limite = datetime.time(12, 30)
                elif periodo == 'tarde':
                    hora_limite = datetime.time(18, 30)
                else:
                    continue

                prazo_efetivo = timezone.make_aware(
                    datetime.datetime.combine(agora.date(), hora_limite)
                )

            # Se ainda NÃO passou do prazo, volta pra pendente
            if agora <= prazo_efetivo:
                ids_desmarcar.append(execucao.id)

        if ids_desmarcar:
            ExecucaoTarefaAdministrativa.objects.filter(
                id__in=ids_desmarcar
            ).update(status=StatusExecucao.PENDENTE)


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