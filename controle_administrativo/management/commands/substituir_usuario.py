"""
Substitui, no cadastro existente, a usuaria de saida (padrao: Layza Rodrigues)
pela usuaria de entrada (padrao: Ellen Costa) — SPEC "Atualizacao de Usuario e Board".

A substituicao e feita SOBRE o mesmo registro (mesmo User + FuncionarioAdministrativo),
apenas trocando login, nome e senha. Assim, todo o historico e todos os vinculos
(tarefas, comentarios, execucoes, itens de bloco, tarefas da divisao) sao preservados
automaticamente, e as permissoes/grupos/roles da conta permanecem intactos.

A busca por --de IGNORA acento e ponto/underscore/espaco: "Layza.Rodrigues",
"Láyza Rodrigues" e "layza_rodrigues" encontram o mesmo registro. Casa por username
OU pelo nome de exibicao na board.

A nova senha e gravada como PROVISORIA: no primeiro acesso o painel obriga a troca
(FuncionarioAdministrativo.senha_provisoria=True). Idempotente e seguro — use
--dry-run para pre-visualizar sem gravar, e --listar para ver os cadastros.

Exemplos:
    python manage.py substituir_usuario --listar
    python manage.py substituir_usuario --dry-run
    python manage.py substituir_usuario
    python manage.py substituir_usuario --de "Layza.Rodrigues" --login Ellen.Costa --nome "Ellen Costa"
"""

import unicodedata

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction

from controle_administrativo.models import FuncionarioAdministrativo


def _norm(s):
    """Normaliza para comparar: sem acento, minusculo, ./_/espaco viram espaco."""
    if not s:
        return ''
    s = unicodedata.normalize('NFKD', str(s))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    for ch in '._-':
        s = s.replace(ch, ' ')
    return ' '.join(s.split())


def _ascii(s):
    """Versao ASCII para imprimir sem quebrar em consoles cp1252 (Windows)."""
    s = unicodedata.normalize('NFKD', str(s))
    return s.encode('ascii', 'replace').decode('ascii')


class Command(BaseCommand):
    help = 'Substitui a usuaria de saida (Layza Rodrigues) pela de entrada (Ellen Costa) no cadastro existente.'

    def add_arguments(self, parser):
        parser.add_argument('--de', default='Layza.Rodrigues',
                            help='Nome ou login atual da usuaria a substituir (padrao: Layza.Rodrigues). Ignora acento/pontuacao.')
        parser.add_argument('--login', default='Ellen.Costa',
                            help='Novo username/login (padrao: Ellen.Costa).')
        parser.add_argument('--nome', default='Ellen Costa',
                            help='Novo nome de exibicao na board (padrao: Ellen Costa).')
        parser.add_argument('--first-name', default='Ellen', help='Novo first_name.')
        parser.add_argument('--last-name', default='Costa', help='Novo last_name.')
        parser.add_argument('--senha', default='ggs@2026',
                            help='Senha provisoria temporaria (padrao: ggs@2026).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostra o que seria alterado sem gravar nada.')
        parser.add_argument('--listar', action='store_true',
                            help='Apenas lista os funcionarios (nome + login) e sai.')

    def _listar(self):
        self.stdout.write('-' * 60)
        self.stdout.write(self.style.MIGRATE_HEADING('Funcionarios cadastrados (nome  |  login)'))
        for f in FuncionarioAdministrativo.objects.select_related('usuario').order_by('nome'):
            uname = f.usuario.username if f.usuario_id else '(sem usuario)'
            self.stdout.write(f'  {_ascii(f.nome):<28} | {_ascii(uname)}')
        self.stdout.write('-' * 60)

    def handle(self, *args, **opts):
        if opts['listar']:
            self._listar()
            return

        de      = opts['de'].strip()
        login   = opts['login'].strip()
        nome    = opts['nome'].strip()
        first   = opts['first_name'].strip()
        last    = opts['last_name'].strip()
        senha   = opts['senha']
        dry_run = opts['dry_run']

        alvo = _norm(de)

        # ── Localiza o funcionario de saida (username OU nome), ignorando acento/pontuacao ──
        candidatos = [
            f for f in FuncionarioAdministrativo.objects.select_related('usuario')
            if _norm(f.nome) == alvo or (f.usuario_id and _norm(f.usuario.username) == alvo)
        ]

        if len(candidatos) > 1:
            achados = ', '.join(f'{_ascii(f.nome)} ({_ascii(f.usuario.username)})' for f in candidatos)
            raise CommandError(
                f'Mais de um funcionario casou com "{_ascii(de)}": {achados}. '
                f'Rode com --de exatamente igual ao login desejado.')

        func = candidatos[0] if candidatos else None

        if func is None:
            # Talvez a substituicao ja tenha sido feita antes — verifica idempotencia.
            ja_feito = next(
                (f for f in FuncionarioAdministrativo.objects.select_related('usuario')
                 if _norm(f.nome) == _norm(nome) or (f.usuario_id and _norm(f.usuario.username) == _norm(login))),
                None,
            )
            if ja_feito:
                self.stdout.write(self.style.WARNING(
                    f'Nada a fazer: "{_ascii(de)}" nao encontrada e "{_ascii(nome)}" '
                    f'({_ascii(ja_feito.usuario.username)}) ja existe. Substituicao ja concluida.'))
                return
            self.stderr.write(self.style.ERROR(
                f'Funcionaria "{_ascii(de)}" nao encontrada (nem por nome nem por login).'))
            self._listar()
            raise CommandError('Ajuste o valor de --de com base na lista acima (use --listar).')

        usuario = func.usuario

        # ── Protecao: o novo login nao pode colidir com OUTRO usuario ──
        conflito = User.objects.filter(username__iexact=login).exclude(pk=usuario.pk).first()
        if conflito:
            raise CommandError(
                f'O login "{login}" ja pertence a outro usuario (id={conflito.pk}). '
                f'Escolha outro --login para evitar duplicidade.')

        # ── Resumo do que sera feito (saida ASCII-safe) ──
        self.stdout.write('-' * 60)
        self.stdout.write(self.style.MIGRATE_HEADING('Substituicao de usuaria (cadastro existente)'))
        self.stdout.write(f'  Funcionario id .... {func.pk}   User id ... {usuario.pk}')
        self.stdout.write(f'  Login ............. {_ascii(usuario.username)!r}  ->  {_ascii(login)!r}')
        self.stdout.write(f'  Nome (board) ...... {_ascii(func.nome)!r}  ->  {_ascii(nome)!r}')
        self.stdout.write(f'  Nome completo ..... {_ascii(usuario.get_full_name())!r}  ->  {_ascii((first + " " + last).strip())!r}')
        self.stdout.write(f'  Senha ............. provisoria (troca obrigatoria no 1o acesso)')
        self.stdout.write(f'  Perfil/ativo ...... {func.get_perfil_display()} / ativo={func.ativo} (mantidos)')
        self.stdout.write(f'  Permissoes/grupos . preservados (mesmo User, so muda nome/login/senha)')
        self.stdout.write('-' * 60)

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN: nenhuma alteracao foi gravada.'))
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
            f'[OK] Concluido. "{_ascii(nome)}" acessa com login "{_ascii(login)}" e a senha provisoria; '
            f'a troca sera exigida no 1o acesso. Historico, permissoes e vinculos preservados.'))
