"""
Vincula um usuário JÁ EXISTENTE ao rodapé do painel (bloco "Divisão de Tarefas"),
criando um FuncionarioAdministrativo com perfil='operador' apontando para a conta
dele. NÃO cria conta, NÃO altera senha e NÃO mexe em permissões/grupos — o usuário
mantém exatamente o acesso que já tem ao sistema int.

Use este comando para pessoas que já acessam o sistema e só precisam aparecer no
rodapé (ex.: André Simão). Para trocar a Laysa pela Ellen, use `substituir_usuario`.

Se o login informado não existir, o comando avisa e NÃO cria nada — porque a
premissa é que a pessoa já tem acesso.

Exemplos:
    python manage.py vincular_operador --dry-run
    python manage.py vincular_operador                       # vincula o padrão (André Simão)
    python manage.py vincular_operador --login joao.silva --nome "João Silva"
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from controle_administrativo.models import FuncionarioAdministrativo

# (nome de exibição na board, login existente). Pessoas que JÁ têm acesso.
OPERADORES_PADRAO = [
    ('André Simão', 'Andre.Simao'),
]


class Command(BaseCommand):
    help = 'Vincula um usuário existente ao rodapé do painel como operador (sem tocar em senha/permissões).'

    def add_arguments(self, parser):
        parser.add_argument('--login', default=None,
                            help='Login (username) existente a vincular. Omitido = usa a lista padrão.')
        parser.add_argument('--nome', default=None,
                            help='Nome de exibição no rodapé (padrão: o próprio login / nome completo).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostra o que seria feito sem gravar nada.')

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']

        if opts['login']:
            alvos = [(opts['nome'] or opts['login'], opts['login'])]
        else:
            alvos = OPERADORES_PADRAO

        self.stdout.write('-' * 60)
        self.stdout.write(self.style.MIGRATE_HEADING('Vincular operador(es) existente(s) ao rodape'))

        for nome, login in alvos:
            user = User.objects.filter(username__iexact=login).first()

            if user is None:
                self.stderr.write(self.style.ERROR(
                    f'  [!] Login "{login}" nao encontrado. Nada criado — a pessoa precisa JA ter '
                    f'acesso ao sistema. Confira o username correto e rode com --login.'))
                continue

            nome_exib = nome or (user.get_full_name().strip() or user.username)

            if dry_run:
                existe = FuncionarioAdministrativo.objects.filter(usuario=user).exists()
                self.stdout.write(
                    f'  [DRY] {nome_exib:<16} login={login:<14} '
                    f'card={"ja existe (garante operador/ativo)" if existe else "criar"} '
                    f'| senha/permissoes: intactas')
                continue

            with transaction.atomic():
                func, criado = FuncionarioAdministrativo.objects.get_or_create(
                    usuario=user,
                    defaults={
                        'nome': nome_exib,
                        'perfil': 'operador',
                        'ativo': True,
                        'senha_provisoria': False,  # mantem o acesso atual; nao forca troca
                    },
                )
                if not criado:
                    func.nome   = nome_exib
                    func.perfil = 'operador'
                    func.ativo  = True
                    # Não forçamos troca de senha para quem já tem acesso.
                    func.senha_provisoria = False
                    func.save(update_fields=['nome', 'perfil', 'ativo', 'senha_provisoria'])

            estado = 'card criado' if criado else 'card atualizado (operador/ativo)'
            self.stdout.write(self.style.SUCCESS(
                f'  [OK] {nome_exib:<16} login={login:<14} -> {estado} | senha intacta'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN: nada foi gravado.'))
            return

        total = FuncionarioAdministrativo.objects.filter(perfil='operador', ativo=True).count()
        self.stdout.write('-' * 60)
        self.stdout.write(self.style.SUCCESS(
            f'Concluido. {total} operador(es) ativo(s) aparecerao no rodape do painel.'))
