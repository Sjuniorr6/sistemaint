import pytest
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from controle_acionamentos.services import validar_cpf, validar_cnpj, validar_cnh
from controle_acionamentos.models import (
    ResponsavelAgente,
    Cliente,
    Agente,
    FranquiaAgente,
    Acionamento,
)

def test_cpf_valido_retorna_true():
    """Um CPF válido conhecido deve ser aceito."""
    assert validar_cpf('529.982.247-25') is True

def test_cpf_digito_invalido_retorna_false():
    """Um CPF com dígito verificador errado deve ser rejeitado."""
    assert validar_cpf('529.982.247-26') is False


def test_cpf_digitos_repetidos_retorna_false():
    """CPF com todos os dígitos iguais é inválido (RN-01), mesmo passando na conta."""
    assert validar_cpf('111.111.111-11') is False

def test_cpf_tamanho_errado_retorna_false():
    """CPF com número de dígitos diferente de 11 é inválido."""
    assert validar_cpf('123') is False
    assert validar_cpf('') is False

def test_cnpj_valido_retorna_true():
    """Um CNPJ válido conhecido deve ser aceito (§11.2)."""
    assert validar_cnpj('04.252.011/0001-10') is True


def test_cnpj_digito_invalido_retorna_false():
    """Um CNPJ com dígito verificador errado deve ser rejeitado."""
    assert validar_cnpj('04.252.011/0001-11') is False


def test_cnpj_digitos_repetidos_retorna_false():
    """CNPJ com todos os dígitos iguais é inválido (RN-02), mesmo passando na conta."""
    assert validar_cnpj('00.000.000/0000-00') is False


def test_cnpj_tamanho_errado_retorna_false():
    """CNPJ com número de dígitos diferente de 14 é inválido."""
    assert validar_cnpj('123') is False
    assert validar_cnpj('') is False

def test_cnh_valido_retorna_true():
    """Uma CNH válida conhecida deve ser aceita (RN-03)."""
    assert validar_cnh('19960271686') is True


def test_cnh_digito_invalido_retorna_false():
    """Uma CNH com dígito verificador errado deve ser rejeitada."""
    assert validar_cnh('19960271687') is False


def test_cnh_digitos_repetidos_retorna_false():
    """CNH com todos os dígitos iguais é inválida, mesmo passando na conta."""
    assert validar_cnh('11111111111') is False


def test_cnh_tamanho_errado_retorna_false():
    """CNH com número de dígitos diferente de 11 é inválida."""
    assert validar_cnh('123') is False
    assert validar_cnh('') is False


@pytest.mark.django_db
def test_responsavel_agente_persiste_com_nome_valido():
    responsavel = ResponsavelAgente.objects.create(nome="João Supervisor")

    assert responsavel.pk is not None
    assert ResponsavelAgente.objects.count() == 1
    assert ResponsavelAgente.objects.get(pk=responsavel.pk).nome == "João Supervisor"

@pytest.mark.django_db
def test_responsavel_agente_nome_vazio_e_rejeitado():
    with pytest.raises(ValidationError):
        ResponsavelAgente(nome="   ").full_clean()


@pytest.mark.django_db
def test_responsavel_agente_lista_ordenada_por_criacao_desc():
    antigo = ResponsavelAgente.objects.create(nome="Antigo")
    recente = ResponsavelAgente.objects.create(nome="Recente")
    ResponsavelAgente.objects.filter(pk=antigo.pk).update(
        criado_em=timezone.now() - timedelta(hours=1)
    )

    assert list(ResponsavelAgente.objects.all()) == [recente, antigo]

@pytest.mark.django_db
def test_cliente_persiste_com_dados_validos():
    cliente = Cliente.objects.create(
        nome_empresa="ACME Logística",
        cnpj="11222333000181",
    )

    assert cliente.pk is not None
    assert Cliente.objects.count() == 1
    assert Cliente.objects.get(pk=cliente.pk).nome_empresa == "ACME Logística"


@pytest.mark.django_db
def test_cliente_nome_empresa_vazio_e_rejeitado():
    with pytest.raises(ValidationError):
        Cliente(nome_empresa="   ", cnpj="11222333000181").full_clean()


@pytest.mark.django_db
def test_cliente_cnpj_invalido_e_rejeitado():
    with pytest.raises(ValidationError):
        Cliente(nome_empresa="ACME", cnpj="11222333000180").full_clean()


@pytest.mark.django_db
def test_cliente_cnpj_duplicado_e_rejeitado():
    Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")

    with pytest.raises(ValidationError):
        Cliente(nome_empresa="Outra Empresa", cnpj="11222333000181").full_clean()

@pytest.mark.django_db
def test_agente_persiste_com_dados_validos():
    agente = Agente.objects.create(nome="João Agente", cpf="52998224725")

    assert agente.pk is not None
    assert Agente.objects.count() == 1
    assert Agente.objects.get(pk=agente.pk).nome == "João Agente"


@pytest.mark.django_db
def test_agente_nome_vazio_e_rejeitado():
    with pytest.raises(ValidationError):
        Agente(nome="   ", cpf="52998224725").full_clean()


@pytest.mark.django_db
def test_agente_cpf_invalido_e_rejeitado():
    with pytest.raises(ValidationError):
        Agente(nome="João", cpf="52998224724").full_clean()


@pytest.mark.django_db
def test_agente_cpf_duplicado_e_rejeitado():
    Agente.objects.create(nome="João", cpf="52998224725")

    with pytest.raises(ValidationError):
        Agente(nome="Outro", cpf="52998224725").full_clean()


@pytest.mark.django_db
def test_agente_cnh_opcional_aceita_vazia():
    agente = Agente(nome="Maria", cpf="52998224725", cnh="")
    agente.full_clean()  # não deve levantar

    assert agente.cnh == ""


@pytest.mark.django_db
def test_agente_cnh_invalida_e_rejeitada():
    with pytest.raises(ValidationError):
        Agente(nome="Maria", cpf="52998224725", cnh="11111111111").full_clean()


@pytest.mark.django_db
def test_agente_vincula_clientes():
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    agente = Agente.objects.create(nome="João", cpf="52998224725")

    agente.clientes_vinculados.add(cliente)

    assert cliente in agente.clientes_vinculados.all()
    assert agente in cliente.agentes_vinculados.all()


def _dados_franquia(cliente, **overrides):
    dados = dict(
        cliente=cliente,
        nome="Franquia Moto 80km/4h",
        valor_acionamento=Decimal("150.00"),
        franquia_km=80,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.50"),
        valor_hora_excedente=Decimal("30.00"),
    )
    dados.update(overrides)
    return dados


@pytest.mark.django_db
def test_franquia_persiste_com_dados_validos():
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente))

    assert franquia.pk is not None
    assert FranquiaAgente.objects.count() == 1
    assert franquia.escalonamento_automatico is False


@pytest.mark.django_db
def test_franquia_nome_vazio_e_rejeitado():
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    with pytest.raises(ValidationError):
        FranquiaAgente(**_dados_franquia(cliente, nome="   ")).full_clean()


@pytest.mark.django_db
def test_franquia_km_zero_sem_escalonamento_e_aceito():
    """Decisão do tech lead: franquia_km passa a aceitar 0 (piso 0) quando não há
    escalonamento. Sem escalonamento não existe divisão por franquia_km, então 0 é válido."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    franquia = FranquiaAgente(**_dados_franquia(cliente, franquia_km=0))
    franquia.full_clean()  # não deve levantar
    franquia.save()

    assert franquia.pk is not None
    assert franquia.franquia_km == 0


@pytest.mark.django_db
def test_franquia_km_zero_com_escalonamento_e_rejeitado():
    """franquia_km=0 com escalonamento_automatico=True é rejeitado no clean(): o §8.3
    divide por franquia_km_base, então zero causaria divisão por zero no escalonamento."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    with pytest.raises(ValidationError):
        FranquiaAgente(
            **_dados_franquia(cliente, franquia_km=0, escalonamento_automatico=True)
        ).full_clean()


@pytest.mark.django_db
def test_franquia_valor_negativo_e_rejeitado():
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    with pytest.raises(ValidationError):
        FranquiaAgente(
            **_dados_franquia(cliente, valor_acionamento=Decimal("-1.00"))
        ).full_clean()


@pytest.mark.django_db
def test_franquia_unicidade_cliente_nome():
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia Padrão"))

    with pytest.raises(ValidationError):
        FranquiaAgente(**_dados_franquia(cliente, nome="Franquia Padrão")).full_clean()


@pytest.mark.django_db
def test_franquia_mesmo_nome_clientes_diferentes_e_permitido():
    cliente_a = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    cliente_b = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")

    FranquiaAgente.objects.create(**_dados_franquia(cliente_a, nome="Franquia Padrão"))
    franquia_b = FranquiaAgente(**_dados_franquia(cliente_b, nome="Franquia Padrão"))
    franquia_b.full_clean()  # não deve levantar — unicidade é por (cliente, nome)
    franquia_b.save()

    assert FranquiaAgente.objects.count() == 2


# ---------------------------------------------------------------------------
# CalculadoraValorAgente — cenários de cálculo do §11.1 do PRD
# (lógica pura em services.py, sem banco; contrato Entrada → Resultado)
# ---------------------------------------------------------------------------


def test_calcular_c1_sem_franquia_dentro_do_limite_sem_excedente():
    """§11.1 Cenário 1 — sem franquia vinculada, serviço inline, dentro dos
    limites (km e horas abaixo da franquia), sem pedágio.

    Entrada (km_total=60 já derivado de km_inicio=0/km_final=60, por §8.2;
    a calculadora recebe km_total e horas_total prontos):
        valor_acionamento=100, franquia_km=80, franquia_horas=4,
        valor_km_excedente=2, valor_hora_excedente=30,
        km_total=60, horas_total=3, pedagio=0, sem escalonamento.

    Então (§8.4/§8.5): km_excedente == 0, hora_excedente == 0,
    valor_agente == 100,00 (não há excedente nem pedágio que somem ao valor base).
    """
    # Import local: enquanto o contrato/função não existem, o Red fica isolado
    # neste teste e não derruba a coleção dos demais (32 testes seguem verdes).
    from controle_acionamentos.services import (
        EntradaCalculoAgente,
        calcular_valor_agente,
    )

    entrada = EntradaCalculoAgente(
        valor_acionamento=Decimal("100.00"),
        franquia_km=80,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.00"),
        valor_hora_excedente=Decimal("30.00"),
        escalonamento_ativo=False,
        km_total=60,
        horas_total=Decimal("3.00"),
        pedagio=Decimal("0.00"),
    )

    resultado = calcular_valor_agente(entrada)

    assert resultado.km_excedente == 0
    assert resultado.hora_excedente == Decimal("0.00")
    assert resultado.valor_agente == Decimal("100.00")


def test_calcular_c2_sem_franquia_com_excedente_inline():
    """§11.1 Cenário 2 — mesmo serviço inline do C1, mas agora ESTOURANDO a
    franquia inline: km e horas acima do limite, sem pedágio.

    Entrada (mesmas tarifas/limites do C1; muda só o uso):
        valor_acionamento=100, franquia_km=80, franquia_horas=4,
        valor_km_excedente=2, valor_hora_excedente=30,
        km_total=100, horas_total=5, pedagio=0, sem escalonamento.

    Então (§8.4/§8.5):
        km_excedente   == max(0, 100−80) == 20
        hora_excedente == max(0, 5−4)    == 1
        valor_agente   == 100 + (20×2) + (1×30) + 0 == 170,00
    """
    from controle_acionamentos.services import (
        EntradaCalculoAgente,
        calcular_valor_agente,
    )

    entrada = EntradaCalculoAgente(
        valor_acionamento=Decimal("100.00"),
        franquia_km=80,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.00"),
        valor_hora_excedente=Decimal("30.00"),
        escalonamento_ativo=False,
        km_total=100,
        horas_total=Decimal("5.00"),
        pedagio=Decimal("0.00"),
    )

    resultado = calcular_valor_agente(entrada)

    assert resultado.km_excedente == 20
    assert resultado.hora_excedente == Decimal("1.00")
    assert resultado.valor_agente == Decimal("170.00")


def test_calcular_c3_franquia_escalonamento_um_bloco_exato():
    """§11.1 Cenário 3 — com franquia vinculada e escalonamento ATIVO, 1 bloco
    exato (km estoura a franquia base em 40 = um bloco redondo), sem excedente
    residual e sem pedágio.

    Entrada (franquia 200km/4h, R$660, tarifas 3,30/55, escalonamento ligado):
        valor_acionamento=660, franquia_km=200, franquia_horas=4,
        valor_km_excedente=3.30, valor_hora_excedente=55,
        escalonamento_ativo=True, km_total=240, horas_total=5, pedagio=0.

    Então (§8.3 escalona, §8.4/§8.5 fecham):
        blocos == floor((240−200)/40) == 1
        franquia_km_ajustada    == 200 + 1×40 == 240
        franquia_horas_ajustada == 4 + 1      == 5
        valor_acionamento_ajustado == 660 × (240/200) == 660 × 1,2 == 792,00
        km_excedente   == max(0, 240−240) == 0
        hora_excedente == max(0, 5−5)     == 0
        valor_agente   == 792,00 (sem excedente, sem pedágio)
    """
    from controle_acionamentos.services import (
        EntradaCalculoAgente,
        calcular_valor_agente,
    )

    entrada = EntradaCalculoAgente(
        valor_acionamento=Decimal("660.00"),
        franquia_km=200,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("3.30"),
        valor_hora_excedente=Decimal("55.00"),
        escalonamento_ativo=True,
        km_total=240,
        horas_total=Decimal("5.00"),
        pedagio=Decimal("0.00"),
    )

    resultado = calcular_valor_agente(entrada)

    assert resultado.blocos == 1
    assert resultado.franquia_km_ajustada == 240
    assert resultado.franquia_horas_ajustada == Decimal("5.00")
    assert resultado.valor_acionamento_ajustado == Decimal("792.00")
    assert resultado.km_excedente == 0
    assert resultado.hora_excedente == Decimal("0.00")
    assert resultado.valor_agente == Decimal("792.00")


def test_calcular_c4_franquia_escalonamento_dois_blocos_com_excedente_e_pedagio():
    """§11.1 Cenário 4 — mesma franquia do C3 (escalonamento ATIVO), mas agora
    com 2 blocos E excedente residual após o escalonamento E pedágio somando.

    Entrada (franquia 200km/4h, R$660, tarifas 3,30/55, escalonamento ligado):
        escalonamento_ativo=True, km_total=285, horas_total=7, pedagio=50.

    Então (§8.3 escalona em 2 blocos, sobra excedente, §8.5 soma pedágio):
        blocos == floor((285−200)/40) == 2
        franquia_km_ajustada    == 200 + 2×40 == 280
        franquia_horas_ajustada == 4 + 2      == 6
        valor_acionamento_ajustado == 660 × (280/200) == 660 × 1,4 == 924,00
        km_excedente   == max(0, 285−280) == 5
        hora_excedente == max(0, 7−6)     == 1
        valor_agente   == 924 + (5×3,30) + (1×55) + 50 == 1.045,50
    """
    from controle_acionamentos.services import (
        EntradaCalculoAgente,
        calcular_valor_agente,
    )

    entrada = EntradaCalculoAgente(
        valor_acionamento=Decimal("660.00"),
        franquia_km=200,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("3.30"),
        valor_hora_excedente=Decimal("55.00"),
        escalonamento_ativo=True,
        km_total=285,
        horas_total=Decimal("7.00"),
        pedagio=Decimal("50.00"),
    )

    resultado = calcular_valor_agente(entrada)

    assert resultado.blocos == 2
    assert resultado.franquia_km_ajustada == 280
    assert resultado.franquia_horas_ajustada == Decimal("6.00")
    assert resultado.valor_acionamento_ajustado == Decimal("924.00")
    assert resultado.km_excedente == 5
    assert resultado.hora_excedente == Decimal("1.00")
    assert resultado.valor_agente == Decimal("1045.50")


def test_calcular_c5_franquia_escalonamento_desativado():
    """§11.1 Cenário 5 — franquia IDÊNTICA ao C3, mas com escalonamento
    DESATIVADO. Mesmo km_total=240, porém sem escalonar: a franquia não cresce,
    e o que passa do limite base vira excedente (cobrado às tarifas da franquia).

    Entrada (franquia 200km/4h, R$660, tarifas 3,30/55, escalonamento DESLIGADO):
        escalonamento_ativo=False, km_total=240, horas_total=5, pedagio=0.

    Então (cai no else do §8.3 — *_ajustada == base — e §8.4/§8.5 fecham):
        blocos == 0
        franquia_km_ajustada    == 200 (sem ajuste)
        franquia_horas_ajustada == 4   (sem ajuste)
        valor_acionamento_ajustado == 660,00 (sem ajuste)
        km_excedente   == max(0, 240−200) == 40
        hora_excedente == max(0, 5−4)     == 1
        valor_agente   == 660 + (40×3,30) + (1×55) + 0 == 847,00
    """
    from controle_acionamentos.services import (
        EntradaCalculoAgente,
        calcular_valor_agente,
    )

    entrada = EntradaCalculoAgente(
        valor_acionamento=Decimal("660.00"),
        franquia_km=200,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("3.30"),
        valor_hora_excedente=Decimal("55.00"),
        escalonamento_ativo=False,
        km_total=240,
        horas_total=Decimal("5.00"),
        pedagio=Decimal("0.00"),
    )

    resultado = calcular_valor_agente(entrada)

    assert resultado.blocos == 0
    assert resultado.franquia_km_ajustada == 200
    assert resultado.franquia_horas_ajustada == Decimal("4.00")
    assert resultado.valor_acionamento_ajustado == Decimal("660.00")
    assert resultado.km_excedente == 40
    assert resultado.hora_excedente == Decimal("1.00")
    assert resultado.valor_agente == Decimal("847.00")


def test_calcular_franquia_km_zero_com_escalonamento_levanta_valueerror():
    """Guard defensivo (cinto-e-suspensório do §11.1 C9) — a calculadora PURA
    protege a divisão do §8.3 contra franquia_km=0 com escalonamento ativo.

    O model FranquiaAgente já proíbe salvar essa combinação (testado no M1), mas
    a calculadora não pode confiar só nisso: chamada à mão com franquia_km=0 +
    escalonamento_ativo=True, deve recusar ANTES da divisão razao = km/franquia_km.

    É ValueError PURO do Python (não ValidationError do Django) — a calculadora
    vive em services.py sem importar Django, justamente para ser testável sem banco.
    """
    from controle_acionamentos.services import (
        EntradaCalculoAgente,
        calcular_valor_agente,
    )

    entrada = EntradaCalculoAgente(
        valor_acionamento=Decimal("660.00"),
        franquia_km=0,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("3.30"),
        valor_hora_excedente=Decimal("55.00"),
        escalonamento_ativo=True,
        km_total=240,
        horas_total=Decimal("5.00"),
        pedagio=Decimal("0.00"),
    )

    with pytest.raises(ValueError):
        calcular_valor_agente(entrada)


# ---------------------------------------------------------------------------
# Acionamento.clean() — validações de coerência do model (RN-04/05/06 + §5.1.5)
# full_clean() (NÃO .clean()/.save()): só ele dispara os field validators E o
# Model.clean() juntos, que é o que estamos testando.
# ---------------------------------------------------------------------------


def _acionamento_valido(cliente, responsavel, agente, **overrides):
    """Monta um Acionamento VÁLIDO em tudo, com os FKs já persistidos.

    Cada teste sobrescreve só o campo da regra sob teste, de modo que um
    ValidationError só pode vir dessa regra — não de um campo obrigatório
    faltando. Espelha o padrão de `_dados_franquia`.
    """
    base = timezone.now()
    dados = dict(
        cliente=cliente,
        responsavel_agente=responsavel,
        agente=agente,
        franquia_agente=None,
        nome_servico="Reboque leve",
        valor_acionamento=Decimal("150.00"),
        franquia_km=80,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.50"),
        valor_hora_excedente=Decimal("30.00"),
        origem="São Paulo - SP",
        destino="Campinas - SP",
        data_hora_solicitado=base,
        data_hora_inicio=base + timedelta(minutes=30),
        data_hora_final=base + timedelta(hours=3),
        km_inicio=1000,
        km_final=1120,
        pedagio=Decimal("0.00"),
    )
    dados.update(overrides)
    return Acionamento(**dados)


@pytest.fixture
def _fks_acionamento(db):
    """FKs persistidos compartilhados pelos testes do Acionamento."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    responsavel = ResponsavelAgente.objects.create(nome="João Supervisor")
    agente = Agente.objects.create(nome="Carlos Agente", cpf="52998224725")
    return cliente, responsavel, agente


# — Rejeições (cada uma asserta o CAMPO específico no message_dict) —


@pytest.mark.django_db
def test_acionamento_inicio_antes_da_solicitacao_e_rejeitado(_fks_acionamento):
    """RN-04 — o início não pode ser anterior à solicitação."""
    cliente, responsavel, agente = _fks_acionamento
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        data_hora_solicitado=base,
        data_hora_inicio=base - timedelta(minutes=1),
        data_hora_final=base + timedelta(hours=3),
    )

    with pytest.raises(ValidationError) as exc:
        ac.full_clean()
    assert "data_hora_inicio" in exc.value.message_dict


@pytest.mark.django_db
def test_acionamento_final_menor_igual_inicio_e_rejeitado(_fks_acionamento):
    """RN-04 — o término deve ser posterior ao início (≤ é rejeitado)."""
    cliente, responsavel, agente = _fks_acionamento
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        data_hora_solicitado=base,
        data_hora_inicio=base + timedelta(minutes=30),
        data_hora_final=base + timedelta(minutes=30),  # igual ao início
    )

    with pytest.raises(ValidationError) as exc:
        ac.full_clean()
    assert "data_hora_final" in exc.value.message_dict


@pytest.mark.django_db
def test_acionamento_km_final_menor_que_inicio_e_rejeitado(_fks_acionamento):
    """RN-05 — o KM final não pode ser menor que o KM inicial."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(
        cliente, responsavel, agente, km_inicio=1120, km_final=1000
    )

    with pytest.raises(ValidationError) as exc:
        ac.full_clean()
    assert "km_final" in exc.value.message_dict


@pytest.mark.django_db
def test_acionamento_franquia_de_outro_cliente_e_rejeitada(_fks_acionamento):
    """RN-06 — a franquia vinculada deve pertencer ao mesmo cliente."""
    cliente, responsavel, agente = _fks_acionamento
    outro_cliente = Cliente.objects.create(
        nome_empresa="Globex", cnpj="11444777000161"
    )
    franquia_alheia = FranquiaAgente.objects.create(
        **_dados_franquia(outro_cliente)
    )
    ac = _acionamento_valido(
        cliente, responsavel, agente, franquia_agente=franquia_alheia
    )

    with pytest.raises(ValidationError) as exc:
        ac.full_clean()
    assert "franquia_agente" in exc.value.message_dict


@pytest.mark.django_db
def test_acionamento_nome_servico_vazio_e_rejeitado(_fks_acionamento):
    """§5.1.5 — nome do serviço é obrigatório (só espaços = vazio após trim)."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente, nome_servico="   ")

    with pytest.raises(ValidationError) as exc:
        ac.full_clean()
    assert "nome_servico" in exc.value.message_dict


# — Casos felizes (full_clean passa sem erro) —


@pytest.mark.django_db
def test_acionamento_valido_sem_franquia_passa(_fks_acionamento):
    """Acionamento completo, sem franquia vinculada, passa no full_clean."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente, franquia_agente=None)

    ac.full_clean()  # não deve levantar


@pytest.mark.django_db
def test_acionamento_valido_com_franquia_mesmo_cliente_passa(_fks_acionamento):
    """RN-06 — franquia do MESMO cliente é aceita."""
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente))
    ac = _acionamento_valido(
        cliente, responsavel, agente, franquia_agente=franquia
    )

    ac.full_clean()  # não deve levantar


@pytest.mark.django_db
def test_acionamento_inicio_igual_solicitado_passa(_fks_acionamento):
    """RN-04 (limite ≤) — início == solicitação é VÁLIDO; só anterior é rejeitado."""
    cliente, responsavel, agente = _fks_acionamento
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        data_hora_solicitado=base,
        data_hora_inicio=base,  # igual — está no limite permitido
        data_hora_final=base + timedelta(hours=3),
    )

    ac.full_clean()  # não deve levantar


@pytest.mark.django_db
def test_acionamento_aceita_franquia_km_zero_no_inline(_fks_acionamento):
    """DD-031 — franquia_km=0 no caminho inline (sem franquia vinculada) deve ser
    aceito. Sem franquia/escalonamento não há divisão por franquia_km, então 0 é
    válido — espelha a decisão já aplicada em FranquiaAgente (piso 0).

    Fase Red do TDD: hoje o model ainda tem MinValueValidator(1) em franquia_km,
    então full_clean() levanta ValidationError e este teste FALHA de propósito.
    """
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(
        cliente, responsavel, agente, franquia_agente=None, franquia_km=0
    )

    ac.full_clean()  # não deve levantar


# ---------------------------------------------------------------------------
# Acionamento.save() — integração: o save dispara recalcular_valor_agente e
# persiste os 5 campos calculados (RN-07, §8). create() chama o save; conferimos
# com refresh_from_db para garantir que o valor foi de fato ao banco e voltou.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_save_sem_franquia_persiste_calculados_cenario2(_fks_acionamento):
    """§11.1 Cenário 2 pela porta do model — sem franquia, valores inline estouram
    a franquia. O save deve derivar km_total/horas_total (§8.2) e gravar os
    excedentes e o valor_agente (§8.4/§8.5).

    Inline: valor=100, franquia 80km/4h, tarifas 2/30, pedágio 0.
    km_total=100 (0→100); horas_total=5 (início→final 5h depois).
    """
    cliente, responsavel, agente = _fks_acionamento
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=None,
        valor_acionamento=Decimal("100.00"),
        franquia_km=80,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.00"),
        valor_hora_excedente=Decimal("30.00"),
        pedagio=Decimal("0.00"),
        km_inicio=0,
        km_final=100,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=5),
    )
    ac.save()  # dispara recalcular_valor_agente (build + save = mesmo caminho do create)
    ac.refresh_from_db()

    assert ac.km_total == 100
    assert ac.horas_total == Decimal("5.00")
    assert ac.km_excedente == 20
    assert ac.hora_excedente == Decimal("1.00")
    assert ac.valor_agente == Decimal("170.00")


@pytest.mark.django_db
def test_save_com_franquia_faz_override_cenario3(_fks_acionamento):
    """§11.1 Cenário 3 pela porta do model — franquia vinculada do MESMO cliente,
    escalonamento ativo. A franquia faz OVERRIDE do serviço inline: o
    valor_acionamento inline (999, errado de propósito) é IGNORADO; usa-se o 660
    da franquia. km_total=240, horas_total=5, pedágio 0 → valor_agente 792,00.
    """
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(
        **_dados_franquia(
            cliente,
            valor_acionamento=Decimal("660.00"),
            franquia_km=200,
            franquia_horas=Decimal("4.00"),
            valor_km_excedente=Decimal("3.30"),
            valor_hora_excedente=Decimal("55.00"),
            escalonamento_automatico=True,
        )
    )
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=franquia,
        valor_acionamento=Decimal("999.00"),  # inline divergente de propósito
        pedagio=Decimal("0.00"),
        km_inicio=0,
        km_final=240,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=5),
    )
    ac.save()  # dispara recalcular_valor_agente (build + save = mesmo caminho do create)
    ac.refresh_from_db()

    assert ac.valor_agente == Decimal("792.00")  # prova o override: usou 660, não 999


# ---------------------------------------------------------------------------
# selectors.listar_acionamentos — listagem base (DD-014/M3, §9): leitura pela
# camada de selectors, ordenada por data_hora_solicitado DESC (mesmo default do
# Meta.ordering do model). Testa só o contrato de leitura, sem filtros ainda.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_listar_acionamentos_ordena_por_solicitacao_desc(_fks_acionamento):
    """DD-014/M3 — listar_acionamentos() devolve todos os acionamentos do mais
    recente para o mais antigo por data_hora_solicitado (§9 / AC-08.3).

    Fase Red do TDD: a função ainda não existe em selectors.py, então o import
    local levanta ImportError e este teste FALHA de propósito (import local para
    isolar o erro e não derrubar a coleta dos demais testes).
    """
    cliente, responsavel, agente = _fks_acionamento
    base = timezone.now()

    # Criados fora de ordem de propósito, para provar que quem ordena é o selector.
    ac_semana = _acionamento_valido(
        cliente, responsavel, agente, data_hora_solicitado=base - timedelta(days=7)
    )
    ac_semana.save()
    ac_hoje = _acionamento_valido(
        cliente, responsavel, agente, data_hora_solicitado=base
    )
    ac_hoje.save()
    ac_ontem = _acionamento_valido(
        cliente, responsavel, agente, data_hora_solicitado=base - timedelta(days=1)
    )
    ac_ontem.save()

    from controle_acionamentos.selectors import listar_acionamentos

    resultado = listar_acionamentos()

    assert [a.pk for a in resultado] == [ac_hoje.pk, ac_ontem.pk, ac_semana.pk]


# ---------------------------------------------------------------------------
# views.acionamento_list — listagem base, DD-014/M3 subtask 2
# View fina: login + permissão view_acionamento; consome listar_acionamentos()
# e entrega a lista ordenada no contexto ("acionamentos"). Fase Red: a rota
# "acionamento_list" ainda não existe → reverse() levanta NoReverseMatch.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_acionamento_list_anonimo_redireciona_para_login(client):
    """Sem autenticação, a listagem redireciona para o login (@login_required)."""
    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url)

    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_acionamento_list_sem_permissao_retorna_403(client, django_user_model):
    """Autenticado mas sem a permissão view_acionamento → 403 (raise_exception)."""
    user = django_user_model.objects.create_user(username="comum", password="x")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_acionamento_list_lista_ordenada_para_usuario_autorizado(
    client, django_user_model, _fks_acionamento
):
    """Com a permissão, a view responde 200 e entrega os acionamentos no contexto,
    do mais recente ao mais antigo por data_hora_solicitado (DD-014/M3)."""
    cliente, responsavel, agente = _fks_acionamento
    base = timezone.now()

    # Criados FORA da ordem de exibição (ontem antes de hoje) para provar que
    # a ordenação vem do selector, não da ordem de criação.
    ontem = _acionamento_valido(
        cliente, responsavel, agente, data_hora_solicitado=base - timedelta(days=1)
    )
    ontem.save()
    hoje = _acionamento_valido(
        cliente, responsavel, agente, data_hora_solicitado=base
    )
    hoje.save()

    user = django_user_model.objects.create_user(username="autorizado", password="x")
    perm = Permission.objects.get(
        codename="view_acionamento",
        content_type__app_label="controle_acionamentos",
    )
    user.user_permissions.add(perm)
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url)

    assert response.status_code == 200
    assert [a.pk for a in response.context["acionamentos"]] == [hoje.pk, ontem.pk]


# ---------------------------------------------------------------------------
# views.acionamento_pedagio_update — recálculo inline, DD-014/M3 subtask 4
# Endpoint POST que atualiza SÓ o pedágio de um acionamento e recalcula o
# valor_agente (pedágio soma; os excedentes não mudam). Protegido por
# change_acionamento (ver != mexer). Fase Red: a rota ainda não existe →
# reverse() levanta NoReverseMatch nos cinco testes.
# ---------------------------------------------------------------------------


def _user_com_perms(django_user_model, *codenames):
    """Cria um usuário e adiciona as Permissions do app pelos codenames.

    Evita repetir o bloco de Permission.objects.get(...) em cada teste.
    """
    user = django_user_model.objects.create_user(
        username=f"user_{'_'.join(codenames) or 'sem'}", password="x"
    )
    for codename in codenames:
        perm = Permission.objects.get(
            codename=codename,
            content_type__app_label="controle_acionamentos",
        )
        user.user_permissions.add(perm)
    return user


@pytest.mark.django_db
def test_pedagio_update_anonimo_redireciona_para_login(client, _fks_acionamento):
    """Sem autenticação, o POST redireciona para o login (@login_required)."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    url = reverse("controle_acionamentos:acionamento_pedagio_update", args=[ac.pk])
    response = client.post(url, {"pedagio": "50.00"})

    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_pedagio_update_com_view_mas_sem_change_retorna_403(
    client, django_user_model, _fks_acionamento
):
    """Granularidade: quem só tem view_acionamento NÃO pode alterar (403).
    Ver não é mexer — o endpoint exige change_acionamento."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_pedagio_update", args=[ac.pk])
    response = client.post(url, {"pedagio": "50.00"})

    assert response.status_code == 403


@pytest.mark.django_db
def test_pedagio_update_get_retorna_405(client, django_user_model, _fks_acionamento):
    """O endpoint é POST-only: GET com permissão devolve 405 (método não permitido)."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_pedagio_update", args=[ac.pk])
    response = client.get(url)

    assert response.status_code == 405


@pytest.mark.django_db
def test_pedagio_update_valido_recalcula_valor_agente_cenario6(
    client, django_user_model, _fks_acionamento
):
    """§11.1 Cenário 6 — mesmo setup do Cenário 3 (valor_agente persiste 792,00
    com pedágio 0), agora atualizando o pedágio para 50,00 via endpoint.

    O pedágio SOMA ao valor_agente (§8.5) sem mexer nos excedentes já calculados:
    792,00 + 50,00 == 842,00. O JSON traz os valores como string; o banco, Decimal.
    """
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(
        **_dados_franquia(
            cliente,
            valor_acionamento=Decimal("660.00"),
            franquia_km=200,
            franquia_horas=Decimal("4.00"),
            valor_km_excedente=Decimal("3.30"),
            valor_hora_excedente=Decimal("55.00"),
            escalonamento_automatico=True,
        )
    )
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=franquia,
        valor_acionamento=Decimal("999.00"),  # inline divergente de propósito
        pedagio=Decimal("0.00"),
        km_inicio=0,
        km_final=240,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=5),
    )
    ac.save()
    ac.refresh_from_db()

    # Guardados ANTES do update: excedentes e valor_agente base do Cenário 3.
    km_excedente_antes = ac.km_excedente
    hora_excedente_antes = ac.hora_excedente
    assert ac.valor_agente == Decimal("792.00")

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_pedagio_update", args=[ac.pk])
    response = client.post(url, {"pedagio": "50.00"})

    assert response.status_code == 200
    data = response.json()
    assert data["pedagio"] == "50.00"
    assert data["valor_agente"] == "842.00"

    ac.refresh_from_db()
    assert ac.pedagio == Decimal("50.00")
    assert ac.valor_agente == Decimal("842.00")
    # Pedágio só soma: os excedentes calculados não podem ter mudado.
    assert ac.km_excedente == km_excedente_antes
    assert ac.hora_excedente == hora_excedente_antes


@pytest.mark.django_db
def test_pedagio_update_negativo_retorna_400_e_nao_persiste(
    client, django_user_model, _fks_acionamento
):
    """AC-07.3 — pedágio negativo é rejeitado (400) e nada é persistido:
    pedágio e valor_agente ficam exatamente como estavam."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente, pedagio=Decimal("0.00"))
    ac.save()
    ac.refresh_from_db()

    pedagio_antes = ac.pedagio
    valor_agente_antes = ac.valor_agente

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_pedagio_update", args=[ac.pk])
    response = client.post(url, {"pedagio": "-10.00"})

    assert response.status_code == 400
    ac.refresh_from_db()
    assert ac.pedagio == pedagio_antes
    assert ac.valor_agente == valor_agente_antes