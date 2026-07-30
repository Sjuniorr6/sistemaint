from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def split(value, arg):
    return value.split(arg)

@register.filter
def filter_by_cliente_and_mes(valores, arg):
    """
    Filtra os valores mensais por cliente e mês.
    arg deve estar no formato 'cliente_id,mes'
    """
    try:
        cliente_id, mes = arg.split(',')
        cliente_id = int(cliente_id)
        
        # Se valores for None ou vazio, retornar um dicionário vazio
        if not valores:
            return {'valor': '', 'enviado': False, 'codigo_rastreio': ''}
        
        # Procurar o valor correspondente
        for valor in valores:
            if valor.cliente_id == cliente_id and valor.mes == mes:
                # Converter para inteiro se houver valor
                valor_int = int(valor.valor) if valor.valor else ''
                # Garantir que codigo_rastreio seja sempre uma string
                codigo_rastreio = str(valor.codigo_rastreio) if valor.codigo_rastreio else ''
                result = {
                    'valor': str(valor_int),
                    'enviado': valor.enviado,
                    'codigo_rastreio': codigo_rastreio
                }
                print(f"DEBUG FILTER: cliente_id={cliente_id}, mes={mes}, valor={result['valor']}, enviado={result['enviado']}, codigo_rastreio={result['codigo_rastreio']}")
                return result
        
        # Se não encontrou, retornar um dicionário vazio
        return {'valor': '', 'enviado': False, 'codigo_rastreio': ''}
    except Exception as e:
        print(f"Erro no filtro filter_by_cliente_and_mes: {str(e)}")
        return {'valor': '', 'enviado': False, 'codigo_rastreio': ''}

@register.filter
def total_por_mes(valores, mes):
    """
    Calcula o total de valores para um determinado mês
    """
    try:
        total = 0
        for valor in valores:
            if valor.mes == mes and valor.valor:
                total += int(valor.valor)
        return total
    except Exception as e:
        print(f"Erro no filtro total_por_mes: {str(e)}")
        return 0

@register.filter
def media_por_cliente(valores, cliente_id):
    """
    Calcula a média mensal de equipamentos enviados para um cliente.

    A média considera apenas os meses que possuem valor registrado, para que
    meses ainda não preenchidos (ex.: meses futuros do ano corrente) não
    puxem o resultado para baixo.
    """
    try:
        cliente_id = int(cliente_id)
        total = 0
        meses_com_valor = 0
        for valor in valores:
            if valor.cliente_id == cliente_id and valor.valor:
                total += int(valor.valor)
                meses_com_valor += 1
        if not meses_com_valor:
            return '-'
        return round(total / meses_com_valor, 1)
    except Exception as e:
        print(f"Erro no filtro media_por_cliente: {str(e)}")
        return '-'

@register.filter
def media_geral(valores, arg=None):
    """
    Calcula a média mensal geral (todos os clientes), usando o mesmo critério
    de media_por_cliente: apenas meses com valor registrado entram na conta.
    """
    try:
        total = 0
        meses_com_valor = 0
        for valor in valores:
            if valor.valor:
                total += int(valor.valor)
                meses_com_valor += 1
        if not meses_com_valor:
            return '-'
        return round(total / meses_com_valor, 1)
    except Exception as e:
        print(f"Erro no filtro media_geral: {str(e)}")
        return '-'

@register.filter
def badge_style(status):
    mapping = {
        'Aguardando Liberação RFB': 'background:#1e7e34;color:#fff;border:2px solid #000;font-weight:bold;',
        'Aguardando Chegada na Base': 'background:#0dcaf0;color:#fff;border:2px solid #0dcaf0;font-weight:bold;',
        'Aguardando Coleta': 'background:#6c757d;color:#fff;border:2px solid #6c757d;font-weight:bold;',
        'Aguardando Embarque Internacional': 'background:#6c757d;color:#fff;border:2px solid #6c757d;font-weight:bold;',
        'Em reversa para o Brasil': 'background:#ff9800;color:#fff;border:2px solid #ff9800;font-weight:bold;',
        'Retirado, Ag. Envio': 'background:#ffc107;color:#111;',
        'Em viagem': 'background:#0d6efd;color:#fff;',
        'No destino': 'background:#6c757d;color:#fff;',
        'Estoque Cliente': 'background:#20c997;color:#fff;',
        'Danificado': 'background:#6f42c1;color:#fff;',
        'Extraviado': 'background:#dc3545;color:#fff;',
        'Equipamento na Base': 'background:#6c757d;color:#fff;',
        'Reversa Finalizada': 'background:#28a745;color:#fff;border:2px solid #28a745;font-weight:bold;',
        'Fora de Operação': 'background:#dc3545;color:#fff;border:2px solid #dc3545;font-weight:bold;',
    }
    return mapping.get(status, 'background:#f8f9fa;color:#111;') 

@register.filter
def dias_entre(date1, date2):
    if date1 and date2:
        return (date1 - date2).days
    return '-' 
