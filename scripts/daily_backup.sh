#!/bin/bash
# scripts/daily_backup.sh
# Скрипт для ежедневного создания резервных копий

# ==============================================
# НАСТРОЙКИ - ИЗМЕНИТЕ ПОД СВОЙ ПРОЕКТ
# ==============================================

# Путь к директории проекта (ОБЯЗАТЕЛЬНО ИЗМЕНИТЕ!)
PROJECT_DIR="/Users/veseliy.hlebushek/student_journal"

# Путь к виртуальному окружению (если используется)
VENV_PATH="/Users/veseliy.hlebushek/student_journal/.venv"

# Количество дней для хранения бэкапов
DAYS_TO_KEEP=30

# ==============================================
# ОСНОВНОЙ СКРИПТ
# ==============================================

# Логирование
LOG_FILE="$PROJECT_DIR/logs/backup.log"
mkdir -p "$PROJECT_DIR/logs"

echo "========================================" >> $LOG_FILE
echo "Запуск ежедневного бэкапа: $(date)" >> $LOG_FILE

# Переход в директорию проекта
cd $PROJECT_DIR
if [ $? -ne 0 ]; then
    echo "ОШИБКА: Не удалось перейти в директорию проекта: $PROJECT_DIR" >> $LOG_FILE
    exit 1
fi

# Активация виртуального окружения (если есть)
if [ -d "$VENV_PATH" ]; then
    echo "Активация виртуального окружения..." >> $LOG_FILE
    source $VENV_PATH/bin/activate
    if [ $? -ne 0 ]; then
        echo "ОШИБКА: Не удалось активировать виртуальное окружение: $VENV_PATH" >> $LOG_FILE
        exit 1
    fi
fi

# Создание резервной копии
echo "Создание резервной копии..." >> $LOG_FILE
python manage.py create_backup --type=scheduled --description="Ежедневная автоматическая резервная копия"
if [ $? -eq 0 ]; then
    echo "Резервная копия создана успешно" >> $LOG_FILE
else
    echo "ОШИБКА: Не удалось создать резервную копию" >> $LOG_FILE
fi

# Очистка старых бэкапов
echo "Очистка старых резервных копий (старше $DAYS_TO_KEEP дней)..." >> $LOG_FILE
python manage.py cleanup_old_backups --days=$DAYS_TO_KEEP
if [ $? -eq 0 ]; then
    echo "Очистка завершена успешно" >> $LOG_FILE
else
    echo "ОШИБКА: Проблема при очистке старых бэкапов" >> $LOG_FILE
fi

# Проверка места на диске
echo "Проверка места на диске..." >> $LOG_FILE
df -h $PROJECT_DIR >> $LOG_FILE

echo "Завершение: $(date)" >> $LOG_FILE
echo "========================================" >> $LOG_FILE
