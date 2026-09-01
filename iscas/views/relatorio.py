"""Extrato, históricos consolidados e exportação CSV (ISC-RF-34 a ISC-RF-37)."""
import csv
from codecs import BOM_UTF8

from django.core.paginator import Paginator
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from iscas import selectors
from iscas.forms import EstornoForm, ExtratoFiltroForm
from iscas.models.cadastro import Agente, Cliente
from iscas.permissions import exige_operador


def _filtros_validos(request):
    form = ExtratoFiltroForm(request.GET or None)
    filtros = form.cleaned_data if form.is_valid() else {}
    return form, {
        "inicio": filtros.get("inicio"),
        "fim": filtros.get("fim"),
        "agente": filtros.get("agente"),
        "cliente": filtros.get("cliente"),
        "modelo": filtros.get("modelo"),
        "tipo": filtros.get("tipo") or None,
        "identificador": filtros.get("identificador") or None,
    }


@exige_operador
def extrato(request):
    """Extrato de movimentações com filtros combináveis (ISC-RF-34)."""
    form, filtros = _filtros_validos(request)
    movimentacoes = selectors.extrato_movimentacoes(**filtros)
    paginas = Paginator(movimentacoes, 25)

    # A tela abre o painel de filtros e sinaliza a contagem quando há algum
    # aplicado — senão o operador vê uma lista curta sem saber por quê.
    filtros_ativos = sum(1 for valor in filtros.values() if valor)

    querystring = request.GET.copy()
    querystring.pop("page", None)

    return render(
        request,
        "iscas/extrato.html",
        {
            "form": form,
            "pagina": paginas.get_page(request.GET.get("page")),
            "form_estorno": EstornoForm(),
            "querystring": querystring.urlencode(),
            "filtros_ativos": filtros_ativos,
            # Botão de estorno desativado por ora, a pedido: é operação
            # destrutiva e o app está entrando em uso. A rota `iscas:estornar`
            # segue ativa — correção de lançamento continua possível por URL
            # direta. Trocar para True devolve o botão à tela.
            "mostrar_estorno": False,
        },
    )


class _Echo:
    """Buffer que devolve o que escrevem nele — o truque do csv em streaming."""

    def write(self, valor):
        return valor


@exige_operador
def extrato_csv(request):
    """Exporta o extrato respeitando os filtros (ISC-RF-37).

    `StreamingHttpResponse` porque a exportação é síncrona (sem Celery,
    ISC-ADR-13): um extrato grande não pode estourar memória nem o timeout do
    servidor enquanto monta a resposta inteira.
    """
    _, filtros = _filtros_validos(request)
    movimentacoes = selectors.extrato_movimentacoes(**filtros)

    escritor = csv.writer(_Echo(), delimiter=";")

    def linhas():
        # BOM primeiro. O conteúdo sempre foi UTF-8 e o `content_type` já
        # declarava o charset — mas o Excel IGNORA o cabeçalho HTTP ao abrir um
        # .csv salvo em disco e assume a codepage ANSI do Windows, que
        # transforma "Solicitação" em "Solicitação". O BOM é o único sinal que
        # ele lê nesse caminho. LibreOffice e pandas detectam os dois.
        yield BOM_UTF8
        yield escritor.writerow(
            [
                "ID", "Tipo", "Ocorrido em", "Registrado em", "Origem", "Destino",
                "Quantidade", "Autor", "Motivo da baixa", "Justificativa",
                "Nota fiscal", "Lote", "Solicitação", "Estorno de",
            ]
        ).encode("utf-8")
        for movimentacao in movimentacoes.iterator(chunk_size=500):
            yield escritor.writerow(
                [
                    movimentacao.pk,
                    movimentacao.get_tipo_display(),
                    timezone.localtime(movimentacao.ocorrido_em).strftime("%d/%m/%Y %H:%M"),
                    timezone.localtime(movimentacao.created_at).strftime("%d/%m/%Y %H:%M"),
                    str(movimentacao.origem),
                    str(movimentacao.destino),
                    movimentacao.quantidade_linhas,
                    movimentacao.autor.get_username(),
                    movimentacao.get_motivo_baixa_display() if movimentacao.motivo_baixa else "",
                    movimentacao.justificativa,
                    movimentacao.nota_fiscal,
                    movimentacao.lote,
                    movimentacao.solicitacao_id or "",
                    movimentacao.estorno_de_id or "",
                ]
            ).encode("utf-8")

    agora = timezone.localtime().strftime("%Y%m%d-%H%M")
    resposta = StreamingHttpResponse(linhas(), content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="extrato-iscas-{agora}.csv"'
    return resposta


@exige_operador
def historico_agente(request, pk):
    """Consolidado do agente (ISC-RF-35)."""
    agente = get_object_or_404(Agente.todos, pk=pk)
    contexto = selectors.historico_agente(agente)
    paginas = Paginator(contexto["movimentacoes"], 50)
    contexto["pagina"] = paginas.get_page(request.GET.get("page"))
    return render(request, "iscas/historico_agente.html", contexto)


@exige_operador
def historico_cliente(request, pk):
    """Consolidado do cliente (ISC-RF-36)."""
    cliente = get_object_or_404(Cliente.todos, pk=pk)
    contexto = selectors.historico_cliente(cliente)
    paginas = Paginator(contexto["movimentacoes"], 50)
    contexto["pagina"] = paginas.get_page(request.GET.get("page"))
    return render(request, "iscas/historico_cliente.html", contexto)
