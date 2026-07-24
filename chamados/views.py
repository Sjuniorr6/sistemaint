"""Views finas do app Chamados: orquestram form → service e renderizam.

Nenhuma view muda status direto (ADR-004) — toda transição passa por
`services.executar`. A UI só reflete o que o backend autoriza (RN-18): as ações
por linha vêm de `selectors.acoes_disponiveis`, mas a autorização real é imposta
no service. Acesso barrado na URL por @exige_operador (fila/detalhe/ações) e
@exige_quality (abertura, RN-01): anônimo cai no login, não-operador leva 403.
"""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from chamados.enums import Acao, Setor
from chamados.forms import (
    AberturaChamadoForm,
    ContatoExpedicaoForm,
    EncaminharComercialForm,
    EncaminharExpedicaoForm,
    EncaminharForm,
    FaturarForm,
    FinalizarComercialForm,
    FinalizarForm,
    MotivoForm,
)
from chamados.permissions import exige_operador, exige_quality, is_quality
from chamados.selectors import (
    acoes_disponiveis,
    chamados_visiveis_para,
    metricas_painel,
)
from chamados import services

# Ação → (form, chaves de dados que o form entrega ao service).
_FORM_POR_ACAO = {
    Acao.ENCAMINHAR: (EncaminharForm, ("procedimento_realizado", "tratativa", "responsavel_inteligencia")),
    Acao.ENCAMINHAR_EXPEDICAO: (EncaminharExpedicaoForm, ("procedimento_realizado", "tratativa")),
    # Marcar chegada não coleta dados: só registra a transição EXPEDICAO→LABORATORIO.
    Acao.MARCAR_CHEGADA: (None, ()),
    # ENCAMINHAR_COMERCIAL é tratado à parte (form dinâmico por equipamento).
    Acao.FATURAR: (FaturarForm, ("valor_faturamento", "nota_fiscal")),
    Acao.FINALIZAR: (FinalizarForm, ("procedimento_realizado",)),
    Acao.RESOLVER: (FinalizarForm, ("procedimento_realizado",)),
    Acao.BLOQUEAR: (MotivoForm, ("motivo",)),
    Acao.REABRIR: (MotivoForm, ("motivo",)),
}


def _linhas_com_acoes(user, chamados):
    """Emparelha cada chamado com as ações que a UI deve oferecer (RF-07)."""
    return [
        {"chamado": c, "acoes": acoes_disponiveis(user, c)} for c in chamados
    ]


@exige_operador
def fila(request):
    """Tela ÚNICA de chamados + painel de indicadores (RF-07, RF-08).

    Todos os papéis usam esta mesma tela; cada um vê um conjunto diferente,
    definido em `chamados_visiveis_para`:
      - Quality/superuser: todos os chamados, em qualquer status;
      - Inteligência: só os encaminhados a ela (responsavel_inteligencia);
      - Expedição/Laboratório/Comercial: só os que estão no SEU status atual
        (EXPEDICAO/LABORATORIO/COMERCIAL) — ao agir, o chamado muda de status e
        sai da visão do grupo.
    """
    chamados = chamados_visiveis_para(request.user)
    contexto = {
        "linhas": _linhas_com_acoes(request.user, chamados),
        "metricas": metricas_painel(),
        "pode_abrir": is_quality(request.user),
        "Acao": Acao,
    }
    return render(request, "chamados/fila.html", contexto)


@exige_operador
def detalhe(request, pk):
    """Detalhe do chamado com histórico completo de transições (RF-10).

    Busca dentro do queryset VISÍVEL ao usuário: inteligência que tenta abrir um
    chamado que não é dele recebe 404 (o recurso não existe para ele), fechando
    o acesso por URL direta, não só na fila.
    """
    chamado = get_object_or_404(chamados_visiveis_para(request.user), pk=pk)
    eventos = chamado.eventos.select_related("autor", "responsavel_inteligencia").all()
    contexto = {
        "chamado": chamado,
        "eventos": eventos,
        # Procedimento/tratativa POR SETOR — derivados do log (os campos do
        # chamado são únicos e sobrescritos a cada encaminhamento; a fonte fiel
        # de "quem escreveu o quê" são os snapshots dos eventos).
        "tratativas_por_setor": _tratativas_por_setor(eventos),
        "acoes": acoes_disponiveis(request.user, chamado),
        "Acao": Acao,
        # Só para o dropdown de responsável do modal Encaminhar (RF-05); a
        # validação real do POST acontece no EncaminharForm de acao().
        "encaminhar_form": EncaminharForm(),
        # Form dinâmico do modal "Encaminhar p/ comercial": um campo de tratativa
        # por equipamento do chamado.
        "comercial_form": EncaminharComercialForm(
            equipamentos=services.equipamentos_do_chamado(chamado)
        ),
        # Form dinâmico do modal "Finalizar chamado" (comercial): tratativa + custo
        # por equipamento.
        "finalizar_comercial_form": FinalizarComercialForm(
            equipamentos=services.equipamentos_do_chamado(chamado)
        ),
        # Modal "Faturado" (Financeiro): valor + NF.
        "faturar_form": FaturarForm(),
        "tratativas_equipamento": chamado.tratativas_equipamento.all(),
        # Tentativas de contato da Expedição — visíveis da expedição em diante.
        "contato_form": ContatoExpedicaoForm(),
        "contatos_expedicao": chamado.contatos_expedicao.select_related(
            "registrado_por"
        ).all(),
        # Laudo da manutenção vinculada: liberado a partir do momento em que o
        # Comercial ACEITA a tratativa (o chamado já chegou nele com a manutenção
        # vinculada pelo laboratório). Segue disponível depois de resolvido.
        "pode_baixar_laudo": _pode_baixar_laudo(chamado),
    }
    return render(request, "chamados/detalhe.html", contexto)


# Ação que gravou procedimento/tratativa → setor que a executou. ABRIR entra
# porque no "abrir já encaminhado" (RN-08) o Quality preenche tudo na abertura
# (não há ENCAMINHAR separado); no fluxo normal o ABRIR não tem snapshots e é
# filtrado, ficando só o ENCAMINHAR.
_SETOR_DA_ACAO = {
    Acao.ABRIR: "Quality",
    Acao.ENCAMINHAR: "Quality",
    Acao.ENCAMINHAR_EXPEDICAO: "Inteligência",
}


def _tratativas_por_setor(eventos):
    """Procedimento + tratativa de cada setor, reconstruídos do log de eventos.

    Só os encaminhamentos que gravam procedimento/tratativa entram (Quality e
    Inteligência); o Comercial tem card próprio (por equipamento). Cada item traz
    o setor, quem fez, quando, e os textos daquela etapa — sem sobrescrever nada.
    """
    itens = []
    for e in eventos:
        setor = _SETOR_DA_ACAO.get(e.acao)
        if setor is None:
            continue
        if not (e.procedimento_snapshot or e.tratativa_snapshot):
            continue
        itens.append({
            "setor": setor,
            "autor": e.autor,
            "em": e.criado_em,
            "procedimento": e.procedimento_snapshot,
            "tratativa": e.tratativa_snapshot,
        })
    return itens


def _pode_baixar_laudo(chamado) -> bool:
    """True quando o laudo da manutenção vinculada deve ser oferecido.

    Exige: manutenção vinculada (feita pelo laboratório ao encaminhar) e que a
    passagem do Comercial — ou a do Financeiro, que recebe o chamado depois para
    cobrar — já tenha sido ACEITA. Uma vez aceita, o botão continua disponível
    (inclusive depois de RESOLVIDO), pois a passagem permanece registrada.
    """
    if chamado.manutencao_id is None:
        return False
    return chamado.passagens.filter(
        setor__in=(Setor.COMERCIAL, Setor.FINANCEIRO), aceito_em__isnull=False
    ).exists()


@exige_quality
def abrir(request):
    """Abertura de chamado — só Quality (RN-01, RF-01/RF-06).

    O gate de grupo está no decorator (@exige_quality → 403 para não-quality); o
    service reforça a mesma regra (defesa em profundidade, RN-18).
    """
    if request.method == "POST":
        form = AberturaChamadoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            try:
                chamado = services.abrir_chamado(
                    autor=request.user,
                    cliente=dados["cliente"],
                    categoria=dados["categoria"],
                    numero_equipamento=dados["numero_equipamento"],
                    modelo_equipamento=dados["modelo_equipamento"],
                    problema_relatado=dados["problema_relatado"],
                    # Responsável (Quality) é sempre o próprio usuário logado
                    # (Quality, por @exige_quality), nunca vem do POST.
                    responsavel=request.user,
                    contato_nome=dados["contato_nome"],
                    contato_telefone=dados.get("contato_telefone", ""),
                    contato_email=dados.get("contato_email", ""),
                    contato_meio=dados["contato_meio"],
                    encaminhar=dados["encaminhar"],
                    procedimento_realizado=dados.get("procedimento_realizado"),
                    tratativa=dados.get("tratativa"),
                    responsavel_inteligencia=dados.get("responsavel_inteligencia"),
                )
            except ValidationError as exc:
                for campo, erros in (exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}).items():
                    for erro in erros:
                        form.add_error(campo if campo != "__all__" else None, erro)
            else:
                messages.success(request, f"Chamado {chamado.protocolo} aberto.")
                return redirect("chamados:detalhe", pk=chamado.pk)
    else:
        form = AberturaChamadoForm()

    return render(request, "chamados/abrir.html", {"form": form})


@exige_operador
@require_POST
def acao(request, pk, acao):
    """Executa uma ação/transição sobre o chamado (RF-11..RF-17).

    Roteia a ação para o form certo, valida a entrada e delega ao service. A
    posse e a validade da transição são impostas no `services.executar` — a view
    só traduz erros em messages e redireciona ao detalhe. A busca é dentro do
    queryset VISÍVEL (404 se o chamado não é do usuário), fechando o POST direto.
    """
    chamado = get_object_or_404(chamados_visiveis_para(request.user), pk=pk)

    if acao not in Acao.values:
        messages.error(request, "Ação inválida.")
        return redirect("chamados:detalhe", pk=pk)

    # Registro de contato da Expedição: não é transição, só acrescenta histórico.
    if acao == Acao.REGISTRAR_CONTATO:
        form = ContatoExpedicaoForm(request.POST)
        if not form.is_valid():
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
            return redirect("chamados:detalhe", pk=pk)
        try:
            services.registrar_contato(
                chamado, request.user,
                nome_contato=form.cleaned_data["nome_contato"],
                tratativa=form.cleaned_data["tratativa"],
                telefone=form.cleaned_data.get("telefone", ""),
                codigo_rastreio=form.cleaned_data.get("codigo_rastreio", ""),
            )
        except PermissionDenied as exc:
            messages.error(request, str(exc) or "Sem permissão para registrar contato.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "Contato registrado.")
        return redirect("chamados:detalhe", pk=pk)

    # Aceite não é transição de estado: só carimba o início da tratativa (SLA).
    if acao == Acao.ACEITAR_TRATATIVA:
        try:
            services.aceitar_tratativa(chamado, request.user)
        except PermissionDenied as exc:
            messages.error(request, str(exc) or "Sem permissão para aceitar.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "Tratativa aceita.")
        return redirect("chamados:detalhe", pk=pk)

    dados = {}
    if acao == Acao.ENCAMINHAR_COMERCIAL:
        # Form dinâmico: uma tratativa por equipamento do chamado.
        equipamentos = services.equipamentos_do_chamado(chamado)
        form = EncaminharComercialForm(request.POST, equipamentos=equipamentos)
        if not form.is_valid():
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
            return redirect("chamados:detalhe", pk=pk)
        dados = {
            "tratativas_equipamento": form.tratativas_por_equipamento(),
            "manutencao": form.cleaned_data["manutencao"],
        }
    elif acao == Acao.FINALIZAR_COMERCIAL:
        # Form dinâmico: tratativa + custo por equipamento (+ termo em PDF quando
        # houver equipamento com custo — por isso request.FILES aqui).
        equipamentos = services.equipamentos_do_chamado(chamado)
        form = FinalizarComercialForm(
            request.POST, request.FILES, equipamentos=equipamentos
        )
        if not form.is_valid():
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
            return redirect("chamados:detalhe", pk=pk)
        dados = {
            "finalizacao_equipamento": form.finalizacao_por_equipamento(),
            "termo_substituicao": form.cleaned_data.get("termo_substituicao"),
        }
    else:
        form_cls, chaves = _FORM_POR_ACAO[acao]
        if form_cls is not None:
            form = form_cls(request.POST)
            if not form.is_valid():
                for erros in form.errors.values():
                    for erro in erros:
                        messages.error(request, erro)
                return redirect("chamados:detalhe", pk=pk)
            dados = {chave: form.cleaned_data[chave] for chave in chaves}

    try:
        services.executar(chamado, acao, dados, request.user)
    except PermissionDenied as exc:
        messages.error(request, str(exc) or "Sem permissão para esta ação.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, f"Ação '{Acao(acao).label}' aplicada.")
        # Ações que "passam a bola" (encaminhar, marcar chegada) tiram o chamado
        # da visibilidade de quem agiu — ex.: expedição deixa de ver após marcar
        # chegada. Nesse caso, ir ao detalhe daria 404; volta-se para a fila.
        if not chamados_visiveis_para(request.user).filter(pk=pk).exists():
            return redirect("chamados:fila")

    return redirect("chamados:detalhe", pk=pk)
