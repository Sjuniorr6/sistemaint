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
def user_financeiro(db):
    """Usuário do grupo `financeiro` (fila compartilhada que fatura e encerra)."""
    financeiro, _ = Group.objects.get_or_create(name="financeiro")
    u = User.objects.create_user(username="f1", password="x")
    u.groups.add(financeiro)
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


@pytest.fixture
def manutencao(db, cliente):
    """Entrada de manutenção elegível para vínculo (mesmos critérios da tela
    "Registro das entradas": status em andamento e data a partir de 2026)."""
    import datetime

    from django.utils import timezone

    from registrodemanutencao.models import registrodemanutencao

    m = registrodemanutencao.objects.create(nome=cliente, status="Manutenção")
    # data_criacao costuma ser auto_now_add; garantimos o corte de data do filtro.
    registrodemanutencao.objects.filter(pk=m.pk).update(
        data_criacao=timezone.make_aware(datetime.datetime(2026, 6, 1, 12, 0))
    )
    m.refresh_from_db()
    return m


def _pdf_falso(nome="termo.pdf"):
    """Arquivo PDF mínimo em memória, para os testes de anexo do termo."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(nome, b"%PDF-1.4 teste", content_type="application/pdf")


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
    services.aceitar_tratativa(chamado, user_inteligencia)  # aceite antes de agir
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
    """Chamado em ENCAMINHADO, já ACEITO pela inteligência.

    O aceite é obrigatório antes de agir (marco inicial do SLA), então os helpers
    já o executam para que os testes de fluxo sigam direto ao ponto.
    """
    chamado = _abrir(
        user_quality, user_quality, encaminhar=True,
        procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=intel,
    )
    services.aceitar_tratativa(chamado, intel)
    return chamado


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


def _em_expedicao(user_quality, user_inteligencia, aceitar=True, user_expedicao=None):
    """Chamado levado até EXPEDICAO. Com `aceitar`, a expedição já aceitou."""
    chamado = _encaminhado_para(user_quality, user_inteligencia)
    services.executar(
        chamado, Acao.ENCAMINHAR_EXPEDICAO,
        {"procedimento_realizado": "p", "tratativa": "t"}, user_inteligencia,
    )
    if aceitar and user_expedicao is not None:
        services.aceitar_tratativa(chamado, user_expedicao)
    return chamado


@pytest.mark.django_db
def test_expedicao_so_marca_chegada_nao_resolve(
    user_quality, user_inteligencia, user_expedicao
):
    """A Expedição NÃO resolve nem bloqueia — só marca chegada. As demais ações
    a partir de EXPEDICAO nem existem (transição inválida)."""
    chamado = _em_expedicao(user_quality, user_inteligencia, user_expedicao=user_expedicao)
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
    chamado = _em_expedicao(user_quality, user_inteligencia, user_expedicao=user_expedicao)
    services.executar(chamado, Acao.MARCAR_CHEGADA, {}, user_expedicao)
    chamado.refresh_from_db()
    assert chamado.status == Status.LABORATORIO


@pytest.mark.django_db
def test_qualquer_expedicao_marca_chegada_fila_compartilhada(
    user_quality, user_inteligencia, outro_expedicao
):
    """Fila compartilhada: um segundo membro da expedição também marca chegada."""
    chamado = _em_expedicao(user_quality, user_inteligencia, user_expedicao=outro_expedicao)
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
    chamado = _em_expedicao(user_quality, user_inteligencia, user_expedicao=user_expedicao)
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
    chamado = _em_expedicao(user_quality, user_inteligencia, user_expedicao=user_expedicao)
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


def _em_laboratorio(user_quality, user_inteligencia, user_expedicao,
                    user_laboratorio=None):
    """Chamado levado até LABORATORIO (aceito pelo lab quando informado)."""
    chamado = _em_expedicao(
        user_quality, user_inteligencia, user_expedicao=user_expedicao
    )
    services.executar(chamado, Acao.MARCAR_CHEGADA, {}, user_expedicao)
    if user_laboratorio is not None:
        services.aceitar_tratativa(chamado, user_laboratorio)
    return chamado


def _em_laboratorio_multi(user_quality, user_inteligencia, user_expedicao, numeros,
                          user_laboratorio=None):
    """Chamado com N equipamentos (numero_equipamento juntado por vírgula), levado
    até LABORATORIO (aceito pelo lab quando informado)."""
    cliente = Clientes.objects.create(nome="ACME", endereco="R", cnpj="00000000000000")
    chamado = _abrir(
        user_quality, user_quality, cliente=cliente,
        encaminhar=True, procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=user_inteligencia,
    )
    services.aceitar_tratativa(chamado, user_inteligencia)
    # sobrescreve numero_equipamento com a lista desejada
    chamado.numero_equipamento = ", ".join(numeros)
    chamado.save(update_fields=["numero_equipamento"])
    services.executar(chamado, Acao.ENCAMINHAR_EXPEDICAO,
                      {"procedimento_realizado": "p", "tratativa": "t"}, user_inteligencia)
    services.aceitar_tratativa(chamado, user_expedicao)
    services.executar(chamado, Acao.MARCAR_CHEGADA, {}, user_expedicao)
    if user_laboratorio is not None:
        services.aceitar_tratativa(chamado, user_laboratorio)
    return chamado


@pytest.mark.django_db
def test_lab_encaminha_para_comercial_por_equipamento(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """O Laboratório informa a tratativa de CADA equipamento; o chamado vai p/
    COMERCIAL e uma linha de TratativaEquipamento é gravada por equipamento."""
    from chamados.models import TratativaEquipamento

    chamado = _em_laboratorio_multi(
        user_quality, user_inteligencia, user_expedicao, ["EQ-1", "EQ-2", "EQ-3"],
        user_laboratorio=user_laboratorio,
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
        user_quality, user_inteligencia, user_expedicao, ["EQ-1", "EQ-2"],
        user_laboratorio=user_laboratorio,
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
    chamado = _em_laboratorio(user_quality, user_inteligencia, user_expedicao, user_laboratorio=user_laboratorio)
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
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    manutencao,
):
    """POST pela view: os campos tratativa_<i> viram linhas por equipamento, a
    manutenção é vinculada e o status vai para COMERCIAL (redireciona à fila)."""
    from chamados.models import TratativaEquipamento

    chamado = _em_laboratorio_multi(
        user_quality, user_inteligencia, user_expedicao, ["EQ-1", "EQ-2"],
        user_laboratorio=user_laboratorio,
    )
    client.force_login(user_laboratorio)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.ENCAMINHAR_COMERCIAL]),
        {
            "tratativa_0": "reparo A", "tratativa_1": "reparo B",
            "manutencao": manutencao.pk,
        },
    )
    assert resp.status_code == 302
    assert resp.url == reverse("chamados:fila")
    chamado.refresh_from_db()
    assert chamado.status == Status.COMERCIAL
    assert chamado.manutencao == manutencao  # vínculo gravado
    linhas = TratativaEquipamento.objects.filter(chamado=chamado).order_by("id")
    assert [(l.numero_equipamento, l.tratativa) for l in linhas] == [
        ("EQ-1", "reparo A"), ("EQ-2", "reparo B"),
    ]


@pytest.mark.django_db
def test_encaminhar_comercial_exige_manutencao(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """Sem selecionar a manutenção, o encaminhamento ao comercial não acontece."""
    chamado = _em_laboratorio(
        user_quality, user_inteligencia, user_expedicao,
        user_laboratorio=user_laboratorio,
    )
    client.force_login(user_laboratorio)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.ENCAMINHAR_COMERCIAL]),
        {"tratativa_0": "reparo"},  # sem `manutencao`
    )
    assert resp.status_code == 302
    assert resp.url == reverse("chamados:detalhe", args=[chamado.pk])  # erro no form
    chamado.refresh_from_db()
    assert chamado.status == Status.LABORATORIO  # inalterado
    assert chamado.manutencao is None


@pytest.mark.django_db
def test_select_de_manutencoes_lista_as_da_tela_de_entradas(manutencao, cliente):
    """O select do modal usa o mesmo critério da tela "Registro das entradas"."""
    import datetime

    from django.utils import timezone

    from chamados.forms import EncaminharComercialForm
    from chamados.selectors import manutencoes_para_vinculo
    from registrodemanutencao.models import registrodemanutencao

    # fora do filtro: status não listado
    fora_status = registrodemanutencao.objects.create(nome=cliente, status="Finalizado")
    registrodemanutencao.objects.filter(pk=fora_status.pk).update(
        data_criacao=timezone.make_aware(datetime.datetime(2026, 6, 1, 12, 0))
    )
    # fora do filtro: anterior a 2026
    fora_data = registrodemanutencao.objects.create(nome=cliente, status="Manutenção")
    registrodemanutencao.objects.filter(pk=fora_data.pk).update(
        data_criacao=timezone.make_aware(datetime.datetime(2025, 12, 31, 12, 0))
    )

    ids = list(manutencoes_para_vinculo().values_list("id", flat=True))
    assert manutencao.pk in ids
    assert fora_status.pk not in ids
    assert fora_data.pk not in ids

    # rótulo do select: "#ID · Empresa"
    form = EncaminharComercialForm(equipamentos=["EQ-1"])
    rotulo = form.fields["manutencao"].label_from_instance(manutencao)
    assert rotulo == f"#{manutencao.pk} · {cliente.nome}"


@pytest.mark.django_db
def test_encaminhar_comercial_via_view_campo_vazio_falha(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """Deixar a tratativa de um equipamento em branco no POST → não transiciona."""
    chamado = _em_laboratorio_multi(
        user_quality, user_inteligencia, user_expedicao, ["EQ-1", "EQ-2"],
        user_laboratorio=user_laboratorio,
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


def _em_comercial(user_quality, user_inteligencia, user_expedicao, user_laboratorio,
                  numeros=None, user_comercial=None):
    """Chamado levado até COMERCIAL (aceito pelo comercial quando informado)."""
    if numeros:
        chamado = _em_laboratorio_multi(
            user_quality, user_inteligencia, user_expedicao, numeros,
            user_laboratorio=user_laboratorio,
        )
        tratativas = [{"numero": n, "tratativa": f"lab {n}"} for n in numeros]
    else:
        chamado = _em_laboratorio(
            user_quality, user_inteligencia, user_expedicao,
            user_laboratorio=user_laboratorio,
        )
        tratativas = [{"numero": "EQ-001", "tratativa": "lab"}]
    services.executar(
        chamado, Acao.ENCAMINHAR_COMERCIAL,
        {"tratativas_equipamento": tratativas}, user_laboratorio,
    )
    if user_comercial is not None:
        services.aceitar_tratativa(chamado, user_comercial)
    return chamado


@pytest.mark.django_db
def test_comercial_tem_acao_finalizar(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    """O comercial vê a ação 'Finalizar chamado' no estado COMERCIAL."""
    from chamados.selectors import acoes_disponiveis

    chamado = _em_comercial(user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial=user_comercial)
    assert acoes_disponiveis(user_comercial, chamado) == [Acao.FINALIZAR_COMERCIAL]


@pytest.mark.django_db
def test_comercial_finaliza_com_tratativa_e_custo(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    """Finalizar grava tratativa_comercial + custo por equipamento e vai a RESOLVIDO."""
    from chamados.models import TratativaEquipamento

    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        numeros=["EQ-1", "EQ-2"], user_comercial=user_comercial,
    )
    services.executar(
        chamado, Acao.FINALIZAR_COMERCIAL,
        {
            "finalizacao_equipamento": [
                {"numero": "EQ-1", "tratativa": "orçado", "custo": "COM_CUSTO"},
                {"numero": "EQ-2", "tratativa": "garantia", "custo": "SEM_CUSTO"},
            ],
            # Há COM_CUSTO → termo obrigatório.
            "termo_substituicao": _pdf_falso(),
        },
        user_comercial,
    )
    chamado.refresh_from_db()
    # Há equipamento COM CUSTO → segue para o FINANCEIRO (não encerra aqui).
    assert chamado.status == Status.FINANCEIRO

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
        numeros=["EQ-1", "EQ-2"], user_comercial=user_comercial,
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
        numeros=["EQ-1", "EQ-2"], user_comercial=user_comercial,
    )
    client.force_login(user_comercial)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.FINALIZAR_COMERCIAL]),
        {
            "tratativa_0": "reparo A", "custo_0": "COM_CUSTO",
            "tratativa_1": "reparo B", "custo_1": "SEM_CUSTO",
            "termo_substituicao": _pdf_falso(),  # há COM_CUSTO
        },
    )
    assert resp.status_code == 302
    chamado.refresh_from_db()
    # COM CUSTO → vai ao FINANCEIRO (encerra só depois do faturamento).
    assert chamado.status == Status.FINANCEIRO
    assert chamado.termo_substituicao  # anexado
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

    chamado = _em_comercial(user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial=user_comercial)
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
    chamado = _em_expedicao(user_quality, user_inteligencia, user_expedicao=user_expedicao)
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
    chamado = _em_laboratorio(user_quality, user_inteligencia, user_expedicao, user_laboratorio=user_laboratorio)
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
    em_exp = _em_expedicao(user_quality, user_inteligencia, user_expedicao=user_expedicao)
    em_lab = _em_laboratorio(user_quality, user_inteligencia, user_expedicao, user_laboratorio=user_laboratorio)
    so_encaminhado = _encaminhado_para(user_quality, user_inteligencia)

    client.force_login(user_expedicao)
    resp = client.get(reverse("chamados:fila"))
    pks = {linha["chamado"].pk for linha in resp.context["linhas"]}
    assert pks == {em_exp.pk}
    assert em_lab.pk not in pks
    assert so_encaminhado.pk not in pks


# --------------------------------------------------------------------------- #
# Aceite da tratativa + passagens por setor (SLA)                              #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_abertura_cria_passagem_do_quality_ja_aceita(user_quality):
    """Quem abre já é dono: a passagem do Quality nasce aceita (sem clique)."""
    from chamados.enums import Setor

    chamado = _abrir(user_quality, user_quality)
    passagem = chamado.passagens.get()
    assert passagem.setor == Setor.QUALITY
    assert passagem.aceito_em == chamado.aberto_em
    assert passagem.aceito_por == user_quality
    assert passagem.finalizado_em is None  # ainda em aberto
    assert passagem.espera.total_seconds() == 0


@pytest.mark.django_db
def test_abrir_ja_encaminhado_fecha_quality_e_abre_inteligencia(
    user_quality, user_inteligencia
):
    """RN-08: nasce em ENCAMINHADO — Quality já sai, Inteligência entra sem aceite."""
    from chamados.enums import Setor

    chamado = _abrir(
        user_quality, user_quality, encaminhar=True,
        procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=user_inteligencia,
    )
    quality, intel = list(chamado.passagens.order_by("id"))
    assert quality.setor == Setor.QUALITY and quality.finalizado_em is not None
    assert quality.acao_saida == Acao.ENCAMINHAR
    assert intel.setor == Setor.INTELIGENCIA
    assert intel.aceito_em is None  # aguarda o aceite da inteligência


@pytest.mark.django_db
def test_sem_aceite_so_oferece_aceitar_e_service_recusa(
    user_quality, user_inteligencia
):
    """Antes do aceite: única ação é ACEITAR e o service recusa as demais."""
    from chamados.selectors import acoes_disponiveis

    chamado = _abrir(
        user_quality, user_quality, encaminhar=True,
        procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=user_inteligencia,
    )
    assert acoes_disponiveis(user_inteligencia, chamado) == [Acao.ACEITAR_TRATATIVA]

    with pytest.raises(ValidationError):  # sem aceite não age
        services.executar(
            chamado, Acao.RESOLVER, {"procedimento_realizado": "x"}, user_inteligencia
        )
    chamado.refresh_from_db()
    assert chamado.status == Status.ENCAMINHADO  # inalterado


@pytest.mark.django_db
def test_aceitar_grava_marco_e_nao_muda_status(user_quality, user_inteligencia):
    """O aceite carimba aceito_em/por, registra o evento e NÃO muda o status."""
    chamado = _abrir(
        user_quality, user_quality, encaminhar=True,
        procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=user_inteligencia,
    )
    services.aceitar_tratativa(chamado, user_inteligencia)
    chamado.refresh_from_db()

    assert chamado.status == Status.ENCAMINHADO  # não mudou
    passagem = chamado.passagens.order_by("id").last()
    assert passagem.aceito_em is not None
    assert passagem.aceito_por == user_inteligencia

    evento = chamado.eventos.order_by("id").last()
    assert evento.acao == Acao.ACEITAR_TRATATIVA
    assert evento.estado_origem == evento.estado_destino == Status.ENCAMINHADO


@pytest.mark.django_db
def test_aceitar_duas_vezes_falha(user_quality, user_inteligencia):
    chamado = _encaminhado_para(user_quality, user_inteligencia)  # já aceito
    with pytest.raises(ValidationError):
        services.aceitar_tratativa(chamado, user_inteligencia)


@pytest.mark.django_db
def test_quem_nao_tem_posse_nao_aceita(
    user_quality, user_inteligencia, outro_inteligencia
):
    """Aceite segue a mesma posse das ações: intel B não aceita o chamado do A."""
    chamado = _abrir(
        user_quality, user_quality, encaminhar=True,
        procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=user_inteligencia,
    )
    with pytest.raises(PermissionDenied):
        services.aceitar_tratativa(chamado, outro_inteligencia)


@pytest.mark.django_db
def test_fluxo_completo_gera_uma_passagem_por_setor(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    """Percorre o ciclo inteiro e confere uma passagem por setor, encadeadas."""
    from chamados.enums import Setor

    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial=user_comercial,
    )
    services.executar(
        chamado, Acao.FINALIZAR_COMERCIAL,
        {"finalizacao_equipamento": [
            {"numero": "EQ-001", "tratativa": "t", "custo": "SEM_CUSTO"}
        ]},
        user_comercial,
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO

    passagens = list(chamado.passagens.order_by("id"))
    assert [p.setor for p in passagens] == [
        Setor.QUALITY, Setor.INTELIGENCIA, Setor.EXPEDICAO,
        Setor.LABORATORIO, Setor.COMERCIAL,
    ]
    # todas fechadas, com os três marcos coerentes e durações não-negativas
    for p in passagens:
        assert p.aceito_em is not None and p.finalizado_em is not None
        assert p.chegou_em <= p.aceito_em <= p.finalizado_em
        assert p.espera.total_seconds() >= 0
        assert p.trabalho.total_seconds() >= 0
        assert p.total == p.espera + p.trabalho
    # encadeamento: a saída de uma passagem é a chegada da seguinte
    for anterior, seguinte in zip(passagens, passagens[1:]):
        assert anterior.finalizado_em == seguinte.chegou_em


@pytest.mark.django_db
def test_bloquear_e_reabrir_nao_mexem_nas_passagens(user_quality):
    """Bloqueio/reabertura pausam o chamado sem trocar de setor: 1 passagem só."""
    chamado = _abrir(user_quality, user_quality)
    assert chamado.passagens.count() == 1

    services.executar(chamado, Acao.BLOQUEAR, {"motivo": "peça"}, user_quality)
    chamado.refresh_from_db()
    services.executar(chamado, Acao.REABRIR, {"motivo": "chegou"}, user_quality)
    chamado.refresh_from_db()

    assert chamado.passagens.count() == 1
    passagem = chamado.passagens.get()
    assert passagem.finalizado_em is None  # segue aberta com o mesmo dono


@pytest.mark.django_db
def test_aceitar_via_view(client, user_quality, user_inteligencia):
    """POST do aceite pela view carimba o marco e volta ao detalhe."""
    chamado = _abrir(
        user_quality, user_quality, encaminhar=True,
        procedimento_realizado="p", tratativa="t",
        responsavel_inteligencia=user_inteligencia,
    )
    client.force_login(user_inteligencia)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.ACEITAR_TRATATIVA])
    )
    assert resp.status_code == 302
    assert resp.url == reverse("chamados:detalhe", args=[chamado.pk])
    passagem = chamado.passagens.order_by("id").last()
    assert passagem.aceito_por == user_inteligencia


@pytest.mark.django_db
def test_sla_nao_aparece_na_ui(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """O SLA é só para o admin: nada de passagens/tempos no detalhe do fluxo."""
    chamado = _em_laboratorio(
        user_quality, user_inteligencia, user_expedicao,
        user_laboratorio=user_laboratorio,
    )
    client.force_login(user_laboratorio)
    html = client.get(reverse("chamados:detalhe", args=[chamado.pk])).content.decode()
    for termo in ("SLA", "Passagem", "passagens", "Espera", "chegou_em"):
        assert termo not in html


# --------------------------------------------------------------------------- #
# Tratativas de contato da Expedição com o cliente                             #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_expedicao_registra_contato(user_quality, user_inteligencia, user_expedicao):
    """Registra a tentativa de contato sem mudar o status do chamado."""
    from chamados.models import ContatoExpedicao

    chamado = _em_expedicao(
        user_quality, user_inteligencia, user_expedicao=user_expedicao
    )
    services.registrar_contato(
        chamado, user_expedicao,
        nome_contato="Maria", telefone="1133334444",
        tratativa="Sem sucesso, retorna amanhã",
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.EXPEDICAO  # não muda

    contato = ContatoExpedicao.objects.get(chamado=chamado)
    assert contato.nome_contato == "Maria"
    assert contato.telefone == "1133334444"
    assert contato.registrado_por == user_expedicao
    assert contato.codigo_rastreio == ""  # opcional


@pytest.mark.django_db
def test_varios_contatos_formam_historico(
    user_quality, user_inteligencia, user_expedicao
):
    """Cada registro é uma tentativa: o histórico acumula (mais recente primeiro)."""
    from chamados.models import ContatoExpedicao

    chamado = _em_expedicao(
        user_quality, user_inteligencia, user_expedicao=user_expedicao
    )
    services.registrar_contato(
        chamado, user_expedicao, nome_contato="Maria", tratativa="Sem sucesso"
    )
    services.registrar_contato(
        chamado, user_expedicao, nome_contato="João",
        tratativa="Vai postar dia 20", codigo_rastreio="BR123456789BR",
    )
    contatos = ContatoExpedicao.objects.filter(chamado=chamado)
    assert contatos.count() == 2
    assert contatos.first().nome_contato == "João"  # ordering: -criado_em
    assert contatos.first().codigo_rastreio == "BR123456789BR"


@pytest.mark.django_db
def test_contato_exige_nome_e_tratativa(
    user_quality, user_inteligencia, user_expedicao
):
    chamado = _em_expedicao(
        user_quality, user_inteligencia, user_expedicao=user_expedicao
    )
    with pytest.raises(ValidationError):
        services.registrar_contato(
            chamado, user_expedicao, nome_contato="", tratativa="x"
        )
    with pytest.raises(ValidationError):
        services.registrar_contato(
            chamado, user_expedicao, nome_contato="Maria", tratativa="   "
        )


@pytest.mark.django_db
def test_contato_exige_aceite(user_quality, user_inteligencia, user_expedicao):
    """Sem aceite, a expedição não registra contato (é trabalho do setor)."""
    chamado = _em_expedicao(user_quality, user_inteligencia)  # sem aceitar
    with pytest.raises(ValidationError):
        services.registrar_contato(
            chamado, user_expedicao, nome_contato="Maria", tratativa="Sem sucesso"
        )


@pytest.mark.django_db
def test_nao_expedicao_nao_registra_contato(
    user_quality, user_inteligencia, user_expedicao, user_comum
):
    chamado = _em_expedicao(
        user_quality, user_inteligencia, user_expedicao=user_expedicao
    )
    with pytest.raises(PermissionDenied):
        services.registrar_contato(
            chamado, user_comum, nome_contato="Maria", tratativa="x"
        )


@pytest.mark.django_db
def test_contato_so_na_expedicao(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """Fora do estado EXPEDICAO não se registra contato (ex.: já no laboratório)."""
    chamado = _em_laboratorio(
        user_quality, user_inteligencia, user_expedicao,
        user_laboratorio=user_laboratorio,
    )
    with pytest.raises(ValidationError):
        services.registrar_contato(
            chamado, user_laboratorio, nome_contato="Maria", tratativa="x"
        )


@pytest.mark.django_db
def test_registrar_contato_via_view(
    client, user_quality, user_inteligencia, user_expedicao
):
    """POST pela view grava o contato e volta ao detalhe."""
    from chamados.models import ContatoExpedicao

    chamado = _em_expedicao(
        user_quality, user_inteligencia, user_expedicao=user_expedicao
    )
    client.force_login(user_expedicao)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.REGISTRAR_CONTATO]),
        {
            "nome_contato": "Andreia falou com Maria",
            "telefone": "11999998888",
            "tratativa": "Cliente vai enviar o equipamento dia 20",
            "codigo_rastreio": "BR987654321BR",
        },
    )
    assert resp.status_code == 302
    assert resp.url == reverse("chamados:detalhe", args=[chamado.pk])
    contato = ContatoExpedicao.objects.get(chamado=chamado)
    assert contato.codigo_rastreio == "BR987654321BR"


@pytest.mark.django_db
def test_contatos_visiveis_da_expedicao_em_diante(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio
):
    """O histórico de contatos segue visível depois que o chamado avança."""
    chamado = _em_expedicao(
        user_quality, user_inteligencia, user_expedicao=user_expedicao
    )
    services.registrar_contato(
        chamado, user_expedicao, nome_contato="Maria",
        tratativa="Vai postar", codigo_rastreio="BR111222333BR",
    )
    # expedição vê
    client.force_login(user_expedicao)
    html = client.get(reverse("chamados:detalhe", args=[chamado.pk])).content.decode()
    assert "Tratativas de contato" in html
    assert "BR111222333BR" in html

    # avança para o laboratório: continua visível lá
    services.executar(chamado, Acao.MARCAR_CHEGADA, {}, user_expedicao)
    client.force_login(user_laboratorio)
    html_lab = client.get(reverse("chamados:detalhe", args=[chamado.pk])).content.decode()
    assert "Maria" in html_lab
    assert "BR111222333BR" in html_lab


@pytest.mark.django_db
def test_botao_contato_aparece_para_expedicao(
    client, user_quality, user_inteligencia, user_expedicao
):
    """A expedição vê 'Tratativas de Contato' ao lado de 'Marcar chegada'."""
    chamado = _em_expedicao(
        user_quality, user_inteligencia, user_expedicao=user_expedicao
    )
    client.force_login(user_expedicao)
    html = client.get(reverse("chamados:detalhe", args=[chamado.pk])).content.decode()
    assert "Tratativas de Contato" in html
    assert "Marcar chegada" in html
    assert "modalContatoExpedicao" in html


# --------------------------------------------------------------------------- #
# Botão "Baixar laudo" (após o Comercial aceitar a tratativa)                   #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_laudo_indisponivel_antes_do_aceite_do_comercial(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial, manutencao,
):
    """Chegou no comercial COM manutenção vinculada, mas sem aceite → sem laudo."""
    chamado = _em_laboratorio(
        user_quality, user_inteligencia, user_expedicao,
        user_laboratorio=user_laboratorio,
    )
    services.executar(
        chamado, Acao.ENCAMINHAR_COMERCIAL,
        {
            "tratativas_equipamento": [{"numero": "EQ-001", "tratativa": "t"}],
            "manutencao": manutencao,
        },
        user_laboratorio,
    )
    client.force_login(user_comercial)
    html = client.get(reverse("chamados:detalhe", args=[chamado.pk])).content.decode()
    assert "Baixar laudo" not in html  # ainda não aceitou


@pytest.mark.django_db
def test_laudo_disponivel_apos_aceite_do_comercial(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial, manutencao,
):
    """Após o aceite do comercial, o botão do laudo aparece apontando para a
    mesma URL da tela "Registro das entradas" (download_pdfmanutencao)."""
    chamado = _em_laboratorio(
        user_quality, user_inteligencia, user_expedicao,
        user_laboratorio=user_laboratorio,
    )
    services.executar(
        chamado, Acao.ENCAMINHAR_COMERCIAL,
        {
            "tratativas_equipamento": [{"numero": "EQ-001", "tratativa": "t"}],
            "manutencao": manutencao,
        },
        user_laboratorio,
    )
    services.aceitar_tratativa(chamado, user_comercial)

    client.force_login(user_comercial)
    html = client.get(reverse("chamados:detalhe", args=[chamado.pk])).content.decode()
    assert "Baixar laudo" in html
    assert reverse("download_pdfmanutencao", args=[manutencao.pk]) in html


@pytest.mark.django_db
def test_laudo_continua_apos_finalizar(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial, manutencao,
):
    """O laudo segue disponível depois de RESOLVIDO (a passagem do comercial
    permanece registrada como aceita)."""
    chamado = _em_laboratorio(
        user_quality, user_inteligencia, user_expedicao,
        user_laboratorio=user_laboratorio,
    )
    services.executar(
        chamado, Acao.ENCAMINHAR_COMERCIAL,
        {
            "tratativas_equipamento": [{"numero": "EQ-001", "tratativa": "t"}],
            "manutencao": manutencao,
        },
        user_laboratorio,
    )
    services.aceitar_tratativa(chamado, user_comercial)
    services.executar(
        chamado, Acao.FINALIZAR_COMERCIAL,
        {"finalizacao_equipamento": [
            {"numero": "EQ-001", "tratativa": "t", "custo": "SEM_CUSTO"}
        ]},
        user_comercial,
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO

    client.force_login(user_quality)  # quality vê tudo
    html = client.get(reverse("chamados:detalhe", args=[chamado.pk])).content.decode()
    assert "Baixar laudo" in html


@pytest.mark.django_db
def test_sem_manutencao_vinculada_nao_tem_laudo(
    client, user_quality, user_inteligencia, user_expedicao
):
    """Chamado sem manutenção vinculada nunca oferece o laudo."""
    chamado = _em_expedicao(
        user_quality, user_inteligencia, user_expedicao=user_expedicao
    )
    client.force_login(user_expedicao)
    html = client.get(reverse("chamados:detalhe", args=[chamado.pk])).content.decode()
    assert "Baixar laudo" not in html


# --------------------------------------------------------------------------- #
# Termo de substituição (obrigatório quando há equipamento COM CUSTO)          #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_com_custo_exige_termo(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    """COM CUSTO sem termo anexado → não finaliza."""
    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial=user_comercial,
    )
    with pytest.raises(ValidationError):
        services.executar(
            chamado, Acao.FINALIZAR_COMERCIAL,
            {"finalizacao_equipamento": [
                {"numero": "EQ-001", "tratativa": "t", "custo": "COM_CUSTO"}
            ]},
            user_comercial,
        )
    chamado.refresh_from_db()
    assert chamado.status == Status.COMERCIAL  # inalterado


@pytest.mark.django_db
def test_sem_custo_nao_exige_termo(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    """Todos SEM CUSTO → finaliza normalmente, sem anexo."""
    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial=user_comercial,
    )
    services.executar(
        chamado, Acao.FINALIZAR_COMERCIAL,
        {"finalizacao_equipamento": [
            {"numero": "EQ-001", "tratativa": "t", "custo": "SEM_CUSTO"}
        ]},
        user_comercial,
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO
    assert not chamado.termo_substituicao


@pytest.mark.django_db
def test_termo_salvo_ao_finalizar_com_custo(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial=user_comercial,
    )
    services.executar(
        chamado, Acao.FINALIZAR_COMERCIAL,
        {
            "finalizacao_equipamento": [
                {"numero": "EQ-001", "tratativa": "t", "custo": "COM_CUSTO"}
            ],
            "termo_substituicao": _pdf_falso("termo-abc.pdf"),
        },
        user_comercial,
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.FINANCEIRO  # com custo → financeiro
    assert chamado.termo_substituicao
    assert chamado.termo_substituicao.name.endswith(".pdf")
    assert "chamados/termos/" in chamado.termo_substituicao.name


@pytest.mark.django_db
def test_form_recusa_arquivo_nao_pdf(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial,
):
    """Só PDF: um anexo de outro tipo é recusado pelo form."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial=user_comercial,
    )
    client.force_login(user_comercial)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.FINALIZAR_COMERCIAL]),
        {
            "tratativa_0": "t", "custo_0": "COM_CUSTO",
            "termo_substituicao": SimpleUploadedFile(
                "termo.docx", b"nao e pdf", content_type="application/msword"
            ),
        },
    )
    assert resp.status_code == 302
    assert resp.url == reverse("chamados:detalhe", args=[chamado.pk])  # erro no form
    chamado.refresh_from_db()
    assert chamado.status == Status.COMERCIAL  # não finalizou


@pytest.mark.django_db
def test_view_exige_termo_quando_ha_custo(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial,
):
    """Pela view: COM CUSTO sem anexo → volta ao detalhe com erro."""
    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial=user_comercial,
    )
    client.force_login(user_comercial)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.FINALIZAR_COMERCIAL]),
        {"tratativa_0": "t", "custo_0": "COM_CUSTO"},  # sem termo
    )
    assert resp.status_code == 302
    assert resp.url == reverse("chamados:detalhe", args=[chamado.pk])
    chamado.refresh_from_db()
    assert chamado.status == Status.COMERCIAL


@pytest.mark.django_db
def test_termo_acessivel_a_quem_ve_o_laudo(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial, manutencao,
):
    """O termo acompanha o laudo: quem tem acesso ao laudo (comercial/financeiro)
    também baixa o termo — o Financeiro precisa dos dois para cobrar o cliente."""
    chamado = _em_laboratorio(
        user_quality, user_inteligencia, user_expedicao,
        user_laboratorio=user_laboratorio,
    )
    services.executar(
        chamado, Acao.ENCAMINHAR_COMERCIAL,
        {
            "tratativas_equipamento": [{"numero": "EQ-001", "tratativa": "t"}],
            "manutencao": manutencao,
        },
        user_laboratorio,
    )
    services.aceitar_tratativa(chamado, user_comercial)
    services.executar(
        chamado, Acao.FINALIZAR_COMERCIAL,
        {
            "finalizacao_equipamento": [
                {"numero": "EQ-001", "tratativa": "t", "custo": "COM_CUSTO"}
            ],
            "termo_substituicao": _pdf_falso(),
        },
        user_comercial,
    )
    client.force_login(user_quality)
    html = client.get(reverse("chamados:detalhe", args=[chamado.pk])).content.decode()
    assert "Termo de substituição" in html
    assert "Baixar laudo" in html


# --------------------------------------------------------------------------- #
# Fluxo Financeiro — com custo vai ao financeiro; sem custo encerra no comercial #
# --------------------------------------------------------------------------- #


def _no_financeiro(user_quality, user_inteligencia, user_expedicao,
                   user_laboratorio, user_comercial, user_financeiro=None,
                   manutencao=None):
    """Chamado levado até FINANCEIRO (comercial finalizou COM CUSTO)."""
    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial=user_comercial,
    )
    services.executar(
        chamado, Acao.FINALIZAR_COMERCIAL,
        {
            "finalizacao_equipamento": [
                {"numero": "EQ-001", "tratativa": "orçado", "custo": "COM_CUSTO"}
            ],
            "termo_substituicao": _pdf_falso(),
        },
        user_comercial,
    )
    if user_financeiro is not None:
        services.aceitar_tratativa(chamado, user_financeiro)
    return chamado


@pytest.mark.django_db
def test_com_custo_vai_para_financeiro(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    """Havendo equipamento COM CUSTO, o comercial NÃO encerra: vai ao financeiro."""
    from chamados.enums import Setor

    chamado = _no_financeiro(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial,
    )
    assert chamado.status == Status.FINANCEIRO
    # abriu a passagem do financeiro (aguardando aceite)
    passagem = chamado.passagens.order_by("id").last()
    assert passagem.setor == Setor.FINANCEIRO
    assert passagem.aceito_em is None


@pytest.mark.django_db
def test_sem_custo_encerra_no_comercial(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio, user_comercial
):
    """Sem nenhum equipamento com custo, o chamado encerra no comercial."""
    chamado = _em_comercial(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial=user_comercial,
    )
    services.executar(
        chamado, Acao.FINALIZAR_COMERCIAL,
        {"finalizacao_equipamento": [
            {"numero": "EQ-001", "tratativa": "t", "custo": "SEM_CUSTO"}
        ]},
        user_comercial,
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO  # encerrado ali mesmo
    assert not chamado.passagens.filter(setor="FINANCEIRO").exists()


@pytest.mark.django_db
def test_financeiro_fatura_e_encerra(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial, user_financeiro,
):
    """Financeiro aceita, informa valor + NF e o chamado é ENCERRADO."""
    from decimal import Decimal

    chamado = _no_financeiro(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial, user_financeiro=user_financeiro,
    )
    services.executar(
        chamado, Acao.FATURAR,
        {"valor_faturamento": Decimal("1250.50"), "nota_fiscal": "NF-12345"},
        user_financeiro,
    )
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO
    assert chamado.valor_faturamento == Decimal("1250.50")
    assert chamado.nota_fiscal == "NF-12345"


@pytest.mark.django_db
def test_faturar_exige_valor_e_nf(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial, user_financeiro,
):
    chamado = _no_financeiro(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial, user_financeiro=user_financeiro,
    )
    with pytest.raises(ValidationError):  # sem NF
        services.executar(
            chamado, Acao.FATURAR,
            {"valor_faturamento": "100.00", "nota_fiscal": ""},
            user_financeiro,
        )
    chamado.refresh_from_db()
    assert chamado.status == Status.FINANCEIRO  # inalterado


@pytest.mark.django_db
def test_financeiro_precisa_aceitar_antes_de_faturar(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial, user_financeiro,
):
    """Sem aceite, o financeiro não fatura (marco inicial do SLA do setor)."""
    from chamados.selectors import acoes_disponiveis

    chamado = _no_financeiro(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial,  # sem aceitar
    )
    assert acoes_disponiveis(user_financeiro, chamado) == [Acao.ACEITAR_TRATATIVA]
    with pytest.raises(ValidationError):
        services.executar(
            chamado, Acao.FATURAR,
            {"valor_faturamento": "100.00", "nota_fiscal": "NF-1"},
            user_financeiro,
        )


@pytest.mark.django_db
def test_nao_financeiro_nao_fatura(
    user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial, user_comum,
):
    chamado = _no_financeiro(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial,
    )
    with pytest.raises(PermissionDenied):
        services.executar(
            chamado, Acao.FATURAR,
            {"valor_faturamento": "100.00", "nota_fiscal": "NF-1"},
            user_comum,
        )


@pytest.mark.django_db
def test_financeiro_ve_fila_de_financeiro(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial, user_financeiro,
):
    """O financeiro vê os chamados em FINANCEIRO; o comercial deixa de vê-los."""
    chamado = _no_financeiro(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial,
    )
    client.force_login(user_financeiro)
    resp = client.get(reverse("chamados:fila"))
    pks = {linha["chamado"].pk for linha in resp.context["linhas"]}
    assert pks == {chamado.pk}

    client.force_login(user_comercial)
    resp = client.get(reverse("chamados:fila"))
    assert chamado.pk not in {l["chamado"].pk for l in resp.context["linhas"]}


@pytest.mark.django_db
def test_faturar_via_view(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial, user_financeiro,
):
    """POST pela view grava valor + NF e encerra o chamado."""
    from decimal import Decimal

    chamado = _no_financeiro(
        user_quality, user_inteligencia, user_expedicao, user_laboratorio,
        user_comercial, user_financeiro=user_financeiro,
    )
    client.force_login(user_financeiro)
    resp = client.post(
        reverse("chamados:acao", args=[chamado.pk, Acao.FATURAR]),
        {"valor_faturamento": "980.00", "nota_fiscal": "NF-777"},
    )
    assert resp.status_code == 302
    chamado.refresh_from_db()
    assert chamado.status == Status.RESOLVIDO
    assert chamado.valor_faturamento == Decimal("980.00")
    assert chamado.nota_fiscal == "NF-777"


@pytest.mark.django_db
def test_financeiro_acessa_laudo_e_termo(
    client, user_quality, user_inteligencia, user_expedicao, user_laboratorio,
    user_comercial, user_financeiro, manutencao,
):
    """O financeiro precisa do laudo E do termo para cobrar do cliente."""
    chamado = _em_laboratorio(
        user_quality, user_inteligencia, user_expedicao,
        user_laboratorio=user_laboratorio,
    )
    services.executar(
        chamado, Acao.ENCAMINHAR_COMERCIAL,
        {
            "tratativas_equipamento": [{"numero": "EQ-001", "tratativa": "t"}],
            "manutencao": manutencao,
        },
        user_laboratorio,
    )
    services.aceitar_tratativa(chamado, user_comercial)
    services.executar(
        chamado, Acao.FINALIZAR_COMERCIAL,
        {
            "finalizacao_equipamento": [
                {"numero": "EQ-001", "tratativa": "t", "custo": "COM_CUSTO"}
            ],
            "termo_substituicao": _pdf_falso(),
        },
        user_comercial,
    )
    services.aceitar_tratativa(chamado, user_financeiro)

    client.force_login(user_financeiro)
    html = client.get(reverse("chamados:detalhe", args=[chamado.pk])).content.decode()
    assert "Baixar laudo" in html
    assert "Termo de substituição" in html
    assert "Faturado" in html  # botão do modal
