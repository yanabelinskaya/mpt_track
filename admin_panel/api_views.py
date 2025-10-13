# admin_panel/api_views.py
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import json
import secrets
import string
from datetime import datetime

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

# ====================================
# API ENDPOINTS ДЛЯ СТУДЕНТОВ
# ====================================

@swagger_auto_schema(
    method='post',
    operation_description="Удалить студента по ID",
    responses={
        200: openapi.Response('Студент успешно удален', openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'message': openapi.Schema(type=openapi.TYPE_STRING)
            }
        )),
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
        return JsonResponse({'success': False, 'message': 'Модели не загружены'}, status=500)
    
    try:
        student = get_object_or_404(Student, id=student_id)
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
        
        return JsonResponse({
            'success': True,
            'message': f'Студент "{student_name}" успешно удален'
        })
        
    except Student.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Студент не найден'
        }, status=404)
        
    except Exception as e:
        print(f"ОШИБКА при удалении студента {student_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при удалении: {str(e)}'
        }, status=500)

@swagger_auto_schema(
    method='post',
    operation_description="Переключить статус активности аккаунта студента",
    responses={
        200: openapi.Response('Статус изменен', openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'is_active': openapi.Schema(type=openapi.TYPE_BOOLEAN)
            }
        )),
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
        return JsonResponse({'success': False, 'message': 'Модели не загружены'}, status=500)
    
    try:
        student = get_object_or_404(Student, id=student_id)
        print(f"Найден студент: {student.get_full_name()}")
        
        if not hasattr(student, 'user') or not student.user:
            return JsonResponse({
                'success': False,
                'message': 'У студента нет аккаунта для изменения статуса'
            }, status=400)
        
        # Переключаем статус
        old_status = student.user.is_active
        student.user.is_active = not old_status
        student.user.save()
        
        new_status = student.user.is_active
        status_text = 'активирован' if new_status else 'деактивирован'
        print(f"Статус изменен: {old_status} -> {new_status}")
        
        return JsonResponse({
            'success': True,
            'message': f'Студент "{student.get_full_name()}" {status_text}',
            'is_active': new_status
        })
        
    except Student.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Студент не найден'
        }, status=404)
        
    except Exception as e:
        print(f"ОШИБКА при изменении статуса студента {student_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при изменении статуса: {str(e)}'
        }, status=500)

@swagger_auto_schema(
    method='post',
    operation_description="Создать доступ к системе для студента",
    responses={
        200: openapi.Response('Доступ создан', openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'username': openapi.Schema(type=openapi.TYPE_STRING),
                'password': openapi.Schema(type=openapi.TYPE_STRING),
                'email_sent': openapi.Schema(type=openapi.TYPE_BOOLEAN)
            }
        )),
        400: 'Доступ уже существует',
        404: 'Студент не найден',
        500: 'Ошибка сервера'
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_create_access_api(request, student_id):
    """Создать доступ к системе для студента"""
    if not MODELS_AVAILABLE:
        return JsonResponse({'success': False, 'message': 'Модели недоступны'}, status=500)
    
    try:
        student = get_object_or_404(Student, id=student_id)
        
        # Проверяем что доступа еще нет
        if hasattr(student, 'user') and student.user:
            return JsonResponse({
                'success': False,
                'message': 'У студента уже есть доступ к системе'
            }, status=400)
        
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
        
        # Отправляем данные на email
        email_sent = send_credentials_email(student, username, password)
        
        return JsonResponse({
            'success': True,
            'message': f'Доступ создан! {"Данные отправлены на email" if email_sent else "Сохраните данные"}',
            'username': username,
            'password': password,
            'email_sent': email_sent
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при создании доступа: {str(e)}'
        }, status=500)

@swagger_auto_schema(
    method='post',
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
        return JsonResponse({'success': False, 'message': 'Модели недоступны'}, status=500)
    
    try:
        student = get_object_or_404(Student, id=student_id)
        
        # Проверяем что у студента есть аккаунт
        if not hasattr(student, 'user') or not student.user:
            return JsonResponse({
                'success': False,
                'message': 'У студента нет доступа к системе'
            }, status=400)
        
        # Генерируем новый пароль
        new_password = generate_password()
        student.user.set_password(new_password)
        student.user.save()
        
        # Отправляем на email
        email_sent = send_password_email(student, new_password)
        
        return JsonResponse({
            'success': True,
            'message': f'Новый пароль {"отправлен на email" if email_sent else "сгенерирован"}: {new_password}',
            'password': new_password,
            'email_sent': email_sent
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при сбросе пароля: {str(e)}'
        }, status=500)

# ====================================
# МАССОВЫЕ ОПЕРАЦИИ
# ====================================

@swagger_auto_schema(
    method='post',
    operation_description="Массовая активация студентов",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'mode': openapi.Schema(type=openapi.TYPE_STRING, description='Режим: selected или all'),
            'student_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                description='Список ID студентов (для режима selected)'
            ),
            'filters': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description='Фильтры (для режима all)',
                properties={
                    'search': openapi.Schema(type=openapi.TYPE_STRING),
                    'group': openapi.Schema(type=openapi.TYPE_STRING),
                    'status': openapi.Schema(type=openapi.TYPE_STRING)
                }
            )
        }
    ),
    responses={
        200: openapi.Response('Студенты активированы', openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'message': openapi.Schema(type=openapi.TYPE_STRING)
            }
        )),
        400: 'Не выбраны студенты',
        500: 'Ошибка сервера'
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_bulk_activate_api(request):
    """Массовая активация студентов"""
    # Импорт функции из views.py
    from .views import student_bulk_activate_view
    return student_bulk_activate_view(request)

@swagger_auto_schema(
    method='post',
    operation_description="Массовая деактивация студентов",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'mode': openapi.Schema(type=openapi.TYPE_STRING, description='Режим: selected или all'),
            'student_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                description='Список ID студентов (для режима selected)'
            ),
            'filters': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description='Фильтры (для режима all)'
            )
        }
    ),
    responses={200: 'Студенты деактивированы', 400: 'Не выбраны студенты', 500: 'Ошибка сервера'}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_bulk_deactivate_api(request):
    """Массовая деактивация студентов"""
    from .views import student_bulk_deactivate_view
    return student_bulk_deactivate_view(request)

@swagger_auto_schema(
    method='post',
    operation_description="Массовое удаление студентов",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'mode': openapi.Schema(type=openapi.TYPE_STRING, description='Режим: selected или all'),
            'student_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                description='Список ID студентов (для режима selected)'
            ),
            'filters': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description='Фильтры (для режима all)'
            )
        }
    ),
    responses={200: 'Студенты удалены', 400: 'Не выбраны студенты', 500: 'Ошибка сервера'}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_bulk_delete_api(request):
    """Массовое удаление студентов"""
    from .views import student_bulk_delete_view
    return student_bulk_delete_view(request)

@swagger_auto_schema(
    method='post',
    operation_description="Массовое создание доступа для студентов",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'mode': openapi.Schema(type=openapi.TYPE_STRING, description='Режим: selected или all'),
            'student_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                description='Список ID студентов (для режима selected)'
            ),
            'filters': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description='Фильтры (для режима all)'
            )
        }
    ),
    responses={200: 'Доступ создан', 400: 'Не выбраны студенты', 500: 'Ошибка сервера'}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def student_bulk_create_access_api(request):
    """Массовое создание доступа для студентов"""
    from .views import student_bulk_create_access_view
    return student_bulk_create_access_view(request)

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
        return JsonResponse({'success': False, 'message': 'Модели не загружены'}, status=500)
    
    try:
        # Получаем студентов с учетом фильтров
        students = Student.objects.all().select_related('group', 'group__faculty', 'user')
        
        # Применяем фильтры
        search = request.GET.get('search', '').strip()
        group_filter = request.GET.get('group', '').strip()
        status_filter = request.GET.get('status', '').strip()
        selected = request.GET.get('selected', '').strip()
        export_all = request.GET.get('export_all', '').strip()
        
        if search:
            print(f"Применяем поиск: '{search}'")
            students = students.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        
        if group_filter:
            print(f"Применяем фильтр группы: {group_filter}")
            students = students.filter(group_id=group_filter)
        
        if status_filter:
            print(f"Применяем фильтр статуса: '{status_filter}'")
            if status_filter == 'active':
                students = students.filter(user__is_active=True)
            elif status_filter == 'inactive':
                students = students.filter(user__is_active=False)
        
        # Если выбраны конкретные студенты
        if selected and not export_all:
            try:
                selected_ids = [int(id) for id in selected.split(',') if id.strip()]
                print(f"Экспорт выбранных студентов: {selected_ids}")
                students = students.filter(id__in=selected_ids)
            except ValueError:
                print("Ошибка парсинга выбранных ID")
                return JsonResponse({
                    'success': False,
                    'message': 'Неверный формат выбранных студентов'
                }, status=400)
        
        students_list = list(students.order_by('last_name', 'first_name'))
        print(f"Студентов для экспорта: {len(students_list)}")
        
        if not students_list:
            return JsonResponse({
                'success': False,
                'message': 'Нет студентов для экспорта'
            }, status=400)
        
        # Создаем Excel файл
        try:
            import pandas as pd
            import io
            from datetime import datetime
        except ImportError:
            return JsonResponse({
                'success': False,
                'message': 'Не установлены необходимые библиотеки для экспорта'
            }, status=500)
        
        data = []
        for student in students_list:
            data.append({
                'ID': student.id,
                'Фамилия': student.last_name,
                'Имя': student.first_name,
                'Отчество': student.middle_name or '',
                'Email': student.email,
                'Телефон': getattr(student, 'phone', '') or '',
                'Группа': student.group.name if student.group else '',
                'Факультет': student.group.faculty.name if student.group and student.group.faculty else '',
                'Статус': 'Активен' if (student.user and student.user.is_active) else 'Неактивен',
                'Логин': student.user.username if student.user else '',
                'Последний вход': student.user.last_login.strftime('%d.%m.%Y %H:%M') if (student.user and student.user.last_login) else '',
                'Дата создания': student.created_at.strftime('%d.%m.%Y') if hasattr(student, 'created_at') else '',
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
        
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при экспорте: {str(e)}',
            'error_type': type(e).__name__
        }, status=500)


@swagger_auto_schema(
    method='get',
    operation_description="Получить список студентов (для AJAX)",
    manual_parameters=[
        openapi.Parameter('search', openapi.IN_QUERY, description="Поиск", type=openapi.TYPE_STRING),
        openapi.Parameter('page', openapi.IN_QUERY, description="Номер страницы", type=openapi.TYPE_INTEGER),
    ],
    responses={
        200: openapi.Response('Список студентов', openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'students': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'full_name': openapi.Schema(type=openapi.TYPE_STRING),
                            'email': openapi.Schema(type=openapi.TYPE_STRING),
                            'group': openapi.Schema(type=openapi.TYPE_STRING),
                            'is_active': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                            'has_access': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        }
                    )
                ),
                'pagination': openapi.Schema(type=openapi.TYPE_OBJECT)
            }
        )),
        500: 'Ошибка сервера'
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def student_list_api(request):
    """API для получения списка студентов (AJAX)"""
    if not MODELS_AVAILABLE:
        return JsonResponse({'success': False, 'message': 'Модели недоступны'}, status=500)
    
    try:
        students = Student.objects.select_related('user', 'group').all()
        
        # Фильтрация
        search = request.GET.get('search', '').strip()
        if search:
            students = students.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        
        # Пагинация
        from django.core.paginator import Paginator
        paginator = Paginator(students, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Сериализация
        students_data = []
        for student in page_obj:
            students_data.append({
                'id': student.id,
                'full_name': student.get_full_name(),
                'email': student.email,
                'group': student.group.name if student.group else '',
                'is_active': hasattr(student, 'user') and student.user and student.user.is_active,
                'has_access': hasattr(student, 'user') and student.user is not None,
            })
        
        return JsonResponse({
            'success': True,
            'students': students_data,
            'pagination': {
                'page': page_obj.number,
                'pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'count': paginator.count,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

# ====================================
# ЗАГЛУШКИ ДЛЯ ФАКУЛЬТЕТОВ
# ====================================

@swagger_auto_schema(
    method='post',
    operation_description="Удалить факультет",
    responses={200: 'Факультет удален', 400: 'Есть связанные группы', 500: 'Ошибка сервера'}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def faculty_delete_api(request, faculty_id):
    return JsonResponse({'success': False, 'message': 'Функция в разработке'}, status=501)

@swagger_auto_schema(
    method='post',
    operation_description="Переключить статус факультета",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'is_active': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Новый статус')
        }
    )
)
@api_view(['POST'])
@permission_classes([AllowAny])
def faculty_toggle_status_api(request, faculty_id):
    return JsonResponse({'success': False, 'message': 'Функция в разработке'}, status=501)

@api_view(['POST'])
@permission_classes([AllowAny])
def faculty_bulk_activate_api(request):
    return JsonResponse({'success': False, 'message': 'Функция в разработке'}, status=501)

@api_view(['POST'])
@permission_classes([AllowAny])
def faculty_bulk_deactivate_api(request):
    return JsonResponse({'success': False, 'message': 'Функция в разработке'}, status=501)

@api_view(['POST'])
@permission_classes([AllowAny])
def faculty_bulk_delete_api(request):
    return JsonResponse({'success': False, 'message': 'Функция в разработке'}, status=501)

@api_view(['GET'])
@permission_classes([AllowAny])
def faculty_export_view(request):
    return JsonResponse({'success': False, 'message': 'Функция в разработке'}, status=501)
