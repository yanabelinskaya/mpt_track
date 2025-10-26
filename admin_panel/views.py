# admin_panel/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, F, Sum
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
import json
import secrets
import string
import pandas as pd
import io
import re
import uuid
from datetime import datetime
from urllib.parse import urlencode
import tempfile
import os
from django.contrib.auth.decorators import login_required, user_passes_test
from admin_panel.services.backup_service import BackupService
from admin_panel.models import Backup
from django.views.decorators.http import require_POST


# Безопасная проверка импорта моделей
try:
    from .models import Student, Group, Faculty
    MODELS_AVAILABLE = True
except:
    MODELS_AVAILABLE = False

def is_admin_user(user):
    """Проверка, является ли пользователь администратором"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)

# ====================================
# ОСНОВНЫЕ VIEWS
# ====================================
def dashboard_view(request):
    """Главная страница - перенаправление по ролям"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Если администратор или персонал - показываем админ-панель
    if request.user.is_staff or request.user.is_superuser:
        return admin_dashboard_view(request)
    
    # Если студент - перенаправляем в студенческий кабинет
    try:
        student = request.user.student_profile
        return redirect('student_dashboard')
    except AttributeError:
        pass
    
    # Если обычный пользователь без роли
    messages.warning(request, 'У вас нет назначенной роли в системе. Обратитесь к администратору.')
    return redirect('login')

@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def admin_dashboard_view(request):
    """Админ-панель - только для администраторов"""
    print(f"=== admin_dashboard_view вызван ===")
    print(f"Пользователь: {request.user.username}")
    print(f"MODELS_AVAILABLE: {MODELS_AVAILABLE}")
    
    students_count = 0
    groups_count = 0
    faculties_count = 0
    
    if MODELS_AVAILABLE:
        try:
            students_count = Student.objects.count()
            groups_count = Group.objects.filter(is_active=True).count()
            faculties_count = Faculty.objects.filter(is_active=True).count()
        except Exception as e:
            print(f"Ошибка получения статистики: {str(e)}")
            students_count = 0
            groups_count = 0
            faculties_count = 0
    
    context = {
        'students_count': students_count,
        'groups_count': groups_count,
        'faculties_count': faculties_count,
    }
    
    return render(request, 'admin_panel/dashboard.html', context)

@login_required
def students_list_view(request):
    """Список студентов с фильтрацией и поиском"""
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции.')
        return redirect('admin_dashboard')
    
    try:
        # Получаем параметры фильтрации
        search = request.GET.get('search', '').strip()
        group_filter = request.GET.get('group', '')
        status_filter = request.GET.get('status', '')
        
        # Получаем выбранных студентов из параметров
        selected_students = request.GET.get('selected', '').strip()
        selected_ids = []
        if selected_students:
            try:
                selected_ids = [int(x) for x in selected_students.split(',') if x.strip()]
            except ValueError:
                selected_ids = []
        
        # Базовый queryset
        students = Student.objects.select_related('user', 'group', 'group__faculty').all()
        
        # Поиск по имени, фамилии, email, студенческому билету
        if search:
            search_lower = search.lower()
            students = students.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(middle_name__icontains=search) |
                Q(email__icontains=search) |
                Q(student_id__icontains=search) |
                Q(user__username__icontains=search)
            )
        
        # Фильтр по группе
        if group_filter:
            students = students.filter(group_id=group_filter)
        
        # Фильтр по статусу
        if status_filter == 'active':
            students = students.filter(user__is_active=True, study_status='active')
        elif status_filter == 'inactive':
            students = students.filter(user__is_active=False)
        elif status_filter:
            students = students.filter(study_status=status_filter)
        
        # Сортировка
        students = students.order_by('last_name', 'first_name')
        
        # Сохраняем общий queryset для подсчета
        total_students = students.count()
        
        # Пагинация
        paginator = Paginator(students, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Получаем список групп для фильтра
        groups = Group.objects.filter(is_active=True).select_related('faculty').order_by('name')
        
        # Добавляем количество студентов в каждой группе
        group_counts = Group.objects.filter(id__in=groups.values_list('id', flat=True)).annotate(total=Count('students'))
        counts_map = {g.id: g.total for g in group_counts}
        for group in groups:
            group.total_students = counts_map.get(group.id, 0)
        
        context = {
            'page_obj': page_obj,
            'groups': groups,
            'search': search,
            'group_filter': group_filter,
            'status_filter': status_filter,
            'total_students': total_students,
            'status_choices': Student._meta.get_field('study_status').choices,
            'selected_students': selected_ids,
            'current_filters': {
                'search': search,
                'group': group_filter,
                'status': status_filter,
            }
        }
        
        return render(request, 'admin_panel/students/students_list.html', context)
    
    except Exception as e:
        import logging, traceback
        logging.exception("Ошибка загрузки списка студентов")
        trace = traceback.format_exc()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': str(e),
                'traceback': trace,
            }, status=500)
        messages.error(request, f'Ошибка загрузки студентов: {str(e)}')
        return render(request, 'admin_panel/students/students_error.html', {
            'error': str(e),
            'traceback': trace,
        }, status=500)

# ====================================
# СТУДЕНТЫ - HTML СТРАНИЦЫ
# ====================================
@login_required
def student_detail_view(request, student_id):
    """Детальная информация о студенте - HTML страница"""
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены.')
        return redirect('admin_dashboard')
    
    try:
        student = get_object_or_404(Student, id=student_id)
        
        # Добавляем дополнительные поля для вашего шаблона
        context = {
            'student': student,
        }
        
        return render(request, 'admin_panel/students/student_detail.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке информации о студенте: {str(e)}')
        return redirect('admin_students')

@login_required
def student_edit_view(request, student_id):
    """Редактирование студента - HTML страница"""
    print(f"=== student_edit_view вызван для студента ID: {student_id} ===")
    print(f"Метод запроса: {request.method}")
    print(f"MODELS_AVAILABLE: {MODELS_AVAILABLE}")
    
    if not MODELS_AVAILABLE:
        error_msg = 'Модели не загружены. Проверьте миграции.'
        print(f"ОШИБКА: {error_msg}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': error_msg}, status=500)
        messages.error(request, error_msg)
        return redirect('admin_dashboard')
    
    try:
        print(f"Пытаемся найти студента с ID: {student_id}")
        student = get_object_or_404(Student, id=student_id)
        print(f"Студент найден: {student.get_full_name()}")
        
        if request.method == 'POST':
            print("=== Обработка POST запроса ===")
            
            # Проверяем тип запроса - AJAX или обычная форма
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            print(f"AJAX запрос: {is_ajax}")
            
            try:
                print("Получаем данные из формы...")
                
                # Получаем данные из формы
                first_name = request.POST.get('first_name', '').strip()
                last_name = request.POST.get('last_name', '').strip()
                middle_name = request.POST.get('middle_name', '').strip()
                email = request.POST.get('email', '').strip()
                phone = request.POST.get('phone', '').strip()
                group_id = request.POST.get('group')
                
                print(f"Полученные данные:")
                print(f"  first_name: '{first_name}'")
                print(f"  last_name: '{last_name}'")
                print(f"  middle_name: '{middle_name}'")
                print(f"  email: '{email}'")
                print(f"  phone: '{phone}'")
                print(f"  group_id: '{group_id}'")
                
                # Валидация
                print("Выполняем валидацию...")
                errors = {}
                if not first_name:
                    errors['first_name'] = ['Имя обязательно для заполнения']
                if not last_name:
                    errors['last_name'] = ['Фамилия обязательна для заполнения']
                if not email:
                    errors['email'] = ['Email обязателен для заполнения']
                
                # Проверяем уникальность email (если изменился)
                if email and email != student.email:
                    print(f"Проверяем уникальность email: {email} (старый: {student.email})")
                    if Student.objects.filter(email=email).exists():
                        errors['email'] = ['Студент с таким email уже существует']
                
                if errors:
                    print(f"Найдены ошибки валидации: {errors}")
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'message': 'Ошибки валидации',
                            'errors': errors
                        }, status=400)
                    else:
                        for field, field_errors in errors.items():
                            messages.error(request, f'{field}: {field_errors[0]}')
                        context = {
                            'student': student,
                            'groups': Group.objects.filter(is_active=True).select_related('faculty').order_by('name'),
                        }
                        return render(request, 'admin_panel/students/student_edit.html', context)
                
                print("Валидация прошла успешно, обновляем данные студента...")
                
                # Обновляем основные данные студента
                print("Обновляем основные поля...")
                student.first_name = first_name
                student.last_name = last_name
                student.middle_name = middle_name
                student.email = email
                
                # Проверяем и обновляем дополнительные поля
                print("Проверяем дополнительные поля модели...")
                
                # Телефон
                if hasattr(student, 'phone'):
                    print(f"Обновляем телефон: {phone}")
                    student.phone = phone
                else:
                    print("Поле 'phone' отсутствует в модели")
                
                # Дата рождения
                date_of_birth = request.POST.get('date_of_birth')
                print(f"Дата рождения из формы: '{date_of_birth}'")
                if hasattr(student, 'date_of_birth') and date_of_birth:
                    try:
                        from datetime import datetime
                        student.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
                        print(f"Дата рождения обновлена: {student.date_of_birth}")
                    except ValueError as e:
                        print(f"Ошибка парсинга даты: {e}")
                else:
                    print("Поле 'date_of_birth' отсутствует в модели или пустое")
                
                # ИСПРАВЛЕНИЕ: Пол - важно правильно обработать
                gender = request.POST.get('gender', '').strip()
                print(f"Пол из формы: '{gender}'")
                if hasattr(student, 'gender'):
                    # Если поле gender обязательное (NOT NULL), устанавливаем значение по умолчанию
                    if gender in ['M', 'F']:
                        student.gender = gender
                        print(f"Пол обновлен: {student.gender}")
                    else:
                        # Если пол не указан, оставляем текущее значение или устанавливаем дефолт
                        if not student.gender:  # Если в базе тоже пустое значение
                            student.gender = 'M'  # Устанавливаем мужской по умолчанию
                            print(f"Пол не указан, установлен по умолчанию: {student.gender}")
                        else:
                            print(f"Пол не изменен, оставлен текущий: {student.gender}")
                else:
                    print("Поле 'gender' отсутствует в модели")
                
                # Адрес
                address = request.POST.get('address', '').strip()
                print(f"Адрес из формы: '{address}'")
                if hasattr(student, 'address'):
                    student.address = address
                    print(f"Адрес обновлен: {student.address}")
                else:
                    print("Поле 'address' отсутствует в модели")
                
                # Заметки
                notes = request.POST.get('notes', '').strip()
                print(f"Заметки из формы: '{notes}'")
                if hasattr(student, 'notes'):
                    student.notes = notes
                    print(f"Заметки обновлены: {student.notes}")
                else:
                    print("Поле 'notes' отсутствует в модели")
                
                # Группа
                print(f"Группа из формы: '{group_id}'")
                if hasattr(student, 'group'):
                    if group_id and group_id.strip():
                        try:
                            group = Group.objects.get(id=int(group_id))
                            student.group = group
                            print(f"Группа обновлена: {group.name}")
                        except Group.DoesNotExist:
                            print(f"Группа с ID {group_id} не найдена")
                            student.group = None
                        except ValueError as e:
                            print(f"Ошибка преобразования ID группы: {e}")
                            student.group = None
                    else:
                        student.group = None
                        print("Группа не выбрана, устанавливаем None")
                else:
                    print("Поле 'group' отсутствует в модели")
                
                # Сохраняем студента
                print("Сохраняем студента в базу данных...")
                student.save()
                print("Студент сохранен успешно!")
                
                # Обновляем связанного пользователя если есть
                if hasattr(student, 'user') and student.user:
                    print("Обновляем связанного пользователя...")
                    student.user.first_name = student.first_name
                    student.user.last_name = student.last_name
                    student.user.email = student.email
                    student.user.save()
                    print("Пользователь обновлен успешно!")
                else:
                    print("Связанный пользователь отсутствует")
                
                # Возвращаем ответ в зависимости от типа запроса
                if is_ajax:
                    print("Возвращаем JSON ответ...")
                    response_data = {
                        'success': True,
                        'message': f'Студент "{student.get_full_name()}" успешно обновлен',
                        'student': {
                            'id': student.id,
                            'full_name': student.get_full_name(),
                            'email': student.email
                        }
                    }
                    print(f"JSON ответ: {response_data}")
                    return JsonResponse(response_data)
                else:
                    print("Возвращаем редирект...")
                    messages.success(request, f'Студент "{student.get_full_name()}" успешно обновлен')
                    return redirect('admin_students')
                
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"КРИТИЧЕСКАЯ ОШИБКА при сохранении студента:")
                print(f"Тип ошибки: {type(e).__name__}")
                print(f"Сообщение ошибки: {str(e)}")
                print(f"Полный traceback:\n{error_details}")
                
                error_message = f'Ошибка при сохранении: {str(e)}'
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'message': error_message,
                        'error_type': type(e).__name__,
                        'traceback': error_details
                    }, status=500)
                else:
                    messages.error(request, error_message)
                    context = {
                        'student': student,
                        'groups': Group.objects.filter(is_active=True).select_related('faculty').order_by('name'),
                    }
                    return render(request, 'admin_panel/students/student_edit.html', context)
        
        # GET запрос - показываем форму редактирования
        print("=== Обработка GET запроса ===")
        try:
            print("Загружаем группы...")
            groups = Group.objects.filter(is_active=True).select_related('faculty').order_by('name')
            print(f"Загружено групп: {groups.count()}")
        except Exception as e:
            print(f"Ошибка загрузки групп: {str(e)}")
            groups = []
        
        context = {
            'student': student,
            'groups': groups,
        }
        
        print("Рендерим шаблон...")
        return render(request, 'admin_panel/students/student_edit.html', context)
        
    except Student.DoesNotExist:
        error_message = f'Студент с ID {student_id} не найден'
        print(f"ОШИБКА 404: {error_message}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': error_message}, status=404)
        messages.error(request, error_message)
        return redirect('admin_students')
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"КРИТИЧЕСКАЯ ОШИБКА в student_edit_view:")
        print(f"Тип ошибки: {type(e).__name__}")
        print(f"Сообщение ошибки: {str(e)}")
        print(f"Полный traceback:\n{error_details}")
        
        error_message = f'Критическая ошибка: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False, 
                'message': error_message,
                'error_type': type(e).__name__,
                'traceback': error_details
            }, status=500)
        messages.error(request, error_message)
        return redirect('admin_students')

@login_required
def student_create_view(request):
    """Создание нового студента"""
    print(f"=== student_create_view вызван ===")
    print(f"Метод запроса: {request.method}")
    print(f"MODELS_AVAILABLE: {MODELS_AVAILABLE}")
    
    if not MODELS_AVAILABLE:
        error_msg = 'Модели не загружены. Выполните миграции.'
        print(f"ОШИБКА: {error_msg}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': error_msg}, status=500)
        messages.error(request, error_msg)
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        print("=== Обработка POST запроса ===")
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        print(f"AJAX запрос: {is_ajax}")
        print(f"Заголовки запроса: {dict(request.headers)}")
        
        try:
            print("Получаем данные из формы...")
            
            # Получаем данные из формы
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            middle_name = request.POST.get('middle_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone', '').strip()
            group_id = request.POST.get('group') or request.POST.get('group_id')
            
            # Дополнительные поля
            date_of_birth = request.POST.get('date_of_birth', '').strip()
            gender = request.POST.get('gender', '').strip()
            address = request.POST.get('address', '').strip()
            notes = request.POST.get('notes', '').strip()
            
            print(f"Полученные данные:")
            print(f"  first_name: '{first_name}'")
            print(f"  last_name: '{last_name}'")
            print(f"  middle_name: '{middle_name}'")
            print(f"  email: '{email}'")
            print(f"  phone: '{phone}'")
            print(f"  group_id: '{group_id}'")
            print(f"  date_of_birth: '{date_of_birth}'")
            print(f"  gender: '{gender}'")
            print(f"  address: '{address}'")
            print(f"  notes: '{notes}'")

            # Валидация
            print("Выполняем валидацию...")
            errors = {}
            if not last_name:
                errors['last_name'] = ['Фамилия обязательна для заполнения.']
            if not first_name:
                errors['first_name'] = ['Имя обязательно для заполнения.']
            if not email:
                errors['email'] = ['Email обязателен для заполнения.']
            elif Student.objects.filter(email=email).exists():
                errors['email'] = ['Пользователь с таким email уже существует.']
            
            if errors:
                print(f"Найдены ошибки валидации: {errors}")
                if is_ajax:
                    return JsonResponse({
                        'success': False, 
                        'errors': errors,
                        'message': 'Исправьте ошибки в форме'
                    }, status=400)
                else:
                    for field, field_errors in errors.items():
                        messages.error(request, f'{field}: {field_errors[0]}')
                    context = {
                        'groups': Group.objects.filter(is_active=True).order_by('name'),
                        'form_data': request.POST
                    }
                    return render(request, 'admin_panel/students/student_create.html', context)
            
            print("Валидация прошла успешно, создаем студента...")
            
            # Подготавливаем данные для создания студента
            student_data = {
                'first_name': first_name,
                'last_name': last_name,
                'middle_name': middle_name,
                'email': email,
            }
            
            # Добавляем дополнительные поля если они существуют в модели
            print("Проверяем дополнительные поля модели...")
            
            # Проверяем поле phone
            from django.db import models
            student_fields = [field.name for field in Student._meta.get_fields()]
            print(f"Поля модели Student: {student_fields}")
            
            if 'phone' in student_fields:
                student_data['phone'] = phone
                print(f"Добавлено поле phone: '{phone}'")
            else:
                print("Поле 'phone' отсутствует в модели")
            
            # Обрабатываем дату рождения
            if 'date_of_birth' in student_fields and date_of_birth:
                try:
                    from datetime import datetime
                    student_data['date_of_birth'] = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
                    print(f"Добавлена дата рождения: {student_data['date_of_birth']}")
                except ValueError as e:
                    print(f"Ошибка парсинга даты рождения: {e}")
            else:
                print("Поле 'date_of_birth' отсутствует в модели или пустое")
            
            # Обрабатываем пол - ВАЖНО для избежания ошибки NOT NULL
            if 'gender' in student_fields:
                if gender in ['M', 'F']:
                    student_data['gender'] = gender
                    print(f"Добавлен пол: '{gender}'")
                else:
                    # Если пол не указан, устанавливаем значение по умолчанию
                    student_data['gender'] = 'M'  # Мужской по умолчанию
                    print(f"Пол не указан, установлен по умолчанию: 'M'")
            else:
                print("Поле 'gender' отсутствует в модели")
            
            # Добавляем адрес
            if 'address' in student_fields:
                student_data['address'] = address
                print(f"Добавлен адрес: '{address}'")
            else:
                print("Поле 'address' отсутствует в модели")
            
            # Добавляем заметки
            if 'notes' in student_fields:
                student_data['notes'] = notes
                print(f"Добавлены заметки: '{notes}'")
            else:
                print("Поле 'notes' отсутствует в модели")
            
            print(f"Итоговые данные для создания студента: {student_data}")
            
            # Создаем студента
            print("Создаем студента в базе данных...")
            student = Student.objects.create(**student_data)
            print(f"Студент создан успешно! ID: {student.id}")
            
            # Назначаем группу если выбрана
            if 'group' in student_fields and group_id and group_id.strip():
                print(f"Назначаем группу с ID: {group_id}")
                try:
                    group = Group.objects.get(id=int(group_id))
                    student.group = group
                    student.save()
                    print(f"Группа назначена успешно: {group.name}")
                except Group.DoesNotExist:
                    print(f"Группа с ID {group_id} не найдена")
                except ValueError as e:
                    print(f"Ошибка преобразования ID группы: {e}")
            else:
                print("Группа не назначена")
            
            print("Студент создан и сохранен успешно!")
            
            if is_ajax:
                print("Возвращаем JSON ответ...")
                response_data = {
                    'success': True, 
                    'student_id': student.id,
                    'message': f'Студент "{student.get_full_name()}" успешно создан',
                    'redirect_url': reverse('admin_students')
                }
                print(f"JSON ответ: {response_data}")
                return JsonResponse(response_data)
            else:
                print("Возвращаем редирект...")
                messages.success(request, f'Студент "{student.get_full_name()}" успешно создан')
                return redirect('admin_students')
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"КРИТИЧЕСКАЯ ОШИБКА при создании студента:")
            print(f"Тип ошибки: {type(e).__name__}")
            print(f"Сообщение ошибки: {str(e)}")
            print(f"Полный traceback:\n{error_details}")
            
            error_message = f'Ошибка при создании студента: {str(e)}'
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': error_message,
                    'error_type': type(e).__name__,
                    'traceback': error_details
                }, status=500)
            else:
                messages.error(request, error_message)
                context = {
                    'groups': Group.objects.filter(is_active=True).order_by('name'),
                    'form_data': request.POST
                }
                return render(request, 'admin_panel/students/student_create.html', context)

    # GET-запрос, показываем форму
    print("=== Обработка GET запроса ===")
    try:
        print("Загружаем группы...")
        groups = Group.objects.filter(is_active=True).order_by('name')
        print(f"Загружено групп: {groups.count()}")
    except Exception as e:
        print(f"Ошибка загрузки групп: {str(e)}")
        groups = []
    
    context = {
        'groups': groups
    }
    
    print("Рендерим шаблон создания...")
    return render(request, 'admin_panel/students/student_create.html', context)

@login_required
def download_sample_excel(request):
    """Скачивание образца Excel файла для импорта студентов"""
    try:
        # Создаем DataFrame с примером данных
        sample_data = {
            'last_name': [
                'Иванов',
                'Петров', 
                'Сидоров',
                'Кузнецова'
            ],
            'first_name': [
                'Иван',
                'Петр',
                'Алексей',
                'Мария'
            ],
            'middle_name': [
                'Петрович',
                'Иванович',
                'Сергеевич',
                'Александровна'
            ],
            'email': [
                'ivanov@example.com',
                'petrov@example.com',
                'sidorov@example.com',
                'kuznetsova@example.com'
            ],
            'phone': [
                '+7 (999) 123-45-67',
                '+7 (999) 234-56-78',
                '+7 (999) 345-67-89',
                '+7 (999) 456-78-90'
            ],
            'group_name': [
                'ИТ-21',
                'ЭК-21',
                'МЕХ-21',
                'ИТ-22'
            ]
        }
        
        df = pd.DataFrame(sample_data)
        
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
        response['Content-Disposition'] = 'attachment; filename="students_import_sample.xlsx"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Ошибка при создании файла: {str(e)}')
        return redirect('admin_students')

@login_required
def student_import_view(request):
    """Массовый импорт студентов из Excel"""
    print(f"=== student_import_view вызван ===")
    print(f"Метод запроса: {request.method}")
    print(f"MODELS_AVAILABLE: {MODELS_AVAILABLE}")
    
    if not MODELS_AVAILABLE:
        error_msg = 'Модели не загружены. Выполните миграции.'
        print(f"ОШИБКА: {error_msg}")
        messages.error(request, error_msg)
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        print("=== Обработка POST запроса ===")
        
        try:
            excel_file = request.FILES.get('excel_file')
            
            if not excel_file:
                print("Файл не выбран")
                messages.error(request, 'Выберите файл для импорта')
                return render(request, 'admin_panel/students/student_import.html')
            
            print(f"Получен файл: {excel_file.name}, размер: {excel_file.size} байт")
            
            # Проверяем формат файла
            if not excel_file.name.endswith(('.xlsx', '.xls')):
                print("Неверный формат файла")
                messages.error(request, 'Поддерживаются только файлы Excel (.xlsx, .xls)')
                return render(request, 'admin_panel/students/student_import.html')
            
            # Читаем Excel файл
            print("Читаем Excel файл...")
            try:
                df = pd.read_excel(excel_file)
            except Exception as e:
                error_msg = f'Ошибка чтения Excel файла: {str(e)}'
                print(f"ОШИБКА: {error_msg}")
                messages.error(request, error_msg)
                return render(request, 'admin_panel/students/student_import.html')
            
            print(f"Прочитано строк: {len(df)}")
            print(f"Колонки в файле: {list(df.columns)}")
            
            if len(df) == 0:
                print("Файл пустой")
                messages.error(request, 'Файл не содержит данных')
                return render(request, 'admin_panel/students/student_import.html')
            
            # Очищаем названия колонок от пробелов
            df.columns = df.columns.str.strip()
            print(f"Колонки после очистки: {list(df.columns)}")
            
            # Проверяем наличие необходимых колонок (поддерживаем оба варианта)
            column_mapping = {}
            
            # Фамилия
            if 'last_name' in df.columns:
                column_mapping['last_name'] = 'last_name'
            elif 'surname' in df.columns:
                column_mapping['last_name'] = 'surname'
            elif 'Фамилия' in df.columns:
                column_mapping['last_name'] = 'Фамилия'
            else:
                error_msg = 'Не найдена колонка с фамилией (last_name, surname или Фамилия)'
                print(f"ОШИБКА: {error_msg}")
                messages.error(request, error_msg)
                return render(request, 'admin_panel/students/student_import.html')
            
            # Имя
            if 'first_name' in df.columns:
                column_mapping['first_name'] = 'first_name'
            elif 'name' in df.columns:
                column_mapping['first_name'] = 'name'
            elif 'Имя' in df.columns:
                column_mapping['first_name'] = 'Имя'
            else:
                error_msg = 'Не найдена колонка с именем (first_name, name или Имя)'
                print(f"ОШИБКА: {error_msg}")
                messages.error(request, error_msg)
                return render(request, 'admin_panel/students/student_import.html')
            
            # Email
            if 'email' in df.columns:
                column_mapping['email'] = 'email'
            elif 'Email' in df.columns:
                column_mapping['email'] = 'Email'
            else:
                error_msg = 'Не найдена колонка с email (email или Email)'
                print(f"ОШИБКА: {error_msg}")
                messages.error(request, error_msg)
                return render(request, 'admin_panel/students/student_import.html')
            
            # Отчество (необязательное)
            if 'middle_name' in df.columns:
                column_mapping['middle_name'] = 'middle_name'
            elif 'patronymic' in df.columns:
                column_mapping['middle_name'] = 'patronymic'
            elif 'Отчество' in df.columns:
                column_mapping['middle_name'] = 'Отчество'
            
            # Телефон (необязательное)
            if 'phone' in df.columns:
                column_mapping['phone'] = 'phone'
            elif 'Телефон' in df.columns:
                column_mapping['phone'] = 'Телефон'
            
            # Группа (необязательное)
            if 'group_name' in df.columns:
                column_mapping['group_name'] = 'group_name'
            elif 'group' in df.columns:
                column_mapping['group_name'] = 'group'
            elif 'Группа' in df.columns:
                column_mapping['group_name'] = 'Группа'
            
            print(f"Маппинг колонок: {column_mapping}")
            
            # Результаты импорта
            import_result = {
                'total_rows': len(df),
                'created_count': 0,
                'duplicates_count': 0,
                'errors_count': 0,
                'duplicates': [],
                'errors': [],
                'success': False
            }
            
            print("Начинаем импорт студентов...")
            
            # Импортируем студентов
            with transaction.atomic():
                for index, row in df.iterrows():
                    row_num = index + 2  # Учитываем заголовок
                    print(f"\nОбрабатываем строку {row_num}:")
                    
                    try:
                        # Получаем данные с использованием маппинга
                        last_name = str(row[column_mapping['last_name']]).strip() if not pd.isna(row[column_mapping['last_name']]) else ''
                        first_name = str(row[column_mapping['first_name']]).strip() if not pd.isna(row[column_mapping['first_name']]) else ''
                        email = str(row[column_mapping['email']]).strip().lower() if not pd.isna(row[column_mapping['email']]) else ''
                        
                        middle_name = ''
                        if 'middle_name' in column_mapping:
                            middle_name = str(row[column_mapping['middle_name']]).strip() if not pd.isna(row[column_mapping['middle_name']]) else ''
                        
                        phone = ''
                        if 'phone' in column_mapping:
                            phone = str(row[column_mapping['phone']]).strip() if not pd.isna(row[column_mapping['phone']]) else ''
                        
                        group_name = ''
                        if 'group_name' in column_mapping:
                            group_name = str(row[column_mapping['group_name']]).strip() if not pd.isna(row[column_mapping['group_name']]) else ''
                        
                        print(f"  Данные: {last_name} {first_name} {middle_name} - {email}")
                        
                        # Проверяем обязательные поля
                        if not last_name or not first_name or not email:
                            error_msg = 'Отсутствуют обязательные поля (фамилия, имя или email)'
                            print(f"  ОШИБКА: {error_msg}")
                            import_result['errors'].append({
                                'row': row_num,
                                'message': error_msg
                            })
                            import_result['errors_count'] += 1
                            continue
                        
                        # Проверяем корректность email
                        if '@' not in email or '.' not in email:
                            error_msg = f'Некорректный email: {email}'
                            print(f"  ОШИБКА: {error_msg}")
                            import_result['errors'].append({
                                'row': row_num,
                                'message': error_msg
                            })
                            import_result['errors_count'] += 1
                            continue
                        
                        # Проверяем уникальность email
                        if Student.objects.filter(email=email).exists():
                            full_name = f"{last_name} {first_name} {middle_name}".strip()
                            print(f"  Дубликат найден: {email}")
                            import_result['duplicates'].append({
                                'row': row_num,
                                'full_name': full_name,
                                'email': email
                            })
                            import_result['duplicates_count'] += 1
                            continue
                        
                        # Подготавливаем данные для создания
                        student_data = {
                            'first_name': first_name,
                            'last_name': last_name,
                            'middle_name': middle_name,
                            'email': email,
                        }
                        
                        # Проверяем дополнительные поля модели
                        student_fields = [field.name for field in Student._meta.get_fields()]
                        
                        if 'phone' in student_fields and phone:
                            student_data['phone'] = phone
                        
                        # Устанавливаем пол по умолчанию если поле обязательное
                        if 'gender' in student_fields:
                            student_data['gender'] = 'M'  # По умолчанию мужской
                        
                        print(f"  Создаем студента с данными: {student_data}")
                        
                        # Создаем студента
                        student = Student.objects.create(**student_data)
                        import_result['created_count'] += 1
                        print(f"  Студент создан успешно! ID: {student.id}")
                        
                        # Назначаем группу если указана
                        if group_name and 'group' in student_fields:
                            try:
                                group = Group.objects.get(name=group_name)
                                student.group = group
                                student.save()
                                print(f"  Назначена группа: {group_name}")
                            except Group.DoesNotExist:
                                print(f"  Группа не найдена: {group_name}")
                        
                    except Exception as e:
                        error_msg = f'Ошибка создания студента: {str(e)}'
                        print(f"  ОШИБКА: {error_msg}")
                        import_result['errors'].append({
                            'row': row_num,
                            'message': error_msg
                        })
                        import_result['errors_count'] += 1
                        continue
            
            # Определяем успешность импорта
            import_result['success'] = import_result['created_count'] > 0 and import_result['errors_count'] == 0
            
            print(f"\nИмпорт завершен:")
            print(f"  Создано: {import_result['created_count']}")
            print(f"  Дублей: {import_result['duplicates_count']}")
            print(f"  Ошибок: {import_result['errors_count']}")
            
            # Показываем результаты через messages
            if import_result['created_count'] > 0:
                messages.success(request, f'Успешно импортировано студентов: {import_result["created_count"]}')
            if import_result['duplicates_count'] > 0:
                messages.warning(request, f'Пропущено дублей: {import_result["duplicates_count"]}')
            if import_result['errors_count'] > 0:
                messages.error(request, f'Ошибок при импорте: {import_result["errors_count"]}')
            
            # Если ничего не импортировано
            if import_result['created_count'] == 0:
                if import_result['duplicates_count'] > 0 and import_result['errors_count'] == 0:
                    messages.warning(request, 'Все студенты уже существуют в системе')
                elif import_result['errors_count'] > 0 and import_result['duplicates_count'] == 0:
                    messages.error(request, 'Не удалось импортировать ни одного студента из-за ошибок')
                else:
                    messages.error(request, 'Импорт не выполнен')
            
            context = {
                'import_result': import_result
            }
            return render(request, 'admin_panel/students/student_import.html', context)
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"\nКРИТИЧЕСКАЯ ОШИБКА при импорте:")
            print(f"Тип ошибки: {type(e).__name__}")
            print(f"Сообщение ошибки: {str(e)}")
            print(f"Полный traceback:\n{error_details}")
            
            messages.error(request, f'Критическая ошибка при импорте файла: {str(e)}')
    
    # GET запрос - показываем форму импорта
    print("=== Обработка GET запроса ===")
    return render(request, 'admin_panel/students/student_import.html')

@login_required
def student_bulk_delete_view(request):
    """Массовое удаление студентов с подробным логированием"""
    print(f"=== student_bulk_delete_view вызван ===")
    print(f"Метод запроса: {request.method}")
    print(f"MODELS_AVAILABLE: {MODELS_AVAILABLE}")
    
    if not MODELS_AVAILABLE:
        error_msg = 'Модели не загружены'
        print(f"ОШИБКА: {error_msg}")
        return JsonResponse({'success': False, 'message': error_msg}, status=500)
    
    if request.method == 'POST':
        try:
            print("Получаем данные из запроса...")
            data = json.loads(request.body)
            print(f"Данные запроса: {data}")
            
            mode = data.get('mode', 'selected')
            print(f"Режим операции: {mode}")
            
            if mode == 'all':
                print("=== Режим: удаление ВСЕХ студентов с фильтрами ===")
                
                # Удаляем всех студентов с учетом фильтров
                filters = data.get('filters', {})
                print(f"Применяемые фильтры: {filters}")
                
                students = Student.objects.all()
                print(f"Изначально студентов в базе: {students.count()}")
                
                if filters.get('search'):
                    search = filters['search']
                    print(f"Применяем поиск: '{search}'")
                    students = students.filter(
                        Q(first_name__icontains=search) |
                        Q(last_name__icontains=search) |
                        Q(email__icontains=search)
                    )
                    print(f"После поиска студентов: {students.count()}")
                
                if filters.get('group'):
                    group_id = filters['group']
                    print(f"Применяем фильтр по группе: {group_id}")
                    students = students.filter(group_id=group_id)
                    print(f"После фильтра по группе студентов: {students.count()}")
                
                if filters.get('status'):
                    status = filters['status']
                    print(f"Применяем фильтр по статусу: '{status}'")
                    if status == 'active':
                        students = students.filter(user__is_active=True)
                    elif status == 'inactive':
                        students = students.filter(user__is_active=False)
                    print(f"После фильтра по статусу студентов: {students.count()}")
                
                deleted_count = students.count()
                print(f"Будет удалено студентов: {deleted_count}")
                
                if deleted_count == 0:
                    print("Нет студентов для удаления")
                    return JsonResponse({
                        'success': True,
                        'message': 'Нет студентов для удаления с указанными фильтрами'
                    })
                
                # Удаляем связанных пользователей
                users_deleted = 0
                print("Удаляем связанных пользователей...")
                for student in students:
                    try:
                        print(f"Обрабатываем студента: {student.get_full_name()} (ID: {student.id})")
                        if hasattr(student, 'user') and student.user:
                            user_id = student.user.id
                            student.user.delete()
                            users_deleted += 1
                            print(f"  Удален пользователь ID: {user_id}")
                        else:
                            print(f"  У студента нет связанного пользователя")
                    except Exception as e:
                        print(f"  ОШИБКА при удалении пользователя: {str(e)}")
                        continue
                
                print(f"Удалено пользователей: {users_deleted}")
                
                # Удаляем студентов
                print("Удаляем студентов...")
                students.delete()
                print(f"Удалено студентов: {deleted_count}")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Удалено студентов: {deleted_count} (пользователей: {users_deleted})'
                })
                
            else:
                print("=== Режим: удаление ВЫБРАННЫХ студентов ===")
                
                # Удаляем выбранных студентов
                student_ids = data.get('student_ids', [])
                print(f"ID студентов для удаления: {student_ids}")
                
                if not student_ids:
                    print("Не указаны ID студентов")
                    return JsonResponse({
                        'success': False,
                        'message': 'Не указаны студенты для удаления'
                    }, status=400)
                
                students = Student.objects.filter(id__in=student_ids)
                deleted_count = students.count()
                print(f"Найдено студентов для удаления: {deleted_count}")
                
                if deleted_count == 0:
                    print("Студенты не найдены")
                    return JsonResponse({
                        'success': False,
                        'message': 'Указанные студенты не найдены'
                    }, status=404)
                
                # Удаляем связанных пользователей
                users_deleted = 0
                print("Удаляем связанных пользователей...")
                for student in students:
                    try:
                        print(f"Обрабатываем студента: {student.get_full_name()} (ID: {student.id})")
                        if hasattr(student, 'user') and student.user:
                            user_id = student.user.id
                            student.user.delete()
                            users_deleted += 1
                            print(f"  Удален пользователь ID: {user_id}")
                        else:
                            print(f"  У студента нет связанного пользователя")
                    except Exception as e:
                        print(f"  ОШИБКА при удалении пользователя: {str(e)}")
                        continue
                
                print(f"Удалено пользователей: {users_deleted}")
                
                # Удаляем студентов
                print("Удаляем студентов...")
                students.delete()
                print(f"Удалено студентов: {deleted_count}")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Удалено студентов: {deleted_count} (пользователей: {users_deleted})'
                })
            
        except json.JSONDecodeError as e:
            error_msg = f'Ошибка парсинга JSON: {str(e)}'
            print(f"ОШИБКА JSON: {error_msg}")
            return JsonResponse({
                'success': False,
                'message': error_msg,
                'error_type': 'JSONDecodeError'
            }, status=400)
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"КРИТИЧЕСКАЯ ОШИБКА при массовом удалении:")
            print(f"Тип ошибки: {type(e).__name__}")
            print(f"Сообщение ошибки: {str(e)}")
            print(f"Полный traceback:\n{error_details}")
            
            return JsonResponse({
                'success': False,
                'message': f'Ошибка при удалении: {str(e)}',
                'error_type': type(e).__name__,
                'traceback': error_details
            }, status=500)
    
    error_msg = 'Метод не поддерживается'
    print(f"ОШИБКА: {error_msg}")
    return JsonResponse({
        'success': False, 
        'message': error_msg
    }, status=405)

@login_required
def student_bulk_activate_view(request):
    """Массовая активация студентов с подробным логированием"""
    print(f"=== student_bulk_activate_view вызван ===")
    print(f"Метод запроса: {request.method}")
    print(f"MODELS_AVAILABLE: {MODELS_AVAILABLE}")
    
    if not MODELS_AVAILABLE:
        error_msg = 'Модели не загружены'
        print(f"ОШИБКА: {error_msg}")
        return JsonResponse({'success': False, 'message': error_msg}, status=500)
    
    if request.method == 'POST':
        try:
            print("Получаем данные из запроса...")
            data = json.loads(request.body)
            print(f"Данные запроса: {data}")
            
            mode = data.get('mode', 'selected')
            print(f"Режим операции: {mode}")
            
            if mode == 'all':
                print("=== Режим: активация ВСЕХ студентов с фильтрами ===")
                
                # Активируем всех студентов с учетом фильтров
                filters = data.get('filters', {})
                print(f"Применяемые фильтры: {filters}")
                
                students = Student.objects.filter(user__isnull=False)
                print(f"Студентов с аккаунтами в базе: {students.count()}")
                
                if filters.get('search'):
                    search = filters['search']
                    print(f"Применяем поиск: '{search}'")
                    students = students.filter(
                        Q(first_name__icontains=search) |
                        Q(last_name__icontains=search) |
                        Q(email__icontains=search)
                    )
                    print(f"После поиска студентов: {students.count()}")
                
                if filters.get('group'):
                    group_id = filters['group']
                    print(f"Применяем фильтр по группе: {group_id}")
                    students = students.filter(group_id=group_id)
                    print(f"После фильтра по группе студентов: {students.count()}")
                
                activated_count = 0
                print("Активируем студентов...")
                for student in students:
                    try:
                        print(f"Обрабатываем студента: {student.get_full_name()} (ID: {student.id})")
                        if student.user:
                            was_active = student.user.is_active
                            student.user.is_active = True
                            student.user.save()
                            if not was_active:
                                activated_count += 1
                                print(f"  Студент активирован")
                            else:
                                print(f"  Студент уже был активен")
                        else:
                            print(f"  У студента нет пользователя")
                    except Exception as e:
                        print(f"  ОШИБКА при активации студента: {str(e)}")
                        continue
                
                print(f"Активировано студентов: {activated_count}")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Активировано студентов: {activated_count}'
                })
                
            else:
                print("=== Режим: активация ВЫБРАННЫХ студентов ===")
                
                # Активируем выбранных студентов
                student_ids = data.get('student_ids', [])
                print(f"ID студентов для активации: {student_ids}")
                
                if not student_ids:
                    print("Не указаны ID студентов")
                    return JsonResponse({
                        'success': False,
                        'message': 'Не указаны студенты для активации'
                    }, status=400)
                
                students = Student.objects.filter(id__in=student_ids, user__isnull=False)
                found_count = students.count()
                print(f"Найдено студентов с аккаунтами: {found_count}")
                
                if found_count == 0:
                    print("Студенты с аккаунтами не найдены")
                    return JsonResponse({
                        'success': False,
                        'message': 'У указанных студентов нет аккаунтов для активации'
                    }, status=404)
                
                activated_count = 0
                print("Активируем студентов...")
                for student in students:
                    try:
                        print(f"Обрабатываем студента: {student.get_full_name()} (ID: {student.id})")
                        if student.user:
                            was_active = student.user.is_active
                            student.user.is_active = True
                            student.user.save()
                            if not was_active:
                                activated_count += 1
                                print(f"  Студент активирован")
                            else:
                                print(f"  Студент уже был активен")
                        else:
                            print(f"  У студента нет пользователя")
                    except Exception as e:
                        print(f"  ОШИБКА при активации студента: {str(e)}")
                        continue
                
                print(f"Активировано студентов: {activated_count}")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Активировано студентов: {activated_count}'
                })
            
        except json.JSONDecodeError as e:
            error_msg = f'Ошибка парсинга JSON: {str(e)}'
            print(f"ОШИБКА JSON: {error_msg}")
            return JsonResponse({
                'success': False,
                'message': error_msg,
                'error_type': 'JSONDecodeError'
            }, status=400)
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"КРИТИЧЕСКАЯ ОШИБКА при массовой активации:")
            print(f"Тип ошибки: {type(e).__name__}")
            print(f"Сообщение ошибки: {str(e)}")
            print(f"Полный traceback:\n{error_details}")
            
            return JsonResponse({
                'success': False,
                'message': f'Ошибка при активации: {str(e)}',
                'error_type': type(e).__name__,
                'traceback': error_details
            }, status=500)
    
    error_msg = 'Метод не поддерживается'
    print(f"ОШИБКА: {error_msg}")
    return JsonResponse({
        'success': False, 
        'message': error_msg
    }, status=405)

@login_required
def student_bulk_deactivate_view(request):
    """Массовая деактивация студентов с подробным логированием"""
    print(f"=== student_bulk_deactivate_view вызван ===")
    print(f"Метод запроса: {request.method}")
    print(f"MODELS_AVAILABLE: {MODELS_AVAILABLE}")
    
    if not MODELS_AVAILABLE:
        error_msg = 'Модели не загружены'
        print(f"ОШИБКА: {error_msg}")
        return JsonResponse({'success': False, 'message': error_msg}, status=500)
    
    if request.method == 'POST':
        try:
            print("Получаем данные из запроса...")
            data = json.loads(request.body)
            print(f"Данные запроса: {data}")
            
            mode = data.get('mode', 'selected')
            print(f"Режим операции: {mode}")
            
            if mode == 'all':
                print("=== Режим: деактивация ВСЕХ студентов с фильтрами ===")
                
                # Деактивируем всех студентов с учетом фильтров
                filters = data.get('filters', {})
                print(f"Применяемые фильтры: {filters}")
                
                students = Student.objects.filter(user__isnull=False)
                print(f"Студентов с аккаунтами в базе: {students.count()}")
                
                if filters.get('search'):
                    search = filters['search']
                    print(f"Применяем поиск: '{search}'")
                    students = students.filter(
                        Q(first_name__icontains=search) |
                        Q(last_name__icontains=search) |
                        Q(email__icontains=search)
                    )
                    print(f"После поиска студентов: {students.count()}")
                
                if filters.get('group'):
                    group_id = filters['group']
                    print(f"Применяем фильтр по группе: {group_id}")
                    students = students.filter(group_id=group_id)
                    print(f"После фильтра по группе студентов: {students.count()}")
                
                deactivated_count = 0
                print("Деактивируем студентов...")
                for student in students:
                    try:
                        print(f"Обрабатываем студента: {student.get_full_name()} (ID: {student.id})")
                        if student.user:
                            was_active = student.user.is_active
                            student.user.is_active = False
                            student.user.save()
                            if was_active:
                                deactivated_count += 1
                                print(f"  Студент деактивирован")
                            else:
                                print(f"  Студент уже был неактивен")
                        else:
                            print(f"  У студента нет пользователя")
                    except Exception as e:
                        print(f"  ОШИБКА при деактивации студента: {str(e)}")
                        continue
                
                print(f"Деактивировано студентов: {deactivated_count}")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Деактивировано студентов: {deactivated_count}'
                })
                
            else:
                print("=== Режим: деактивация ВЫБРАННЫХ студентов ===")
                
                # Деактивируем выбранных студентов
                student_ids = data.get('student_ids', [])
                print(f"ID студентов для деактивации: {student_ids}")
                
                if not student_ids:
                    print("Не указаны ID студентов")
                    return JsonResponse({
                        'success': False,
                        'message': 'Не указаны студенты для деактивации'
                    }, status=400)
                
                students = Student.objects.filter(id__in=student_ids, user__isnull=False)
                found_count = students.count()
                print(f"Найдено студентов с аккаунтами: {found_count}")
                
                if found_count == 0:
                    print("Студенты с аккаунтами не найдены")
                    return JsonResponse({
                        'success': False,
                        'message': 'У указанных студентов нет аккаунтов для деактивации'
                    }, status=404)
                
                deactivated_count = 0
                print("Деактивируем студентов...")
                for student in students:
                    try:
                        print(f"Обрабатываем студента: {student.get_full_name()} (ID: {student.id})")
                        if student.user:
                            was_active = student.user.is_active
                            student.user.is_active = False
                            student.user.save()
                            if was_active:
                                deactivated_count += 1
                                print(f"  Студент деактивирован")
                            else:
                                print(f"  Студент уже был неактивен")
                        else:
                            print(f"  У студента нет пользователя")
                    except Exception as e:
                        print(f"  ОШИБКА при деактивации студента: {str(e)}")
                        continue
                
                print(f"Деактивировано студентов: {deactivated_count}")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Деактивировано студентов: {deactivated_count}'
                })
            
        except json.JSONDecodeError as e:
            error_msg = f'Ошибка парсинга JSON: {str(e)}'
            print(f"ОШИБКА JSON: {error_msg}")
            return JsonResponse({
                'success': False,
                'message': error_msg,
                'error_type': 'JSONDecodeError'
            }, status=400)
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"КРИТИЧЕСКАЯ ОШИБКА при массовой деактивации:")
            print(f"Тип ошибки: {type(e).__name__}")
            print(f"Сообщение ошибки: {str(e)}")
            print(f"Полный traceback:\n{error_details}")
            
            return JsonResponse({
                'success': False,
                'message': f'Ошибка при деактивации: {str(e)}',
                'error_type': type(e).__name__,
                'traceback': error_details
            }, status=500)
    
    error_msg = 'Метод не поддерживается'
    print(f"ОШИБКА: {error_msg}")
    return JsonResponse({
        'success': False, 
        'message': error_msg
    }, status=405)

@login_required
def student_bulk_create_access_view(request):
    """Массовое создание доступа для студентов с подробным логированием"""
    print(f"=== student_bulk_create_access_view вызван ===")
    print(f"Метод запроса: {request.method}")
    print(f"MODELS_AVAILABLE: {MODELS_AVAILABLE}")
    
    if not MODELS_AVAILABLE:
        error_msg = 'Модели не загружены'
        print(f"ОШИБКА: {error_msg}")
        return JsonResponse({'success': False, 'message': error_msg}, status=500)
    
    if request.method == 'POST':
        try:
            print("Получаем данные из запроса...")
            data = json.loads(request.body)
            print(f"Данные запроса: {data}")
            
            mode = data.get('mode', 'selected')
            print(f"Режим операции: {mode}")
            
            if mode == 'all':
                print("=== Режим: создание доступа для ВСЕХ студентов с фильтрами ===")
                
                # Создаем доступ для всех студентов с учетом фильтров
                filters = data.get('filters', {})
                print(f"Применяемые фильтры: {filters}")
                
                students = Student.objects.filter(user__isnull=True)
                print(f"Студентов без аккаунтов в базе: {students.count()}")
                
                if filters.get('search'):
                    search = filters['search']
                    print(f"Применяем поиск: '{search}'")
                    students = students.filter(
                        Q(first_name__icontains=search) |
                        Q(last_name__icontains=search) |
                        Q(email__icontains=search)
                    )
                    print(f"После поиска студентов: {students.count()}")
                
                if filters.get('group'):
                    group_id = filters['group']
                    print(f"Применяем фильтр по группе: {group_id}")
                    students = students.filter(group_id=group_id)
                    print(f"После фильтра по группе студентов: {students.count()}")
                
            else:
                print("=== Режим: создание доступа для ВЫБРАННЫХ студентов ===")
                
                # Создаем доступ для выбранных студентов
                student_ids = data.get('student_ids', [])
                print(f"ID студентов для создания доступа: {student_ids}")
                
                if not student_ids:
                    print("Не указаны ID студентов")
                    return JsonResponse({
                        'success': False,
                        'message': 'Не указаны студенты для создания доступа'
                    }, status=400)
                
                students = Student.objects.filter(id__in=student_ids, user__isnull=True)
                print(f"Найдено студентов без аккаунтов: {students.count()}")
            
            if students.count() == 0:
                print("Нет студентов для создания доступа")
                return JsonResponse({
                    'success': True,
                    'message': 'Нет студентов без аккаунтов для создания доступа'
                })
            
            created_count = 0
            print("Создаем доступ для студентов...")
            for student in students:
                try:
                    print(f"Обрабатываем студента: {student.get_full_name()} (ID: {student.id})")
                    
                    # Создаем пользователя
                    username = generate_username(student.first_name, student.last_name)
                    password = generate_password()
                    print(f"  Создаем пользователя: {username}")
                    
                    user = User.objects.create_user(
                        username=username,
                        email=student.email,
                        first_name=student.first_name,
                        last_name=student.last_name,
                        password=password
                    )
                    print(f"  Пользователь создан с ID: {user.id}")
                    
                    student.user = user
                    student.save()
                    print(f"  Пользователь привязан к студенту")
                    
                    # Отправляем данные на email
                    try:
                        email_sent = send_credentials_email(student, username, password)
                        if email_sent:
                            print(f"  Email отправлен успешно")
                        else:
                            print(f"  Ошибка отправки email")
                    except Exception as email_error:
                        print(f"  ОШИБКА отправки email: {str(email_error)}")
                    
                    created_count += 1
                    print(f"  Доступ создан успешно")
                    
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    print(f"  ОШИБКА создания доступа для студента {student.id}:")
                    print(f"    Тип ошибки: {type(e).__name__}")
                    print(f"    Сообщение: {str(e)}")
                    print(f"    Traceback:\n{error_details}")
                    continue
            
            print(f"Создано аккаунтов: {created_count}")
            
            return JsonResponse({
                'success': True,
                'message': f'Создан доступ для {created_count} студентов',
                'created_count': created_count
            })
            
        except json.JSONDecodeError as e:
            error_msg = f'Ошибка парсинга JSON: {str(e)}'
            print(f"ОШИБКА JSON: {error_msg}")
            return JsonResponse({
                'success': False,
                'message': error_msg,
                'error_type': 'JSONDecodeError'
            }, status=400)
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"КРИТИЧЕСКАЯ ОШИБКА при массовом создании доступа:")
            print(f"Тип ошибки: {type(e).__name__}")
            print(f"Сообщение ошибки: {str(e)}")
            print(f"Полный traceback:\n{error_details}")
            
            return JsonResponse({
                'success': False,
                'message': f'Ошибка при создании доступа: {str(e)}',
                'error_type': type(e).__name__,
                'traceback': error_details
            }, status=500)
    
    error_msg = 'Метод не поддерживается'
    print(f"ОШИБКА: {error_msg}")
    return JsonResponse({
        'success': False, 
        'message': error_msg
    }, status=405)

@login_required
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
            search_lower = search.lower()
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
@login_required   
def student_redirect_view(request, student_id):
    """Редирект с уведомлением"""
    messages.info(request, 'Функция просмотра/редактирования студентов в разработке')
    return redirect('admin_students')

# Добавьте в admin_panel/views.py

@login_required
def student_dashboard_view(request):
    """Личный кабинет студента"""
    # Проверяем, является ли пользователь студентом
    try:
        student = request.user.student_profile
    except AttributeError:
        # Если у пользователя нет профиля студента
        messages.error(request, 'У вас нет доступа к личному кабинету студента')
        return redirect('login')
    
    # Получаем информацию о студенте
    context = {
        'student': student,
        'group': student.group,
        'faculty': student.group.faculty if student.group else None,
    }
    
    return render(request, 'student/dashboard.html', context)

def redirect_user_after_login(request):
    """Перенаправление пользователя в зависимости от его роли"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Если администратор или персонал
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_dashboard')
    
    # Если студент
    try:
        student = request.user.student_profile
        return redirect('student_dashboard')
    except AttributeError:
        pass
    
    # Если обычный пользователь без роли
    messages.warning(request, 'У вас нет назначенной роли в системе. Обратитесь к администратору.')
    return redirect('login')




# ====================================
# УТИЛИТЫ
# ====================================
@login_required
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
@login_required
def generate_password(length=8):
    """Генерация случайного пароля"""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

@login_required
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

Адрес входа: {settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000'}

С уважением,
Администрация МПТ
'''
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@mpt.ru',
            [student.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False



# views.py (добавляем к существующим views


def validate_faculty_code(code, faculty_id=None):
    """Валидация кода факультета в формате XX.XX.XX"""
    if not code:
        return 'Код специальности обязателен'
    
    code = code.strip()
    
    if len(code) > 8:
        return 'Код не может быть длиннее 8 символов'
    
    # Проверяем формат XX.XX.XX
    if not re.match(r'^\d{2}\.\d{2}\.\d{2}$', code):
        return 'Код должен быть в формате XX.XX.XX (например: 09.02.07)'
    
    # Проверяем уникальность
    existing_query = Faculty.objects.filter(code=code)
    if faculty_id:
        existing_query = existing_query.exclude(id=faculty_id)
    
    if existing_query.exists():
        return f'Факультет с кодом "{code}" уже существует'
    
    return None


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def faculties_list_view(request):
    """Список факультетов"""
    print(f"=== faculties_list_view вызван ===")
    print(f"Метод запроса: {request.method}")
    print(f"MODELS_AVAILABLE: {MODELS_AVAILABLE}")
    
    if not MODELS_AVAILABLE:
        error_msg = 'Модели недоступны. Обратитесь к администратору.'
        print(f"Ошибка: {error_msg}")
        messages.error(request, error_msg)
        return redirect('admin_dashboard')
    
    try:
        print("Получаем параметры фильтрации...")
        
        # Параметры фильтрации и поиска
        search = request.GET.get('search', '').strip()
        status_filter = request.GET.get('status', '')
        
        print(f"Поиск: '{search}'")
        print(f"Фильтр статуса: '{status_filter}'")
        
        # Выбранные факультеты для массовых операций
        selected_faculties = request.GET.get('selected', '').strip()
        selected_ids = []
        if selected_faculties:
            try:
                selected_ids = [int(x) for x in selected_faculties.split(',') if x.strip()]
            except ValueError:
                selected_ids = []
        
        print(f"Выбранные ID: {selected_ids}")
        
        # Базовый queryset БЕЗ аннотаций (так как они уже есть как @property)
        faculties = Faculty.objects.all()
        
        print("Применяем фильтры...")
        
        # Поиск по названию, коду или описанию
        if search:
            faculties = faculties.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Фильтр по статусу
        if status_filter == 'active':
            faculties = faculties.filter(is_active=True)
        elif status_filter == 'inactive':
            faculties = faculties.filter(is_active=False)
        
        # Сортировка
        faculties = faculties.order_by('name')
        
        # Подсчет общего количества
        total_faculties = faculties.count()
        
        print(f"Общее количество факультетов: {total_faculties}")
        
        # Пагинация
        paginator = Paginator(faculties, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        print(f"Страница: {page_obj.number} из {paginator.num_pages}")
        
        context = {
            'page_obj': page_obj,
            'search': search,
            'status_filter': status_filter,
            'total_faculties': total_faculties,
            'selected_faculties': selected_ids,
            'current_filters': {
                'search': search,
                'status': status_filter,
            },
        }
        
        print("Рендерим шаблон...")
        return render(request, 'admin_panel/faculty/faculties_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке факультетов: {str(e)}')
        print(f"Ошибка: {str(e)}")
        return redirect('admin_dashboard')


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def faculty_create_view(request):
    """Создание нового факультета"""
    print(f"=== faculty_create_view вызван ===")
    print(f"Метод запроса: {request.method}")
    print(f"MODELS_AVAILABLE: {MODELS_AVAILABLE}")
    
    if not MODELS_AVAILABLE:
        error_msg = 'Модели недоступны. Обратитесь к администратору.'
        print(f"Ошибка: {error_msg}")
        messages.error(request, error_msg)
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        print("Обработка POST запроса...")
        
        try:
            print("Получаем данные из формы...")
            
            # Получаем основные данные из формы
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip()
            description = request.POST.get('description', '').strip()
            is_active = bool(request.POST.get('is_active'))
            
            # НОВОЕ: Получаем профессии
            professions_input = request.POST.get('professions_input', '').strip()
            
            print(f"Название: '{name}'")
            print(f"Код: '{code}'")
            print(f"Описание: '{description}'")
            print(f"Активен: {is_active}")
            print(f"Профессии (текст): '{professions_input}'")
            
            # ОБРАБАТЫВАЕМ ПРОФЕССИИ:
            professions_list = []
            if professions_input:
                # Разбиваем по строкам и очищаем
                lines = professions_input.split('\n')
                for line in lines:
                    profession_name = line.strip()
                    if profession_name and len(profession_name) >= 2:
                        # Проверяем на дубликаты
                        existing_names = [p.lower() for p in professions_list]
                        if profession_name.lower() not in existing_names:
                            professions_list.append(profession_name)
            
            print(f"Обработанные профессии: {professions_list}")
            
            # Валидация
            print("Валидация данных...")
            errors = {}
            
            if not name:
                errors['name'] = 'Название обязательно'
            elif len(name) < 2:
                errors['name'] = 'Название должно содержать минимум 2 символа'
            elif len(name) > 200:
                errors['name'] = 'Название не может быть длиннее 200 символов'
            
            # Валидация кода с новой функцией
            code_error = validate_faculty_code(code)
            if code_error:
                errors['code'] = code_error
            
            if description and len(description) > 500:
                errors['description'] = 'Описание не может быть длиннее 500 символов'
            
            # ВАЛИДАЦИЯ ПРОФЕССИЙ:
            if not professions_list:
                errors['professions_input'] = 'Добавьте хотя бы одну профессию'
            elif len(professions_list) > 20:
                errors['professions_input'] = 'Максимум 20 профессий'
            
            # Проверяем длину названий профессий
            for prof in professions_list:
                if len(prof) > 150:
                    errors['professions_input'] = f'Название профессии "{prof[:30]}..." слишком длинное (максимум 150 символов)'
                    break
            
            print(f"Ошибки валидации: {errors}")
            
            if errors:
                # Сохраняем данные формы для повторного отображения
                for field, error in errors.items():
                    messages.error(request, f'{field}: {error}')
                
                context = {
                    'form_data': {
                        'name': name,
                        'code': code,
                        'description': description,
                        'professions_input': professions_input,
                        'is_active': is_active,
                    }
                }
                return render(request, 'admin_panel/faculty/faculty_create.html', context)
            
            # Создаем факультет
            print("Создаем новый факультет...")
            
            faculty_data = {
                'name': name,
                'code': code,
                'description': description,
                'professions': professions_list,  # JSON поле
                'is_active': is_active,
                'created_by': request.user
            }
            
            print(f"Данные факультета: {faculty_data}")
            
            # Создаем объект
            faculty = Faculty.objects.create(**faculty_data)
            print(f"Создан факультет с {len(professions_list)} профессиями! ID: {faculty.id}")
            
            messages.success(request, f'Специальность "{faculty.name}" создана с {len(professions_list)} профессиями')
            return redirect('admin_faculties')
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"ОШИБКА при создании факультета:")
            print(f"Тип ошибки: {type(e).__name__}")
            print(f"Сообщение: {str(e)}")
            print(f"Traceback:\n{error_details}")
            
            error_message = f'Ошибка при создании факультета: {str(e)}'
            messages.error(request, error_message)
            
            context = {
                'form_data': request.POST
            }
            return render(request, 'admin_panel/faculty/faculty_create.html', context)
    
    # GET запрос - показываем форму
    print("GET запрос - показываем форму создания...")
    context = {}
    return render(request, 'admin_panel/faculty/faculty_create.html', context)


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def faculty_detail_view(request, faculty_id):
    """Детальный просмотр факультета - HTML страница"""
    print(f"=== faculty_detail_view вызван для ID: {faculty_id} ===")
    
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели недоступны. Обратитесь к администратору.')
        return redirect('admin_dashboard')
    
    try:
        faculty = get_object_or_404(Faculty, id=faculty_id)
        print(f"Найден факультет: {faculty.name}")
        print(f"Профессий: {faculty.get_professions_count()}")
        
        # Получаем группы факультета с количеством студентов
        groups = faculty.group_set.annotate(
            students_count=Count('students')
        ).order_by('name')
        
        # НЕ присваиваем атрибуты, используем готовые @property
        # faculty.groups_count - уже есть как свойство
        # faculty.students_count - уже есть как свойство  
        # faculty.active_students_count - уже есть как свойство
        
        context = {
            'faculty': faculty,
            'groups': groups,
        }
        
        return render(request, 'admin_panel/faculty/faculty_detail.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке факультета: {str(e)}')
        print(f"Ошибка: {str(e)}")
        return redirect('admin_faculties')


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def faculty_edit_view(request, faculty_id):
    """Редактирование факультета - HTML страница"""
    print(f"=== faculty_edit_view вызван для ID: {faculty_id} ===")
    print(f"Метод запроса: {request.method}")
    print(f"MODELS_AVAILABLE: {MODELS_AVAILABLE}")
    
    if not MODELS_AVAILABLE:
        error_msg = 'Модели недоступны. Обратитесь к администратору.'
        print(f"Ошибка: {error_msg}")
        messages.error(request, error_msg)
        return redirect('admin_dashboard')
    
    try:
        print(f"Ищем факультет с ID: {faculty_id}")
        faculty = get_object_or_404(Faculty, id=faculty_id)
        print(f"Найден факультет: {faculty.name}")
        print(f"Профессий: {faculty.get_professions_count()}")
        
        # НЕ присваиваем атрибуты статистики - используем готовые @property
        # faculty.groups_count - уже есть
        # faculty.students_count - уже есть
        # faculty.active_students_count - уже есть
        
        if request.method == 'POST':
            print("Обработка POST запроса...")
            
            try:
                print("Получаем данные из формы...")
                
                # Получаем основные данные из формы
                name = request.POST.get('name', '').strip()
                code = request.POST.get('code', '').strip()
                description = request.POST.get('description', '').strip()
                is_active = request.POST.get('is_active') == 'true'
                
                # НОВОЕ: Получаем профессии
                professions_input = request.POST.get('professions_input', '').strip()
                
                print(f"Название: '{name}'")
                print(f"Код: '{code}'")
                print(f"Описание: '{description}'")
                print(f"Активен: {is_active}")
                print(f"Профессии (текст): '{professions_input}'")
                
                # ОБРАБАТЫВАЕМ ПРОФЕССИИ:
                professions_list = []
                if professions_input:
                    # Разбиваем по строкам и очищаем
                    lines = professions_input.split('\n')
                    for line in lines:
                        profession_name = line.strip()
                        if profession_name and len(profession_name) >= 2:
                            # Проверяем на дубликаты
                            existing_names = [p.lower() for p in professions_list]
                            if profession_name.lower() not in existing_names:
                                professions_list.append(profession_name)
                
                print(f"Обработанные профессии: {professions_list}")
                
                # Валидация
                print("Валидация данных...")
                errors = {}
                
                if not name:
                    errors['name'] = 'Название обязательно'
                elif len(name) < 2:
                    errors['name'] = 'Название должно содержать минимум 2 символа'
                elif len(name) > 200:
                    errors['name'] = 'Название не может быть длиннее 200 символов'
                
                # Валидация кода с новой функцией
                code_error = validate_faculty_code(code, faculty.id)
                if code_error:
                    errors['code'] = code_error
                
                if description and len(description) > 500:
                    errors['description'] = 'Описание не может быть длиннее 500 символов'
                
                # ВАЛИДАЦИЯ ПРОФЕССИЙ:
                if not professions_list:
                    errors['professions_input'] = 'Добавьте хотя бы одну профессию'
                elif len(professions_list) > 20:
                    errors['professions_input'] = 'Максимум 20 профессий'
                
                # Проверяем длину названий профессий
                for prof in professions_list:
                    if len(prof) > 150:
                        errors['professions_input'] = f'Название профессии "{prof[:30]}..." слишком длинное (максимум 150 символов)'
                        break
                
                print(f"Ошибки валидации: {errors}")
                
                if errors:
                    for field, error in errors.items():
                        messages.error(request, f'{field}: {error}')
                    # Не перенаправляем, показываем форму с ошибками
                
                else:
                    # Обновляем факультет
                    print("Обновляем факультет...")
                    
                    faculty.name = name
                    faculty.code = code
                    faculty.description = description
                    faculty.professions = professions_list  # Обновляем профессии
                    faculty.is_active = is_active
                    faculty.save()
                    
                    print(f"Факультет обновлен: {faculty.name}, профессий: {len(professions_list)}")
                    
                    messages.success(request, f'Специальность "{faculty.name}" успешно обновлена')
                    return redirect('admin_faculty_detail', faculty_id=faculty.id)
                        
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"ОШИБКА при обновлении факультета:")
                print(f"Тип ошибки: {type(e).__name__}")
                print(f"Сообщение: {str(e)}")
                print(f"Traceback:\n{error_details}")
                
                error_message = f'Ошибка при обновлении: {str(e)}'
                messages.error(request, error_message)
        
        # GET запрос или POST с ошибками - показываем форму
        print("Показываем форму редактирования...")
        
        context = {
            'faculty': faculty,
        }
        
        return render(request, 'admin_panel/faculty/faculty_edit.html', context)
        
    except Faculty.DoesNotExist:
        error_msg = 'Факультет не найден'
        messages.error(request, error_msg)
        return redirect('admin_faculties')
    except Exception as e:
        error_msg = f'Ошибка: {str(e)}'
        print(f"Общая ошибка: {error_msg}")
        messages.error(request, error_msg)
        return redirect('admin_faculties')


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def faculty_delete_view(request, faculty_id):
    """Удаление факультета"""
    print(f"=== faculty_delete_view вызван для ID: {faculty_id} ===")
    
    if not MODELS_AVAILABLE:
        return JsonResponse({
            'success': False, 
            'message': 'Модели недоступны'
        }, status=500)
    
    if request.method == 'POST':
        try:
            faculty = get_object_or_404(Faculty, id=faculty_id)
            faculty_name = faculty.name
            
            print(f"Найден факультет: {faculty_name}")
            
            # Проверяем связанные данные
            groups_count = faculty.group_set.count()
            students_count = Student.objects.filter(group__faculty=faculty).count()
            
            if groups_count > 0 or students_count > 0:
                return JsonResponse({
                    'success': False,
                    'message': f'Нельзя удалить специальность "{faculty_name}". '
                              f'К ней привязано групп: {groups_count}, студентов: {students_count}. '
                              f'Сначала удалите или переместите связанные данные.',
                    'groups_count': groups_count,
                    'students_count': students_count
                })
            
            # Удаляем факультет
            faculty.delete()
            print(f"Специальность удалена: {faculty_name}")
            
            return JsonResponse({
                'success': True,
                'message': f'Специальность "{faculty_name}" успешно удалена'
            })
                
        except Faculty.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Специальность не найдена'
            }, status=404)
        except Exception as e:
            print(f"ОШИБКА при удалении специальности {faculty_id}: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Ошибка при удалении: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Метод не разрешен'
    }, status=405)


# admin_panel/views.py - добавьте в конец файла

@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def backups_list_view(request):
    """Список резервных копий"""
    print("=== backups_list_view вызван ===")
    
    try:
        # Получаем все бэкапы
        backups = Backup.objects.all().order_by('-created_at')
        
        # Пагинация
        paginator = Paginator(backups, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Статистика
        backup_service = BackupService()
        stats = backup_service.get_backup_statistics()
        
        context = {
            'page_obj': page_obj,
            'stats': stats,
        }
        
        return render(request, 'admin_panel/backups/backups_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке резервных копий: {str(e)}')
        return redirect('admin_dashboard')


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def backup_create_view(request):
    """Создание резервной копии"""
    print("=== backup_create_view вызван ===")
    
    if request.method == 'POST':
        try:
            description = request.POST.get('description', '').strip()
            
            backup_service = BackupService()
            backup = backup_service.create_backup(
                backup_type='manual',
                user=request.user,
                description=description
            )
            
            if backup:
                messages.success(request, f'Резервная копия "{backup.name}" создана успешно')
            else:
                messages.error(request, 'Ошибка при создании резервной копии')
                
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')
    
    return redirect('admin_backups')


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def backup_delete_view(request, backup_id):
    """Удаление резервной копии"""
    print(f"=== backup_delete_view вызван для ID: {backup_id} ===")
    
    if request.method == 'POST':
        try:
            backup_service = BackupService()
            
            if backup_service.delete_backup(backup_id):
                return JsonResponse({
                    'success': True,
                    'message': 'Резервная копия удалена'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Ошибка при удалении'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Ошибка: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Метод не разрешен'})


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def backup_download_view(request, backup_id):
    """Скачивание резервной копии"""
    try:
        backup = get_object_or_404(Backup, id=backup_id)
        
        if not backup.file_exists:
            messages.error(request, 'Файл резервной копии не найден')
            return redirect('admin_backups')
        
        # Отдаем файл для скачивания
        with open(backup.file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/gzip')
            response['Content-Disposition'] = f'attachment; filename="{backup.name}"'
            return response
            
    except Exception as e:
        messages.error(request, f'Ошибка при скачивании: {str(e)}')
        return redirect('admin_backups')
# admin_panel/views.py - добавьте в конец файла

from admin_panel.services.backup_service import BackupService
from admin_panel.models import Backup

@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def backups_list_view(request):
    """Список резервных копий"""
    print("=== backups_list_view вызван ===")
    
    try:
        # Получаем все бэкапы
        backups = Backup.objects.all().order_by('-created_at')
        
        # Пагинация
        paginator = Paginator(backups, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Статистика
        backup_service = BackupService()
        stats = backup_service.get_backup_statistics()
        
        context = {
            'page_obj': page_obj,
            'stats': stats,
        }
        
        return render(request, 'admin_panel/backups/backups_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке резервных копий: {str(e)}')
        return redirect('admin_dashboard')


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def backup_create_view(request):
    """Создание резервной копии"""
    print("=== backup_create_view вызван ===")
    
    if request.method == 'POST':
        try:
            description = request.POST.get('description', '').strip()
            
            backup_service = BackupService()
            backup = backup_service.create_backup(
                backup_type='manual',
                user=request.user,
                description=description
            )
            
            if backup:
                messages.success(request, f'Резервная копия "{backup.name}" создана успешно')
            else:
                messages.error(request, 'Ошибка при создании резервной копии')
                
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')
    
    return redirect('admin_backups')


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def backup_delete_view(request, backup_id):
    """Удаление резервной копии"""
    print(f"=== backup_delete_view вызван для ID: {backup_id} ===")
    
    if request.method == 'POST':
        try:
            backup_service = BackupService()
            
            if backup_service.delete_backup(backup_id):
                return JsonResponse({
                    'success': True,
                    'message': 'Резервная копия удалена'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Ошибка при удалении'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Ошибка: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Метод не разрешен'})


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def backup_download_view(request, backup_id):
    """Скачивание резервной копии"""
    try:
        backup = get_object_or_404(Backup, id=backup_id)
        
        if not backup.file_exists:
            messages.error(request, 'Файл резервной копии не найден')
            return redirect('admin_backups')
        
        # Отдаем файл для скачивания
        with open(backup.file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/gzip')
            response['Content-Disposition'] = f'attachment; filename="{backup.name}"'
            return response
            
    except Exception as e:
        messages.error(request, f'Ошибка при скачивании: {str(e)}')
        return redirect('admin_backups')










@login_required
def groups_main_view(request):
    search_query = request.GET.get('search', '').strip()
    specialty_filter = request.GET.get('specialty', '').strip()
    profession_filter = request.GET.get('profession', '').strip()
    course_filter = request.GET.get('course', '').strip() or '1'

    faculties = list(Faculty.objects.filter(is_active=True).order_by('name'))
    all_faculties = faculties  # нужно в шаблон

    faculty_ids = [faculty.id for faculty in faculties]
    profession_sets = {
        faculty.id: set(p for p in (faculty.get_professions_list() or []) if p)
        for faculty in faculties
    }

    if faculty_ids:
        for faculty_id, profession in (
            Group.objects.filter(faculty_id__in=faculty_ids)
            .values_list('faculty_id', 'profession')
            .distinct()
        ):
            if profession:
                profession_sets.setdefault(faculty_id, set()).add(profession)

    specialties_data = {
        str(faculty.id): {
            'name': faculty.name,
            'professions': sorted(profession_sets.get(faculty.id, set()))
        }
        for faculty in faculties
    }

    groups_data = []
    total_groups = 0
    total_students = 0

    for faculty in faculties:
        if specialty_filter and str(faculty.id) != specialty_filter:
            continue

        # 1) Берём из JSON
        faculty_professions = set(faculty.get_professions_list() or [])
        # 2) Добавляем фактические профессии из групп
        group_professions = set(
            Group.objects.filter(faculty=faculty)
            .values_list('profession', flat=True)
            .distinct()
        )
        all_professions = sorted(p for p in (faculty_professions | group_professions) if p)

        faculty_data = {'faculty': faculty, 'professions': []}

        # Если вообще нет профессий ни в JSON, ни в группах — показываем пустой блок
        if not all_professions:
            groups_data.append(faculty_data)
            continue

        for profession in all_professions:
            if profession_filter and profession != profession_filter:
                continue

            groups = Group.objects.filter(
                faculty=faculty,
                profession=profession,
                is_active=True
            ).annotate(total_students=Count('students')).order_by('code')

            filtered_groups = []
            for group in groups:
                course = group.current_course
                if course_filter and str(course) != course_filter:
                    continue
                if search_query:
                    q = search_query.lower()
                    if not (q in group.code.lower() or q in faculty.name.lower() or q in profession.lower()):
                        continue
                filtered_groups.append({
                    'group': group,
                    'current_course': course,
                    'students_count': group.total_students
                })

            profession_entry = {
                'name': profession,
                'groups': filtered_groups,
                'groups_count': len(filtered_groups),
                'total_students': sum(g['students_count'] for g in filtered_groups),
            }

            faculty_data['professions'].append(profession_entry)

            if filtered_groups:
                total_groups += len(filtered_groups)
                total_students += profession_entry['total_students']

        groups_data.append(faculty_data)

    faculties_with_professions = sum(1 for data in groups_data if data['professions'])

    context = {
        'groups_data': groups_data,
        'faculties': faculties,
        'all_faculties': all_faculties,  # важно для шаблона фильтра
        'total_faculties': faculties_with_professions,
        'total_groups': total_groups,
        'total_students': total_students,
        'search_query': search_query,
        'specialty_filter': specialty_filter,
        'profession_filter': profession_filter,
        'course_filter': course_filter,
        'specialties_data_json': json.dumps(specialties_data, ensure_ascii=False),
    }
    return render(request, 'admin_panel/groups/groups_main.html', context)

@login_required
def group_create_view(request):
    faculties = Faculty.objects.filter(is_active=True).order_by('name')
    students = Student.objects.filter(group__isnull=True).order_by('last_name', 'first_name')
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        faculty_id = request.POST.get('faculty', '').strip()
        profession = request.POST.get('profession', '').strip()
        enrollment_date = request.POST.get('enrollment_date')
        graduation_date = request.POST.get('graduation_date')
        selected_student_ids = request.POST.getlist('students')

        faculty = get_object_or_404(Faculty, id=faculty_id)
        group = Group(code=code, name=code, faculty=faculty, profession=profession, is_active=True)
        try:
            with transaction.atomic():
                if enrollment_date:
                    group.enrollment_date = datetime.strptime(enrollment_date, '%Y-%m-%d').date()
                if graduation_date:
                    group.graduation_date = datetime.strptime(graduation_date, '%Y-%m-%d').date()
                group.save()

                if selected_student_ids:
                    students_to_assign = Student.objects.filter(id__in=selected_student_ids)
                    for student in students_to_assign:
                        student.group = group
                        if group.enrollment_date:
                            student.enrollment_date = group.enrollment_date
                        if group.graduation_date:
                            student.graduation_date = group.graduation_date
                        student.save()

            messages.success(request, 'Группа успешно создана')
            
            query = urlencode({
                'search': group.code,
                'course': group.current_course or 1,
            })
            redirect_url = f"{reverse('groups_main')}?{query}"
            return redirect(redirect_url)
        except Exception as e:
            messages.error(request, f'Ошибка при создании группы: {str(e)}')

    context = {
        'faculties': faculties,
        'students': students,
    }
    return render(request, 'admin_panel/groups/group_create.html', context)

@login_required
def group_edit_view(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    faculties = Faculty.objects.filter(is_active=True).order_by('name')
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        faculty_id = request.POST.get('faculty', '').strip()
        profession = request.POST.get('profession', '').strip()
        enrollment_date = request.POST.get('enrollment_date')
        graduation_date = request.POST.get('graduation_date')
        is_active = request.POST.get('is_active') == 'on'

        faculty = get_object_or_404(Faculty, id=faculty_id)
        group.code = code
        group.name = code
        group.faculty = faculty
        group.profession = profession
        group.is_active = is_active
        try:
            if enrollment_date:
                group.enrollment_date = datetime.strptime(enrollment_date, '%Y-%m-%d').date()
            if graduation_date:
                group.graduation_date = datetime.strptime(graduation_date, '%Y-%m-%d').date()
            group.save()
            messages.success(request, 'Группа успешно обновлена')
            return redirect('group_detail', group_id=group.id)
        except Exception as e:
            messages.error(request, f'Ошибка при сохранении: {str(e)}')
    students = group.students.all().order_by('last_name', 'first_name')
    students_without_group = Student.objects.filter(group__isnull=True).order_by('last_name', 'first_name')
    other_groups = Group.objects.exclude(id=group.id).filter(is_active=True).order_by('code')
    context = {
        'group': group,
        'faculties': faculties,
        'students': students,
        'students_without_group': students_without_group,
        'other_groups': other_groups,
        'total_students': students.count(),
        'students_without_group_count': students_without_group.count(),
    }
    return render(request, 'admin_panel/groups/group_edit.html', context)

@login_required
def group_detail_view(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    students = group.students.all().order_by('last_name', 'first_name')
    context = {
        'group': group,
        'students': students,
    }
    return render(request, 'admin_panel/groups/group_detail.html', context)

# API-операции для управления студентами в группе
@login_required
@require_POST
def transfer_student_api(request):
    try:
        data = json.loads(request.body or '{}')
        student_id = data.get('student_id')
        target_group_id = data.get('target_group_id')

        if not student_id or not target_group_id:
            return JsonResponse({'success': False, 'error': 'Не указаны студент или целевая группа'}, status=400)

        student = get_object_or_404(Student, id=student_id)
        target_group = get_object_or_404(Group, id=target_group_id)

        if student.group_id == target_group.id:
            return JsonResponse({'success': False, 'error': 'Студент уже состоит в этой группе'}, status=400)

        with transaction.atomic():
            student.group = target_group
            if target_group.enrollment_date:
                student.enrollment_date = target_group.enrollment_date
            if target_group.graduation_date:
                student.graduation_date = target_group.graduation_date
            student.save()

        return JsonResponse({'success': True, 'message': 'Студент успешно переведен'})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)


@login_required
@require_POST
def remove_student_from_group_api(request):
    try:
        data = json.loads(request.body or '{}')
        student_id = data.get('student_id')

        if not student_id:
            return JsonResponse({'success': False, 'error': 'Не указан студент'}, status=400)

        student = get_object_or_404(Student, id=student_id)

        with transaction.atomic():
            student.group = None
            if hasattr(student, 'study_status'):
                student.study_status = 'expelled'
            student.save()

        return JsonResponse({'success': True, 'message': 'Студент исключён из группы'})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)


@login_required
@require_POST
def add_student_to_group_api(request, group_id):
    try:
        data = json.loads(request.body or '{}')
        student_id = data.get('student_id')

        if not student_id:
            return JsonResponse({'success': False, 'error': 'Не указан студент'}, status=400)

        group = get_object_or_404(Group, id=group_id)
        student = get_object_or_404(Student, id=student_id)

        if student.group_id == group.id:
            return JsonResponse({'success': False, 'error': 'Студент уже состоит в этой группе'}, status=400)

        if student.group_id:
            return JsonResponse({'success': False, 'error': 'Студент уже состоит в другой группе'}, status=400)

        with transaction.atomic():
            student.group = group
            if group.enrollment_date:
                student.enrollment_date = group.enrollment_date
            if group.graduation_date:
                student.graduation_date = group.graduation_date
            student.save()

        return JsonResponse({'success': True, 'message': 'Студент добавлен в группу'})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)
