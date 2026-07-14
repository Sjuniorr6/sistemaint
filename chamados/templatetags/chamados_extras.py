"""Filtros de template do app Chamados."""
from django import template

register = template.Library()


@register.filter
def split(value, separador=", "):
    """Divide uma string por `separador`, descartando itens vazios.

    Usado para exibir campos multi-valor (ex.: numero_equipamento, gravado como
    "EQ-1, EQ-2") como itens separados no template.
    """
    if not value:
        return []
    return [parte.strip() for parte in str(value).split(separador) if parte.strip()]
