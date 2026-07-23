"""DD-052 ST2 — cria/converge os grupos de permissão de produção do app.

Passo de PÓS-DEPLOY: depois do `migrate` (que cria as Permissions), rodar

    python manage.py criar_grupos_acionamentos

É SEGURO rodar quantas vezes for preciso: o comportamento é DECLARATIVO —
`get_or_create` no grupo e `permissions.set` com o conjunto canônico, então
rodar de novo não duplica nada (idempotência) e um grupo editado à mão
converge de volta ao conjunto exato (permissão intrusa é removida).

Nenhum grupo recebe permissão de DELETE — exclusão não faz parte da operação
(histórico imutável); se um dia existir, será decisão explícita, não default.
"""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

_ACOES = ("view", "add", "change")  # nunca delete
_PERMISSOES_OPERACAO = [f"{acao}_acionamento" for acao in _ACOES]
_PERMISSOES_CADASTROS = [
    f"{acao}_{entidade}"
    for entidade in (
        "cliente", "agente", "responsavelagente", "franquiaagente", "servicocliente"
    )
    for acao in _ACOES
]

# Nome do grupo -> codenames canônicos. Gestão é a UNIÃO calculada dos dois
# (fonte única — não digitar a lista duas vezes).
GRUPOS_ACIONAMENTOS = {
    "Acionamentos Operação": _PERMISSOES_OPERACAO,
    "Acionamentos Cadastros": _PERMISSOES_CADASTROS,
    "Acionamentos Gestão": _PERMISSOES_OPERACAO + _PERMISSOES_CADASTROS,
}


class Command(BaseCommand):
    help = (
        "Cria/converge os grupos de permissão do controle_acionamentos "
        "(DD-052 ST2). Idempotente — seguro rodar quantas vezes for preciso."
    )

    def handle(self, *args, **options):
        for nome, codenames in GRUPOS_ACIONAMENTOS.items():
            permissoes = list(
                Permission.objects.filter(
                    content_type__app_label="controle_acionamentos",
                    codename__in=codenames,
                )
            )
            faltantes = set(codenames) - {p.codename for p in permissoes}
            if faltantes:
                # Em produção, permissão faltando = migrate não rodado. Falhar
                # alto e nomeando — jamais ignorar em silêncio.
                raise CommandError(
                    "Permissões esperadas não existem no banco (o migrate "
                    "rodou?): " + ", ".join(sorted(faltantes))
                )
            grupo, _ = Group.objects.get_or_create(name=nome)
            grupo.permissions.set(permissoes)
            self.stdout.write(f"{nome}: {len(permissoes)} permissões aplicadas")
