import pytest
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from controle_acionamentos.services import validar_cpf, validar_cnpj, validar_cnh
from controle_acionamentos.models import ResponsavelAgente, Cliente, Agente, FranquiaAgente

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