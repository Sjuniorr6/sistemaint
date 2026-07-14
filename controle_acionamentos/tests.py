import pytest
import time
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlparse, parse_qs

from django.contrib.auth import get_user_model
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


def test_cnh_dv1_estoura_vira_zero_com_desconto():
    """dv1 >= 10 (soma1 % 11 == 10) → dv1 = 0 e marca desconto=2 (services.py 126-127).

    Base 816184959: soma1 = 230, 230 % 11 = 10 → dv1 = 0; soma2 = 280,
    280 % 11 = 5, dv2 = 5 - 2 = 3. CNH válida = base + '0' + '3'.
    """
    assert validar_cnh('81618495903') is True


def test_cnh_dv2_negativo_soma_onze():
    """dv2 < 0 após o desconto → dv2 += 11 (services.py 136), ainda com dv1 estourado.

    Base 104332181: soma1 = 98, 98 % 11 = 10 → dv1 = 0, desconto=2;
    soma2 = 132, 132 % 11 = 0, dv2 = 0 - 2 = -2 → +11 = 9. CNH válida = base + '0' + '9'.
    """
    assert validar_cnh('10433218109') is True


def test_cnh_dv2_estoura_vira_zero():
    """dv2 >= 10 (soma2 % 11 == 10, sem desconto) → dv2 = 0 (services.py 138).

    Base 627048281: soma1 = 194, 194 % 11 = 7 → dv1 = 7 (desconto=0);
    soma2 = 186, 186 % 11 = 10 → dv2 = 10 → 0. CNH válida = base + '7' + '0'.
    """
    assert validar_cnh('62704828170') is True


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


# ---------------------------------------------------------------------------
# services.compor_valor_agente — extrato de parcelas do detalhe (DD-032/ST5).
# Recompõe as parcelas do cálculo (base ajustada, subtotais de excedente às
# tarifas da FONTE resolvida — franquia quando vinculada, RN-08 — e pedágio) SEM
# persistir nada. Invariante central: a soma das parcelas == valor_agente já
# persistido. Recebe instância com FKs, por isso @pytest.mark.django_db.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_compor_valor_agente_inline_sem_franquia_parcelas_batem(_fks_acionamento):
    """DD-032/ST5 — extrato do acionamento INLINE (sem franquia), cenário C2:
    excedentes cobrados às tarifas do próprio acionamento; blocos=0; a soma das
    parcelas fecha o valor_agente persistido.

    Arrange do C2 (inline valor=100, franquia 80km/4h, tarifas 2/30, pedágio 0;
    km_total=100, horas_total=5) → valor_agente 170,00.

    Fase RED do TDD: compor_valor_agente ainda não existe em services.py, então
    o import local levanta ImportError e este teste FALHA de propósito.
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
    ac.save()  # persiste os calculados (valor_agente == 170,00)

    from controle_acionamentos.services import compor_valor_agente

    comp = compor_valor_agente(ac)

    assert comp.fonte_franquia is False
    assert comp.blocos == 0
    assert comp.valor_acionamento_ajustado == Decimal("100.00")
    # Subtotais == quantidade × tarifa (tarifa inline, pois não há franquia).
    assert comp.km_excedente == 20
    assert comp.valor_unitario_km == Decimal("2.00")
    assert comp.subtotal_km == comp.km_excedente * comp.valor_unitario_km
    assert comp.hora_excedente == Decimal("1.00")
    assert comp.valor_unitario_hora == Decimal("30.00")
    assert comp.subtotal_hora == comp.hora_excedente * comp.valor_unitario_hora
    assert comp.pedagio == Decimal("0.00")
    # INVARIANTE: soma das parcelas == total == valor_agente persistido.
    soma = (
        comp.valor_acionamento_ajustado
        + comp.subtotal_km
        + comp.subtotal_hora
        + comp.pedagio
    )
    assert soma == comp.valor_agente == ac.valor_agente == Decimal("170.00")


@pytest.mark.django_db
def test_compor_valor_agente_franquia_escalonada_usa_tarifas_da_franquia(_fks_acionamento):
    """DD-032/ST5 — extrato com FRANQUIA escalonável (cenário C4, 2 blocos): as
    tarifas unitárias vêm da FRANQUIA (RN-08), não dos campos inline do
    acionamento — a armadilha do override.

    O acionamento recebe tarifas inline DIVERGENTES de propósito (1,00) para
    provar que compor usa a tarifa da franquia (3,30), não a do acionamento.

    Arrange do C4 (franquia 200km/4h, R$660, tarifas 3,30/55, escalonamento ON;
    km_total=285, horas_total=7, pedágio 50) → valor_agente 1.045,50.

    Fase RED do TDD: compor_valor_agente ainda não existe → ImportError.
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
        # Inline divergente de propósito: prova que a tarifa usada é a da franquia.
        valor_km_excedente=Decimal("1.00"),
        valor_hora_excedente=Decimal("1.00"),
        pedagio=Decimal("50.00"),
        km_inicio=0,
        km_final=285,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=7),
    )
    ac.save()  # override da franquia → valor_agente 1.045,50

    from controle_acionamentos.services import compor_valor_agente

    comp = compor_valor_agente(ac)

    assert comp.fonte_franquia is True
    assert comp.blocos == 2
    assert comp.valor_acionamento_ajustado == Decimal("924.00")
    # RN-08: tarifa DA FRANQUIA (3,30), não a inline divergente (1,00).
    assert comp.valor_unitario_km == franquia.valor_km_excedente == Decimal("3.30")
    assert comp.valor_unitario_hora == franquia.valor_hora_excedente == Decimal("55.00")
    assert comp.km_excedente == 5
    assert comp.hora_excedente == Decimal("1.00")
    assert comp.subtotal_km == comp.km_excedente * comp.valor_unitario_km
    assert comp.subtotal_hora == comp.hora_excedente * comp.valor_unitario_hora
    # INVARIANTE: soma das parcelas == total == valor_agente persistido.
    soma = (
        comp.valor_acionamento_ajustado
        + comp.subtotal_km
        + comp.subtotal_hora
        + comp.pedagio
    )
    assert soma == comp.valor_agente == ac.valor_agente == Decimal("1045.50")


@pytest.mark.django_db
def test_compor_valor_agente_soma_das_parcelas_e_igual_ao_persistido(_fks_acionamento):
    """DD-032/ST5 — cenário C3 (franquia, 1 bloco EXATO, sem excedentes): os
    subtotais de excedente são zero e a soma das parcelas fecha o valor_agente
    persistido.

    Arrange do C3 (franquia 200km/4h, R$660, tarifas 3,30/55, escalonamento ON;
    km_total=240, horas_total=5, pedágio 0) → escalona 1 bloco exato, sem
    excedente residual, valor_agente 792,00.

    Fase RED do TDD: compor_valor_agente ainda não existe → ImportError.
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
        pedagio=Decimal("0.00"),
        km_inicio=0,
        km_final=240,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=5),
    )
    ac.save()  # 1 bloco exato → valor_agente 792,00

    from controle_acionamentos.services import compor_valor_agente

    comp = compor_valor_agente(ac)

    assert comp.fonte_franquia is True
    assert comp.blocos == 1
    # Sem excedente residual: quantidades e subtotais zerados.
    assert comp.km_excedente == 0
    assert comp.hora_excedente == Decimal("0.00")
    assert comp.subtotal_km == Decimal("0")
    assert comp.subtotal_hora == Decimal("0")
    # INVARIANTE: soma das parcelas == total == valor_agente persistido.
    soma = (
        comp.valor_acionamento_ajustado
        + comp.subtotal_km
        + comp.subtotal_hora
        + comp.pedagio
    )
    assert soma == comp.valor_agente == ac.valor_agente == Decimal("792.00")


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
def test_acionamento_codigo_formata_pk_zero_padded_6_digitos(_fks_acionamento):
    """DD-032/ST4 — a property `codigo` é exibição pura: f"ACN-{pk:06d}", sem
    coluna nem migration (deriva do pk existente). O formato é fixado pela spec
    visual do badge (ex.: ACN-000031): prefixo "ACN-" + pk com zero-padding a 6
    dígitos.

    Depende de pk → o acionamento é PERSISTIDO antes de ler o código.

    Nota: o assert de comprimento (==10) vale enquanto o pk couber em 6 dígitos;
    se um dia passar de 999999, o :06d cresce naturalmente e este comprimento
    deve ser revisto (o formato f"ACN-{pk:06d}" continua correto).

    Fase RED do TDD: a property `codigo` ainda não existe no model, então o
    acesso a ac.codigo levanta AttributeError.
    """
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()  # sem pk não há código

    assert ac.codigo == f"ACN-{ac.pk:06d}"
    # Exemplo concreto do formato legível: pk=1 → "ACN-000001".
    assert ac.codigo.startswith("ACN-") and len(ac.codigo) == 10


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
def test_listar_acionamentos_combina_todos_os_filtros_preservando_desc(_fks_acionamento):
    """DD-016/M5 (AC-08.1/08.3) — caracterização do contrato de composição: os
    quatro filtros aplicados juntos fazem interseção (AND) e a ordenação DESC
    sobrevive ao encadeamento. Fecha as pendências anotadas nos ciclos 1-3 da
    subtask 1."""
    cliente_a, responsavel, agente_x = _fks_acionamento
    cliente_b = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")
    agente_y = Agente.objects.create(nome="Agente Y", cpf="11144477735")
    franquia_a = FranquiaAgente.objects.create(**_dados_franquia(cliente_a, nome="Franquia A"))
    # Franquia do cliente B: deixa o quase-alvo "outro cliente" ser COM franquia
    # (RN-06 proíbe franquia de A em acionamento de B), diferindo só pelo cliente.
    franquia_b = FranquiaAgente.objects.create(**_dados_franquia(cliente_b, nome="Franquia B"))

    base = timezone.now()

    def _cria(cli, ag, solicitado, franquia):
        ac = _acionamento_valido(
            cli,
            responsavel,
            ag,
            franquia_agente=franquia,
            data_hora_solicitado=solicitado,
            data_hora_inicio=solicitado + timedelta(minutes=30),
            data_hora_final=solicitado + timedelta(hours=3),
        )
        ac.save()
        return ac

    # Alvo (cliente A + agente X + dentro do intervalo + COM franquia): o mais
    # recente é criado AGORA; o mais antigo é criado por ÚLTIMO (ordem invertida
    # à cronológica) para provar que a ordem vem do order_by, não da inserção.
    alvo_recente = _cria(cliente_a, agente_x, base, franquia_a)

    # Quase-alvos — cada um difere do recorte por UM único critério:
    _cria(cliente_b, agente_x, base, franquia_b)                      # outro cliente
    _cria(cliente_a, agente_y, base, franquia_a)                      # outro agente
    _cria(cliente_a, agente_x, base - timedelta(days=5), franquia_a)  # fora do intervalo
    _cria(cliente_a, agente_x, base, None)                            # sem franquia

    # ...e só agora o mais antigo do par alvo (criado por último de propósito).
    alvo_antigo = _cria(cliente_a, agente_x, base - timedelta(days=1), franquia_a)

    from controle_acionamentos.selectors import listar_acionamentos

    resultado = listar_acionamentos(
        cliente=cliente_a,
        agente=agente_x,
        data_de=(base - timedelta(days=2)).date(),
        data_ate=base.date(),
        com_franquia=True,
    )

    # Só o par alvo (interseção AND), na ordem DESC (mais recente primeiro).
    assert [a.pk for a in resultado] == [alvo_recente.pk, alvo_antigo.pk]


@pytest.mark.django_db
def test_listar_acionamentos_com_franquia_acessivel_sem_n_mais_1(
    _fks_acionamento, django_assert_num_queries
):
    """DD-032/ST3 — trava o N+1 da coluna Franquia da listagem.

    A ST3 passa a exibir {{ a.franquia_agente.nome }} por linha da tabela. Sem
    select_related("franquia_agente") no selector, cada linha COM franquia
    dispararia uma query lazy extra ao acessar o nome (N+1): a contagem cresceria
    com o nº de linhas. Este teste fixa o contrato de que avaliar o queryset E
    tocar a franquia de TODAS as linhas custa uma contagem CONSTANTE de queries
    (=1), independente do nº de registros — a garantia do §7/nº10.

    Fase RED do TDD: hoje o selector só faz select_related de cliente/agente, então
    este teste FALHA (5 queries: a base + 4 lazy loads das franquias vinculadas).
    """
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia"))

    # 4 acionamentos COM franquia (cada um seria um lazy load) e 2 SEM (FK nula
    # não dispara query — cobre o ramo do if a.franquia_agente_id).
    for _ in range(4):
        _acionamento_valido(cliente, responsavel, agente, franquia_agente=franquia).save()
    for _ in range(2):
        _acionamento_valido(cliente, responsavel, agente, franquia_agente=None).save()

    from controle_acionamentos.selectors import listar_acionamentos

    # Uma única query: a avaliação da lista. Acessar a.franquia_agente.nome de
    # cada linha COM franquia não pode gerar query nova — checa-se pelo _id (que
    # já está na linha) para não disparar o lazy load justamente ao testá-lo.
    with django_assert_num_queries(1):
        acionamentos = list(listar_acionamentos())
        for a in acionamentos:
            _ = a.franquia_agente.nome if a.franquia_agente_id else None


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
def test_acionamento_list_filtra_por_agente_via_get(
    client, django_user_model, _fks_acionamento
):
    """DD-016/M5 (AC-08.1) — a view lê ?agente= do GET, valida pelo
    FiltroAcionamentosForm e repassa ao selector; espelho do filtro por cliente
    do M4, mesma filosofia tolerante."""
    cliente, responsavel, agente_a = _fks_acionamento
    agente_b = Agente.objects.create(nome="Segundo Agente", cpf="11144477735")

    ac_a = _acionamento_valido(cliente, responsavel, agente_a)
    ac_a.save()
    ac_b = _acionamento_valido(cliente, responsavel, agente_b)
    ac_b.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url, {"agente": agente_a.pk})

    assert response.status_code == 200
    # Só o acionamento do agente A (comparar pks, nunca HTML).
    assert [a.pk for a in response.context["acionamentos"]] == [ac_a.pk]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data_de_str, data_ate_str",
    [
        ("2026-06-23", "2026-06-25"),   # ISO — o <input type="date"> sempre envia assim
        ("23/06/2026", "25/06/2026"),   # dd/mm/aaaa — URL digitada à brasileira
    ],
)
def test_acionamento_list_filtra_por_intervalo_de_data_via_get(
    client, django_user_model, _fks_acionamento, data_de_str, data_ate_str
):
    """DD-016/M5 (AC-08.1) — intervalo de data via GET aceita ISO (input
    type=date do navegador) e dd/mm/aaaa (URL manual); validação no form,
    repasse ao selector com fronteira inclusiva já testada."""
    from datetime import datetime

    cliente, responsavel, agente = _fks_acionamento

    def _cria(solicitado):
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

    # 24/06/2026 às 14h (aware): dentro do intervalo [23..25]. O outro, 10 dias
    # antes, fica de fora.
    dentro = _cria(timezone.make_aware(datetime(2026, 6, 24, 14, 0)))
    fora = _cria(timezone.make_aware(datetime(2026, 6, 14, 14, 0)))

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url, {"data_de": data_de_str, "data_ate": data_ate_str})

    assert response.status_code == 200
    # Só o acionamento de dentro do intervalo (comparar pks, nunca HTML).
    assert [a.pk for a in response.context["acionamentos"]] == [dentro.pk]


@pytest.mark.django_db
@pytest.mark.parametrize("status, espera_vinculado", [("com", True), ("sem", False)])
def test_acionamento_list_filtra_por_status_de_franquia_via_get(
    client, django_user_model, _fks_acionamento, status, espera_vinculado
):
    """DD-016/M5 (AC-08.1) — status via GET: ChoiceField traduz "com"/"sem"/vazio
    para True/False/None no clean_status; o selector nunca vê strings de tela."""
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia"))

    com = _acionamento_valido(cliente, responsavel, agente, franquia_agente=franquia)
    com.save()
    sem = _acionamento_valido(cliente, responsavel, agente, franquia_agente=None)
    sem.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url, {"status": status})

    assert response.status_code == 200
    esperado = com.pk if espera_vinculado else sem.pk
    # Só o acionamento do status pedido (comparar pks, nunca HTML).
    assert [a.pk for a in response.context["acionamentos"]] == [esperado]


@pytest.mark.django_db
def test_acionamento_list_combina_cliente_e_status_via_get(
    client, django_user_model, _fks_acionamento
):
    """DD-016/M5 (AC-08.1) — composição de filtros na camada view/HTTP: dois
    filtros juntos no GET (?cliente= E ?status=com) fazem interseção (AND). Só o
    alvo casa os dois; cada quase-alvo difere por UM único critério. Espelha o
    teste de composição do selector, mas provando o AND ponta a ponta pela view."""
    cliente_a, responsavel, agente = _fks_acionamento
    cliente_b = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")
    franquia_a = FranquiaAgente.objects.create(**_dados_franquia(cliente_a, nome="Franquia A"))
    # Franquia própria do cliente B: RN-06 proíbe franquia de A em acionamento de
    # B, então o quase-alvo "outro cliente" também é COM franquia, diferindo SÓ
    # pelo cliente.
    franquia_b = FranquiaAgente.objects.create(**_dados_franquia(cliente_b, nome="Franquia B"))

    # Alvo: cliente A + COM franquia (casa os dois critérios).
    alvo = _acionamento_valido(cliente_a, responsavel, agente, franquia_agente=franquia_a)
    alvo.save()
    # Quase-alvo 1: outro cliente (B), mas COM franquia → cai pelo filtro de cliente.
    _acionamento_valido(cliente_b, responsavel, agente, franquia_agente=franquia_b).save()
    # Quase-alvo 2: cliente A, mas SEM franquia → cai pelo filtro de status.
    _acionamento_valido(cliente_a, responsavel, agente, franquia_agente=None).save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url, {"cliente": cliente_a.pk, "status": "com"})

    assert response.status_code == 200
    # Só o alvo sobrevive à interseção dos dois filtros (comparar pks, nunca HTML).
    assert [a.pk for a in response.context["acionamentos"]] == [alvo.pk]


@pytest.mark.django_db
def test_acionamento_list_pagina_com_25_por_pagina(
    client, django_user_model, _fks_acionamento
):
    """DD-016/M5 (AC-08.2) — paginação default de 25/página com get_page
    tolerante; ordenação DESC preservada entre páginas."""
    cliente, responsavel, agente = _fks_acionamento
    base = timezone.now()

    # 30 acionamentos com data_hora_solicitado decrescente (i=0 é o mais recente),
    # para ordenação determinística que atravessa a paginação.
    mais_recente = None
    for i in range(30):
        solicitado = base - timedelta(minutes=i)
        ac = _acionamento_valido(
            cliente,
            responsavel,
            agente,
            data_hora_solicitado=solicitado,
            data_hora_inicio=solicitado + timedelta(minutes=30),
            data_hora_final=solicitado + timedelta(hours=3),
        )
        ac.save()
        if i == 0:
            mais_recente = ac

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")

    # Página 1 (default): 25 itens, começando pelo mais recente dos 30.
    resp1 = client.get(url)
    assert resp1.status_code == 200
    pagina1 = resp1.context["acionamentos"]
    assert len(pagina1) == 25
    assert list(pagina1)[0].pk == mais_recente.pk

    # Página 2: os 5 restantes.
    resp2 = client.get(url, {"page": 2})
    assert resp2.status_code == 200
    assert len(resp2.context["acionamentos"]) == 5


@pytest.mark.django_db
def test_acionamento_list_carga_10k_responde_abaixo_de_500ms(
    client, django_user_model, _fks_acionamento
):
    """DD-016/M5 (subtask 6, critério de carga do PRD) — a listagem responde em
    < 500ms com 10.000 acionamentos, tanto sem filtros (ordenação DESC +
    paginação default) quanto com o filtro de intervalo de datas (lookup __date,
    suspeito da ST4).

    Semeadura via bulk_create(batch_size=1000) — NUNCA save() em loop (§7). Como
    bulk_create pula o save()/recalcular_valor_agente, os campos obrigatórios E os
    calculados são pré-preenchidos com valores fixos plausíveis (Decimal). Dados
    variados (2 clientes, ~12 meses, com/sem franquia) dão seletividade real ao
    filtro de data."""
    cliente_a, responsavel, agente = _fks_acionamento
    cliente_b = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")
    franquia_a = FranquiaAgente.objects.create(**_dados_franquia(cliente_a, nome="Franquia A"))
    franquia_b = FranquiaAgente.objects.create(**_dados_franquia(cliente_b, nome="Franquia B"))

    base = timezone.now()
    TOTAL = 10_000

    lote = []
    for i in range(TOTAL):
        # Cliente alterna A/B; franquia sempre coerente com o cliente (RN-06),
        # e 1 em cada 3 nasce SEM franquia — dá as duas populações ao filtro.
        usa_a = (i % 2 == 0)
        cliente = cliente_a if usa_a else cliente_b
        tem_franquia = (i % 3 != 0)
        franquia = (franquia_a if usa_a else franquia_b) if tem_franquia else None

        # Datas espalhadas por ~12 meses (dias 0..364), com hora variando também.
        solicitado = base - timedelta(days=i % 365, hours=i % 24)
        lote.append(
            Acionamento(
                cliente=cliente,
                responsavel_agente=responsavel,
                agente=agente,
                franquia_agente=franquia,
                nome_servico="Reboque leve",
                valor_acionamento=Decimal("150.00"),
                franquia_km=80,
                franquia_horas=Decimal("4.00"),
                valor_km_excedente=Decimal("2.50"),
                valor_hora_excedente=Decimal("30.00"),
                origem="São Paulo - SP",
                destino="Campinas - SP",
                data_hora_solicitado=solicitado,
                data_hora_inicio=solicitado + timedelta(minutes=30),
                data_hora_final=solicitado + timedelta(hours=3),
                km_inicio=1000,
                km_final=1120,
                pedagio=Decimal("0.00"),
                # Calculados (RN-07): bulk_create pula o service, então fixos e
                # plausíveis só para satisfazer a leitura da listagem.
                km_total=120,
                horas_total=Decimal("2.50"),
                km_excedente=40,
                hora_excedente=Decimal("0.00"),
                valor_agente=Decimal("250.00"),
            )
        )

    Acionamento.objects.bulk_create(lote, batch_size=1000)
    assert Acionamento.objects.count() == TOTAL  # sanidade da semeadura

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")

    # Cenário (a): listagem sem filtros — DESC + paginação default.
    t0 = time.perf_counter()
    resp_sem = client.get(url)
    dt_sem = time.perf_counter() - t0
    assert resp_sem.status_code == 200

    # Cenário (b): filtro por intervalo de datas (últimos 30 dias) — lookup __date.
    t1 = time.perf_counter()
    resp_data = client.get(
        url,
        {"data_de": (base - timedelta(days=30)).date().isoformat(),
         "data_ate": base.date().isoformat()},
    )
    dt_data = time.perf_counter() - t1
    assert resp_data.status_code == 200

    # Sanidade: a paginação está de pé sob carga (página 1 cheia = 25).
    assert len(resp_sem.context["acionamentos"]) == 25

    print(
        f"\n[CARGA 10k] sem filtro: {dt_sem * 1000:.1f} ms | "
        f"filtro data (__date): {dt_data * 1000:.1f} ms | limite: 500 ms"
    )

    assert dt_sem < 0.5, f"listagem sem filtro levou {dt_sem * 1000:.1f} ms (limite 500)"
    assert dt_data < 0.5, f"listagem c/ filtro de data levou {dt_data * 1000:.1f} ms (limite 500)"


@pytest.mark.django_db
def test_acionamento_list_expoe_querystring_dos_filtros_sem_page(
    client, django_user_model, _fks_acionamento
):
    """DD-016/M5 (AC-08.2) — contrato da navegação de páginas: a querystring dos
    filtros sobrevive ao clique de Anterior/Próxima; o page é removido da base
    para o template injetar o novo valor."""
    cliente, responsavel, agente = _fks_acionamento
    _acionamento_valido(cliente, responsavel, agente).save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    # Filtros + page juntos, de propósito: o page precisa ser retirado da base.
    response = client.get(url, {"cliente": cliente.pk, "status": "com", "page": 2})

    assert response.status_code == 200
    querystring = response.context["filtros_querystring"]
    assert f"cliente={cliente.pk}" in querystring
    assert "status=com" in querystring
    # O page NÃO entra na base — o template o injeta com o valor novo.
    assert "page=" not in querystring


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
def test_acionamento_detail_renderiza_extrato_de_composicao(
    client, django_user_model, _fks_acionamento
):
    """Regressão (nasce VERDE) — trava o contrato view→template do extrato
    (DD-032/ST5): a view injeta `composicao` no contexto e o template renderiza o
    card "Composição do valor" com a anotação dinâmica de escalonamento.

    Arrange do cenário C4 (franquia 660/200km/4h/3,30/55, escalonamento ON; km 285,
    7h, pedágio 50) → valor_agente 1.045,50 com 2 blocos.
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
        pedagio=Decimal("50.00"),
        km_inicio=0,
        km_final=285,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=7),
    )
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_detail", args=[ac.pk])
    response = client.get(url)

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert "Composição do valor" in conteudo   # o card do extrato existe
    assert "escalonado" in conteudo            # anotação dinâmica da 1ª linha
    assert "2 blocos" in conteudo              # blocos + pluralize
    # floatformat:2 sob L10N pt-br (sem separador de milhar) → vírgula decimal.
    assert "1045,50" in conteudo               # total do extrato renderizado


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


# ---------------------------------------------------------------------------
# DD-016/M5 subtask 5 — hardening de autenticação (teste de caracterização).
# A listagem é protegida por @login_required: um anônimo deve ser redirecionado
# (302) para o LOGIN_URL, preservando o destino em ?next=. Nasce verde — apenas
# caracteriza o comportamento já existente, não é red-green.
# Cobertura CANÔNICA destes contratos (302→login com ?next= e 403 sem permissão):
# os antecessores "frouxos" da listagem foram removidos no fecho do DD-032 por
# serem duplicata estrita (asserts mais fracos) do que esta classe já garante.
# ---------------------------------------------------------------------------


class TestHardeningAutenticacao:
    @pytest.mark.django_db
    def test_listagem_anonima_redireciona_para_login_com_next(self, client):
        """Anônimo na listagem → 302 para o login com ?next= apontando à listagem."""
        url_listagem = reverse("controle_acionamentos:acionamento_list")
        response = client.get(url_listagem)

        assert response.status_code == 302

        redirect = urlparse(response.url)
        assert redirect.path == reverse("login")
        assert parse_qs(redirect.query)["next"] == [url_listagem]

    @pytest.mark.django_db
    def test_lote_anonimo_post_redireciona_para_login_com_next(self, client):
        """Anônimo no POST do lote → 302 para o login ANTES do @require_POST/service."""
        url_lote = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")
        response = client.post(url_lote, data={})

        assert response.status_code == 302

        redirect = urlparse(response.url)
        assert redirect.path == reverse("login")
        assert parse_qs(redirect.query)["next"] == [url_lote]

    @pytest.mark.django_db
    def test_listagem_autenticado_sem_permissao_retorna_403(self, client):
        """Autenticado sem view_acionamento → 403 (permission_required raise_exception)."""
        user = get_user_model().objects.create_user(username="comum", password="x")
        client.force_login(user)

        url_listagem = reverse("controle_acionamentos:acionamento_list")
        response = client.get(url_listagem)

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# DD-032/ST7 — selectors do dashboard (FASE RED)
# A home dashboard terá 2 contadores. Os selectors correspondentes ainda NÃO
# existem em controle_acionamentos.selectors — por isso os 4 testes abaixo
# nascem VERMELHOS de propósito (TDD): o import LOCAL dispara ImportError,
# isolado dentro de cada teste para não derrubar a coleta dos demais.
# Contrato sob teste:
#   contar_acionamentos_no_mes(hoje=None) -> int  (mês/ano de `hoje`)
#   contar_sem_franquia() -> int                  (franquia_agente__isnull=True)
# Datas SEMPRE injetadas e timezone-aware — nunca o relógio real.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_contar_acionamentos_no_mes_conta_apenas_o_mes_corrente(_fks_acionamento):
    """DD-032/ST7 (RED) — conta só os acionamentos do mês/ano de `hoje`.

    Função ainda não existe em selectors.py; a fase é RED e a falha é
    proposital, por ImportError no import local de contar_acionamentos_no_mes.
    Arrange: 2 acionamentos em junho/2026 e 1 em maio/2026 (todos com
    data_hora_solicitado FIXA e timezone-aware). Act com hoje=15/06/2026.
    """
    from datetime import date, datetime

    from controle_acionamentos.selectors import contar_acionamentos_no_mes

    cliente, responsavel, agente = _fks_acionamento

    def _solicitado(dt):
        base = timezone.make_aware(dt)
        return _acionamento_valido(
            cliente,
            responsavel,
            agente,
            data_hora_solicitado=base,
            data_hora_inicio=base + timedelta(minutes=30),
            data_hora_final=base + timedelta(hours=3),
        )

    _solicitado(datetime(2026, 6, 10, 9, 0)).save()   # dentro do mês
    _solicitado(datetime(2026, 6, 20, 14, 0)).save()  # dentro do mês
    _solicitado(datetime(2026, 5, 31, 23, 0)).save()  # mês anterior

    assert contar_acionamentos_no_mes(hoje=date(2026, 6, 15)) == 2


@pytest.mark.django_db
def test_contar_acionamentos_no_mes_zero_quando_vazio():
    """DD-032/ST7 (RED) — sem acionamentos no banco, o contador do mês é 0.

    Função ainda não existe em selectors.py; a fase é RED e a falha é
    proposital, por ImportError no import local de contar_acionamentos_no_mes.
    """
    from datetime import date

    from controle_acionamentos.selectors import contar_acionamentos_no_mes

    assert contar_acionamentos_no_mes(hoje=date(2026, 6, 15)) == 0


@pytest.mark.django_db
def test_contar_sem_franquia_conta_apenas_sem_vinculo(_fks_acionamento):
    """DD-032/ST7 (RED) — conta só acionamentos com franquia_agente nulo, sem
    recorte temporal.

    Função ainda não existe em selectors.py; a fase é RED e a falha é
    proposital, por ImportError no import local de contar_sem_franquia.
    Arrange: 1 acionamento COM franquia vinculada + 2 SEM vínculo.
    """
    from controle_acionamentos.selectors import contar_sem_franquia

    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente))

    _acionamento_valido(cliente, responsavel, agente, franquia_agente=franquia).save()
    _acionamento_valido(cliente, responsavel, agente).save()
    _acionamento_valido(cliente, responsavel, agente).save()

    assert contar_sem_franquia() == 2


@pytest.mark.django_db
def test_contar_sem_franquia_zero_quando_todos_vinculados(_fks_acionamento):
    """DD-032/ST7 (RED) — todos os acionamentos com franquia vinculada → 0.

    Função ainda não existe em selectors.py; a fase é RED e a falha é
    proposital, por ImportError no import local de contar_sem_franquia.
    """
    from controle_acionamentos.selectors import contar_sem_franquia

    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente))

    _acionamento_valido(cliente, responsavel, agente, franquia_agente=franquia).save()

    assert contar_sem_franquia() == 0


# ---------------------------------------------------------------------------
# DD-032 — regressão: gating do botão Novo por permissão
# Na ST6 parte 3 o botão "Novo acionamento" do _cabecalho.html vazou para
# usuário SEM add_acionamento (o include recebe botao_novo=perms.…add_acionamento
# na listagem). A regressão foi pega em review e corrigida no mesmo diff; estes
# 2 testes NASCEM VERDES para travar o comportamento e fechar a lacuna de
# cobertura. Âncora do assert = "Novo acionamento" (texto do BOTÃO); a pill da
# nav tem só "Novo", então não colide.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_listagem_sem_add_nao_exibe_botao_novo(client, django_user_model):
    """DD-032 (regressão, nasce VERDE) — quem só tem view_acionamento NÃO vê o
    botão "Novo acionamento" na listagem (gating capturado em review na ST6 p3)."""
    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url)

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert "Novo acionamento" not in conteudo


@pytest.mark.django_db
def test_listagem_com_add_exibe_botao_novo(client, django_user_model):
    """DD-032 (regressão, nasce VERDE) — quem tem view_acionamento + add_acionamento
    vê o botão "Novo acionamento" na listagem (o gating libera o botão)."""
    user = _user_com_perms(django_user_model, "view_acionamento", "add_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url)

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert "Novo acionamento" in conteudo


# ---------------------------------------------------------------------------
# DD-032 — filtro de template `cnpj` (camada de apresentação). Formata 14
# dígitos como 00.000.000/0000-00; devolve o valor original se não tiver
# exatamente 14 dígitos. Import LOCAL da função (padrão da suíte).
# ---------------------------------------------------------------------------


def test_filtro_cnpj_formata_14_digitos():
    """14 dígitos viram a máscara 00.000.000/0000-00."""
    from controle_acionamentos.templatetags.formatos import cnpj

    assert cnpj("11222333000181") == "11.222.333/0001-81"


def test_filtro_cnpj_valor_invalido_retorna_original():
    """Sem 14 dígitos, o filtro devolve o valor original intocado."""
    from controle_acionamentos.templatetags.formatos import cnpj

    assert cnpj("123") == "123"


# ---------------------------------------------------------------------------
# DD-048 — dashboard: 3º contador (soma de valor_agente no mês) + tabela
# "Últimos acionamentos" na home. Import LOCAL das funções sob teste (padrão
# da suíte); reuso dos helpers _fks_acionamento / _acionamento_valido.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_somar_valor_agente_no_mes_soma_apenas_mes_corrente(_fks_acionamento):
    """DD-048 — soma valor_agente só dos acionamentos do mês/ano de `hoje`.

    Um acionamento em jun/2026 e outro em mai/2026 (datas fixas, timezone-aware).
    O valor_agente é computado no save (recalcular_valor_agente), então a soma
    esperada é o valor do registro de dentro, lido do banco (Decimal, não float).
    """
    from datetime import date, datetime

    from controle_acionamentos.selectors import somar_valor_agente_no_mes

    cliente, responsavel, agente = _fks_acionamento

    dentro = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        data_hora_solicitado=timezone.make_aware(datetime(2026, 6, 10, 9, 0)),
        data_hora_inicio=timezone.make_aware(datetime(2026, 6, 10, 9, 30)),
        data_hora_final=timezone.make_aware(datetime(2026, 6, 10, 12, 0)),
    )
    dentro.save()
    dentro.refresh_from_db()

    fora = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        data_hora_solicitado=timezone.make_aware(datetime(2026, 5, 20, 9, 0)),
        data_hora_inicio=timezone.make_aware(datetime(2026, 5, 20, 9, 30)),
        data_hora_final=timezone.make_aware(datetime(2026, 5, 20, 12, 0)),
    )
    fora.save()

    resultado = somar_valor_agente_no_mes(hoje=date(2026, 6, 15))

    assert resultado == dentro.valor_agente
    assert isinstance(resultado, Decimal)


@pytest.mark.django_db
def test_somar_valor_agente_no_mes_zero_quando_vazio():
    """DD-048 — mês sem acionamentos soma Decimal("0") (Coalesce), nunca None."""
    from datetime import date

    from controle_acionamentos.selectors import somar_valor_agente_no_mes

    assert somar_valor_agente_no_mes(hoje=date(2026, 6, 15)) == Decimal("0")


@pytest.mark.django_db
def test_home_renderiza_ultimos_acionamentos(
    client, django_user_model, _fks_acionamento
):
    """DD-048 — a home logada renderiza a tabela "Últimos acionamentos" com o
    código ACN do acionamento mais recente."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    user = django_user_model.objects.create_user(username="home", password="x")
    client.force_login(user)

    url = reverse("controle_acionamentos:index")
    response = client.get(url)

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert "Últimos acionamentos" in conteudo
    assert ac.codigo in conteudo


# ---------------------------------------------------------------
# DD-049/ST1 — edição de acionamento (RED: view/rota ainda não existem)
# Rota alvo: controle_acionamentos:acionamento_update (kwarg pk)
# Os 4 testes nascem VERMELHOS: o reverse() está DENTRO de cada corpo, então
# o NoReverseMatch derruba só estes testes, sem quebrar a coleta dos 116
# existentes. NÃO existem ainda a view acionamento_update nem a rota.
# ---------------------------------------------------------------


def _post_payload_acionamento(ac, **overrides):
    """Serializa um Acionamento salvo no formato que o AcionamentoForm espera,
    pronto para client.post(): FKs por pk, datas em '%Y-%m-%dT%H:%M' (o que o
    <input type="datetime-local"> envia e o form parseia via input_formats).

    Os 5 campos calculados (editable=False) ficam de fora por construção — quem
    os preenche é o save(). `overrides` troca campos pontuais (ex.: o
    valor_acionamento sob edição). Espelha o helper `_acionamento_valido`, mas
    na direção model → POST.
    """
    def _dt(valor):
        # localtime + naive '%Y-%m-%dT%H:%M' fecha o round-trip sob USE_TZ=True:
        # é o mesmo formato que o widget renderiza e o input_formats do form lê.
        return timezone.localtime(valor).strftime("%Y-%m-%dT%H:%M")

    payload = {
        "cliente": ac.cliente_id,
        "nome_servico": ac.nome_servico,
        "valor_acionamento": str(ac.valor_acionamento),
        "franquia_km": ac.franquia_km,
        "franquia_horas": str(ac.franquia_horas),
        "valor_km_excedente": str(ac.valor_km_excedente),
        "valor_hora_excedente": str(ac.valor_hora_excedente),
        "origem": ac.origem,
        "destino": ac.destino,
        "responsavel_agente": ac.responsavel_agente_id,
        "agente": ac.agente_id,
        "placa_agente": ac.placa_agente or "",
        "motorista": ac.motorista or "",
        "placa_motorista": ac.placa_motorista or "",
        "numero_motorista": ac.numero_motorista or "",
        "data_hora_solicitado": _dt(ac.data_hora_solicitado),
        "data_hora_inicio": _dt(ac.data_hora_inicio),
        "data_hora_final": _dt(ac.data_hora_final),
        "km_inicio": ac.km_inicio,
        "km_final": ac.km_final,
        "pedagio": str(ac.pedagio),
        "franquia_agente": ac.franquia_agente_id or "",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_acionamento_update_anonimo_redireciona_para_login(client, _fks_acionamento):
    """Sem autenticação, o GET na edição redireciona (302) para o login,
    preservando o destino em ?next= (padrão do hardening já existente)."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    response = client.get(url)

    assert response.status_code == 302
    redirect = urlparse(response.url)
    assert redirect.path == reverse("login")
    assert parse_qs(redirect.query)["next"] == [url]


@pytest.mark.django_db
def test_acionamento_update_com_view_mas_sem_change_retorna_403(
    client, django_user_model, _fks_acionamento
):
    """Granularidade: quem só tem view_acionamento NÃO pode editar (403).
    Ver não é mexer — a edição exige change_acionamento."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_acionamento_update_get_carrega_dados_do_registro(
    client, django_user_model, _fks_acionamento
):
    """Com view+change, o GET devolve 200 renderizando o form_template com o
    registro pré-carregado (instance): o nome_servico do acionamento aparece
    no HTML, provando que o form veio populado."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente, nome_servico="Reboque pesado XYZ")
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento", "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    response = client.get(url)

    assert response.status_code == 200
    assert "controle_acionamentos/acionamento_form.html" in [
        t.name for t in response.templates
    ]
    conteudo = response.content.decode(response.charset)
    assert "Reboque pesado XYZ" in conteudo


@pytest.mark.django_db
def test_acionamento_update_post_valido_edita_e_recalcula(
    client, django_user_model, _fks_acionamento
):
    """Com view+change, o POST válido edita o registro e RECALCULA o valor_agente.

    Cenário sem franquia (inline manda): valor 500→600, mantidos os demais
    campos. Após o POST: 302 para o detalhe, valor_acionamento persistido == 600
    e valor_agente (a) diferente do anterior E (b) igual ao que o próprio service
    recalcular_valor_agente produz para o mesmo cenário — sem número mágico.
    """
    from controle_acionamentos.services import recalcular_valor_agente

    cliente, responsavel, agente = _fks_acionamento
    base = timezone.now()
    params = dict(
        franquia_agente=None,
        valor_acionamento=Decimal("500.00"),
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
    ac = _acionamento_valido(cliente, responsavel, agente, **params)
    ac.save()
    ac.refresh_from_db()
    valor_agente_antes = ac.valor_agente

    # Espelho PURO do que o service deve produzir com valor 600 (mesmos demais
    # campos): não persistido, só para extrair o valor_agente esperado.
    esperado = _acionamento_valido(
        cliente, responsavel, agente, **{**params, "valor_acionamento": Decimal("600.00")}
    )
    recalcular_valor_agente(esperado)

    user = _user_com_perms(django_user_model, "view_acionamento", "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    payload = _post_payload_acionamento(ac, valor_acionamento="600.00")
    response = client.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse(
        "controle_acionamentos:acionamento_detail", args=[ac.pk]
    )

    ac.refresh_from_db()
    assert ac.valor_acionamento == Decimal("600.00")
    assert ac.valor_agente != valor_agente_antes          # recalculou de fato
    assert ac.valor_agente == esperado.valor_agente        # bate com o service


# --- DD-049 ST2: AcionamentoHistorico (RED) ---
# O model AcionamentoHistorico AINDA NÃO EXISTE — estes 3 testes nascem VERMELHOS.
# O import fica DENTRO de cada corpo (nunca no topo) para isolar o ImportError e
# manter os 120 testes existentes coletáveis. Contrato exercitado:
#   acionamento -> Acionamento (on_delete=PROTECT)
#   editado_por -> User (on_delete=PROTECT)
#   campo / valor_anterior / valor_novo: texto
#   editado_em: DateTimeField(auto_now_add=True)
#   Meta.ordering = ['-editado_em']


@pytest.mark.django_db
def test_historico_persiste_com_editado_em_automatico(
    django_user_model, _fks_acionamento
):
    """editado_em é preenchido sozinho (auto_now_add) e os 3 campos de texto
    voltam exatamente como gravados."""
    from controle_acionamentos.models import AcionamentoHistorico

    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()
    user = _user_com_perms(django_user_model)  # editado_por não precisa de perm

    registro = AcionamentoHistorico.objects.create(
        acionamento=ac,
        editado_por=user,
        campo="pedagio",
        valor_anterior="0.00",
        valor_novo="25.00",
    )

    assert AcionamentoHistorico.objects.count() == 1
    registro.refresh_from_db()
    assert registro.editado_em is not None
    assert registro.campo == "pedagio"
    assert registro.valor_anterior == "0.00"
    assert registro.valor_novo == "25.00"


@pytest.mark.django_db
def test_historico_ordering_mais_recente_primeiro(
    django_user_model, _fks_acionamento
):
    """Meta.ordering = ['-editado_em'] — o mais recente vem primeiro em all()."""
    from controle_acionamentos.models import AcionamentoHistorico

    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()
    user = _user_com_perms(django_user_model)

    primeiro = AcionamentoHistorico.objects.create(
        acionamento=ac,
        editado_por=user,
        campo="pedagio",
        valor_anterior="0.00",
        valor_novo="10.00",
    )
    segundo = AcionamentoHistorico.objects.create(
        acionamento=ac,
        editado_por=user,
        campo="pedagio",
        valor_anterior="10.00",
        valor_novo="20.00",
    )

    # auto_now_add pode colidir no mesmo tick no SQLite; recuo o timestamp do 1º
    # via update() (update() NÃO dispara auto_now_add) para garantir a diferença.
    AcionamentoHistorico.objects.filter(pk=primeiro.pk).update(
        editado_em=timezone.now() - timedelta(hours=1)
    )

    ordenados = list(AcionamentoHistorico.objects.all())
    assert ordenados[0].pk == segundo.pk


@pytest.mark.django_db
def test_acionamento_com_historico_nao_pode_ser_excluido(
    django_user_model, _fks_acionamento
):
    """on_delete=PROTECT no FK acionamento: excluir um acionamento com histórico
    levanta ProtectedError e o acionamento permanece no banco."""
    from django.db.models import ProtectedError

    from controle_acionamentos.models import AcionamentoHistorico

    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()
    user = _user_com_perms(django_user_model)
    AcionamentoHistorico.objects.create(
        acionamento=ac,
        editado_por=user,
        campo="pedagio",
        valor_anterior="0.00",
        valor_novo="25.00",
    )

    with pytest.raises(ProtectedError):
        ac.delete()

    assert Acionamento.objects.filter(pk=ac.pk).exists()