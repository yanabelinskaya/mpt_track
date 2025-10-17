# admin_panel/management/commands/cleanup_old_backups.py

from django.core.management.base import BaseCommand
from admin_panel.services.backup_service import BackupService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Очищает старые резервные копии'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Количество дней для хранения бэкапов (по умолчанию 30)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет удалено, но не удалять',
        )

    def handle(self, *args, **options):
        days_to_keep = options['days']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(f'ТЕСТОВЫЙ РЕЖИМ: Показываем что будет удалено (старше {days_to_keep} дней)...')
        else:
            self.stdout.write(f'Очистка резервных копий старше {days_to_keep} дней...')
        
        try:
            backup_service = BackupService()
            
            if dry_run:
                # В тестовом режиме только показываем
                from datetime import timedelta
                from django.utils import timezone
                from admin_panel.models import Backup
                
                cutoff_date = timezone.now() - timedelta(days=days_to_keep)
                old_backups = Backup.objects.filter(
                    created_at__lt=cutoff_date,
                    status='completed'
                )
                
                if old_backups.exists():
                    self.stdout.write(f'Будет удалено {old_backups.count()} резервных копий:')
                    for backup in old_backups:
                        self.stdout.write(f'  - {backup.name} ({backup.created_at.strftime("%d.%m.%Y %H:%M")})')
                else:
                    self.stdout.write('Старых резервных копий для удаления не найдено')
            else:
                # Реальное удаление
                deleted_count = backup_service.cleanup_old_backups(days_to_keep)
                
                if deleted_count > 0:
                    self.stdout.write(
                        self.style.SUCCESS(f'Удалено {deleted_count} старых резервных копий')
                    )
                else:
                    self.stdout.write('Старых резервных копий для удаления не найдено')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка: {str(e)}')
            )
