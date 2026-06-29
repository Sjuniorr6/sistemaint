from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AcionamentoForm
from .models import Acionamento


@login_required
def index(request):
    """Página inicial do app de Acionamentos.

    View fina do Módulo 0: apenas renderiza a tela inicial para validar
    o encanamento URL -> view -> template. Sem regra de negócio aqui.
    """
    return render(request, 'controle_acionamentos/index.html')


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