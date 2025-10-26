# admin_panel/api_views.py
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
from django.core.paginator import Paginator
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import secrets
import string
from datetime import datetime

from .serializers import (
    StudentSerializer, BulkOperationSerializer, CreateAccessSerializer,
    PasswordResetSerializer, StudentListResponseSerializer, StudentListSerializer,
    PaginationSerializer, FacultySerializer, FacultyCreateSerializer, 
    FacultyListSerializer, FacultyBulkOperationSerializer, FacultyListResponseSerializer
)

# Безопасная проверка импорта моделей
try:
    from .models import Student, Group, Faculty
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False

# ====================================
# ФУНКЦИИ ДЛЯ ГЕНЕРАЦИИ УЧЕТНЫХ ДАННЫХ
# ====================================

def generate_username(first_name, last_name):
    """Генерация уникального username"""
    base = f"{first_name.lower()}.{last_name.lower()}"
    # Транслитерация
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya', ' ': '_'
    }
    
    username = ''.join(translit_map.get(char, char) for char in base.lower())
    
    # Проверка уникальности
    counter = 1
    original_username = username
    while User.objects.filter(username=username).exists():
        username = f"{original_username}_{counter}"
        counter += 1
    
    return username

def generate_password(length=8):
    """Генерация случайного пароля"""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def send_credentials_email(student, username, password):
    """Отправка учетных данных студенту"""
    try:
        subject = f'Доступ к системе МПТ Журнал'
        message = f'''
Здравствуйте, {student.get_full_name()}!

Для вас создан аккаунт в системе МПТ Журнал.

Данные для входа:
Логин: {username}
Пароль: {password}

Адрес входа: {getattr(settings, 'SITE_URL', 'http://localhost:8000')}

С уважением,
Администрация МПТ
'''
        
        send_mail(
            subject,
            message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@mpt.ru'),
            [student.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False

def send_password_email(student, password):
    """Отправить новый пароль на email"""
    try:
        subject = 'Новый пароль для доступа к МПТ Журнал'
        message = f'''
Здравствуйте, {student.get_full_name()}!

Ваш пароль для входа в систему МПТ Журнал был сброшен.

Новые данные для входа:
Логин: {student.user.username}
Пароль: {password}

Адрес входа: {getattr(settings, 'SITE_URL', 'http://localhost:8000')}

С уважением,
Администрация МПТ
'''
        
        send_mail(
            subject,
            message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@mpt.ru'),
            [student.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False

def apply_student_filters(queryset, filters):
    """Применить фильтры к queryset студентов"""
    search = filters.get('search', '').strip()
    group_filter = filters.get('group', '').strip()
    status_filter = filters.get('status', '').strip()
    
    if search:
        search_lower = search.lower()
        queryset = queryset.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )
    
    if group_filter:
        queryset = queryset.filter(group_id=group_filter)
    
    if status_filter:
        if status_filter == 'active':
            queryset = queryset.filter(user__is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(user__is_active=False)
    
    return queryset

# ====================================
# API ENDPOINTS ДЛЯ СТУДЕНТОВ
# ====================================

@swagger_auto_schema(
    method='post',
    operation_description="Удалить студента по ID",
    responses={
        200: openapi.Response('Студент успешно удален', StudentSerializer),
        404: 'Студент не найден',
        500: 'Ошибка сервера'
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_delete_api(request, student_id):
    """API для удаления одного студента"""
    print(f"=== student_delete_api вызван для студента ID: {student_id} ===")
    
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели не загружены'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        student = get_object_or_404(Student, id=student_id)
        student_data = StudentSerializer(student).data
        student_name = student.get_full_name()
        
        print(f"Найден студент: {student_name}")
        
        # Удаляем связанного пользователя если есть
        if hasattr(student, 'user') and student.user:
            user_id = student.user.id
            student.user.delete()
            print(f"Удален пользователь ID: {user_id}")
        
        # Удаляем студента
        student.delete()
        print(f"Студент удален: {student_name}")
        
        return Response({
            'success': True,
            'message': f'Студент "{student_name}" успешно удален',
            'deleted_student': student_data
        }, status=status.HTTP_200_OK)
        
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Студент не найден'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        print(f"ОШИБКА при удалении студента {student_id}: {str(e)}")
        return Response({
            'success': False,
            'message': f'Ошибка при удалении: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    operation_description="Переключить статус активности аккаунта студента",
    responses={
        200: openapi.Response('Статус изменен', StudentSerializer),
        400: 'У студента нет аккаунта',
        404: 'Студент не найден',
        500: 'Ошибка сервера'
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_toggle_status_api(request, student_id):
    """API для изменения статуса студента"""
    print(f"=== student_toggle_status_api вызван для студента ID: {student_id} ===")
    
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели не загружены'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        student = get_object_or_404(Student, id=student_id)
        print(f"Найден студент: {student.get_full_name()}")
        
        if not hasattr(student, 'user') or not student.user:
            return Response({
                'success': False,
                'message': 'У студента нет аккаунта для изменения статуса'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Переключаем статус
        old_status = student.user.is_active
        student.user.is_active = not old_status
        student.user.save()
        
        new_status = student.user.is_active
        status_text = 'активирован' if new_status else 'деактивирован'
        print(f"Статус изменен: {old_status} -> {new_status}")
        
        # Возвращаем обновленные данные студента
        student_data = StudentSerializer(student).data
        
        return Response({
            'success': True,
            'message': f'Студент "{student.get_full_name()}" {status_text}',
            'is_active': new_status,
            'student': student_data
        }, status=status.HTTP_200_OK)
        
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Студент не найден'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        print(f"ОШИБКА при изменении статуса студента {student_id}: {str(e)}")
        return Response({
            'success': False,
            'message': f'Ошибка при изменении статуса: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    request_body=CreateAccessSerializer,
    operation_description="Создать доступ к системе для студента",
    responses={
        200: openapi.Response('Доступ создан', StudentSerializer),
        400: 'Доступ уже существует или ошибка валидации',
        404: 'Студент не найден',
        500: 'Ошибка сервера'
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_create_access_api(request, student_id):
    """Создать доступ к системе для студента"""
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        student = get_object_or_404(Student, id=student_id)
        
        # Проверяем что доступа еще нет
        if hasattr(student, 'user') and student.user:
            return Response({
                'success': False,
                'message': 'У студента уже есть доступ к системе'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Валидируем входные данные
        serializer = CreateAccessSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Создаем пользователя
        username = generate_username(student.first_name, student.last_name)
        password = generate_password()
        
        user = User.objects.create_user(
            username=username,
            email=student.email,
            first_name=student.first_name,
            last_name=student.last_name,
            password=password
        )
        
        # Связываем с студентом
        student.user = user
        student.save()
        
        # Отправляем данные на email если нужно
        email_sent = False
        if serializer.validated_data.get('send_email', True):
            email_sent = send_credentials_email(student, username, password)
        
        # Возвращаем обновленные данные студента
        student_data = StudentSerializer(student).data
        
        return Response({
            'success': True,
            'message': 'Доступ создан успешно',
            'student': student_data,
            'credentials': {
                'username': username,
                'password': password if not email_sent else None
            },
            'email_sent': email_sent
        }, status=status.HTTP_200_OK)
        
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Студент не найден'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Ошибка при создании доступа: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    request_body=PasswordResetSerializer,
    operation_description="Сбросить пароль студента",
    responses={
        200: openapi.Response('Пароль сброшен', openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'password': openapi.Schema(type=openapi.TYPE_STRING),
                'email_sent': openapi.Schema(type=openapi.TYPE_BOOLEAN)
            }
        )),
        400: 'У студента нет аккаунта',
        404: 'Студент не найден',
        500: 'Ошибка сервера'
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_reset_password_api(request, student_id):
    """Сбросить пароль студента"""
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        student = get_object_or_404(Student, id=student_id)
        
        # Проверяем что у студента есть аккаунт
        if not hasattr(student, 'user') or not student.user:
            return Response({
                'success': False,
                'message': 'У студента нет доступа к системе'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Валидируем входные данные
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Генерируем новый пароль
        new_password = generate_password()
        student.user.set_password(new_password)
        student.user.save()
        
        # Отправляем на email если нужно
        email_sent = False
        if serializer.validated_data.get('send_email', True):
            email_sent = send_password_email(student, new_password)
        
        return Response({
            'success': True,
            'message': f'Новый пароль {"отправлен на email" if email_sent else "сгенерирован"}',
            'password': new_password if not email_sent else None,
            'email_sent': email_sent
        }, status=status.HTTP_200_OK)
        
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Студент не найден'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Ошибка при сбросе пароля: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ====================================
# МАССОВЫЕ ОПЕРАЦИИ
# ====================================

@swagger_auto_schema(
    method='post',
    request_body=BulkOperationSerializer,
    operation_description="Массовая активация студентов",
    responses={
        200: openapi.Response('Студенты активированы', openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'activated_count': openapi.Schema(type=openapi.TYPE_INTEGER)
            }
        )),
        400: 'Ошибка валидации',
        500: 'Ошибка сервера'
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_bulk_activate_api(request):
    """Массовая активация студентов"""
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Валидируем входные данные
    serializer = BulkOperationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        validated_data = serializer.validated_data
        
        # Получаем студентов в зависимости от режима
        if validated_data['mode'] == 'all':
            students = Student.objects.select_related('user').all()
            filters = validated_data.get('filters', {})
            students = apply_student_filters(students, filters)
        else:
            student_ids = validated_data['student_ids']
            students = Student.objects.select_related('user').filter(id__in=student_ids)
        
        activated_count = 0
        for student in students:
            if hasattr(student, 'user') and student.user:
                student.user.is_active = True
                student.user.save()
                activated_count += 1
        
        return Response({
            'success': True,
            'message': f'Активировано {activated_count} студентов',
            'activated_count': activated_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Ошибка при массовой активации: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    request_body=BulkOperationSerializer,
    operation_description="Массовая деактивация студентов",
    responses={200: 'Студенты деактивированы', 400: 'Ошибка валидации', 500: 'Ошибка сервера'}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_bulk_deactivate_api(request):
    """Массовая деактивация студентов"""
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    serializer = BulkOperationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        validated_data = serializer.validated_data
        
        if validated_data['mode'] == 'all':
            students = Student.objects.select_related('user').all()
            filters = validated_data.get('filters', {})
            students = apply_student_filters(students, filters)
        else:
            student_ids = validated_data['student_ids']
            students = Student.objects.select_related('user').filter(id__in=student_ids)
        
        deactivated_count = 0
        for student in students:
            if hasattr(student, 'user') and student.user:
                student.user.is_active = False
                student.user.save()
                deactivated_count += 1
        
        return Response({
            'success': True,
            'message': f'Деактивировано {deactivated_count} студентов',
            'deactivated_count': deactivated_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Ошибка при массовой деактивации: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    request_body=BulkOperationSerializer,
    operation_description="Массовое удаление студентов",
    responses={200: 'Студенты удалены', 400: 'Ошибка валидации', 500: 'Ошибка сервера'}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_bulk_delete_api(request):
    """Массовое удаление студентов"""
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    serializer = BulkOperationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        validated_data = serializer.validated_data
        
        if validated_data['mode'] == 'all':
            students = Student.objects.select_related('user').all()
            filters = validated_data.get('filters', {})
            students = apply_student_filters(students, filters)
        else:
            student_ids = validated_data['student_ids']
            students = Student.objects.select_related('user').filter(id__in=student_ids)
        
        deleted_count = 0
        deleted_students = []
        
        for student in students:
            student_data = StudentSerializer(student).data
            deleted_students.append(student_data)
            
            # Удаляем связанного пользователя
            if hasattr(student, 'user') and student.user:
                student.user.delete()
            
            student.delete()
            deleted_count += 1
        
        return Response({
            'success': True,
            'message': f'Удалено {deleted_count} студентов',
            'deleted_count': deleted_count,
            'deleted_students': deleted_students[:10]  # Показываем первые 10 для экономии трафика
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Ошибка при массовом удалении: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    request_body=BulkOperationSerializer,
    operation_description="Массовое создание доступа для студентов",
    responses={200: 'Доступ создан', 400: 'Ошибка валидации', 500: 'Ошибка сервера'}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_bulk_create_access_api(request):
    """Массовое создание доступа для студентов"""
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    serializer = BulkOperationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        validated_data = serializer.validated_data
        
        if validated_data['mode'] == 'all':
            students = Student.objects.select_related('user').all()
            filters = validated_data.get('filters', {})
            students = apply_student_filters(students, filters)
        else:
            student_ids = validated_data['student_ids']
            students = Student.objects.select_related('user').filter(id__in=student_ids)
        
        created_count = 0
        for student in students:
            # Проверяем что доступа еще нет
            if hasattr(student, 'user') and student.user:
                continue
            
            # Создаем пользователя
            username = generate_username(student.first_name, student.last_name)
            password = generate_password()
            
            user = User.objects.create_user(
                username=username,
                email=student.email,
                first_name=student.first_name,
                last_name=student.last_name,
                password=password
            )
            
            student.user = user
            student.save()
            
            # Отправляем данные на email
            send_credentials_email(student, username, password)
            created_count += 1
        
        return Response({
            'success': True,
            'message': f'Создан доступ для {created_count} студентов',
            'created_count': created_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Ошибка при массовом создании доступа: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ====================================
# ЭКСПОРТ И СПИСКИ
# ====================================

@swagger_auto_schema(
    method='get',
    operation_description="Экспорт студентов в Excel",
    manual_parameters=[
        openapi.Parameter('search', openapi.IN_QUERY, description="Поиск по имени/фамилии/email", type=openapi.TYPE_STRING),
        openapi.Parameter('group', openapi.IN_QUERY, description="Фильтр по группе", type=openapi.TYPE_STRING),
        openapi.Parameter('status', openapi.IN_QUERY, description="Фильтр по статусу", type=openapi.TYPE_STRING),
        openapi.Parameter('selected', openapi.IN_QUERY, description="ID выбранных студентов через запятую", type=openapi.TYPE_STRING),
        openapi.Parameter('export_all', openapi.IN_QUERY, description="Экспортировать всех", type=openapi.TYPE_STRING),
    ],
    responses={
        200: openapi.Response('Excel файл', schema=openapi.Schema(type=openapi.TYPE_FILE)),
        400: 'Нет студентов для экспорта',
        500: 'Ошибка сервера'
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def student_export_view(request):
    """Экспорт студентов в Excel"""
    print(f"=== student_export_view вызван ===")
    print(f"Параметры запроса: {dict(request.GET)}")
    
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели не загружены'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        # Получаем студентов с учетом фильтров
        students = Student.objects.all().select_related('group', 'group__faculty', 'user')
        
        # Применяем фильтры из GET параметров
        filters = {
            'search': request.GET.get('search', '').strip(),
            'group': request.GET.get('group', '').strip(),
            'status': request.GET.get('status', '').strip(),
        }
        
        students = apply_student_filters(students, filters)
        
        # Если выбраны конкретные студенты
        selected = request.GET.get('selected', '').strip()
        export_all = request.GET.get('export_all', '').strip()
        
        if selected and not export_all:
            try:
                selected_ids = [int(id) for id in selected.split(',') if id.strip()]
                print(f"Экспорт выбранных студентов: {selected_ids}")
                students = students.filter(id__in=selected_ids)
            except ValueError:
                return Response({
                    'success': False,
                    'message': 'Неверный формат выбранных студентов'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        students_list = list(students.order_by('last_name', 'first_name'))
        print(f"Студентов для экспорта: {len(students_list)}")
        
        if not students_list:
            return Response({
                'success': False,
                'message': 'Нет студентов для экспорта'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Создаем Excel файл
        try:
            import pandas as pd
            import io
        except ImportError:
            return Response({
                'success': False,
                'message': 'Не установлены необходимые библиотеки для экспорта'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Используем serializer для консистентности данных
        students_data = StudentSerializer(students_list, many=True).data
        
        # Преобразуем в формат для pandas
        data = []
        for student_data in students_data:
            data.append({
                'ID': student_data['id'],
                'Фамилия': student_data['last_name'],
                'Имя': student_data['first_name'],
                'Отчество': student_data['middle_name'] or '',
                'Email': student_data['email'],
                'Телефон': student_data.get('phone', '') or '',
                'Группа': student_data['group']['name'] if student_data['group'] else '',
                'Факультет': student_data['group']['faculty']['name'] if student_data['group'] and student_data['group']['faculty'] else '',
                'Статус': 'Активен' if student_data['is_active_account'] else 'Неактивен',
                'Логин': student_data['username'] or '',
                'Последний вход': student_data['last_login'] or '',
                'Дата создания': student_data['created_at'][:10] if student_data['created_at'] else '',
            })
        
        df = pd.DataFrame(data)
        
        # Создаем Excel файл в памяти
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Студенты', index=False)
            
            # Автоширина колонок
            worksheet = writer.sheets['Студенты']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        # Возвращаем файл
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Формируем имя файла
        if selected and not export_all:
            filename = f'students_selected_{len(students_list)}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        else:
            filename = f'students_all_{len(students_list)}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        print(f"Excel файл создан успешно: {filename}")
        return response
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ОШИБКА при экспорте:")
        print(f"Тип ошибки: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        print(f"Traceback:\n{error_details}")
        
        return Response({
            'success': False,
            'message': f'Ошибка при экспорте: {str(e)}',
            'error_type': type(e).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_description="Получить список студентов (для AJAX)",
    manual_parameters=[
        openapi.Parameter('search', openapi.IN_QUERY, description="Поиск", type=openapi.TYPE_STRING),
        openapi.Parameter('page', openapi.IN_QUERY, description="Номер страницы", type=openapi.TYPE_INTEGER),
    ],
    responses={
        200: StudentListResponseSerializer,
        500: 'Ошибка сервера'
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def student_list_api(request):
    """API для получения списка студентов (AJAX)"""
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        students = Student.objects.select_related('user', 'group').all()
        
        # Фильтрация
        search = request.GET.get('search', '').strip() 
        if search:
            search_lower = search.lower()
            students = students.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        
        # Пагинация
        paginator = Paginator(students, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Сериализация с использованием StudentListSerializer
        students_data = StudentListSerializer(page_obj, many=True).data
        
        # Сериализация пагинации
        pagination_data = {
            'page': page_obj.number,
            'pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'count': paginator.count,
        }
        
        return Response({
            'success': True,
            'students': students_data,
            'pagination': pagination_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False, 
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Факультеты
@swagger_auto_schema(
    method='post',
    operation_description="Удалить факультет по ID",
    responses={
        200: openapi.Response('Факультет удален', FacultySerializer),
        400: 'Есть связанные группы или студенты',
        404: 'Факультет не найден',
        500: 'Ошибка сервера'
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def faculty_delete_api(request, faculty_id):
    """API для удаления факультета"""
    print(f"=== faculty_delete_api вызван для факультета ID: {faculty_id} ===")
    
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели не загружены'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        faculty = get_object_or_404(Faculty, id=faculty_id)
        faculty_data = FacultySerializer(faculty).data
        faculty_name = faculty.name
        
        print(f"Найден факультет: {faculty_name}")
        
        # Проверяем связанные группы и студентов
        groups_count = faculty.group_set.count()
        students_count = Student.objects.filter(group__faculty=faculty).count()
        
        if groups_count > 0 or students_count > 0:
            return Response({
                'success': False,
                'message': f'Нельзя удалить факультет "{faculty_name}". '
                          f'К нему привязано групп: {groups_count}, студентов: {students_count}. '
                          f'Сначала удалите или переместите связанные данные.',
                'groups_count': groups_count,
                'students_count': students_count
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Удаляем факультет
        faculty.delete()
        print(f"Факультет удален: {faculty_name}")
        
        return Response({
            'success': True,
            'message': f'Факультет "{faculty_name}" успешно удален',
            'deleted_faculty': faculty_data
        }, status=status.HTTP_200_OK)
        
    except Faculty.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Факультет не найден'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        print(f"ОШИБКА при удалении факультета {faculty_id}: {str(e)}")
        return Response({
            'success': False,
            'message': f'Ошибка при удалении: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    operation_description="Переключить статус активности факультета",
    responses={
        200: openapi.Response('Статус изменен', FacultySerializer),
        404: 'Факультет не найден',
        500: 'Ошибка сервера'
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def faculty_toggle_status_api(request, faculty_id):
    """API для изменения статуса факультета"""
    print(f"=== faculty_toggle_status_api вызван для факультета ID: {faculty_id} ===")
    
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели не загружены'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        faculty = get_object_or_404(Faculty, id=faculty_id)
        print(f"Найден факультет: {faculty.name}")
        
        # Переключаем статус
        old_status = faculty.is_active
        faculty.is_active = not old_status
        faculty.save()
        
        new_status = faculty.is_active
        status_text = 'активирован' if new_status else 'деактивирован'
        print(f"Статус изменен: {old_status} -> {new_status}")
        
        # Возвращаем обновленные данные факультета
        faculty_data = FacultySerializer(faculty).data
        
        return Response({
            'success': True,
            'message': f'Факультет "{faculty.name}" {status_text}',
            'is_active': new_status,
            'faculty': faculty_data
        }, status=status.HTTP_200_OK)
        
    except Faculty.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Факультет не найден'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        print(f"ОШИБКА при изменении статуса факультета {faculty_id}: {str(e)}")
        return Response({
            'success': False,
            'message': f'Ошибка при изменении статуса: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    request_body=FacultyBulkOperationSerializer,
    operation_description="Массовая активация факультетов",
    responses={
        200: openapi.Response('Факультеты активированы', openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'updated_count': openapi.Schema(type=openapi.TYPE_INTEGER)
            }
        )),
        400: 'Ошибка валидации',
        500: 'Ошибка сервера'
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def faculty_bulk_activate_api(request):
    """Массовая активация факультетов"""
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    serializer = FacultyBulkOperationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        faculty_ids = serializer.validated_data['faculty_ids']
        
        # Получаем факультеты для обновления
        faculties = Faculty.objects.filter(id__in=faculty_ids)
        updated_count = faculties.update(is_active=True)
        
        return Response({
            'success': True,
            'message': f'Активировано {updated_count} факультетов',
            'updated_count': updated_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Ошибка при массовой активации: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    request_body=FacultyBulkOperationSerializer,
    operation_description="Массовая деактивация факультетов",
    responses={200: 'Факультеты деактивированы', 400: 'Ошибка валидации', 500: 'Ошибка сервера'}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def faculty_bulk_deactivate_api(request):
    """Массовая деактивация факультетов"""
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    serializer = FacultyBulkOperationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        faculty_ids = serializer.validated_data['faculty_ids']
        
        faculties = Faculty.objects.filter(id__in=faculty_ids)
        updated_count = faculties.update(is_active=False)
        
        return Response({
            'success': True,
            'message': f'Деактивировано {updated_count} факультетов',
            'updated_count': updated_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Ошибка при массовой деактивации: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    request_body=FacultyBulkOperationSerializer,
    operation_description="Массовое удаление факультетов",
    responses={200: 'Факультеты удалены', 400: 'Ошибка валидации или есть связанные данные', 500: 'Ошибка сервера'}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def faculty_bulk_delete_api(request):
    """Массовое удаление факультетов"""
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    serializer = FacultyBulkOperationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        faculty_ids = serializer.validated_data['faculty_ids']
        
        # Проверяем связанные данные для каждого факультета
        protected_faculties = []
        faculties_to_delete = []
        
        for faculty in Faculty.objects.filter(id__in=faculty_ids):
            groups_count = faculty.group_set.count()
            students_count = Student.objects.filter(group__faculty=faculty).count()
            
            if groups_count > 0 or students_count > 0:
                protected_faculties.append({
                    'id': faculty.id,
                    'name': faculty.name,
                    'groups_count': groups_count,
                    'students_count': students_count
                })
            else:
                faculties_to_delete.append(faculty)
        
        if protected_faculties:
            message = 'Следующие факультеты нельзя удалить из-за связанных данных:\n'
            for faculty in protected_faculties:
                message += f'• {faculty["name"]}: {faculty["groups_count"]} групп, {faculty["students_count"]} студентов\n'
            message += 'Сначала удалите или переместите связанные данные.'
            
            return Response({
                'success': False,
                'message': message,
                'protected_faculties': protected_faculties
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Удаляем факультеты
        deleted_faculties = []
        for faculty in faculties_to_delete:
            faculty_data = FacultySerializer(faculty).data
            deleted_faculties.append(faculty_data)
            faculty.delete()
        
        deleted_count = len(deleted_faculties)
        
        return Response({
            'success': True,
            'message': f'Удалено {deleted_count} факультетов',
            'deleted_count': deleted_count,
            'deleted_faculties': deleted_faculties[:10]  # Показываем первые 10
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Ошибка при массовом удалении: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_description="Экспорт факультетов в Excel",
    manual_parameters=[
        openapi.Parameter('search', openapi.IN_QUERY, description="Поиск по названию/коду", type=openapi.TYPE_STRING),
        openapi.Parameter('status', openapi.IN_QUERY, description="Фильтр по статусу", type=openapi.TYPE_STRING),
        openapi.Parameter('selected', openapi.IN_QUERY, description="ID выбранных факультетов через запятую", type=openapi.TYPE_STRING),
        openapi.Parameter('export_all', openapi.IN_QUERY, description="Экспортировать все", type=openapi.TYPE_STRING),
    ],
    responses={
        200: openapi.Response('Excel файл', schema=openapi.Schema(type=openapi.TYPE_FILE)),
        400: 'Нет факультетов для экспорта',
        500: 'Ошибка сервера'
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def faculty_export_view(request):
    """Экспорт факультетов в Excel"""
    print(f"=== faculty_export_view вызван ===")
    print(f"Параметры запроса: {dict(request.GET)}")
    
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели не загружены'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        faculties = Faculty.objects.all()
        
        # Применяем фильтры из GET параметров
        search = request.GET.get('search', '').strip()
        status_filter = request.GET.get('status', '').strip()
        selected = request.GET.get('selected', '').strip()
        export_all = request.GET.get('export_all', '').strip()
        
        if search:
            search_lower = search.lower()
            print(f"Применяем поиск: '{search}'")
            faculties = faculties.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        if status_filter:
            print(f"Применяем фильтр статуса: '{status_filter}'")
            if status_filter == 'active':
                faculties = faculties.filter(is_active=True)
            elif status_filter == 'inactive':
                faculties = faculties.filter(is_active=False)
        
        # Если выбраны конкретные факультеты
        if selected and not export_all:
            try:
                selected_ids = [int(id) for id in selected.split(',') if id.strip()]
                print(f"Экспорт выбранных факультетов: {selected_ids}")
                faculties = faculties.filter(id__in=selected_ids)
            except ValueError:
                return Response({
                    'success': False,
                    'message': 'Неверный формат выбранных факультетов'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        faculties_list = list(faculties.order_by('name'))
        print(f"Факультетов для экспорта: {len(faculties_list)}")
        
        if not faculties_list:
            return Response({
                'success': False,
                'message': 'Нет факультетов для экспорта'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Создаем Excel файл
        try:
            import pandas as pd
            import io
        except ImportError:
            return Response({
                'success': False,
                'message': 'Не установлены необходимые библиотеки для экспорта'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Используем serializer для консистентности данных
        faculties_data = FacultySerializer(faculties_list, many=True).data
        
        # Преобразуем в формат для pandas
        data = []
        for faculty_data in faculties_data:
            data.append({
                'ID': faculty_data['id'],
                'Название': faculty_data['name'],
                'Код': faculty_data['code'],
                'Описание': faculty_data['description'] or '',
                'Статус': 'Активен' if faculty_data['is_active'] else 'Неактивен',
                'Групп': faculty_data['groups_count'],
                'Студентов': faculty_data['students_count'],
                'Активных студентов': faculty_data['active_students_count'],
                'Дата создания': faculty_data['created_at'][:10] if faculty_data['created_at'] else '',
            })
        
        df = pd.DataFrame(data)
        
        # Создаем Excel файл в памяти
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Факультеты', index=False)
            
            # Автоширина колонок
            worksheet = writer.sheets['Факультеты']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        # Возвращаем файл
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Формируем имя файла
        if selected and not export_all:
            filename = f'faculties_selected_{len(faculties_list)}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        else:
            filename = f'faculties_all_{len(faculties_list)}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        print(f"Excel файл создан успешно: {filename}")
        return response
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ОШИБКА при экспорте:")
        print(f"Тип ошибки: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        print(f"Traceback:\n{error_details}")
        
        return Response({
            'success': False,
            'message': f'Ошибка при экспорте: {str(e)}',
            'error_type': type(e).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_description="Получить список факультетов (для AJAX)",
    manual_parameters=[
        openapi.Parameter('search', openapi.IN_QUERY, description="Поиск", type=openapi.TYPE_STRING),
        openapi.Parameter('page', openapi.IN_QUERY, description="Номер страницы", type=openapi.TYPE_INTEGER),
        openapi.Parameter('status', openapi.IN_QUERY, description="Фильтр по статусу", type=openapi.TYPE_STRING),
    ],
    responses={
        200: FacultyListResponseSerializer,
        500: 'Ошибка сервера'
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def faculty_list_api(request):
    """API для получения списка факультетов (AJAX)"""
    if not MODELS_AVAILABLE:
        return Response({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        faculties = Faculty.objects.all()
        
        # Фильтрация
        search = request.GET.get('search', '').strip() 
        if search:
            search_lower = search.lower()
            faculties = faculties.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        status_filter = request.GET.get('status', '').strip()
        if status_filter == 'active':
            faculties = faculties.filter(is_active=True)
        elif status_filter == 'inactive':
            faculties = faculties.filter(is_active=False)
        
        # Сортировка
        faculties = faculties.order_by('name')
        
        # Пагинация
        paginator = Paginator(faculties, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Сериализация с использованием FacultyListSerializer
        faculties_data = FacultyListSerializer(page_obj, many=True).data
        
        # Сериализация пагинации
        pagination_data = {
            'page': page_obj.number,
            'pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'count': paginator.count,
        }
        
        return Response({
            'success': True,
            'faculties': faculties_data,
            'pagination': pagination_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False, 
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Group, Student
from .serializers import GroupSerializer
import json

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_list_api(request):
    groups = Group.objects.all().order_by('faculty__name', 'profession', 'code')
    serializer = GroupSerializer(groups, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_detail_api(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    serializer = GroupSerializer(group)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def group_create_api(request):
    serializer = GroupSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'success': True, 'data': serializer.data}, status=status.HTTP_201_CREATED)
    return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def group_update_api(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    serializer = GroupSerializer(group, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({'success': True, 'data': serializer.data})
    return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def group_delete_api(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    group.delete()
    return Response({'success': True, 'message': 'Группа удалена'})

# Пример API для перевода студента
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def transfer_student_api(request):
    try:
        data = request.data
        student_id = data.get('student_id')
        target_group_id = data.get('target_group_id')

        student = get_object_or_404(Student, id=student_id)
        target_group = get_object_or_404(Group, id=target_group_id)

        student.group = target_group
        student.save()

        return Response({'success': True, 'message': 'Студент переведен'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

