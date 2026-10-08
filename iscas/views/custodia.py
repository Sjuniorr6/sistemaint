"""Views de estoque: entrada, transferência, baixa, manutenção e retornáveis."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from iscas.enums import SITUACOES_TERMINAIS, SituacaoUnidade, TipoModelo
from iscas.forms import (
    BaixaForm,
    EntradaLoteForm,
    EstornoForm,
    ManutencaoForm,
    RetornoForm,
    RetornoManutencaoForm,
    TransferenciaForm,
)
from iscas.models.cadastro import Agente, Deposito, ModeloEquipamento
from iscas.models.config import ConfiguracaoIscas
from iscas.models.custodia import Movimentacao, Unidade
from iscas.enums import Capacidade
from iscas.permissions import exige
from iscas.selectors import historico_unidade, unidades_filtradas, unidades_por_custodia
from iscas.services import baixa as baixa_service
from iscas.services import entrada as entrada_service
from iscas.services import estorno as estorno_service
from iscas.services import retorno as retorno_service
from iscas.services import transferencia as transferencia_service
from iscas.services.exceptions import IscasError
from iscas.services.exportacao import saldo_agentes_xlsx
from iscas.services.saldo import anexar_identificadores, saldo_por_modelo_em_lote


#: Teto das unidades listadas ao abrir um grupo. Custódia com mais que isso
#: (um depósito central, por exemplo) mostra o começo e manda filtrar.
_LIMITE_DO_GRUPO = 500


@exige(Capacidade.VER_ESTOQUE)
def unidade_lista(request):
    """Unidades agrupadas por quem está com elas (ISC-ADR-07).

    Três modos na mesma rota:
    - padrão: uma linha por custódia (agente, depósito, cliente…), com a
      contagem por situação; as unidades não vêm junto;
    - `?custodia=<id>` via HTMX: as unidades daquele grupo, ao abri-lo;
    - `?q=<id>`: busca por identificador, lista plana e paginada.
    """
    modelo_id = request.GET.get("modelo") or None
    situacao = request.GET.get("situacao") or None
    identificador = request.GET.get("q", "").strip() or None
    encerradas = request.GET.get("encerradas") == "1"
    filtros = {
        "modelo": modelo_id, "situacao": situacao,
        "q": identificador or "", "encerradas": encerradas,
    }

    custodia_id = request.GET.get("custodia", "")
    if custodia_id.isdigit():
        unidades = unidades_filtradas(
            modelo=modelo_id, situacao=situacao, custodia=int(custodia_id)
        )
        if not situacao and not encerradas:
            unidades = unidades.exclude(situacao__in=SITUACOES_TERMINAIS)
        lista = list(unidades[: _LIMITE_DO_GRUPO + 1])
        return render(request, "iscas/_unidades_do_grupo.html", {
            "unidades": lista[:_LIMITE_DO_GRUPO],
            "cortado": len(lista) > _LIMITE_DO_GRUPO,
            "limite": _LIMITE_DO_GRUPO,
        })

    contexto = {
        "modelos": ModeloEquipamento.objects.order_by("nome"),
        "situacoes": SituacaoUnidade.choices,
        "filtros": filtros,
    }
    if identificador:
        unidades = unidades_filtradas(
            modelo=modelo_id, situacao=situacao, identificador=identificador
        )
        contexto["pagina"] = Paginator(unidades, 50).get_page(request.GET.get("page"))
    else:
        contexto.update(unidades_por_custodia(
            modelo=modelo_id, situacao=situacao, incluir_encerradas=encerradas,
        ))
    return render(request, "iscas/unidade_lista.html", contexto)


@exige(Capacidade.VER_ESTOQUE)
def unidade_detalhe(request, identificador):
    """Onde a unidade está e por onde passou (ISC-RF-10)."""
    unidade = get_object_or_404(
        Unidade.objects.com_situacao().select_related("modelo", "custodia_atual"),
        identificador=identificador,
    )
    return render(
        request,
        "iscas/unidade_detalhe.html",
        {
            "unidade": unidade,
            "historico": historico_unidade(unidade),
            "reservas": unidade.reservas.select_related(
                "atribuicao__solicitacao__cliente", "atribuicao__agente"
            ).order_by("-reservada_em"),
        },
    )


@exige(Capacidade.MOVIMENTAR_ESTOQUE)
def entrada(request):
    """Entrada de unidades novas, em lote (ISC-RF-07, ISC-RF-08)."""
    if request.method == "POST":
        form = EntradaLoteForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            try:
                movimentacao, unidades = entrada_service.registrar_entrada(
                    modelo=dados["modelo"],
                    identificadores=dados["lista_identificadores"],
                    destino=dados["destino"],
                    autor=request.user,
                    ocorrido_em=dados.get("ocorrido_em"),
                    nota_fiscal=dados.get("nota_fiscal", ""),
                    lote=dados.get("lote", ""),
                    gerar_internos=dados["gerar_internos"],
                    quantidade=dados.get("quantidade"),
                )
            except IscasError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"{len(unidades)} unidade(s) de {dados['modelo']} deram "
                    f"entrada em {dados['destino']}.",
                )
                return redirect("iscas:unidade_lista")
    else:
        form = EntradaLoteForm()
    return render(
        request,
        "iscas/entrada_form.html",
        # Sem depósito o dropdown de destino fica vazio e o operador não
        # entende por quê — a tela avisa e oferece o cadastro.
        {"form": form, "tem_deposito": Deposito.objects.exists()},
    )


@exige(Capacidade.MOVIMENTAR_ESTOQUE)
def transferencia(request):
    """Transferência entre custódias internas (ISC-RF-11)."""
    if request.method == "POST":
        form = TransferenciaForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            unidades = dados["lista_unidades"]
            try:
                transferencia_service.transferir(
                    origem=dados["origem"],
                    destino=dados["destino"],
                    autor=request.user,
                    unidades=unidades,
                    justificativa=dados.get("justificativa", ""),
                )
            except IscasError as exc:
                messages.error(request, str(exc))
            else:
                identificadores = ", ".join(u.identificador for u in unidades[:5])
                if len(unidades) > 5:
                    identificadores += f" e mais {len(unidades) - 5}"
                messages.success(
                    request,
                    f"{len(unidades)} unidade(s) transferida(s) de "
                    f"{dados['origem']} para {dados['destino']}: {identificadores}.",
                )
                return redirect("iscas:painel_saldo")
        else:
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
    else:
        form = TransferenciaForm()
    return render(request, "iscas/transferencia_form.html", {"form": form})


@exige(Capacidade.BAIXAR_MANUTENCAO)
def baixa(request):
    """Baixa por perda, avaria ou obsolescência (ISC-RF-12)."""
    if request.method == "POST":
        form = BaixaForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            unidades = dados["lista_unidades"]
            try:
                baixa_service.dar_baixa(
                    origem=dados["origem"],
                    motivo=dados["motivo"],
                    justificativa=dados["justificativa"],
                    autor=request.user,
                    unidades=unidades,
                )
            except IscasError as exc:
                messages.error(request, str(exc))
            else:
                identificadores = ", ".join(u.identificador for u in unidades[:5])
                if len(unidades) > 5:
                    identificadores += f" e mais {len(unidades) - 5}"
                messages.success(
                    request,
                    f"Baixa de {len(unidades)} unidade(s) registrada: {identificadores}.",
                )
                return redirect("iscas:unidade_lista")
        else:
            # Erros de campo viram mensagem: o form é remontado vazio no
            # redirect, então o operador precisa saber o que houve.
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
    else:
        form = BaixaForm()
    return render(request, "iscas/baixa_form.html", {"form": form})


@exige(Capacidade.BAIXAR_MANUTENCAO)
def manutencao(request):
    """Envio para manutenção (ISC-RF-13). Não é baixa (ISC-RN-14)."""
    if request.method == "POST":
        form = ManutencaoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            unidades = dados["lista_unidades"]
            try:
                transferencia_service.enviar_para_manutencao(
                    origem=dados["origem"],
                    autor=request.user,
                    unidades=unidades,
                    justificativa=dados.get("justificativa", ""),
                )
            except IscasError as exc:
                messages.error(request, str(exc))
            else:
                identificadores = ", ".join(u.identificador for u in unidades[:5])
                if len(unidades) > 5:
                    identificadores += f" e mais {len(unidades) - 5}"
                messages.success(
                    request,
                    f"{len(unidades)} unidade(s) enviada(s) para manutenção: "
                    f"{identificadores}.",
                )
                return redirect("iscas:unidade_lista")
        else:
            # O form é remontado vazio no redirect: o erro precisa virar
            # mensagem, senão o operador não sabe o que houve.
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
    else:
        form = ManutencaoForm()
    return render(request, "iscas/manutencao_form.html", {"form": form})


@exige(Capacidade.BAIXAR_MANUTENCAO)
def manutencao_retorno(request):
    """Retorno da manutenção ao estoque (ISC-RF-13)."""
    if request.method == "POST":
        form = RetornoManutencaoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            unidades = dados["lista_unidades"]
            try:
                transferencia_service.retornar_de_manutencao(
                    unidades=unidades,
                    destino=dados["destino"],
                    autor=request.user,
                    justificativa=dados.get("justificativa", ""),
                )
            except IscasError as exc:
                messages.error(request, str(exc))
            else:
                identificadores = ", ".join(u.identificador for u in unidades[:5])
                if len(unidades) > 5:
                    identificadores += f" e mais {len(unidades) - 5}"
                messages.success(
                    request,
                    f"{len(unidades)} unidade(s) retornaram da manutenção para "
                    f"{dados['destino']}: {identificadores}.",
                )
                return redirect("iscas:unidade_lista")
        else:
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
    else:
        form = RetornoManutencaoForm()

    em_manutencao = unidades_filtradas(situacao=SituacaoUnidade.EM_MANUTENCAO)
    return render(
        request,
        "iscas/manutencao_retorno_form.html",
        {"form": form, "em_manutencao": em_manutencao},
    )


@exige(Capacidade.MOVIMENTAR_ESTOQUE)
@require_POST
def estornar(request, pk):
    """Estorno de lançamento (ISC-RF-14, ISC-ADR-16)."""
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    form = EstornoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Informe a justificativa do estorno.")
        return redirect("iscas:extrato")

    try:
        estorno_service.estornar(
            movimentacao=movimentacao,
            autor=request.user,
            justificativa=form.cleaned_data["justificativa"],
        )
    except IscasError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"Movimentação #{movimentacao.pk} estornada. O lançamento original "
            "permanece no histórico.",
        )
    return redirect("iscas:extrato")


def _blocos_de_saldo(entidades, saldos_por_custodia):
    """Monta a linha da tela para cada entidade, já com os totais.

    Os totais vêm somados aqui, e não no template: `{% for %}` com soma à mão
    em template é onde some a diferença entre "total" e "disponível".
    """
    blocos = []
    for entidade in entidades:
        # `custodia` é OneToOne com related_name='custodia'; o `select_related`
        # de quem chama já trouxe, então isto não vai ao banco.
        conta = getattr(entidade, "custodia", None)
        saldos = saldos_por_custodia.get(conta.pk, []) if conta else []
        blocos.append(
            {
                "entidade": entidade,
                "saldos": saldos,
                "total": sum(s["total"] for s in saldos),
                "disponivel": sum(s["disponivel"] for s in saldos),
                "reservado": sum(s["reservado"] for s in saldos),
                "modelos": len(saldos),
            }
        )
    return blocos


@exige(Capacidade.VER_ESTOQUE)
def painel_saldo(request):
    """Saldo por custódia e por modelo (ISC-RF-15).

    A tela mostra uma linha por depósito/agente com os totais; o detalhe por
    modelo abre sob demanda. Antes eram duas tabelas com uma linha por
    (custódia × modelo) — com 40 agentes e 6 modelos, 240 linhas de números
    onde não dava para achar quem tem saldo de quê.
    """
    busca = (request.GET.get("q") or "").strip()
    # `sem_saldo=1` mostra também quem está zerado. O padrão é esconder: numa
    # tela de saldo, quem tem zero é ruído — mas precisa ser alcançável, senão
    # o operador acha que o agente sumiu do cadastro.
    mostrar_zerados = request.GET.get("sem_saldo") == "1"

    depositos_qs = Deposito.objects.select_related("custodia").order_by("nome")
    agentes_qs = Agente.objects.select_related("custodia").order_by("nome")
    if busca:
        depositos_qs = depositos_qs.filter(nome__icontains=busca)
        agentes_qs = agentes_qs.filter(nome__icontains=busca)

    depositos_lista = list(depositos_qs)
    agentes_lista = list(agentes_qs)

    # Uma consulta para o saldo de TODAS as custódias das duas listas.
    contas = [
        e.custodia
        for e in (*depositos_lista, *agentes_lista)
        if getattr(e, "custodia", None)
    ]
    saldos_por_custodia = anexar_identificadores(
        contas, saldo_por_modelo_em_lote(contas)
    )

    depositos = _blocos_de_saldo(depositos_lista, saldos_por_custodia)
    agentes = _blocos_de_saldo(agentes_lista, saldos_por_custodia)

    if not mostrar_zerados:
        zerados = sum(1 for b in (*depositos, *agentes) if not b["total"])
        depositos = [b for b in depositos if b["total"]]
        agentes = [b for b in agentes if b["total"]]
    else:
        zerados = 0

    return render(
        request,
        "iscas/painel_saldo.html",
        {
            # Um só bloco de template serve os dois grupos: duplicar a tabela
            # era o que fazia depósitos e agentes divergirem com o tempo.
            "grupos": [
                {
                    "titulo": "Depósitos",
                    "rotulo": "Depósito",
                    "icone": "bi-building",
                    "prefixo": "dep",
                    "url_nome": None,
                    "blocos": depositos,
                    "vazio": "Nenhum depósito com estoque.",
                },
                {
                    "titulo": "Agentes",
                    "rotulo": "Agente",
                    "icone": "bi-person-badge",
                    "prefixo": "age",
                    "url_nome": "iscas:agente_detalhe",
                    "blocos": agentes,
                    "vazio": "Nenhum agente com estoque.",
                },
            ],
            "depositos": depositos,
            "agentes": agentes,
            "busca": busca,
            "mostrar_zerados": mostrar_zerados,
            "zerados": zerados,
            "total_geral": {
                "total": sum(b["total"] for b in (*depositos, *agentes)),
                "disponivel": sum(b["disponivel"] for b in (*depositos, *agentes)),
                "reservado": sum(b["reservado"] for b in (*depositos, *agentes)),
            },
        },
    )


@exige(Capacidade.VER_ESTOQUE)
def retornaveis(request):
    """Devolução: o operador digita os IDs das iscas que o cliente devolveu."""
    return render(request, "iscas/retornaveis.html", {"form": RetornoForm()})


@exige(Capacidade.BAIXAR_MANUTENCAO)
@require_POST
def registrar_retorno(request):
    """Devolução de iscas do cliente para depósito ou agente (ISC-RF-32)."""
    form = RetornoForm(request.POST)
    if not form.is_valid():
        for erro in form.errors.values():
            messages.error(request, "; ".join(erro))
        return redirect("iscas:retornaveis")

    dados = form.cleaned_data
    try:
        retorno_service.registrar_devolucao(
            unidades=dados["ids_unidades"],
            destino=dados["destino"],
            motivo=dados["motivo"],
            autor=request.user,
        )
    except IscasError as exc:
        messages.error(request, str(exc))
    else:
        total = len(set(dados["ids_unidades"]))
        messages.success(
            request, f"{total} isca(s) devolvida(s) para {dados['destino']}."
        )
    return redirect("iscas:retornaveis")


@exige(Capacidade.VER_ESTOQUE)
def saldo_excel(request):
    """Iscas com agentes, por região, em Excel — respeita a busca da tela."""
    conteudo = saldo_agentes_xlsx(busca=(request.GET.get("q") or "").strip())
    nome = f"iscas_com_agentes_{timezone.localdate():%Y-%m-%d}.xlsx"
    resposta = HttpResponse(
        conteudo,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta
