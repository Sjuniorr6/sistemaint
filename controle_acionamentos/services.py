"""Serviços de regra de negócio do app de Acionamentos.

Funções puras (sem dependência de models/banco), testáveis em isolamento.
"""


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