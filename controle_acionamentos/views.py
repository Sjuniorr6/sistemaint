from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    AcionamentoForm,
    FiltroAcionamentosForm,
    PedagioUpdateForm,
    VincularFranquiaLoteForm,
)
from .models import Acionamento, FranquiaAgente
from .selectors import listar_acionamentos, listar_franquias_por_cliente
from .services import vincular_franquia_em_lote


@login_required
def index(request):
    """Página inicial do app de Acionamentos.

    View fina do Módulo 0: apenas renderiza a tela inicial para validar
    o encanamento URL -> view -> template. Sem regra de negócio aqui.
    """
    return render(request, 'controle_acionamentos/index.html')


@login_required
@permission_required("controle_acionamentos.view_acionamento", raise_exception=True)
def acionamento_list(request):
    """Listagem base de Acionamentos (DD-014/M3) — view FINA.

    Aceita o filtro opcional por cliente (AC-06.1) via querystring. O
    FiltroAcionamentosForm valida o GET de forma TOLERANTE: valor inválido ou
    ausente vira cliente=None (sem filtro), nunca erro — por isso NÃO usamos
    get_object_or_404. Quem ordena e resolve os joins é o selector; a view só
    entrega o queryset e o cliente escolhido ao template. raise_exception=True:
    sem a permissão de leitura, devolve 403 em vez de mandar pro login.

    AC-06.2/06.3: com cliente filtrado, expõe as franquias daquele cliente para
    o select do vínculo em lote. Sem cliente, franquias = none() (contrato de
    contexto consistente; quem liga a UI de lote é cliente_filtrado, não a
    presença da chave).
    """
    form = FiltroAcionamentosForm(request.GET)
    cliente = form.cleaned_data.get("cliente") if form.is_valid() else None
    franquias = (
        listar_franquias_por_cliente(cliente)
        if cliente is not None
        else FranquiaAgente.objects.none()
    )
    return render(
        request,
        "controle_acionamentos/acionamento_list.html",
        {
            "acionamentos": listar_acionamentos(cliente=cliente),
            "cliente_filtrado": cliente,
            "franquias": franquias,
            "filtro_form": form,
        },
    )


@login_required
@permission_required("controle_acionamentos.add_acionamento", raise_exception=True)
def acionamento_create(request):
    """Criação de Acionamento (US-05) — view FINA.

    O ModelForm valida (is_valid -> full_clean -> Acionamento.clean) e o
    cálculo dos 5 campos derivados acontece sozinho no Acionamento.save()
    (recalcular_valor_agente). A view não contém regra de negócio nem recalcula.
    raise_exception=True: sem a permissão, devolve 403 em vez de mandar pro login.
    """
    if request.method == "POST":
        form = AcionamentoForm(request.POST)
        if form.is_valid():
            acionamento = form.save()  # o save() do model dispara o cálculo
            return redirect(
                "controle_acionamentos:acionamento_detail", pk=acionamento.pk
            )
    else:
        form = AcionamentoForm()

    return render(
        request, "controle_acionamentos/acionamento_form.html", {"form": form}
    )


@login_required
@permission_required("controle_acionamentos.view_acionamento", raise_exception=True)
def acionamento_detail(request, pk):
    """Detalhe de um Acionamento — somente leitura."""
    acionamento = get_object_or_404(Acionamento, pk=pk)
    return render(
        request,
        "controle_acionamentos/acionamento_detail.html",
        {"acionamento": acionamento},
    )


@login_required
@permission_required("controle_acionamentos.change_acionamento", raise_exception=True)
@require_POST
def acionamento_pedagio_update(request, pk):
    """Atualiza SÓ o pedágio de um Acionamento e recalcula (DD-014/M3) — view FINA.

    require_POST embaixo do login/permissão: anônimo cai no login (302), quem não
    tem change_acionamento leva 403, e só então GET vira 405. O save() já dispara
    recalcular_valor_agente (pedágio soma ao valor_agente, §8.5); nada extra aqui.
    """
    ac = get_object_or_404(Acionamento, pk=pk)
    form = PedagioUpdateForm(request.POST)
    if not form.is_valid():
        # AC-07.3: entrada inválida (ex.: pedágio negativo) não toca no banco.
        return JsonResponse({"erros": form.errors}, status=400)

    ac.pedagio = form.cleaned_data["pedagio"]
    ac.save()  # o save() do model recalcula os campos derivados
    ac.refresh_from_db()

    return JsonResponse(
        {"pedagio": str(ac.pedagio), "valor_agente": str(ac.valor_agente)}
    )


@login_required
@permission_required("controle_acionamentos.change_acionamento", raise_exception=True)
@require_POST
def acionamento_vincular_franquia_lote(request):
    """DD-015/M4 (subtask 5) — valida a seleção via VincularFranquiaLoteForm,
    delega o vínculo ao service vincular_franquia_em_lote (atômico) e traduz
    o resultado em messages + redirect preservando o filtro por cliente
    (?cliente=<pk do cliente da franquia>)."""
    form = VincularFranquiaLoteForm(request.POST)
    url_list = reverse("controle_acionamentos:acionamento_list")

    if not form.is_valid():
        messages.error(request, "Seleção inválida para o vínculo em lote.")
        return redirect(url_list)

    franquia = form.cleaned_data["franquia"]
    pks = [a.pk for a in form.cleaned_data["acionamentos"]]

    try:
        atualizados = vincular_franquia_em_lote(
            pks, franquia, sobrescrever=form.cleaned_data["sobrescrever"]
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect(f"{url_list}?cliente={franquia.cliente_id}")

    messages.success(request, f"{atualizados} acionamentos atualizados.")
    return redirect(f"{url_list}?cliente={franquia.cliente_id}")