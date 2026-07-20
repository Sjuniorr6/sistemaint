from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    AcionamentoForm,
    AgenteForm,
    ClienteForm,
    FiltroAcionamentosForm,
    FranquiaForm,
    PedagioUpdateForm,
    ResponsavelForm,
    VincularFranquiaLoteForm,
    montar_catalogo_formset,
)
from .models import Acionamento, Agente, Cliente, FranquiaAgente, ResponsavelAgente
from .selectors import (
    contar_acionamentos_no_mes,
    contar_agentes,
    contar_clientes,
    contar_franquias,
    contar_responsaveis,
    contar_sem_franquia,
    listar_acionamentos,
    listar_franquias_por_cliente,
    listar_historico_do_acionamento,
    listar_servicos_ativos_por_cliente,
    somar_valor_agente_no_mes,
)
from .services import (
    acionamentos_em_conflito_de_franquia,
    aplicar_servico_ao_acionamento,
    compor_valor_agente,
    registrar_edicao_acionamento,
    sincronizar_catalogo_do_cliente,
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
        # DD-050/ST5: contadores da fileira de cadastros. O template gateia cada
        # item por perms.view_<model>; os números só são exibidos junto do link.
        "contador_clientes": contar_clientes(),
        "contador_agentes": contar_agentes(),
        "contador_responsaveis": contar_responsaveis(),
        "contador_franquias": contar_franquias(),
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
            # commit=False: carimbamos o autor (DD-051/ST1) e aplicamos o snapshot
            # do serviço (DD-067/ST2) ANTES do save do model, que é quem dispara o
            # cálculo (recalcular_valor_agente). aplicar_servico copia os 5 valores
            # do serviço para os campos inline (a fonte do cálculo) e deriva o
            # nome_servico. Acionamento não tem M2M, então sem save_m2m() depois.
            acionamento = form.save(commit=False)
            acionamento.criado_por = request.user
            aplicar_servico_ao_acionamento(
                acionamento, form.cleaned_data["servico_cliente"]
            )
            acionamento.save()
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
            # Aplica o snapshot do serviço (DD-067/ST2) antes do save, como no
            # create. As regras finas de edição (re-snapshot ao trocar serviço,
            # coerência ao trocar cliente) são ST3 — aqui só o mínimo.
            salvo = form.save(commit=False)
            aplicar_servico_ao_acionamento(
                salvo, form.cleaned_data["servico_cliente"]
            )
            with transaction.atomic():
                # Trilha e save na mesma transação — ou tudo, ou nada.
                salvo.save()  # o save() do model dispara o recálculo
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
    historico = listar_historico_do_acionamento(acionamento)
    return render(
        request,
        "controle_acionamentos/acionamento_detail.html",
        {
            "acionamento": acionamento,
            "composicao": composicao,
            "historico": historico,
        },
    )


@login_required
@permission_required("controle_acionamentos.change_acionamento", raise_exception=True)
@require_POST
def acionamento_pedagio_update(request, pk):
    """Atualiza SÓ o pedágio de um Acionamento e recalcula (DD-014/M3) — view FINA.

    require_POST embaixo do login/permissão: anônimo cai no login (302), quem não
    tem change_acionamento leva 403, e só então GET vira 405. O save() já dispara
    recalcular_valor_agente (pedágio soma ao valor_agente, §8.5); nada extra aqui.

    DD-068/ST3: sem franquia o pedágio persiste normalmente, mas o valor do
    agente é PENDENTE (None) — o JSON devolve null de verdade, nunca a string
    "None". Com franquia, segue o Decimal serializado como string.
    """
    ac = get_object_or_404(Acionamento, pk=pk)
    form = PedagioUpdateForm(request.POST)
    if not form.is_valid():
        # AC-07.3: entrada inválida (ex.: pedágio negativo) não toca no banco.
        return JsonResponse({"erros": form.errors}, status=400)

    # Foto independente do estado atual ANTES do save (DD-068/ST4) — o "antes"
    # que a trilha compara com o "depois", como em acionamento_update.
    antigo = Acionamento.objects.get(pk=ac.pk)
    ac.pedagio = form.cleaned_data["pedagio"]
    with transaction.atomic():
        # Trilha e save na mesma transação — ou tudo, ou nada.
        ac.save()  # o save() do model recalcula os campos derivados
        ac.refresh_from_db()
        registrar_edicao_acionamento(antigo, ac, request.user)

    valor_agente = str(ac.valor_agente) if ac.valor_agente is not None else None
    return JsonResponse({"pedagio": str(ac.pedagio), "valor_agente": valor_agente})


@login_required
@permission_required("controle_acionamentos.view_acionamento", raise_exception=True)
@require_GET
def servicos_por_cliente(request, cliente_id):
    """DD-067/ST2 — serviços ATIVOS de um cliente, para o select do form de
    acionamento (criação e edição) — view FINA.

    Permissão view_acionamento (não add/change): é leitura pura do catálogo, que
    serve tanto a tela de criação quanto a de edição. O selector
    listar_servicos_ativos_por_cliente já filtra por ativo e ordena pelo catálogo.
    Decimais serializados como STRING (str(Decimal), regra da casa); franquia_km é
    inteiro. 404 se o cliente não existir.

    DD-067/ST4 — parâmetro opcional `incluir` (id do serviço já vinculado a um
    acionamento em edição): faz o serviço reaparecer MESMO desativado, para a tela
    de edição não perder a opção atual. Conversão tolerante: valor não-numérico ou
    ausente vira None (parâmetro ignorado, sem erro) — a regra de "outro cliente /
    inexistente" já é tratada pelo selector. Cada item ganha `inativo` (bool).
    """
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    incluir_raw = request.GET.get("incluir")
    try:
        incluir_id = int(incluir_raw) if incluir_raw else None
    except (TypeError, ValueError):
        incluir_id = None
    servicos = [
        {
            "id": s.pk,
            "nome": s.get_nome_display(),
            "inativo": not s.ativo,
            "valor_acionamento": str(s.valor_acionamento),
            "franquia_km": s.franquia_km,
            "franquia_horas": str(s.franquia_horas),
            "valor_km_excedente": str(s.valor_km_excedente),
            "valor_hora_excedente": str(s.valor_hora_excedente),
        }
        for s in listar_servicos_ativos_por_cliente(cliente, incluir_id=incluir_id)
    ]
    return JsonResponse({"servicos": servicos})


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
    # segue no service). MESMA regra do service, via helper (fonte única): conflito
    # é franquia já vinculada E DIFERENTE da selecionada (DD-051/ST2) — idêntica
    # passa. Cross-cliente NÃO cai aqui: só olha franquia já vinculada.
    if not form.cleaned_data["sobrescrever"]:
        conflitantes = acionamentos_em_conflito_de_franquia(
            pks, franquia
        ).select_related("cliente", "agente", "franquia_agente")
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


# ---------------------------------------------------------------------------
# Cadastros — DD-050: telas de Cliente (lista/criar/editar). Views FINAS,
# espelho das de acionamento. Cadastro pequeno: sem paginação; ordena por nome.
# ---------------------------------------------------------------------------


@login_required
@permission_required("controle_acionamentos.view_cliente", raise_exception=True)
def cliente_list(request):
    """Listagem de Clientes (DD-050/ST1) — view FINA.

    Cadastro pequeno: sem paginação, ordenado por nome_empresa. Sem regra de
    negócio — só entrega o queryset. raise_exception=True: sem view_cliente,
    devolve 403 em vez de mandar pro login.
    """
    clientes = Cliente.objects.all().order_by("nome_empresa")
    return render(
        request,
        "controle_acionamentos/cliente_list.html",
        {"clientes": clientes},
    )


@login_required
@permission_required("controle_acionamentos.add_cliente", raise_exception=True)
def cliente_create(request):
    """Criação de Cliente (DD-050/ST1) — view FINA.

    O ClienteForm valida via is_valid -> full_clean -> Cliente.clean (nome
    obrigatório, CNPJ válido e normalizado). O catálogo de serviços (DD-066/ST2)
    viaja no MESMO POST via formset: cliente e catálogo só persistem juntos, em
    transaction.atomic — qualquer parte inválida reexibe a página (200) sem
    gravar nada.
    """
    if request.method == "POST":
        form = ClienteForm(request.POST)
        formset = montar_catalogo_formset(data=request.POST)
        # Validar os DOIS sem short-circuit: assim os erros de ambos aparecem
        # juntos no reexibir, não só os do primeiro que falhar. O catálogo é
        # parte do POST do cliente — sem o management form o formset é inválido
        # e a página é reexibida (200), sem porta dos fundos.
        form_ok = form.is_valid()
        formset_ok = formset.is_valid()
        if form_ok and formset_ok:
            with transaction.atomic():
                cliente = form.save()
                sincronizar_catalogo_do_cliente(cliente, formset)
            return redirect("controle_acionamentos:cliente_list")
    else:
        form = ClienteForm()
        formset = montar_catalogo_formset()

    return render(
        request,
        "controle_acionamentos/cliente_form.html",
        {"form": form, "formset": formset, "modo": "criar"},
    )


@login_required
@permission_required("controle_acionamentos.change_cliente", raise_exception=True)
def cliente_update(request, pk):
    """Edição de Cliente (DD-050/ST1) — view FINA, espelho do create.

    Reusa o ClienteForm com instance; POST válido salva e redireciona para a
    listagem. raise_exception=True: sem change_cliente, devolve 403.

    O catálogo de serviços (DD-066/ST2) é montado COM o cliente: as linhas nascem
    preenchidas pelos registros existentes, e o cliente chega ao clean do formset
    (barra esvaziar um serviço já cadastrado). Cliente e catálogo persistem juntos
    em transaction.atomic; qualquer parte inválida reexibe a página (200).
    """
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        formset = montar_catalogo_formset(data=request.POST, cliente=cliente)
        form_ok = form.is_valid()
        formset_ok = formset.is_valid()
        if form_ok and formset_ok:
            with transaction.atomic():
                form.save()
                sincronizar_catalogo_do_cliente(cliente, formset)
            return redirect("controle_acionamentos:cliente_list")
    else:
        form = ClienteForm(instance=cliente)
        formset = montar_catalogo_formset(cliente=cliente)

    return render(
        request,
        "controle_acionamentos/cliente_form.html",
        {"form": form, "formset": formset, "modo": "editar"},
    )


@login_required
@permission_required("controle_acionamentos.view_agente", raise_exception=True)
def agente_list(request):
    """Listagem de Agentes (DD-050/ST2) — view FINA.

    Cadastro pequeno: sem paginação, ordenado por nome. prefetch_related dos
    clientes vinculados evita N+1 ao listar os nomes por linha (o template
    percorre agente.clientes_vinculados por agente).
    """
    agentes = (
        Agente.objects.all()
        .order_by("nome")
        .prefetch_related("clientes_vinculados")
    )
    return render(
        request,
        "controle_acionamentos/agente_list.html",
        {"agentes": agentes},
    )


@login_required
@permission_required("controle_acionamentos.add_agente", raise_exception=True)
def agente_create(request):
    """Criação de Agente (DD-050/ST2) — view FINA, espelho do cliente_create.

    O AgenteForm valida via is_valid -> full_clean -> Agente.clean (nome, CPF,
    CNH). form.save() persiste o M2M clientes_vinculados sozinho (sem commit=False).
    POST válido salva e redireciona para a listagem.
    """
    if request.method == "POST":
        form = AgenteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("controle_acionamentos:agente_list")
    else:
        form = AgenteForm()

    return render(
        request,
        "controle_acionamentos/agente_form.html",
        {"form": form, "modo": "criar"},
    )


@login_required
@permission_required("controle_acionamentos.change_agente", raise_exception=True)
def agente_update(request, pk):
    """Edição de Agente (DD-050/ST2) — view FINA, espelho do cliente_update.

    Reusa o AgenteForm com instance; form.save() atualiza os campos e o M2M.
    raise_exception=True: sem change_agente, devolve 403.
    """
    agente = get_object_or_404(Agente, pk=pk)
    if request.method == "POST":
        form = AgenteForm(request.POST, instance=agente)
        if form.is_valid():
            form.save()
            return redirect("controle_acionamentos:agente_list")
    else:
        form = AgenteForm(instance=agente)

    return render(
        request,
        "controle_acionamentos/agente_form.html",
        {"form": form, "modo": "editar"},
    )


@login_required
@permission_required("controle_acionamentos.view_responsavelagente", raise_exception=True)
def responsavel_list(request):
    """Listagem de Responsáveis (DD-050/ST3) — view FINA.

    Cadastro pequeno: sem paginação, ordenado por nome. Sem regra de negócio —
    só entrega o queryset. raise_exception=True: sem view_responsavelagente,
    devolve 403 em vez de mandar pro login.
    """
    responsaveis = ResponsavelAgente.objects.all().order_by("nome")
    return render(
        request,
        "controle_acionamentos/responsavel_list.html",
        {"responsaveis": responsaveis},
    )


@login_required
@permission_required("controle_acionamentos.add_responsavelagente", raise_exception=True)
def responsavel_create(request):
    """Criação de Responsável (DD-050/ST3) — view FINA, espelho do cliente_create.

    O ResponsavelForm valida via is_valid -> full_clean -> ResponsavelAgente.clean
    (nome obrigatório). POST válido salva e redireciona para a listagem.
    """
    if request.method == "POST":
        form = ResponsavelForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("controle_acionamentos:responsavel_list")
    else:
        form = ResponsavelForm()

    return render(
        request,
        "controle_acionamentos/responsavel_form.html",
        {"form": form, "modo": "criar"},
    )


@login_required
@permission_required("controle_acionamentos.change_responsavelagente", raise_exception=True)
def responsavel_update(request, pk):
    """Edição de Responsável (DD-050/ST3) — view FINA, espelho do cliente_update.

    Reusa o ResponsavelForm com instance; POST válido salva e redireciona para a
    listagem. raise_exception=True: sem change_responsavelagente, devolve 403.
    """
    responsavel = get_object_or_404(ResponsavelAgente, pk=pk)
    if request.method == "POST":
        form = ResponsavelForm(request.POST, instance=responsavel)
        if form.is_valid():
            form.save()
            return redirect("controle_acionamentos:responsavel_list")
    else:
        form = ResponsavelForm(instance=responsavel)

    return render(
        request,
        "controle_acionamentos/responsavel_form.html",
        {"form": form, "modo": "editar"},
    )


@login_required
@permission_required("controle_acionamentos.view_franquiaagente", raise_exception=True)
def franquia_list(request):
    """Listagem de Franquias (DD-050/ST4) — view FINA.

    Cadastro pequeno: sem paginação. select_related("cliente") evita N+1 ao
    exibir o cliente por linha; ordena por cliente e depois nome.
    """
    franquias = (
        FranquiaAgente.objects.select_related("cliente")
        .order_by("cliente__nome_empresa", "nome")
    )
    return render(
        request,
        "controle_acionamentos/franquia_list.html",
        {"franquias": franquias},
    )


@login_required
@permission_required("controle_acionamentos.add_franquiaagente", raise_exception=True)
def franquia_create(request):
    """Criação de Franquia (DD-050/ST4) — view FINA, espelho do cliente_create.

    O FranquiaForm valida via is_valid -> full_clean -> FranquiaAgente.clean
    (regra km 0 + escalonamento) + UniqueConstraint (cliente+nome). POST inválido
    re-renderiza (200) com os erros; POST válido salva e redireciona.
    """
    if request.method == "POST":
        form = FranquiaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("controle_acionamentos:franquia_list")
    else:
        form = FranquiaForm()

    return render(
        request,
        "controle_acionamentos/franquia_form.html",
        {"form": form, "modo": "criar"},
    )


@login_required
@permission_required("controle_acionamentos.change_franquiaagente", raise_exception=True)
def franquia_update(request, pk):
    """Edição de Franquia (DD-050/ST4) — view FINA, espelho do cliente_update.

    CRÍTICO (§18 / teste 8): salva SÓ a franquia (form.save() e nada mais).
    JAMAIS recalcular ou re-salvar acionamentos vinculados — os valores ficam
    congelados no acionamento no momento do cálculo. Editar a franquia aqui não
    pode alterar histórico.
    """
    franquia = get_object_or_404(FranquiaAgente, pk=pk)
    if request.method == "POST":
        form = FranquiaForm(request.POST, instance=franquia)
        if form.is_valid():
            form.save()
            return redirect("controle_acionamentos:franquia_list")
    else:
        form = FranquiaForm(instance=franquia)

    return render(
        request,
        "controle_acionamentos/franquia_form.html",
        {"form": form, "modo": "editar"},
    )