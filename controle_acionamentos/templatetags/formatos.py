from django import template

register = template.Library()


@register.filter
def cnpj(valor):
    """Formata 14 dígitos como 00.000.000/0000-00; devolve o valor
    original se não tiver exatamente 14 dígitos."""
    digitos = "".join(c for c in str(valor) if c.isdigit())
    if len(digitos) != 14:
        return valor
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"


@register.filter
def cpf(valor):
    """Formata 11 dígitos como 000.000.000-00; devolve o valor
    original se não tiver exatamente 11 dígitos (mesmo padrão defensivo do cnpj)."""
    digitos = "".join(c for c in str(valor) if c.isdigit())
    if len(digitos) != 11:
        return valor
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
