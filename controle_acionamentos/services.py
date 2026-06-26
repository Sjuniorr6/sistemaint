"""Serviços de regra de negócio do app de Acionamentos.

Funções puras (sem dependência de models/banco), testáveis em isolamento.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


def _so_digitos(documento: str) -> list[int]:
    """Extrai apenas os dígitos de um documento, como lista de inteiros.

    Base comum dos validadores de CPF, CNPJ e CNH — ignora pontos,
    barra, hífen e espaços. O underscore inicial sinaliza "uso interno
    do módulo".
    """
    return [int(d) for d in documento if d.isdigit()]


def validar_cpf(cpf: str) -> bool:
    """Valida um CPF pelo algoritmo dos dígitos verificadores.

    Aceita CPF com ou sem máscara (pontos e hífen são ignorados).
    Retorna True se o CPF for válido, False caso contrário.
    """
    # Mantém só os dígitos, descartando pontos, hífen e espaços.
    numeros = _so_digitos(cpf)

    # CPF tem exatamente 11 dígitos.
    if len(numeros) != 11:
        return False

    # CPFs com todos os dígitos iguais (ex.: 111.111.111-11) são inválidos
    # por convenção (RN-01), embora passem no cálculo do dígito verificador.
    if len(set(numeros)) == 1:
        return False

    # Calcula um dígito verificador a partir dos dígitos anteriores.
    def calcular_digito(parciais: list[int]) -> int:
        # O peso começa em (quantidade de dígitos + 1) e decresce.
        peso = len(parciais) + 1
        soma = 0
        for numero in parciais:
            soma += numero * peso
            peso -= 1
        resto = (soma * 10) % 11
        # Resto 10 é tratado como 0 (regra do algoritmo).
        return resto if resto < 10 else 0

    # Primeiro dígito verificador: calculado sobre os 9 primeiros números.
    primeiro = calcular_digito(numeros[:9])
    # Segundo dígito verificador: calculado sobre os 10 primeiros números.
    segundo = calcular_digito(numeros[:10])

    # O CPF é válido se os dois dígitos calculados batem com os informados.
    return numeros[9] == primeiro and numeros[10] == segundo


def validar_cnpj(cnpj: str) -> bool:
    """Valida um CNPJ pelo algoritmo dos dígitos verificadores.

    Aceita CNPJ com ou sem máscara (pontos, barra e hífen são ignorados).
    Retorna True se o CNPJ for válido, False caso contrário.
    """
    # Mantém só os dígitos, descartando pontos, barra, hífen e espaços.
    numeros = _so_digitos(cnpj)

    # CNPJ tem exatamente 14 dígitos.
    if len(numeros) != 14:
        return False

    # CNPJs com todos os dígitos iguais (ex.: 00.000.000/0000-00) são inválidos
    # por convenção (RN-02), embora passem no cálculo do dígito verificador.
    if len(set(numeros)) == 1:
        return False

    # Calcula um dígito verificador a partir dos dígitos e seus pesos.
    # Diferente do CPF, os pesos do CNPJ não seguem uma sequência simples
    # (saltam de 2 para 9 no meio), então vêm de fora, explícitos.
    def calcular_digito(parciais: list[int], pesos: list[int]) -> int:
        soma = sum(numero * peso for numero, peso in zip(parciais, pesos))
        resto = (soma * 10) % 11
        # Resto 10 é tratado como 0 (mesma regra do validar_cpf).
        return resto if resto < 10 else 0

    # Pesos oficiais do CNPJ para cada dígito verificador.
    pesos_primeiro = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_segundo = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    # Primeiro dígito verificador: calculado sobre os 12 primeiros números.
    primeiro = calcular_digito(numeros[:12], pesos_primeiro)
    # Segundo dígito verificador: calculado sobre os 13 primeiros números.
    segundo = calcular_digito(numeros[:13], pesos_segundo)

    # O CNPJ é válido se os dois dígitos calculados batem com os informados.
    return numeros[12] == primeiro and numeros[13] == segundo

def validar_cnh(cnh: str) -> bool:
    """Valida uma CNH pelo algoritmo dos dígitos verificadores.

    Aceita CNH com ou sem máscara (espaços e pontuação são ignorados).
    Retorna True se a CNH for válida, False caso contrário.
    """
    numeros = _so_digitos(cnh)

    # CNH tem exatamente 11 dígitos.
    if len(numeros) != 11:
        return False

    # CNHs com todos os dígitos iguais são inválidas, embora passem na conta.
    if len(set(numeros)) == 1:
        return False

    # Primeiro dígito verificador: pesos 9..1 sobre os 9 primeiros números.
    soma = sum(numeros[i] * (9 - i) for i in range(9))
    dv1 = soma % 11
    # Pegadinha da CNH: se o cálculo "estoura" (>= 10), o dígito vira 0 e
    # marca um desconto que será aplicado no segundo dígito.
    desconto = 0
    if dv1 >= 10:
        dv1 = 0
        desconto = 2

    # Segundo dígito verificador: pesos 1..9 sobre os 9 primeiros números.
    # A ORDEM dos ajustes importa: subtrai o desconto -> corrige se ficar
    # negativo (+11) -> e só então trata o "estouro" (>= 10) como 0.
    soma = sum(numeros[i] * (i + 1) for i in range(9))
    dv2 = soma % 11
    dv2 = dv2 - desconto
    if dv2 < 0:
        dv2 += 11
    if dv2 >= 10:
        dv2 = 0

    # A CNH é válida se os dois dígitos calculados batem com os informados.
    return numeros[9] == dv1 and numeros[10] == dv2


# ---------------------------------------------------------------------------
# CalculadoraValorAgente — cálculo do valor pago ao agente (§8 e §11 do PRD)
# ---------------------------------------------------------------------------

# Dinheiro e horas são sempre apresentados com 2 casas decimais. Centralizamos
# o quantum num lugar só para a regra de arredondamento não se espalhar.
_DOIS_CASAS = Decimal("0.01")


def _quantizar(valor: Decimal) -> Decimal:
    """Arredonda um Decimal para 2 casas, meio-para-cima (ROUND_HALF_UP).

    É o arredondamento contábil esperado em valor monetário. O default do
    Python para Decimal é ROUND_HALF_EVEN ("banker's rounding"), que
    arredondaria 2,005 para 2,00 — não é o que queremos aqui.
    """
    return valor.quantize(_DOIS_CASAS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class EntradaCalculoAgente:
    """Entrada do cálculo do valor do agente — os 9 campos-fonte do contrato.

    Dado puro, sem Django/model: a calculadora recebe ``km_total`` e
    ``horas_total`` JÁ resolvidos (a derivação do §8.2 é feita por quem chama).
    Campos de exibição como ``nome_servico`` não entram aqui — não participam de
    nenhuma conta. ``frozen=True`` porque a entrada de um cálculo é imutável:
    montou, não muda mais.
    """

    valor_acionamento: Decimal
    franquia_km: int
    franquia_horas: Decimal
    valor_km_excedente: Decimal
    valor_hora_excedente: Decimal
    escalonamento_ativo: bool
    km_total: int
    horas_total: Decimal
    pedagio: Decimal


@dataclass(frozen=True)
class ResultadoCalculoAgente:
    """Resultado do cálculo — todos os campos derivados do contrato.

    Além do ``valor_agente`` final, expõe os passos intermediários do
    escalonamento (``blocos`` e os ``*_ajustada``) para a auditoria do PRD
    (§8.6/§8.7) poder conferir cada etapa, não só o número final. ``frozen=True``
    para o resultado de um cálculo não ser alterado depois de produzido.
    """

    blocos: int
    franquia_km_ajustada: int
    franquia_horas_ajustada: Decimal
    valor_acionamento_ajustado: Decimal
    km_excedente: int
    hora_excedente: Decimal
    valor_agente: Decimal


def calcular_valor_agente(entrada: EntradaCalculoAgente) -> ResultadoCalculoAgente:
    """Calcula o valor a pagar ao agente a partir dos campos-fonte (§8.4/§8.5).

    Escopo atual (Green do Cenário 1): SEM escalonamento — os valores ajustados
    são iguais aos de base e ``blocos == 0``. A lógica do §8.3 (escalonamento)
    entra nos Cenários 3 e 4 e só vai alterar o bloco de ajuste abaixo; a soma
    final do §8.5 já está na forma definitiva (usa ``valor_acionamento_ajustado``).
    """
    # §8.3 — escalonamento: a cada 40 km acima da franquia base soma-se um
    # "bloco" à franquia (km e horas) e o valor é escalado na MESMA proporção do
    # km. A razão é calculada em Decimal/Decimal para nunca passar por float —
    # dinheiro não tolera o erro binário do float.
    if entrada.escalonamento_ativo and entrada.km_total > entrada.franquia_km:
        blocos = (entrada.km_total - entrada.franquia_km) // 40
        franquia_km_ajustada = entrada.franquia_km + blocos * 40
        franquia_horas_ajustada = entrada.franquia_horas + blocos
        razao = Decimal(franquia_km_ajustada) / Decimal(entrada.franquia_km)
        valor_acionamento_ajustado = _quantizar(entrada.valor_acionamento * razao)
    else:
        # Sem escalonamento (ou km dentro da franquia): o "ajustado" é o de base.
        blocos = 0
        franquia_km_ajustada = entrada.franquia_km
        franquia_horas_ajustada = entrada.franquia_horas
        valor_acionamento_ajustado = entrada.valor_acionamento

    # §8.4 — excedente é o que passou da franquia ajustada (nunca negativo).
    km_excedente = max(0, entrada.km_total - franquia_km_ajustada)
    hora_excedente = _quantizar(
        max(Decimal("0"), entrada.horas_total - franquia_horas_ajustada)
    )

    # §8.5 — valor final = base ajustada + excedentes às tarifas + pedágio.
    valor_agente = _quantizar(
        valor_acionamento_ajustado
        + (km_excedente * entrada.valor_km_excedente)
        + (hora_excedente * entrada.valor_hora_excedente)
        + entrada.pedagio
    )

    return ResultadoCalculoAgente(
        blocos=blocos,
        franquia_km_ajustada=franquia_km_ajustada,
        franquia_horas_ajustada=franquia_horas_ajustada,
        valor_acionamento_ajustado=valor_acionamento_ajustado,
        km_excedente=km_excedente,
        hora_excedente=hora_excedente,
        valor_agente=valor_agente,
    )