from django.contrib import admin
from .models import Faculty, Group, Student
from admin_panel.models import Backup

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'code']
    ordering = ['name']

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'faculty', 'course', 'year_start', 'is_active', 'students_count']
    list_filter = ['faculty', 'course', 'is_active', 'year_start']
    search_fields = ['name', 'code', 'faculty__name']
    ordering = ['faculty', 'course', 'name']
    
    def students_count(self, obj):
        return obj.students_count
    students_count.short_description = 'Количество студентов'

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        'student_id', 
        'get_full_name', 
        'email', 
        'group', 
        'course', 
        'study_status',
        'has_system_access_display',
        'is_active_display'
    ]
    list_filter = [
        'study_status', 
        'course', 
        'group__faculty',
        'created_at'
    ]  # УБРАЛИ 'is_active_account'
    
    search_fields = [
        'first_name', 
        'last_name', 
        'middle_name', 
        'email', 
        'student_id',
        'user__username'
    ]
    
    ordering = ['last_name', 'first_name']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('first_name', 'last_name', 'middle_name', 'student_id')
        }),
        ('Учебная информация', {
            'fields': ('group', 'course', 'study_status', 'enrollment_date', 'graduation_date')
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
    
    # НОВЫЕ МЕТОДЫ для отображения статусов
    def has_system_access_display(self, obj):
        """Отображение наличия доступа к системе"""
        if obj.has_system_access():
            return "✅ Есть доступ"
        return "❌ Нет доступа"
    has_system_access_display.short_description = 'Доступ к системе'
    has_system_access_display.boolean = True
    
    def is_active_display(self, obj):
        """Отображение активности аккаунта"""
        if obj.has_system_access():
            if obj.is_active_account:
                return "✅ Активен"
            return "❌ Заблокирован"
        return "—"
    is_active_display.short_description = 'Статус аккаунта'
    
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
            """Генерация логина"""
            transliteration = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
            }
            
            def translit(text):
                return ''.join(transliteration.get(char.lower(), char.lower()) for char in text)
            
            username = f"{translit(last_name)}.{translit(first_name)}"
            
            counter = 1
            original_username = username
            while User.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                counter += 1
            
            return username
        
        def generate_password(length=8):
            """Генерация пароля"""
            characters = string.ascii_letters + string.digits
            return ''.join(secrets.choice(characters) for _ in range(length))
        
        count = 0
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
                    count += 1
                    
                except Exception as e:
                    self.message_user(request, f'Ошибка при создании доступа для {student.get_full_name()}: {e}', level='ERROR')
        
        self.message_user(request, f'Создан доступ для {count} студентов.')
    create_system_access.short_description = "Создать доступ к системе"


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    list_display = ['name', 'backup_type', 'status', 'file_size_mb', 'created_at', 'created_by']
    list_filter = ['status', 'backup_type', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['name', 'file_path', 'file_size', 'tables_count', 'records_count', 
                      'created_at', 'completed_at', 'created_by']
    
    def file_size_mb(self, obj):
        return f"{obj.file_size_mb} МБ"
    file_size_mb.short_description = 'Размер файла'