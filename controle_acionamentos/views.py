from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def index(request):
    """Página inicial do app de Acionamentos.

    View fina do Módulo 0: apenas renderiza a tela inicial para validar
    o encanamento URL -> view -> template. Sem regra de negócio aqui.
    """
    return render(request, 'controle_acionamentos/index.html')