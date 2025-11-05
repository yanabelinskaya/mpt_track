# admin_panel/services/backup_service.py

import os
import gzip
from gzip import BadGzipFile
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from admin_panel.models import Backup
import logging
from django.db import models


class BackupRestoreError(Exception):
    """Ошибка восстановления резервной копии."""
    pass

logger = logging.getLogger(__name__)

class BackupService:
    """Сервис для создания и управления резервными копиями"""
    
    def __init__(self):
        self.backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        self.command_timeout = getattr(settings, 'BACKUP_COMMAND_TIMEOUT', 600)
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
                success, error_message = self._create_postgresql_backup(db_config, backup_path)
            elif db_config['ENGINE'] == 'django.db.backends.sqlite3':
                success, error_message = self._create_sqlite_backup(db_config, backup_path)
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
                if os.path.exists(backup_path):
                    try:
                        os.remove(backup_path)
                    except OSError:
                        logger.warning(f"Не удалось удалить невалидный бэкап {backup_path}")
                backup.error_message = error_message or 'Ошибка при создании бэкапа'
                backup.save()
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при создании бэкапа: {str(e)}")
            backup.status = 'failed'
            backup.error_message = str(e)
            if backup.file_path and os.path.exists(backup.file_path):
                try:
                    os.remove(backup.file_path)
                except OSError:
                    logger.warning(f"Не удалось удалить проблемный бэкап {backup.file_path}")
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
                    text=True,
                    timeout=self.command_timeout
                )
            
            if process.returncode == 0:
                return True, None
            else:
                logger.error(f"pg_dump ошибка: {process.stderr}")
                return False, process.stderr
        except subprocess.TimeoutExpired:
            logger.error("pg_dump превышено время ожидания")
            return False, 'Время ожидания команды pg_dump истекло'
        except FileNotFoundError:
            error_message = 'pg_dump не установлен или недоступен в PATH'
            logger.error(f"pg_dump ошибка: {error_message}")
            return False, error_message
        except Exception as e:
            logger.error(f"Ошибка PostgreSQL бэкапа: {str(e)}")
            return False, str(e)
    
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
                    text=True,
                    timeout=self.command_timeout
                )
            
            if process.returncode == 0:
                return True, None
            else:
                logger.error(f"sqlite3 ошибка: {process.stderr}")
                return False, process.stderr
        except subprocess.TimeoutExpired:
            logger.error("sqlite3 превышено время ожидания")
            return False, 'Время ожидания команды sqlite3 истекло'
        except FileNotFoundError:
            error_message = 'sqlite3 не установлен или недоступен в PATH'
            logger.error(f"sqlite3 ошибка: {error_message}")
            return False, error_message
        except Exception as e:
            logger.error(f"Ошибка SQLite бэкапа: {str(e)}")
            return False, str(e)
    
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
    
    def restore_backup(self, backup_id):
        """Восстанавливает базу данных из выбранного бэкапа"""
        try:
            backup = Backup.objects.get(id=backup_id)
        except Backup.DoesNotExist:
            raise Backup.DoesNotExist("Резервная копия не найдена")
        
        if backup.status != 'completed':
            raise BackupRestoreError('Можно восстановить только завершенные бэкапы')
        
        if not backup.file_exists:
            raise FileNotFoundError('Файл резервной копии не найден на диске')
        
        temp_sql_path = None
        try:
            with tempfile.NamedTemporaryFile('wb', suffix='.sql', delete=False) as temp_file:
                try:
                    with gzip.open(backup.file_path, 'rb') as gz_file:
                        shutil.copyfileobj(gz_file, temp_file)
                except (OSError, BadGzipFile):
                    temp_file.seek(0)
                    temp_file.truncate()
                    with open(backup.file_path, 'rb') as raw_file:
                        shutil.copyfileobj(raw_file, temp_file)
                temp_sql_path = temp_file.name
            
            db_config = settings.DATABASES['default']
            connection.close()
            if db_config['ENGINE'] == 'django.db.backends.postgresql':
                success, error_output = self._restore_postgresql(db_config, temp_sql_path)
            elif db_config['ENGINE'] == 'django.db.backends.sqlite3':
                success, error_output = self._restore_sqlite(db_config, temp_sql_path)
            else:
                raise BackupRestoreError(f"Неподдерживаемая база данных: {db_config['ENGINE']}")
            
            if not success:
                raise BackupRestoreError(error_output or 'Ошибка при восстановлении резервной копии')
            
            logger.info(f"Бэкап успешно восстановлен: {backup.name}")
            return backup
        finally:
            if temp_sql_path and os.path.exists(temp_sql_path):
                try:
                    os.remove(temp_sql_path)
                except OSError:
                    logger.warning(f"Не удалось удалить временный файл {temp_sql_path}")
    
    def _restore_postgresql(self, db_config, sql_path):
        """Восстановление базы данных PostgreSQL из SQL файла"""
        env = os.environ.copy()
        if db_config.get('PASSWORD'):
            env['PGPASSWORD'] = db_config['PASSWORD']
        
        cmd = [
            'psql',
            f"--host={db_config.get('HOST', 'localhost')}",
            f"--port={db_config.get('PORT', '5432')}",
            f"--username={db_config['USER']}",
            f"--dbname={db_config['NAME']}",
            '-f', sql_path,
        ]
        
        try:
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                timeout=self.command_timeout
            )
        except FileNotFoundError:
            error_message = 'psql не установлен или недоступен в PATH'
            logger.error(f"psql restore ошибка: {error_message}")
            return False, error_message
        except subprocess.TimeoutExpired:
            logger.error("psql restore превышено время ожидания")
            return False, 'Время ожидания команды psql истекло'
        except Exception as exc:
            logger.error(f"psql restore исключение: {str(exc)}")
            return False, str(exc)
        
        if process.returncode == 0:
            return True, None
        
        logger.error(f"psql restore ошибка: {process.stderr}")
        return False, process.stderr
    
    def _restore_sqlite(self, db_config, sql_path):
        """Восстановление базы данных SQLite из SQL файла"""
        db_path = db_config['NAME']
        cmd = ['sqlite3', db_path]
        
        try:
            with open(sql_path, 'r', encoding='utf-8') as sql_file:
                process = subprocess.run(
                    cmd,
                    stdin=sql_file,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.command_timeout
                )
        except FileNotFoundError:
            error_message = 'sqlite3 не установлен или недоступен в PATH'
            logger.error(f"sqlite restore ошибка: {error_message}")
            return False, error_message
        except subprocess.TimeoutExpired:
            logger.error("sqlite restore превышено время ожидания")
            return False, 'Время ожидания команды sqlite3 истекло'
        except Exception as exc:
            logger.error(f"sqlite restore исключение: {str(exc)}")
            return False, str(exc)
        
        if process.returncode == 0:
            return True, None
        
        logger.error(f"sqlite3 restore ошибка: {process.stderr}")
        return False, process.stderr
    
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
    
    def expire_stale_backups(self, max_age_minutes=10):
        """Ставит зависшие бэкапы в корректный статус в зависимости от наличия файла"""
        cutoff = timezone.now() - timedelta(minutes=max_age_minutes)
        stale_backups = list(Backup.objects.filter(status='creating', created_at__lt=cutoff))
        if not stale_backups:
            return {'completed': 0, 'failed': 0}
        
        completed_ids = []
        failed_ids = []
        for backup in stale_backups:
            if backup.file_exists and os.path.getsize(backup.file_path) > 0:
                completed_ids.append(backup.id)
            else:
                failed_ids.append(backup.id)
        
        now = timezone.now()
        if completed_ids:
            for backup in Backup.objects.filter(id__in=completed_ids):
                try:
                    backup.file_size = os.path.getsize(backup.file_path)
                except OSError:
                    pass
                backup.status = 'completed'
                if not backup.completed_at:
                    backup.completed_at = now
                backup.error_message = ''
                backup.save(update_fields=['file_size', 'status', 'completed_at', 'error_message'])
            logger.info(f"Исправлено зависших бэкапов (completed): {len(completed_ids)}")
        
        if failed_ids:
            Backup.objects.filter(id__in=failed_ids).update(
                status='failed',
                error_message='Создание прервано: файл не найден',
                completed_at=now
            )
            logger.warning(f"Помечено зависших бэкапов (failed): {len(failed_ids)}")
        
        return {'completed': len(completed_ids), 'failed': len(failed_ids)}
    
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
