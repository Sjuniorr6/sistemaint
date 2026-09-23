"""Autorização do Iscas Fast (ISC-RN-19).

Três grupos governam o app, e a autorização é por **capacidade**, não por papel:
a view declara o que ela faz (`@exige(Capacidade.VER_ESTOQUE)`) e o mapa
papel → capacidades vive num dicionário único aqui. O requisito não é
hierárquico — o Operador Fast dá baixa e manutenção mas não dá entrada — então
decorator por papel exigiria uma combinação nova por view; são ~45 delas.

O decorator grava `capacidade_iscas` na função, que é o que o middleware de
auditoria (`iscas/middleware.py`) lê para derivar a ação sem conhecer as views.

Os decorators barram na fronteira da URL: anônimo cai no login, autenticado sem
capacidade leva 403. Mesmo padrão do app Chamados.

**Risco aceito:** a checagem é na fronteira da URL, não nos services — eles são
chamados por management commands e migrations que não têm `request.user`. Quem
tem shell ou /admin contorna, o que já vale hoje. Não há verificação de posse
nem de tenant: todo usuário enxerga os dados que sua capacidade alcança.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from iscas.enums import (
    GRUPO_COMERCIAL_FAST,
    GRUPO_OPERADORES,
    GRUPO_OPERADORES_FAST,
    Capacidade,
)

#: Papel → o que ele pode fazer. Fonte única da autorização do app.
#:
#: `Operadores Iscas` recebe o conjunto COMPLETO por construção
#: (`frozenset(Capacidade)`), e não por lista literal: assim uma capacidade nova
#: nunca fica de fora do grupo total por esquecimento — o modo de falha seria
#: trancar o administrador para fora da própria feature.
CAPACIDADES_POR_GRUPO = {
    GRUPO_OPERADORES: frozenset(Capacidade),
    GRUPO_OPERADORES_FAST: frozenset({
        Capacidade.VER_PAINEL,
        Capacidade.VER_MAPA,
        Capacidade.VER_SOLICITACAO,
        Capacidade.CRIAR_SOLICITACAO,
        Capacidade.ATENDER_SOLICITACAO,
        Capacidade.VER_ESTOQUE,
        Capacidade.BAIXAR_MANUTENCAO,
        Capacidade.CADASTRAR_CLIENTE,
        Capacidade.CADASTRAR_MODELO,
        Capacidade.CONSULTAR_APOIO,
        # Vê quanto o agente cobrou, mas NÃO o que o cliente paga nem a
        # margem: ele digita o valor do cliente ao abrir e não o consulta
        # depois (decisão do negócio, confirmada).
        Capacidade.VER_CUSTO_AGENTE,
    }),
    GRUPO_COMERCIAL_FAST: frozenset({
        Capacidade.VER_PAINEL,
        Capacidade.VER_MAPA,
        Capacidade.VER_SOLICITACAO,
        Capacidade.CRIAR_SOLICITACAO,
        Capacidade.CADASTRAR_CLIENTE,
        Capacidade.CONSULTAR_APOIO,
        # O comercial vê o quadro financeiro completo — é quem negocia.
        Capacidade.VER_VALOR_CLIENTE,
        Capacidade.VER_CUSTO_AGENTE,
    }),
}


def _pertence_a(user, nome_do_grupo) -> bool:
    """Pertencimento por igualdade EXATA do nome do grupo.

    "Operadores Iscas" é prefixo de "Operadores Iscas Fast": um lookup por
    `startswith`/`icontains` promoveria o operador restrito a acesso total sem
    erro nenhum aparecer.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=nome_do_grupo).exists()


def is_operador(user) -> bool:
    """True se o usuário está no grupo total (ou é superuser)."""
    return _pertence_a(user, GRUPO_OPERADORES)


def is_operador_fast(user) -> bool:
    """True se o usuário opera o Iscas Fast com escopo restrito."""
    return _pertence_a(user, GRUPO_OPERADORES_FAST)


def is_comercial_fast(user) -> bool:
    """True se o usuário é do comercial (abre solicitação e cadastra cliente)."""
    return _pertence_a(user, GRUPO_COMERCIAL_FAST)


def capacidades_do(user) -> set:
    """Tudo o que o usuário pode fazer — a UNIÃO dos grupos dele.

    União, e não interseção: quem acumula papéis soma poderes, que é a leitura
    natural de "está nos dois grupos". Uma query só, independentemente de
    quantos grupos o usuário tenha.
    """
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(Capacidade)

    capacidades = set()
    for nome in user.groups.values_list("name", flat=True):
        capacidades |= CAPACIDADES_POR_GRUPO.get(nome, frozenset())
    return capacidades


def pode(user, capacidade) -> bool:
    """O usuário tem esta capacidade?"""
    return capacidade in capacidades_do(user)


def exige(capacidade):
    """Restringe a view a quem tem a capacidade.

    Além de barrar, grava `capacidade_iscas` na função decorada — é daí que o
    middleware de auditoria lê a categoria da ação, sem precisar de um mapa
    paralelo de view → ação que alguém teria de manter à mão.
    """

    def _decorador(view):
        @wraps(view)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if not pode(request.user, capacidade):
                raise PermissionDenied(
                    f"Acesso restrito: exige a permissão "
                    f"'{Capacidade(capacidade).label}' no Iscas Fast."
                )
            return view(request, *args, **kwargs)

        _wrapped.capacidade_iscas = capacidade
        return _wrapped

    return _decorador


def exige_operador(view):
    """Restringe ao grupo total.

    `VER_AUDITORIA` existe apenas no conjunto de `Operadores Iscas`, então
    exigi-la é equivalente a exigir o grupo total — mas mantém uma única forma
    de autorização no app, em vez de um decorator que checa grupo e outro que
    checa capacidade.
    """
    return exige(Capacidade.VER_AUDITORIA)(view)
