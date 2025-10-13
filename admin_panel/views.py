# admin_panel/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
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
import uuid
from datetime import datetime
import tempfile
import os

# Безопасная проверка импорта моделей
try:
    from .models import Student, Group, Faculty
    MODELS_AVAILABLE = True
except:
    MODELS_AVAILABLE = False

# ====================================
# ОСНОВНЫЕ VIEWS
# ====================================

def dashboard_view(request):
    """Главная страница админки"""
    students_count = 0
    groups_count = 0
    
    if MODELS_AVAILABLE:
        try:
            students_count = Student.objects.count()
            groups_count = Group.objects.filter(is_active=True).count()
        except:
            students_count = 0
            groups_count = 0
    
    context = {
        'students_count': students_count,
        'teachers_count': 0,
        'groups_count': groups_count,
        'subjects_count': 0,
    }
    return render(request, 'admin_panel/dashboard.html', context)

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
        course_filter = request.GET.get('course', '')
        
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
        
        # Фильтр по курсу
        if course_filter:
            students = students.filter(course=course_filter)
        
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
        for group in groups:
            group.students_count = group.students.count()
        
        context = {
            'page_obj': page_obj,
            'groups': groups,
            'search': search,
            'group_filter': group_filter,
            'status_filter': status_filter,
            'course_filter': course_filter,
            'course_choices': Student._meta.get_field('course').choices,
            'status_choices': Student._meta.get_field('study_status').choices,
            'total_students': total_students,
            'selected_students': selected_ids,
            'current_filters': {
                'search': search,
                'group': group_filter,
                'status': status_filter,
                'course': course_filter,
            }
        }
        
        return render(request, 'admin_panel/students/students_list.html', context)
    
    except Exception as e:
        messages.error(request, f'Ошибка загрузки студентов: {str(e)}')
        return redirect('admin_dashboard')

# ====================================
# СТУДЕНТЫ - HTML СТРАНИЦЫ
# ====================================

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



# ====================================
# ЗАГЛУШКИ ДЛЯ ФАКУЛЬТЕТОВ
# ====================================

def faculties_list_view(request):
    """Список факультетов"""
    return HttpResponse("<h1>Страница факультетов в разработке</h1><a href='/'>← На главную</a>")

def faculty_create_view(request):
    """Создание факультета"""
    return HttpResponse("<h1>Создание факультета в разработке</h1><a href='/'>← На главную</a>")

def faculty_import_view(request):
    """Импорт факультетов"""
    return HttpResponse("<h1>Импорт факультетов в разработке</h1><a href='/'>← На главную</a>")



# ====================================
# УТИЛИТЫ
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



# views.py (добавляем к существующим views)

def faculties_list_view(request):
    """Список факультетов"""
    # Простая проверка доступности моделей
    try:
        Faculty.objects.all()[:1]
    except Exception as e:
        messages.error(request, f'Модели недоступны: {str(e)}')
        return redirect('admin_dashboard')
    
    try:
        # Поиск и фильтры
        search = request.GET.get('search', '').strip()
        status_filter = request.GET.get('status', '')
        
        # Базовый queryset
        faculties = Faculty.objects.all()
        
        # Применяем поиск
        if search:
            faculties = faculties.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Применяем фильтры
        if status_filter == 'active':
            faculties = faculties.filter(is_active=True)
        elif status_filter == 'inactive':
            faculties = faculties.filter(is_active=False)
        
        # Сортировка
        faculties = faculties.order_by('name')
        
        # ИСПРАВЛЕНО: Создаем список словарей вместо изменения объектов
        faculty_list = []
        for faculty in faculties:
            try:
                # Считаем группы (безопасно)
                groups_count = 0
                students_count = 0
                active_students_count = 0
                
                # Если есть связь с группами
                if hasattr(faculty, 'group_set'):
                    groups_count = faculty.group_set.count()
                    
                    # Считаем студентов через группы
                    students_count = Student.objects.filter(group__faculty=faculty).count()
                    active_students_count = Student.objects.filter(
                        group__faculty=faculty, 
                        study_status='active'
                    ).count()
                
                # Создаем объект для шаблона с дополнительными атрибутами
                faculty_data = {
                    'object': faculty,
                    'id': faculty.id,
                    'name': faculty.name,
                    'code': faculty.code,
                    'description': faculty.description,
                    'is_active': faculty.is_active,
                    'created_at': faculty.created_at,
                    'groups_count': groups_count,
                    'students_count': students_count,
                    'active_students_count': active_students_count,
                }
                
                faculty_list.append(faculty_data)
                
            except Exception as e:
                # Если ошибка с конкретным факультетом, добавляем с нулевыми значениями
                faculty_data = {
                    'object': faculty,
                    'id': faculty.id,
                    'name': faculty.name,
                    'code': faculty.code,
                    'description': getattr(faculty, 'description', ''),
                    'is_active': faculty.is_active,
                    'created_at': faculty.created_at,
                    'groups_count': 0,
                    'students_count': 0,
                    'active_students_count': 0,
                }
                faculty_list.append(faculty_data)
        
        # Общая статистика
        total_faculties = len(faculty_list)
        
        # Пагинация
        paginator = Paginator(faculty_list, 20)
        page_number = request.GET.get('page', 1)
        
        try:
            page_obj = paginator.get_page(page_number)
        except Exception:
            page_obj = paginator.get_page(1)
        
        context = {
            'page_obj': page_obj,
            'search': search,
            'status_filter': status_filter,
            'total_faculties': total_faculties,
            'current_filters': {
                'search': search,
                'status': status_filter,
            },
        }
        
        return render(request, 'admin_panel/faculity/faculties_list.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при загрузке факультетов: {str(e)}')
        # Создаем пустой контекст для отображения пустой страницы
        context = {
            'page_obj': None,
            'search': '',
            'status_filter': '',
            'total_faculties': 0,
            'current_filters': {
                'search': '',
                'status': '',
            },
        }
        return render(request, 'admin_panel/faculity/faculties_list.html', context)

   

def faculty_create_view(request):
    """Создание нового факультета"""
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели недоступны. Обратитесь к администратору.')
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            description = request.POST.get('description', '').strip()
            is_active = request.POST.get('is_active') == 'on'  # checkbox
            
            # Валидация
            errors = {}
            
            if not name:
                errors['name'] = 'Название факультета обязательно'
            elif len(name) > 200:
                errors['name'] = 'Название слишком длинное (максимум 200 символов)'
            
            if not code:
                errors['code'] = 'Код факультета обязателен'
            elif len(code) > 10:
                errors['code'] = 'Код слишком длинный (максимум 10 символов)'
            elif Faculty.objects.filter(code=code).exists():
                errors['code'] = f'Факультет с кодом "{code}" уже существует'
            
            if description and len(description) > 500:
                errors['description'] = 'Описание слишком длинное (максимум 500 символов)'
            
            # Если есть ошибки, возвращаем их
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                    'message': 'Исправьте ошибки в форме'
                })
            
            # Создаем факультет
            with transaction.atomic():
                created_by = request.user if request.user.is_authenticated else None
                
                faculty = Faculty.objects.create(
                    name=name,
                    code=code,
                    description=description,
                    is_active=is_active,
                    created_by=created_by
                )
                
                # Возвращаем успешный ответ
                return JsonResponse({
                    'success': True,
                    'message': f'Факультет "{faculty.name}" успешно создан!',
                    'redirect_url': reverse('admin_faculties'),
                    'faculty_id': faculty.id
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Ошибка при создании факультета: {str(e)}'
            })
    
    # GET запрос - показываем форму создания
    context = {}
    return render(request, 'admin_panel/faculity/faculty_create.html', context)

def faculty_edit_view(request, pk):
    """Редактирование факультета"""
    try:
        faculty = Faculty.objects.get(pk=pk)
    except Faculty.DoesNotExist:
        messages.error(request, 'Факультет не найден')
        return redirect('admin_faculties')
    
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            description = request.POST.get('description', '').strip()
            is_active = request.POST.get('is_active') == 'on'
            
            # Валидация
            errors = {}
            if not name:
                errors['name'] = 'Название факультета обязательно'
            if not code:
                errors['code'] = 'Код факультета обязателен'
            elif len(code) > 10:
                errors['code'] = 'Код не должен превышать 10 символов'
            elif Faculty.objects.filter(code=code).exclude(pk=pk).exists():
                errors['code'] = 'Факультет с таким кодом уже существует'
            
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                    'message': 'Исправьте ошибки в форме'
                })
            
            # Обновляем данные
            faculty.name = name
            faculty.code = code
            faculty.description = description
            faculty.is_active = is_active
            faculty.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Факультет "{faculty.name}" успешно обновлен',
                'redirect_url': reverse('admin_faculties')
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Ошибка при обновлении факультета: {str(e)}'
            })
    
    # GET запрос - показываем форму
    context = {
        'faculty': faculty
    }
    return render(request, 'admin_panel/faculity/faculty_edit.html', context)

def faculty_delete_view(request, pk):
    """Удаление факультета"""
    if request.method == 'POST':
        try:
            faculty = Faculty.objects.get(pk=pk)
            
            # Проверяем связанные данные
            groups_count = faculty.group_set.count()
            students_count = Student.objects.filter(group__faculty=faculty).count()
            
            if groups_count > 0 or students_count > 0:
                return JsonResponse({
                    'success': False,
                    'message': f'Нельзя удалить факультет. К нему привязано {groups_count} групп и {students_count} студентов. Сначала переведите их на другие факультеты.'
                })
            
            # Удаляем факультет
            faculty_name = faculty.name
            faculty.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Факультет "{faculty_name}" успешно удален'
            })
            
        except Faculty.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Факультет не найден'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Ошибка при удалении факультета: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Неверный метод запроса'})

def faculty_toggle_status_view(request, pk):
    """Переключение статуса активности факультета"""
    if request.method == 'POST':
        try:
            faculty = Faculty.objects.get(pk=pk)
            
            # Переключаем статус
            faculty.is_active = not faculty.is_active
            faculty.save()
            
            status_text = "активирован" if faculty.is_active else "деактивирован"
            
            return JsonResponse({
                'success': True,
                'message': f'Факультет "{faculty.name}" {status_text}',
                'is_active': faculty.is_active
            })
            
        except Faculty.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Факультет не найден'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Ошибка при изменении статуса: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Неверный метод запроса'})

@require_http_methods(["POST"])
def faculties_bulk_delete_view(request):
    """Массовое удаление факультетов"""
    try:
        data = json.loads(request.body)
        faculty_ids = data.get('faculty_ids', [])
        
        if not faculty_ids:
            return JsonResponse({
                'success': False,
                'message': 'Не выбраны факультеты для удаления'
            })
        
        # Получаем факультеты
        faculties = Faculty.objects.filter(id__in=faculty_ids)
        
        # Проверяем связанные данные
        protected_faculties = []
        for faculty in faculties:
            groups_count = faculty.group_set.count()
            students_count = Student.objects.filter(group__faculty=faculty).count()
            if groups_count > 0 or students_count > 0:
                protected_faculties.append({
                    'name': faculty.name,
                    'groups': groups_count,
                    'students': students_count
                })
        
        if protected_faculties:
            message = "Следующие факультеты нельзя удалить:\n"
            for faculty in protected_faculties:
                message += f"• {faculty['name']}: {faculty['groups']} групп, {faculty['students']} студентов\n"
            message += "Сначала переведите связанные данные на другие факультеты."
            
            return JsonResponse({
                'success': False,
                'message': message
            })
        
        # Удаляем факультеты
        deleted_count = len(faculties)
        faculties.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Удалено факультетов: {deleted_count}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при массовом удалении: {str(e)}'
        })

@require_http_methods(["POST"])
def faculties_bulk_update_status_view(request):
    """Массовое изменение статуса факультетов"""
    try:
        data = json.loads(request.body)
        faculty_ids = data.get('faculty_ids', [])
        action = data.get('action')
        
        if not faculty_ids:
            return JsonResponse({
                'success': False,
                'message': 'Не выбраны факультеты для изменения статуса'
            })
        
        if action not in ['activate', 'deactivate']:
            return JsonResponse({
                'success': False,
                'message': 'Неверное действие'
            })
        
        # Обновляем статус
        is_active = action == 'activate'
        updated_count = Faculty.objects.filter(id__in=faculty_ids).update(is_active=is_active)
        
        action_text = "активированы" if is_active else "деактивированы"
        
        return JsonResponse({
            'success': True,
            'message': f'Факультеты {action_text}: {updated_count}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при массовом изменении статуса: {str(e)}'
        })

def faculty_detail_view(request, pk):
    """Детальная информация о факультете"""
    try:
        faculty = Faculty.objects.get(pk=pk)
        
        # Получаем группы факультета
        groups = faculty.group_set.all().order_by('name')
        
        # Получаем статистику
        total_groups = groups.count()
        total_students = Student.objects.filter(group__faculty=faculty).count()
        active_students = Student.objects.filter(group__faculty=faculty, study_status='active').count()
        
        # Получаем преподавателей (если модель Teacher уже создана)
        # teachers = Teacher.objects.filter(faculty=faculty)
        
        context = {
            'faculty': faculty,
            'groups': groups,
            'total_groups': total_groups,
            'total_students': total_students,
            'active_students': active_students,
            # 'teachers': teachers,
        }
        
        return render(request, 'admin_panel/faculty_detail.html', context)
        
    except Faculty.DoesNotExist:
        messages.error(request, 'Факультет не найден')
        return redirect('admin_faculties')

def faculties_export_view(request):
    """Экспорт списка факультетов в Excel"""
    try:
        # Получаем те же фильтры что и в списке
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        
        # Базовый queryset
        faculties = Faculty.objects.all()
        
        # Применяем фильтры
        if search:
            faculties = faculties.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        if status_filter == 'active':
            faculties = faculties.filter(is_active=True)
        elif status_filter == 'inactive':
            faculties = faculties.filter(is_active=False)
        
        faculties = faculties.order_by('name')
        
        # Создаем DataFrame
        data = []
        for faculty in faculties:
            groups_count = faculty.group_set.count()
            students_count = Student.objects.filter(group__faculty=faculty).count()
            active_students_count = Student.objects.filter(
                group__faculty=faculty, 
                study_status='active'
            ).count()
            
            data.append({
                'Название': faculty.name,
                'Код': faculty.code,
                'Описание': faculty.description or '',
                'Статус': 'Активный' if faculty.is_active else 'Неактивный',
                'Количество групп': groups_count,
                'Всего студентов': students_count,
                'Активных студентов': active_students_count,
                'Дата создания': faculty.created_at.strftime('%d.%m.%Y %H:%M') if faculty.created_at else '',
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
        response['Content-Disposition'] = f'attachment; filename="faculties_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Ошибка при экспорте: {str(e)}')
        return redirect('admin_faculties')

def faculty_import_view(request):
    """Импорт факультетов из Excel файла"""
    if request.method == 'POST' and request.FILES.get('excel_file'):
        try:
            excel_file = request.FILES['excel_file']
            
            # Проверяем формат файла
            if excel_file.name.endswith('.xlsx') or excel_file.name.endswith('.xls'):
                df = pd.read_excel(excel_file)
            else:
                messages.error(request, 'Поддерживаются только файлы .xlsx и .xls')
                return redirect('admin_faculty_import')
            
            # Проверяем наличие обязательных столбцов
            required_columns = ['Название', 'Код']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                messages.error(request, f'Отсутствуют обязательные столбцы: {", ".join(missing_columns)}')
                return redirect('admin_faculty_import')
            
            # Обрабатываем данные
            errors = []
            faculties_data = []
            
            for index, row in df.iterrows():
                row_num = index + 2  # Учитываем заголовок
                
                # Проверяем обязательные поля
                if pd.isna(row['Название']) or not str(row['Название']).strip():
                    errors.append(f'Строка {row_num}: отсутствует название факультета')
                    continue
                
                if pd.isna(row['Код']) or not str(row['Код']).strip():
                    errors.append(f'Строка {row_num}: отсутствует код факультета')
                    continue
                
                # Собираем данные факультета
                faculty_data = {
                    'name': str(row['Название']).strip(),
                    'code': str(row['Код']).strip().upper(),
                    'description': str(row['Описание']).strip() if not pd.isna(row.get('Описание')) else '',
                    'is_active': True,  # По умолчанию активный
                    'row_num': row_num
                }
                
                # Обрабатываем статус если есть
                if 'Активный' in row and not pd.isna(row['Активный']):
                    status_str = str(row['Активный']).lower().strip()
                    faculty_data['is_active'] = status_str in ['да', 'yes', 'true', '1', 'активный']
                
                # Валидация
                if len(faculty_data['name']) > 200:
                    errors.append(f'Строка {row_num}: название слишком длинное (максимум 200 символов)')
                    continue
                
                if len(faculty_data['code']) > 10:
                    errors.append(f'Строка {row_num}: код слишком длинный (максимум 10 символов)')
                    continue
                
                # Проверяем уникальность кода
                if Faculty.objects.filter(code=faculty_data['code']).exists():
                    errors.append(f'Строка {row_num}: факультет с кодом "{faculty_data["code"]}" уже существует')
                    continue
                
                faculties_data.append(faculty_data)
            
            # Если есть ошибки, показываем первые 10
            if errors:
                for error in errors[:10]:
                    messages.error(request, error)
                if len(errors) > 10:
                    messages.error(request, f'И еще {len(errors) - 10} ошибок...')
                return redirect('admin_faculty_import')
            
            # Если нет данных для импорта
            if not faculties_data:
                messages.error(request, 'Нет данных для импорта')
                return redirect('admin_faculty_import')
            
            # Создаем факультеты
            with transaction.atomic():
                created_count = 0
                duplicate_count = 0
                
                for faculty_data in faculties_data:
                    try:
                        # Проверяем еще раз на дубликаты (может появиться между операциями)
                        if Faculty.objects.filter(code=faculty_data['code']).exists():
                            duplicate_count += 1
                            continue
                        
                        # Создаем факультет
                        created_by = request.user if request.user.is_authenticated else None
                        Faculty.objects.create(
                            name=faculty_data['name'],
                            code=faculty_data['code'],
                            description=faculty_data['description'],
                            is_active=faculty_data['is_active'],
                            created_by=created_by
                        )
                        created_count += 1
                        
                    except Exception as e:
                        messages.error(request, f'Строка {faculty_data["row_num"]}: ошибка создания - {str(e)}')
                
                # Результаты импорта
                if created_count > 0:
                    messages.success(request, f'Успешно создано факультетов: {created_count}')
                if duplicate_count > 0:
                    messages.warning(request, f'Пропущено дубликатов: {duplicate_count}')
                
                return JsonResponse({
                    'success': True,
                    'created': created_count,
                    'duplicates': duplicate_count,
                    'errors': [],
                    'errors_count': 0
                })
                
        except Exception as e:
            messages.error(request, f'Ошибка при обработке файла: {str(e)}')
            return redirect('admin_faculty_import')
    
    # GET запрос - показываем форму импорта
    context = {
        'sample_data': [
            {'Название': 'Информационных технологий', 'Код': 'ИТ', 'Описание': 'Факультет информационных технологий', 'Активный': 'да'},
            {'Название': 'Экономический', 'Код': 'ЭК', 'Описание': 'Экономический факультет', 'Активный': 'да'},
            {'Название': 'Механический', 'Код': 'МЕХ', 'Описание': 'Механический факультет', 'Активный': 'нет'},
        ]
    }
    return render(request, 'admin_panel/faculity/faculty_import.html', context)


def download_faculty_sample_excel(request):
    """Скачивание образца Excel файла для импорта факультетов"""
    try:
        # Создаем DataFrame с примером данных
        sample_data = {
            'Название': [
                'Информационных технологий',
                'Экономический', 
                'Механический'
            ],
            'Код': [
                'ИТ',
                'ЭК',
                'МЕХ'
            ],
            'Описание': [
                'Факультет информационных технологий и компьютерных наук',
                'Экономический факультет',
                'Механический факультет'
            ],
            'Активный': [
                'да',
                'да',
                'нет'
            ]
        }
        
        df = pd.DataFrame(sample_data)
        
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
        response['Content-Disposition'] = 'attachment; filename="faculty_import_sample.xlsx"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Ошибка при создании файла: {str(e)}')
        return redirect('admin_faculties')


def student_redirect_view(request, student_id):
    """Редирект с уведомлением"""
    messages.info(request, 'Функция просмотра/редактирования студентов в разработке')
    return redirect('admin_students')
