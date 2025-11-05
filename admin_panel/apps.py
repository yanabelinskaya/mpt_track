from django.apps import AppConfig
from django.conf import settings
import os


class AdminPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_panel'

    def ready(self):
        # Избегаем двойного запуска при autoreload
        if settings.DEBUG and os.environ.get('RUN_MAIN') != 'true':
            return

        try:
            from .tasks import start_backup_scheduler
            start_backup_scheduler()
        except Exception as exc:
            # Логируем, но не мешаем запуску приложения
            print(f'[admin_panel] Не удалось запустить планировщик резервных копий: {exc}')
