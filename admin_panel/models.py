from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
import os
from datetime import date, datetime


class Subject(models.Model):
    """Учебный предмет"""
    name = models.CharField('Название', max_length=150, unique=True)
    short_name = models.CharField('Короткое название', max_length=50, blank=True)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_subjects',
        verbose_name='Создан пользователем'
    )

    class Meta:
        verbose_name = 'Предмет'
        verbose_name_plural = 'Предметы'
        ordering = ['name']

    def __str__(self):
        return self.short_name or self.name

    @property
    def assignments_count(self):
        return self.assignments.count()


class Faculty(models.Model):
    """Факультет (Специальность) - оставляем как есть"""
    name = models.CharField('Название специальности', max_length=200)
    
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
        verbose_name = 'Специальность'
        verbose_name_plural = 'Специальности'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    # МЕТОДЫ ДЛЯ РАБОТЫ С ПРОФЕССИЯМИ - оставляем как есть
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
    
    # ОБНОВЛЕННЫЕ МЕТОДЫ для новой структуры
    @property
    def groups_count(self):
        """Количество групп через профессии"""
        return Group.objects.filter(profession__in=self.get_professions_list(), 
                                   faculty=self).count()
    
    @property 
    def students_count(self):
        """Количество студентов через группы"""
        return Student.objects.filter(group__faculty=self).count()
    
    @property
    def active_students_count(self):
        """Количество активных студентов"""
        return Student.objects.filter(group__faculty=self, user__is_active=True).count()



class Group(models.Model):
    """Учебная группа - ОБНОВЛЕННАЯ МОДЕЛЬ"""
    
    STATUS_CHOICES = [
        ('studying', 'Учится'),
        ('graduated', 'Выпущена'),
        ('disbanded', 'Расформирована'),
    ]
    
    # Основные поля
    name = models.CharField('Название группы', max_length=50)  # оставляем для совместимости
    code = models.CharField('Код группы', max_length=20, unique=True)
    
    # Связи - ИЗМЕНЯЕМ СТРУКТУРУ
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, verbose_name='Специальность')
    profession = models.CharField('Профессия', max_length=150, help_text='Профессия в рамках специальности')
    
    # Временные поля - ОБНОВЛЯЕМ
    enrollment_date = models.DateField('Дата поступления', null=True, blank=True)
    graduation_date = models.DateField('Дата планируемого окончания', null=True, blank=True)
    
    # Статус
    is_active = models.BooleanField('Активная группа', default=True)
    
    # Служебные поля
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='created_groups', verbose_name='Создан пользователем')
    
    class Meta:
        verbose_name = 'Группа'
        verbose_name_plural = 'Группы'
        ordering = ['faculty', 'profession', 'code']
    
    def __str__(self):
        return f"{self.code} ({self.profession})"
    
    # АВТОМАТИЧЕСКИЕ РАСЧЕТЫ
    @property
    def current_course(self):
        """Автоматический расчет текущего курса"""
        if not self.enrollment_date:
            return 1
            
        current_date = date.today()
        years_passed = current_date.year - self.enrollment_date.year
        
        # Если еще не сентябрь текущего учебного года, курс меньше на 1
        if current_date.month < 9:
            years_passed -= 1
            
        course = max(years_passed + 1, 1)
        return min(course, 4)  # Максимум 4 курса
    
    @property
    def status(self):
        """Автоматический расчет статуса группы"""
        if not self.is_active:
            return 'disbanded'
        
        if self.current_course > 4:
            return 'graduated'
        
        return 'studying'
    
    @property
    def status_display(self):
        """Отображение статуса"""
        status_dict = {
            'studying': f'{self.current_course} курс',
            'graduated': 'Выпущена',
            'disbanded': 'Расформирована'
        }
        return status_dict.get(self.status, 'Неизвестно')
    
    @property
    def students_count(self):
        """Количество студентов в группе"""
        return self.students.count()
    
    @property
    def active_students_count(self):
        """Количество активных студентов"""
        return self.students.filter(study_status='active').count()
    
    # МЕТОДЫ ДЛЯ РАБОТЫ С ПРОФЕССИЯМИ
    def get_available_professions(self):
        """Возвращает доступные профессии для специальности"""
        return self.faculty.get_professions_list()
    
    def is_valid_profession(self):
        """Проверяет валидность выбранной профессии"""
        available = self.get_available_professions()
        return self.profession in available if available else True

    def save(self, *args, **kwargs):
        # Автоматически подставляем даты выпуска, если они не заполнены
        if self.enrollment_date and not self.graduation_date:
            self.graduation_date = self.enrollment_date.replace(
                year=self.enrollment_date.year + 4,
                month=6,
                day=30
            )

        # Для совместимости заполняем name, если пусто
        if not self.name:
            self.name = self.code

        super().save(*args, **kwargs)

    def clean(self):
        """Валидация модели"""
        if self.profession and not self.is_valid_profession():
            available = self.get_available_professions()
            if available:
                available_str = ', '.join(available)
                raise ValidationError({
                    'profession': (
                        f'Выбранная профессия недоступна для специальности "{self.faculty.name}". '
                        f'Доступные профессии: {available_str}'
                    )
                })


class SubjectAssignment(models.Model):
    """Связь предмета с курсом и специальностью"""

    COURSE_CHOICES = [(i, f'{i} курс') for i in range(1, 5)]

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='Предмет'
    )
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.CASCADE,
        related_name='subject_assignments',
        verbose_name='Специальность'
    )
    profession = models.CharField('Профессия', max_length=150)
    course = models.PositiveSmallIntegerField('Курс', choices=COURSE_CHOICES)
    teachers = models.ManyToManyField(
        'Teacher',
        blank=True,
        related_name='subject_assignments',
        verbose_name='Преподаватели'
    )
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_subject_assignments',
        verbose_name='Создан пользователем'
    )

    class Meta:
        verbose_name = 'Предмет по курсу'
        verbose_name_plural = 'Предметы по курсам'
        ordering = ['faculty__name', 'profession', 'course', 'subject__name']
        unique_together = ('subject', 'faculty', 'profession', 'course')

    def __str__(self):
        return f'{self.subject} — {self.faculty.name} / {self.profession} / {self.get_course_display()}'

    def clean(self):
        profession = (self.profession or '').strip()
        if self.faculty_id:
            professions = self.faculty.get_professions_list()
            if professions and profession not in professions:
                raise ValidationError({'profession': 'Профессия не относится к выбранной специальности'})
        self.profession = profession

    def save(self, *args, **kwargs):
        self.profession = (self.profession or '').strip()
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def course_number(self):
        return int(self.course)



class Student(models.Model):
    """Студент - ДОБАВЛЯЕМ СВЯЗЬ С НОВОЙ ГРУППОЙ"""
    
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
    
    # Учебная информация - ОБНОВЛЯЕМ
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, 
                             verbose_name='Группа', related_name='students')
    
    # УБИРАЕМ ДУБЛИРУЮЩИЕ ПОЛЯ (course берем из группы)
    # course = models.IntegerField... - удаляем, берем из group.current_course
    
    # УБИРАЕМ profession - берем из группы
    # profession = models.CharField... - удаляем, берем из group.profession
    
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
    
    # СВОЙСТВА ДЛЯ ПОЛУЧЕНИЯ ДАННЫХ ИЗ ГРУППЫ
    @property
    def course(self):
        """Курс студента (из группы)"""
        return self.group.current_course if self.group else None
    
    def get_course_display(self):
        """Отображение курса"""
        course = self.course
        if course:
            return f"{course} курс"
        return "Не определен"
    
    @property
    def profession(self):
        """Профессия студента (из группы)"""
        return self.group.profession if self.group else None
    
    def get_profession_display(self):
        """Возвращает название профессии для отображения"""
        return self.profession if self.profession else 'Не определена'
    
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
    
    def save(self, *args, **kwargs):
    # Автогенерация студенческого билета если не указан
        if not self.student_id:
            year = datetime.now().year
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
        
        # ИСПРАВЛЯЕМ: Синхронизируем даты с группой всегда, если группа изменилась
        if self.group:
            # Проверяем, изменилась ли группа
            group_changed = False
            if self.pk:  # Если студент уже существует
                try:
                    old_student = Student.objects.get(pk=self.pk)
                    group_changed = (old_student.group != self.group)
                except Student.DoesNotExist:
                    group_changed = True
            else:
                # Новый студент
                group_changed = True
            
            # Обновляем даты если группа изменилась или даты не заданы
            if group_changed or not self.enrollment_date:
                self.enrollment_date = self.group.enrollment_date
            
            if group_changed or not self.graduation_date:
                self.graduation_date = self.group.graduation_date
        
        super().save(*args, **kwargs)




class Teacher(models.Model):
    """Преподаватель"""
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teacher_profile',
        verbose_name='Пользователь'
    )
    first_name = models.CharField('Имя', max_length=50)
    last_name = models.CharField('Фамилия', max_length=50)
    middle_name = models.CharField('Отчество', max_length=50, blank=True)
    email = models.EmailField('Email', unique=True)
    phone = models.CharField('Телефон', max_length=20, blank=True)
    position = models.CharField('Должность', max_length=150, blank=True)
    academic_title = models.CharField('Ученое звание', max_length=150, blank=True)
    academic_degree = models.CharField('Ученая степень', max_length=150, blank=True)
    hire_date = models.DateField('Дата приема', null=True, blank=True)
    is_curator = models.BooleanField('Куратор', default=False)
    is_active = models.BooleanField('Активен', default=True)
    subjects = models.ManyToManyField(
        Subject,
        blank=True,
        related_name='teachers',
        verbose_name='Предметы'
    )
    groups = models.ManyToManyField(
        'Group',
        blank=True,
        related_name='teachers',
        verbose_name='Группы'
    )
    notes = models.TextField('Заметки', blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_teachers',
        verbose_name='Создан пользователем'
    )

    class Meta:
        verbose_name = 'Преподаватель'
        verbose_name_plural = 'Преподаватели'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return self.get_full_name()

    def get_full_name(self):
        if self.middle_name:
            return f"{self.last_name} {self.first_name} {self.middle_name}"
        return f"{self.last_name} {self.first_name}"

    def get_short_name(self):
        if self.middle_name:
            return f"{self.last_name} {self.first_name[0]}.{self.middle_name[0]}."
        return f"{self.last_name} {self.first_name[0]}."

    @property
    def has_system_access(self):
        return self.user is not None

    @property
    def is_active_account(self):
        return self.user.is_active if self.user else False

    @property
    def username(self):
        return self.user.username if self.user else None

    @property
    def last_login(self):
        return self.user.last_login if self.user else None

    @property
    def subjects_display(self):
        return ', '.join(
            subject.short_name or subject.name for subject in self.subjects.all()
        )

    @property
    def faculties(self):
        faculty_ids = self.groups.values_list('faculty_id', flat=True)
        return Faculty.objects.filter(id__in=faculty_ids).distinct()

    @property
    def professions(self):
        return self.groups.values_list('profession', flat=True).distinct()

    @property
    def teaching_subjects(self):
        return self.subjects.all()

    @property
    def curated_groups(self):
        return self.groups.all()


class Backup(models.Model):
    """Модель для хранения информации о резервных копиях - оставляем как есть"""
    
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
