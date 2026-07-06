"""
Substitui, no cadastro existente, a usuária de saída (padrão: Laysa) pela usuária
de entrada (padrão: Ellen Costa) — SPEC "Atualização de Usuário e Board", seção 8.

A substituição é feita SOBRE o mesmo registro (mesmo User + FuncionarioAdministrativo),
apenas trocando login, nome e senha. Assim, todo o histórico e todos os vínculos
(tarefas, comentários, execuções, itens de bloco, tarefas da divisão) são preservados
automaticamente, pois as chaves estrangeiras continuam apontando para o mesmo id.

A nova senha é gravada como PROVISÓRIA: no primeiro acesso o painel obriga a troca
(FuncionarioAdministrativo.senha_provisoria=True). Idempotente e seguro para rodar em
produção — use --dry-run para pré-visualizar sem gravar.

Exemplos:
    python manage.py substituir_usuario --dry-run
    python manage.py substituir_usuario
    python manage.py substituir_usuario --de Laysa --login Ellen.Costa --nome "Ellen Costa"
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q

from controle_administrativo.models import FuncionarioAdministrativo


class Command(BaseCommand):
    help = 'Substitui a usuária de saída (Laysa) pela de entrada (Ellen Costa) no cadastro existente.'

    def add_arguments(self, parser):
        parser.add_argument('--de', default='Laysa',
                            help='Nome ou login atual da usuária a ser substituída (padrão: Laysa).')
        parser.add_argument('--login', default='Ellen.Costa',
                            help='Novo username/login (padrão: Ellen.Costa).')
        parser.add_argument('--nome', default='Ellen Costa',
                            help='Novo nome de exibição na board (padrão: Ellen Costa).')
        parser.add_argument('--first-name', default='Ellen', help='Novo first_name.')
        parser.add_argument('--last-name', default='Costa', help='Novo last_name.')
        parser.add_argument('--senha', default='ggs@2026',
                            help='Senha provisória temporária (padrão: ggs@2026).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostra o que seria alterado sem gravar nada.')

    def handle(self, *args, **opts):
        de       = opts['de'].strip()
        login    = opts['login'].strip()
        nome     = opts['nome'].strip()
        first    = opts['first_name'].strip()
        last     = opts['last_name'].strip()
        senha    = opts['senha']
        dry_run  = opts['dry_run']

        # ── Localiza o funcionário de saída (por nome de exibição ou por username) ──
        func = (FuncionarioAdministrativo.objects
                .select_related('usuario')
                .filter(Q(nome__iexact=de) | Q(usuario__username__iexact=de))
                .first())

        if func is None:
            # Talvez a substituição já tenha sido feita antes — verifica idempotência.
            ja_feito = (FuncionarioAdministrativo.objects
                        .filter(Q(nome__iexact=nome) | Q(usuario__username__iexact=login))
                        .first())
            if ja_feito:
                self.stdout.write(self.style.WARNING(
                    f'Nada a fazer: "{de}" não encontrada e "{nome}" ({ja_feito.usuario.username}) '
                    f'já existe. Substituição parece já concluída.'))
                return
            raise CommandError(
                f'Funcionária "{de}" não encontrada (nem por nome nem por login). '
                f'Confira o valor de --de. Funcionários existentes: '
                + ', '.join(FuncionarioAdministrativo.objects.values_list('nome', flat=True)))

        usuario = func.usuario

        # ── Proteção: o novo login não pode colidir com OUTRO usuário ──
        conflito = User.objects.filter(username__iexact=login).exclude(pk=usuario.pk).first()
        if conflito:
            raise CommandError(
                f'O login "{login}" já pertence a outro usuário (id={conflito.pk}). '
                f'Escolha outro --login para evitar duplicidade.')

        # ── Resumo do que será feito ──
        self.stdout.write('-' * 60)
        self.stdout.write(self.style.MIGRATE_HEADING('Substituição de usuária (cadastro existente)'))
        self.stdout.write(f'  Funcionário id .... {func.pk}   User id ... {usuario.pk}')
        self.stdout.write(f'  Login ............. {usuario.username!r}  ->  {login!r}')
        self.stdout.write(f'  Nome (board) ...... {func.nome!r}  ->  {nome!r}')
        self.stdout.write(f'  Nome completo ..... {usuario.get_full_name()!r}  ->  {(first + " " + last).strip()!r}')
        self.stdout.write(f'  Senha ............. provisória (troca obrigatória no 1º acesso)')
        self.stdout.write(f'  Perfil/ativo ...... {func.get_perfil_display()} / ativo={func.ativo} (mantidos)')
        self.stdout.write('-' * 60)

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN: nenhuma alteração foi gravada.'))
            return

        with transaction.atomic():
            usuario.username   = login
            usuario.first_name = first
            usuario.last_name  = last
            usuario.is_active  = True
            usuario.set_password(senha)
            usuario.save()

            func.nome              = nome
            func.senha_provisoria  = True
            func.senha_alterada_em = None
            func.ativo             = True
            func.save(update_fields=['nome', 'senha_provisoria', 'senha_alterada_em', 'ativo'])

        self.stdout.write(self.style.SUCCESS(
            f'[OK] Concluido. "{nome}" acessa com login "{login}" e a senha provisoria informada; '
            f'a troca será exigida no primeiro acesso. Histórico e vínculos preservados.'))
