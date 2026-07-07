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


@pytest.mark.django_db
def test_listar_acionamentos_filtra_por_cliente(_fks_acionamento):
    """DD-015/M4 (AC-06.1) — listar_acionamentos(cliente=...) devolve só os
    acionamentos do cliente pedido."""
    cliente_a, responsavel, agente = _fks_acionamento
    cliente_b = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")

    # 2 acionamentos para o cliente_a e 1 para o cliente_b.
    _acionamento_valido(cliente_a, responsavel, agente).save()
    _acionamento_valido(cliente_a, responsavel, agente).save()
    _acionamento_valido(cliente_b, responsavel, agente).save()

    from controle_acionamentos.selectors import listar_acionamentos

    resultado = listar_acionamentos(cliente=cliente_a)

    assert resultado.count() == 2
    assert all(a.cliente_id == cliente_a.pk for a in resultado) is True


@pytest.mark.django_db
def test_listar_acionamentos_filtra_por_agente(_fks_acionamento):
    """DD-016/M5 (AC-08.1) — a listagem filtra por agente no selector; combina
    com os demais filtros sem quebrar a ordenação DESC."""
    cliente, responsavel, agente_a = _fks_acionamento
    agente_b = Agente.objects.create(nome="Segundo Agente", cpf="11144477735")

    # Um acionamento para cada agente, mesmo cliente.
    _acionamento_valido(cliente, responsavel, agente_a).save()
    _acionamento_valido(cliente, responsavel, agente_b).save()

    from controle_acionamentos.selectors import listar_acionamentos

    resultado = listar_acionamentos(agente=agente_a)

    assert [a.agente_id for a in resultado] == [agente_a.pk]


@pytest.mark.django_db
def test_listar_acionamentos_filtra_por_intervalo_de_data(_fks_acionamento):
    """DD-016/M5 (AC-08.1) — filtro por intervalo de data_hora_solicitado com
    fronteiras inclusivas por DATA (lookup __date): um acionamento às 14h do
    ÚLTIMO dia do intervalo DEVE aparecer."""
    cliente, responsavel, agente = _fks_acionamento
    base = timezone.now()

    def _cria(solicitado):
        # inicio/final coerentes com o solicitado escolhido (RN-04), mesmos
        # offsets do helper padrão (30min / 3h).
        ac = _acionamento_valido(
            cliente,
            responsavel,
            agente,
            data_hora_solicitado=solicitado,
            data_hora_inicio=solicitado + timedelta(minutes=30),
            data_hora_final=solicitado + timedelta(hours=3),
        )
        ac.save()
        return ac

    antes = _cria(base - timedelta(days=5))  # fora, antes do intervalo
    # Dentro E no último dia do intervalo, às 14h: prova a fronteira inclusiva
    # por DATA (uma comparação por datetime <= meia-noite o excluiria).
    dentro = _cria(base.replace(hour=14, minute=0, second=0, microsecond=0))
    depois = _cria(base + timedelta(days=5))  # fora, depois do intervalo

    from controle_acionamentos.selectors import listar_acionamentos

    resultado = listar_acionamentos(
        data_de=(base - timedelta(days=2)).date(),
        data_ate=base.date(),
    )

    assert [a.pk for a in resultado] == [dentro.pk]


@pytest.mark.django_db
@pytest.mark.parametrize("com_franquia", [True, False])
def test_listar_acionamentos_filtra_por_status_de_franquia(
    _fks_acionamento, com_franquia
):
    """DD-016/M5 (AC-08.1) — filtro por status de franquia no selector via
    booleano de domínio; None = todos (comportamento default já coberto pelos
    demais testes)."""
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia"))

    com = _acionamento_valido(cliente, responsavel, agente, franquia_agente=franquia)
    com.save()
    sem = _acionamento_valido(cliente, responsavel, agente, franquia_agente=None)
    sem.save()

    from controle_acionamentos.selectors import listar_acionamentos

    resultado = listar_acionamentos(com_franquia=com_franquia)

    esperado = com.pk if com_franquia else sem.pk
    assert [a.pk for a in resultado] == [esperado]


@pytest.mark.django_db
def test_listar_franquias_por_cliente_filtra_e_ordena_por_nome(_fks_acionamento):
    """DD-015/M4 (AC-06.3) — select de franquias do vínculo em lote mostra só
    franquias do cliente filtrado, em ordem alfabética (ordering explícito no
    selector, nunca Meta.ordering)."""
    cliente_a, responsavel, agente = _fks_acionamento
    cliente_b = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")

    # No cliente A, duas franquias fora de ordem alfabética (Zeta antes de Alfa),
    # para provar que a ordenação vem do selector, não da ordem de criação.
    zeta = FranquiaAgente.objects.create(**_dados_franquia(cliente_a, nome="Zeta"))
    alfa = FranquiaAgente.objects.create(**_dados_franquia(cliente_a, nome="Alfa"))
    # No cliente B, uma franquia qualquer (não pode aparecer no resultado de A).
    FranquiaAgente.objects.create(**_dados_franquia(cliente_b, nome="Beta"))

    from controle_acionamentos.selectors import listar_franquias_por_cliente

    resultado = listar_franquias_por_cliente(cliente_a)

    # Só as franquias do cliente A, em ordem alfabética por nome.
    assert [f.pk for f in resultado] == [alfa.pk, zeta.pk]


# ---------------------------------------------------------------------------
# services.vincular_franquia_em_lote — vínculo de franquia em lote (DD-015/M4
# subtask 3). Vincula uma FranquiaAgente a vários acionamentos de uma vez e
# recalcula os campos derivados de cada um (override da franquia), em transação
# atômica: falha em qualquer item desfaz o lote inteiro (AC-06.6).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_vincular_franquia_em_lote_vincula_e_recalcula_cenario7(_fks_acionamento):
    """DD-015/M4 (AC-06.4, cenário 7) — o lote vincula a franquia a todos os
    acionamentos e recalcula km_excedente/hora_excedente/valor_agente de cada um.

    Franquia e valores esperados espelham o cenário 3 (override → 792,00, sem
    excedentes): cada acionamento nasce SEM franquia e, após o lote, passa a
    apontar para ela e recalcula pelo override.
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

    # 3 acionamentos SEM franquia, mas com km/tempo do cenário 3 (240 km, 5 h),
    # para que o override recalcule cada um para 792,00 sem excedentes.
    acionamentos = []
    for _ in range(3):
        ac = _acionamento_valido(
            cliente,
            responsavel,
            agente,
            franquia_agente=None,
            km_inicio=0,
            km_final=240,
            data_hora_solicitado=base,
            data_hora_inicio=base,
            data_hora_final=base + timedelta(hours=5),
        )
        ac.save()
        acionamentos.append(ac)

    from controle_acionamentos.services import vincular_franquia_em_lote

    resultado = vincular_franquia_em_lote([a.pk for a in acionamentos], franquia)

    assert resultado == 3
    for ac in acionamentos:
        ac.refresh_from_db()
        assert ac.franquia_agente_id == franquia.pk
        assert ac.km_excedente == 0
        assert ac.hora_excedente == Decimal("0.00")
        assert ac.valor_agente == Decimal("792.00")


@pytest.mark.django_db
def test_vincular_franquia_em_lote_cross_cliente_desfaz_tudo_cenario8(_fks_acionamento):
    """DD-015/M4 (cenário 8, RN-06) — franquia de cliente diferente é rejeitada
    e NADA persiste: a falha de um item desfaz o lote inteiro (AC-06.6). A prova
    determinística do rollback de escritas já efetuadas é do teste de falha no
    meio do lote (critério global 5, §12)."""
    cliente_a, responsavel, agente = _fks_acionamento
    cliente_b = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")

    # Franquia do cliente_a (mesmo arranjo do cenário 7).
    franquia = FranquiaAgente.objects.create(
        **_dados_franquia(
            cliente_a,
            valor_acionamento=Decimal("660.00"),
            franquia_km=200,
            franquia_horas=Decimal("4.00"),
            valor_km_excedente=Decimal("3.30"),
            valor_hora_excedente=Decimal("55.00"),
            escalonamento_automatico=True,
        )
    )
    base = timezone.now()

    def _cria(cli):
        ac = _acionamento_valido(
            cli,
            responsavel,
            agente,
            franquia_agente=None,
            km_inicio=0,
            km_final=240,
            data_hora_solicitado=base,
            data_hora_inicio=base,
            data_hora_final=base + timedelta(hours=5),
        )
        ac.save()
        ac.refresh_from_db()
        return ac

    valido1 = _cria(cliente_a)
    valido2 = _cria(cliente_a)
    invalido = _cria(cliente_b)  # cross-cliente: viola RN-06 ao receber a franquia

    # valor_agente original de cada um ANTES do lote (todos SEM franquia ainda).
    originais = {ac.pk: ac.valor_agente for ac in (valido1, valido2, invalido)}

    from controle_acionamentos.services import vincular_franquia_em_lote

    # A ordem de iteração não é garantida (o filter segue o ordering do model),
    # mas o resultado é o mesmo em qualquer ordem: ao primeiro erro, nada persiste.
    with pytest.raises(ValidationError):
        vincular_franquia_em_lote([valido1.pk, valido2.pk, invalido.pk], franquia)

    # Nada persistiu — nem os válidos processados antes da falha (rollback do lote).
    for ac in (valido1, valido2, invalido):
        ac.refresh_from_db()
        assert ac.franquia_agente_id is None
        assert ac.valor_agente == originais[ac.pk]


@pytest.mark.django_db
def test_vincular_franquia_em_lote_sem_flag_nao_sobrescreve_ac065(_fks_acionamento):
    """DD-015/M4 (AC-06.5) — item que já possui franquia vinculada só pode ser
    sobrescrito com confirmação explícita: sem sobrescrever=True, o service
    levanta ValidationError e nada persiste (nem os itens sem franquia)."""
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

    def _cria(franquia_agente=None):
        ac = _acionamento_valido(
            cliente,
            responsavel,
            agente,
            franquia_agente=franquia_agente,
            km_inicio=0,
            km_final=240,
            data_hora_solicitado=base,
            data_hora_inicio=base,
            data_hora_final=base + timedelta(hours=5),
        )
        ac.save()
        ac.refresh_from_db()
        return ac

    livre1 = _cria()
    livre2 = _cria()
    ja_vinculado = _cria(franquia_agente=franquia)  # já nasce com a franquia

    # valor_agente original dos 2 SEM franquia, antes do lote.
    originais = {ac.pk: ac.valor_agente for ac in (livre1, livre2)}

    from controle_acionamentos.services import vincular_franquia_em_lote

    # SEM sobrescrever: o default deve ser o caminho seguro (recusa e desfaz tudo).
    with pytest.raises(ValidationError):
        vincular_franquia_em_lote([livre1.pk, livre2.pk, ja_vinculado.pk], franquia)

    # Nada persistiu: nem os livres, nem alteração no já vinculado.
    for ac in (livre1, livre2):
        ac.refresh_from_db()
        assert ac.franquia_agente_id is None
        assert ac.valor_agente == originais[ac.pk]

    ja_vinculado.refresh_from_db()
    assert ja_vinculado.franquia_agente_id == franquia.pk


@pytest.mark.django_db
def test_vincular_franquia_em_lote_com_flag_sobrescreve_ac065(_fks_acionamento):
    """DD-015/M4 (AC-06.5) — com sobrescrever=True, itens que já possuem
    franquia são re-vinculados e recalculados junto com os demais."""
    cliente, responsavel, agente = _fks_acionamento

    # Duas franquias do MESMO cliente; nomes distintos (unicidade cliente+nome).
    # A nova muda só o valor_acionamento (700), para o recálculo ser observável.
    franquia_antiga = FranquiaAgente.objects.create(
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
    franquia_nova = FranquiaAgente.objects.create(
        **_dados_franquia(
            cliente,
            nome="Franquia Nova 200km/4h",
            valor_acionamento=Decimal("700.00"),
            franquia_km=200,
            franquia_horas=Decimal("4.00"),
            valor_km_excedente=Decimal("3.30"),
            valor_hora_excedente=Decimal("55.00"),
            escalonamento_automatico=True,
        )
    )
    base = timezone.now()

    def _cria(franquia_agente=None):
        ac = _acionamento_valido(
            cliente,
            responsavel,
            agente,
            franquia_agente=franquia_agente,
            km_inicio=0,
            km_final=240,
            data_hora_solicitado=base,
            data_hora_inicio=base,
            data_hora_final=base + timedelta(hours=5),
        )
        ac.save()
        ac.refresh_from_db()
        return ac

    livre1 = _cria()
    livre2 = _cria()
    ja_vinculado = _cria(franquia_agente=franquia_antiga)

    from controle_acionamentos.services import vincular_franquia_em_lote

    resultado = vincular_franquia_em_lote(
        [livre1.pk, livre2.pk, ja_vinculado.pk],
        franquia_nova,
        sobrescrever=True,
    )

    assert resultado == 3
    # Escalonamento da franquia_nova: 700 × (240/200) == 840,00, sem excedentes.
    for ac in (livre1, livre2, ja_vinculado):
        ac.refresh_from_db()
        assert ac.franquia_agente_id == franquia_nova.pk
        assert ac.valor_agente == Decimal("840.00")


@pytest.mark.django_db
def test_vincular_franquia_em_lote_falha_no_meio_desfaz_tudo(_fks_acionamento, monkeypatch):
    """DD-015/M4 (critério global 5, §12) — prova determinística do rollback:
    o 1º item do lote é salvo com sucesso DENTRO da transação; o 2º save
    explode; o atomic desfaz tudo, inclusive a escrita já efetuada."""
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

    # 3 acionamentos SEM franquia (mesmo arranjo dos testes de lote: 240 km, 5 h).
    acionamentos = []
    for _ in range(3):
        ac = _acionamento_valido(
            cliente,
            responsavel,
            agente,
            franquia_agente=None,
            km_inicio=0,
            km_final=240,
            data_hora_solicitado=base,
            data_hora_inicio=base,
            data_hora_final=base + timedelta(hours=5),
        )
        ac.save()
        ac.refresh_from_db()
        acionamentos.append(ac)

    a1, a2, a3 = acionamentos
    # valor_agente original dos 3 (todos SEM franquia), antes do lote.
    originais = {ac.pk: ac.valor_agente for ac in acionamentos}

    # Sabotagem: só DEPOIS do arrange (os saves acima não podem contar). Embrulha
    # Acionamento.save para explodir na 2ª chamada — a 1ª executa o save real,
    # provando que houve escrita dentro da transação antes da falha.
    save_original = Acionamento.save
    chamadas = {"n": 0}

    def save_sabotado(self, *args, **kwargs):
        chamadas["n"] += 1
        if chamadas["n"] == 2:
            raise RuntimeError("falha simulada no meio do lote")
        return save_original(self, *args, **kwargs)

    monkeypatch.setattr(Acionamento, "save", save_sabotado)

    from controle_acionamentos.services import vincular_franquia_em_lote

    with pytest.raises(RuntimeError):
        vincular_franquia_em_lote([a1.pk, a2.pk, a3.pk], franquia)

    # O 1º save real aconteceu (chamada 1) e a 2ª disparou a falha.
    assert chamadas["n"] == 2

    # Nada persistiu: a 1ª escrita foi desfeita junto com o lote inteiro.
    for ac in acionamentos:
        ac.refresh_from_db()
        assert ac.franquia_agente_id is None
        assert ac.valor_agente == originais[ac.pk]


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


@pytest.mark.django_db
def test_acionamento_list_filtra_por_cliente_via_get(
    client, django_user_model, _fks_acionamento
):
    """DD-015/M4 (AC-06.1) — a listagem aceita ?cliente=<pk> no GET e devolve só
    os acionamentos daquele cliente, expondo o cliente escolhido no contexto
    (cliente_filtrado) para a UI marcar o filtro ativo."""
    cliente_a, responsavel, agente = _fks_acionamento
    cliente_b = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")

    ac_a = _acionamento_valido(cliente_a, responsavel, agente)
    ac_a.save()
    ac_b = _acionamento_valido(cliente_b, responsavel, agente)
    ac_b.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url, {"cliente": cliente_a.pk})

    assert response.status_code == 200
    # Só o acionamento do cliente A (comparar pks, nunca HTML).
    assert [a.pk for a in response.context["acionamentos"]] == [ac_a.pk]
    # E a view expõe qual cliente está filtrando.
    assert response.context["cliente_filtrado"] == cliente_a


@pytest.mark.django_db
@pytest.mark.parametrize("valor_querystring", ["9999", "abc"])
def test_acionamento_list_filtro_invalido_e_tolerante(
    client, django_user_model, _fks_acionamento, valor_querystring
):
    """DD-015/M4 — caracterização do filtro TOLERANTE (decisão registrada):
    querystring inválida (pk inexistente ou não numérica) = sem filtro, nunca
    erro. A view responde 200 com a lista completa e cliente_filtrado None."""
    cliente, responsavel, agente = _fks_acionamento

    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url, {"cliente": valor_querystring})

    assert response.status_code == 200  # nunca 404
    # Filtro ignorado → lista completa (o acionamento existente aparece).
    assert [a.pk for a in response.context["acionamentos"]] == [ac.pk]
    assert response.context["cliente_filtrado"] is None


@pytest.mark.django_db
def test_acionamento_list_com_cliente_filtrado_expoe_franquias_do_cliente(
    client, django_user_model, _fks_acionamento
):
    """DD-015/M4 (AC-06.2/06.3) — com cliente filtrado, a view expõe as
    franquias daquele cliente (via listar_franquias_por_cliente) para o
    select do vínculo em lote."""
    cliente_a, responsavel, agente = _fks_acionamento
    cliente_b = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")

    franquia_a = FranquiaAgente.objects.create(
        **_dados_franquia(cliente_a, nome="Franquia A")
    )
    FranquiaAgente.objects.create(**_dados_franquia(cliente_b, nome="Franquia B"))

    ac = _acionamento_valido(cliente_a, responsavel, agente)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url, {"cliente": cliente_a.pk})

    assert response.status_code == 200
    # Só a franquia do cliente A no select (comparar pks, nunca HTML).
    assert [f.pk for f in response.context["franquias"]] == [franquia_a.pk]


@pytest.mark.django_db
def test_acionamento_list_sem_cliente_filtrado_franquias_vazio(
    client, django_user_model, _fks_acionamento
):
    """DD-015/M4 — caracterização do contrato de contexto (decisão registrada):
    sem cliente filtrado, "franquias" é queryset vazio; quem liga a UI de lote é
    cliente_filtrado, não a presença da chave."""
    cliente, responsavel, agente = _fks_acionamento

    FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia X"))
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url)  # SEM querystring

    assert response.status_code == 200
    assert response.context["cliente_filtrado"] is None
    # A chave existe e está vazia, mesmo havendo franquia no banco.
    assert list(response.context["franquias"]) == []


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


@pytest.mark.django_db
def test_pedagio_update_nao_afeta_outras_linhas_ac074(
    client, django_user_model, _fks_acionamento
):
    """AC-07.4 — o update de pedágio é isolado por linha: atualizar um acionamento
    não pode tocar em nenhum outro. Dois acionamentos; só o alvo recebe o POST, e
    o vizinho tem de sair exatamente como entrou (pedágio e valor_agente)."""
    cliente, responsavel, agente = _fks_acionamento
    ac_alvo = _acionamento_valido(
        cliente, responsavel, agente, pedagio=Decimal("0.00")
    )
    ac_alvo.save()
    ac_vizinho = _acionamento_valido(
        cliente, responsavel, agente, pedagio=Decimal("0.00")
    )
    ac_vizinho.save()

    ac_alvo.refresh_from_db()
    ac_vizinho.refresh_from_db()
    pedagio_vizinho_antes = ac_vizinho.pedagio
    valor_agente_vizinho_antes = ac_vizinho.valor_agente

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_pedagio_update", args=[ac_alvo.pk])
    response = client.post(url, {"pedagio": "50.00"})

    assert response.status_code == 200

    ac_alvo.refresh_from_db()
    ac_vizinho.refresh_from_db()
    # A linha alvo mudou...
    assert ac_alvo.pedagio == Decimal("50.00")
    # ...e a vizinha ficou intocada (coração do AC-07.4).
    assert ac_vizinho.pedagio == pedagio_vizinho_antes
    assert ac_vizinho.valor_agente == valor_agente_vizinho_antes


# ---------------------------------------------------------------------------
# views.acionamento_vincular_franquia_lote — vínculo em lote, DD-015/M4 subtask 5
# Endpoint POST que vincula uma franquia a vários acionamentos de uma vez,
# delegando ao service vincular_franquia_em_lote (atômico). Ação de lote: a
# rota NÃO tem <pk>. Fase Red: a rota ainda não existe → reverse() levanta
# NoReverseMatch.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_vincular_franquia_lote_anonimo_redireciona_para_login(client, db):
    """DD-015/M4 (subtask 5) — POST anônimo no endpoint de vínculo em lote
    redireciona para login (@login_required)."""
    url = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")
    response = client.post(url)

    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_vincular_franquia_lote_com_view_mas_sem_change_retorna_403(
    client, django_user_model
):
    """DD-015/M4 (subtask 5) — usuário com view_acionamento mas sem
    change_acionamento recebe 403 (ver ≠ mexer)."""
    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")
    response = client.post(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_vincular_franquia_lote_get_retorna_405(client, django_user_model):
    """DD-015/M4 (subtask 5) — GET no endpoint de lote retorna 405
    (@require_POST; ordem dos decorators garante 403 antes de 405 para
    quem não tem permissão)."""
    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")
    response = client.get(url)

    assert response.status_code == 405


@pytest.mark.django_db
def test_vincular_franquia_lote_post_valido_vincula_e_redireciona_com_filtro(
    client, django_user_model, _fks_acionamento
):
    """DD-015/M4 (AC-06.6 + subtask 5) — POST válido vincula via service,
    redireciona para a listagem PRESERVANDO o filtro por cliente na
    querystring (?cliente=<pk da franquia.cliente>) e emite message de
    sucesso com a contagem."""
    from django.contrib.messages import get_messages

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

    # 3 acionamentos SEM franquia (240 km, 5 h) → override recalcula p/ 792,00.
    acionamentos = []
    for _ in range(3):
        ac = _acionamento_valido(
            cliente,
            responsavel,
            agente,
            franquia_agente=None,
            km_inicio=0,
            km_final=240,
            data_hora_solicitado=base,
            data_hora_inicio=base,
            data_hora_final=base + timedelta(hours=5),
        )
        ac.save()
        acionamentos.append(ac)
    a1, a2, a3 = acionamentos

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")
    response = client.post(
        url,
        {
            "acionamentos": [a1.pk, a2.pk, a3.pk],
            "franquia": franquia.pk,
        },
    )

    assert response.status_code == 302
    assert response.url == (
        reverse("controle_acionamentos:acionamento_list")
        + f"?cliente={franquia.cliente_id}"
    )

    for ac in acionamentos:
        ac.refresh_from_db()
        assert ac.franquia_agente_id == franquia.pk
        assert ac.valor_agente == Decimal("792.00")

    mensagens = list(get_messages(response.wsgi_request))
    assert len(mensagens) == 1
    assert "3" in str(mensagens[0])


@pytest.mark.django_db
def test_vincular_franquia_lote_erro_de_dominio_redireciona_com_filtro_e_message(
    client, django_user_model, _fks_acionamento
):
    """DD-015/M4 (subtask 5) — quando o service recusa o lote por erro TERMINAL
    (aqui: franquia de outro cliente, RN-06), a view traduz em message de erro e
    redireciona PRESERVANDO o filtro (?cliente=...); nada persiste. (O conflito
    de sobrescrita sem flag NÃO é erro terminal — vira confirmação, AC-06.5.)"""
    from django.contrib.messages import get_messages, constants as message_constants

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
    cliente_b = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")
    base = timezone.now()

    def _cria(cli):
        ac = _acionamento_valido(
            cli,
            responsavel,
            agente,
            franquia_agente=None,
            km_inicio=0,
            km_final=240,
            data_hora_solicitado=base,
            data_hora_inicio=base,
            data_hora_final=base + timedelta(hours=5),
        )
        ac.save()
        ac.refresh_from_db()
        return ac

    valido = _cria(cliente)       # mesmo cliente da franquia
    invalido = _cria(cliente_b)   # cross-cliente: viola RN-06 ao receber a franquia

    # valor_agente original de cada um (ambos SEM franquia), antes do POST.
    originais = {ac.pk: ac.valor_agente for ac in (valido, invalido)}

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")
    response = client.post(
        url,
        {
            "acionamentos": [valido.pk, invalido.pk],
            "franquia": franquia.pk,
        },  # SEM sobrescrever; erro TERMINAL é o cross-cliente (RN-06), não sobrescrita
    )

    assert response.status_code == 302
    assert response.url == (
        reverse("controle_acionamentos:acionamento_list")
        + f"?cliente={franquia.cliente_id}"
    )

    # Nada persistiu: rollback atômico do lote (AC-06.6) — nem o válido.
    for ac in (valido, invalido):
        ac.refresh_from_db()
        assert ac.franquia_agente_id is None
        assert ac.valor_agente == originais[ac.pk]

    mensagens = list(get_messages(response.wsgi_request))
    assert len(mensagens) == 1
    assert mensagens[0].level == message_constants.ERROR


@pytest.mark.django_db
def test_vincular_franquia_lote_entrada_invalida_redireciona_com_message_de_erro(
    client, django_user_model
):
    """DD-015/M4 (subtask 5) — POST com payload inválido (ids inexistentes)
    não estoura 500: o form rejeita, a view emite message de erro e
    redireciona para a listagem (sem querystring — sem franquia válida,
    não há cliente para derivar o filtro)."""
    from django.contrib.messages import get_messages, constants as message_constants

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")
    response = client.post(
        url,
        {
            "acionamentos": [99991, 99992],  # pks inexistentes de propósito
            "franquia": 99999,
        },
    )

    assert response.status_code == 302
    # Sem franquia válida não há cliente para derivar o filtro → redirect seco.
    assert response.url == reverse("controle_acionamentos:acionamento_list")

    mensagens = list(get_messages(response.wsgi_request))
    assert len(mensagens) == 1
    assert mensagens[0].level == message_constants.ERROR


@pytest.mark.django_db
def test_vincular_franquia_lote_conflito_sem_flag_renderiza_confirmacao(
    client, django_user_model, _fks_acionamento
):
    """DD-015/M4 (AC-06.5) — conflito de sobrescrita sem flag não executa nem
    redireciona: renderiza página de confirmação em duas etapas (padrão
    delete-confirm)."""
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia"))
    base = timezone.now()

    def _cria(franquia_agente=None):
        ac = _acionamento_valido(
            cliente,
            responsavel,
            agente,
            franquia_agente=franquia_agente,
            km_inicio=0,
            km_final=240,
            data_hora_solicitado=base,
            data_hora_inicio=base,
            data_hora_final=base + timedelta(hours=5),
        )
        ac.save()
        ac.refresh_from_db()
        return ac

    ja_vinculado = _cria(franquia_agente=franquia)  # já nasce com a franquia
    livre = _cria()  # sem franquia

    user = _user_com_perms(
        django_user_model, "view_acionamento", "change_acionamento"
    )
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")
    response = client.post(
        url,
        {
            "acionamentos": [ja_vinculado.pk, livre.pk],
            "franquia": franquia.pk,
        },  # SEM sobrescrever → conflito exige confirmação
    )

    # Não redireciona (comportamento novo): renderiza a confirmação.
    assert response.status_code == 200
    assert (
        "controle_acionamentos/acionamento_vincular_confirmar.html"
        in [t.name for t in response.templates]
    )

    # Nada foi executado ainda: o livre continua sem franquia.
    livre.refresh_from_db()
    assert livre.franquia_agente_id is None


@pytest.mark.django_db
def test_vincular_franquia_lote_confirmado_sobrescreve_e_redireciona(
    client, django_user_model, _fks_acionamento
):
    """DD-015/M4 (AC-06.5, etapa 2) — POST confirmado com sobrescrever executa a
    troca de franquia, recalcula e redireciona com sucesso. Fecha o teste
    pendente registrado: sobrescrever=True pela view."""
    from django.contrib.messages import get_messages, constants as message_constants

    cliente, responsavel, agente = _fks_acionamento
    franquia_antiga = FranquiaAgente.objects.create(
        **_dados_franquia(
            cliente,
            nome="Franquia Antiga",
            valor_acionamento=Decimal("660.00"),
            franquia_km=200,
            franquia_horas=Decimal("4.00"),
            valor_km_excedente=Decimal("3.30"),
            valor_hora_excedente=Decimal("55.00"),
            escalonamento_automatico=True,
        )
    )
    franquia_nova = FranquiaAgente.objects.create(
        **_dados_franquia(
            cliente,
            nome="Franquia Nova",
            valor_acionamento=Decimal("700.00"),
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
        franquia_agente=franquia_antiga,  # já vinculado à ANTIGA
        km_inicio=0,
        km_final=240,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=5),
    )
    ac.save()
    ac.refresh_from_db()
    valor_original = ac.valor_agente

    user = _user_com_perms(
        django_user_model, "view_acionamento", "change_acionamento"
    )
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")
    response = client.post(
        url,
        {
            "acionamentos": [ac.pk],
            "franquia": franquia_nova.pk,
            "sobrescrever": "on",  # simula o submit da página de confirmação
        },
    )

    assert response.status_code == 302
    assert response.url == (
        reverse("controle_acionamentos:acionamento_list")
        + f"?cliente={franquia_nova.cliente_id}"
    )

    ac.refresh_from_db()
    assert ac.franquia_agente_id == franquia_nova.pk
    # Recálculo executado: o valor mudou em relação ao da franquia antiga.
    assert ac.valor_agente != valor_original

    mensagens = list(get_messages(response.wsgi_request))
    assert len(mensagens) == 1
    assert mensagens[0].level == message_constants.SUCCESS


@pytest.mark.django_db
def test_confirmacao_etapa1_reenvia_hidden_fieis_para_etapa2(
    client, django_user_model, _fks_acionamento
):
    """DD-015/M4 (subtask 6) — contrato etapa 1 → etapa 2: os hidden do template
    de confirmação reproduzem fielmente o POST que executa a sobrescrita. Fecha
    a lacuna 5 da auditoria de cobertura."""
    import re
    from collections import defaultdict
    from django.contrib.messages import get_messages, constants as message_constants

    cliente, responsavel, agente = _fks_acionamento
    franquia_antiga = FranquiaAgente.objects.create(
        **_dados_franquia(
            cliente,
            nome="Franquia Antiga",
            valor_acionamento=Decimal("660.00"),
            franquia_km=200,
            franquia_horas=Decimal("4.00"),
            valor_km_excedente=Decimal("3.30"),
            valor_hora_excedente=Decimal("55.00"),
            escalonamento_automatico=True,
        )
    )
    franquia_nova = FranquiaAgente.objects.create(
        **_dados_franquia(
            cliente,
            nome="Franquia Nova",
            valor_acionamento=Decimal("700.00"),
            franquia_km=200,
            franquia_horas=Decimal("4.00"),
            valor_km_excedente=Decimal("3.30"),
            valor_hora_excedente=Decimal("55.00"),
            escalonamento_automatico=True,
        )
    )
    base = timezone.now()

    def _cria(franquia_agente=None):
        ac = _acionamento_valido(
            cliente,
            responsavel,
            agente,
            franquia_agente=franquia_agente,
            km_inicio=0,
            km_final=240,
            data_hora_solicitado=base,
            data_hora_inicio=base,
            data_hora_final=base + timedelta(hours=5),
        )
        ac.save()
        ac.refresh_from_db()
        return ac

    ja_vinculado = _cria(franquia_agente=franquia_antiga)
    livre = _cria()

    user = _user_com_perms(
        django_user_model, "view_acionamento", "change_acionamento"
    )
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")

    # Etapa 1: conflito sem flag → página de confirmação (200).
    resp1 = client.post(
        url,
        {"acionamentos": [ja_vinculado.pk, livre.pk], "franquia": franquia_nova.pk},
    )
    assert resp1.status_code == 200

    # Extrai os <input type="hidden"> de DENTRO do form de confirmação (escopo
    # pelo action, para não pegar o csrf de header/outros forms da página).
    html = resp1.content.decode()
    form_m = re.search(
        r'<form[^>]*action="' + re.escape(url) + r'"[^>]*>(.*?)</form>',
        html,
        re.DOTALL,
    )
    assert form_m, "form de confirmação não encontrado no HTML"
    form_html = form_m.group(1)

    dados_etapa2 = defaultdict(list)
    for tag in re.findall(r'<input[^>]*type="hidden"[^>]*>', form_html):
        nome = re.search(r'name="([^"]+)"', tag)
        valor = re.search(r'value="([^"]*)"', tag)
        if nome:
            dados_etapa2[nome.group(1)].append(valor.group(1) if valor else "")

    # Assert intermediário: os hidden reproduzem o POST de execução.
    assert set(dados_etapa2["acionamentos"]) == {str(ja_vinculado.pk), str(livre.pk)}
    assert dados_etapa2["franquia"] == [str(franquia_nova.pk)]
    assert "sobrescrever" in dados_etapa2

    # Etapa 2: reenvia EXATAMENTE o extraído (não montado à mão).
    resp2 = client.post(url, dict(dados_etapa2))

    assert resp2.status_code == 302
    assert resp2.url == (
        reverse("controle_acionamentos:acionamento_list")
        + f"?cliente={franquia_nova.cliente_id}"
    )

    # Os DOIS acionamentos passaram para a franquia nova (sobrescrita executada).
    for ac in (ja_vinculado, livre):
        ac.refresh_from_db()
        assert ac.franquia_agente_id == franquia_nova.pk

    mensagens = list(get_messages(resp2.wsgi_request))
    assert len(mensagens) == 1
    assert mensagens[0].level == message_constants.SUCCESS