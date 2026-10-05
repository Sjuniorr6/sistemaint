"""Helpers de papel (Django Groups) e de posse do chamado.

A separação Quality × Inteligência é lógica (ADR-008): dois grupos governam
quem abre, quem trata e o conteúdo dos dropdowns. Estes helpers centralizam as
checagens; a autorização REAL é imposta no service (a UI só reflete, RN-18).
Superuser passa em tudo — é o Superusuário GSInt do PRD.

Além dos predicados (is_quality/is_inteligencia/pode_agir), expõe decorators de
view (exige_quality/exige_operador) que barram na fronteira da URL: usuário
anônimo cai no login, autenticado sem papel leva 403 — nenhuma URL do app fica
acessível a quem não é operador.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from chamados.enums import (
    GRUPO_COMERCIAL,
    GRUPO_EXPEDICAO,
    GRUPO_CONFIGURACAO,
    GRUPO_FINANCEIRO,
    GRUPO_INTELIGENCIA,
    GRUPO_LABORATORIO,
    GRUPO_QUALITY,
    GRUPO_RECEPCAO,
    Status,
)


def is_quality(user) -> bool:
    """True se o usuário é do grupo `quality` (ou superuser)."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=GRUPO_QUALITY).exists()


def is_inteligencia(user) -> bool:
    """True se o usuário é do grupo `inteligencia` (ou superuser)."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=GRUPO_INTELIGENCIA).exists()


def is_expedicao(user) -> bool:
    """True se o usuário é do grupo `expedicao` (ou superuser).

    Expedição é uma fila COMPARTILHADA: qualquer membro do grupo age nos chamados
    em EXPEDICAO (diferente da Inteligência, cuja posse é individual).
    """
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=GRUPO_EXPEDICAO).exists()


def is_laboratorio(user) -> bool:
    """True se o usuário é do grupo `laboratorio` (ou superuser).

    Também fila COMPARTILHADA: recebe os chamados que chegaram à base (LABORATORIO).
    """
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=GRUPO_LABORATORIO).exists()


def is_comercial(user) -> bool:
    """True se o usuário é do grupo `COMERCIAL` (ou superuser).

    Fila COMPARTILHADA: recebe os chamados encaminhados pelo Laboratório (COMERCIAL).
    """
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=GRUPO_COMERCIAL).exists()


def is_financeiro(user) -> bool:
    """True se o usuário é do grupo `financeiro` (ou superuser).

    Fila COMPARTILHADA: recebe os chamados com equipamento COM CUSTO para cobrar
    do cliente (tem acesso ao laudo e ao termo anexado pelo Comercial).
    """
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=GRUPO_FINANCEIRO).exists()


def is_recepcao(user) -> bool:
    """True se o usuário é do grupo `recepcao` (ou superuser). Fila COMPARTILHADA:
    recebe os chamados com equipamento de substituição e abre a requisição."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=GRUPO_RECEPCAO).exists()


def is_configuracao(user) -> bool:
    """True se o usuário é do grupo `CONFIGURACAO` (ou superuser). Fila
    COMPARTILHADA: configura os equipamentos antes do envio ao cliente."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=GRUPO_CONFIGURACAO).exists()


def is_operador(user) -> bool:
    """True se o usuário é operador do app: quality, inteligencia, expedicao,
    laboratorio, comercial, recepcao, configuracao OU financeiro (ou superuser).

    É o gate de acesso às telas do app (fila, detalhe, ações). Quem não é operador
    não enxerga nada de chamados (RN-18: todos os operadores veem tudo; não-
    operadores, nada).
    """
    return (
        is_quality(user)
        or is_inteligencia(user)
        or is_expedicao(user)
        or is_laboratorio(user)
        or is_comercial(user)
        or is_recepcao(user)
        or is_configuracao(user)
        or is_financeiro(user)
    )


def exige_quality(view):
    """Decorator de view: exige grupo quality (ou superuser); senão 403.

    Empilha login_required por baixo: anônimo vai para o login; autenticado sem
    o papel leva PermissionDenied (403). Usado na abertura de chamado (RN-01).
    """

    @wraps(view)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not is_quality(request.user):
            raise PermissionDenied("Apenas o grupo 'quality' pode abrir chamados.")
        return view(request, *args, **kwargs)

    return _wrapped


def exige_operador(view):
    """Decorator de view: exige ser operador (quality ou inteligencia); senão 403.

    Gate padrão das telas do app. Anônimo → login; autenticado sem papel → 403.
    """

    @wraps(view)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not is_operador(request.user):
            raise PermissionDenied("Acesso restrito aos operadores de Chamados.")
        return view(request, *args, **kwargs)

    return _wrapped


def pode_agir(user, chamado) -> bool:
    """Posse: quem pode agir sobre o chamado no estado atual (RN-17, RN-18).

    A posse acompanha o estado: enquanto o chamado é do Quality (ABERTO, ou
    BLOQUEADO vindo dele), o Quality age; a partir de ENCAMINHADO (e BLOQUEADO
    vindo dele), a posse é da Inteligência. RESOLVIDO é terminal — ninguém age.
    O superuser sempre pode.

    Para BLOQUEADO, a posse deriva do estado ativo anterior ao bloqueio (o mesmo
    log que a reabertura consulta, ADR-005) — assim o dono atual reabre.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if chamado.status == Status.RESOLVIDO:
        return False

    estado_de_posse = chamado.status
    if chamado.status == Status.BLOQUEADO:
        from chamados.services import estado_ativo_anterior_ao_bloqueio

        estado_de_posse = estado_ativo_anterior_ao_bloqueio(chamado)

    if estado_de_posse == Status.ENCAMINHADO:
        # Posse individual: só o responsável de inteligência DAQUELE chamado age;
        # não basta pertencer ao grupo (senão qualquer intel mexeria no de outro).
        return is_inteligencia(user) and chamado.responsavel_inteligencia_id == user.id
    if estado_de_posse == Status.EXPEDICAO:
        # Posse COMPARTILHADA: qualquer membro do grupo expedicao age (fila comum).
        return is_expedicao(user)
    if estado_de_posse == Status.LABORATORIO:
        # Fila compartilhada do laboratório (encaminha p/ comercial).
        return is_laboratorio(user)
    if estado_de_posse == Status.COMERCIAL:
        # Fila compartilhada do comercial (finaliza a tratativa).
        return is_comercial(user)
    if estado_de_posse == Status.RECEPCAO:
        return is_recepcao(user)
    if estado_de_posse == Status.CONFIGURACAO:
        return is_configuracao(user)
    if estado_de_posse == Status.ENVIO:
        # A volta para a Expedição (envio ao cliente) é da mesma fila compartilhada.
        return is_expedicao(user)
    if estado_de_posse == Status.FINANCEIRO:
        # Fila compartilhada do financeiro (fatura e encerra).
        return is_financeiro(user)
    # ABERTO → posse do Quality.
    return is_quality(user)


# ---------------------------------------------------------------------------
# Horizonte: até onde do fluxo o usuário enxerga um chamado
# ---------------------------------------------------------------------------


def setores_operacionais(user):
    """Setores do fluxo pós-Inteligência a que o usuário pertence."""
    from chamados.enums import Setor

    papeis = (
        (Setor.EXPEDICAO, is_expedicao),
        (Setor.LABORATORIO, is_laboratorio),
        (Setor.COMERCIAL, is_comercial),
        (Setor.RECEPCAO, is_recepcao),
        (Setor.CONFIGURACAO, is_configuracao),
        (Setor.FINANCEIRO, is_financeiro),
    )
    return [setor for setor, pertence in papeis if pertence(user)]


def ve_fluxo_inteiro(user) -> bool:
    """Quality e Inteligência (e o superuser) veem tudo de todo chamado visível."""
    return is_quality(user) or is_inteligencia(user)


def corte_de_visibilidade(user, chamado):
    """Até quando `user` enxerga o que foi registrado no chamado, ou None (tudo).

    Quem está com o chamado agora (passagem aberta num setor seu) vê tudo; quem
    já passou por ele vê o registrado até a ÚLTIMA saída do seu setor. Por TEMPO,
    e não pela ordem dos setores, porque o fluxo não é linear: a Expedição recebe
    a chegada no começo e volta no fim para o envio.
    """
    if ve_fluxo_inteiro(user):
        return None
    setores = setores_operacionais(user)
    passagens = chamado.passagens.filter(setor__in=setores)
    if passagens.filter(finalizado_em__isnull=True).exists():
        return None
    ultima = passagens.exclude(finalizado_em__isnull=True).order_by("-finalizado_em").first()
    return ultima.finalizado_em if ultima else None
