import os
import threading
import time
from datetime import datetime, time as time_cls
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone

from .activity import log_activity
from .models import Backup
from .services.backup_service import BackupService


_scheduler_started = False
_scheduler_lock = threading.Lock()


def _should_create_backup(now, target_time):
    """Возвращает True, если на текущий день ещё нет автоматической копии и время уже наступило."""
    today = now.date()
    has_backup = Backup.objects.filter(
        backup_type='automatic',
        created_at__date=today
    ).exists()

    if has_backup:
        return False

    return now >= target_time


def _scheduler_loop():
    interval = getattr(settings, 'AUTO_BACKUP_CHECK_INTERVAL', 1800)  # 30 минут
    backup_time_setting = getattr(settings, 'AUTO_BACKUP_TIME', '02:00')

    try:
        hour, minute = map(int, str(backup_time_setting).split(':'))
        backup_time = time_cls(hour=hour, minute=minute)
    except Exception:
        backup_time = time_cls(hour=2, minute=0)

    tz_name = getattr(settings, 'AUTO_BACKUP_TIMEZONE', getattr(settings, 'TIME_ZONE', 'Europe/Moscow'))
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = timezone.get_current_timezone()

    while True:
        try:
            now = timezone.now().astimezone(tz)
            target_dt = datetime.combine(now.date(), backup_time, tzinfo=tz)

            if _should_create_backup(now, target_dt):
                service = BackupService()
                backup = service.create_backup(
                    backup_type='automatic',
                    user=None,
                    description='Ежедневная автоматическая резервная копия'
                )
                if backup:
                    log_activity(
                        user=None,
                        action_type='create',
                        description=f'Создана автоматическая резервная копия \"{backup.name}\"',
                        icon='bi-hdd-stack',
                        metadata={'backup_id': backup.id, 'type': 'automatic'}
                    )
        except Exception as exc:
            print(f'[admin_panel] Ошибка при создании автоматической резервной копии: {exc}')
        finally:
            time.sleep(max(60, interval))


def start_backup_scheduler():
    global _scheduler_started

    if not getattr(settings, 'ENABLE_AUTO_DAILY_BACKUP', True):
        return

    with _scheduler_lock:
        if _scheduler_started:
            return

        # В бэкграунде могут быть тесты/скрипты; не запускаем в управляемых командах
        if os.environ.get('RUN_BACKUP_SCHEDULER') == '0':
            return

        thread = threading.Thread(target=_scheduler_loop, name='daily-backup-scheduler', daemon=True)
        thread.start()
        _scheduler_started = True
