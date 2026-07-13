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
