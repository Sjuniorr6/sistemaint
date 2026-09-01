"""Autorização do Iscas Fast.

Um único grupo governa o app: `Operadores Iscas` (ISC-RN-19). Não há verificação
de posse nem de tenant — o app é interno e todo operador enxerga todos os dados.

Os decorators barram na fronteira da URL: anônimo cai no login, autenticado sem
papel leva 403. Mesmo padrão do app Chamados.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from iscas.enums import GRUPO_OPERADORES


def is_operador(user) -> bool:
    """True se o usuário opera o Iscas Fast (ou é superuser)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=GRUPO_OPERADORES).exists()


def exige_operador(view):
    """Restringe a view ao grupo de operadores."""

    @wraps(view)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not is_operador(request.user):
            raise PermissionDenied(
                "Acesso restrito aos operadores do Iscas Fast."
            )
        return view(request, *args, **kwargs)

    return _wrapped
