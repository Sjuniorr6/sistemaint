"""Histórico de auditoria — quem fez o quê no app (ISC-RN-19).

Restrita a `VER_AUDITORIA`, capacidade que só o grupo total possui: é a tela que
mostra a atividade dos papéis restritos, e não faz sentido que eles se auditem.
"""
from django.core.paginator import Paginator
from django.shortcuts import render

from iscas.enums import Capacidade
from iscas.models.operacao import RegistroAuditoria
from iscas.permissions import exige


@exige(Capacidade.VER_AUDITORIA)
def lista(request):
    """Registros de auditoria, do mais recente, com filtros combináveis."""
    autor = request.GET.get("autor") or ""
    acao = request.GET.get("acao") or ""
    capacidade = request.GET.get("capacidade") or ""
    inicio = request.GET.get("inicio") or ""
    fim = request.GET.get("fim") or ""
    busca = (request.GET.get("q") or "").strip()

    # select_related obrigatório: sem ele a tabela faz uma query por linha só
    # para imprimir o nome do autor — 50 por página.
    registros = RegistroAuditoria.objects.select_related("autor")

    if autor:
        registros = registros.filter(autor_id=autor)
    if acao:
        registros = registros.filter(acao=acao)
    if capacidade:
        registros = registros.filter(capacidade=capacidade)
    if inicio:
        registros = registros.filter(created_at__date__gte=inicio)
    if fim:
        registros = registros.filter(created_at__date__lte=fim)
    if busca:
        registros = registros.filter(caminho__icontains=busca)

    paginas = Paginator(registros, 50)

    # Sem carregar os filtros adiante, ir para a página 2 devolve a lista
    # inteira — o mesmo bug que extrato e solicitações já comentam.
    querystring = request.GET.copy()
    querystring.pop("page", None)

    return render(
        request,
        "iscas/auditoria.html",
        {
            "pagina": paginas.get_page(request.GET.get("page")),
            "total": paginas.count,
            "querystring": querystring.urlencode(),
            # Os selects saem do que existe no log, não das tabelas inteiras:
            # filtrar por um usuário que nunca agiu não tem utilidade.
            "autores": _autores_com_registro(),
            "acoes": sorted(
                RegistroAuditoria.objects.values_list("acao", flat=True).distinct()
            ),
            "capacidades": Capacidade.choices,
            "autor_atual": autor,
            "acao_atual": acao,
            "capacidade_atual": capacidade,
            "inicio": inicio,
            "fim": fim,
            "busca": busca,
            "filtros_ativos": sum(
                1 for v in (autor, acao, capacidade, inicio, fim, busca) if v
            ),
        },
    )


def _autores_com_registro():
    """(id, nome) de quem aparece no log, para o select de autor."""
    from django.contrib.auth import get_user_model

    ids = RegistroAuditoria.objects.values_list("autor_id", flat=True).distinct()
    return get_user_model().objects.filter(pk__in=ids).order_by("username")
