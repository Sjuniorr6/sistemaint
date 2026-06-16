from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


class NoIndexMiddleware:
    """Force noindex headers for this internal system."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet, noimageindex"
        return response


class LoginObrigatorioMiddleware:
    """
    Redireciona para o login qualquer requisição de usuário não autenticado,
    exceto as rotas explicitamente públicas (login, registro, estáticos) e as
    rotas que possuem autenticação própria (admin, API com token/webhook).

    Defesa em profundidade: complementa o @login_required das views, garantindo
    que nenhuma página interna seja servida sem sessão autenticada.

    IMPORTANTE: deve ser registrado DEPOIS do AuthenticationMiddleware para que
    request.user já exista.
    """

    # Rotas públicas por correspondência EXATA.
    # O login fica na raiz "/" — por isso é exato, e não prefixo (senão tudo
    # passaria a ser público via startswith).
    ROTAS_PUBLICAS_EXATAS = {
        "/",            # página de login (login.urls -> name='login')
        "/logout/",
        "/register/",
        "/robots.txt",
        "/favicon.ico",
    }

    # Rotas públicas por PREFIXO. Incluem áreas com autenticação própria
    # (admin via sessão de staff, /api/ via token DRF e webhooks) e arquivos
    # estáticos/mídia.
    ROTAS_PUBLICAS_PREFIXOS = (
        "/static/",
        "/media/",
        "/admin/",
        "/api/",
    )

    # Métodos HTTP que não alteram dados (modo somente leitura).
    METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}

    def __init__(self, get_response):
        self.get_response = get_response
        # Resolve a URL de login uma vez. Ela DEVE ser sempre pública, senão o
        # redirecionamento de não autenticados cairia em loop infinito.
        self.login_url = self._resolver_login_url()
        # Kanban TI: única área liberada (em leitura) para os demais usuários.
        self.kanban_ti_url = self._resolver_url("kanban_TI:home", "/TI/kanban/")

    def _resolver_login_url(self):
        try:
            return reverse(settings.LOGIN_URL)
        except (NoReverseMatch, AttributeError):
            return settings.LOGIN_URL

    def _resolver_url(self, nome, fallback):
        try:
            return reverse(nome)
        except NoReverseMatch:
            return fallback

    def __call__(self, request):
        if self._eh_publica(request.path_info):
            return self.get_response(request)

        if not request.user.is_authenticated:
            return redirect(f"{self.login_url}?next={request.path_info}")

        # Usuários autorizados: acesso total.
        if self._usuario_autorizado(request.user):
            return self.get_response(request)

        # Demais usuários: somente VISUALIZAÇÃO do Kanban TI.
        if request.path_info.startswith(self.kanban_ti_url):
            if request.method in self.METODOS_SEGUROS:
                return self.get_response(request)
            return HttpResponseForbidden(
                "Acesso somente leitura: você não tem permissão para alterar o Kanban TI."
            )

        # Qualquer outra página: redireciona para o kanban (GET) ou nega (demais métodos).
        if request.method in self.METODOS_SEGUROS:
            return redirect(self.kanban_ti_url)
        return HttpResponseForbidden(
            "Acesso restrito. Você só pode visualizar o Kanban TI."
        )

    def _eh_publica(self, caminho):
        if caminho == self.login_url or caminho in self.ROTAS_PUBLICAS_EXATAS:
            return True
        return any(caminho.startswith(prefixo) for prefixo in self.ROTAS_PUBLICAS_PREFIXOS)

    def _usuario_autorizado(self, user):
        from app.permissions import usuario_autorizado
        return usuario_autorizado(user)
