from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AcionamentoForm,
    FiltroAcionamentosForm,
    PedagioUpdateForm,
    VincularFranquiaLoteForm,
)
from .models import Acionamento, FranquiaAgente
from .selectors import (
    contar_acionamentos_no_mes,
    contar_sem_franquia,
    listar_acionamentos,
    listar_franquias_por_cliente,
    somar_valor_agente_no_mes,
)
from .services import (
    compor_valor_agente,
    registrar_edicao_acionamento,
    vincular_franquia_em_lote,
)


@login_required
def index(request):
    """Home dashboard do app de Acionamentos (DD-032/ST7 + DD-048).

    View fina: os números vêm dos selectors (contar_acionamentos_no_mes /
    contar_sem_franquia / somar_valor_agente_no_mes) e o rótulo do mês é
    renderizado no template (filtro `date`, catálogo pt-br). `ultimos` reusa
    listar_acionamentos() (já ordenado DESC e com select_related), fatiado nos
    5 primeiros — sem query nova. Sem regra de negócio aqui.
    """
    hoje = timezone.localdate()  # âncora única: rótulo e contagens usam a mesma data
    contexto = {
        "hoje": hoje,
        "total_mes": contar_acionamentos_no_mes(hoje=hoje),
        "total_sem_franquia": contar_sem_franquia(),
        "total_valor_mes": somar_valor_agente_no_mes(hoje=hoje),
        "ultimos": listar_acionamentos()[:5],
    }
    return render(request, 'controle_acionamentos/index.html', contexto)


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

    DD-016/M5 (AC-08.2): paginação de 25/página com get_page TOLERANTE (page
    inválido → 1, fora do alcance → última), aplicada DEPOIS dos filtros e da
    ordenação do selector. O contexto "acionamentos" passa a ser o Page object,
    que é iterável — o template (tabela + form de lote) segue igual.
    """
    form = FiltroAcionamentosForm(request.GET)
    cliente = form.cleaned_data.get("cliente") if form.is_valid() else None
    agente = form.cleaned_data.get("agente") if form.is_valid() else None
    data_de = form.cleaned_data.get("data_de") if form.is_valid() else None
    data_ate = form.cleaned_data.get("data_ate") if form.is_valid() else None
    # Ponte tela→domínio: o campo se chama "status" no form; clean_status já
    # devolve True/False/None, que o selector consome como com_franquia.
    com_franquia = form.cleaned_data.get("status") if form.is_valid() else None
    franquias = (
        listar_franquias_por_cliente(cliente)
        if cliente is not None
        else FranquiaAgente.objects.none()
    )
    acionamentos = listar_acionamentos(
        cliente=cliente,
        agente=agente,
        data_de=data_de,
        data_ate=data_ate,
        com_franquia=com_franquia,
    )
    paginator = Paginator(acionamentos, 25)
    pagina = paginator.get_page(request.GET.get("page"))
    # Base da navegação de páginas: o template injeta &page=N sobre esta base;
    # sem o pop, o page antigo viajaria duplicado no link.
    params = request.GET.copy()
    params.pop("page", None)
    filtros_querystring = params.urlencode()
    return render(
        request,
        "controle_acionamentos/acionamento_list.html",
        {
            "acionamentos": pagina,
            "cliente_filtrado": cliente,
            "franquias": franquias,
            "filtro_form": form,
            "filtros_querystring": filtros_querystring,
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
@permission_required("controle_acionamentos.change_acionamento", raise_exception=True)
def acionamento_update(request, pk):
    """Edição de Acionamento (DD-049/ST1) — view FINA, espelho do create.

    O ModelForm valida (is_valid -> full_clean -> Acionamento.clean) e o
    recálculo dos 5 campos derivados acontece sozinho no Acionamento.save()
    (recalcular_valor_agente). A view não contém regra de negócio nem recalcula;
    só delega. raise_exception=True: sem change_acionamento, devolve 403 em vez
    de mandar pro login.
    """
    acionamento = get_object_or_404(Acionamento, pk=pk)
    if request.method == "POST":
        form = AcionamentoForm(request.POST, instance=acionamento)
        if form.is_valid():
            # Foto independente do estado atual ANTES do save (não é a instância
            # do form) — é o "antes" que a trilha compara com o "depois".
            antigo = Acionamento.objects.get(pk=acionamento.pk)
            with transaction.atomic():
                # Trilha e save na mesma transação — ou tudo, ou nada.
                salvo = form.save()  # o save() do model dispara o recálculo
                registrar_edicao_acionamento(antigo, salvo, request.user)
            return redirect(
                "controle_acionamentos:acionamento_detail", pk=acionamento.pk
            )
    else:
        form = AcionamentoForm(instance=acionamento)

    return render(
        request,
        "controle_acionamentos/acionamento_form.html",
        {
            "form": form,
            "titulo_pagina": "Editar acionamento",
            "subtitulo_pagina": "Ajuste os campos — o valor do agente é recalculado ao salvar",
            "texto_botao": "Salvar alterações",
            "modo_edicao": True,
            "ativo_pill": "editando",
        },
    )


@login_required
@permission_required("controle_acionamentos.view_acionamento", raise_exception=True)
def acionamento_detail(request, pk):
    """Detalhe de um Acionamento — somente leitura.

    O extrato de parcelas (DD-032/ST5) é recomposto pelo service, sem persistir;
    a view só delega e entrega ao template.
    """
    acionamento = get_object_or_404(Acionamento, pk=pk)
    composicao = compor_valor_agente(acionamento)
    return render(
        request,
        "controle_acionamentos/acionamento_detail.html",
        {"acionamento": acionamento, "composicao": composicao},
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
    (?cliente=<pk do cliente da franquia>).

    AC-06.5 (subtask 4): sem a flag sobrescrever, se algum dos selecionados já
    tiver franquia, NÃO executa — renderiza a página de confirmação em duas
    etapas (padrão delete-confirm). A checagem aqui é roteamento de UX; a
    enforcement (recusar sem flag) permanece no service. Cross-cliente (RN-06)
    segue erro terminal via ValidationError.
    """
    form = VincularFranquiaLoteForm(request.POST)
    url_list = reverse("controle_acionamentos:acionamento_list")

    if not form.is_valid():
        messages.error(request, "Seleção inválida para o vínculo em lote.")
        return redirect(url_list)

    franquia = form.cleaned_data["franquia"]
    acionamentos_selecionados = form.cleaned_data["acionamentos"]
    pks = [a.pk for a in acionamentos_selecionados]

    # AC-06.5 — etapa 1: conflito de sobrescrita sem confirmação não executa
    # nada; renderiza a página de confirmação. Roteamento de UX (a enforcement
    # segue no service). Cross-cliente NÃO cai aqui: só olha franquia já vinculada.
    if not form.cleaned_data["sobrescrever"]:
        conflitantes = (
            Acionamento.objects.select_related("cliente", "agente", "franquia_agente")
            .filter(pk__in=pks, franquia_agente__isnull=False)
        )
        if conflitantes.exists():
            return render(
                request,
                "controle_acionamentos/acionamento_vincular_confirmar.html",
                {
                    "franquia": franquia,
                    "acionamentos_selecionados": acionamentos_selecionados,
                    "conflitantes": conflitantes,
                    "cliente": franquia.cliente_id,
                },
            )

    try:
        atualizados = vincular_franquia_em_lote(
            pks, franquia, sobrescrever=form.cleaned_data["sobrescrever"]
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect(f"{url_list}?cliente={franquia.cliente_id}")

    messages.success(request, f"{atualizados} acionamentos atualizados.")
    return redirect(f"{url_list}?cliente={franquia.cliente_id}")