from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """
    Verifica se o usuário pertence a um grupo específico.
    Uso: {% if user|has_group:"Nome do Grupo" %}
    """
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()

@register.filter(name='is_gestao_kanban')
def is_gestao_kanban(user):
    """
    Verifica se o usuário pertence ao grupo Gestão Kanban.
    Uso: {% if user|is_gestao_kanban %}
    """
    return has_group(user, 'Gestão Kanban')

@register.filter(name='is_config_kanban')
def is_config_kanban(user):
    """
    Verifica se o usuário pertence ao grupo Configuração Kanban.
    Uso: {% if user|is_config_kanban %}
    """
    return has_group(user, 'Configuração Kanban')

@register.filter(name='format_responsavel')
def format_responsavel(username):
    """
    Formata o username do responsável para exibição amigável.
    Exemplo: GuilhermeAmarante -> Guilherme A.
             Talita.Espinosa -> Talita E.
    """
    if not username:
        return ''
    
    # Mapeia usernames para nomes formatados
    formatacao = {
        'GuilhermeAmarante': 'Guilherme A.',
        'Talita.Espinosa': 'Talita E.',
        'Vinicius.Rodrigues': 'Vinicius R.',
        'Patricia.Costa': 'Patricia C.',
        'Anália': 'Anália V.',
        'Evellyn.Taila': 'Evellyn T.',
        'Tiago.Faria': 'Tiago F.',
        'Inteligencia': 'Inteligencia',
    }
    
    return formatacao.get(username, username)

@register.filter(name='eh_carregador_cabo')
def eh_carregador_cabo(requisicao):
    """
    Verifica se a requisição é do tipo CARREGADOR + CABO.
    Normaliza espaços extras para evitar problemas de comparação.
    Uso: {% if requisicao|eh_carregador_cabo %}
    """
    if not requisicao or not requisicao.tipo_produto:
        return False
    
    nome_produto = requisicao.tipo_produto.nome.strip().upper()
    return 'CARREGADOR' in nome_produto and 'CABO' in nome_produto
