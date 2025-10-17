# admin_panel/services/backup_service.py

import os
import gzip
import json
import subprocess
from datetime import datetime, timedelta
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from admin_panel.models import Backup
import logging
from django.db import models

logger = logging.getLogger(__name__)

class BackupService:
    """Сервис для создания и управления резервными копиями"""
    
    def __init__(self):
        self.backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        self.ensure_backup_directory()
    
    def ensure_backup_directory(self):
        """Создает директорию для бэкапов если её нет"""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
            logger.info(f"Создана директория для бэкапов: {self.backup_dir}")
    
    def create_backup(self, backup_type='manual', user=None, description=''):
        """Создает резервную копию базы данных"""
        
        # Создаем запись о бэкапе
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{timestamp}.sql.gz"
        
        backup = Backup.objects.create(
            name=backup_name,
            backup_type=backup_type,
            status='creating',
            created_by=user,
            description=description
        )
        
        try:
            logger.info(f"Начинаем создание бэкапа: {backup_name}")
            
            # Путь к файлу бэкапа
            backup_path = os.path.join(self.backup_dir, backup_name)
            backup.file_path = backup_path
            backup.save()
            
            # Получаем информацию о базе данных
            db_config = settings.DATABASES['default']
            
            if db_config['ENGINE'] == 'django.db.backends.postgresql':
                success = self._create_postgresql_backup(db_config, backup_path)
            elif db_config['ENGINE'] == 'django.db.backends.sqlite3':
                success = self._create_sqlite_backup(db_config, backup_path)
            else:
                raise Exception(f"Неподдерживаемая база данных: {db_config['ENGINE']}")
            
            if success:
                # Получаем размер файла
                if os.path.exists(backup_path):
                    backup.file_size = os.path.getsize(backup_path)
                
                # Получаем статистику
                stats = self._get_database_stats()
                backup.tables_count = stats['tables_count']
                backup.records_count = stats['records_count']
                
                # Завершаем успешно
                backup.status = 'completed'
                backup.completed_at = timezone.now()
                backup.save()
                
                logger.info(f"Бэкап создан успешно: {backup_name} ({backup.file_size_mb} МБ)")
                return backup
            else:
                backup.status = 'failed'
                backup.error_message = 'Ошибка при создании бэкапа'
                backup.save()
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при создании бэкапа: {str(e)}")
            backup.status = 'failed'
            backup.error_message = str(e)
            backup.save()
            return None
    
    def _create_postgresql_backup(self, db_config, backup_path):
        """Создает бэкап для PostgreSQL"""
        try:
            cmd = [
                'pg_dump',
                f"--host={db_config.get('HOST', 'localhost')}",
                f"--port={db_config.get('PORT', '5432')}",
                f"--username={db_config['USER']}",
                f"--dbname={db_config['NAME']}",
                '--verbose',
                '--clean',
                '--no-owner',
                '--no-privileges'
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['PASSWORD']
            
            # Выполняем pg_dump и сжимаем
            with gzip.open(backup_path, 'wt') as f:
                process = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True
                )
            
            if process.returncode == 0:
                return True
            else:
                logger.error(f"pg_dump ошибка: {process.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка PostgreSQL бэкапа: {str(e)}")
            return False
    
    def _create_sqlite_backup(self, db_config, backup_path):
        """Создает бэкап для SQLite"""
        try:
            db_path = db_config['NAME']
            
            # Используем sqlite3 .dump команду
            cmd = ['sqlite3', db_path, '.dump']
            
            with gzip.open(backup_path, 'wt') as f:
                process = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            if process.returncode == 0:
                return True
            else:
                logger.error(f"sqlite3 ошибка: {process.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка SQLite бэкапа: {str(e)}")
            return False
    
    def _get_database_stats(self):
        """Получает статистику базы данных"""
        try:
            with connection.cursor() as cursor:
                # Получаем список таблиц
                if connection.vendor == 'postgresql':
                    cursor.execute("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    """)
                elif connection.vendor == 'sqlite':
                    cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    """)
                else:
                    return {'tables_count': 0, 'records_count': 0}
                
                tables = [row[0] for row in cursor.fetchall()]
                
                # Подсчитываем записи
                total_records = 0
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        total_records += count
                    except:
                        continue
                
                return {
                    'tables_count': len(tables),
                    'records_count': total_records
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {str(e)}")
            return {'tables_count': 0, 'records_count': 0}
    
    def delete_backup(self, backup_id):
        """Удаляет резервную копию"""
        try:
            backup = Backup.objects.get(id=backup_id)
            
            # Удаляем файл
            if backup.file_path and os.path.exists(backup.file_path):
                os.remove(backup.file_path)
                logger.info(f"Файл бэкапа удален: {backup.file_path}")
            
            # Обновляем статус
            backup.status = 'deleted'
            backup.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления бэкапа: {str(e)}")
            return False
    
    def cleanup_old_backups(self, days_to_keep=30):
        """Удаляет старые бэкапы"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days_to_keep)
            
            old_backups = Backup.objects.filter(
                created_at__lt=cutoff_date,
                status='completed'
            )
            
            deleted_count = 0
            for backup in old_backups:
                if self.delete_backup(backup.id):
                    deleted_count += 1
            
            logger.info(f"Удалено старых бэкапов: {deleted_count}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {str(e)}")
            return 0
    
    def get_backup_statistics(self):
        """Возвращает статистику по бэкапам"""
        try:
            total_backups = Backup.objects.count()
            completed_backups = Backup.objects.filter(status='completed').count()
            failed_backups = Backup.objects.filter(status='failed').count()
            
            # Размер всех бэкапов
            total_size = Backup.objects.filter(status='completed').aggregate(
                total=models.Sum('file_size')
            )['total'] or 0
            
            # Последний бэкап
            last_backup = Backup.objects.filter(status='completed').first()
            
            return {
                'total_backups': total_backups,
                'completed_backups': completed_backups,
                'failed_backups': failed_backups,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'last_backup': last_backup,
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {str(e)}")
            return {}
