"""Views de solicitação e atendimento — o fluxo central do app."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from iscas.enums import StatusSolicitacao
from iscas.forms import (
    AtribuicaoForm,
    ConfirmarEntregaForm,
    EscolhaUnidadesForm,
    MotivoForm,
    SolicitacaoForm,
)
from iscas.models.cadastro import ModeloEquipamento
from iscas.models.config import ConfiguracaoIscas
from iscas.models.operacao import Atribuicao, Solicitacao
from iscas.permissions import exige_operador
from iscas.selectors import solicitacoes_filtradas
from iscas.services import mensagem as mensagem_service
from iscas.services import solicitacao as solicitacao_service
from iscas.services.exceptions import IscasError
from iscas.services.saldo import saldo_disponivel


@exige_operador
def lista(request):
    status = request.GET.get("status") or None
    busca = (request.GET.get("q") or "").strip()
    # Excluídas ficam fora por padrão; a lixeira é um modo explícito da tela.
    excluidas = request.GET.get("excluidas") == "1"

    solicitacoes = solicitacoes_filtradas(
        status=status, busca=busca, excluidas=excluidas
    )
    paginas = Paginator(solicitacoes, 25)

    # A paginação precisa carregar os filtros adiante. Sem isto, ir para a
    # página 2 com um status filtrado devolvia a lista inteira — o filtro
    # sumia em silêncio, e a lista parecia ter mudado sozinha.
    querystring = request.GET.copy()
    querystring.pop("page", None)

    return render(
        request,
        "iscas/solicitacao_lista.html",
        {
            "pagina": paginas.get_page(request.GET.get("page")),
            "status_choices": StatusSolicitacao.choices,
            "status_atual": status,
            "busca": busca,
            "excluidas": excluidas,
            "querystring": querystring.urlencode(),
            "total": paginas.count,
        },
    )


@exige_operador
@require_POST
def excluir(request, pk):
    """Soft delete da solicitação (ISC-ADR-15).

    Correção de cadastro — duplicata, engano —, não evento de negócio. Para
    desistência do cliente existe o cancelamento, que libera reservas e mantém
    a solicitação visível como CANCELADA.
    """
    solicitacao = get_object_or_404(Solicitacao.todos, pk=pk)
    try:
        solicitacao_service.excluir_solicitacao(
            solicitacao=solicitacao,
            autor=request.user,
            motivo=request.POST.get("motivo", "").strip(),
        )
    except IscasError as exc:
        messages.error(request, str(exc))
        return redirect("iscas:solicitacao_detalhe", pk=pk)

    messages.success(
        request,
        f"Solicitação #{solicitacao.pk} excluída. Ela sai da lista, mas o "
        "histórico permanece — dá para restaurar pela lixeira.",
    )
    return redirect("iscas:solicitacao_lista")


@exige_operador
@require_POST
def restaurar(request, pk):
    """Desfaz a exclusão (ISC-ADR-15)."""
    solicitacao = get_object_or_404(Solicitacao.todos, pk=pk)
    solicitacao_service.restaurar_solicitacao(
        solicitacao=solicitacao, autor=request.user
    )
    messages.success(request, f"Solicitação #{solicitacao.pk} restaurada.")
    return redirect("iscas:solicitacao_detalhe", pk=pk)


@exige_operador
def criar(request):
    """Abertura da solicitação com um ou mais itens (ISC-RF-22)."""
    modelos = ModeloEquipamento.objects.order_by("nome")

    if request.method == "POST":
        form = SolicitacaoForm(request.POST)
        itens = _itens_do_post(request.POST, modelos)
        if form.is_valid() and itens:
            dados = form.cleaned_data
            try:
                solicitacao = solicitacao_service.abrir_solicitacao(
                    cliente=dados["cliente"],
                    itens=itens,
                    autor=request.user,
                    observacao=dados.get("observacao", ""),
                    prazo_desejado=dados.get("prazo_desejado"),
                    # Contato e endereço desta entrega: o form já trouxe do
                    # cadastro e o operador pôde ajustar.
                    **{
                        campo: dados.get(campo, "")
                        for campo in solicitacao_service._CAMPOS_DO_CLIENTE
                    },
                )
            except IscasError as exc:
                messages.error(request, str(exc))
            else:
                # Fora da transação de abertura, de propósito: é chamada de
                # rede ao Nominatim, e falha aqui não desfaz a solicitação.
                solicitacao_service.resolver_coordenada_de_entrega(
                    solicitacao, pin=form.pin_de_entrega()
                )
                if solicitacao.tem_coordenada_de_busca:
                    messages.success(request, f"Solicitação #{solicitacao.pk} aberta.")
                else:
                    messages.warning(
                        request,
                        f"Solicitação #{solicitacao.pk} aberta, mas o endereço de "
                        "entrega não foi localizado no mapa. Posicione o pin para "
                        "que ela entre na busca por agentes próximos.",
                    )
                return redirect("iscas:solicitacao_detalhe", pk=solicitacao.pk)
        elif not itens:
            messages.error(request, "Informe ao menos um modelo com quantidade.")
    else:
        form = SolicitacaoForm()

    return render(
        request,
        "iscas/solicitacao_form.html",
        # `config` traz a URL dos tiles do mapa de entrega — mesma fonte que os
        # formulários de cadastro usam.
        {"form": form, "modelos": modelos, "config": ConfiguracaoIscas.carregar()},
    )


@exige_operador
@require_POST
def ajustar_pin_entrega(request, pk):
    """Grava a coordenada do ponto de entrega arrastada no mapa.

    O par do `agente_ajustar_pin`, para a solicitação: endereço de entrega que
    o Nominatim não achou — condomínio novo, estrada rural, obra sem número —
    ganha posição pela mão do operador, e a solicitação volta para a busca por
    proximidade.
    """
    solicitacao = get_object_or_404(Solicitacao.todos, pk=pk)
    eh_ajax = request.headers.get("HX-Request") or request.headers.get(
        "X-Requested-With"
    ) == "XMLHttpRequest"

    gravou = solicitacao_service.resolver_coordenada_de_entrega(
        solicitacao,
        pin=(request.POST.get("latitude"), request.POST.get("longitude")),
    )
    if not gravou:
        erro = "Coordenada inválida. Posicione o pin no mapa antes de salvar."
        if eh_ajax:
            return JsonResponse({"erro": erro}, status=400)
        messages.error(request, erro)
        return redirect("iscas:solicitacao_detalhe", pk=pk)

    if eh_ajax:
        return JsonResponse(
            {
                "ok": True,
                "latitude": float(solicitacao.entrega_latitude),
                "longitude": float(solicitacao.entrega_longitude),
            }
        )
    messages.success(request, "Posição da entrega ajustada.")
    return redirect("iscas:solicitacao_detalhe", pk=pk)


def _itens_do_post(post, modelos):
    """Extrai os pares (modelo, quantidade) dos campos dinâmicos do template."""
    itens = []
    for modelo in modelos:
        bruto = post.get(f"quantidade_{modelo.pk}", "").strip()
        if not bruto:
            continue
        try:
            quantidade = int(bruto)
        except ValueError:
            continue
        if quantidade > 0:
            itens.append((modelo, quantidade))
    return itens


@exige_operador
def detalhe(request, pk):
    """Solicitação com cobertura, atribuições e busca por proximidade."""
    solicitacao = get_object_or_404(
        Solicitacao.todos.select_related("cliente", "aberta_por"), pk=pk
    )
    atribuicoes = solicitacao.atribuicoes.select_related("agente").order_by("id")

    return render(
        request,
        "iscas/solicitacao_detalhe.html",
        {
            "solicitacao": solicitacao,
            "cobertura": solicitacao_service.cobertura(solicitacao),
            "cobertura_total": solicitacao_service.cobertura_total(solicitacao),
            "atribuicoes": [
                {
                    "atribuicao": atribuicao,
                    "unidades": atribuicao.unidades_reservadas(),
                    "link_whatsapp": mensagem_service.link_whatsapp(atribuicao),
                }
                for atribuicao in atribuicoes
            ],
            "form_atribuicao": AtribuicaoForm(solicitacao=solicitacao),
            "form_entrega": ConfirmarEntregaForm(),
            "form_motivo": MotivoForm(),
            "eventos": solicitacao.eventos.select_related("autor").order_by(
                "-created_at", "-id"
            ),
            "config": ConfiguracaoIscas.carregar(),
        },
    )


@exige_operador
@require_POST
def atribuir(request, pk):
    """Cria a atribuição e reserva as unidades escolhidas (ISC-RF-23 a 25).

    Dois passos no mesmo endpoint, distinguidos pelo botão do formulário:

    1. **Escolher o agente.** Responde com a tela de escolha de unidades, que
       só existe depois de saber o agente — as unidades listadas são as dele.
    2. **Confirmar as unidades.** Reserva o que foi marcado, um ou vários
       modelos numa atribuição só (ISC-RN-10).
    """
    solicitacao = get_object_or_404(Solicitacao.todos, pk=pk)
    form_agente = AtribuicaoForm(request.POST, solicitacao=solicitacao)

    if not form_agente.is_valid():
        # Mostra o erro real do campo ("não tem nenhuma unidade disponível"),
        # não um "revise os dados" que deixa o operador adivinhando.
        for erros in form_agente.errors.values():
            for erro in erros:
                messages.error(request, erro)
        return redirect("iscas:solicitacao_detalhe", pk=pk)

    agente = form_agente.cleaned_data["agente"]
    confirmando = "confirmar" in request.POST

    form_unidades = EscolhaUnidadesForm(
        request.POST if confirmando else None,
        agente=agente,
        solicitacao=solicitacao,
    )

    if not confirmando or not form_unidades.is_valid():
        if confirmando:
            for erros in form_unidades.errors.values():
                for erro in erros:
                    messages.error(request, erro)
        return _render_escolha_unidades(request, solicitacao, agente, form_unidades)

    try:
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao,
            agente=agente,
            itens=form_unidades.itens(),
            unidades_por_modelo=form_unidades.unidades_por_modelo(),
            autor=request.user,
        )
    except IscasError as exc:
        messages.error(request, str(exc))
        return redirect("iscas:solicitacao_detalhe", pk=pk)

    total = atribuicao.reservas_ativas().count()
    messages.success(
        request,
        f"{total} unidade(s) reservada(s) com {agente.nome}. "
        "Envie a mensagem pelo WhatsApp.",
    )
    return redirect("iscas:solicitacao_detalhe", pk=pk)


def _render_escolha_unidades(request, solicitacao, agente, form_unidades):
    """Tela do segundo passo: quais unidades do agente vão para o cliente."""
    return render(
        request,
        "iscas/solicitacao_escolher_unidades.html",
        {
            "solicitacao": solicitacao,
            "agente": agente,
            "form_unidades": form_unidades,
            "cobertura": solicitacao_service.cobertura(solicitacao),
        },
    )


@exige_operador
@require_POST
def marcar_em_rota(request, pk):
    """ISC-RF-26."""
    atribuicao = get_object_or_404(Atribuicao.todos, pk=pk)
    try:
        solicitacao_service.marcar_em_rota(atribuicao=atribuicao, autor=request.user)
    except IscasError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{atribuicao.agente.nome} está em rota.")
    return redirect("iscas:solicitacao_detalhe", pk=atribuicao.solicitacao_id)


@exige_operador
@require_POST
def confirmar_entrega(request, pk):
    """ISC-RF-27: é aqui que a custódia passa ao cliente."""
    atribuicao = get_object_or_404(Atribuicao.todos, pk=pk)
    form = ConfirmarEntregaForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revise os dados da entrega.")
        return redirect("iscas:solicitacao_detalhe", pk=atribuicao.solicitacao_id)

    try:
        solicitacao_service.confirmar_entrega(
            atribuicao=atribuicao,
            autor=request.user,
            entregue_em=form.cleaned_data.get("entregue_em"),
            recebido_por=form.cleaned_data.get("recebido_por", ""),
        )
    except IscasError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request, f"Entrega de {atribuicao.agente.nome} confirmada."
        )
    return redirect("iscas:solicitacao_detalhe", pk=atribuicao.solicitacao_id)


@exige_operador
@require_POST
def cancelar_atribuicao(request, pk):
    """ISC-RF-28: libera as reservas, com motivo obrigatório."""
    atribuicao = get_object_or_404(Atribuicao.todos, pk=pk)
    form = MotivoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "O cancelamento exige motivo.")
        return redirect("iscas:solicitacao_detalhe", pk=atribuicao.solicitacao_id)

    try:
        solicitacao_service.cancelar_atribuicao(
            atribuicao=atribuicao,
            motivo=form.cleaned_data["motivo"],
            autor=request.user,
        )
    except IscasError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"Atribuição cancelada; as unidades voltaram ao saldo de "
            f"{atribuicao.agente.nome}.",
        )
    return redirect("iscas:solicitacao_detalhe", pk=atribuicao.solicitacao_id)


@exige_operador
@require_POST
def cancelar(request, pk):
    """Cancela a solicitação inteira (ISC-RF-28)."""
    solicitacao = get_object_or_404(Solicitacao.todos, pk=pk)
    form = MotivoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "O cancelamento exige motivo.")
        return redirect("iscas:solicitacao_detalhe", pk=pk)

    try:
        solicitacao_service.cancelar_solicitacao(
            solicitacao=solicitacao,
            motivo=form.cleaned_data["motivo"],
            autor=request.user,
        )
    except IscasError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request, "Solicitação cancelada e reservas liberadas."
        )
    return redirect("iscas:solicitacao_detalhe", pk=pk)


@exige_operador
def mensagem(request, pk):
    """Texto pronto para o WhatsApp (ISC-RF-29). O sistema não envia nada."""
    atribuicao = get_object_or_404(
        Atribuicao.todos.select_related("agente", "solicitacao__cliente"), pk=pk
    )
    return render(
        request,
        "iscas/_mensagem.html",
        {
            "atribuicao": atribuicao,
            "texto": mensagem_service.montar_texto_atribuicao(atribuicao),
            "link": mensagem_service.link_whatsapp(atribuicao),
        },
    )
