from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator


# models.py
class Faculty(models.Model):
    """Факультет"""
    name = models.CharField('Название факультета', max_length=200)
    code = models.CharField('Код факультета', max_length=10, unique=True)
    description = models.TextField('Описание', blank=True)
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
        return self.name
    
    @property
    def groups_count(self):
        return self.group_set.count()
    
    @property 
    def students_count(self):
        return Student.objects.filter(group__faculty=self).count()
    
    @property
    def active_students_count(self):
        return Student.objects.filter(group__faculty=self, study_status='active').count()



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
    
    # Контактная информация
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Номер телефона должен быть в формате: '+999999999'. До 15 цифр."
    )
    phone = models.CharField('Телефон', validators=[phone_regex], max_length=17, blank=True)
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
        
        super().save(*args, **kwargs)
