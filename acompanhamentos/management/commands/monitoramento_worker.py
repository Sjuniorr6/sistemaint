import os
import time
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from acompanhamentos.services.monitoramento_service import (
    processar_fotos_pendentes,
    processar_geofence,
)

try:
    import msvcrt
except ImportError:  # pragma: no cover - non-Windows fallback
    msvcrt = None

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


@contextmanager
def singleton_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = open(lock_path, 'a+')

    try:
        if msvcrt is not None:
            lock_file.seek(0)
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                lock_file.close()
                raise CommandError('Worker de monitoramento ja esta em execucao.') from exc
        elif fcntl is not None:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                lock_file.close()
                raise CommandError('Worker de monitoramento ja esta em execucao.') from exc
        else:
            raise CommandError('Nao foi possivel aplicar lock de instancia unica neste ambiente.')

        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(f'pid={os.getpid()}\nstarted_at={time.time()}\n')
        lock_file.flush()
        yield
    finally:
        try:
            if msvcrt is not None:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            elif fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


class Command(BaseCommand):
    help = 'Executa geofence e IA de fotos em backend, fora do navegador.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Executa apenas uma rodada e encerra.')
        parser.add_argument('--interval', type=int, default=10, help='Segundos entre rodadas.')
        parser.add_argument('--photo-limit', type=int, default=20, help='Quantidade maxima de fotos pendentes por rodada.')
        parser.add_argument('--mission-limit', type=int, default=500, help='Quantidade maxima de missoes ativas por rodada.')

    def handle(self, *args, **options):
        interval = max(1, int(options['interval']))
        photo_limit = max(1, int(options['photo_limit']))
        mission_limit = max(1, int(options['mission_limit']))
        lock_path = Path(settings.BASE_DIR) / 'cache' / 'monitoramento_worker.lock'

        with singleton_lock(lock_path):
            self.stdout.write(self.style.SUCCESS('Worker de monitoramento iniciado.'))
            if options['once']:
                summary = self.run_cycle(photo_limit=photo_limit, mission_limit=mission_limit)
                self.write_summary(summary)
                return

            while True:
                start = time.time()
                summary = self.run_cycle(photo_limit=photo_limit, mission_limit=mission_limit)
                self.write_summary(summary)
                elapsed = time.time() - start
                sleep_for = max(0, interval - elapsed)
                if sleep_for:
                    time.sleep(sleep_for)

    def run_cycle(self, photo_limit: int, mission_limit: int):
        summary = {
            'photos_found': 0,
            'photos_ok': 0,
            'photos_fail': 0,
            'missions_found': 0,
            'missions_checked': 0,
            'missions_changed': 0,
            'missions_fail': 0,
        }

        try:
            summary.update(self.process_pending_photos(photo_limit))
        except Exception as exc:
            summary['photos_fail'] += 1
            self.stderr.write(f'[worker] erro ao processar fotos: {exc}')

        try:
            summary.update(self.process_geofences(mission_limit))
        except Exception as exc:
            summary['missions_fail'] += 1
            self.stderr.write(f'[worker] erro ao processar geofence: {exc}')

        return summary

    def process_pending_photos(self, photo_limit: int):
        result = processar_fotos_pendentes(photo_limit=photo_limit)
        for failure in result.get('photo_failures', []):
            self.stderr.write(
                f"[worker] foto {failure.get('photo_id')} falhou ({failure.get('status_code')}): {failure.get('error')}"
            )

        return {
            'photos_found': result.get('photos_found', 0),
            'photos_ok': result.get('photos_ok', 0),
            'photos_fail': result.get('photos_fail', 0),
        }

    def process_geofences(self, mission_limit: int):
        result = processar_geofence(mission_limit=mission_limit)
        for failure in result.get('mission_failures', []):
            self.stderr.write(
                f"[worker] geofence {failure.get('mission_id')} falhou: {failure.get('error')}"
            )

        return {
            'missions_found': result.get('missions_found', 0),
            'missions_checked': result.get('missions_checked', 0),
            'missions_changed': result.get('missions_changed', 0),
            'missions_fail': result.get('missions_fail', 0),
        }

    def write_summary(self, summary):
        self.stdout.write(
            '[worker] fotos: '
            f"{summary['photos_ok']}/{summary['photos_found']} processadas, "
            f"{summary['photos_fail']} falha(s); "
            'geofence: '
            f"{summary['missions_checked']}/{summary['missions_found']} verificadas, "
            f"{summary['missions_changed']} com no_local, "
            f"{summary['missions_fail']} falha(s)."
        )
