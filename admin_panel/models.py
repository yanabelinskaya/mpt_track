from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
import os


class Faculty(models.Model):
    """Факультет"""
    name = models.CharField('Название факультета', max_length=200)
    
    # Изменяем поле code для формата специальности
    code_validator = RegexValidator(
        regex=r'^\d{2}\.\d{2}\.\d{2}$',
        message="Код должен быть в формате XX.XX.XX (например: 09.02.07)"
    )
    code = models.CharField(
        'Код специальности', 
        max_length=8, 
        unique=True,
        validators=[code_validator],
        help_text="Код специальности в формате XX.XX.XX (например: 09.02.07)"
    )
    
    description = models.TextField('Описание', blank=True)
    
    # ДОБАВЛЯЕМ ПОЛЕ ДЛЯ ПРОФЕССИЙ
    professions = models.JSONField(
        'Профессии',
        default=list,
        blank=True,
        help_text="Список профессий для данной специальности"
    )
    
    is_active = models.BooleanField('Активный', default=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='created_faculties', verbose_name='Создан пользователем')
    
    class Meta:
        verbose_name = 'Факультет'
        verbose_name_plural = 'Факультеты'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    # МЕТОДЫ ДЛЯ РАБОТЫ С ПРОФЕССИЯМИ
    def get_professions_list(self):
        """Возвращает список названий профессий"""
        if not self.professions:
            return []
        # Если профессии хранятся как простые строки
        if isinstance(self.professions[0], str):
            return self.professions
        # Если профессии хранятся как объекты (для будущего расширения)
        return [prof if isinstance(prof, str) else prof.get('name', '') for prof in self.professions]
    
    def get_professions_display(self):
        """Возвращает строку профессий через запятую для отображения"""
        professions = self.get_professions_list()
        return ', '.join(professions) if professions else 'Не указаны'
    
    def get_professions_count(self):
        """Возвращает количество профессий"""
        return len(self.get_professions_list())
    
    def add_profession(self, name):
        """Добавляет профессию (только название)"""
        if not self.professions:
            self.professions = []
        
        profession_name = name.strip()
        
        # Проверяем, что такой профессии еще нет (регистронезависимо)
        existing_names = [p.lower() for p in self.get_professions_list()]
        if profession_name.lower() not in existing_names and profession_name:
            self.professions.append(profession_name)
            return True
        return False
    
    def remove_profession(self, name):
        """Удаляет профессию по названию"""
        if not self.professions:
            return False
        
        original_count = len(self.professions)
        self.professions = [p for p in self.professions if p.lower() != name.lower()]
        return len(self.professions) < original_count
    
    def set_professions_from_text(self, text):
        """Устанавливает профессии из текста (каждая профессия с новой строки)"""
        if not text or not text.strip():
            self.professions = []
            return []
        
        # Разбиваем по строкам и очищаем
        lines = text.strip().split('\n')
        professions = []
        
        for line in lines:
            profession_name = line.strip()
            if profession_name and len(profession_name) >= 2:
                # Проверяем на дубликаты (регистронезависимо)
                existing_names = [p.lower() for p in professions]
                if profession_name.lower() not in existing_names:
                    professions.append(profession_name)
        
        self.professions = professions
        return professions
    
    def get_professions_as_text(self):
        """Возвращает профессии как текст (каждая с новой строки) для форм"""
        professions = self.get_professions_list()
        return '\n'.join(professions) if professions else ''
    
    # СУЩЕСТВУЮЩИЕ МЕТОДЫ
    @property
    def groups_count(self):
        return self.group_set.count()
    
    @property 
    def students_count(self):
        return Student.objects.filter(group__faculty=self).count()
    
    @property
    def active_students_count(self):
        return Student.objects.filter(group__faculty=self, user__is_active=True).count()





class Group(models.Model):
    """Учебная группа"""
    name = models.CharField('Название группы', max_length=50)
    code = models.CharField('Код группы', max_length=20, unique=True, default='TEMP')
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, verbose_name='Факультет')
    course = models.IntegerField('Курс', choices=[
        (1, '1 курс'),
        (2, '2 курс'),
        (3, '3 курс'),
        (4, '4 курс'),
        (5, '5 курс'),
    ])
    year_start = models.IntegerField('Год поступления')
    is_active = models.BooleanField('Активная группа', default=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Группа'
        verbose_name_plural = 'Группы'
        ordering = ['faculty', 'course', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.faculty.code})"
    
    @property
    def students_count(self):
        return self.students.count()


class Student(models.Model):
    """Студент"""
    # ИЗМЕНЕНО: Связь с пользователем теперь опциональна
    user = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Пользователь',
        related_name='student_profile'
    )
    
    # Основная информация
    student_id = models.CharField('Студенческий билет', max_length=20, unique=True, blank=True)
    first_name = models.CharField('Имя', max_length=50)
    last_name = models.CharField('Фамилия', max_length=50)
    middle_name = models.CharField('Отчество', max_length=50, blank=True)
    
    # Учебная информация
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, 
                             verbose_name='Группа', related_name='students')
    course = models.IntegerField('Курс', choices=[
        (1, '1 курс'),
        (2, '2 курс'),
        (3, '3 курс'),
        (4, '4 курс'),
        (5, '5 курс'),
    ], default=1)
    
    # ДОБАВЛЯЕМ ПОЛЕ ПРОФЕССИИ
    profession = models.CharField(
        'Профессия',
        max_length=150,
        blank=True,
        null=True,
        help_text='Выбранная профессия в рамках специальности'
    )
    
    # Контактная информация
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,20}$',
        message="Номер телефона должен быть в формате: '+999999999'. До 20 цифр."
    )
    phone = models.CharField('Телефон', validators=[phone_regex], max_length=20, blank=True)
    email = models.EmailField('Email')  # ИЗМЕНЕНО: сделали обязательным
    
    # Персональная информация
    date_of_birth = models.DateField('Дата рождения', null=True, blank=True)
    GENDER_CHOICES = [
        ('M', 'Мужской'),
        ('F', 'Женский'),
    ]
    gender = models.CharField('Пол', max_length=1, choices=GENDER_CHOICES, blank=True)
    
    # Адрес
    address = models.TextField('Адрес проживания', blank=True)
    city = models.CharField('Город', max_length=100, blank=True)
    
    # Академическая информация
    enrollment_date = models.DateField('Дата поступления', null=True, blank=True)
    graduation_date = models.DateField('Дата выпуска', null=True, blank=True)
    
    # Статусы
    STUDY_STATUS_CHOICES = [
        ('active', 'Обучается'),
        ('academic_leave', 'Академический отпуск'),
        ('expelled', 'Отчислен'),
        ('graduated', 'Выпускник'),
        ('transferred', 'Переведен'),
    ]
    study_status = models.CharField('Статус обучения', max_length=20, 
                                   choices=STUDY_STATUS_CHOICES, default='active')
    
    # Дополнительная информация
    notes = models.TextField('Заметки', blank=True)
    
    # Служебные поля
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='created_students', verbose_name='Создан пользователем')
    
    class Meta:
        verbose_name = 'Студент'
        verbose_name_plural = 'Студенты'
        ordering = ['last_name', 'first_name']
    
    def __str__(self):
        return self.get_full_name()
    
    def get_full_name(self):
        """Полное имя студента"""
        if self.middle_name:
            return f"{self.last_name} {self.first_name} {self.middle_name}"
        return f"{self.last_name} {self.first_name}"
    
    def get_short_name(self):
        """Короткое имя студента"""
        if self.middle_name:
            return f"{self.last_name} {self.first_name[0]}.{self.middle_name[0]}."
        return f"{self.last_name} {self.first_name[0]}."
    
    # МЕТОДЫ ДЛЯ РАБОТЫ С ПРОФЕССИЯМИ
    def get_available_professions(self):
        """Возвращает список доступных профессий из специальности"""
        if self.group and self.group.faculty:
            return self.group.faculty.get_professions_list()
        return []
    
    def is_valid_profession(self):
        """Проверяет, что выбранная профессия доступна для специальности"""
        if not self.profession:
            return True  # Профессия не обязательна
        
        available_professions = self.get_available_professions()
        if not available_professions:
            return True  # Если в специальности нет профессий, любая подходит
        
        return self.profession in available_professions
    
    def get_profession_display(self):
        """Возвращает название профессии для отображения"""
        return self.profession if self.profession else 'Не выбрана'
    
    # НОВЫЕ МЕТОДЫ для управления доступом
    def has_system_access(self):
        """Проверяет, есть ли у студента доступ к системе"""
        return hasattr(self, 'user') and self.user is not None
    
    @property
    def is_active_account(self):
        """Проверяет активность аккаунта студента"""
        if self.has_system_access():
            return self.user.is_active
        return False
    
    @property
    def username(self):
        """Возвращает логин студента"""
        if self.has_system_access():
            return self.user.username
        return None
    
    @property
    def last_login(self):
        """Возвращает дату последнего входа"""
        if self.has_system_access():
            return self.user.last_login
        return None
    
    @property
    def age(self):
        """Возраст студента"""
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    # ДОПОЛНИТЕЛЬНЫЕ СВОЙСТВА ДЛЯ ИНФОРМАЦИИ О СПЕЦИАЛЬНОСТИ
    @property
    def faculty(self):
        """Возвращает факультет (специальность) студента"""
        if self.group:
            return self.group.faculty
        return None
    
    @property
    def faculty_name(self):
        """Возвращает название специальности"""
        if self.faculty:
            return self.faculty.name
        return 'Не указана'
    
    @property
    def faculty_code(self):
        """Возвращает код специальности"""
        if self.faculty:
            return self.faculty.code
        return 'Не указан'
    
    def clean(self):
        """Валидация модели"""
        from django.core.exceptions import ValidationError
        
        # Проверяем, что профессия доступна для специальности
        if self.profession and not self.is_valid_profession():
            available = self.get_available_professions()
            if available:
                available_str = ', '.join(available)
                raise ValidationError({
                    'profession': f'Выбранная профессия недоступна для специальности "{self.faculty_name}". '
                                f'Доступные профессии: {available_str}'
                })
    
    def save(self, *args, **kwargs):
        # Автогенерация студенческого билета если не указан
        if not self.student_id:
            import datetime
            year = datetime.datetime.now().year
            # Находим максимальный номер для текущего года
            last_student = Student.objects.filter(
                student_id__startswith=f"MPT{year}"
            ).order_by('-student_id').first()
            
            if last_student:
                last_number = int(last_student.student_id[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
            
            self.student_id = f"MPT{year}{new_number:04d}"
        
        # Вызываем clean для валидации
        self.full_clean()
        
        super().save(*args, **kwargs)


# admin_panel/models.py - добавьте в конец файла
class Backup(models.Model):
    """Модель для хранения информации о резервных копиях"""
    
    BACKUP_TYPE_CHOICES = [
        ('manual', 'Ручная'),
        ('automatic', 'Автоматическая'),
        ('scheduled', 'По расписанию'),
    ]
    
    BACKUP_STATUS_CHOICES = [
        ('creating', 'Создается'),
        ('completed', 'Завершена'),
        ('failed', 'Ошибка'),
        ('deleted', 'Удалена'),
    ]
    
    name = models.CharField('Название', max_length=200)
    file_path = models.CharField('Путь к файлу', max_length=500)
    file_size = models.BigIntegerField('Размер файла (байт)', default=0)
    backup_type = models.CharField('Тип', max_length=20, choices=BACKUP_TYPE_CHOICES, default='manual')
    status = models.CharField('Статус', max_length=20, choices=BACKUP_STATUS_CHOICES, default='creating')
    
    # Информация о содержимом
    tables_count = models.IntegerField('Количество таблиц', default=0)
    records_count = models.BigIntegerField('Количество записей', default=0)
    
    # Временные метки
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    completed_at = models.DateTimeField('Дата завершения', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Создан пользователем')
    
    # Дополнительная информация
    description = models.TextField('Описание', blank=True)
    error_message = models.TextField('Сообщение об ошибке', blank=True)

    class Meta:
        verbose_name = 'Резервная копия'
        verbose_name_plural = 'Резервные копии'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def file_size_mb(self):
        """Размер файла в МБ"""
        return round(self.file_size / (1024 * 1024), 2)
    
    @property
    def file_exists(self):
        """Проверяет, существует ли файл"""
        return os.path.exists(self.file_path) if self.file_path else False
    
    @property
    def duration(self):
        """Время создания бэкапа"""
        if self.completed_at and self.created_at:
            delta = self.completed_at - self.created_at
            return delta.total_seconds()
        return None
    
    def get_backup_info(self):
        """Возвращает информацию о бэкапе"""
        info = {
            'name': self.name,
            'size_mb': self.file_size_mb,
            'type': self.get_backup_type_display(),
            'status': self.get_status_display(),
            'created': self.created_at,
            'duration': self.duration,
            'tables': self.tables_count,
            'records': self.records_count,
        }
        return info

