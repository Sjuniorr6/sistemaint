"""Testes do app Chamados (pytest + pytest-django).

Cobre os testes críticos da ARCHITECTURE.md: máquina de estados (transições
válidas/inválidas), imutabilidade dos fatos de abertura, campos obrigatórios por
ação, reabertura derivada do log, fronteira da Inteligência, permissão de
abertura, protocolo por ano, painel derivado do log e atomicidade.
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from acompanhamento.models import Clientes
from produto.models import Produto
from chamados import services
from chamados.enums import Acao, Status
from chamados.models import Chamado, ChamadoEvento
from chamados.selectors import metricas_painel

User = get_user_model()


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture
def grupos(db):
    quality, _ = Group.objects.get_or_create(name="quality")
    inteligencia, _ = Group.objects.get_or_create(name="inteligencia")
    return quality, inteligencia


@pytest.fixture
def user_quality(db, grupos):
    quality, _ = grupos
    u = User.objects.create_user(username="q1", password="x")
    u.groups.add(quality)
    return u


@pytest.fixture
def outro_quality(db, grupos):
    quality, _ = grupos
    u = User.objects.create_user(username="q2", password="x")
    u.groups.add(quality)
    return u


@pytest.fixture
def user_inteligencia(db, grupos):
    _, inteligencia = grupos
    u = User.objects.create_user(username="i1", password="x")
    u.groups.add(inteligencia)
    return u


@pytest.fixture
def outro_inteligencia(db, grupos):
    _, inteligencia = grupos
    u = User.objects.create_user(username="i2", password="x")
    u.groups.add(inteligencia)
    return u


@pytest.fixture
def user_expedicao(db):
    """Usuário do grupo `expedicao` (fila compartilhada). O grupo é criado por
    migration no app real; aqui garantimos sua existência no banco de teste."""
    expedicao, _ = Group.objects.get_or_create(name="expedicao")
    u = User.objects.create_user(username="e1", password="x")
    u.groups.add(expedicao)
    return u


@pytest.fixture
def outro_expedicao(db):
    expedicao, _ = Group.objects.get_or_create(name="expedicao")
    u = User.objects.create_user(username="e2", password="x")
    u.groups.add(expedicao)
    return u


@pytest.fixture
def user_laboratorio(db):
    """Usuário do grupo `laboratorio` (fila compartilhada que recebe as chegadas)."""
    laboratorio, _ = Group.objects.get_or_create(name="laboratorio")
    u = User.objects.create_user(username="l1", password="x")
    u.groups.add(laboratorio)
    return u


@pytest.fixture
def user_comercial(db):
    """Usuário do grupo `COMERCIAL` (maiúsculo — reaproveitado do sistema)."""
    comercial, _ = Group.objects.get_or_create(name="COMERCIAL")
    u = User.objects.create_user(username="c1", password="x")
    u.groups.add(comercial)
    return u


@pytest.fixture
def user_comum(db):
    return User.objects.create_user(username="comum", password="x")


@pytest.fixture
def cliente(db):
    """Cliente do cadastro (acompanhamento.Clientes) usado nas aberturas."""
    return Clientes.objects.create(nome="ACME", endereco="Rua 1", cnpj="00000000000000")


@pytest.fixture
def produto(db):
    """Modelo de equipamento (produto.Produto) usado nas aberturas."""
    return Produto.objects.create(nome="Rastreador GT06")


def _abrir(autor, responsavel, cliente=None, modelo=None, **extra):
    if cliente is None:
        cliente = Clientes.objects.create(
            nome="ACME", endereco="Rua 1", cnpj="00000000000000"
        )
    if modelo is None:
        modelo = Produto.objects.create(nome="Rastreador GT06")
    return services.abrir_chamado(
        autor=autor,
        cliente=cliente,
        categoria="HARDWARE",
        numero_equipamento="EQ-001",
        modelo_equipamento=modelo,
        problema_relatado="Não liga",
        responsavel=responsavel,
        contato_nome="João da Silva",
        contato_telefone="11999998888",
        contato_email="joao@exemplo.com",
        contato_meio="WHATSAPP",
        **extra,
    )


# --------------------------------------------------------------------------- #
# Abertura + protocolo                                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_abertura_cria_chamado_aberto_com_evento_inicial(user_quality):
    chamado = _abrir(user_quality, user_quality)
    assert chamado.status == Status.ABERTO
    assert chamado.aberto_por == user_quality
    assert chamado.aberto_em is not None
    evento = chamado.eventos.get()
    assert evento.acao == Acao.ABRIR
    assert evento.estado_origem is None
    assert evento.estado_destino == Status.ABERTO


@pytest.mark.django_db
def test_abertura_por_nao_quality_e_rejeitada(user_inteligencia, user_quality):
    """RN-01 — usuário fora do grupo quality não abre chamado."""
    with pytest.raises(PermissionDenied):
        _abrir(user_inteligencia, user_quality)


@pytest.mark.django_db
def test_responsavel_deve_ser_quality(user_quality, user_inteligencia):
    """RN-02 — o responsável do chamado deve ser do grupo quality."""
    with pytest.raises(ValidationError):
        _abrir(user_quality, user_inteligencia)


@pytest.mark.django_db
def test_abrir_encaminhado_exige_procedimento_tratativa_e_resp_inteligencia(
    user_quality, user_inteligencia
):
    """RN-08 — abrir já ENCAMINHADO exige os três campos."""
    with pytest.raises(ValidationError):
        _abrir(user_quality, user_quality, encaminhar=True)  # sem os campos

    chamado = _abrir(
        user_quality,
        user_quality,
        encaminhar=True,
        procedimento_realizado="tentei reset",
        tratativa="trocar antena",
        responsavel_inteligencia=user_inteligencia,
    )
    assert chamado.status == Status.ENCAMINHADO
    assert chamado.responsavel_inteligencia == user_inteligencia


@pytest.mark.django_db
def test_protocolo_formato_e_sequencial_por_ano(user_quality):
    """RN-07 — AAAA-NNNNNN; sequencial incrementa dentro do ano."""
    c1 = _abrir(user_quality, user_quality)
    c2 = _abrir(user_quality, user_quality)
    ano = c1.aberto_em.year
    assert c1.protocolo == f"{ano}-000001"
    assert c2.protocolo == f"{ano}-000002"


@pytest.mark.django_db
def test_protocolo_reinicia_no_novo_ano(user_quality, cliente, produto):
    """RN-07 — o sequencial reinicia na virada de ano (protocolos de 2024 não
    contam para 2025)."""
    Chamado.objects.create(
        protocolo="2024-000009",
        cliente=cliente, categoria="OUTROS", numero_equipamento="E",
        modelo_equipamento=produto, problema_relatado="p", responsavel=user_quality,
        contato_nome="Fulano", contato_meio="TELEFONE",
        aberto_por=user_quality, aberto_em=_dt(2024),
    )
    assert services.gerar_protocolo(2025) == "2025-000001"


def _dt(ano):
    from django.utils import timezone
    import datetime

    return timezone.make_aware(datetime.datetime(ano, 6, 1, 12, 0))


# --------------------------------------------------------------------------- #
# Máquina de estados — transições válidas e inválidas (RN-14)                  #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_finalizar_exige_procedimento(user_quality):
    """RN-10 — Finalizar sem procedimento falha; com procedimento, resolve."""
    chamado = _abrir(user_quality, user_quality)
    with pytest.raises(ValidationError):
        services.executar(chamado, Acao.FINALIZAR, {}, user_quality)

    services.executar(
        chamado, Acao.FINALIZAR, {"procedimento_realizado": "trocado"}, user_quality
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO


@pytest.mark.django_db
def test_encaminhar_exige_procedimento_tratativa_e_resp(user_quality, user_inteligencia):
    """RN-09 — Encaminhar exige os três campos."""
    chamado = _abrir(user_quality, user_quality)
    with pytest.raises(ValidationError):
        services.executar(
            chamado, Acao.ENCAMINHAR, {"procedimento_realizado": "x"}, user_quality
        )
    services.executar(
        chamado,
        Acao.ENCAMINHAR,
        {
            "procedimento_realizado": "x",
            "tratativa": "y",
            "responsavel_inteligencia": user_inteligencia,
        },
        user_quality,
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.ENCAMINHADO
    assert chamado.responsavel_inteligencia == user_inteligencia


@pytest.mark.django_db
def test_resolvido_e_terminal(user_quality):
    """RN-13 — RESOLVIDO não tem transição de saída."""
    chamado = _abrir(user_quality, user_quality)
    services.executar(
        chamado, Acao.FINALIZAR, {"procedimento_realizado": "ok"}, user_quality
    )
    chamado.refresh_from_db()
    for acao in (Acao.ENCAMINHAR, Acao.BLOQUEAR, Acao.REABRIR):
        with pytest.raises(ValidationError):
            services.executar(chamado, acao, {"motivo": "m", "procedimento_realizado": "p", "tratativa": "t"}, user_quality)


@pytest.mark.django_db
def test_transicao_invalida_aberto_para_resolver_intel(user_quality, user_inteligencia):
    """ENCAMINHAR→RESOLVER é da Inteligência; ABERTO não sai para RESOLVER via
    RESOLVER (só via FINALIZAR do Quality)."""
    chamado = _abrir(user_quality, user_quality)
    with pytest.raises(ValidationError):
        services.executar(
            chamado, Acao.RESOLVER, {"procedimento_realizado": "x"}, user_inteligencia
        )


# --------------------------------------------------------------------------- #
# Fronteira da Inteligência (RN-16)                                            #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_inteligencia_resolve_encaminhado(user_quality, user_inteligencia):
    chamado = _abrir(
        user_quality, user_quality, encaminhar=True,
        procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=user_inteligencia,
    )
    services.executar(
        chamado, Acao.RESOLVER, {"procedimento_realizado": "resolvido"}, user_inteligencia
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO


@pytest.mark.django_db
def test_inteligencia_nao_pode_agir_em_aberto(user_quality, user_inteligencia):
    """RN-16 — a Inteligência não age em chamado ABERTO (posse do Quality);
    tentar finalizar um ABERTO não é dela."""
    chamado = _abrir(user_quality, user_quality)
    with pytest.raises(PermissionDenied):
        services.executar(
            chamado, Acao.FINALIZAR, {"procedimento_realizado": "x"}, user_inteligencia
        )


@pytest.mark.django_db
def test_quality_nao_age_apos_encaminhar(user_quality, user_inteligencia):
    """RN-17 — após ENCAMINHADO, a posse é da Inteligência; Quality não resolve."""
    chamado = _abrir(
        user_quality, user_quality, encaminhar=True,
        procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=user_inteligencia,
    )
    with pytest.raises(PermissionDenied):
        services.executar(
            chamado, Acao.RESOLVER, {"procedimento_realizado": "x"}, user_quality
        )


# --------------------------------------------------------------------------- #
# Bloqueio e reabertura (RN-11, RN-12) — destino derivado do log (ADR-005)     #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_bloquear_exige_motivo(user_quality):
    chamado = _abrir(user_quality, user_quality)
    with pytest.raises(ValidationError):
        services.executar(chamado, Acao.BLOQUEAR, {}, user_quality)


@pytest.mark.django_db
def test_reabrir_de_aberto_volta_para_aberto(user_quality):
    """RN-12 — bloqueado a partir de ABERTO reabre para ABERTO (dono Quality)."""
    chamado = _abrir(user_quality, user_quality)
    services.executar(chamado, Acao.BLOQUEAR, {"motivo": "peça"}, user_quality)
    chamado.refresh_from_db()
    assert chamado.status == Status.BLOQUEADO
    services.executar(chamado, Acao.REABRIR, {"motivo": "chegou"}, user_quality)
    chamado.refresh_from_db()
    assert chamado.status == Status.ABERTO


@pytest.mark.django_db
def test_reabrir_de_encaminhado_volta_para_encaminhado_posse_intel(
    user_quality, user_inteligencia
):
    """RN-12 — bloqueado a partir de ENCAMINHADO reabre para ENCAMINHADO, e é a
    Inteligência (dono atual) quem reabre."""
    chamado = _abrir(
        user_quality, user_quality, encaminhar=True,
        procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=user_inteligencia,
    )
    services.executar(chamado, Acao.BLOQUEAR, {"motivo": "terceiro"}, user_inteligencia)
    chamado.refresh_from_db()
    # Quality não reabre um bloqueio que era da Inteligência.
    with pytest.raises(PermissionDenied):
        services.executar(chamado, Acao.REABRIR, {"motivo": "x"}, user_quality)
    services.executar(chamado, Acao.REABRIR, {"motivo": "resolvido terceiro"}, user_inteligencia)
    chamado.refresh_from_db()
    assert chamado.status == Status.ENCAMINHADO


# --------------------------------------------------------------------------- #
# Imutabilidade dos fatos de abertura (RN-03)                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_transicao_nao_altera_fatos_de_abertura(user_quality):
    """RN-03 — nenhuma ação toca cliente/categoria/equipamento/responsável."""
    chamado = _abrir(user_quality, user_quality)
    antes = (chamado.cliente, chamado.categoria, chamado.numero_equipamento,
             chamado.modelo_equipamento, chamado.problema_relatado,
             chamado.responsavel_id, chamado.aberto_em,
             chamado.contato_nome, chamado.contato_telefone,
             chamado.contato_email, chamado.contato_meio)
    services.executar(chamado, Acao.BLOQUEAR, {"motivo": "aguardando"}, user_quality)
    chamado.refresh_from_db()
    depois = (chamado.cliente, chamado.categoria, chamado.numero_equipamento,
              chamado.modelo_equipamento, chamado.problema_relatado,
              chamado.responsavel_id, chamado.aberto_em,
              chamado.contato_nome, chamado.contato_telefone,
              chamado.contato_email, chamado.contato_meio)
    assert antes == depois


@pytest.mark.django_db
def test_evento_e_append_only(user_quality):
    """ADR-010 — um ChamadoEvento já criado não pode ser reescrito nem apagado."""
    chamado = _abrir(user_quality, user_quality)
    evento = chamado.eventos.get()
    evento.motivo = "hack"
    with pytest.raises(ValidationError):
        evento.save()
    with pytest.raises(ValidationError):
        evento.delete()


# --------------------------------------------------------------------------- #
# Painel derivado do log (RN-05, ADR-011)                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_painel_bate_com_o_log(user_quality, user_inteligencia):
    aberto = _abrir(user_quality, user_quality)  # ABERTO
    encaminhado = _abrir(
        user_quality, user_quality, encaminhar=True,
        procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=user_inteligencia,
    )
    resolvido = _abrir(user_quality, user_quality)
    services.executar(resolvido, Acao.FINALIZAR, {"procedimento_realizado": "ok"}, user_quality)

    m = metricas_painel()
    assert m["fila_ativa"] == 1
    assert m["encaminhados"] == 1
    assert m["resolvidos_hoje"] == 1
    assert "em_analise" not in m


# --------------------------------------------------------------------------- #
# Views / permissões (integração)                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_fila_exige_login(client):
    resp = client.get(reverse("chamados:fila"))
    assert resp.status_code == 302
    assert "login" in resp.url.lower() or resp.url


@pytest.mark.django_db
def test_abrir_get_bloqueado_para_nao_quality(client, user_inteligencia):
    """Inteligência é operador, mas ABRIR é exclusivo de quality → 403."""
    client.force_login(user_inteligencia)
    resp = client.get(reverse("chamados:abrir"))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_fila_bloqueada_para_nao_operador(client, user_comum):
    """Usuário logado fora de quality/inteligencia não acessa a fila → 403."""
    client.force_login(user_comum)
    resp = client.get(reverse("chamados:fila"))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_fila_liberada_para_inteligencia(client, user_inteligencia):
    """Inteligência é operador → vê a fila (RN-18)."""
    client.force_login(user_inteligencia)
    resp = client.get(reverse("chamados:fila"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_detalhe_bloqueado_para_nao_operador(client, user_comum, user_quality):
    chamado = _abrir(user_quality, user_quality)
    client.force_login(user_comum)
    resp = client.get(reverse("chamados:detalhe", args=[chamado.pk]))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_acao_bloqueada_para_nao_operador(client, user_comum, user_quality):
    """Mesmo o POST de ação é barrado na URL para não-operador → 403."""
    chamado = _abrir(user_quality, user_quality)
    client.force_login(user_comum)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.FINALIZAR])
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_abrir_post_cria_chamado(client, user_quality, cliente, produto):
    client.force_login(user_quality)
    # `responsavel` não é mais enviado no POST: vem do usuário logado.
    resp = client.post(
        reverse("chamados:abrir"),
        {
            "cliente": cliente.pk,
            "categoria": "HARDWARE",
            "numero_equipamento": "EQ-9",
            "modelo_equipamento": produto.pk,
            "problema_relatado": "Falha",
            "contato_nome": "Maria Contato",
            "contato_telefone": "1133334444",
            "contato_email": "maria@exemplo.com",
            "contato_meio": "EMAIL",
        },
    )
    assert resp.status_code == 302
    chamado = Chamado.objects.get(cliente=cliente, numero_equipamento="EQ-9")
    assert chamado.responsavel == user_quality  # definido pelo usuário logado
    assert chamado.contato_nome == "Maria Contato"
    assert chamado.contato_meio == "EMAIL"


@pytest.mark.django_db
def test_abrir_com_multiplos_equipamentos(client, user_quality, cliente, produto):
    """Vários inputs de numero_equipamento são juntados em 'EQ-1, EQ-2, EQ-3'."""
    client.force_login(user_quality)
    resp = client.post(
        reverse("chamados:abrir"),
        {
            "cliente": cliente.pk,
            "categoria": "HARDWARE",
            # o test client envia a lista como múltiplos valores de mesmo name
            "numero_equipamento": ["EQ-1", " EQ-2 ", "", "EQ-3"],
            "modelo_equipamento": produto.pk,
            "problema_relatado": "Falha",
            "contato_nome": "Contato",
            "contato_meio": "TELEFONE",
        },
    )
    assert resp.status_code == 302
    chamado = Chamado.objects.get(cliente=cliente)
    # vazios descartados, espaços aparados, juntados por ", "
    assert chamado.numero_equipamento == "EQ-1, EQ-2, EQ-3"


@pytest.mark.django_db
def test_abrir_ignora_responsavel_forjado_no_post(
    client, user_quality, outro_quality, cliente, produto
):
    """O responsável é sempre o usuário logado; um `responsavel` enviado no POST
    (tentando forjar outro Quality) é ignorado pela view."""
    client.force_login(user_quality)
    resp = client.post(
        reverse("chamados:abrir"),
        {
            "cliente": cliente.pk,
            "categoria": "HARDWARE",
            "numero_equipamento": "EQ-FORJADO",
            "modelo_equipamento": produto.pk,
            "problema_relatado": "Falha",
            "responsavel": outro_quality.pk,  # tentativa de forjar — deve ser ignorada
            "contato_nome": "Contato",
            "contato_meio": "TELEFONE",
        },
    )
    assert resp.status_code == 302
    chamado = Chamado.objects.get(numero_equipamento="EQ-FORJADO")
    assert chamado.responsavel == user_quality  # e NÃO outro_quality


@pytest.mark.django_db
def test_acao_finalizar_via_view(client, user_quality):
    chamado = _abrir(user_quality, user_quality)
    client.force_login(user_quality)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.FINALIZAR]),
        {"procedimento_realizado": "resolvido no local"},
    )
    assert resp.status_code == 302
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO


# --------------------------------------------------------------------------- #
# Isolamento da Inteligência — só vê e age no que foi encaminhado a ELE        #
# --------------------------------------------------------------------------- #


def _encaminhado_para(user_quality, intel):
    return _abrir(
        user_quality, user_quality, encaminhar=True,
        procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=intel,
    )


@pytest.mark.django_db
def test_intel_nao_age_em_encaminhado_de_outro_intel(
    user_quality, user_inteligencia, outro_inteligencia
):
    """Posse individual: intel B não resolve chamado encaminhado ao intel A."""
    chamado = _encaminhado_para(user_quality, user_inteligencia)
    with pytest.raises(PermissionDenied):
        services.executar(
            chamado, Acao.RESOLVER, {"procedimento_realizado": "x"}, outro_inteligencia
        )


@pytest.mark.django_db
def test_intel_dono_resolve_o_seu(user_quality, user_inteligencia):
    """O intel a quem foi encaminhado continua resolvendo normalmente."""
    chamado = _encaminhado_para(user_quality, user_inteligencia)
    services.executar(
        chamado, Acao.RESOLVER, {"procedimento_realizado": "ok"}, user_inteligencia
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO


@pytest.mark.django_db
def test_fila_do_intel_mostra_so_os_dele(
    client, user_quality, user_inteligencia, outro_inteligencia
):
    """A fila do intel A não lista chamados de quality nem os do intel B."""
    meu = _encaminhado_para(user_quality, user_inteligencia)
    do_outro = _encaminhado_para(user_quality, outro_inteligencia)
    aberto_quality = _abrir(user_quality, user_quality)  # ABERTO, não é de intel

    client.force_login(user_inteligencia)
    resp = client.get(reverse("chamados:fila"))
    pks = {linha["chamado"].pk for linha in resp.context["linhas"]}
    assert pks == {meu.pk}
    assert do_outro.pk not in pks
    assert aberto_quality.pk not in pks


@pytest.mark.django_db
def test_quality_ve_tudo_na_fila(
    client, user_quality, user_inteligencia, outro_inteligencia
):
    """Quality continua vendo todos os chamados."""
    a = _abrir(user_quality, user_quality)
    b = _encaminhado_para(user_quality, user_inteligencia)
    c = _encaminhado_para(user_quality, outro_inteligencia)

    client.force_login(user_quality)
    resp = client.get(reverse("chamados:fila"))
    pks = {linha["chamado"].pk for linha in resp.context["linhas"]}
    assert {a.pk, b.pk, c.pk} <= pks


@pytest.mark.django_db
def test_intel_nao_abre_detalhe_de_outro(
    client, user_quality, user_inteligencia, outro_inteligencia
):
    """Acesso direto por URL: intel A recebe 404 no detalhe de chamado do B."""
    do_outro = _encaminhado_para(user_quality, outro_inteligencia)
    client.force_login(user_inteligencia)
    resp = client.get(reverse("chamados:detalhe", args=[do_outro.pk]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_intel_nao_posta_acao_em_chamado_de_outro(
    client, user_quality, user_inteligencia, outro_inteligencia
):
    """POST direto de ação em chamado alheio → 404 (nem chega ao service)."""
    do_outro = _encaminhado_para(user_quality, outro_inteligencia)
    client.force_login(user_inteligencia)
    resp = client.post(
        reverse("chamados:acao", args=[do_outro.pk, Acao.RESOLVER]),
        {"procedimento_realizado": "x"},
    )
    assert resp.status_code == 404
    do_outro.refresh_from_db()
    assert do_outro.status == Status.ENCAMINHADO  # inalterado


# --------------------------------------------------------------------------- #
# Fluxo Expedição — Inteligência encaminha p/ expedição; grupo expedicao age   #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_intel_encaminha_para_expedicao(user_quality, user_inteligencia):
    """A Inteligência (dona do ENCAMINHADO) envia o chamado para EXPEDICAO."""
    chamado = _encaminhado_para(user_quality, user_inteligencia)
    services.executar(
        chamado,
        Acao.ENCAMINHAR_EXPEDICAO,
        {"procedimento_realizado": "verificado", "tratativa": "precisa manutenção"},
        user_inteligencia,
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.EXPEDICAO
    # o responsável de inteligência permanece registrado (RN-15 análogo)
    assert chamado.responsavel_inteligencia == user_inteligencia


@pytest.mark.django_db
def test_encaminhar_expedicao_exige_procedimento_e_tratativa(
    user_quality, user_inteligencia
):
    chamado = _encaminhado_para(user_quality, user_inteligencia)
    with pytest.raises(ValidationError):
        services.executar(
            chamado, Acao.ENCAMINHAR_EXPEDICAO,
            {"procedimento_realizado": "só isso"}, user_inteligencia,
        )


@pytest.mark.django_db
def test_quality_nao_encaminha_para_expedicao(user_quality, user_inteligencia):
    """Só a Inteligência (dona do ENCAMINHADO) manda p/ expedição — não o Quality."""
    chamado = _encaminhado_para(user_quality, user_inteligencia)
    with pytest.raises(PermissionDenied):
        services.executar(
            chamado, Acao.ENCAMINHAR_EXPEDICAO,
            {"procedimento_realizado": "p", "tratativa": "t"}, user_quality,
        )


def _em_expedicao(user_quality, user_inteligencia):
    """Helper: chamado levado até o estado EXPEDICAO."""
    chamado = _encaminhado_para(user_quality, user_inteligencia)
    services.executar(
        chamado, Acao.ENCAMINHAR_EXPEDICAO,
        {"procedimento_realizado": "p", "tratativa": "t"}, user_inteligencia,
    )
    return chamado


@pytest.mark.django_db
def test_expedicao_so_marca_chegada_nao_resolve(
    user_quality, user_inteligencia, user_expedicao
):
    """A Expedição NÃO resolve nem bloqueia — só marca chegada. As demais ações
    a partir de EXPEDICAO nem existem (transição inválida)."""
    chamado = _em_expedicao(user_quality, user_inteligencia)
    for acao, dados in (
        (Acao.RESOLVER, {"procedimento_realizado": "x"}),
        (Acao.BLOQUEAR, {"motivo": "m"}),
        (Acao.ENCAMINHAR_EXPEDICAO, {"procedimento_realizado": "p", "tratativa": "t"}),
    ):
        with pytest.raises(ValidationError):  # não é transição válida de EXPEDICAO
            services.executar(chamado, acao, dados, user_expedicao)
    chamado.refresh_from_db()
    assert chamado.status == Status.EXPEDICAO  # inalterado


@pytest.mark.django_db
def test_expedicao_marca_chegada_vai_para_laboratorio(
    user_quality, user_inteligencia, user_expedicao
):
    """Marcar chegada leva o chamado de EXPEDICAO para LABORATORIO."""
    chamado = _em_expedicao(user_quality, user_inteligencia)
    services.executar(chamado, Acao.MARCAR_CHEGADA, {}, user_expedicao)
    chamado.refresh_from_db()
    assert chamado.status == Status.LABORATORIO


@pytest.mark.django_db
def test_qualquer_expedicao_marca_chegada_fila_compartilhada(
    user_quality, user_inteligencia, outro_expedicao
):
    """Fila compartilhada: um segundo membro da expedição também marca chegada."""
    chamado = _em_expedicao(user_quality, user_inteligencia)
    services.executar(chamado, Acao.MARCAR_CHEGADA, {}, outro_expedicao)
    chamado.refresh_from_db()
    assert chamado.status == Status.LABORATORIO


@pytest.mark.django_db
def test_nao_expedicao_nao_marca_chegada(
    user_quality, user_inteligencia, user_comum
):
    """Quem não é da expedição não marca chegada (posse do grupo expedicao)."""
    chamado = _em_expedicao(user_quality, user_inteligencia)
    with pytest.raises(PermissionDenied):
        services.executar(chamado, Acao.MARCAR_CHEGADA, {}, user_comum)


@pytest.mark.django_db
def test_laboratorio_ve_fila_de_laboratorio(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """Após marcar chegada, o chamado (LABORATORIO) aparece na fila do laboratório
    e não na da expedição."""
    chamado = _em_expedicao(user_quality, user_inteligencia)
    services.executar(chamado, Acao.MARCAR_CHEGADA, {}, user_expedicao)

    client.force_login(user_laboratorio)
    resp = client.get(reverse("chamados:fila"))
    pks = {linha["chamado"].pk for linha in resp.context["linhas"]}
    assert pks == {chamado.pk}

    # e a expedição não vê mais (saiu de EXPEDICAO)
    client.force_login(user_expedicao)
    resp = client.get(reverse("chamados:fila"))
    pks_exp = {linha["chamado"].pk for linha in resp.context["linhas"]}
    assert chamado.pk not in pks_exp


@pytest.mark.django_db
def test_marcar_chegada_via_view(client, user_quality, user_inteligencia, user_expedicao):
    """POST da ação pela view muda o status para LABORATORIO e, como o chamado
    sai da fila da expedição, redireciona para a fila (não para o detalhe = 404)."""
    chamado = _em_expedicao(user_quality, user_inteligencia)
    client.force_login(user_expedicao)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.MARCAR_CHEGADA])
    )
    assert resp.status_code == 302
    assert resp.url == reverse("chamados:fila")  # não o detalhe (evita 404)
    chamado.refresh_from_db()
    assert chamado.status == Status.LABORATORIO


@pytest.mark.django_db
def test_intel_nao_age_apos_enviar_para_expedicao(user_quality, user_inteligencia):
    """Após EXPEDICAO a Inteligência não resolve mais: RESOLVER nem é transição
    válida a partir de EXPEDICAO (a expedição só marca chegada)."""
    chamado = _em_expedicao(user_quality, user_inteligencia)
    with pytest.raises(ValidationError):
        services.executar(
            chamado, Acao.RESOLVER,
            {"procedimento_realizado": "x"}, user_inteligencia,
        )


@pytest.mark.django_db
def test_expedicao_ve_fila_de_expedicao(
    client, user_quality, user_inteligencia, user_expedicao
):
    """A expedição vê os chamados em EXPEDICAO e não os ABERTO/ENCAMINHADO."""
    em_expedicao = _encaminhado_para(user_quality, user_inteligencia)
    services.executar(
        em_expedicao, Acao.ENCAMINHAR_EXPEDICAO,
        {"procedimento_realizado": "p", "tratativa": "t"}, user_inteligencia,
    )
    so_aberto = _abrir(user_quality, user_quality)  # ABERTO
    so_encaminhado = _encaminhado_para(user_quality, user_inteligencia)  # ENCAMINHADO

    client.force_login(user_expedicao)
    resp = client.get(reverse("chamados:fila"))
    pks = {linha["chamado"].pk for linha in resp.context["linhas"]}
    assert pks == {em_expedicao.pk}
    assert so_aberto.pk not in pks
    assert so_encaminhado.pk not in pks


@pytest.mark.django_db
def test_encaminhar_para_expedicao_via_view(
    client, user_quality, user_inteligencia
):
    """POST da ação pela view muda o status para EXPEDICAO."""
    chamado = _encaminhado_para(user_quality, user_inteligencia)
    client.force_login(user_inteligencia)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.ENCAMINHAR_EXPEDICAO]),
        {"procedimento_realizado": "verificado", "tratativa": "manutenção"},
    )
    assert resp.status_code == 302
    chamado.refresh_from_db()
    assert chamado.status == Status.EXPEDICAO


# --------------------------------------------------------------------------- #
# Fluxo Laboratório → Comercial — lab dá a tratativa e encaminha ao comercial  #
# --------------------------------------------------------------------------- #


def _em_laboratorio(user_quality, user_inteligencia, user_expedicao):
    """Helper: chamado levado até o estado LABORATORIO."""
    chamado = _em_expedicao(user_quality, user_inteligencia)
    services.executar(chamado, Acao.MARCAR_CHEGADA, {}, user_expedicao)
    return chamado


def _em_laboratorio_multi(user_quality, user_inteligencia, user_expedicao, numeros):
    """Chamado com N equipamentos (numero_equipamento juntado por vírgula), levado
    até LABORATORIO."""
    cliente = Clientes.objects.create(nome="ACME", endereco="R", cnpj="00000000000000")
    chamado = _abrir(
        user_quality, user_quality, cliente=cliente,
        encaminhar=True, procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=user_inteligencia,
    )
    # sobrescreve numero_equipamento com a lista desejada
    chamado.numero_equipamento = ", ".join(numeros)
    chamado.save(update_fields=["numero_equipamento"])
    services.executar(chamado, Acao.ENCAMINHAR_EXPEDICAO,
                      {"procedimento_realizado": "p", "tratativa": "t"}, user_inteligencia)
    services.executar(chamado, Acao.MARCAR_CHEGADA, {}, user_expedicao)
    return chamado


@pytest.mark.django_db
def test_lab_encaminha_para_comercial_por_equipamento(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """O Laboratório informa a tratativa de CADA equipamento; o chamado vai p/
    COMERCIAL e uma linha de TratativaEquipamento é gravada por equipamento."""
    from chamados.models import TratativaEquipamento

    chamado = _em_laboratorio_multi(
        user_quality, user_inteligencia, user_expedicao, ["EQ-1", "EQ-2", "EQ-3"]
    )
    services.executar(
        chamado, Acao.ENCAMINHAR_COMERCIAL,
        {"tratativas_equipamento": [
            {"numero": "EQ-1", "tratativa": "trocada a placa"},
            {"numero": "EQ-2", "tratativa": "limpeza de contato"},
            {"numero": "EQ-3", "tratativa": "sem reparo"},
        ]},
        user_laboratorio,
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.COMERCIAL

    linhas = TratativaEquipamento.objects.filter(chamado=chamado).order_by("id")
    assert [(l.numero_equipamento, l.tratativa) for l in linhas] == [
        ("EQ-1", "trocada a placa"),
        ("EQ-2", "limpeza de contato"),
        ("EQ-3", "sem reparo"),
    ]
    # a tratativa consolidada reúne os três
    assert "EQ-1: trocada a placa" in chamado.tratativa
    assert "EQ-3: sem reparo" in chamado.tratativa


@pytest.mark.django_db
def test_encaminhar_comercial_exige_tratativa_de_cada_equipamento(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """Falta a tratativa de um equipamento → erro (nem transiciona)."""
    from chamados.models import TratativaEquipamento

    chamado = _em_laboratorio_multi(
        user_quality, user_inteligencia, user_expedicao, ["EQ-1", "EQ-2"]
    )
    with pytest.raises(ValidationError):
        services.executar(
            chamado, Acao.ENCAMINHAR_COMERCIAL,
            {"tratativas_equipamento": [{"numero": "EQ-1", "tratativa": "só esse"}]},
            user_laboratorio,
        )
    chamado.refresh_from_db()
    assert chamado.status == Status.LABORATORIO  # inalterado
    assert TratativaEquipamento.objects.filter(chamado=chamado).count() == 0  # atômico


@pytest.mark.django_db
def test_nao_laboratorio_nao_encaminha_para_comercial(
    user_quality, user_inteligencia, user_expedicao, user_comercial
):
    """Quem não é do laboratório não encaminha p/ comercial (posse do grupo lab)."""
    chamado = _em_laboratorio(user_quality, user_inteligencia, user_expedicao)
    with pytest.raises(PermissionDenied):
        services.executar(
            chamado, Acao.ENCAMINHAR_COMERCIAL,
            {"tratativas_equipamento": [{"numero": "EQ-001", "tratativa": "x"}]},
            user_comercial,
        )


@pytest.mark.django_db
def test_comercial_ve_fila_de_comercial(
    client, user_quality, user_inteligencia, user_expedicao,
    user_laboratorio, user_comercial,
):
    """Após encaminhar p/ comercial, o chamado (COMERCIAL) aparece na fila do
    comercial e sai da fila do laboratório."""
    chamado = _em_laboratorio(user_quality, user_inteligencia, user_expedicao)
    services.executar(
        chamado, Acao.ENCAMINHAR_COMERCIAL,
        {"tratativas_equipamento": [{"numero": "EQ-001", "tratativa": "t"}]},
        user_laboratorio,
    )

    client.force_login(user_comercial)
    resp = client.get(reverse("chamados:fila"))
    pks = {linha["chamado"].pk for linha in resp.context["linhas"]}
    assert pks == {chamado.pk}

    client.force_login(user_laboratorio)
    resp = client.get(reverse("chamados:fila"))
    pks_lab = {linha["chamado"].pk for linha in resp.context["linhas"]}
    assert chamado.pk not in pks_lab


@pytest.mark.django_db
def test_encaminhar_comercial_via_view_por_equipamento(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """POST pela view: os campos tratativa_<i> viram linhas por equipamento e o
    status vai para COMERCIAL (redireciona à fila, pois sai da fila do lab)."""
    from chamados.models import TratativaEquipamento

    chamado = _em_laboratorio_multi(
        user_quality, user_inteligencia, user_expedicao, ["EQ-1", "EQ-2"]
    )
    client.force_login(user_laboratorio)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.ENCAMINHAR_COMERCIAL]),
        {"tratativa_0": "reparo A", "tratativa_1": "reparo B"},
    )
    assert resp.status_code == 302
    assert resp.url == reverse("chamados:fila")
    chamado.refresh_from_db()
    assert chamado.status == Status.COMERCIAL
    linhas = TratativaEquipamento.objects.filter(chamado=chamado).order_by("id")
    assert [(l.numero_equipamento, l.tratativa) for l in linhas] == [
        ("EQ-1", "reparo A"), ("EQ-2", "reparo B"),
    ]


@pytest.mark.django_db
def test_encaminhar_comercial_via_view_campo_vazio_falha(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """Deixar a tratativa de um equipamento em branco no POST → não transiciona."""
    chamado = _em_laboratorio_multi(
        user_quality, user_inteligencia, user_expedicao, ["EQ-1", "EQ-2"]
    )
    client.force_login(user_laboratorio)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.ENCAMINHAR_COMERCIAL]),
        {"tratativa_0": "reparo A", "tratativa_1": ""},
    )
    assert resp.status_code == 302
    assert resp.url == reverse("chamados:detalhe", args=[chamado.pk])  # volta ao detalhe c/ erro
    chamado.refresh_from_db()
    assert chamado.status == Status.LABORATORIO  # inalterado


def _em_comercial(user_quality, user_inteligencia, user_expedicao, user_laboratorio, numeros=None):
    """Chamado levado até o estado COMERCIAL (opcionalmente com N equipamentos)."""
    if numeros:
        chamado = _em_laboratorio_multi(user_quality, user_inteligencia, user_expedicao, numeros)
        tratativas = [{"numero": n, "tratativa": f"lab {n}"} for n in numeros]
    else:
        chamado = _em_laboratorio(user_quality, user_inteligencia, user_expedicao)
        tratativas = [{"numero": "EQ-001", "tratativa": "lab"}]
    services.executar(
        chamado, Acao.ENCAMINHAR_COMERCIAL,
        {"tratativas_equipamento": tratativas}, user_laboratorio,
    )
    return chamado


@pytest.mark.django_db
def test_comercial_tem_acao_finalizar(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    """O comercial vê a ação 'Finalizar chamado' no estado COMERCIAL."""
    from chamados.selectors import acoes_disponiveis

    chamado = _em_comercial(user_quality, user_inteligencia, user_expedicao, user_laboratorio)
    assert acoes_disponiveis(user_comercial, chamado) == [Acao.FINALIZAR_COMERCIAL]


@pytest.mark.django_db
def test_comercial_finaliza_com_tratativa_e_custo(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    """Finalizar grava tratativa_comercial + custo por equipamento e vai a RESOLVIDO."""
    from chamados.models import TratativaEquipamento

    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        numeros=["EQ-1", "EQ-2"],
    )
    services.executar(
        chamado, Acao.FINALIZAR_COMERCIAL,
        {"finalizacao_equipamento": [
            {"numero": "EQ-1", "tratativa": "orçado", "custo": "COM_CUSTO"},
            {"numero": "EQ-2", "tratativa": "garantia", "custo": "SEM_CUSTO"},
        ]},
        user_comercial,
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO

    linhas = {l.numero_equipamento: l for l in
              TratativaEquipamento.objects.filter(chamado=chamado)}
    assert linhas["EQ-1"].tratativa_comercial == "orçado"
    assert linhas["EQ-1"].custo == "COM_CUSTO"
    assert linhas["EQ-2"].tratativa_comercial == "garantia"
    assert linhas["EQ-2"].custo == "SEM_CUSTO"
    # não duplicou linhas: continua 1 por equipamento (a do lab foi completada)
    assert TratativaEquipamento.objects.filter(chamado=chamado).count() == 2


@pytest.mark.django_db
def test_finalizar_comercial_exige_custo_de_cada_equipamento(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        numeros=["EQ-1", "EQ-2"],
    )
    with pytest.raises(ValidationError):  # falta custo do EQ-2
        services.executar(
            chamado, Acao.FINALIZAR_COMERCIAL,
            {"finalizacao_equipamento": [
                {"numero": "EQ-1", "tratativa": "ok", "custo": "COM_CUSTO"},
                {"numero": "EQ-2", "tratativa": "ok", "custo": ""},
            ]},
            user_comercial,
        )
    chamado.refresh_from_db()
    assert chamado.status == Status.COMERCIAL  # inalterado


@pytest.mark.django_db
def test_nao_comercial_nao_finaliza(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comum
):
    """Quem não é do comercial não finaliza (posse do grupo comercial)."""
    chamado = _em_comercial(user_quality, user_inteligencia, user_expedicao, user_laboratorio)
    with pytest.raises(PermissionDenied):
        services.executar(
            chamado, Acao.FINALIZAR_COMERCIAL,
            {"finalizacao_equipamento": [
                {"numero": "EQ-001", "tratativa": "x", "custo": "COM_CUSTO"}
            ]},
            user_comum,
        )


@pytest.mark.django_db
def test_finalizar_comercial_via_view(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    """POST pela view: campos tratativa_<i>/custo_<i> viram os dados por equipamento
    e o chamado vai a RESOLVIDO."""
    from chamados.models import TratativaEquipamento

    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        numeros=["EQ-1", "EQ-2"],
    )
    client.force_login(user_comercial)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.FINALIZAR_COMERCIAL]),
        {
            "tratativa_0": "reparo A", "custo_0": "COM_CUSTO",
            "tratativa_1": "reparo B", "custo_1": "SEM_CUSTO",
        },
    )
    assert resp.status_code == 302
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO
    linhas = {l.numero_equipamento: l for l in
              TratativaEquipamento.objects.filter(chamado=chamado)}
    assert linhas["EQ-1"].custo == "COM_CUSTO"
    assert linhas["EQ-2"].custo == "SEM_CUSTO"


@pytest.mark.django_db
def test_resolvido_apos_comercial_e_terminal(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    """Após finalizar pelo comercial, RESOLVIDO é terminal (sem novas ações)."""
    from chamados.selectors import acoes_disponiveis

    chamado = _em_comercial(user_quality, user_inteligencia, user_expedicao, user_laboratorio)
    services.executar(
        chamado, Acao.FINALIZAR_COMERCIAL,
        {"finalizacao_equipamento": [
            {"numero": "EQ-001", "tratativa": "t", "custo": "SEM_CUSTO"}
        ]},
        user_comercial,
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO
    assert acoes_disponiveis(user_comercial, chamado) == []


# --------------------------------------------------------------------------- #
# Revisão de visibilidade: tela ÚNICA + detalhe bloqueado por papel            #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_expedicao_perde_detalhe_apos_marcar_chegada(
    client, user_quality, user_inteligencia, user_expedicao
):
    """A expedição abre o detalhe enquanto está em EXPEDICAO; após marcar chegada
    (vai p/ LABORATORIO), o mesmo detalhe passa a dar 404 para ela."""
    chamado = _em_expedicao(user_quality, user_inteligencia)
    client.force_login(user_expedicao)
    assert client.get(reverse("chamados:detalhe", args=[chamado.pk])).status_code == 200

    services.executar(chamado, Acao.MARCAR_CHEGADA, {}, user_expedicao)
    assert client.get(reverse("chamados:detalhe", args=[chamado.pk])).status_code == 404


@pytest.mark.django_db
def test_laboratorio_perde_detalhe_apos_encaminhar_comercial(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """O laboratório vê o detalhe em LABORATORIO; após encaminhar p/ comercial
    (vai p/ COMERCIAL), o detalhe passa a dar 404 para ele."""
    chamado = _em_laboratorio(user_quality, user_inteligencia, user_expedicao)
    client.force_login(user_laboratorio)
    assert client.get(reverse("chamados:detalhe", args=[chamado.pk])).status_code == 200

    services.executar(
        chamado, Acao.ENCAMINHAR_COMERCIAL,
        {"tratativas_equipamento": [{"numero": "EQ-001", "tratativa": "t"}]},
        user_laboratorio,
    )
    assert client.get(reverse("chamados:detalhe", args=[chamado.pk])).status_code == 404


@pytest.mark.django_db
def test_expedicao_nao_abre_detalhe_de_encaminhado(
    client, user_quality, user_inteligencia, user_expedicao
):
    """A expedição não enxerga (404) um chamado que ainda está ENCAMINHADO."""
    encaminhado = _encaminhado_para(user_quality, user_inteligencia)
    client.force_login(user_expedicao)
    resp = client.get(reverse("chamados:detalhe", args=[encaminhado.pk]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_comercial_nao_abre_detalhe_de_laboratorio(
    client, user_quality, user_inteligencia, user_expedicao, user_comercial
):
    """O comercial não enxerga (404) um chamado que ainda está no LABORATORIO."""
    no_lab = _em_laboratorio(user_quality, user_inteligencia, user_expedicao)
    client.force_login(user_comercial)
    resp = client.get(reverse("chamados:detalhe", args=[no_lab.pk]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_todos_os_papeis_usam_a_mesma_tela(
    client, user_quality, user_inteligencia, user_expedicao,
    user_laboratorio, user_comercial,
):
    """A tela é única (chamados:fila): todos os papéis acessam a MESMA URL com 200."""
    for usuario in (user_quality, user_inteligencia, user_expedicao,
                    user_laboratorio, user_comercial):
        client.force_login(usuario)
        resp = client.get(reverse("chamados:fila"))
        assert resp.status_code == 200


@pytest.mark.django_db
def test_expedicao_ve_so_expedicao_na_fila_unica(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """Na tela única, a expedição vê só os EXPEDICAO — nem ENCAMINHADO, nem
    LABORATORIO, nem RESOLVIDO."""
    em_exp = _em_expedicao(user_quality, user_inteligencia)
    em_lab = _em_laboratorio(user_quality, user_inteligencia, user_expedicao)
    so_encaminhado = _encaminhado_para(user_quality, user_inteligencia)

    client.force_login(user_expedicao)
    resp = client.get(reverse("chamados:fila"))
    pks = {linha["chamado"].pk for linha in resp.context["linhas"]}
    assert pks == {em_exp.pk}
    assert em_lab.pk not in pks
    assert so_encaminhado.pk not in pks
