from django.conf import settings


def usuario_autorizado(user):
    """
    True se o usuário tem acesso TOTAL ao sistema.

    Controlado por settings.USUARIOS_AUTORIZADOS (lista de usernames).
    Lista vazia/ausente = não restringe (qualquer autenticado é autorizado).
    Os demais usuários ficam em modo somente leitura do Kanban TI.
    """
    autorizados = getattr(settings, "USUARIOS_AUTORIZADOS", None)
    if not autorizados:
        return True
    return getattr(user, "username", None) in autorizados
