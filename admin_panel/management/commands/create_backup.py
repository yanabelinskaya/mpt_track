# admin_panel/management/commands/create_backup.py

from django.core.management.base import BaseCommand
from admin_panel.services.backup_service import BackupService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Создает резервную копию базы данных'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='automatic',
            help='Тип бэкапа (manual, automatic, scheduled)',
        )
        parser.add_argument(
            '--description',
            type=str,
            default='',
            help='Описание бэкапа',
        )

    def handle(self, *args, **options):
        backup_type = options['type']
        description = options['description']
        
        self.stdout.write(f'Создание резервной копии (тип: {backup_type})...')
        
        try:
            backup_service = BackupService()
            backup = backup_service.create_backup(
                backup_type=backup_type,
                description=description or f'Автоматическая резервная копия'
            )
            
            if backup:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Резервная копия создана успешно: {backup.name} ({backup.file_size_mb} МБ)'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Ошибка при создании резервной копии')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка: {str(e)}')
            )
