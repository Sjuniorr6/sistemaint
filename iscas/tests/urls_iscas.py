"""Mantido por compatibilidade: os testes usam o `app.urls` real.

O URLconf de teste precisa ser o do projeto inteiro, e não só as rotas do
iscas, porque `templates/base.html` inclui `components/_header.html`, que faz
`{% url %}` para rotas de vários apps do GSInt. Ver `settings_iscas.py`.
"""
from app.urls import urlpatterns  # noqa: F401
