from .models import registrodemanutencao


def manutencoes_pendentes(request):

    if not request.user.is_authenticated:
        return {}

    total_pendentes = registrodemanutencao.objects.filter(
        status__in=[
            'Comercial',
            'Aprovado pela Inteligência'
        ]
    ).count()


    return {
        'manutencoes_pendentes': total_pendentes
    }
