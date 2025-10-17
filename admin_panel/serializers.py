# admin_panel/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Student, Faculty, Group
import re


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'is_active', 'last_login', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class FacultySerializer(serializers.ModelSerializer):
    groups_count = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()
    active_students_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Faculty
        fields = [
            'id', 'name', 'code', 'description', 'is_active', 
            'created_at', 'groups_count', 'students_count', 'active_students_count'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_groups_count(self, obj):
        return obj.group_set.count()
    
    def get_students_count(self, obj):
        return Student.objects.filter(group__faculty=obj).count()
    
    def get_active_students_count(self, obj):
        return Student.objects.filter(
            group__faculty=obj, 
            user__is_active=True
        ).count()
    
    def validate_code(self, value):
        # Проверяем формат XX.XX.XX
        if not re.match(r'^\d{2}\.\d{2}\.\d{2}$', value):
            raise serializers.ValidationError(
                "Код должен быть в формате XX.XX.XX (например: 09.02.07)"
            )
        
        # Проверяем уникальность
        faculty_id = self.instance.id if self.instance else None
        if Faculty.objects.filter(code=value).exclude(id=faculty_id).exists():
            raise serializers.ValidationError("Факультет с таким кодом уже существует")
        
        return value
    
    def validate_name(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Название должно содержать минимум 2 символа")
        return value.strip()


class FacultyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ['name', 'code', 'description', 'is_active']
    
    def validate_code(self, value):
        # Проверяем формат XX.XX.XX
        if not re.match(r'^\d{2}\.\d{2}\.\d{2}$', value):
            raise serializers.ValidationError(
                "Код должен быть в формате XX.XX.XX (например: 09.02.07)"
            )
        
        # Проверяем уникальность
        if Faculty.objects.filter(code=value).exists():
            raise serializers.ValidationError("Факультет с таким кодом уже существует")
        
        return value
    
    def validate_name(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Название должно содержать минимум 2 символа")
        return value.strip()
    
    def create(self, validated_data):
        return Faculty.objects.create(**validated_data)


class FacultyListSerializer(serializers.ModelSerializer):
    groups_count = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Faculty
        fields = [
            'id', 'name', 'code', 'description', 'is_active', 
            'groups_count', 'students_count', 'status_display', 'created_at'
        ]
    
    def get_groups_count(self, obj):
        return obj.group_set.count()
    
    def get_students_count(self, obj):
        return Student.objects.filter(group__faculty=obj).count()
    
    def get_status_display(self, obj):
        return 'Активен' if obj.is_active else 'Неактивен'


class FacultyBulkOperationSerializer(serializers.Serializer):
    faculty_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=False
    )
    
    def validate_faculty_ids(self, value):
        if not value:
            raise serializers.ValidationError("Список ID факультетов не может быть пустым")
        
        # Проверяем, что все ID существуют
        existing_ids = Faculty.objects.filter(id__in=value).values_list('id', flat=True)
        missing_ids = set(value) - set(existing_ids)
        
        if missing_ids:
            raise serializers.ValidationError(f"Факультеты с ID {list(missing_ids)} не найдены")
        
        return value


class GroupSerializer(serializers.ModelSerializer):
    faculty = FacultySerializer(read_only=True)
    faculty_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'faculty', 'faculty_id', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class GroupWithFacultySerializer(serializers.ModelSerializer):
    faculty_name = serializers.SerializerMethodField()
    faculty_code = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'code', 'faculty_name', 'faculty_code', 'is_active', 'students_count', 'created_at']
    
    def get_faculty_name(self, obj):
        return obj.faculty.name if obj.faculty else None
    
    def get_faculty_code(self, obj):
        return obj.faculty.code if obj.faculty else None
    
    def get_students_count(self, obj):
        return obj.students.count()


class StudentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    group = GroupSerializer(read_only=True)
    group_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    full_name = serializers.SerializerMethodField()
    has_system_access = serializers.SerializerMethodField()
    is_active_account = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    last_login = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = [
            'id', 'first_name', 'last_name', 'middle_name', 'email',
            'phone', 'date_of_birth', 'gender', 'address', 'notes',
            'group', 'group_id', 'user', 'full_name', 'has_system_access',
            'is_active_account', 'username', 'last_login', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_has_system_access(self, obj):
        return hasattr(obj, 'user') and obj.user is not None
    
    def get_is_active_account(self, obj):
        return hasattr(obj, 'user') and obj.user and obj.user.is_active
    
    def get_username(self, obj):
        return obj.user.username if (hasattr(obj, 'user') and obj.user) else None
    
    def get_last_login(self, obj):
        if hasattr(obj, 'user') and obj.user and obj.user.last_login:
            return obj.user.last_login.strftime('%d.%m.%Y %H:%M')
        return None
    
    def validate_email(self, value):
        student_id = self.instance.id if self.instance else None
        if Student.objects.filter(email=value).exclude(id=student_id).exists():
            raise serializers.ValidationError("Студент с таким email уже существует")
        return value


class StudentCreateSerializer(serializers.ModelSerializer):
    group_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'middle_name', 'email',
            'phone', 'date_of_birth', 'gender', 'address', 'notes', 'group_id'
        ]
    
    def validate_email(self, value):
        if Student.objects.filter(email=value).exists():
            raise serializers.ValidationError("Студент с таким email уже существует")
        return value
    
    def create(self, validated_data):
        group_id = validated_data.pop('group_id', None)
        student = Student.objects.create(**validated_data)
        
        if group_id:
            try:
                group = Group.objects.get(id=group_id)
                student.group = group
                student.save()
            except Group.DoesNotExist:
                pass
        
        return student


class StudentListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    group_name = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    has_access = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = ['id', 'full_name', 'email', 'group_name', 'is_active', 'has_access']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_group_name(self, obj):
        return obj.group.name if obj.group else ''
    
    def get_is_active(self, obj):
        return hasattr(obj, 'user') and obj.user and obj.user.is_active
    
    def get_has_access(self, obj):
        return hasattr(obj, 'user') and obj.user is not None


# Общие сериализаторы
class PaginationSerializer(serializers.Serializer):
    page = serializers.IntegerField()
    pages = serializers.IntegerField()
    has_next = serializers.BooleanField()
    has_previous = serializers.BooleanField()
    count = serializers.IntegerField()


class BulkOperationSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=['selected', 'all'], required=True)
    student_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    filters = serializers.DictField(required=False, allow_empty=True)
    
    def validate(self, data):
        if data['mode'] == 'selected' and not data.get('student_ids'):
            raise serializers.ValidationError({
                'student_ids': 'Для режима "selected" требуется список student_ids'
            })
        return data


class CreateAccessSerializer(serializers.Serializer):
    send_email = serializers.BooleanField(default=True)


class PasswordResetSerializer(serializers.Serializer):
    send_email = serializers.BooleanField(default=True)


# Response сериализаторы
class StudentListResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    students = StudentListSerializer(many=True)
    pagination = PaginationSerializer()


class FacultyListResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    faculties = FacultyListSerializer(many=True)
    pagination = PaginationSerializer()
