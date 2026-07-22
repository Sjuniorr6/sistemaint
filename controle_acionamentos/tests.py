import pytest
import time
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlparse, parse_qs

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db.models import PROTECT, ProtectedError
from django.urls import reverse
from django.utils import timezone

from pytest_django.asserts import assertContains, assertNotContains

from controle_acionamentos.services import (
    validar_cpf,
    validar_cnpj,
    validar_cnh,
    aplicar_servico_ao_acionamento,
)
from controle_acionamentos.models import (
    ResponsavelAgente,
    Cliente,
    Agente,
    FranquiaAgente,
    Acionamento,
    ServicoCliente,
)
from controle_acionamentos.selectors import listar_servicos_ativos_por_cliente

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
def test_compor_valor_agente_sem_franquia_retorna_none(_fks_acionamento):
    """DD-068/ST3 — SEM franquia vinculada não há composição: compor_valor_agente
    retorna None (estado PENDENTE). O inline NUNCA alimenta o valor do agente; o
    card de composição não renderiza (o visual completo do pendente é da DD-069).

    Substitui o antigo test_compor_valor_agente_inline_sem_franquia_parcelas_batem:
    o MESMO arrange que antes fechava 170,00 pelo inline agora não tem extrato.
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
    ac.save()  # sem franquia: persiste o estado pendente (valor_agente None)

    from controle_acionamentos.services import compor_valor_agente

    assert compor_valor_agente(ac) is None


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
def test_save_sem_franquia_valor_agente_pendente(_fks_acionamento):
    """DD-068/ST3 pela porta do model — SEM franquia o valor do agente é PENDENTE:
    o save deriva km_total/horas_total normalmente (§8.2 — fatos da jornada), mas
    persiste valor_agente=None, km_excedente=None e hora_excedente=None (saídas
    da MESMA conta, que só existe pela franquia). Nunca calcula pelo inline,
    nunca zero.

    Substitui o antigo test_save_sem_franquia_persiste_calculados_cenario2 (o
    inline fechava 170,00). Arrange mantido: valores inline continuam gravados
    (auditoria), km_total=100 (0→100); horas_total=5 (início→final 5h depois).
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

    # Fatos da jornada seguem derivados sempre...
    assert ac.km_total == 100
    assert ac.horas_total == Decimal("5.00")
    # ...mas sem franquia a conta do agente não roda: estado PENDENTE (None).
    assert ac.km_excedente is None
    assert ac.hora_excedente is None
    assert ac.valor_agente is None


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

    # valor_agente de cada um ANTES do lote (todos SEM franquia: pendente/None
    # sob a DD-068 ST3). O mapa é agnóstico ao regime — o rollback deve devolver
    # exatamente este estado, seja ele Decimal ou None.
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
    """DD-051/ST2 (AC-06.5 REVISADO) — franquia IDÊNTICA à já vinculada NÃO é
    conflito: sem sobrescrever=True, o lote passa, vincula os itens livres e
    re-salva o já vinculado na MESMA franquia (recálculo idêntico), sem levantar.

    EVOLUÇÃO EXPLÍCITA do contrato DD-015 (não silenciosa): este mesmo cenário
    (lote com a MESMA franquia do item já vinculado) antes esperava ValidationError
    (recusa). Sob AC-06.5 revisado, conflito passa a ser só franquia DIFERENTE —
    coberto por test_lote_franquia_diferente_sem_flag_continua_recusando."""
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

    # valor_agente do item já vinculado à MESMA franquia, antes do lote: re-salvar
    # a franquia idêntica deve recalcular para o MESMO valor.
    valor_ja_vinculado_antes = ja_vinculado.valor_agente

    from controle_acionamentos.services import vincular_franquia_em_lote

    # AC-06.5 revisado: franquia idêntica NÃO é conflito → sem sobrescrever, o lote
    # passa e vincula os livres normalmente (antes, DD-015, esperava ValidationError).
    resultado = vincular_franquia_em_lote(
        [livre1.pk, livre2.pk, ja_vinculado.pk], franquia
    )

    assert resultado == 3
    # Os livres passam a apontar para a franquia.
    for ac in (livre1, livre2):
        ac.refresh_from_db()
        assert ac.franquia_agente_id == franquia.pk

    # O já vinculado continua na MESMA franquia e com o MESMO valor_agente.
    ja_vinculado.refresh_from_db()
    assert ja_vinculado.franquia_agente_id == franquia.pk
    assert ja_vinculado.valor_agente == valor_ja_vinculado_antes


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
    # valor_agente dos 3 ANTES do lote (todos SEM franquia: pendente/None sob a
    # DD-068 ST3). Mapa agnóstico ao regime — o rollback devolve este estado.
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
# DD-069/ST2 — listagem: colunas "Valor cliente" e "Valor agente" + badge
# "Pendente de franquia" (RED)
# Mockups aprovados: spec/mockups/dd069/dd069_st2_listagem_caminho_a.png
# (caminho A — a coluna única de valor vira DUAS) e dd069_st2_badge_b2.png
# (badge B2 explícito no lugar do INLINE). O valor do cliente é calculado na
# VIEW após a paginação: cada acionamento da página recebe o atributo
# `valor_cliente` com o total do compor_valor_cliente (mesma fonte do detalhe,
# ST1) — nada de coluna nova no banco. Fase RED: view e template seguem no
# layout antigo → os três testes falham.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_listagem_exibe_colunas_de_valor_cliente_e_valor_agente(
    client, django_user_model, _fks_acionamento
):
    """DD-069/ST2 — a tabela troca a coluna única de valor pelos cabeçalhos
    "Valor cliente (R$)" e "Valor agente (R$)" (mockup caminho A + decisão
    pós-GREEN de manter o sufixo de moeda). Sem guard de ausência: o antigo
    ("Valor agente (R$)") sobrevive legitimamente como cabeçalho novo — a
    remoção foi autorizada nesta correção; os asserts de presença cobrem os
    rótulos por substring."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:acionamento_list"))

    assert response.status_code == 200
    conteudo = response.content.decode("utf-8")
    assert "Valor cliente" in conteudo
    assert "Valor agente" in conteudo


@pytest.mark.django_db
def test_listagem_exibe_valor_do_cliente_calculado_por_linha(
    client, django_user_model, _fks_acionamento
):
    """DD-069/ST2 — contrato-ouro da ST1 agora na LISTAGEM: serviço 1500,00,
    franquia 100km/4h, tarifas 2,80/55,00, percurso 100→150 km (50 km) em 7h →
    1500,00 + 0,00 (km dentro da franquia) + 3h × 55,00 = 1665,00. A view anexa
    a cada item da página o atributo `valor_cliente` (Decimal vindo do
    compor_valor_cliente) e o template exibe o total na coluna nova
    (floatformat sob L10N pt-br → vírgula decimal).
    Micro-etapa DD-070: o formato esperado ganhou separador de milhar
    ("2g") — 1665,00 → 1.665,00."""
    cliente, responsavel, agente = _fks_acionamento
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=None,
        valor_acionamento=Decimal("1500.00"),
        franquia_km=100,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.80"),
        valor_hora_excedente=Decimal("55.00"),
        pedagio=Decimal("0.00"),
        km_inicio=100,
        km_final=150,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=7),
    )
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:acionamento_list"))

    assert response.status_code == 200
    conteudo = response.content.decode("utf-8")
    assert "1.665,00" in conteudo
    # Cada acionamento da página carrega o total do cliente calculado na view.
    for item in response.context["acionamentos"]:
        assert item.valor_cliente == Decimal("1665.00")


@pytest.mark.django_db
def test_listagem_sem_franquia_exibe_badge_pendente_de_franquia(
    client, django_user_model, _fks_acionamento
):
    """DD-069/ST2 — linha SEM franquia vinculada: o badge INLINE morre e entra
    o "Pendente de franquia" (mockup B2 explícito, coerente com a pílula do
    detalhe da ST1); a célula do valor do agente segue exibindo o marcador "—"
    de valor nulo (DD-068: sem franquia, valor_agente pendente)."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente, franquia_agente=None)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:acionamento_list"))

    assert response.status_code == 200
    conteudo = response.content.decode("utf-8")
    assert "Pendente de franquia" in conteudo
    assert "INLINE" not in conteudo
    # O marcador de nulo segue na célula do agente — recorte pelo data-attr que
    # o JS do pedágio inline já usa, sem pinar o resto do markup da linha.
    celula = conteudo.split(f'data-valor-agente="{ac.pk}"', 1)[1].split("</td>", 1)[0]
    assert "—" in celula


@pytest.mark.django_db
def test_listagem_badge_pendente_com_change_e_link_para_vincular(
    client, django_user_model, _fks_acionamento
):
    """DD-069/ST2 (refinamento) — COM change_acionamento o badge "Pendente de
    franquia" vira LINK para o form de edição com âncora no campo de franquia,
    espelhando a pílula do herói do detalhe (ST1). A URL sozinha seria vácua
    (o lápis de editar já a renderiza): o assert pina URL + âncora coladas."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente, franquia_agente=None)
    ac.save()

    user = _user_com_perms(
        django_user_model, "view_acionamento", "change_acionamento"
    )
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:acionamento_list"))

    assert response.status_code == 200
    conteudo = response.content.decode("utf-8")
    assert "Pendente de franquia" in conteudo
    url_vincular = (
        reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
        + "#id_franquia_agente"
    )
    assert url_vincular in conteudo


@pytest.mark.django_db
def test_listagem_badge_pendente_sem_change_e_selo_estatico(
    client, django_user_model, _fks_acionamento
):
    """DD-069/ST2 (refinamento) — SÓ com view_acionamento o badge segue selo
    estático, sem link (mesma guarda da pílula do detalhe): a âncora
    id_franquia_agente não aparece em lugar nenhum da resposta. Asserção
    NEGATIVA — nasce verde no RED (regra registrada da casa); trava a guarda
    de permissão contra regressão na GREEN."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente, franquia_agente=None)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:acionamento_list"))

    assert response.status_code == 200
    conteudo = response.content.decode("utf-8")
    assert "Pendente de franquia" in conteudo
    assert "id_franquia_agente" not in conteudo


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
    Micro-etapa DD-070: o formato esperado ganhou separador de milhar
    (floatformat "2g") — 1045,50 → 1.045,50.
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
    assert "Composição do agente" in conteudo   # o card do extrato existe
    assert "escalonado" in conteudo            # anotação dinâmica da 1ª linha
    assert "2 blocos" in conteudo              # blocos + pluralize
    # floatformat:"2g" sob L10N pt-br → vírgula decimal + ponto de milhar.
    assert "1.045,50" in conteudo              # total do extrato renderizado


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
    """AC-07.3 — pedágio negativo é rejeitado (400) e nada é persistido: o
    pedágio fica como estava. DD-068/ST3: o acionamento é SEM franquia, então o
    valor_agente já nasce PENDENTE (None) e assim permanece após a rejeição."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente, pedagio=Decimal("0.00"))
    ac.save()
    ac.refresh_from_db()

    pedagio_antes = ac.pedagio
    # DD-068/ST3 — sem franquia, o valor do agente é pendente desde o save.
    assert ac.valor_agente is None

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_pedagio_update", args=[ac.pk])
    response = client.post(url, {"pedagio": "-10.00"})

    assert response.status_code == 400
    ac.refresh_from_db()
    assert ac.pedagio == pedagio_antes
    assert ac.valor_agente is None


@pytest.mark.django_db
def test_pedagio_update_nao_afeta_outras_linhas_ac074(
    client, django_user_model, _fks_acionamento
):
    """AC-07.4 — o update de pedágio é isolado por linha: atualizar um acionamento
    não pode tocar em nenhum outro. Dois acionamentos SEM franquia; só o alvo
    recebe o POST, e o vizinho sai exatamente como entrou.

    DD-068/ST3: sem franquia o pedágio continua aceito e persistido, mas o valor
    do agente segue PENDENTE — e o JSON devolve valor_agente como null JSON de
    verdade (None serializado), NUNCA a string "None"."""
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

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_pedagio_update", args=[ac_alvo.pk])
    response = client.post(url, {"pedagio": "50.00"})

    assert response.status_code == 200
    data = response.json()
    assert data["pedagio"] == "50.00"
    # null JSON de verdade: response.json() o traduz para None (nunca "None").
    assert data["valor_agente"] is None

    ac_alvo.refresh_from_db()
    ac_vizinho.refresh_from_db()
    # A linha alvo mudou (pedágio persiste mesmo com valor pendente)...
    assert ac_alvo.pedagio == Decimal("50.00")
    assert ac_alvo.valor_agente is None
    # ...e a vizinha ficou intocada (coração do AC-07.4).
    assert ac_vizinho.pedagio == pedagio_vizinho_antes
    assert ac_vizinho.valor_agente is None


# --- DD-068 ST4: edição inline de pedágio grava trilha de auditoria (RED) ---
# O endpoint acionamento_pedagio_update AINDA NÃO chama
# registrar_edicao_acionamento — a edição inline persiste o pedágio sem deixar
# rastro em AcionamentoHistorico (só o formulário de edição registra). Estes
# 2 testes nascem VERMELHOS até a view integrar a trilha.


@pytest.mark.django_db
def test_pedagio_update_com_franquia_gera_trilha_de_pedagio_e_valor_agente(
    client, django_user_model, _fks_acionamento
):
    """COM franquia: o POST inline muda pedagio E o valor_agente recalculado
    (pedágio soma, §8.5) → a trilha deve ganhar uma linha por campo mudado,
    com a serialização do service (Decimal -> string) e o autor logado."""
    from controle_acionamentos.models import AcionamentoHistorico

    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente))
    ac = _acionamento_valido(
        cliente, responsavel, agente, franquia_agente=franquia,
        pedagio=Decimal("0.00"),
    )
    ac.save()
    ac.refresh_from_db()

    # Com franquia o valor nasce calculado — é o "antes" da linha de trilha.
    valor_agente_antes = ac.valor_agente
    assert valor_agente_antes is not None

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_pedagio_update", args=[ac.pk])
    response = client.post(url, {"pedagio": "25.00"})

    assert response.status_code == 200
    registros = AcionamentoHistorico.objects.filter(acionamento=ac)
    assert {r.campo for r in registros} == {"pedagio", "valor_agente"}

    reg_pedagio = registros.get(campo="pedagio")
    assert reg_pedagio.valor_anterior == "0.00"   # Decimal -> string
    assert reg_pedagio.valor_novo == "25.00"
    assert reg_pedagio.editado_por == user

    reg_valor = registros.get(campo="valor_agente")
    assert reg_valor.valor_anterior == str(valor_agente_antes)
    assert reg_valor.valor_novo == str(valor_agente_antes + Decimal("25.00"))
    assert reg_valor.editado_por == user


@pytest.mark.django_db
def test_pedagio_update_sem_franquia_gera_trilha_so_de_pedagio(
    client, django_user_model, _fks_acionamento
):
    """SEM franquia (DD-068: regime pendente): valor_agente/km_excedente/
    hora_excedente são None antes E depois — None -> None não é mudança, então
    a trilha deve registrar SÓ a linha do pedagio."""
    from controle_acionamentos.models import AcionamentoHistorico

    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente, pedagio=Decimal("0.00"))
    ac.save()
    ac.refresh_from_db()

    # Regime pendente: os três calculados nascem None (DD-068/ST2).
    assert ac.valor_agente is None
    assert ac.km_excedente is None
    assert ac.hora_excedente is None

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_pedagio_update", args=[ac.pk])
    response = client.post(url, {"pedagio": "25.00"})

    assert response.status_code == 200
    registros = AcionamentoHistorico.objects.filter(acionamento=ac)
    assert {r.campo for r in registros} == {"pedagio"}
    assert not registros.filter(
        campo__in=["valor_agente", "km_excedente", "hora_excedente"]
    ).exists()

    reg_pedagio = registros.get(campo="pedagio")
    assert reg_pedagio.valor_anterior == "0.00"
    assert reg_pedagio.valor_novo == "25.00"
    assert reg_pedagio.editado_por == user


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

    # valor_agente de cada um ANTES do POST (ambos SEM franquia: pendente/None
    # sob a DD-068 ST3). Mapa agnóstico ao regime — o rollback devolve este estado.
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
def test_vincular_franquia_lote_identica_sem_flag_nao_renderiza_confirmacao(
    client, django_user_model, _fks_acionamento
):
    """DD-051/ST2 (AC-06.5 REVISADO) — franquia IDÊNTICA à já vinculada não é
    conflito: a view NÃO renderiza a confirmação — executa o lote e redireciona
    (302), vinculando também o item livre.

    EVOLUÇÃO EXPLÍCITA do contrato DD-015 (não silenciosa): este cenário (lote com
    a MESMA franquia do item já vinculado) antes renderizava a confirmação (200) —
    tanto que a função se chamava ..._conflito_sem_flag_renderiza_confirmacao. A
    confirmação só sobrevive para franquia DIFERENTE, coberta por
    test_vincular_franquia_lote_confirmado_sobrescreve_e_redireciona e
    test_confirmacao_etapa1_reenvia_hidden_fieis_para_etapa2 (que usam franquia
    distinta da já vinculada)."""
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

    # AC-06.5 revisado: franquia idêntica não é conflito → a view NÃO renderiza a
    # confirmação; executa o lote e redireciona.
    assert response.status_code == 302
    assert (
        "controle_acionamentos/acionamento_vincular_confirmar.html"
        not in [t.name for t in response.templates]
    )

    # O lote executou: o item livre passou a apontar para a franquia.
    livre.refresh_from_db()
    assert livre.franquia_agente_id == franquia.pk


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


@pytest.mark.django_db
def test_confirmacao_etapa1_vocabulario_recalculo_so_do_agente(
    client, django_user_model, _fks_acionamento
):
    """DD-069/ST4 (RED) — vocabulário da confirmação de sobrescrita: com as duas
    colunas de valor (ST2), o vínculo de franquia recalcula SÓ o valor do
    AGENTE — o do cliente vem do serviço e não muda. O alerta troca "e os
    valores a pagar serão recalculados" por "e o valor do agente será
    recalculado. O valor do cliente não muda."; o rodapé ganha "do agente" em
    "recalcula o valor do agente de todos os selecionados". Mesmo arranjo de
    conflito do teste da etapa 1→2 (franquia DIFERENTE da já vinculada)."""
    cliente, responsavel, agente = _fks_acionamento
    franquia_antiga = FranquiaAgente.objects.create(
        **_dados_franquia(cliente, nome="Franquia Antiga")
    )
    franquia_nova = FranquiaAgente.objects.create(
        **_dados_franquia(cliente, nome="Franquia Nova")
    )
    base = timezone.now()

    ja_vinculado = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=franquia_antiga,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=5),
    )
    ja_vinculado.save()

    user = _user_com_perms(
        django_user_model, "view_acionamento", "change_acionamento"
    )
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")
    # Etapa 1: conflito sem flag → página de confirmação (200).
    response = client.post(
        url,
        {"acionamentos": [ja_vinculado.pk], "franquia": franquia_nova.pk},
    )

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert "o valor do agente será recalculado" in conteudo
    assert "recalcula o valor do agente de todos os selecionados" in conteudo
    assert "valores a pagar" not in conteudo


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
    """DD-048 + DD-068/ST3 — soma valor_agente só dos acionamentos do mês/ano de
    `hoje`, e acionamento SEM franquia entra como NULL (pendente) — o Sum do
    banco o ignora, sem virar zero na conta.

    Caso misto: em jun/2026, um COM franquia (único que soma) e um SEM franquia
    (pendente, ignorado); em mai/2026, outro com franquia (ignorado pela data).
    O valor_agente é computado no save (recalcular_valor_agente), então a soma
    esperada é o valor do registro de dentro, lido do banco (Decimal, não float).
    """
    from datetime import date, datetime

    from controle_acionamentos.selectors import somar_valor_agente_no_mes

    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente))

    dentro = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=franquia,
        data_hora_solicitado=timezone.make_aware(datetime(2026, 6, 10, 9, 0)),
        data_hora_inicio=timezone.make_aware(datetime(2026, 6, 10, 9, 30)),
        data_hora_final=timezone.make_aware(datetime(2026, 6, 10, 12, 0)),
    )
    dentro.save()
    dentro.refresh_from_db()

    pendente_no_mes = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=None,  # pendente: valor_agente NULL, fora da soma
        data_hora_solicitado=timezone.make_aware(datetime(2026, 6, 12, 9, 0)),
        data_hora_inicio=timezone.make_aware(datetime(2026, 6, 12, 9, 30)),
        data_hora_final=timezone.make_aware(datetime(2026, 6, 12, 12, 0)),
    )
    pendente_no_mes.save()

    fora = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=franquia,
        data_hora_solicitado=timezone.make_aware(datetime(2026, 5, 20, 9, 0)),
        data_hora_inicio=timezone.make_aware(datetime(2026, 5, 20, 9, 30)),
        data_hora_final=timezone.make_aware(datetime(2026, 5, 20, 12, 0)),
    )
    fora.save()

    resultado = somar_valor_agente_no_mes(hoje=date(2026, 6, 15))

    assert dentro.valor_agente is not None      # com franquia, a conta roda
    assert resultado == dentro.valor_agente     # o pendente NÃO entrou na soma
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


@pytest.mark.django_db
def test_home_rotulo_do_card_de_valor_e_do_agente_no_mes(client, django_user_model):
    """DD-069/ST3 (RED) — o 3º card de indicadores troca o rótulo genérico
    "Valor total do mês" por "Valor do agente no mês": com as duas colunas de
    valor na listagem (ST2), o nome precisa dizer QUAL valor o número soma
    (somar_valor_agente_no_mes). O rótulo antigo não pode sobrar na home."""
    user = django_user_model.objects.create_user(username="home_rotulo", password="x")
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:index"))

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert "Valor do agente no mês" in conteudo
    assert "Valor total do mês" not in conteudo


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

    DD-068/ST3: quem manda no valor do agente é a FRANQUIA vinculada (o inline
    morreu como fonte), então o arrange nasce COM franquia e a edição muda o
    km_final (100 → 240) — insumo real da conta. O snapshot do serviço
    (DD-067 ST2) segue persistindo nos campos inline (valor_acionamento == 600),
    mas NÃO alimenta o valor_agente. Após o POST: 302 para o detalhe e
    valor_agente (a) diferente do anterior E (b) igual ao que o próprio service
    recalcular_valor_agente produz para o mesmo cenário — sem número mágico.
    """
    from controle_acionamentos.services import recalcular_valor_agente

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
    params = dict(
        franquia_agente=franquia,
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

    # Serviço de 600 (demais valores idênticos aos do cenário) que o POST vai
    # aplicar: o snapshot passa a ser a fonte dos campos inline (não mais o
    # campo digitado). Ativo e do mesmo cliente para o form aceitar.
    servico = ServicoCliente.objects.create(
        cliente=cliente,
        nome=_SERVICOS_EM_ORDEM[0],
        ativo=True,
        valor_acionamento=Decimal("600.00"),
        franquia_km=80,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.00"),
        valor_hora_excedente=Decimal("30.00"),
    )

    # Espelho PURO do que o service deve produzir após a edição (km_final 240 +
    # snapshot 600 no inline, mesma franquia): não persistido, só para extrair o
    # valor_agente esperado.
    esperado = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        **{
            **params,
            "km_final": 240,
            "valor_acionamento": Decimal("600.00"),
        },
    )
    recalcular_valor_agente(esperado)

    user = _user_com_perms(django_user_model, "view_acionamento", "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    payload = _post_payload_acionamento(ac, servico_cliente=servico.pk, km_final=240)
    response = client.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse(
        "controle_acionamentos:acionamento_detail", args=[ac.pk]
    )

    ac.refresh_from_db()
    assert ac.valor_acionamento == Decimal("600.00")       # do snapshot do serviço
    assert ac.valor_agente is not None                     # com franquia, a conta roda
    assert ac.valor_agente != valor_agente_antes           # recalculou de fato (km mudou)
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


# --- DD-049 ST3: service registrar_edicao_acionamento (RED) ---
# O service AINDA NÃO EXISTE — estes 3 testes nascem VERMELHOS por ImportError.
# Imports (service E model) ficam DENTRO de cada corpo para isolar o ImportError
# e manter os 123 existentes coletáveis. Contrato exercitado:
#   registrar_edicao_acionamento(antigo, novo, editado_por)
#     antigo = foto do banco ANTES do save; novo = instância já salva.
#   Compara CAMPOS_AUDITADOS (editáveis do form + calculados financeiros).
#   Grava um AcionamentoHistorico por campo mudado; str() serializa; Decimal
#   vira string; None vira "". Retorna a lista de registros criados.


@pytest.mark.django_db
def test_registrar_edicao_um_campo_gera_um_registro(
    django_user_model, _fks_acionamento
):
    """Edita só nome_servico (não-financeiro, sem recálculo): um único registro,
    com valor_anterior/valor_novo corretos e os FKs certos."""
    from controle_acionamentos.models import AcionamentoHistorico
    from controle_acionamentos.services import registrar_edicao_acionamento

    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente, nome_servico="Reboque leve")
    ac.save()
    user = _user_com_perms(django_user_model)

    antigo = Acionamento.objects.get(pk=ac.pk)  # foto do estado atual
    ac.nome_servico = "Reboque pesado"
    ac.save()

    registros = registrar_edicao_acionamento(antigo, ac, user)

    assert len(registros) == 1
    assert AcionamentoHistorico.objects.count() == 1
    reg = registros[0]
    assert reg.campo == "nome_servico"
    assert reg.valor_anterior == "Reboque leve"
    assert reg.valor_novo == "Reboque pesado"
    assert reg.editado_por == user
    assert reg.acionamento == ac


@pytest.mark.django_db
def test_registrar_edicao_n_campos_gera_um_registro_por_campo(
    django_user_model, _fks_acionamento
):
    """Edita nome_servico E pedagio; COM franquia vinculada (DD-068/ST3: única
    fonte do valor do agente — sem ela seria None → None, sem registro) o save
    recalcula valor_agente (pedágio soma) → 3 mudanças, 3 registros. Crava a
    serialização Decimal->string no registro do pedagio."""
    from controle_acionamentos.models import AcionamentoHistorico
    from controle_acionamentos.services import registrar_edicao_acionamento

    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente))
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=franquia,
        nome_servico="Reboque leve",
        pedagio=Decimal("0.00"),
    )
    ac.save()
    user = _user_com_perms(django_user_model)

    antigo = Acionamento.objects.get(pk=ac.pk)  # foto do estado atual
    ac.nome_servico = "Reboque pesado"
    ac.pedagio = Decimal("25.00")
    ac.save()  # recalcula valor_agente (pedágio soma)

    registros = registrar_edicao_acionamento(antigo, ac, user)

    assert {r.campo for r in registros} == {"nome_servico", "pedagio", "valor_agente"}
    assert AcionamentoHistorico.objects.count() == 3
    reg_pedagio = next(r for r in registros if r.campo == "pedagio")
    assert reg_pedagio.valor_novo == "25.00"  # Decimal -> string


@pytest.mark.django_db
def test_registrar_edicao_sem_mudanca_nao_gera_registro(
    django_user_model, _fks_acionamento
):
    """Save sem alterar nada: nenhuma diferença → nada gravado, lista vazia."""
    from controle_acionamentos.models import AcionamentoHistorico
    from controle_acionamentos.services import registrar_edicao_acionamento

    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()
    user = _user_com_perms(django_user_model)

    antigo = Acionamento.objects.get(pk=ac.pk)  # foto do estado atual
    ac.save()  # sem alterar nenhum campo

    registros = registrar_edicao_acionamento(antigo, ac, user)

    assert registros == []
    assert AcionamentoHistorico.objects.count() == 0


# --- DD-049 ST3 (integração): view acionamento_update grava trilha (RED) ---
# A view ainda NÃO chama registrar_edicao_acionamento. Imports de
# AcionamentoHistorico dentro do corpo (consistência do bloco). As datas são
# ALINHADAS ao minuto (.replace(second=0, microsecond=0)) porque o
# _post_payload_acionamento serializa em '%Y-%m-%dT%H:%M' (precisão de minuto):
# assim o POST "idêntico" volta sem perda e não gera diff espúrio de data.


@pytest.mark.django_db
def test_acionamento_update_post_gera_trilha_de_auditoria(
    client, django_user_model, _fks_acionamento
):
    """POST que muda pedagio (0->25) deve gravar a trilha via a view: COM
    franquia vinculada (DD-068/ST3: única fonte do valor do agente) o pedágio
    soma no valor_agente, então a auditoria registra 'pedagio' e 'valor_agente',
    ambos atribuídos ao usuário logado e ao acionamento editado.

    Contrato evoluiu na DD-067 ST2: o serviço é obrigatório no POST. O acionamento
    já NASCE com o serviço aplicado (valores idênticos aos do molde), então
    reaplicar o MESMO serviço na edição não muda os campos do snapshot — só o
    pedágio (e o valor_agente derivado da franquia) entram na trilha. O payload
    reenviado pelo _post_payload_acionamento preserva a franquia_agente."""
    from controle_acionamentos.models import AcionamentoHistorico

    cliente, responsavel, agente = _fks_acionamento
    servico = _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=True)
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente))
    base = timezone.now().replace(second=0, microsecond=0)
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=franquia,
        pedagio=Decimal("0.00"),
        data_hora_solicitado=base,
        data_hora_inicio=base + timedelta(minutes=30),
        data_hora_final=base + timedelta(hours=3),
    )
    aplicar_servico_ao_acionamento(ac, servico)
    ac.save()
    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    payload = _post_payload_acionamento(ac, servico_cliente=servico.pk, pedagio="25.00")
    response = client.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse(
        "controle_acionamentos:acionamento_detail", args=[ac.pk]
    )

    registros = list(AcionamentoHistorico.objects.all())
    campos = {r.campo for r in registros}
    assert "pedagio" in campos
    assert "valor_agente" in campos
    for r in registros:
        assert r.editado_por == user
        assert r.acionamento == ac


@pytest.mark.django_db
def test_acionamento_update_post_sem_mudanca_nao_gera_trilha(
    client, django_user_model, _fks_acionamento
):
    """Guarda de regressão: POST idêntico ao estado atual não gera trilha.

    NOTA: já nasce VERDE — no RED a view ainda não grava nada. O papel deste
    teste é travar o comportamento 'sem mudança => sem histórico' para o GREEN
    não regredir (o payload de minuto volta sem perda, então não há diff).

    Contrato evoluiu na DD-067 ST2: o serviço é obrigatório no POST. O acionamento
    nasce com o serviço aplicado e o POST reenvia o MESMO serviço — reaplicar não
    altera nada, então segue sem trilha."""
    from controle_acionamentos.models import AcionamentoHistorico

    cliente, responsavel, agente = _fks_acionamento
    servico = _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=True)
    base = timezone.now().replace(second=0, microsecond=0)
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        data_hora_solicitado=base,
        data_hora_inicio=base + timedelta(minutes=30),
        data_hora_final=base + timedelta(hours=3),
    )
    aplicar_servico_ao_acionamento(ac, servico)
    ac.save()
    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    payload = _post_payload_acionamento(ac, servico_cliente=servico.pk)  # estado atual
    response = client.post(url, payload)

    assert response.status_code == 302
    assert AcionamentoHistorico.objects.count() == 0


@pytest.mark.django_db
def test_acionamento_update_atomicidade_rollback(
    client, django_user_model, _fks_acionamento, monkeypatch
):
    """Atomicidade: se a gravação da trilha falhar, o save do acionamento também
    é desfeito (mesmo transaction.atomic). Patch no PONTO DE USO (views) para
    fazer registrar_edicao_acionamento explodir.

    NOTA: no RED este teste falha por AttributeError — o nome ainda não existe
    em controle_acionamentos.views (a view não importa/chama o service).

    Contrato evoluiu na DD-067 ST2: o serviço é obrigatório no POST; o acionamento
    nasce com o serviço aplicado e o POST reenvia esse serviço."""
    from controle_acionamentos.models import AcionamentoHistorico

    cliente, responsavel, agente = _fks_acionamento
    servico = _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=True)
    base = timezone.now().replace(second=0, microsecond=0)
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        pedagio=Decimal("0.00"),
        data_hora_solicitado=base,
        data_hora_inicio=base + timedelta(minutes=30),
        data_hora_final=base + timedelta(hours=3),
    )
    aplicar_servico_ao_acionamento(ac, servico)
    ac.save()
    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)

    def _explode(*args, **kwargs):
        raise RuntimeError("falha proposital para provar o rollback")

    monkeypatch.setattr(
        "controle_acionamentos.views.registrar_edicao_acionamento", _explode
    )

    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    payload = _post_payload_acionamento(ac, servico_cliente=servico.pk, pedagio="25.00")
    with pytest.raises(RuntimeError):
        client.post(url, payload)

    assert AcionamentoHistorico.objects.count() == 0
    ac.refresh_from_db()
    assert ac.pedagio == Decimal("0.00")  # o save também sofreu rollback


# --- DD-049 ST4: exibição do histórico no detalhe (RED) ---
# Selector listar_historico_do_acionamento e a seção "Histórico de edições" no
# detalhe AINDA NÃO EXISTEM. Imports do selector/model DENTRO do corpo (isola o
# ImportError, mantém a suíte coletável). Contrato do selector (query pura):
#   listar_historico_do_acionamento(acionamento) -> queryset dos históricos
#   DAQUELE acionamento, mais recente primeiro (Meta.ordering do model), com
#   select_related("editado_por") (o template mostra quem editou — evita N+1).
# RED: testes 1 e 2 falham por ImportError; o 3 por AssertionError (a seção não
# existe no template).


@pytest.mark.django_db
def test_listar_historico_do_acionamento_filtra_e_ordena(
    django_user_model, _fks_acionamento
):
    """Retorna só os históricos do acionamento pedido, mais recente primeiro —
    não vaza o histórico de outro acionamento."""
    from controle_acionamentos.models import AcionamentoHistorico
    from controle_acionamentos.selectors import listar_historico_do_acionamento

    cliente, responsavel, agente = _fks_acionamento
    ac_a = _acionamento_valido(cliente, responsavel, agente)
    ac_a.save()
    ac_b = _acionamento_valido(cliente, responsavel, agente)
    ac_b.save()
    user = _user_com_perms(django_user_model)

    a1 = AcionamentoHistorico.objects.create(
        acionamento=ac_a, editado_por=user,
        campo="pedagio", valor_anterior="0.00", valor_novo="10.00",
    )
    a2 = AcionamentoHistorico.objects.create(
        acionamento=ac_a, editado_por=user,
        campo="pedagio", valor_anterior="10.00", valor_novo="20.00",
    )
    AcionamentoHistorico.objects.create(
        acionamento=ac_b, editado_por=user,
        campo="pedagio", valor_anterior="0.00", valor_novo="5.00",
    )

    # Força a1 mais antigo que a2 (update() NÃO dispara auto_now_add) — padrão ST2.
    AcionamentoHistorico.objects.filter(pk=a1.pk).update(
        editado_em=timezone.now() - timedelta(hours=1)
    )

    resultado = list(listar_historico_do_acionamento(ac_a))

    assert resultado == [a2, a1]  # só os de A, mais recente primeiro


@pytest.mark.django_db
def test_listar_historico_sem_registros_retorna_vazio(
    django_user_model, _fks_acionamento
):
    """Acionamento sem histórico → queryset vazio."""
    from controle_acionamentos.selectors import listar_historico_do_acionamento

    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    assert listar_historico_do_acionamento(ac).count() == 0


@pytest.mark.django_db
def test_detalhe_renderiza_historico_de_edicoes(
    client, django_user_model, _fks_acionamento
):
    """O detalhe exibe a seção "Histórico de edições" com campo, valores antes/
    depois e quem editou (username "Fulano" = fallback de __str__/get_full_name)."""
    from controle_acionamentos.models import AcionamentoHistorico

    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()
    editor = django_user_model.objects.create_user(username="Fulano", password="x")
    AcionamentoHistorico.objects.create(
        acionamento=ac,
        editado_por=editor,
        campo="pedagio",
        valor_anterior="0.00",
        valor_novo="25.00",
    )

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_detail", args=[ac.pk])
    response = client.get(url)

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert "Histórico de edições" in conteudo
    assert "pedagio" in conteudo  # o campo (ou seu rótulo)
    assert "0.00" in conteudo
    assert "25.00" in conteudo
    assert "Fulano" in conteudo  # quem editou


# --- DD-049 ST5: botao Editar gated por change_acionamento (RED) ---
# O botão "Editar" ainda NÃO existe em nenhum template. Espelha o padrão dos
# testes do botão Novo (gating por permissão), mas a ÂNCORA é o href da rota
# acionamento_update (/acionamentos/<pk>/editar/): a palavra "Editar" solta
# poderia colidir com outro texto; o href é distintivo e não colide com os
# links de detalhe (/acionamentos/<pk>/) nem de pedágio (.../pedagio/).
# RED: os 2 "com_change" nascem VERMELHOS (AssertionError); os 2 "sem_change"
# podem nascer VERDES (o botão não existe p/ ninguém) — são guardas.


@pytest.mark.django_db
def test_listagem_sem_change_nao_exibe_botao_editar(
    client, django_user_model, _fks_acionamento
):
    """Guarda (pode nascer VERDE — o botão ainda não existe p/ ninguém): quem só
    tem view_acionamento NÃO vê o link de editar na listagem."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url)

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    url_editar = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    assert url_editar not in conteudo


@pytest.mark.django_db
def test_listagem_com_change_exibe_botao_editar(
    client, django_user_model, _fks_acionamento
):
    """view + change → o link de editar do registro aparece na listagem,
    apontando para acionamento_update do acionamento."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    user = _user_com_perms(
        django_user_model, "view_acionamento", "change_acionamento"
    )
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_list")
    response = client.get(url)

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    url_editar = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    assert url_editar in conteudo


@pytest.mark.django_db
def test_detalhe_sem_change_nao_exibe_botao_editar(
    client, django_user_model, _fks_acionamento
):
    """Guarda (pode nascer VERDE): no detalhe, quem só tem view_acionamento NÃO
    vê o link de editar."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_detail", args=[ac.pk])
    response = client.get(url)

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    url_editar = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    assert url_editar not in conteudo


@pytest.mark.django_db
def test_detalhe_com_change_exibe_botao_editar(
    client, django_user_model, _fks_acionamento
):
    """view + change → o botão de editar aparece no detalhe, apontando para
    acionamento_update."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()

    user = _user_com_perms(
        django_user_model, "view_acionamento", "change_acionamento"
    )
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_detail", args=[ac.pk])
    response = client.get(url)

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    url_editar = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    assert url_editar in conteudo


# --- DD-050 ST1: telas de Cliente (lista/criar/editar) (RED) ---
# Views/urls/forms/templates de Cliente ainda NÃO existem. reverse() DENTRO de
# cada corpo: no RED a rota não existe e o NoReverseMatch deve falhar SÓ estes
# testes, sem quebrar a coleção dos 136 já verdes.


class TestViewsCliente:
    """DD-050/ST1 (RED) — telas de Cliente no padrão de permissões do app:
    @login_required + @permission_required(raise_exception=True).

    CONTRATO DE ROTAS para o GREEN (mesma convenção EN do acionamento_*):
      controle_acionamentos:cliente_list    -> lista   (view_cliente)
      controle_acionamentos:cliente_create  -> criar   (add_cliente)
      controle_acionamentos:cliente_update  -> editar, kwarg pk (change_cliente)

    CNPJ do payload: 11.222.333/0001-81 (válido no dígito verificador); o
    Cliente.clean() normaliza para dígitos e valida.
    """

    @pytest.mark.django_db
    def test_lista_exige_login(self, client):
        """Anônimo na lista → 302 para o login (login_required)."""
        url = reverse("controle_acionamentos:cliente_list")
        response = client.get(url)

        assert response.status_code == 302
        assert "login" in response.url

    @pytest.mark.django_db
    def test_lista_exige_permissao_view(self, client, django_user_model):
        """Logado SEM view_cliente → 403 (permission_required raise_exception)."""
        user = django_user_model.objects.create_user(username="sem_perm", password="x")
        client.force_login(user)

        url = reverse("controle_acionamentos:cliente_list")
        response = client.get(url)

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_lista_renderiza_com_cliente(self, client, django_user_model):
        """Com view_cliente → 200 e o nome do cliente criado aparece na lista."""
        Cliente.objects.create(nome_empresa="Empresa Alfa SA", cnpj="11222333000181")
        user = _user_com_perms(django_user_model, "view_cliente")
        client.force_login(user)

        url = reverse("controle_acionamentos:cliente_list")
        response = client.get(url)

        assert response.status_code == 200
        conteudo = response.content.decode(response.charset)
        assert "Empresa Alfa SA" in conteudo

    @pytest.mark.django_db
    def test_criar_exige_permissao_add(self, client, django_user_model):
        """Ver não é criar: quem só tem view_cliente NÃO acessa o criar (403)."""
        user = _user_com_perms(django_user_model, "view_cliente")
        client.force_login(user)

        url = reverse("controle_acionamentos:cliente_create")
        response = client.get(url)

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_criar_post_valido_cria_e_redireciona(self, client, django_user_model):
        """Com add_cliente, POST válido cria o Cliente e redireciona (302).

        Contrato evoluiu na DD-066 ST2: o catálogo de serviços viaja no mesmo
        POST do cliente; o teste passa a enviar o management form com as 5 linhas
        em branco (linhas em branco são válidas — nenhum serviço criado)."""
        user = _user_com_perms(django_user_model, "add_cliente")
        client.force_login(user)

        url = reverse("controle_acionamentos:cliente_create")
        data = {"nome_empresa": "Nova Empresa LTDA", "cnpj": "11.222.333/0001-81"}
        data.update(_payload_formset([{}, {}, {}, {}, {}]))
        response = client.post(url, data)

        assert response.status_code == 302
        assert Cliente.objects.count() == 1

    @pytest.mark.django_db
    def test_editar_exige_permissao_change(self, client, django_user_model):
        """Ver não é editar: quem só tem view_cliente NÃO acessa o editar (403)."""
        cliente = Cliente.objects.create(
            nome_empresa="Empresa Beta", cnpj="11222333000181"
        )
        user = _user_com_perms(django_user_model, "view_cliente")
        client.force_login(user)

        url = reverse("controle_acionamentos:cliente_update", args=[cliente.pk])
        response = client.get(url)

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_editar_post_valido_atualiza_e_redireciona(self, client, django_user_model):
        """Com change_cliente, POST válido atualiza o nome e redireciona (302).

        Contrato evoluiu na DD-066 ST2: o catálogo de serviços viaja no mesmo
        POST do cliente; o teste passa a enviar o management form com as 5 linhas
        em branco (linhas em branco são válidas — nenhum serviço alterado)."""
        cliente = Cliente.objects.create(
            nome_empresa="Nome Antigo", cnpj="11222333000181"
        )
        user = _user_com_perms(django_user_model, "change_cliente")
        client.force_login(user)

        url = reverse("controle_acionamentos:cliente_update", args=[cliente.pk])
        data = {"nome_empresa": "Nome Novo", "cnpj": "11.222.333/0001-81"}
        data.update(_payload_formset([{}, {}, {}, {}, {}]))
        response = client.post(url, data)

        assert response.status_code == 302
        cliente.refresh_from_db()
        assert cliente.nome_empresa == "Nome Novo"


# --- DD-050 ST2: telas de Agente (lista/criar/editar) (RED) ---
# Views/urls/forms/templates de Agente ainda NÃO existem. reverse() DENTRO de
# cada corpo: no RED a rota não existe e o NoReverseMatch deve falhar SÓ estes
# testes, sem quebrar a coleção já verde.


class TestViewsAgente:
    """DD-050/ST2 (RED) — telas de Agente no padrão de permissões do app:
    @login_required + @permission_required(raise_exception=True).

    CONTRATO DE ROTAS para o GREEN (mesma convenção EN do acionamento_*):
      controle_acionamentos:agente_list    -> lista   (view_agente)
      controle_acionamentos:agente_create  -> criar   (add_agente)
      controle_acionamentos:agente_update  -> editar, kwarg pk (change_agente)

    Payload: CPF 529.982.247-25 (válido no dígito verificador; o Agente.clean()
    normaliza para dígitos e valida). CNH fica vazia (blank=True, opcional). O
    M2M clientes_vinculados é blank=True → opcional no form (criar sem vínculo
    é válido). Clientes de apoio usam CNPJs válidos e DISTINTOS (unique).
    """

    @pytest.mark.django_db
    def test_lista_exige_login(self, client):
        """Anônimo na lista → 302 para o login (login_required)."""
        url = reverse("controle_acionamentos:agente_list")
        response = client.get(url)

        assert response.status_code == 302
        assert "login" in response.url

    @pytest.mark.django_db
    def test_lista_exige_permissao_view(self, client, django_user_model):
        """Logado SEM view_agente → 403 (permission_required raise_exception)."""
        user = django_user_model.objects.create_user(username="sem_perm", password="x")
        client.force_login(user)

        url = reverse("controle_acionamentos:agente_list")
        response = client.get(url)

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_lista_renderiza_com_agente(self, client, django_user_model):
        """Com view_agente → 200 e o nome do agente criado aparece na lista."""
        Agente.objects.create(nome="Carlos Agente", cpf="52998224725")
        user = _user_com_perms(django_user_model, "view_agente")
        client.force_login(user)

        url = reverse("controle_acionamentos:agente_list")
        response = client.get(url)

        assert response.status_code == 200
        conteudo = response.content.decode(response.charset)
        assert "Carlos Agente" in conteudo

    @pytest.mark.django_db
    def test_criar_exige_permissao_add(self, client, django_user_model):
        """Ver não é criar: quem só tem view_agente NÃO acessa o criar (403)."""
        user = _user_com_perms(django_user_model, "view_agente")
        client.force_login(user)

        url = reverse("controle_acionamentos:agente_create")
        response = client.get(url)

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_criar_post_valido_sem_vinculos_cria_e_redireciona(
        self, client, django_user_model
    ):
        """Com add_agente, POST válido SEM clientes vinculados cria e redireciona
        (302). O M2M é opcional (blank=True)."""
        user = _user_com_perms(django_user_model, "add_agente")
        client.force_login(user)

        url = reverse("controle_acionamentos:agente_create")
        response = client.post(
            url,
            {"nome": "Novo Agente", "cpf": "529.982.247-25", "cnh": ""},
        )

        assert response.status_code == 302
        assert Agente.objects.count() == 1

    @pytest.mark.django_db
    def test_criar_post_valido_com_vinculos_persiste_dois(
        self, client, django_user_model
    ):
        """Com add_agente, POST com clientes_vinculados=[pk1, pk2] cria o agente e
        persiste os 2 vínculos M2M (302)."""
        c1 = Cliente.objects.create(nome_empresa="Alfa SA", cnpj="11222333000181")
        c2 = Cliente.objects.create(nome_empresa="Beta SA", cnpj="11444777000161")
        user = _user_com_perms(django_user_model, "add_agente")
        client.force_login(user)

        url = reverse("controle_acionamentos:agente_create")
        response = client.post(
            url,
            {
                "nome": "Agente Vinculado",
                "cpf": "529.982.247-25",
                "cnh": "",
                "clientes_vinculados": [c1.pk, c2.pk],
            },
        )

        assert response.status_code == 302
        agente = Agente.objects.get()
        assert agente.clientes_vinculados.count() == 2

    @pytest.mark.django_db
    def test_editar_exige_permissao_change(self, client, django_user_model):
        """Ver não é editar: quem só tem view_agente NÃO acessa o editar (403)."""
        agente = Agente.objects.create(nome="Agente Beta", cpf="52998224725")
        user = _user_com_perms(django_user_model, "view_agente")
        client.force_login(user)

        url = reverse("controle_acionamentos:agente_update", args=[agente.pk])
        response = client.get(url)

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_editar_post_valido_troca_vinculo_e_atualiza_nome(
        self, client, django_user_model
    ):
        """Com change_agente, POST troca o vínculo para [pk2] e atualiza o nome
        (302). O M2M final tem só c2; o nome é o novo."""
        c1 = Cliente.objects.create(nome_empresa="Alfa SA", cnpj="11222333000181")
        c2 = Cliente.objects.create(nome_empresa="Beta SA", cnpj="11444777000161")
        agente = Agente.objects.create(nome="Nome Antigo", cpf="52998224725")
        agente.clientes_vinculados.set([c1, c2])
        user = _user_com_perms(django_user_model, "change_agente")
        client.force_login(user)

        url = reverse("controle_acionamentos:agente_update", args=[agente.pk])
        response = client.post(
            url,
            {
                "nome": "Nome Novo",
                "cpf": "529.982.247-25",
                "cnh": "",
                "clientes_vinculados": [c2.pk],
            },
        )

        assert response.status_code == 302
        agente.refresh_from_db()
        assert agente.nome == "Nome Novo"
        assert agente.clientes_vinculados.count() == 1
        assert c2 in agente.clientes_vinculados.all()


# ---------------------------------------------------------------------------
# DD-050/ST2 — filtro de template `cpf` (irmão do `cnpj`). Formata 11 dígitos
# como 000.000.000-00; devolve o valor original se não tiver exatamente 11
# dígitos. Import LOCAL da função (padrão da suíte).
# ---------------------------------------------------------------------------


def test_filtro_cpf_formata_11_digitos():
    """11 dígitos viram a máscara 000.000.000-00."""
    from controle_acionamentos.templatetags.formatos import cpf

    assert cpf("52998224725") == "529.982.247-25"


def test_filtro_cpf_valor_invalido_retorna_original():
    """Sem 11 dígitos, o filtro devolve o valor original intocado."""
    from controle_acionamentos.templatetags.formatos import cpf

    assert cpf("123") == "123"


# --- DD-050 ST3: telas de Responsável (lista/criar/editar) (RED) ---
# Views/urls/forms/templates de ResponsavelAgente ainda NÃO existem. reverse()
# DENTRO de cada corpo: no RED a rota não existe e o NoReverseMatch deve falhar
# SÓ estes testes, sem quebrar a coleção já verde.


class TestViewsResponsavel:
    """DD-050/ST3 (RED) — telas de Responsável (ResponsavelAgente) no padrão de
    permissões do app: @login_required + @permission_required(raise_exception=True).

    CONTRATO DE ROTAS para o GREEN (mesma convenção EN do acionamento_*):
      controle_acionamentos:responsavel_list    -> lista   (view_responsavelagente)
      controle_acionamentos:responsavel_create  -> criar   (add_responsavelagente)
      controle_acionamentos:responsavel_update  -> editar, kwarg pk (change_responsavelagente)

    Entidade sem documento: só o campo `nome` (obrigatório, validado no
    ResponsavelAgente.clean()). Espelho direto da TestViewsCliente.
    """

    @pytest.mark.django_db
    def test_lista_exige_login(self, client):
        """Anônimo na lista → 302 para o login (login_required)."""
        url = reverse("controle_acionamentos:responsavel_list")
        response = client.get(url)

        assert response.status_code == 302
        assert "login" in response.url

    @pytest.mark.django_db
    def test_lista_exige_permissao_view(self, client, django_user_model):
        """Logado SEM view_responsavelagente → 403 (raise_exception)."""
        user = django_user_model.objects.create_user(username="sem_perm", password="x")
        client.force_login(user)

        url = reverse("controle_acionamentos:responsavel_list")
        response = client.get(url)

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_lista_renderiza_com_responsavel(self, client, django_user_model):
        """Com view_responsavelagente → 200 e o nome do responsável aparece."""
        ResponsavelAgente.objects.create(nome="João Supervisor")
        user = _user_com_perms(django_user_model, "view_responsavelagente")
        client.force_login(user)

        url = reverse("controle_acionamentos:responsavel_list")
        response = client.get(url)

        assert response.status_code == 200
        conteudo = response.content.decode(response.charset)
        assert "João Supervisor" in conteudo

    @pytest.mark.django_db
    def test_criar_exige_permissao_add(self, client, django_user_model):
        """Ver não é criar: quem só tem view NÃO acessa o criar (403)."""
        user = _user_com_perms(django_user_model, "view_responsavelagente")
        client.force_login(user)

        url = reverse("controle_acionamentos:responsavel_create")
        response = client.get(url)

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_criar_post_valido_cria_e_redireciona(self, client, django_user_model):
        """Com add_responsavelagente, POST válido cria e redireciona (302)."""
        user = _user_com_perms(django_user_model, "add_responsavelagente")
        client.force_login(user)

        url = reverse("controle_acionamentos:responsavel_create")
        response = client.post(url, {"nome": "Novo Responsável"})

        assert response.status_code == 302
        assert ResponsavelAgente.objects.count() == 1

    @pytest.mark.django_db
    def test_editar_post_valido_atualiza_e_redireciona(self, client, django_user_model):
        """Com change_responsavelagente, POST válido atualiza o nome e
        redireciona (302). Cobre implicitamente a rota update."""
        responsavel = ResponsavelAgente.objects.create(nome="Nome Antigo")
        user = _user_com_perms(django_user_model, "change_responsavelagente")
        client.force_login(user)

        url = reverse("controle_acionamentos:responsavel_update", args=[responsavel.pk])
        response = client.post(url, {"nome": "Nome Novo"})

        assert response.status_code == 302
        responsavel.refresh_from_db()
        assert responsavel.nome == "Nome Novo"


# --- DD-050 ST4: telas de Franquia (lista/criar/editar) (RED) ---
# Views/urls/forms/templates de FranquiaAgente ainda NÃO existem. reverse()
# DENTRO de cada corpo: no RED a rota não existe e o NoReverseMatch deve falhar
# SÓ estes testes, sem quebrar a coleção já verde.


def _franquia_form_payload(cliente, **overrides):
    """Payload de POST do form de Franquia: FK por pk; monetários como STRINGS
    decimais (nunca float); escalonamento_automatico é checkbox — ausente = off,
    "on" = ligado. `overrides` troca campos pontuais."""
    payload = {
        "cliente": cliente.pk,
        "nome": "Franquia Moto 80km/4h",
        "valor_acionamento": "150.00",
        "franquia_km": "80",
        "franquia_horas": "4.00",
        "valor_km_excedente": "2.50",
        "valor_hora_excedente": "30.00",
        # escalonamento_automatico: checkbox — omitido = False
    }
    payload.update(overrides)
    return payload


class TestViewsFranquia:
    """DD-050/ST4 (RED) — telas de Franquia (FranquiaAgente) no padrão de
    permissões do app: @login_required + @permission_required(raise_exception=True).

    CONTRATO DE ROTAS para o GREEN (mesma convenção EN do acionamento_*):
      controle_acionamentos:franquia_list    -> lista   (view_franquiaagente)
      controle_acionamentos:franquia_create  -> criar   (add_franquiaagente)
      controle_acionamentos:franquia_update  -> editar, kwarg pk (change_franquiaagente)

    Monetários no payload como strings decimais ("150.00"); FK por pk. Regra do
    clean: escalonamento_automatico ligado com franquia_km=0 é rejeitado.
    """

    @pytest.mark.django_db
    def test_lista_exige_login(self, client):
        """Anônimo na lista → 302 para o login (login_required)."""
        url = reverse("controle_acionamentos:franquia_list")
        response = client.get(url)

        assert response.status_code == 302
        assert "login" in response.url

    @pytest.mark.django_db
    def test_lista_exige_permissao_view(self, client, django_user_model):
        """Logado SEM view_franquiaagente → 403 (raise_exception)."""
        user = django_user_model.objects.create_user(username="sem_perm", password="x")
        client.force_login(user)

        url = reverse("controle_acionamentos:franquia_list")
        response = client.get(url)

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_lista_renderiza_com_franquia(self, client, django_user_model):
        """Com view_franquiaagente → 200; o nome da franquia E o nome do cliente
        dela aparecem na lista."""
        cliente = Cliente.objects.create(nome_empresa="ACME LTDA", cnpj="11222333000181")
        FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia Alfa"))
        user = _user_com_perms(django_user_model, "view_franquiaagente")
        client.force_login(user)

        url = reverse("controle_acionamentos:franquia_list")
        response = client.get(url)

        assert response.status_code == 200
        conteudo = response.content.decode(response.charset)
        assert "Franquia Alfa" in conteudo
        assert "ACME LTDA" in conteudo

    @pytest.mark.django_db
    def test_criar_exige_permissao_add(self, client, django_user_model):
        """Ver não é criar: quem só tem view NÃO acessa o criar (403)."""
        user = _user_com_perms(django_user_model, "view_franquiaagente")
        client.force_login(user)

        url = reverse("controle_acionamentos:franquia_create")
        response = client.get(url)

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_criar_post_valido_cria_e_redireciona(self, client, django_user_model):
        """Com add_franquiaagente, POST válido (valores Decimal como strings,
        escalonamento off) cria a franquia e redireciona (302)."""
        cliente = Cliente.objects.create(nome_empresa="ACME LTDA", cnpj="11222333000181")
        user = _user_com_perms(django_user_model, "add_franquiaagente")
        client.force_login(user)

        url = reverse("controle_acionamentos:franquia_create")
        response = client.post(url, _franquia_form_payload(cliente))

        assert response.status_code == 302
        assert FranquiaAgente.objects.count() == 1

    @pytest.mark.django_db
    def test_criar_post_invalido_km_zero_com_escalonamento_nao_cria(
        self, client, django_user_model
    ):
        """POST INVÁLIDO (franquia_km=0 + escalonamento ligado) é barrado pelo
        clean: form re-renderiza (200) e nada é gravado (count == 0)."""
        cliente = Cliente.objects.create(nome_empresa="ACME LTDA", cnpj="11222333000181")
        user = _user_com_perms(django_user_model, "add_franquiaagente")
        client.force_login(user)

        url = reverse("controle_acionamentos:franquia_create")
        response = client.post(
            url,
            _franquia_form_payload(
                cliente, franquia_km="0", escalonamento_automatico="on"
            ),
        )

        assert response.status_code == 200
        assert FranquiaAgente.objects.count() == 0

    @pytest.mark.django_db
    def test_editar_post_valido_atualiza_e_redireciona(self, client, django_user_model):
        """Com change_franquiaagente, POST válido atualiza um valor e redireciona
        (302). refresh confirma o novo valor_acionamento."""
        cliente = Cliente.objects.create(nome_empresa="ACME LTDA", cnpj="11222333000181")
        franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente))
        user = _user_com_perms(django_user_model, "change_franquiaagente")
        client.force_login(user)

        url = reverse("controle_acionamentos:franquia_update", args=[franquia.pk])
        response = client.post(
            url,
            _franquia_form_payload(
                cliente, nome=franquia.nome, valor_acionamento="200.00"
            ),
        )

        assert response.status_code == 302
        franquia.refresh_from_db()
        assert franquia.valor_acionamento == Decimal("200.00")

    @pytest.mark.django_db
    def test_editar_franquia_nao_altera_acionamento_antigo(
        self, client, django_user_model, _fks_acionamento
    ):
        """REGRA DO CARD (§18): editar uma franquia NÃO altera acionamento já
        registrado. Cria acionamento vinculado à franquia, guarda o valor_agente
        persistido; edita a franquia pela VIEW mudando valor_km_excedente; o
        valor_agente do acionamento antigo permanece congelado."""
        cliente, responsavel, agente = _fks_acionamento
        franquia = FranquiaAgente.objects.create(
            **_dados_franquia(
                cliente,
                valor_km_excedente=Decimal("2.50"),
                escalonamento_automatico=True,
            )
        )
        ac = _acionamento_valido(cliente, responsavel, agente, franquia_agente=franquia)
        ac.save()
        ac.refresh_from_db()
        valor_agente_congelado = ac.valor_agente

        user = _user_com_perms(django_user_model, "change_franquiaagente")
        client.force_login(user)

        url = reverse("controle_acionamentos:franquia_update", args=[franquia.pk])
        response = client.post(
            url,
            _franquia_form_payload(
                cliente,
                nome=franquia.nome,
                valor_km_excedente="9.99",  # tarifa muito diferente
                escalonamento_automatico="on",
            ),
        )

        assert response.status_code == 302
        ac.refresh_from_db()
        assert ac.valor_agente == valor_agente_congelado


# ---------------------------------------------------------------
# DD-050/ST5 — Navegação: fileira de Cadastros na home + contadores (RED)
#
# Contadores puros em selectors.py (contar_clientes/agentes/responsaveis/
# franquias) e a fileira de cadastros na home, cada item gated pela view_<model>
# correspondente. Os 4 testes de selector importam DENTRO do corpo: as funções
# ainda NÃO existem, então o ImportError derruba SÓ estes, sem quebrar a coleta
# dos testes já verdes. Os 2 testes de view usam a home (rota já existe) e
# nascem vermelhos por ASSERT — a fileira ainda não está no template.
# ---------------------------------------------------------------


@pytest.mark.django_db
def test_contar_clientes_conta_todos():
    """DD-050/ST5 — contar_clientes() devolve o total de Clientes cadastrados."""
    from controle_acionamentos.selectors import contar_clientes

    Cliente.objects.create(nome_empresa="Alfa SA", cnpj="11222333000181")
    Cliente.objects.create(nome_empresa="Beta SA", cnpj="11444777000161")

    assert contar_clientes() == 2


@pytest.mark.django_db
def test_contar_agentes_conta_todos():
    """DD-050/ST5 — contar_agentes() devolve o total de Agentes cadastrados."""
    from controle_acionamentos.selectors import contar_agentes

    Agente.objects.create(nome="Carlos Agente", cpf="52998224725")

    assert contar_agentes() == 1


@pytest.mark.django_db
def test_contar_responsaveis_conta_todos():
    """DD-050/ST5 — contar_responsaveis() devolve o total de ResponsavelAgente."""
    from controle_acionamentos.selectors import contar_responsaveis

    ResponsavelAgente.objects.create(nome="João Supervisor")
    ResponsavelAgente.objects.create(nome="Maria Supervisora")

    assert contar_responsaveis() == 2


@pytest.mark.django_db
def test_contar_franquias_conta_todos():
    """DD-050/ST5 — contar_franquias() devolve o total de FranquiaAgente."""
    from controle_acionamentos.selectors import contar_franquias

    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    FranquiaAgente.objects.create(**_dados_franquia(cliente))

    assert contar_franquias() == 1


@pytest.mark.django_db
def test_home_renderiza_fileira_de_cadastros_com_contadores(
    client, django_user_model
):
    """DD-050/ST5 — com as 4 perms de leitura de cadastro, a home renderiza a
    fileira de cadastros: o HTML contém os links (reverse) das 4 listagens."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    Agente.objects.create(nome="Carlos Agente", cpf="52998224725")
    ResponsavelAgente.objects.create(nome="João Supervisor")
    FranquiaAgente.objects.create(**_dados_franquia(cliente))

    user = _user_com_perms(
        django_user_model,
        "view_cliente",
        "view_agente",
        "view_responsavelagente",
        "view_franquiaagente",
    )
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:index"))

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert reverse("controle_acionamentos:cliente_list") in conteudo
    assert reverse("controle_acionamentos:agente_list") in conteudo
    assert reverse("controle_acionamentos:responsavel_list") in conteudo
    assert reverse("controle_acionamentos:franquia_list") in conteudo


@pytest.mark.django_db
def test_home_sem_perm_de_cadastro_nao_exibe_fileira(client, django_user_model):
    """DD-050/ST5 — usuário SEM nenhuma das 4 perms de cadastro: a home abre
    (200), mas a fileira não aparece — o link de cliente_list NÃO está no HTML."""
    user = django_user_model.objects.create_user(username="sem_cad", password="x")
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:index"))

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert reverse("controle_acionamentos:cliente_list") not in conteudo


@pytest.mark.django_db
def test_home_com_perm_parcial_exibe_apenas_itens_permitidos(
    client, django_user_model
):
    """DD-050/ST5 — guarda de regressão do gating POR ITEM: com APENAS view_cliente,
    a home mostra só o link de Clientes; Agentes/Responsáveis/Franquias ficam de
    fora. A fileira da home E o dropdown do cabeçalho usam os mesmos links, cada um
    gated pela sua view_<model>. Este teste FALHA se alguém trocar o gating granular
    por um "qualquer perm mostra tudo" (a seção inteira aparece com ≥1 perm, mas os
    itens seguem individuais)."""
    user = _user_com_perms(django_user_model, "view_cliente")
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:index"))

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert reverse("controle_acionamentos:cliente_list") in conteudo
    assert reverse("controle_acionamentos:agente_list") not in conteudo
    assert reverse("controle_acionamentos:responsavel_list") not in conteudo
    assert reverse("controle_acionamentos:franquia_list") not in conteudo


# ---------------------------------------------------------------
# DD-051/ST1 — rastreio de criação (RED)
#
# Contrato que ainda NÃO existe no model/view/template:
#   - criado_por = FK p/ o User model, on_delete=PROTECT, null=True, editable=False
#   - criado_em  = DateTimeField(auto_now_add=True, null=True)  [o campo já existe;
#                  a ST1 só acrescenta null=True para a migration retroagir]
#   - acionamento_create grava criado_por = request.user
#   - detalhe: badge da franquia colado ao ACN no cabeçalho; linha
#     "criado por <nome> em <data> <hora>", exibida SÓ quando criado_por existe
#
# Os testes que dependem do campo novo nascem VERMELHOS: `criado_por` como kwarg
# do model ou como atributo estoura TypeError/AttributeError; get_field() estoura
# FieldDoesNotExist. Os guards de convenção (6 e 7) podem já nascer verdes — o
# template atual não tem "criado por" e já marca a franquia com .acn-badge-franquia.
# ---------------------------------------------------------------


@pytest.mark.django_db
def test_criado_em_preenchido_automaticamente_na_criacao(_fks_acionamento):
    """DD-051/ST1 — criar um Acionamento carimba criado_em (auto_now_add), nunca
    fica None. Guarda que o timestamp de criação é automático, não digitado."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)
    ac.save()
    ac.refresh_from_db()

    assert ac.criado_em is not None


@pytest.mark.django_db
def test_acionamento_create_grava_criado_por_do_request(
    client, django_user_model, _fks_acionamento
):
    """DD-051/ST1 — o POST de criação registra QUEM criou: criado_por = request.user.
    A view fina só carimba o autor; o cálculo segue no save() do model.

    Contrato evoluiu na DD-067 ST2: o serviço do cliente é obrigatório no POST do
    acionamento (o serviço substitui os antigos campos inline digitados)."""
    cliente, responsavel, agente = _fks_acionamento
    servico = _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=True)
    # Instância válida NÃO salva: serve só de molde para o payload do POST.
    molde = _acionamento_valido(cliente, responsavel, agente)
    payload = _post_payload_acionamento(molde, servico_cliente=servico.pk)

    user = _user_com_perms(django_user_model, "add_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_create")
    response = client.post(url, payload)

    assert response.status_code == 302
    acionamento = Acionamento.objects.get()
    assert acionamento.criado_por == user


@pytest.mark.django_db
def test_contrato_dos_campos_de_rastreio():
    """DD-051/ST1 — contrato dos campos via _meta (independe de dados):
    criado_por é FK opcional (null=True), não editável, PROTECT, apontando para o
    User model; criado_em tem auto_now_add=True."""
    campo_por = Acionamento._meta.get_field("criado_por")
    assert campo_por.null is True
    assert campo_por.editable is False
    assert campo_por.remote_field.on_delete is PROTECT
    assert campo_por.related_model is get_user_model()

    campo_em = Acionamento._meta.get_field("criado_em")
    assert campo_em.auto_now_add is True


@pytest.mark.django_db
def test_deletar_user_criador_levanta_protected_error(
    django_user_model, _fks_acionamento
):
    """DD-051/ST1 — PROTECT preserva a autoria: apagar o usuário que criou um
    acionamento é bloqueado (ProtectedError), como já ocorre com editado_por."""
    cliente, responsavel, agente = _fks_acionamento
    user = django_user_model.objects.create_user(username="criador", password="x")
    ac = _acionamento_valido(cliente, responsavel, agente, criado_por=user)
    ac.save()

    with pytest.raises(ProtectedError):
        user.delete()


@pytest.mark.django_db
def test_detalhe_exibe_linha_criado_por(
    client, django_user_model, _fks_acionamento
):
    """DD-051/ST1 — com criado_por preenchido, o detalhe mostra a linha de autoria
    ("criado por <nome>"). Usuário SEM nome completo → exibe o username, o que
    torna o assert robusto a get_full_name|default:username no template."""
    cliente, responsavel, agente = _fks_acionamento
    autor = django_user_model.objects.create_user(username="ana.autora", password="x")
    ac = _acionamento_valido(cliente, responsavel, agente, criado_por=autor)
    ac.save()

    viewer = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(viewer)

    url = reverse("controle_acionamentos:acionamento_detail", args=[ac.pk])
    response = client.get(url)

    assertContains(response, "criado por")
    assertContains(response, "ana.autora")


@pytest.mark.django_db
def test_detalhe_omite_linha_quando_criado_por_nulo(
    client, django_user_model, _fks_acionamento
):
    """DD-051/ST1 — guarda de regressão: sem criado_por, a linha de autoria NÃO
    aparece (nada de "criado por" no detalhe). Pode nascer verde no RED."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)  # criado_por fica nulo
    ac.save()

    viewer = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(viewer)

    url = reverse("controle_acionamentos:acionamento_detail", args=[ac.pk])
    response = client.get(url)

    assertNotContains(response, "criado por")


@pytest.mark.django_db
def test_detalhe_exibe_badge_franquia_no_cabecalho(
    client, django_user_model, _fks_acionamento
):
    """DD-051/ST1 — acionamento com franquia vinculada exibe o badge da franquia no
    cabeçalho, na convenção da listagem (.acn-badge-franquia + nome da franquia).
    Guarda a marcação do badge; pode nascer verde no RED."""
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(
        **_dados_franquia(cliente, nome="Franquia Ouro")
    )
    ac = _acionamento_valido(cliente, responsavel, agente, franquia_agente=franquia)
    ac.save()

    viewer = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(viewer)

    url = reverse("controle_acionamentos:acionamento_detail", args=[ac.pk])
    response = client.get(url)

    assertContains(response, "acn-badge-franquia")
    assertContains(response, "Franquia Ouro")


# ---------------------------------------------------------------
# DD-051/ST2 — AC-06.5 revisado: franquia idêntica NÃO é conflito (RED)
#
# Contrato NOVO (ainda não implementado em services.py/views.py):
#   com sobrescrever=False, conflito = item com franquia JÁ VINCULADA e DIFERENTE
#   da selecionada. Franquia idêntica segue no lote normalmente (re-salva e
#   recalcula, resultado igual) — não recusa no service nem pede confirmação na view.
#
# A guarda atual (franquia_agente__isnull=False, em services e na view) trata
# QUALQUER item com franquia como conflito, então os testes de cenário idêntico
# nascem VERMELHOS. O de franquia DIFERENTE (guarda que permanece) pode nascer verde.
# ---------------------------------------------------------------


@pytest.mark.django_db
def test_lote_franquia_identica_sem_flag_nao_e_conflito(_fks_acionamento):
    """DD-051/ST2 (AC-06.5) — service: item já vinculado à franquia X e o lote
    seleciona a MESMA X, sem sobrescrever → não levanta ValidationError, retorna a
    contagem e o valor_agente do item permanece igual (recálculo idêntico)."""
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia X"))
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=franquia,
        km_inicio=0,
        km_final=240,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=5),
    )
    ac.save()
    ac.refresh_from_db()
    valor_antes = ac.valor_agente

    from controle_acionamentos.services import vincular_franquia_em_lote

    resultado = vincular_franquia_em_lote([ac.pk], franquia)  # sem sobrescrever

    assert resultado == 1
    ac.refresh_from_db()
    assert ac.franquia_agente_id == franquia.pk
    assert ac.valor_agente == valor_antes


@pytest.mark.django_db
def test_lote_misto_sem_franquia_e_identica_sem_flag_passa(_fks_acionamento):
    """DD-051/ST2 (AC-06.5) — service: lote com um item SEM franquia + um já com a
    franquia X, aplicando X sem sobrescrever → passa e vincula os DOIS (o livre
    ganha X; o já vinculado permanece em X)."""
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia X"))
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

    livre = _cria()
    ja_vinculado = _cria(franquia_agente=franquia)

    from controle_acionamentos.services import vincular_franquia_em_lote

    resultado = vincular_franquia_em_lote([livre.pk, ja_vinculado.pk], franquia)

    assert resultado == 2
    for ac in (livre, ja_vinculado):
        ac.refresh_from_db()
        assert ac.franquia_agente_id == franquia.pk


@pytest.mark.django_db
def test_lote_franquia_diferente_sem_flag_continua_recusando(_fks_acionamento):
    """DD-051/ST2 (AC-06.5) — guarda do contrato que PERMANECE: item já vinculado à
    franquia Y e o lote aplica X (DIFERENTE) sem sobrescrever → ValidationError. A
    revisão isenta só franquia idêntica; conflito real (troca) segue exigindo
    confirmação. Pode nascer VERDE no RED (a guarda antiga já recusa)."""
    cliente, responsavel, agente = _fks_acionamento
    # Mesmo cliente (RN-06 não entra), nomes distintos (unicidade cliente+nome).
    franquia_y = FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia Y"))
    franquia_x = FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia X"))
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=franquia_y,
        km_inicio=0,
        km_final=240,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=5),
    )
    ac.save()

    from controle_acionamentos.services import vincular_franquia_em_lote

    with pytest.raises(ValidationError):
        vincular_franquia_em_lote([ac.pk], franquia_x)  # sem sobrescrever


@pytest.mark.django_db
def test_view_lote_franquia_identica_pula_confirmacao(
    client, django_user_model, _fks_acionamento
):
    """DD-051/ST2 (AC-06.5) — view: POST do lote com a franquia IDÊNTICA à já
    vinculada, sem sobrescrever → NÃO renderiza a tela de confirmação; redireciona
    (302) com o vínculo mantido no item."""
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente, nome="Franquia X"))
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=franquia,
        km_inicio=0,
        km_final=240,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=5),
    )
    ac.save()

    user = _user_com_perms(
        django_user_model, "view_acionamento", "change_acionamento"
    )
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_vincular_franquia_lote")
    response = client.post(
        url,
        {"acionamentos": [ac.pk], "franquia": franquia.pk},  # sem sobrescrever
    )

    assert response.status_code == 302
    assert (
        "controle_acionamentos/acionamento_vincular_confirmar.html"
        not in [t.name for t in response.templates]
    )
    ac.refresh_from_db()
    assert ac.franquia_agente_id == franquia.pk


# ---------------------------------------------------------------
# Modo Foco — ocultar a navbar do INT nas telas do app
# ---------------------------------------------------------------
@pytest.mark.django_db
def test_home_exibe_botao_modo_foco(client, django_user_model):
    """Modo Foco — a home autenticada renderiza o botão "Foco" no cabeçalho
    (pill ao lado do toggle de tema). Trava o contrato do partial
    _cabecalho.html: se o botão sumir ou for renomeado, este teste quebra.
    O id `acn-btn-foco` é o mesmo que o JS de toggle/persistência e o CSS de
    estado ativo localizam. Não há gate de permissão — é preferência de UI,
    igual ao toggle de tema — então um usuário comum já vê o botão."""
    user = django_user_model.objects.create_user(username="foco", password="x")
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:index"))

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert 'id="acn-btn-foco"' in conteudo


# ---------------------------------------------------------------
# ServicoCliente — catálogo de serviços do cliente (DD-066/ST1)
# ---------------------------------------------------------------
# Os 5 serviços do catálogo, na ORDEM DE DEFINIÇÃO do negócio (não alfabética).
# São os VALORES dos TextChoices `Nome` que o model deve expor na fase GREEN;
# usar os literais aqui deixa o RED falhar por asserção (não por AttributeError
# de um enum ainda inexistente) e dispensa reescrever os testes na GREEN.
_SERVICOS_EM_ORDEM = [
    "MOTO_1_AGENTE",
    "CARRO_1_AGENTE",
    "CARRO_2_AGENTES",
    "CARRO_1_AGENTE_1P",
    "CARRO_2_AGENTES_2P",
]


def _dados_servico(cliente, **overrides):
    """Espelha o _dados_franquia: kwargs válidos para criar um ServicoCliente.
    `nome` default = primeiro serviço do catálogo; sobrescrevível por override.
    """
    dados = dict(
        cliente=cliente,
        nome=_SERVICOS_EM_ORDEM[0],
        valor_acionamento=Decimal("150.00"),
        franquia_km=80,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.50"),
        valor_hora_excedente=Decimal("30.00"),
    )
    dados.update(overrides)
    return dados


@pytest.mark.django_db
def test_servico_persiste_com_dados_validos():
    """1 — criação válida; `ativo` nasce False por default (é o operador que
    ativa o serviço depois, não o cadastro)."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    servico = ServicoCliente.objects.create(**_dados_servico(cliente))

    assert servico.pk is not None
    assert ServicoCliente.objects.count() == 1
    assert servico.ativo is False


@pytest.mark.django_db
def test_servico_mesmo_nome_clientes_diferentes_e_permitido():
    """2 — a unicidade é por (cliente, nome): o MESMO serviço pode existir em
    clientes diferentes. Espelha o caso homólogo da FranquiaAgente."""
    cliente_a = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    cliente_b = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")

    ServicoCliente.objects.create(**_dados_servico(cliente_a))
    servico_b = ServicoCliente(**_dados_servico(cliente_b))
    servico_b.full_clean()  # não deve levantar — unicidade é por (cliente, nome)
    servico_b.save()

    assert ServicoCliente.objects.count() == 2


@pytest.mark.django_db
def test_servico_unicidade_cliente_nome():
    """3 — o MESMO cliente não repete o mesmo serviço: o segundo full_clean com o
    mesmo (cliente, nome) é rejeitado pela UniqueConstraint."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    ServicoCliente.objects.create(**_dados_servico(cliente))

    with pytest.raises(ValidationError):
        ServicoCliente(**_dados_servico(cliente)).full_clean()


@pytest.mark.django_db
def test_servico_deletar_cliente_com_servico_e_protegido():
    """4 — on_delete=PROTECT: um cliente que possui serviço não pode ser
    excluído por baixo do catálogo (ProtectedError)."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    ServicoCliente.objects.create(**_dados_servico(cliente))

    with pytest.raises(ProtectedError):
        cliente.delete()


@pytest.mark.django_db
def test_servico_nome_fora_das_opcoes_e_rejeitado():
    """5 — `nome` só aceita um dos 5 serviços do catálogo (TextChoices): um valor
    fora da lista falha no full_clean."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    with pytest.raises(ValidationError):
        ServicoCliente(**_dados_servico(cliente, nome="PLANO_INEXISTENTE")).full_clean()


@pytest.mark.django_db
def test_servico_valores_negativos_sao_rejeitados():
    """6 — valores não-negativos (MinValueValidator): valor_acionamento e
    franquia_horas negativos falham no full_clean."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")

    with pytest.raises(ValidationError):
        ServicoCliente(
            **_dados_servico(cliente, valor_acionamento=Decimal("-1.00"))
        ).full_clean()

    with pytest.raises(ValidationError):
        ServicoCliente(
            **_dados_servico(cliente, franquia_horas=Decimal("-0.50"))
        ).full_clean()


@pytest.mark.django_db
def test_selector_devolve_apenas_ativos_na_ordem_de_definicao():
    """7 — o selector retorna só os serviços ATIVOS do cliente, na ORDEM DE
    DEFINIÇÃO dos choices (não alfabética, não por criação). Crio em ordem
    inversa e com um inativo no meio para provar as duas regras de uma vez."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")

    # Ativos criados FORA de ordem (inverso da definição) → o selector reordena.
    for nome in reversed(_SERVICOS_EM_ORDEM):
        ServicoCliente.objects.create(**_dados_servico(cliente, nome=nome, ativo=True))
    # Um serviço INATIVO não deve aparecer — mas como todos os nomes já foram
    # usados, desativo um dos criados para testar o filtro sem violar a unicidade.
    inativado = ServicoCliente.objects.get(cliente=cliente, nome=_SERVICOS_EM_ORDEM[2])
    inativado.ativo = False
    inativado.save()

    resultado = list(listar_servicos_ativos_por_cliente(cliente))
    nomes = [s.nome for s in resultado]

    esperado = [n for n in _SERVICOS_EM_ORDEM if n != _SERVICOS_EM_ORDEM[2]]
    assert nomes == esperado


@pytest.mark.django_db
def test_selector_nao_devolve_servico_de_outro_cliente():
    """8 — escopo por cliente: o serviço ativo de OUTRO cliente não vaza no
    selector do cliente-alvo (e o do alvo aparece)."""
    alvo = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    outro = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")

    servico_alvo = ServicoCliente.objects.create(**_dados_servico(alvo, ativo=True))
    ServicoCliente.objects.create(**_dados_servico(outro, ativo=True))

    resultado = list(listar_servicos_ativos_por_cliente(alvo))

    assert resultado == [servico_alvo]


# ---------------------------------------------------------------
# DD-066 ST2 — catálogo de serviços dentro do formulário do cliente (RED)
# ---------------------------------------------------------------
# As views cliente_create/cliente_update ainda NÃO montam/processam o formset e
# o clean cruzado da linha ainda NÃO existe — por isso estes 10 testes ficam
# vermelhos (é o RED). Os símbolos referenciados (ServicoClienteLinhaForm) já
# existem como esqueleto, então a coleta não quebra.

# Valores válidos de UMA linha do catálogo (strings, como chegam no POST).
_VALORES_LINHA = {
    "valor_acionamento": "150.00",
    "franquia_km": "80",
    "franquia_horas": "4.00",
    "valor_km_excedente": "2.50",
    "valor_hora_excedente": "30.00",
}


def _payload_formset(linhas):
    """Monta o POST do formset do catálogo (prefixo "servicos", 5 linhas fixas).

    `linhas`: lista de 5 dicts, na ordem do catálogo, com os campos da linha
    (sem "nome" — preenchido aqui a partir de _SERVICOS_EM_ORDEM). Dict vazio =
    linha em branco. Para marcar `ativo`, incluir {"ativo": "on"}.
    """
    data = {
        "servicos-TOTAL_FORMS": "5",
        "servicos-INITIAL_FORMS": "5",
        "servicos-MIN_NUM_FORMS": "0",
        "servicos-MAX_NUM_FORMS": "5",
    }
    for i, (nome, campos) in enumerate(zip(_SERVICOS_EM_ORDEM, linhas)):
        data[f"servicos-{i}-nome"] = nome
        for chave, valor in campos.items():
            data[f"servicos-{i}-{chave}"] = valor
    return data


def _cria_servico(cliente, nome, ativo=True, valor_acionamento=Decimal("150.00")):
    """Cria um ServicoCliente completo para os testes de update."""
    return ServicoCliente.objects.create(
        cliente=cliente,
        nome=nome,
        ativo=ativo,
        valor_acionamento=valor_acionamento,
        franquia_km=80,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.50"),
        valor_hora_excedente=Decimal("30.00"),
    )


class TestCatalogoServicosNoCliente:
    """DD-066/ST2 (RED) — tabela fixa de 5 serviços no formulário do cliente.

    Permissões continuam as do cliente (add_cliente/change_cliente); o catálogo
    viaja junto no mesmo POST, sem permissão própria.
    """

    def test_linha_ativa_sem_valores_e_invalida(self):
        """1 — ativo marcado obriga os 5 valores: linha ativa e vazia é inválida."""
        from controle_acionamentos.forms import ServicoClienteLinhaForm

        form = ServicoClienteLinhaForm(
            data={"nome": _SERVICOS_EM_ORDEM[0], "ativo": "on"}
        )
        assert form.is_valid() is False

    def test_linha_parcial_e_invalida(self):
        """2 — preencher só um valor é parcial: exige os 5 (ou nenhum)."""
        from controle_acionamentos.forms import ServicoClienteLinhaForm

        form = ServicoClienteLinhaForm(
            data={"nome": _SERVICOS_EM_ORDEM[1], "valor_acionamento": "150.00"}
        )
        assert form.is_valid() is False

    @pytest.mark.django_db
    def test_get_create_exibe_catalogo_com_5_linhas(self, client, django_user_model):
        """3 — o create exibe o formset: management form + 5 hidden `nome`, na
        ordem de definição dos choices."""
        user = _user_com_perms(django_user_model, "add_cliente")
        client.force_login(user)

        response = client.get(reverse("controle_acionamentos:cliente_create"))

        assert response.status_code == 200
        conteudo = response.content.decode(response.charset)
        assert 'name="servicos-TOTAL_FORMS"' in conteudo
        for i, nome in enumerate(_SERVICOS_EM_ORDEM):
            assert f'name="servicos-{i}-nome"' in conteudo
            assert f'value="{nome}"' in conteudo

    @pytest.mark.django_db
    def test_post_create_valido_cria_cliente_e_servicos(self, client, django_user_model):
        """4 — POST válido cria o cliente e os serviços das linhas preenchidas:
        linha 0 ativa; linha 1 só com valores (nasce ativo=False); demais em
        branco não criam registro."""
        user = _user_com_perms(django_user_model, "add_cliente")
        client.force_login(user)

        linhas = [
            {"ativo": "on", **_VALORES_LINHA},
            {**_VALORES_LINHA},
            {}, {}, {},
        ]
        data = {"nome_empresa": "Cliente Catalogo", "cnpj": "11.222.333/0001-81"}
        data.update(_payload_formset(linhas))

        response = client.post(reverse("controle_acionamentos:cliente_create"), data)

        assert response.status_code == 302
        cliente = Cliente.objects.get(nome_empresa="Cliente Catalogo")
        servicos = ServicoCliente.objects.filter(cliente=cliente)
        assert servicos.count() == 2
        assert servicos.get(nome=_SERVICOS_EM_ORDEM[0]).ativo is True
        assert servicos.get(nome=_SERVICOS_EM_ORDEM[1]).ativo is False

    @pytest.mark.django_db
    def test_post_create_linha_ativa_sem_valores_nao_cria_nada(
        self, client, django_user_model
    ):
        """5 — atomicidade: uma linha ativa e vazia invalida o POST inteiro; nem
        o cliente nem serviço nenhum são criados, e a resposta é 200 (reexibe)."""
        user = _user_com_perms(django_user_model, "add_cliente")
        client.force_login(user)

        linhas = [{"ativo": "on"}, {}, {}, {}, {}]
        data = {"nome_empresa": "Nao Deve Existir", "cnpj": "11.222.333/0001-81"}
        data.update(_payload_formset(linhas))

        response = client.post(reverse("controle_acionamentos:cliente_create"), data)

        assert response.status_code == 200
        assert Cliente.objects.count() == 0
        assert ServicoCliente.objects.count() == 0

    @pytest.mark.django_db
    def test_get_update_carrega_linhas_existentes(self, client, django_user_model):
        """6 — o update carrega os valores do serviço existente (linha
        preenchida) e deixa as demais em branco."""
        cliente = Cliente.objects.create(
            nome_empresa="Com Servico", cnpj="11222333000181"
        )
        _cria_servico(cliente, _SERVICOS_EM_ORDEM[2], valor_acionamento=Decimal("150.00"))
        user = _user_com_perms(django_user_model, "change_cliente")
        client.force_login(user)

        response = client.get(
            reverse("controle_acionamentos:cliente_update", args=[cliente.pk])
        )

        assert response.status_code == 200
        conteudo = response.content.decode(response.charset)
        assert 'value="150.00"' in conteudo

    @pytest.mark.django_db
    def test_post_update_edita_servico_existente(self, client, django_user_model):
        """7 — POST edita os valores de um serviço já existente."""
        cliente = Cliente.objects.create(
            nome_empresa="Edita Servico", cnpj="11222333000181"
        )
        servico = _cria_servico(cliente, _SERVICOS_EM_ORDEM[2])
        user = _user_com_perms(django_user_model, "change_cliente")
        client.force_login(user)

        linhas = [{}, {}, {"ativo": "on", **_VALORES_LINHA, "valor_acionamento": "999.00"}, {}, {}]
        data = {"nome_empresa": "Edita Servico", "cnpj": "11.222.333/0001-81"}
        data.update(_payload_formset(linhas))

        response = client.post(
            reverse("controle_acionamentos:cliente_update", args=[cliente.pk]), data
        )

        assert response.status_code == 302
        servico.refresh_from_db()
        assert servico.valor_acionamento == Decimal("999.00")

    @pytest.mark.django_db
    def test_post_update_desmarca_ativo_mantem_registro(self, client, django_user_model):
        """8 — desmarcar `ativo` de um serviço existente NÃO deleta: o registro
        permanece com os valores, apenas ativo=False."""
        cliente = Cliente.objects.create(
            nome_empresa="Desativa Servico", cnpj="11222333000181"
        )
        servico = _cria_servico(cliente, _SERVICOS_EM_ORDEM[2], ativo=True)
        user = _user_com_perms(django_user_model, "change_cliente")
        client.force_login(user)

        # Linha 2 com valores, mas SEM "ativo" (checkbox desmarcado não posta).
        linhas = [{}, {}, {**_VALORES_LINHA}, {}, {}]
        data = {"nome_empresa": "Desativa Servico", "cnpj": "11.222.333/0001-81"}
        data.update(_payload_formset(linhas))

        response = client.post(
            reverse("controle_acionamentos:cliente_update", args=[cliente.pk]), data
        )

        assert response.status_code == 302
        servico.refresh_from_db()
        assert servico.ativo is False
        assert servico.valor_acionamento == Decimal("150.00")

    @pytest.mark.django_db
    def test_post_update_preenche_linha_sem_registro_cria(self, client, django_user_model):
        """9 — preencher uma linha que ainda não tinha registro cria o serviço."""
        cliente = Cliente.objects.create(
            nome_empresa="Cria No Update", cnpj="11222333000181"
        )
        user = _user_com_perms(django_user_model, "change_cliente")
        client.force_login(user)

        linhas = [{"ativo": "on", **_VALORES_LINHA}, {}, {}, {}, {}]
        data = {"nome_empresa": "Cria No Update", "cnpj": "11.222.333/0001-81"}
        data.update(_payload_formset(linhas))

        response = client.post(
            reverse("controle_acionamentos:cliente_update", args=[cliente.pk]), data
        )

        assert response.status_code == 302
        assert ServicoCliente.objects.filter(
            cliente=cliente, nome=_SERVICOS_EM_ORDEM[0]
        ).exists()

    @pytest.mark.django_db
    def test_post_update_linha_existente_limpa_e_invalida(self, client, django_user_model):
        """10 — esvaziar (deixar em branco) uma linha que TEM registro é
        inválido: o registro não some e o POST volta 200 pedindo completar os
        valores (não há como "apagar" pela tela — só desativar)."""
        cliente = Cliente.objects.create(
            nome_empresa="Nao Esvazia", cnpj="11222333000181"
        )
        servico = _cria_servico(cliente, _SERVICOS_EM_ORDEM[2])
        user = _user_com_perms(django_user_model, "change_cliente")
        client.force_login(user)

        # Linha 2 totalmente vazia (só o hidden nome), mas existe registro para ela.
        linhas = [{}, {}, {}, {}, {}]
        data = {"nome_empresa": "Nao Esvazia", "cnpj": "11.222.333/0001-81"}
        data.update(_payload_formset(linhas))

        response = client.post(
            reverse("controle_acionamentos:cliente_update", args=[cliente.pk]), data
        )

        assert response.status_code == 200
        assert ServicoCliente.objects.filter(pk=servico.pk).exists()
        servico.refresh_from_db()
        assert servico.valor_acionamento == Decimal("150.00")


# ---------------------------------------------------------------
# DD-067 ST1 — Acionamento: escolha do serviço do cliente (RED)
# ---------------------------------------------------------------
# O snapshot (cópia dos 5 valores) e a regra de cliente no clean ainda NÃO
# existem — por isso os testes 1, 2 e 5 ficam vermelhos. Os testes 3, 4 e 6
# nascem verdes por estrutura (FK PROTECT + null=True). O campo servico_cliente
# e aplicar_servico_ao_acionamento já existem como esqueleto, então a coleta não
# quebra.


def _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[0]):
    """ServicoCliente com valores DISTINTOS dos do _acionamento_valido (que usa
    150/80/4/2.5/30), para provar que a cópia/snapshot realmente ocorreu."""
    return ServicoCliente.objects.create(
        cliente=cliente,
        nome=nome,
        ativo=True,
        valor_acionamento=Decimal("500.00"),
        franquia_km=200,
        franquia_horas=Decimal("8.00"),
        valor_km_excedente=Decimal("5.00"),
        valor_hora_excedente=Decimal("60.00"),
    )


@pytest.mark.django_db
def test_aplicar_servico_copia_os_5_valores_para_o_inline(_fks_acionamento):
    """1 — aplicar_servico_ao_acionamento faz o snapshot: copia os 5 valores do
    serviço para os campos inline do acionamento (a FK é só a referência)."""
    cliente, responsavel, agente = _fks_acionamento
    servico = _servico_distinto(cliente)
    ac = _acionamento_valido(cliente, responsavel, agente)

    aplicar_servico_ao_acionamento(ac, servico)

    assert ac.servico_cliente == servico
    assert ac.valor_acionamento == Decimal("500.00")
    assert ac.franquia_km == 200
    assert ac.franquia_horas == Decimal("8.00")
    assert ac.valor_km_excedente == Decimal("5.00")
    assert ac.valor_hora_excedente == Decimal("60.00")


@pytest.mark.django_db
def test_acionamento_servico_de_outro_cliente_e_rejeitado(_fks_acionamento):
    """2 — análogo ao RN-06 da franquia: o serviço vinculado tem de pertencer ao
    MESMO cliente do acionamento; serviço de outro cliente falha no full_clean."""
    cliente, responsavel, agente = _fks_acionamento
    outro = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")
    servico_outro = _servico_distinto(outro)
    ac = _acionamento_valido(
        cliente, responsavel, agente, servico_cliente=servico_outro
    )

    with pytest.raises(ValidationError):
        ac.full_clean()


@pytest.mark.django_db
def test_acionamento_servico_do_mesmo_cliente_e_valido(_fks_acionamento):
    """3 — serviço do mesmo cliente passa no full_clean e salva."""
    cliente, responsavel, agente = _fks_acionamento
    servico = _servico_distinto(cliente)
    ac = _acionamento_valido(cliente, responsavel, agente, servico_cliente=servico)

    ac.full_clean()  # não deve levantar
    ac.save()

    assert ac.pk is not None
    assert ac.servico_cliente == servico


@pytest.mark.django_db
def test_deletar_servico_referenciado_por_acionamento_e_protegido(_fks_acionamento):
    """4 — on_delete=PROTECT: um serviço referenciado por acionamento não pode
    ser excluído (ProtectedError)."""
    cliente, responsavel, agente = _fks_acionamento
    servico = _servico_distinto(cliente)
    ac = _acionamento_valido(cliente, responsavel, agente, servico_cliente=servico)
    ac.save()

    with pytest.raises(ProtectedError):
        servico.delete()


@pytest.mark.django_db
def test_congelamento_forte_snapshot_nao_reflete_edicao_do_catalogo(_fks_acionamento):
    """5 — CONGELAMENTO FORTE: com o serviço aplicado e o acionamento salvo,
    EDITAR o serviço no catálogo e re-salvar o acionamento (simulando update de
    pedágio) NÃO puxa os valores novos — os campos inline seguem o snapshot da
    época. DD-068/ST3: sem franquia vinculada o valor_agente é PENDENTE (None)
    antes e depois do re-save — o snapshot nunca alimenta a conta do agente."""
    cliente, responsavel, agente = _fks_acionamento
    servico = _servico_distinto(cliente)
    ac = _acionamento_valido(cliente, responsavel, agente)
    aplicar_servico_ao_acionamento(ac, servico)
    ac.save()  # congela o snapshot no inline; sem franquia, valor_agente pendente
    assert ac.valor_agente is None

    # O catálogo muda DEPOIS que o acionamento já existe.
    servico.valor_acionamento = Decimal("999.00")
    servico.franquia_km = 10
    servico.franquia_horas = Decimal("1.00")
    servico.valor_km_excedente = Decimal("50.00")
    servico.valor_hora_excedente = Decimal("500.00")
    servico.save()

    # Re-save do acionamento (ex.: operador ajusta o pedágio).
    ac.pedagio = Decimal("25.00")
    ac.save()
    ac.refresh_from_db()

    # Os campos inline seguem o snapshot (500/200/8/5/60), não o catálogo novo.
    assert ac.valor_acionamento == Decimal("500.00")
    assert ac.franquia_km == 200
    assert ac.franquia_horas == Decimal("8.00")
    assert ac.valor_km_excedente == Decimal("5.00")
    assert ac.valor_hora_excedente == Decimal("60.00")
    # Sem franquia o valor do agente segue PENDENTE — nada do catálogo, nada de conta.
    assert ac.valor_agente is None


# ---------------------------------------------------------------
# DD-067 ST2 — tela de criação escolhendo o serviço do cliente (RED)
# ---------------------------------------------------------------
# Nesta fase existe só o esqueleto: a rota + a view STUB do endpoint (devolve
# lista vazia). O AcionamentoForm ainda expõe os 5 campos inline e não tem o
# campo servico_cliente; a view de create ainda não aplica o serviço; o template
# ainda não tem o select nem a prévia. Por isso, dos 8 testes abaixo, ficam
# VERMELHOS 1, 3, 4, 5, 6, 7 e 8; o teste 2 (cliente sem serviços ativos) nasce
# VERDE já com o stub (lista vazia == resposta do stub).
#
# Truque dos POST (5–8): o payload leva OS 5 INLINE (valores do molde 150/80/…)
# JUNTO do servico_cliente. Na RED o form valida pelos inline e ignora o campo
# novo → cria (302), contradizendo o esperado → vermelho. Na GREEN o form perde
# os inline e passa a exigir servico_cliente → o comportamento correto aparece.


@pytest.mark.django_db
def test_endpoint_servicos_por_cliente_devolve_ativos_na_ordem(client, django_user_model):
    """1 — o endpoint devolve SÓ os serviços ATIVOS do cliente, na ORDEM do
    catálogo (não a de criação), com os Decimais serializados como STRING e o
    `nome` já como label humano do choice. Crio fora de ordem + 1 inativo para
    provar filtro e ordenação de uma vez (espelha o teste do selector)."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    # Ativos criados na ordem INVERSA da definição → o endpoint reordena.
    _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[1])
    servico_primeiro = _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[0])
    # Inativo NÃO deve aparecer.
    _cria_servico(cliente, _SERVICOS_EM_ORDEM[2], ativo=False)

    # Permissão do endpoint evoluiu na GREEN: view_acionamento (leitura pura do
    # catálogo, serve criação E edição), não add_acionamento.
    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:servicos_por_cliente", args=[cliente.pk])
    response = client.get(url)

    assert response.status_code == 200
    servicos = response.json()["servicos"]
    assert [s["nome"] for s in servicos] == [
        ServicoCliente.Nome(_SERVICOS_EM_ORDEM[0]).label,
        ServicoCliente.Nome(_SERVICOS_EM_ORDEM[1]).label,
    ]
    primeiro = servicos[0]
    assert primeiro["id"] == servico_primeiro.pk
    assert primeiro["valor_acionamento"] == "500.00"
    assert primeiro["franquia_km"] == 200
    assert primeiro["franquia_horas"] == "8.00"
    assert primeiro["valor_km_excedente"] == "5.00"
    assert primeiro["valor_hora_excedente"] == "60.00"


@pytest.mark.django_db
def test_endpoint_servicos_por_cliente_sem_ativos_devolve_vazio(client, django_user_model):
    """2 — cliente sem NENHUM serviço ativo (só um inativo) devolve lista vazia.
    Nasce VERDE já na RED: o stub responde exatamente {"servicos": []}."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=False)

    # Permissão do endpoint evoluiu na GREEN: view_acionamento (leitura pura).
    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:servicos_por_cliente", args=[cliente.pk])
    response = client.get(url)

    assert response.status_code == 200
    assert response.json() == {"servicos": []}


@pytest.mark.django_db
def test_acionamento_form_troca_inline_por_servico_cliente():
    """3 — o AcionamentoForm não expõe mais os 5 campos inline (eles saíram do
    form; seguem no model como snapshot) e passa a exigir servico_cliente."""
    from controle_acionamentos.forms import AcionamentoForm

    form = AcionamentoForm()
    for campo in (
        "valor_acionamento",
        "franquia_km",
        "franquia_horas",
        "valor_km_excedente",
        "valor_hora_excedente",
    ):
        assert campo not in form.fields
    assert "servico_cliente" in form.fields
    assert form.fields["servico_cliente"].required is True


@pytest.mark.django_db
def test_get_create_renderiza_select_de_servico_e_previa(client, django_user_model):
    """4 — o GET da criação renderiza o select do serviço (name="servico_cliente")
    e o container read-only da prévia (id="acn-servico-previa")."""
    user = _user_com_perms(django_user_model, "add_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:acionamento_create")
    response = client.get(url)

    assert response.status_code == 200
    assertContains(response, 'name="servico_cliente"')
    assertContains(response, 'id="acn-servico-previa"')


@pytest.mark.django_db
def test_post_create_valido_aplica_snapshot_do_servico(
    client, django_user_model, _fks_acionamento
):
    """5 — POST válido (serviço ATIVO do cliente): 302, acionamento criado com o
    SNAPSHOT dos 5 valores do serviço (500/200/8/5/60), FK servico_cliente setada
    e criado_por carimbado. DD-068/ST3: sem franquia vinculada o valor_agente
    nasce PENDENTE (None) — o snapshot não alimenta a conta do agente.

    O payload leva os inline do molde (150/…), DISTINTOS dos do serviço: se o
    snapshot não ocorrer, os valores denunciam."""
    cliente, responsavel, agente = _fks_acionamento
    servico = _servico_distinto(cliente)  # ativo, mesmo cliente, 500/200/8/5/60
    molde = _acionamento_valido(cliente, responsavel, agente)
    payload = _post_payload_acionamento(molde, servico_cliente=servico.pk)

    user = _user_com_perms(django_user_model, "add_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:acionamento_create")
    response = client.post(url, payload)

    assert response.status_code == 302
    ac = Acionamento.objects.get()
    assert ac.servico_cliente == servico
    assert ac.valor_acionamento == Decimal("500.00")
    assert ac.franquia_km == 200
    assert ac.franquia_horas == Decimal("8.00")
    assert ac.valor_km_excedente == Decimal("5.00")
    assert ac.valor_hora_excedente == Decimal("60.00")
    # DD-068/ST3 — sem franquia vinculada, o valor do agente fica pendente.
    assert ac.valor_agente is None
    assert ac.criado_por == user


@pytest.mark.django_db
def test_post_create_servico_de_outro_cliente_nao_cria(
    client, django_user_model, _fks_acionamento
):
    """6 — serviço de OUTRO cliente é rejeitado no form: 200 (reexibe) e nada
    criado."""
    cliente, responsavel, agente = _fks_acionamento
    outro = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")
    servico_outro = _servico_distinto(outro)
    molde = _acionamento_valido(cliente, responsavel, agente)
    payload = _post_payload_acionamento(molde, servico_cliente=servico_outro.pk)

    user = _user_com_perms(django_user_model, "add_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:acionamento_create")
    response = client.post(url, payload)

    assert response.status_code == 200
    assert Acionamento.objects.count() == 0


@pytest.mark.django_db
def test_post_create_servico_inativo_nao_cria(
    client, django_user_model, _fks_acionamento
):
    """7 — serviço INATIVO do próprio cliente é rejeitado no form: 200 e nada
    criado (só serviços ativos podem ser escolhidos na criação)."""
    cliente, responsavel, agente = _fks_acionamento
    servico_inativo = _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=False)
    molde = _acionamento_valido(cliente, responsavel, agente)
    payload = _post_payload_acionamento(molde, servico_cliente=servico_inativo.pk)

    user = _user_com_perms(django_user_model, "add_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:acionamento_create")
    response = client.post(url, payload)

    assert response.status_code == 200
    assert Acionamento.objects.count() == 0


@pytest.mark.django_db
def test_post_create_sem_servico_nao_cria(
    client, django_user_model, _fks_acionamento
):
    """8 — serviço é OBRIGATÓRIO na criação (regra de 17/07): POST sem
    servico_cliente é rejeitado no form: 200 e nada criado."""
    cliente, responsavel, agente = _fks_acionamento
    molde = _acionamento_valido(cliente, responsavel, agente)
    payload = _post_payload_acionamento(molde)  # sem servico_cliente

    user = _user_com_perms(django_user_model, "add_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:acionamento_create")
    response = client.post(url, payload)

    assert response.status_code == 200
    assert Acionamento.objects.count() == 0


@pytest.mark.django_db
def test_acionamento_legado_sem_servico_e_valido_e_pendente(_fks_acionamento):
    """6 — acionamento legado SEM serviço continua VÁLIDO (full_clean passa);
    DD-068/ST3: sem franquia vinculada o valor do agente fica PENDENTE (None) —
    o inline não calcula mais."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente)

    ac.full_clean()  # não deve levantar
    ac.save()

    assert ac.servico_cliente is None
    assert ac.valor_agente is None


@pytest.mark.django_db
def test_aplicar_servico_deriva_nome_servico_do_label(_fks_acionamento):
    """DD-067/ST2 — aplicar_servico_ao_acionamento também DERIVA o nome_servico do
    LABEL do serviço (o catálogo passa a ser a fonte única do nome exibido, não
    mais um texto digitado). Parte do 'derivar no backend' decidido na ST2."""
    cliente, responsavel, agente = _fks_acionamento
    servico = _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[0])
    ac = _acionamento_valido(cliente, responsavel, agente, nome_servico="Texto antigo")

    aplicar_servico_ao_acionamento(ac, servico)

    assert ac.nome_servico == ServicoCliente.Nome(_SERVICOS_EM_ORDEM[0]).label


# ---------------------------------------------------------------
# DD-067 ST3 — regras de edição do acionamento com serviço vinculado (RED)
# ---------------------------------------------------------------
# Fase RED: NADA a implementar. As regras A (re-snapshot ao trocar serviço) e B
# (coerência ao trocar cliente) já existem por construção da ST2; a fresta C
# (serviço desativado APÓS o vínculo não pode travar a edição) é o que a GREEN
# corrige no clean do form. Estes 6 testes (o cenário 2 vira 2a/2b para dar
# granularidade) provam exatamente ISSO: só a fresta deve estar aberta.
#
# Helper local: acionamento SALVO já com um serviço aplicado (o "antes" da edição).
def _acionamento_com_servico(cliente, responsavel, agente, servico, base):
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        data_hora_solicitado=base,
        data_hora_inicio=base + timedelta(minutes=30),
        data_hora_final=base + timedelta(hours=3),
    )
    aplicar_servico_ao_acionamento(ac, servico)
    ac.save()
    return ac


@pytest.mark.django_db
def test_update_troca_servico_faz_re_snapshot(
    client, django_user_model, _fks_acionamento
):
    """1 (regra A) — trocar por OUTRO serviço ativo do MESMO cliente recopia os 5
    valores + nome: FK nova, inline = valores do serviço novo. DD-068/ST3: sem
    franquia vinculada o valor_agente segue PENDENTE (None) — o re-snapshot não
    alimenta a conta do agente."""
    cliente, responsavel, agente = _fks_acionamento
    servico_a = _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=True)  # 150/80/4/2.5/30
    servico_b = _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[1])     # 500/200/8/5/60
    base = timezone.now().replace(second=0, microsecond=0)
    ac = _acionamento_com_servico(cliente, responsavel, agente, servico_a, base)

    user = _user_com_perms(django_user_model, "view_acionamento", "change_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    payload = _post_payload_acionamento(ac, servico_cliente=servico_b.pk)
    response = client.post(url, payload)

    assert response.status_code == 302
    ac.refresh_from_db()
    assert ac.servico_cliente_id == servico_b.pk
    assert ac.valor_acionamento == Decimal("500.00")
    assert ac.franquia_km == 200
    assert ac.franquia_horas == Decimal("8.00")
    assert ac.valor_km_excedente == Decimal("5.00")
    assert ac.valor_hora_excedente == Decimal("60.00")
    assert ac.nome_servico == ServicoCliente.Nome(_SERVICOS_EM_ORDEM[1]).label
    # DD-068/ST3 — sem franquia vinculada, o valor do agente permanece pendente.
    assert ac.valor_agente is None


@pytest.mark.django_db
def test_update_troca_cliente_e_servico_coerente(
    client, django_user_model, _fks_acionamento
):
    """2a (regra B) — trocar cliente E serviço juntos, com o serviço pertencendo ao
    cliente NOVO: 302 e ambos persistidos coerentes."""
    cliente, responsavel, agente = _fks_acionamento
    servico_a = _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=True)
    cliente_novo = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")
    servico_novo = _cria_servico(cliente_novo, _SERVICOS_EM_ORDEM[0], ativo=True)
    base = timezone.now().replace(second=0, microsecond=0)
    ac = _acionamento_com_servico(cliente, responsavel, agente, servico_a, base)

    user = _user_com_perms(django_user_model, "view_acionamento", "change_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    payload = _post_payload_acionamento(
        ac, cliente=cliente_novo.pk, servico_cliente=servico_novo.pk
    )
    response = client.post(url, payload)

    assert response.status_code == 302
    ac.refresh_from_db()
    assert ac.cliente_id == cliente_novo.pk
    assert ac.servico_cliente_id == servico_novo.pk


@pytest.mark.django_db
def test_update_troca_cliente_com_servico_do_cliente_antigo_rejeitado(
    client, django_user_model, _fks_acionamento
):
    """2b (regra B) — trocar o cliente mas manter um serviço do cliente ANTIGO:
    200 e erro no campo servico_cliente (o serviço tem de ser do cliente novo)."""
    cliente, responsavel, agente = _fks_acionamento
    servico_a = _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=True)
    cliente_novo = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")
    base = timezone.now().replace(second=0, microsecond=0)
    ac = _acionamento_com_servico(cliente, responsavel, agente, servico_a, base)

    user = _user_com_perms(django_user_model, "view_acionamento", "change_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    payload = _post_payload_acionamento(
        ac, cliente=cliente_novo.pk, servico_cliente=servico_a.pk
    )
    response = client.post(url, payload)

    assert response.status_code == 200
    assert "servico_cliente" in response.context["form"].errors


@pytest.mark.django_db
def test_update_mantendo_servico_desativado_apos_vinculo(
    client, django_user_model, _fks_acionamento
):
    """3 (fresta C) — o serviço vinculado foi DESATIVADO depois; manter o MESMO
    serviço na edição deve salvar normalmente (302). No RED nasce VERMELHO: o
    clean ainda rejeita serviço inativo mesmo sendo o já vinculado."""
    cliente, responsavel, agente = _fks_acionamento
    servico = _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=True)
    base = timezone.now().replace(second=0, microsecond=0)
    ac = _acionamento_com_servico(cliente, responsavel, agente, servico, base)

    # Desativa o serviço DEPOIS de já estar vinculado ao acionamento.
    servico.ativo = False
    servico.save()

    user = _user_com_perms(django_user_model, "view_acionamento", "change_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    payload = _post_payload_acionamento(ac, servico_cliente=servico.pk, pedagio="25.00")
    response = client.post(url, payload)

    assert response.status_code == 302
    ac.refresh_from_db()
    assert ac.pedagio == Decimal("25.00")
    assert ac.servico_cliente_id == servico.pk


@pytest.mark.django_db
def test_update_troca_para_servico_desativado_diferente_rejeitado(
    client, django_user_model, _fks_acionamento
):
    """4 (fresta C, limite) — trocar para um serviço DIFERENTE que está desativado
    continua barrado: 200 e a mensagem de serviço desativado."""
    cliente, responsavel, agente = _fks_acionamento
    servico_a = _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=True)
    servico_inativo = _cria_servico(cliente, _SERVICOS_EM_ORDEM[1], ativo=False)
    base = timezone.now().replace(second=0, microsecond=0)
    ac = _acionamento_com_servico(cliente, responsavel, agente, servico_a, base)

    user = _user_com_perms(django_user_model, "view_acionamento", "change_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    payload = _post_payload_acionamento(ac, servico_cliente=servico_inativo.pk)
    response = client.post(url, payload)

    assert response.status_code == 200
    assert "Este serviço está desativado para o cliente." in str(
        response.context["form"].errors
    )


@pytest.mark.django_db
def test_update_troca_servico_aparece_na_trilha(
    client, django_user_model, _fks_acionamento
):
    """5 (regra D) — trocar o serviço na edição gera trilha refletindo nome_servico
    e os valores inline novos do re-snapshot. DD-068/ST3: sem franquia vinculada o
    valor_agente não muda (None → None) e por isso NÃO entra na trilha."""
    from controle_acionamentos.models import AcionamentoHistorico

    cliente, responsavel, agente = _fks_acionamento
    servico_a = _cria_servico(cliente, _SERVICOS_EM_ORDEM[0], ativo=True)  # 150/80/4/2.5/30
    servico_b = _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[1])     # 500/200/8/5/60
    base = timezone.now().replace(second=0, microsecond=0)
    ac = _acionamento_com_servico(cliente, responsavel, agente, servico_a, base)

    user = _user_com_perms(django_user_model, "change_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:acionamento_update", args=[ac.pk])
    payload = _post_payload_acionamento(ac, servico_cliente=servico_b.pk)
    response = client.post(url, payload)

    assert response.status_code == 302
    campos = {r.campo for r in AcionamentoHistorico.objects.all()}
    assert {"nome_servico", "valor_acionamento"} <= campos
    # DD-068/ST3 — sem franquia, valor_agente é None → None: não gera registro.
    assert "valor_agente" not in campos
    reg_valor = AcionamentoHistorico.objects.get(campo="valor_acionamento")
    assert reg_valor.valor_novo == "500.00"


# ---------------------------------------------------------------
# DD-067 ST4 — endpoint inclui o serviço vinculado-inativo na edição (RED)
# ---------------------------------------------------------------
# Correção do bug do checklist (Caminho A): o endpoint servicos-por-cliente ganha
# o parâmetro OPCIONAL ?incluir=<servico_id>, que anexa o serviço já vinculado
# mesmo desativado. No RED os 5 nascem VERMELHOS: nem a chave "inativo" nem o
# parâmetro "incluir" existem hoje. Estilo de assert espelha os testes do endpoint.


@pytest.mark.django_db
def test_endpoint_sem_incluir_todos_ativos_com_inativo_false(client, django_user_model):
    """1 — sem o parâmetro "incluir", o contrato atual segue intacto (só ativos, na
    ordem do catálogo) E cada item passa a trazer "inativo": false."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[0])
    _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[1])

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:servicos_por_cliente", args=[cliente.pk])
    response = client.get(url)

    assert response.status_code == 200
    servicos = response.json()["servicos"]
    assert [s["nome"] for s in servicos] == [
        ServicoCliente.Nome(_SERVICOS_EM_ORDEM[0]).label,
        ServicoCliente.Nome(_SERVICOS_EM_ORDEM[1]).label,
    ]
    assert all(s["inativo"] is False for s in servicos)


@pytest.mark.django_db
def test_endpoint_incluir_servico_desativado_do_cliente(client, django_user_model):
    """2 — com "incluir" de um serviço DESATIVADO do cliente: ele entra no JSON com
    "inativo": true, ao lado dos ativos (que seguem "inativo": false)."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    ativo = _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[0])
    inativo = _cria_servico(cliente, _SERVICOS_EM_ORDEM[1], ativo=False)

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:servicos_por_cliente", args=[cliente.pk])
    response = client.get(f"{url}?incluir={inativo.pk}")

    assert response.status_code == 200
    por_id = {s["id"]: s for s in response.json()["servicos"]}
    assert inativo.pk in por_id
    assert por_id[inativo.pk]["inativo"] is True
    assert por_id[ativo.pk]["inativo"] is False


@pytest.mark.django_db
def test_endpoint_incluir_servico_ativo_nao_duplica(client, django_user_model):
    """3 — com "incluir" de um serviço que já está ATIVO (logo já na lista), ele
    aparece UMA vez só, com "inativo": false."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    ativo = _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[0])

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:servicos_por_cliente", args=[cliente.pk])
    response = client.get(f"{url}?incluir={ativo.pk}")

    assert response.status_code == 200
    servicos = response.json()["servicos"]
    ids = [s["id"] for s in servicos]
    assert ids.count(ativo.pk) == 1
    por_id = {s["id"]: s for s in servicos}
    assert por_id[ativo.pk]["inativo"] is False


@pytest.mark.django_db
def test_endpoint_incluir_servico_de_outro_cliente_e_ignorado(client, django_user_model):
    """4 — "incluir" de um serviço de OUTRO cliente é contexto que não se aplica:
    ignora o parâmetro silenciosamente (200) e devolve só os ativos do cliente."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    outro = Cliente.objects.create(nome_empresa="Globex", cnpj="11444777000161")
    ativo = _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[0])
    intruso = _cria_servico(outro, _SERVICOS_EM_ORDEM[0], ativo=False)

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:servicos_por_cliente", args=[cliente.pk])
    response = client.get(f"{url}?incluir={intruso.pk}")

    assert response.status_code == 200
    servicos = response.json()["servicos"]
    ids = [s["id"] for s in servicos]
    assert intruso.pk not in ids
    assert ids == [ativo.pk]
    assert all(s["inativo"] is False for s in servicos)


@pytest.mark.django_db
def test_endpoint_incluir_desativado_respeita_ordem_de_definicao(client, django_user_model):
    """5 — o incluído-desativado respeita a ORDEM DE DEFINIÇÃO dos choices (não vai
    colado no fim): ativos nas posições 0 e 2, incluído-desativado na 1 → sai no meio."""
    cliente = Cliente.objects.create(nome_empresa="ACME", cnpj="11222333000181")
    _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[0])
    _servico_distinto(cliente, nome=_SERVICOS_EM_ORDEM[2])
    meio = _cria_servico(cliente, _SERVICOS_EM_ORDEM[1], ativo=False)

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)
    url = reverse("controle_acionamentos:servicos_por_cliente", args=[cliente.pk])
    response = client.get(f"{url}?incluir={meio.pk}")

    assert response.status_code == 200
    servicos = response.json()["servicos"]
    assert [s["nome"] for s in servicos] == [
        ServicoCliente.Nome(_SERVICOS_EM_ORDEM[0]).label,
        ServicoCliente.Nome(_SERVICOS_EM_ORDEM[1]).label,
        ServicoCliente.Nome(_SERVICOS_EM_ORDEM[2]).label,
    ]


# ---------------------------------------------------------------
# DD-068 ST1 — valor que o CLIENTE paga (RED)
# ---------------------------------------------------------------
# calcular_valor_cliente ainda NÃO existe em services.py — o import DENTRO do
# corpo isola o ImportError como "failed" (não derruba a coleta dos 230). Função
# pura, sem banco (nem @django_db). Exemplo-ouro: base 1500 + 0 km excedente
# (50 < 100) + 3h excedentes (7 - 4) × 55,00 = 1500 + 165 = 1665,00 (sem pedágio,
# sem escalonamento).
def test_valor_cliente_exemplo_ouro():
    from controle_acionamentos.services import calcular_valor_cliente
    valor = calcular_valor_cliente(
        valor_acionamento=Decimal("1500.00"),
        franquia_km=100,
        franquia_horas=4,
        valor_km_excedente=Decimal("2.80"),
        valor_hora_excedente=Decimal("55.00"),
        km_total=50,
        horas_total=Decimal("7.00"),
    )
    assert valor == Decimal("1665.00")


# ---------------------------------------------------------------
# DD-068 ST2 — valor do AGENTE resolvido pela franquia (RED)
# ---------------------------------------------------------------
# calcular_valor_agente_por_franquia ainda NÃO existe em services.py — o import
# DENTRO do corpo de CADA teste isola o ImportError como "failed" por teste, sem
# derrubar a coleta dos 231. Contrato: com franquia vinculada, usa EXCLUSIVAMENTE
# os valores da franquia (nunca os inline), delegando a matemática ao
# calcular_valor_agente existente (escalonamento e pedágio inclusos); sem
# franquia (None), retorna None — estado PENDENTE (decisão registrada). Funções
# puras: a franquia é um stub SimpleNamespace (sem banco, sem models).
from types import SimpleNamespace


def _franquia_stub_basica():
    """Franquia dos testes 1 e 2 (500/120km/5h/1,80/45, sem escalonamento)."""
    return SimpleNamespace(
        valor_acionamento=Decimal("500.00"),
        franquia_km=120,
        franquia_horas=5,
        valor_km_excedente=Decimal("1.80"),
        valor_hora_excedente=Decimal("45.00"),
        escalonamento_automatico=False,
    )


def test_valor_agente_exemplo_ouro():
    """1 — franquia sem escalonamento, km dentro (50 < 120), 2h excedentes:
    500 + 0 + 2 × 45 = 590,00."""
    from controle_acionamentos.services import calcular_valor_agente_por_franquia

    valor = calcular_valor_agente_por_franquia(
        franquia_agente=_franquia_stub_basica(),
        km_total=50,
        horas_total=Decimal("7.00"),
        pedagio=Decimal("0.00"),
    )
    assert valor == Decimal("590.00")


def test_valor_agente_soma_pedagio():
    """2 — mesma franquia e entradas do teste 1, pedágio 25,00: o pedágio soma
    SOMENTE no agente → 590 + 25 = 615,00."""
    from controle_acionamentos.services import calcular_valor_agente_por_franquia

    valor = calcular_valor_agente_por_franquia(
        franquia_agente=_franquia_stub_basica(),
        km_total=50,
        horas_total=Decimal("7.00"),
        pedagio=Decimal("25.00"),
    )
    assert valor == Decimal("615.00")


def test_valor_agente_escalonamento_via_franquia():
    """3 — exemplo 8.6 do PRD: franquia 660/200km/4h/3,30/55 com escalonamento,
    km 240 → 1 bloco (franquia ajustada 240km/5h, razão 1,2 → base 792,00), sem
    excedentes (240 = 240; 5,00 = 5) → 792,00. Prova que a delegação ao
    calcular_valor_agente preserva o escalonamento."""
    from controle_acionamentos.services import calcular_valor_agente_por_franquia

    franquia = SimpleNamespace(
        valor_acionamento=Decimal("660.00"),
        franquia_km=200,
        franquia_horas=4,
        valor_km_excedente=Decimal("3.30"),
        valor_hora_excedente=Decimal("55.00"),
        escalonamento_automatico=True,
    )
    valor = calcular_valor_agente_por_franquia(
        franquia_agente=franquia,
        km_total=240,
        horas_total=Decimal("5.00"),
        pedagio=Decimal("0.00"),
    )
    assert valor == Decimal("792.00")


def test_valor_agente_pendente_sem_franquia():
    """4 — sem franquia vinculada (None) não há o que calcular: retorna None,
    o estado PENDENTE (decisão registrada na DD-068)."""
    from controle_acionamentos.services import calcular_valor_agente_por_franquia

    valor = calcular_valor_agente_por_franquia(
        franquia_agente=None,
        km_total=50,
        horas_total=Decimal("7.00"),
        pedagio=Decimal("0.00"),
    )
    assert valor is None


# ---------------------------------------------------------------
# DD-069 ST1 — composição do valor do CLIENTE no detalhe (RED)
# ---------------------------------------------------------------
# compor_valor_cliente ainda NÃO existe em services.py — o import DENTRO do
# corpo isola o ImportError como "failed" por teste, sem derrubar a coleta.
# Contrato: compor_valor_cliente(acionamento) espelha compor_valor_agente
# (mesma família de extrato), mas a fonte são os valores do SERVIÇO gravados
# no acionamento (inline/snapshot) — NUNCA a franquia (que é lado agente) —
# e por isso não há parcela de pedágio nem escalonamento, em hipótese alguma.
# A view de detalhe passa a entregar `composicao_cliente` no contexto, ao lado
# da `composicao` (agente) já existente.


@pytest.mark.django_db
def test_compor_valor_cliente_contrato_ouro_parcelas_e_total(_fks_acionamento):
    """Contrato-ouro da DD-068/ST1 agora em parcelas: serviço 1500,00, franquia
    100km/4h, tarifas 2,80/55,00, percurso 50km/7h → base 1500,00 + km excedente
    0,00 (qtd 0) + hora excedente 165,00 (qtd 3) = 1665,00, tudo quantizado a
    2 casas (ROUND_HALF_UP, o _quantizar da casa)."""
    cliente, responsavel, agente = _fks_acionamento
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=None,
        valor_acionamento=Decimal("1500.00"),
        franquia_km=100,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.80"),
        valor_hora_excedente=Decimal("55.00"),
        pedagio=Decimal("0.00"),
        km_inicio=0,
        km_final=50,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=7),
    )
    ac.save()

    from controle_acionamentos.services import compor_valor_cliente

    comp = compor_valor_cliente(ac)

    assert comp.valor_acionamento == Decimal("1500.00")
    # 50 < 100: sem km excedente — quantidade 0, subtotal zerado quantizado.
    assert comp.km_excedente == 0
    assert comp.subtotal_km == Decimal("0.00")
    # 7 - 4 = 3h excedentes × 55,00 = 165,00.
    assert comp.hora_excedente == Decimal("3.00")
    assert comp.subtotal_hora == Decimal("165.00")
    # Tarifas unitárias do SERVIÇO (espelho do extrato do agente).
    assert comp.valor_unitario_km == Decimal("2.80")
    assert comp.valor_unitario_hora == Decimal("55.00")
    # Total: soma das parcelas, quantizado.
    assert comp.valor_cliente == Decimal("1665.00")


@pytest.mark.django_db
def test_compor_valor_cliente_sem_pedagio_e_sem_escalonamento(_fks_acionamento):
    """Pedágio e escalonamento são EXCLUSIVOS do agente: mesmo com pedágio 50,00
    registrado E franquia escalonável vinculada, o extrato do cliente não ganha
    parcela de pedágio nem blocos — e o total segue 1665,00 (contrato-ouro)."""
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(
        **_dados_franquia(cliente, escalonamento_automatico=True)
    )
    base = timezone.now()
    ac = _acionamento_valido(
        cliente,
        responsavel,
        agente,
        franquia_agente=franquia,
        valor_acionamento=Decimal("1500.00"),
        franquia_km=100,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.80"),
        valor_hora_excedente=Decimal("55.00"),
        pedagio=Decimal("50.00"),
        km_inicio=0,
        km_final=50,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=7),
    )
    ac.save()

    from controle_acionamentos.services import compor_valor_cliente

    comp = compor_valor_cliente(ac)

    # O extrato do cliente NÃO tem as parcelas exclusivas do agente.
    assert not hasattr(comp, "pedagio")
    assert not hasattr(comp, "blocos")
    # Base sem escalonamento e total sem pedágio: contrato-ouro intacto.
    assert comp.valor_acionamento == Decimal("1500.00")
    assert comp.valor_cliente == Decimal("1665.00")


@pytest.mark.django_db
def test_acionamento_detail_contexto_traz_composicao_cliente_com_franquia(
    client, django_user_model, _fks_acionamento
):
    """A view de detalhe entrega `composicao_cliente` preenchida no contexto,
    ao lado da `composicao` (agente) já existente — acionamento COM franquia
    tem os dois extratos."""
    cliente, responsavel, agente = _fks_acionamento
    franquia = FranquiaAgente.objects.create(**_dados_franquia(cliente))
    ac = _acionamento_valido(cliente, responsavel, agente, franquia_agente=franquia)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_detail", args=[ac.pk])
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["composicao"] is not None
    assert response.context["composicao_cliente"] is not None


@pytest.mark.django_db
def test_acionamento_detail_sem_franquia_composicao_cliente_preenchida(
    client, django_user_model, _fks_acionamento
):
    """SEM franquia o agente fica pendente (`composicao` None, DD-068/ST3), mas
    o valor do CLIENTE não depende de franquia: `composicao_cliente` vem
    preenchida do mesmo jeito."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_valido(cliente, responsavel, agente, franquia_agente=None)
    ac.save()

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    url = reverse("controle_acionamentos:acionamento_detail", args=[ac.pk])
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["composicao"] is None
    assert response.context["composicao_cliente"] is not None


# ---------------------------------------------------------------------------
# DD-070 ST1 — regras de suspeita do saneamento de legados (FASE RED)
# As três funções PURAS ainda NÃO existem em controle_acionamentos.services —
# por isso os 14 testes abaixo nascem VERMELHOS de propósito (TDD): o import
# LOCAL dispara ImportError isolado por teste, sem derrubar a coleta da suite.
# Contrato sob teste (todas devolvem list[str]; lista vazia = registro limpo):
#   avaliar_suspeita_velocidade(km_inicial, km_final, minutos) -> list[str]
#   avaliar_suspeita_faixas(valor_base, tarifa_km, tarifa_hora) -> list[str]
#   avaliar_suspeita_valores_identicos(valor_base, tarifa_km, tarifa_hora)
#       -> list[str]
# Valores monetários e de km SEMPRE em Decimal; `minutos` é int ou None.
# O script de saneamento só RELATA suspeitas — nunca altera registro.
# ---------------------------------------------------------------------------


class TestRegrasSuspeitaSaneamento:
    # -- avaliar_suspeita_velocidade ------------------------------------

    def test_velocidade_contrato_ouro_e_limpa(self):
        """1 — percurso do contrato-ouro: 50 km em 420 min (~7,1 km/h) é
        plenamente plausível → lista vazia (registro limpo)."""
        from controle_acionamentos.services import avaliar_suspeita_velocidade

        motivos = avaliar_suspeita_velocidade(
            km_inicial=Decimal("100"),
            km_final=Decimal("150"),
            minutos=420,
        )
        assert motivos == []

    def test_velocidade_especime_absurda_gera_motivo(self):
        """2 — espécime real do saneamento: 310 km em 4 minutos (4650 km/h)
        é fisicamente impossível → pelo menos um motivo de suspeita."""
        from controle_acionamentos.services import avaliar_suspeita_velocidade

        motivos = avaliar_suspeita_velocidade(
            km_inicial=Decimal("0"),
            km_final=Decimal("310"),
            minutos=4,
        )
        assert len(motivos) >= 1

    def test_velocidade_borda_exatos_120_kmh_e_limpa(self):
        """3 — borda INCLUSIVA do teto: 120 km em 60 min = exatamente
        120 km/h ainda é aceito → lista vazia."""
        from controle_acionamentos.services import avaliar_suspeita_velocidade

        motivos = avaliar_suspeita_velocidade(
            km_inicial=Decimal("0"),
            km_final=Decimal("120"),
            minutos=60,
        )
        assert motivos == []

    def test_velocidade_borda_121_kmh_e_suspeita(self):
        """4 — primeiro valor acima do teto: 121 km em 60 min = 121 km/h
        estoura a borda → pelo menos um motivo."""
        from controle_acionamentos.services import avaliar_suspeita_velocidade

        motivos = avaliar_suspeita_velocidade(
            km_inicial=Decimal("0"),
            km_final=Decimal("121"),
            minutos=60,
        )
        assert len(motivos) >= 1

    def test_velocidade_tempo_impossivel_gera_motivo(self):
        """5 — km percorrido > 0 exige tempo: minutos == 0 e minutos None
        são ambos tempo impossível de apurar → motivo nos dois subcasos."""
        from controle_acionamentos.services import avaliar_suspeita_velocidade

        motivos_zero = avaliar_suspeita_velocidade(
            km_inicial=Decimal("0"),
            km_final=Decimal("50"),
            minutos=0,
        )
        assert len(motivos_zero) >= 1

        motivos_none = avaliar_suspeita_velocidade(
            km_inicial=Decimal("0"),
            km_final=Decimal("50"),
            minutos=None,
        )
        assert len(motivos_none) >= 1

    def test_velocidade_km_final_menor_que_inicial_gera_motivo(self):
        """6 — hodômetro andando para trás (150 → 100) é registro
        inconsistente → pelo menos um motivo."""
        from controle_acionamentos.services import avaliar_suspeita_velocidade

        motivos = avaliar_suspeita_velocidade(
            km_inicial=Decimal("150"),
            km_final=Decimal("100"),
            minutos=60,
        )
        assert len(motivos) >= 1

    # -- avaliar_suspeita_faixas ----------------------------------------

    def test_faixas_contratos_ouro_sao_limpos(self):
        """7 — os dois contratos-ouro da casa caem dentro de todas as
        faixas → lista vazia em ambos."""
        from controle_acionamentos.services import avaliar_suspeita_faixas

        motivos_1500 = avaliar_suspeita_faixas(
            valor_base=Decimal("1500"),
            tarifa_km=Decimal("4.00"),
            tarifa_hora=Decimal("55.00"),
        )
        assert motivos_1500 == []

        motivos_500 = avaliar_suspeita_faixas(
            valor_base=Decimal("500"),
            tarifa_km=Decimal("2.80"),
            tarifa_hora=Decimal("45.00"),
        )
        assert motivos_500 == []

    def test_faixas_especime_estoura_tarifas_com_exatamente_dois_motivos(self):
        """8 — espécime real: tarifa_km 4214,00 e tarifa_hora 421412,00
        estouram os tetos, mas o valor_base 4214,00 está dentro da faixa
        → EXATAMENTE 2 motivos."""
        from controle_acionamentos.services import avaliar_suspeita_faixas

        motivos = avaliar_suspeita_faixas(
            valor_base=Decimal("4214.00"),
            tarifa_km=Decimal("4214.00"),
            tarifa_hora=Decimal("421412.00"),
        )
        assert len(motivos) == 2

    def test_faixas_bordas_inclusivas_sao_limpas(self):
        """9 — bordas INCLUSIVAS das faixas: o trio no piso (200/1,00/5,00)
        e o trio no teto (20000/6,00/60,00) são ambos aceitos → vazias."""
        from controle_acionamentos.services import avaliar_suspeita_faixas

        motivos_piso = avaliar_suspeita_faixas(
            valor_base=Decimal("200.00"),
            tarifa_km=Decimal("1.00"),
            tarifa_hora=Decimal("5.00"),
        )
        assert motivos_piso == []

        motivos_teto = avaliar_suspeita_faixas(
            valor_base=Decimal("20000.00"),
            tarifa_km=Decimal("6.00"),
            tarifa_hora=Decimal("60.00"),
        )
        assert motivos_teto == []

    def test_faixas_tarifa_hora_abaixo_do_piso_gera_motivo(self):
        """10 — tarifa_hora 4,00 fica abaixo do piso da faixa (5,00)
        → pelo menos um motivo."""
        from controle_acionamentos.services import avaliar_suspeita_faixas

        motivos = avaliar_suspeita_faixas(
            valor_base=Decimal("1500"),
            tarifa_km=Decimal("4.00"),
            tarifa_hora=Decimal("4.00"),
        )
        assert len(motivos) >= 1

    # -- avaliar_suspeita_valores_identicos ------------------------------

    def test_identicos_valor_base_igual_tarifa_km_gera_motivo(self):
        """11 — valor_base e tarifa_km idênticos (4214,00, o espécime) é a
        assinatura de digitação repetida → pelo menos um motivo."""
        from controle_acionamentos.services import (
            avaliar_suspeita_valores_identicos,
        )

        motivos = avaliar_suspeita_valores_identicos(
            valor_base=Decimal("4214.00"),
            tarifa_km=Decimal("4214.00"),
            tarifa_hora=Decimal("55.00"),
        )
        assert len(motivos) >= 1

    def test_identicos_tarifa_km_igual_tarifa_hora_gera_motivo(self):
        """12 — tarifa_km e tarifa_hora idênticas (6,00) também são par
        suspeito de digitação repetida → pelo menos um motivo."""
        from controle_acionamentos.services import (
            avaliar_suspeita_valores_identicos,
        )

        motivos = avaliar_suspeita_valores_identicos(
            valor_base=Decimal("1500"),
            tarifa_km=Decimal("6.00"),
            tarifa_hora=Decimal("6.00"),
        )
        assert len(motivos) >= 1

    def test_identicos_contrato_ouro_tres_valores_distintos_e_limpo(self):
        """13 — contrato-ouro com três valores distintos (1500 / 4,00 /
        55,00): nenhum par idêntico → lista vazia."""
        from controle_acionamentos.services import (
            avaliar_suspeita_valores_identicos,
        )

        motivos = avaliar_suspeita_valores_identicos(
            valor_base=Decimal("1500"),
            tarifa_km=Decimal("4.00"),
            tarifa_hora=Decimal("55.00"),
        )
        assert motivos == []

    def test_identicos_dois_campos_zerados_nao_gera_motivo(self):
        """14 — tarifa_km e tarifa_hora ambas 0,00: a comparação de
        idênticos só vale quando AMBOS os valores são > 0 — zero a zero
        não é digitação repetida → lista vazia."""
        from controle_acionamentos.services import (
            avaliar_suspeita_valores_identicos,
        )

        motivos = avaliar_suspeita_valores_identicos(
            valor_base=Decimal("1500"),
            tarifa_km=Decimal("0.00"),
            tarifa_hora=Decimal("0.00"),
        )
        assert motivos == []


# ---------------------------------------------------------------------------
# DD-070 ST4 — persistência do valor do cliente (FASE RED)
# O campo `valor_cliente` ainda NÃO existe no model Acionamento — os 5 testes
# abaixo nascem VERMELHOS de propósito (TDD). Contrato sob teste:
#   Acionamento.valor_cliente — DecimalField(max_digits=10, decimal_places=2,
#       null=True, editable=False), gravado no fluxo de save como espelho do
#       valor_agente (RN-08/§8.9 do PRD v1.5): a fonte é o snapshot inline do
#       serviço, sem pedágio e sem escalonamento; independe da franquia.
# Nenhuma função nova é importada — o alvo é o campo do model; o save e o
# vincular_franquia_em_lote existentes é que passam a persisti-lo no GREEN.
# ---------------------------------------------------------------------------


def _acionamento_contrato_ouro(cliente, responsavel, agente, **overrides):
    """Acionamento do contrato-ouro (DD-068/DD-069): serviço moto 1500,00,
    franquia 100 km/4 h, tarifas 2,80/55,00, percurso 100→150 km (50 km) em
    7 h, pedágio 0 → valor do cliente 1665,00. Espelha o setup dos testes de
    compor_valor_cliente, por cima do _acionamento_valido."""
    base = timezone.now()
    dados = dict(
        franquia_agente=None,
        valor_acionamento=Decimal("1500.00"),
        franquia_km=100,
        franquia_horas=Decimal("4.00"),
        valor_km_excedente=Decimal("2.80"),
        valor_hora_excedente=Decimal("55.00"),
        pedagio=Decimal("0.00"),
        km_inicio=100,
        km_final=150,
        data_hora_solicitado=base,
        data_hora_inicio=base,
        data_hora_final=base + timedelta(hours=7),
    )
    dados.update(overrides)
    return _acionamento_valido(cliente, responsavel, agente, **dados)


def _franquia_ouro_do_agente(cliente):
    """Franquia do agente do contrato-ouro: 500,00 base, 120 km/5 h, tarifas
    1,80/45,00, sem escalonamento (com o percurso de 50 km nem escalonaria)."""
    return FranquiaAgente.objects.create(
        **_dados_franquia(
            cliente,
            nome="Franquia Ouro Agente",
            valor_acionamento=Decimal("500.00"),
            franquia_km=120,
            franquia_horas=Decimal("5.00"),
            valor_km_excedente=Decimal("1.80"),
            valor_hora_excedente=Decimal("45.00"),
        )
    )


class TestPersistenciaValorCliente:
    @pytest.mark.django_db
    def test_contrato_do_campo_valor_cliente(self):
        """1 — contrato do campo via _meta (independe de dados), no padrão do
        test_contrato_dos_campos_de_rastreio: valor_cliente é DecimalField com
        max_digits=10 e decimal_places=2, null=True (legados nascem pendentes)
        e editable=False (calculado no save, nunca digitado)."""
        campo = Acionamento._meta.get_field("valor_cliente")

        assert campo.max_digits == 10
        assert campo.decimal_places == 2
        assert campo.null is True
        assert campo.editable is False

    @pytest.mark.django_db
    def test_save_sem_franquia_persiste_valor_cliente_e_agente_pendente(
        self, _fks_acionamento
    ):
        """2 — contrato-ouro sem franquia: o save persiste valor_cliente
        1665,00 (1500 + 3 h excedentes × 55,00) enquanto o valor_agente segue
        PENDENTE (None) — as duas contas são independentes (RN-08)."""
        cliente, responsavel, agente = _fks_acionamento
        ac = _acionamento_contrato_ouro(cliente, responsavel, agente)
        ac.save()

        ac.refresh_from_db()
        assert ac.valor_cliente == Decimal("1665.00")
        assert ac.valor_agente is None

    @pytest.mark.django_db
    def test_editar_campo_fonte_recalcula_valor_cliente(self, _fks_acionamento):
        """3 — editar um campo-fonte recalcula no save: esticando a jornada de
        7 para 8 h, as horas excedentes vão de 3 para 4 → 1500 + 4 × 55,00 =
        1720,00 persistidos."""
        cliente, responsavel, agente = _fks_acionamento
        ac = _acionamento_contrato_ouro(cliente, responsavel, agente)
        ac.save()

        ac.data_hora_final = ac.data_hora_inicio + timedelta(hours=8)
        ac.save()

        ac.refresh_from_db()
        assert ac.valor_cliente == Decimal("1720.00")

    @pytest.mark.django_db
    def test_pedagio_altera_valor_agente_e_preserva_valor_cliente(
        self, client, django_user_model, _fks_acionamento
    ):
        """4 — pedágio é exclusivo do agente: com a franquia-ouro vinculada
        (500 + 2 h excedentes × 45,00 = 590,00), atualizar o pedágio para
        25,00 pelo mesmo endpoint dos testes de pedágio leva o valor_agente a
        615,00 e o valor_cliente permanece 1665,00."""
        cliente, responsavel, agente = _fks_acionamento
        franquia = _franquia_ouro_do_agente(cliente)
        ac = _acionamento_contrato_ouro(
            cliente, responsavel, agente, franquia_agente=franquia
        )
        ac.save()

        user = _user_com_perms(django_user_model, "change_acionamento")
        client.force_login(user)

        url = reverse(
            "controle_acionamentos:acionamento_pedagio_update", args=[ac.pk]
        )
        response = client.post(url, {"pedagio": "25.00"})

        assert response.status_code == 200
        ac.refresh_from_db()
        assert ac.valor_agente == Decimal("615.00")
        assert ac.valor_cliente == Decimal("1665.00")

    @pytest.mark.django_db
    def test_vinculo_em_lote_calcula_agente_e_preserva_valor_cliente(
        self, _fks_acionamento
    ):
        """5 — o vínculo em lote resolve o agente pela franquia-ouro (500 +
        2 h excedentes × 45,00 = 590,00) e NÃO mexe no valor_cliente, que
        segue 1665,00 gravado desde o primeiro save."""
        cliente, responsavel, agente = _fks_acionamento
        franquia = _franquia_ouro_do_agente(cliente)
        ac = _acionamento_contrato_ouro(cliente, responsavel, agente)
        ac.save()

        from controle_acionamentos.services import vincular_franquia_em_lote

        vincular_franquia_em_lote([ac.pk], franquia)

        ac.refresh_from_db()
        assert ac.valor_agente == Decimal("590.00")
        assert ac.valor_cliente == Decimal("1665.00")


# ---------------------------------------------------------------------------
# DD-070 ST5 (parte 2) — home e listagem lendo o valor_cliente PERSISTIDO (RED)
# Três alvos que ainda NÃO existem — os 5 testes abaixo nascem VERMELHOS:
#   * selectors.somar_valor_cliente_no_mes — espelho do somar_valor_agente_no_mes
#     (testes 1-2 caem por ImportError, com o import LOCAL no corpo);
#   * card "Valor do cliente no mês" na home (teste 3);
#   * coluna "Valor cliente" na tabela de últimos acionamentos da home (teste 4);
#   * listagem lendo o CAMPO PERSISTIDO valor_cliente em vez de recalcular por
#     linha (teste 5 — a prova é gravar 999,99 direto via .update(), sem save).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_somar_valor_cliente_no_mes_soma_apenas_mes_corrente(_fks_acionamento):
    """DD-070/ST5 — espelho do somar_valor_agente_no_mes: soma o valor_cliente
    persistido só dos acionamentos do mês corrente. O contrato-ouro do mês
    atual (1665,00) entra; o de dois meses atrás fica fora → soma == 1665,00."""
    from controle_acionamentos.selectors import somar_valor_cliente_no_mes

    cliente, responsavel, agente = _fks_acionamento

    dentro = _acionamento_contrato_ouro(cliente, responsavel, agente)
    dentro.save()

    passado = timezone.now() - timedelta(days=62)
    fora = _acionamento_contrato_ouro(
        cliente,
        responsavel,
        agente,
        data_hora_solicitado=passado,
        data_hora_inicio=passado,
        data_hora_final=passado + timedelta(hours=7),
    )
    fora.save()

    resultado = somar_valor_cliente_no_mes(hoje=timezone.localdate())

    assert resultado == Decimal("1665.00")
    assert isinstance(resultado, Decimal)


@pytest.mark.django_db
def test_somar_valor_cliente_no_mes_zero_quando_vazio():
    """DD-070/ST5 — mês sem acionamentos soma Decimal("0") (Coalesce), nunca
    None — mesmo contrato do somar_valor_agente_no_mes."""
    from datetime import date

    from controle_acionamentos.selectors import somar_valor_cliente_no_mes

    assert somar_valor_cliente_no_mes(hoje=date(2026, 6, 15)) == Decimal("0")


@pytest.mark.django_db
def test_home_rotulo_do_card_de_valor_do_cliente_no_mes(
    client, django_user_model, _fks_acionamento
):
    """DD-070/ST5 (RED) — a home ganha o card "Valor do cliente no mês", irmão
    do card do agente (DD-069/ST3), somando o valor_cliente persistido: com um
    contrato-ouro no mês, a soma 1.665,00 aparece na resposta.
    Micro-etapa DD-070: o formato esperado ganhou separador de milhar ("2g")."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_contrato_ouro(cliente, responsavel, agente)
    ac.save()

    user = django_user_model.objects.create_user(
        username="home_cliente", password="x"
    )
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:index"))

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert "Valor do cliente no mês" in conteudo
    assert "1.665,00" in conteudo


@pytest.mark.django_db
def test_home_ultimos_acionamentos_exibem_coluna_valor_cliente(
    client, django_user_model, _fks_acionamento
):
    """DD-070/ST5 (RED) — a tabela "Últimos acionamentos" da home ganha a
    coluna "Valor cliente" (mesmo rótulo da listagem), exibindo na linha do
    contrato-ouro o valor_cliente persistido (1.665,00).
    Micro-etapa DD-070: o formato esperado ganhou separador de milhar ("2g")."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_contrato_ouro(cliente, responsavel, agente)
    ac.save()

    user = django_user_model.objects.create_user(
        username="home_coluna", password="x"
    )
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:index"))

    assert response.status_code == 200
    conteudo = response.content.decode(response.charset)
    assert "Últimos acionamentos" in conteudo
    assert "Valor cliente" in conteudo
    assert "1.665,00" in conteudo


@pytest.mark.django_db
def test_listagem_le_valor_cliente_persistido_e_nao_recalcula(
    client, django_user_model, _fks_acionamento
):
    """DD-070/ST5 (RED) — a PROVA da troca de fonte na listagem: gravando
    999,99 direto no banco via .update() (sem passar pelo save/recálculo), a
    página deve exibir o PERSISTIDO 999,99 — e não os 1665,00 que o recálculo
    por linha (compor_valor_cliente na view, o temporário da DD-069) produz.
    Micro-etapa DD-070: o formato esperado ganhou separador de milhar ("2g") —
    o guardião negativo passa a mirar "1.665,00", o render que o recálculo
    indevido produziria no formato novo."""
    cliente, responsavel, agente = _fks_acionamento
    ac = _acionamento_contrato_ouro(cliente, responsavel, agente)
    ac.save()

    Acionamento.objects.filter(pk=ac.pk).update(valor_cliente=Decimal("999.99"))

    user = _user_com_perms(django_user_model, "view_acionamento")
    client.force_login(user)

    response = client.get(reverse("controle_acionamentos:acionamento_list"))

    assert response.status_code == 200
    conteudo = response.content.decode("utf-8")
    assert "999,99" in conteudo
    assert "1.665,00" not in conteudo