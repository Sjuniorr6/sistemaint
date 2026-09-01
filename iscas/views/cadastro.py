"""Views de cadastro: Agente, Cliente e Modelo."""
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from iscas.forms import AgenteForm, ClienteForm, DepositoForm, ModeloForm
from iscas.models.cadastro import Agente, Cliente, Deposito, ModeloEquipamento
from iscas.models.config import ConfiguracaoIscas
from iscas.permissions import exige_operador
from iscas.selectors import historico_agente as historico_agente_selector
from iscas.services import cadastro as cadastro_service
from iscas.services.exceptions import AgenteComSaldo, DepositoComSaldo, IscasError
from iscas.services.geo import ajustar_pin
from iscas.services.saldo import saldo_por_modelo, tem_saldo


def _contexto_endereco(form, *, titulo, entidade=None, **extra):
    """Contexto comum dos formulários com CEP e mapa de conferência.

    As coordenadas vão como **string** com ponto decimal, prontas para entrar
    no JavaScript. Não é preciosismo: com `LANGUAGE_CODE = 'pt-br'`, o Django
    formata float no template como `-23,55052` — vírgula —, o que é
    `SyntaxError` em JS e derruba o `<script>` inteiro, junto com o Alpine.
    `"null"` (string) é o literal que o JS entende quando não há coordenada.
    """
    latitude = longitude = "null"
    if entidade is not None and entidade.tem_coordenada:
        latitude = f"{entidade.latitude:.6f}"
        longitude = f"{entidade.longitude:.6f}"
    return {
        "form": form,
        "titulo": titulo,
        "config": ConfiguracaoIscas.carregar(),
        "latitude_js": latitude,
        "longitude_js": longitude,
        **extra,
    }


# ---------------------------------------------------------------------------
# Agentes
# ---------------------------------------------------------------------------


@exige_operador
def agente_lista(request):
    """Listagem com CPF mascarado (ISC-RN-16) e alerta de pin pendente."""
    busca = request.GET.get("q", "").strip()
    agentes = Agente.objects.order_by("nome")
    if busca:
        agentes = agentes.filter(nome__icontains=busca)

    linhas = [
        {
            "agente": agente,
            "cpf": agente.cpf_mascarado,
            "saldos": list(saldo_por_modelo(agente)),
        }
        for agente in agentes
    ]
    return render(
        request,
        "iscas/agente_lista.html",
        {"linhas": linhas, "busca": busca},
    )


@exige_operador
def agente_detalhe(request, pk):
    """Ficha do agente — único lugar que exibe o CPF completo (ISC-RN-16)."""
    agente = get_object_or_404(Agente.todos, pk=pk)
    contexto = historico_agente_selector(agente)
    contexto.update(
        {
            "cpf_completo": agente.cpf,
            "config": ConfiguracaoIscas.carregar(),
        }
    )
    return render(request, "iscas/agente_detalhe.html", contexto)


@exige_operador
def agente_criar(request):
    if request.method == "POST":
        form = AgenteForm(request.POST)
        if form.is_valid():
            agente = form.save(commit=False)
            cadastro_service.salvar_com_geocodificacao(
                agente, endereco_mudou=True, pin=form.pin_ajustado()
            )
            if agente.tem_coordenada:
                messages.success(request, f"Agente {agente.nome} cadastrado.")
            else:
                messages.warning(
                    request,
                    f"Agente {agente.nome} cadastrado, mas o endereço não foi "
                    "localizado. Ajuste o pin no mapa para que ele apareça na "
                    "busca por proximidade.",
                )
            return redirect("iscas:agente_detalhe", pk=agente.pk)
    else:
        form = AgenteForm()
    return render(
        request,
        "iscas/agente_form.html",
        _contexto_endereco(form, titulo="Novo agente"),
    )


@exige_operador
def agente_editar(request, pk):
    agente = get_object_or_404(Agente.todos, pk=pk)
    if request.method == "POST":
        form = AgenteForm(request.POST, instance=agente)
        if form.is_valid():
            atualizado = form.save(commit=False)
            cadastro_service.salvar_com_geocodificacao(
                atualizado,
                endereco_mudou=form.endereco_mudou(),
                pin=form.pin_ajustado(),
            )
            messages.success(request, "Agente atualizado.")
            return redirect("iscas:agente_detalhe", pk=agente.pk)
    else:
        form = AgenteForm(instance=agente)
    return render(
        request,
        "iscas/agente_form.html",
        _contexto_endereco(
            form, titulo=f"Editar {agente.nome}", entidade=agente, agente=agente
        ),
    )


@exige_operador
@require_POST
def agente_desativar(request, pk):
    """Desativação bloqueada se o agente ainda segura equipamento (ISC-RN-18)."""
    agente = get_object_or_404(Agente.todos, pk=pk)
    try:
        cadastro_service.desativar_agente(agente)
    except AgenteComSaldo as exc:
        messages.error(request, str(exc))
        return redirect("iscas:agente_detalhe", pk=agente.pk)
    messages.success(request, f"Agente {agente.nome} desativado.")
    return redirect("iscas:agente_lista")


@exige_operador
@require_POST
def agente_ajustar_pin(request, pk):
    """Grava a posição arrastada no mapa (ISC-RF-03)."""
    agente = get_object_or_404(Agente.todos, pk=pk)
    eh_ajax = request.headers.get("HX-Request") or request.headers.get(
        "X-Requested-With"
    ) == "XMLHttpRequest"

    try:
        ajustar_pin(
            agente,
            latitude=request.POST.get("latitude"),
            longitude=request.POST.get("longitude"),
        )
    except ValueError as exc:
        # Sem pin posicionado o formulário manda campos vazios. É erro do
        # operador, não do servidor: avisa e volta para a ficha.
        if eh_ajax:
            return JsonResponse({"erro": str(exc)}, status=400)
        messages.error(request, str(exc))
        return redirect("iscas:agente_detalhe", pk=agente.pk)

    if eh_ajax:
        return JsonResponse(
            {
                "ok": True,
                "latitude": float(agente.latitude),
                "longitude": float(agente.longitude),
            }
        )
    messages.success(request, "Posição do agente ajustada.")
    return redirect("iscas:agente_detalhe", pk=agente.pk)


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------


@exige_operador
def cliente_lista(request):
    busca = request.GET.get("q", "").strip()
    clientes = Cliente.objects.order_by("nome_razao_social")
    if busca:
        clientes = clientes.filter(nome_razao_social__icontains=busca)
    return render(
        request, "iscas/cliente_lista.html", {"clientes": clientes, "busca": busca}
    )


@exige_operador
def cliente_detalhe(request, pk):
    from iscas.selectors import historico_cliente

    cliente = get_object_or_404(Cliente.todos, pk=pk)
    contexto = historico_cliente(cliente)
    contexto["config"] = ConfiguracaoIscas.carregar()
    return render(request, "iscas/cliente_detalhe.html", contexto)


@exige_operador
def cliente_criar(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cadastro_service.salvar_com_geocodificacao(
                cliente, endereco_mudou=True, pin=form.pin_ajustado()
            )
            if cliente.tem_coordenada:
                messages.success(request, f"Cliente {cliente} cadastrado.")
            else:
                messages.warning(
                    request,
                    f"Cliente {cliente} cadastrado, mas sem coordenada. "
                    "Ajuste o pin para usar a busca por proximidade a partir dele.",
                )
            return redirect("iscas:cliente_detalhe", pk=cliente.pk)
    else:
        form = ClienteForm()
    return render(
        request,
        "iscas/cliente_form.html",
        _contexto_endereco(form, titulo="Novo cliente"),
    )


@exige_operador
def cliente_editar(request, pk):
    cliente = get_object_or_404(Cliente.todos, pk=pk)
    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            atualizado = form.save(commit=False)
            cadastro_service.salvar_com_geocodificacao(
                atualizado,
                endereco_mudou=form.endereco_mudou(),
                pin=form.pin_ajustado(),
            )
            messages.success(request, "Cliente atualizado.")
            return redirect("iscas:cliente_detalhe", pk=cliente.pk)
    else:
        form = ClienteForm(instance=cliente)
    return render(
        request,
        "iscas/cliente_form.html",
        _contexto_endereco(
            form, titulo=f"Editar {cliente}", entidade=cliente, cliente=cliente
        ),
    )


@exige_operador
@require_POST
def cliente_desativar(request, pk):
    cliente = get_object_or_404(Cliente.todos, pk=pk)
    cadastro_service.desativar_cliente(cliente)
    messages.success(request, f"Cliente {cliente} desativado.")
    return redirect("iscas:cliente_lista")


@exige_operador
@require_POST
def cliente_ajustar_pin(request, pk):
    cliente = get_object_or_404(Cliente.todos, pk=pk)
    eh_ajax = request.headers.get("HX-Request") or request.headers.get(
        "X-Requested-With"
    ) == "XMLHttpRequest"

    try:
        ajustar_pin(
            cliente,
            latitude=request.POST.get("latitude"),
            longitude=request.POST.get("longitude"),
        )
    except ValueError as exc:
        if eh_ajax:
            return JsonResponse({"erro": str(exc)}, status=400)
        messages.error(request, str(exc))
        return redirect("iscas:cliente_detalhe", pk=cliente.pk)

    if eh_ajax:
        return JsonResponse(
            {
                "ok": True,
                "latitude": float(cliente.latitude),
                "longitude": float(cliente.longitude),
            }
        )
    messages.success(request, "Posição do cliente ajustada.")
    return redirect("iscas:cliente_detalhe", pk=cliente.pk)


# ---------------------------------------------------------------------------
# Depósitos
# ---------------------------------------------------------------------------


@exige_operador
def deposito_lista(request):
    """Pontos de estoque da empresa — de onde o equipamento sai para os agentes."""
    depositos = [
        {
            "deposito": deposito,
            "saldos": list(saldo_por_modelo(deposito)),
            "tem_saldo": tem_saldo(deposito),
        }
        for deposito in Deposito.objects.order_by("nome")
    ]
    return render(request, "iscas/deposito_lista.html", {"linhas": depositos})


@exige_operador
def deposito_criar(request):
    if request.method == "POST":
        form = DepositoForm(request.POST)
        if form.is_valid():
            deposito = form.save(commit=False)
            cadastro_service.salvar_com_geocodificacao(
                deposito, endereco_mudou=True, pin=form.pin_ajustado()
            )
            messages.success(request, f"Depósito {deposito.nome} cadastrado.")
            return redirect("iscas:deposito_lista")
    else:
        form = DepositoForm()
    return render(
        request,
        "iscas/deposito_form.html",
        _contexto_endereco(form, titulo="Novo depósito"),
    )


@exige_operador
def deposito_editar(request, pk):
    deposito = get_object_or_404(Deposito.todos, pk=pk)
    if request.method == "POST":
        form = DepositoForm(request.POST, instance=deposito)
        if form.is_valid():
            atualizado = form.save(commit=False)
            cadastro_service.salvar_com_geocodificacao(
                atualizado,
                endereco_mudou=form.endereco_mudou(),
                pin=form.pin_ajustado(),
            )
            messages.success(request, "Depósito atualizado.")
            return redirect("iscas:deposito_lista")
    else:
        form = DepositoForm(instance=deposito)
    return render(
        request,
        "iscas/deposito_form.html",
        _contexto_endereco(
            form, titulo=f"Editar {deposito.nome}", entidade=deposito,
            deposito=deposito,
        ),
    )


@exige_operador
@require_POST
def deposito_desativar(request, pk):
    """Desativar depósito com estoque é bloqueado, como no agente (ISC-RN-18).

    O motivo é o mesmo: desativação não pode evaporar estoque. O equipamento
    precisa ser transferido antes.
    """
    deposito = get_object_or_404(Deposito.todos, pk=pk)
    try:
        cadastro_service.desativar_deposito(deposito)
    except DepositoComSaldo as exc:
        messages.error(request, str(exc))
        return redirect("iscas:deposito_lista")
    messages.success(request, f"Depósito {deposito.nome} desativado.")
    return redirect("iscas:deposito_lista")


# ---------------------------------------------------------------------------
# Modelos de equipamento
# ---------------------------------------------------------------------------


@exige_operador
def modelo_lista(request):
    modelos = ModeloEquipamento.objects.order_by("nome")
    linhas = [
        {"modelo": modelo, "bloqueado": modelo.tem_movimentacao()}
        for modelo in modelos
    ]
    return render(request, "iscas/modelo_lista.html", {"linhas": linhas})


@exige_operador
def modelo_criar(request):
    if request.method == "POST":
        form = ModeloForm(request.POST)
        if form.is_valid():
            modelo = form.save()
            messages.success(request, f"Modelo {modelo} cadastrado.")
            return redirect("iscas:modelo_lista")
    else:
        form = ModeloForm()
    return render(
        request, "iscas/modelo_form.html", {"form": form, "titulo": "Novo modelo"}
    )


@exige_operador
def modelo_editar(request, pk):
    modelo = get_object_or_404(ModeloEquipamento.todos, pk=pk)
    if request.method == "POST":
        form = ModeloForm(request.POST, instance=modelo)
        if form.is_valid():
            try:
                cadastro_service.alterar_modelo(
                    modelo,
                    tipo=form.cleaned_data.get("tipo"),
                    nome=form.cleaned_data["nome"],
                    codigo=form.cleaned_data["codigo"],
                    fabricante=form.cleaned_data["fabricante"],
                    descricao=form.cleaned_data["descricao"],
                )
            except IscasError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Modelo atualizado.")
                return redirect("iscas:modelo_lista")
    else:
        form = ModeloForm(instance=modelo)
    return render(
        request,
        "iscas/modelo_form.html",
        {"form": form, "modelo": modelo, "titulo": f"Editar {modelo}"},
    )


@exige_operador
@require_POST
def modelo_desativar(request, pk):
    modelo = get_object_or_404(ModeloEquipamento.todos, pk=pk)
    modelo.desativar()
    messages.success(request, f"Modelo {modelo} desativado.")
    return redirect("iscas:modelo_lista")
