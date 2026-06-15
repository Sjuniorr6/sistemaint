"""Serviços de regra de negócio do app de Acionamentos.

Funções puras (sem dependência de models/banco), testáveis em isolamento.
"""


def validar_cpf(cpf: str) -> bool:
    """Valida um CPF pelo algoritmo dos dígitos verificadores.

    Aceita CPF com ou sem máscara (pontos e hífen são ignorados).
    Retorna True se o CPF for válido, False caso contrário.
    """
    # Mantém só os dígitos, descartando pontos, hífen e espaços.
    numeros = [int(d) for d in cpf if d.isdigit()]

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
