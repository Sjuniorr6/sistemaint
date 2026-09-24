"""Views de cadastro: Agente, Cliente e Modelo."""
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django.db import IntegrityError

from iscas.forms import AgenteForm, ClienteForm, DepositoForm, ModeloForm
from iscas.forms.cadastro import DestinatarioNotificacaoForm
from iscas.models.config import DestinatarioNotificacao
from iscas.models.cadastro import Agente, Cliente, Deposito, ModeloEquipamento
from iscas.models.config import ConfiguracaoIscas
from iscas.models.custodia import Unidade
from iscas.enums import Capacidade
from iscas.permissions import exige
from iscas.selectors import historico_agente as historico_agente_selector
from iscas.services import cadastro as cadastro_service
from iscas.services.exceptions import AgenteComSaldo, DepositoComSaldo, IscasError
from iscas.services.geo import ajustar_pin
from iscas.services.saldo import saldo_por_modelo_em_lote


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


@exige(Capacidade.CADASTRAR_AGENTE)
def agente_lista(request):
    """Listagem com CPF mascarado (ISC-RN-16) e alerta de pin pendente.

    Desativados ficam fora por padrão; a lixeira é um modo explícito da tela,
    como na lista de modelos. Sem ela o agente desativado seria inalcançável —
    some do `ActiveManager` e não haveria como reativá-lo pela interface.
    """
    busca = request.GET.get("q", "").strip()
    desativados = request.GET.get("desativados") == "1"

    # `select_related("custodia")`: a conta de cada agente é lida no loop
    # abaixo para montar o lote de saldos. Sem isto, cada acesso a
    # `agente.custodia` seria uma consulta — o N+1 voltaria pela porta dos
    # fundos, agora buscando custódia em vez de saldo.
    agentes = (
        Agente.todos.filter(is_active=False) if desativados else Agente.objects.all()
    ).select_related("custodia").order_by("nome")
    if busca:
        agentes = agentes.filter(nome__icontains=busca)

    agentes = list(agentes)

    # UMA consulta agrega o saldo de todos os agentes da página. Antes, o
    # `saldo_por_modelo()` era chamado dentro do laço: três consultas por
    # agente, degradando exatamente conforme a operação cresce — que é quando
    # a tela mais importa.
    contas = [a.custodia for a in agentes if getattr(a, "custodia", None)]
    saldos_por_custodia = saldo_por_modelo_em_lote(contas)

    linhas = [
        {
            "agente": agente,
            "cpf": agente.cpf_mascarado,
            "saldos": saldos_por_custodia.get(
                getattr(agente.custodia, "pk", None), []
            ) if getattr(agente, "custodia", None) else [],
        }
        for agente in agentes
    ]
    return render(
        request,
        "iscas/agente_lista.html",
        {
            "linhas": linhas,
            "busca": busca,
            "desativados": desativados,
            "total_desativados": Agente.todos.filter(is_active=False).count(),
        },
    )


@exige(Capacidade.CADASTRAR_AGENTE)
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


@exige(Capacidade.CADASTRAR_AGENTE)
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


@exige(Capacidade.CADASTRAR_AGENTE)
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


@exige(Capacidade.DESATIVAR_CADASTRO)
@require_POST
def agente_desativar(request, pk):
    """Desativação bloqueada se o agente ainda segura equipamento (ISC-RN-18)."""
    agente = get_object_or_404(Agente.todos, pk=pk)
    try:
        cadastro_service.desativar_agente(agente)
    except AgenteComSaldo as exc:
        messages.error(request, str(exc))
        return redirect("iscas:agente_detalhe", pk=agente.pk)
    messages.success(
        request,
        f"Agente {agente.nome} desativado. Ele sai das listas e da busca por "
        "proximidade; o histórico e as movimentações dele permanecem.",
    )
    return redirect("iscas:agente_lista")


@exige(Capacidade.DESATIVAR_CADASTRO)
@require_POST
def agente_reativar(request, pk):
    """Devolve o agente à operação.

    Contraparte obrigatória do soft-delete: desativação sem volta é deleção com
    passos extras, e o operador que errou o clique ficaria sem saída no app.
    """
    agente = get_object_or_404(Agente.todos, pk=pk)
    cadastro_service.reativar_agente(agente)
    messages.success(request, f"Agente {agente.nome} reativado.")
    return redirect("iscas:agente_detalhe", pk=agente.pk)


@exige(Capacidade.CADASTRAR_AGENTE)
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


@exige(Capacidade.CADASTRAR_CLIENTE)
def cliente_lista(request):
    busca = request.GET.get("q", "").strip()
    clientes = Cliente.objects.order_by("nome_razao_social")
    if busca:
        clientes = clientes.filter(nome_razao_social__icontains=busca)
    return render(
        request, "iscas/cliente_lista.html", {"clientes": clientes, "busca": busca}
    )


@exige(Capacidade.CADASTRAR_CLIENTE)
def cliente_detalhe(request, pk):
    from iscas.selectors import historico_cliente

    cliente = get_object_or_404(Cliente.todos, pk=pk)
    contexto = historico_cliente(cliente)
    contexto["config"] = ConfiguracaoIscas.carregar()
    return render(request, "iscas/cliente_detalhe.html", contexto)


@exige(Capacidade.CADASTRAR_CLIENTE)
def cliente_criar(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cadastro_service.salvar_com_geocodificacao(
                cliente, endereco_mudou=True, pin=form.pin_ajustado()
            )
            if cliente.tem_coordenada or not cliente.tem_endereco:
                # Sem endereço não há coordenada a cobrar: o endereço do
                # cliente é opcional, e cada solicitação traz o próprio ponto
                # de entrega. Avisar aqui seria alarme sobre algo correto.
                messages.success(request, f"Cliente {cliente} cadastrado.")
            else:
                messages.warning(
                    request,
                    f"Cliente {cliente} cadastrado, mas o endereço não foi "
                    "localizado no mapa. Ajuste o pin para usar este endereço "
                    "como sugestão de entrega.",
                )
            return redirect("iscas:cliente_detalhe", pk=cliente.pk)
    else:
        form = ClienteForm()
    return render(
        request,
        "iscas/cliente_form.html",
        _contexto_endereco(form, titulo="Novo cliente"),
    )


@exige(Capacidade.CADASTRAR_CLIENTE)
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


@exige(Capacidade.DESATIVAR_CADASTRO)
@require_POST
def cliente_desativar(request, pk):
    cliente = get_object_or_404(Cliente.todos, pk=pk)
    cadastro_service.desativar_cliente(cliente)
    messages.success(request, f"Cliente {cliente} desativado.")
    return redirect("iscas:cliente_lista")


@exige(Capacidade.CADASTRAR_CLIENTE)
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


@exige(Capacidade.CADASTRAR_DEPOSITO)
def deposito_lista(request):
    """Pontos de estoque da empresa — de onde o equipamento sai para os agentes.

    Saldo de todos os depósitos numa consulta só. Antes eram DUAS por depósito
    (`saldo_por_modelo` + `tem_saldo`), e `tem_saldo` nem precisa ir ao banco:
    é derivável do próprio lote.
    """
    depositos_lista = list(
        Deposito.objects.select_related("custodia").order_by("nome")
    )
    contas = [d.custodia for d in depositos_lista if getattr(d, "custodia", None)]
    saldos_por_custodia = saldo_por_modelo_em_lote(contas)

    depositos = []
    for deposito in depositos_lista:
        conta = getattr(deposito, "custodia", None)
        saldos = saldos_por_custodia.get(conta.pk, []) if conta else []
        depositos.append(
            {
                "deposito": deposito,
                "saldos": saldos,
                # Derivado do lote: depósito com qualquer linha de saldo tem
                # unidade em custódia. Uma consulta a menos por linha.
                "tem_saldo": any(linha["total"] for linha in saldos),
            }
        )
    return render(request, "iscas/deposito_lista.html", {"linhas": depositos})


@exige(Capacidade.CADASTRAR_DEPOSITO)
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


@exige(Capacidade.CADASTRAR_DEPOSITO)
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


@exige(Capacidade.DESATIVAR_CADASTRO)
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


@exige(Capacidade.CADASTRAR_MODELO)
def modelo_lista(request):
    """Catálogo de modelos. Desativados ficam fora por padrão (ISC-RN-20).

    A lixeira é um modo explícito da tela, como na lista de solicitações: o
    operador precisa enxergar o que desativou para poder reativar, mas não no
    caminho de quem só quer o catálogo em uso.
    """
    desativados = request.GET.get("desativados") == "1"
    modelos = (
        ModeloEquipamento.todos.filter(is_active=False)
        if desativados
        else ModeloEquipamento.objects.all()
    ).order_by("nome")

    linhas = [
        {"modelo": modelo, "bloqueado": modelo.tem_movimentacao()}
        for modelo in modelos
    ]
    return render(
        request,
        "iscas/modelo_lista.html",
        {
            "linhas": linhas,
            "desativados": desativados,
            "total_desativados": ModeloEquipamento.todos.filter(
                is_active=False
            ).count(),
        },
    )


@exige(Capacidade.CADASTRAR_MODELO)
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


@exige(Capacidade.CADASTRAR_MODELO)
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


@exige(Capacidade.DESATIVAR_CADASTRO)
@require_POST
def modelo_desativar(request, pk):
    """Soft-delete: sai do catálogo, o estoque existente continua (ISC-RN-20)."""
    modelo = get_object_or_404(ModeloEquipamento.todos, pk=pk)
    cadastro_service.desativar_modelo(modelo)

    # O aviso muda conforme haja estoque: dizer só "desativado" deixaria o
    # operador em dúvida sobre o que aconteceu com as unidades que existem.
    em_estoque = Unidade.objects.filter(modelo=modelo).count()
    if em_estoque:
        messages.success(
            request,
            f"Modelo {modelo} desativado. Ele não aceita mais unidades novas; "
            f"as {em_estoque} unidade(s) já cadastradas seguem no estoque e no "
            "histórico.",
        )
    else:
        messages.success(request, f"Modelo {modelo} desativado.")
    return redirect("iscas:modelo_lista")


@exige(Capacidade.DESATIVAR_CADASTRO)
@require_POST
def modelo_reativar(request, pk):
    """Devolve o modelo ao catálogo."""
    modelo = get_object_or_404(ModeloEquipamento.todos, pk=pk)
    cadastro_service.reativar_modelo(modelo)
    messages.success(request, f"Modelo {modelo} reativado.")
    return redirect("iscas:modelo_lista")


# — Destinatários de notificação —


@exige(Capacidade.CADASTRAR_NOTIFICACAO)
def notificacao_lista(request):
    """Quem recebe o e-mail de encerramento de solicitação."""
    desativados = request.GET.get("desativados") == "1"
    destinatarios = (
        DestinatarioNotificacao.todos.filter(is_active=False)
        if desativados
        else DestinatarioNotificacao.objects.all()
    )
    return render(
        request,
        "iscas/notificacao_lista.html",
        {
            "destinatarios": destinatarios,
            "desativados": desativados,
            "total_desativados": DestinatarioNotificacao.todos.filter(
                is_active=False
            ).count(),
        },
    )


@exige(Capacidade.CADASTRAR_NOTIFICACAO)
def notificacao_criar(request):
    if request.method == "POST":
        form = DestinatarioNotificacaoForm(request.POST)
        if form.is_valid():
            try:
                destinatario = form.save()
            except IntegrityError:
                # O `unique` do banco é alheio a `is_active`: o endereço pode
                # existir desativado, e aí o caminho é reativar, não recriar.
                messages.error(
                    request,
                    "Este e-mail já está cadastrado. Se não aparece na lista, "
                    "procure entre os desativados e reative.",
                )
            else:
                messages.success(request, f"{destinatario.email} vai receber as notificações.")
                return redirect("iscas:notificacao_lista")
    else:
        form = DestinatarioNotificacaoForm()
    return render(
        request, "iscas/notificacao_form.html",
        {"form": form, "titulo": "Novo destinatário"},
    )


@exige(Capacidade.CADASTRAR_NOTIFICACAO)
def notificacao_editar(request, pk):
    destinatario = get_object_or_404(DestinatarioNotificacao.todos, pk=pk)
    if request.method == "POST":
        form = DestinatarioNotificacaoForm(request.POST, instance=destinatario)
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                messages.error(request, "Este e-mail já está cadastrado.")
            else:
                messages.success(request, "Destinatário atualizado.")
                return redirect("iscas:notificacao_lista")
    else:
        form = DestinatarioNotificacaoForm(instance=destinatario)
    return render(
        request, "iscas/notificacao_form.html",
        {"form": form, "destinatario": destinatario,
         "titulo": f"Editar {destinatario.email}"},
    )


@exige(Capacidade.CADASTRAR_NOTIFICACAO)
@require_POST
def notificacao_desativar(request, pk):
    destinatario = get_object_or_404(DestinatarioNotificacao.todos, pk=pk)
    destinatario.desativar()
    messages.success(request, f"{destinatario.email} não recebe mais as notificações.")
    return redirect("iscas:notificacao_lista")


@exige(Capacidade.CADASTRAR_NOTIFICACAO)
@require_POST
def notificacao_reativar(request, pk):
    destinatario = get_object_or_404(DestinatarioNotificacao.todos, pk=pk)
    destinatario.reativar()
    messages.success(request, f"{destinatario.email} voltou a receber as notificações.")
    return redirect("iscas:notificacao_lista")
