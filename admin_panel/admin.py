from django.contrib import admin
from .models import Faculty, Group, Student, Subject, Teacher, SubjectAssignment, PasswordResetRequest
from admin_panel.models import Backup


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    # Нет 'course' и 'year_start' в модели — используем вычисляемые колонки
    ordering = ('faculty', 'profession', 'code')
    list_display = (
        'code',
        'faculty',
        'profession',
        'current_course_display',
        'enrollment_year',
        'is_active',
        'students_count_display',
        'status_display_admin',
    )
    list_filter = ('faculty', 'profession', 'is_active')
    search_fields = ('code', 'profession', 'faculty__name')

    # вычисляемые колонки
    def current_course_display(self, obj):
        return obj.current_course
    current_course_display.short_description = 'Курс'

    def enrollment_year(self, obj):
        return obj.enrollment_date.year if obj.enrollment_date else '-'
    enrollment_year.short_description = 'Год поступления'

    def students_count_display(self, obj):
        return obj.students.count()
    students_count_display.short_description = 'Студентов'

    def status_display_admin(self, obj):
        return obj.status_display
    status_display_admin.short_description = 'Статус'


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        'student_id',
        'get_full_name',
        'email',
        'group',
        'course_display',          # заменяем прямое поле course на вычисляемую колонку
        'study_status',
        'has_system_access_display',
        'is_active_display',
    ]
    # убираем несуществующее поле 'course' из фильтров
    list_filter = [
        'study_status',
        'group__faculty',
        'group__profession',
        'created_at',
    ]
    search_fields = [
        'first_name',
        'last_name',
        'middle_name',
        'email',
        'student_id',
        'user__username',
    ]
    ordering = ['last_name', 'first_name']

    fieldsets = (
        ('Основная информация', {
            'fields': ('first_name', 'last_name', 'middle_name', 'student_id')
        }),
        ('Учебная информация', {
            # убираем несуществующее поле 'course' из формы
            'fields': ('group', 'study_status', 'enrollment_date', 'graduation_date')
        }),
        ('Контактная информация', {
            'fields': ('email', 'phone', 'address', 'city')
        }),
        ('Персональная информация', {
            'fields': ('date_of_birth', 'gender')
        }),
        ('Система доступа', {
            'fields': ('user',),
            'classes': ('collapse',)
        }),
        ('Дополнительно', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    # вычисляемая колонка курса студента
    def course_display(self, obj):
        return obj.course or '-'
    course_display.short_description = 'Курс'

    # НОВЫЕ МЕТОДЫ для отображения статусов
    def has_system_access_display(self, obj):
        """Отображение наличия доступа к системе"""
        return obj.has_system_access()
    has_system_access_display.short_description = 'Доступ к системе'
    has_system_access_display.boolean = True

    def is_active_display(self, obj):
        """Отображение активности аккаунта"""
        if obj.has_system_access():
            return obj.is_active_account
        return False
    is_active_display.short_description = 'Активен'
    is_active_display.boolean = True

    # Действия для массовых операций
    actions = ['activate_students', 'deactivate_students', 'create_system_access']

    def activate_students(self, request, queryset):
        """Активировать выбранных студентов"""
        count = 0
        for student in queryset:
            if student.has_system_access():
                student.user.is_active = True
                student.user.save()
                count += 1
        self.message_user(request, f'Активированы аккаунты {count} студентов.')
    activate_students.short_description = "Активировать аккаунты"

    def deactivate_students(self, request, queryset):
        """Деактивировать выбранных студентов"""
        count = 0
        for student in queryset:
            if student.has_system_access():
                student.user.is_active = False
                student.user.save()
                count += 1
        self.message_user(request, f'Деактивированы аккаунты {count} студентов.')
    deactivate_students.short_description = "Деактивировать аккаунты"

    def create_system_access(self, request, queryset):
        """Создать доступ к системе для выбранных студентов"""
        from django.contrib.auth.models import User
        import secrets
        import string

        def generate_username(first_name, last_name):
            transliteration = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
            }
            def translit(text):
                return ''.join(transliteration.get(char.lower(), char.lower()) for char in text)
            base = f"{translit(last_name)}.{translit(first_name)}"
            username = base
            i = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{i}"
                i += 1
            return username

        def generate_password(length=10):
            characters = string.ascii_letters + string.digits
            return ''.join(secrets.choice(characters) for _ in range(length))

        created = 0
        for student in queryset:
            if not student.has_system_access():
                try:
                    username = generate_username(student.first_name, student.last_name)
                    password = generate_password()
                    user = User.objects.create_user(
                        username=username,
                        email=student.email,
                        password=password,
                        first_name=student.first_name,
                        last_name=student.last_name,
                        is_active=True,
                    )
                    student.user = user
                    student.save()
                    created += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f'Ошибка при создании доступа для {student.get_full_name()}: {e}',
                        level='ERROR'
                    )
        self.message_user(request, f'Создан доступ для {created} студентов.')
    create_system_access.short_description = "Создать доступ к системе"


@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = ('email', 'role', 'status', 'target_display', 'created_at', 'processed_by')
    list_filter = ('role', 'status', 'created_at')
    search_fields = ('email', 'student__first_name', 'student__last_name', 'teacher__first_name', 'teacher__last_name')
    readonly_fields = ('email', 'role', 'student', 'teacher', 'created_at', 'processed_at', 'processed_by')
    fieldsets = (
        (None, {
            'fields': ('email', 'role', 'student', 'teacher')
        }),
        ('Статус', {
            'fields': ('status', 'comment')
        }),
        ('Обработка', {
            'fields': ('created_at', 'processed_at', 'processed_by')
        })
    )

    def target_display(self, obj):
        return obj.target_name or '—'
    target_display.short_description = 'Пользователь'


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    list_display = ['name', 'backup_type', 'status', 'file_size_mb', 'created_at', 'created_by']
    list_filter = ['status', 'backup_type', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = [
        'name', 'file_path', 'file_size', 'tables_count', 'records_count',
        'created_at', 'completed_at', 'created_by'
    ]

    def file_size_mb(self, obj):
        return f"{obj.file_size_mb} МБ"
    file_size_mb.short_description = 'Размер файла'


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'is_active', 'created_at']
    search_fields = ['name', 'short_name']
    list_filter = ['is_active', 'created_at']
    ordering = ['name']


@admin.register(SubjectAssignment)
class SubjectAssignmentAdmin(admin.ModelAdmin):
    list_display = ['subject', 'faculty', 'profession', 'course', 'is_active', 'created_at']
    list_filter = ['faculty', 'profession', 'course', 'is_active']
    search_fields = ['subject__name', 'subject__short_name', 'faculty__name', 'profession']
    filter_horizontal = ['teachers']
    ordering = ['faculty__name', 'profession', 'course', 'subject__name']


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['get_full_name', 'email', 'position', 'is_curator', 'is_active']
    search_fields = ['first_name', 'last_name', 'middle_name', 'email', 'phone', 'position']
    list_filter = ['is_curator', 'is_active', 'subjects', 'groups']
    filter_horizontal = ['subjects', 'groups']
    ordering = ['last_name', 'first_name']
