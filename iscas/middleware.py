"""Auditoria automática das ações do Iscas Fast (ISC-RN-19).

Registra toda requisição POST bem-sucedida do app. Automático de propósito: uma
view nova nasce auditada sem ninguém lembrar de chamar nada — a alternativa
(cada service registrando o próprio evento) tem como modo de falha a lacuna
silenciosa, que é exatamente o que auditoria não pode ter.

Não conhece nenhuma view. Deriva tudo do que o Django já resolveu: `url_name`
para a ação, `capacidade_iscas` (gravada pelo decorator `exige`) para a
categoria, e os kwargs da URL para o alvo.

**Escopo honesto:** este é um log de requisições bem-sucedidas em transporte,
não de transações de negócio confirmadas. Várias views do app redirecionam
tanto no sucesso quanto no erro (`estornar`, `cancelar`), então o status HTTP
não distingue os dois — e registrar de mais é aceitável numa auditoria,
registrar de menos não é. Para o livro de transações existem `Movimentacao` e
`SolicitacaoEvento`.
"""
import logging

logger = logging.getLogger(__name__)

#: Nunca faz sentido guardar, e é ruído em toda linha do log.
_CAMPOS_IGNORADOS = {"csrfmiddlewaretoken"}


class AuditoriaIscasMiddleware:
    """Grava um `RegistroAuditoria` por POST bem-sucedido do app iscas."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)

        if self._deve_registrar(request, resposta):
            self._registrar(request, resposta)

        return resposta

    def _deve_registrar(self, request, resposta) -> bool:
        """Guardas da mais barata para a mais cara.

        A de `app_name` é a que isola os outros ~40 apps do projeto: sem ela,
        este middleware gravaria uma linha para cada POST do sistema inteiro.
        """
        if request.method != "POST":
            return False

        match = getattr(request, "resolver_match", None)
        if not match or match.app_name != "iscas":
            return False

        usuario = getattr(request, "user", None)
        if not usuario or not usuario.is_authenticated:
            return False

        return 200 <= resposta.status_code < 400

    def _registrar(self, request, resposta):
        # Import tardio: middleware é carregado antes do app registry estar pronto.
        from iscas.models.operacao import RegistroAuditoria

        match = request.resolver_match
        try:
            RegistroAuditoria.objects.create(
                autor=request.user,
                acao=(match.url_name or "")[:100],
                capacidade=getattr(match.func, "capacidade_iscas", "") or "",
                caminho=request.path[:255],
                alvo=self._alvo(match.kwargs),
                campos=self._campos(request.POST),
                status_http=resposta.status_code,
            )
        except Exception:
            # O evento já aconteceu; o usuário já viu o resultado. Um erro ao
            # gravar o log (SQLite serializa escritas e devolve "database is
            # locked" sob concorrência) não pode transformar uma operação
            # bem-sucedida num 500. Consequência assumida: sob pressão, o log
            # pode ter buracos. Auditoria à prova de buracos exigiria outro
            # desenho, e não é o requisito de hoje.
            logger.exception(
                "[auditoria_iscas] falha ao registrar %s %s",
                request.method,
                request.path,
            )

    @staticmethod
    def _alvo(kwargs) -> dict:
        """Os kwargs da URL, coagidos para JSON."""
        return {
            str(chave): valor if isinstance(valor, (int, str)) else str(valor)
            for chave, valor in (kwargs or {}).items()
        }

    @staticmethod
    def _campos(post) -> list:
        """SÓ as chaves do POST, ordenadas. NUNCA os valores.

        Allowlist por construção: nada é gravado por default, então o campo
        sensível que alguém acrescentar ao formulário amanhã não vaza. O
        formulário de agente traz CPF em texto puro — saber que o CPF foi
        mexido é auditoria, saber qual é o CPF é vazamento (ISC-RN-16).
        """
        return sorted(chave for chave in post if chave not in _CAMPOS_IGNORADOS)
