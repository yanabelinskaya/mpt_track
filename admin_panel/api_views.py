import json
import secrets
import string
from datetime import datetime, date
from io import BytesIO

from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import transaction
from django.db.models import Q

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

from .models import Faculty, Group, Student

# ====================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ====================================

def get_csrf_token(request):
    """Получить CSRF токен"""
    from django.middleware.csrf import get_token
    return get_token(request)

def generate_username(first_name, last_name):
    """Генерация уникального логина"""
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
    """Генерация безопасного пароля"""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

# ====================================
# API ДЛЯ ФАКУЛЬТЕТОВ
# ====================================

@login_required
def faculty_detail_view(request, faculty_id):
    """Просмотр детальной информации о факультете"""
    faculty = get_object_or_404(Faculty, id=faculty_id)
    
    context = {
        'faculty': faculty,
        'groups_count': faculty.groups_count,
        'students_count': faculty.students_count,
        'active_students_count': faculty.active_students_count,
    }
    
    return render(request, 'admin_panel/faculty/faculty_detail.html', context)

@login_required
def faculty_edit_view(request, faculty_id):
    """Редактирование факультета"""
    faculty = get_object_or_404(Faculty, id=faculty_id)
    
    if request.method == 'POST':
        try:
            faculty.name = request.POST.get('name', faculty.name).strip()
            faculty.code = request.POST.get('code', faculty.code).strip()
            faculty.description = request.POST.get('description', faculty.description).strip()
            faculty.is_active = request.POST.get('is_active') == 'on'
            
            faculty.save()
            messages.success(request, f'Факультет "{faculty.name}" успешно обновлен!')
            return redirect('admin_faculties')
            
        except Exception as e:
            messages.error(request, f'Ошибка при сохранении: {str(e)}')
    
    context = {
        'faculty': faculty,
        'is_edit': True,
    }
    
    return render(request, 'admin_panel/faculty/faculty_form.html', context)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def faculty_delete_api(request, faculty_id):
    """API удаления факультета"""
    try:
        faculty = get_object_or_404(Faculty, id=faculty_id)
        faculty_name = faculty.name
        
        # Проверяем связанные объекты
        groups_count = faculty.groups_count
        
        if groups_count > 0:
            return JsonResponse({
                'success': False,
                'message': f'Нельзя удалить факультет "{faculty_name}". К нему привязано {groups_count} групп.'
            }, status=400)
        
        # Удаляем факультет
        faculty.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Факультет "{faculty_name}" успешно удален',
            'faculty_id': faculty_id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при удалении факультета: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def faculty_toggle_status_api(request, faculty_id):
    """API переключения статуса факультета"""
    try:
        faculty = get_object_or_404(Faculty, id=faculty_id)
        
        # Получаем новый статус из JSON
        try:
            data = json.loads(request.body)
            new_status = data.get('is_active')
        except:
            new_status = None
        
        if new_status is None:
            # Если статус не передан, переключаем текущий
            new_status = not faculty.is_active
        
        faculty.is_active = new_status
        faculty.save()
        
        status_text = "активирован" if new_status else "деактивирован"
        
        return JsonResponse({
            'success': True,
            'message': f'Факультет "{faculty.name}" {status_text}',
            'is_active': new_status,
            'faculty_id': faculty_id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при изменении статуса: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def faculty_bulk_activate_api(request):
    """API массовой активации факультетов"""
    try:
        data = json.loads(request.body)
        faculty_ids = data.get('faculty_ids', [])
        
        if not faculty_ids:
            return JsonResponse({
                'success': False,
                'message': 'Не выбраны факультеты для активации'
            }, status=400)
        
        with transaction.atomic():
            updated_count = Faculty.objects.filter(
                id__in=faculty_ids
            ).update(is_active=True)
        
        return JsonResponse({
            'success': True,
            'message': f'Активировано {updated_count} факультетов',
            'updated_count': updated_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при массовой активации: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def faculty_bulk_deactivate_api(request):
    """API массовой деактивации факультетов"""
    try:
        data = json.loads(request.body)
        faculty_ids = data.get('faculty_ids', [])
        
        if not faculty_ids:
            return JsonResponse({
                'success': False,
                'message': 'Не выбраны факультеты для деактивации'
            }, status=400)
        
        with transaction.atomic():
            updated_count = Faculty.objects.filter(
                id__in=faculty_ids
            ).update(is_active=False)
        
        return JsonResponse({
            'success': True,
            'message': f'Деактивировано {updated_count} факультетов',
            'updated_count': updated_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при массовой деактивации: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def faculty_bulk_delete_api(request):
    """API массового удаления факультетов"""
    try:
        data = json.loads(request.body)
        faculty_ids = data.get('faculty_ids', [])
        
        if not faculty_ids:
            return JsonResponse({
                'success': False,
                'message': 'Не выбраны факультеты для удаления'
            }, status=400)
        
        # Получаем факультеты для проверки
        faculties = Faculty.objects.filter(id__in=faculty_ids)
        
        # Проверяем какие можно удалить
        deletable_ids = []
        non_deletable = []
        
        for faculty in faculties:
            groups_count = faculty.groups_count
            if groups_count > 0:
                non_deletable.append(f"{faculty.name} ({groups_count} групп)")
            else:
                deletable_ids.append(faculty.id)
        
        deleted_count = 0
        if deletable_ids:
            with transaction.atomic():
                deleted_count = Faculty.objects.filter(
                    id__in=deletable_ids
                ).delete()[0]
        
        message = f'Удалено {deleted_count} факультетов'
        if non_deletable:
            message += f'. Не удалено {len(non_deletable)} (есть связанные группы)'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'deleted_ids': deletable_ids,
            'deleted_count': deleted_count,
            'non_deletable': non_deletable
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при массовом удалении: {str(e)}'
        }, status=500)

# ====================================
# API ДЛЯ СТУДЕНТОВ
# ====================================

@login_required
def student_detail_view(request, student_id):
    """Просмотр детальной информации о студенте"""
    student = get_object_or_404(Student, id=student_id)
    
    context = {
        'student': student,
        'has_system_access': student.has_system_access(),
        'is_active_account': student.is_active_account,
    }
    
    return render(request, 'admin_panel/student/student_detail.html', context)

@login_required
def student_edit_view(request, student_id):
    """Редактирование студента"""
    student = get_object_or_404(Student, id=student_id)
    
    if request.method == 'POST':
        try:
            # Обновляем основные поля
            student.first_name = request.POST.get('first_name', '').strip()
            student.last_name = request.POST.get('last_name', '').strip()
            student.middle_name = request.POST.get('middle_name', '').strip()
            student.email = request.POST.get('email', '').strip()
            student.phone = request.POST.get('phone', '').strip()
            student.course = int(request.POST.get('course', 1))
            student.study_status = request.POST.get('study_status', 'active')
            
            # Обновляем группу если указана
            group_id = request.POST.get('group')
            if group_id:
                student.group = get_object_or_404(Group, id=group_id)
            
            student.save()
            messages.success(request, f'Студент "{student.get_full_name()}" успешно обновлен!')
            return redirect('admin_students')
            
        except Exception as e:
            messages.error(request, f'Ошибка при сохранении: {str(e)}')
    
    context = {
        'student': student,
        'groups': Group.objects.filter(is_active=True),
        'is_edit': True,
    }
    
    return render(request, 'admin_panel/student/student_form.html', context)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def student_delete_api(request, student_id):
    """API удаления студента"""
    try:
        student = get_object_or_404(Student, id=student_id)
        student_name = student.get_full_name()
        
        # Удаляем связанного пользователя если есть
        if student.has_system_access():
            student.user.delete()
        
        # Удаляем студента
        student.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Студент "{student_name}" успешно удален',
            'student_id': student_id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при удалении студента: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def student_toggle_status_api(request, student_id):
    """API переключения статуса аккаунта студента"""
    try:
        student = get_object_or_404(Student, id=student_id)
        
        if not student.has_system_access():
            return JsonResponse({
                'success': False,
                'message': 'У студента нет доступа к системе'
            }, status=400)
        
        # Переключаем статус аккаунта
        new_status = not student.user.is_active
        student.user.is_active = new_status
        student.user.save()
        
        status_text = "активирован" if new_status else "заблокирован"
        
        return JsonResponse({
            'success': True,
            'message': f'Аккаунт студента "{student.get_full_name()}" {status_text}',
            'is_active': new_status,
            'student_id': student_id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при изменении статуса: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def student_create_access_api(request, student_id):
    """API создания доступа к системе для студента"""
    try:
        student = get_object_or_404(Student, id=student_id)
        
        if student.has_system_access():
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
            password=password,
            first_name=student.first_name,
            last_name=student.last_name,
            is_active=True,
        )
        
        student.user = user
        student.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Создан доступ для студента "{student.get_full_name()}"',
            'username': username,
            'password': password,
            'student_id': student_id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при создании доступа: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def student_bulk_activate_api(request):
    """API массовой активации студентов"""
    try:
        data = json.loads(request.body)
        student_ids = data.get('student_ids', [])
        
        if not student_ids:
            return JsonResponse({
                'success': False,
                'message': 'Не выбраны студенты для активации'
            }, status=400)
        
        students = Student.objects.filter(id__in=student_ids)
        updated_count = 0
        
        with transaction.atomic():
            for student in students:
                if student.has_system_access():
                    student.user.is_active = True
                    student.user.save()
                    updated_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Активировано {updated_count} аккаунтов студентов',
            'updated_count': updated_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при массовой активации: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def student_bulk_deactivate_api(request):
    """API массовой деактивации студентов"""
    try:
        data = json.loads(request.body)
        student_ids = data.get('student_ids', [])
        
        if not student_ids:
            return JsonResponse({
                'success': False,
                'message': 'Не выбраны студенты для деактивации'
            }, status=400)
        
        students = Student.objects.filter(id__in=student_ids)
        updated_count = 0
        
        with transaction.atomic():
            for student in students:
                if student.has_system_access():
                    student.user.is_active = False
                    student.user.save()
                    updated_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Деактивировано {updated_count} аккаунтов студентов',
            'updated_count': updated_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при массовой деактивации: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def student_bulk_delete_api(request):
    """API массового удаления студентов"""
    try:
        data = json.loads(request.body)
        student_ids = data.get('student_ids', [])
        
        if not student_ids:
            return JsonResponse({
                'success': False,
                'message': 'Не выбраны студенты для удаления'
            }, status=400)
        
        students = Student.objects.filter(id__in=student_ids)
        deleted_count = 0
        
        with transaction.atomic():
            for student in students:
                # Удаляем связанного пользователя если есть
                if student.has_system_access():
                    student.user.delete()
                
                student.delete()
                deleted_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Удалено {deleted_count} студентов',
            'deleted_ids': student_ids,
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при массовом удалении: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def student_bulk_create_access_api(request):
    """API массового создания доступа для студентов"""
    try:
        data = json.loads(request.body)
        student_ids = data.get('student_ids', [])
        
        if not student_ids:
            return JsonResponse({
                'success': False,
                'message': 'Не выбраны студенты для создания доступа'
            }, status=400)
        
        students = Student.objects.filter(id__in=student_ids)
        created_count = 0
        created_accounts = []
        
        with transaction.atomic():
            for student in students:
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
                        
                        created_accounts.append({
                            'student_name': student.get_full_name(),
                            'username': username,
                            'password': password
                        })
                        created_count += 1
                        
                    except Exception as e:
                        continue  # Пропускаем если не удалось создать
        
        return JsonResponse({
            'success': True,
            'message': f'Создан доступ для {created_count} студентов',
            'created_count': created_count,
            'accounts': created_accounts
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при массовом создании доступа: {str(e)}'
        }, status=500)

# ====================================
# ЭКСПОРТ В EXCEL
# ====================================

def create_excel_workbook():
    """Создать Excel workbook со стилями"""
    if not EXCEL_AVAILABLE:
        raise ImportError("openpyxl не установлен")
    
    wb = openpyxl.Workbook()
    return wb

@login_required
def faculty_export_view(request):
    """Экспорт факультетов в Excel"""
    try:
        if not EXCEL_AVAILABLE:
            messages.error(request, 'Экспорт недоступен: не установлен openpyxl')
            return redirect('admin_faculties')
        
        # Получаем параметры фильтрации
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        selected_ids = request.GET.get('selected', '')
        
        # Формируем queryset
        queryset = Faculty.objects.all()
        
        if selected_ids:
            faculty_ids = [int(id) for id in selected_ids.split(',') if id.isdigit()]
            queryset = queryset.filter(id__in=faculty_ids)
        else:
            if search:
                queryset = queryset.filter(name__icontains=search)
            
            if status_filter == 'active':
                queryset = queryset.filter(is_active=True)
            elif status_filter == 'inactive':
                queryset = queryset.filter(is_active=False)
        
        # Создаем Excel файл
        wb = create_excel_workbook()
        ws = wb.active
        ws.title = "Факультеты"
        
        # Стили
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        
        # Заголовки
        headers = ['№', 'Название', 'Код', 'Описание', 'Статус', 'Групп', 'Студентов']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        
        # Данные
        for row_idx, faculty in enumerate(queryset, 2):
            ws.cell(row=row_idx, column=1, value=row_idx-1)
            ws.cell(row=row_idx, column=2, value=faculty.name)
            ws.cell(row=row_idx, column=3, value=faculty.code)
            ws.cell(row=row_idx, column=4, value=faculty.description or '')
            ws.cell(row=row_idx, column=5, value='Активный' if faculty.is_active else 'Неактивный')
            ws.cell(row=row_idx, column=6, value=faculty.groups_count)
            ws.cell(row=row_idx, column=7, value=faculty.students_count)
        
        # Автоширина колонок
        for column in ws.columns:
            max_length = max(len(str(cell.value or '')) for cell in column)
            ws.column_dimensions[column[0].column_letter].width = min(max_length + 2, 50)
        
        # Сохраняем в память
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        # Отправляем файл
        response = HttpResponse(
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        filename = f'faculties_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        if selected_ids:
            filename = f'selected_faculties_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        messages.error(request, f'Ошибка при экспорте: {str(e)}')
        return redirect('admin_faculties')

@login_required
def student_export_view(request):
    """Экспорт студентов в Excel"""
    try:
        if not EXCEL_AVAILABLE:
            messages.error(request, 'Экспорт недоступен: не установлен openpyxl')
            return redirect('admin_students')
        
        # Получаем параметры фильтрации
        search = request.GET.get('search', '')
        group_filter = request.GET.get('group', '')
        status_filter = request.GET.get('status', '')
        account_filter = request.GET.get('account', '')
        selected_ids = request.GET.get('selected', '')
        
        # Формируем queryset
        queryset = Student.objects.select_related('group', 'user').all()
        
        if selected_ids:
            student_ids = [int(id) for id in selected_ids.split(',') if id.isdigit()]
            queryset = queryset.filter(id__in=student_ids)
        else:
            if search:
                queryset = queryset.filter(
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(middle_name__icontains=search) |
                    Q(email__icontains=search) |
                    Q(student_id__icontains=search)
                )
            
            if group_filter:
                queryset = queryset.filter(group_id=group_filter)
            
            if status_filter:
                queryset = queryset.filter(study_status=status_filter)
            
            if account_filter == 'with_access':
                queryset = queryset.filter(user__isnull=False)
            elif account_filter == 'without_access':
                queryset = queryset.filter(user__isnull=True)
            elif account_filter == 'active_accounts':
                queryset = queryset.filter(user__isnull=False, user__is_active=True)
            elif account_filter == 'inactive_accounts':
                queryset = queryset.filter(user__isnull=False, user__is_active=False)
        
        # Создаем Excel файл
        wb = create_excel_workbook()
        ws = wb.active
        ws.title = "Студенты"
        
        # Стили
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        
        # Заголовки
        headers = [
            '№', 'Студ. билет', 'ФИО', 'Email', 'Телефон', 
            'Группа', 'Курс', 'Статус обучения', 'Логин', 'Статус аккаунта'
        ]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        
        # Данные
        for row_idx, student in enumerate(queryset, 2):
            ws.cell(row=row_idx, column=1, value=row_idx-1)
            ws.cell(row=row_idx, column=2, value=student.student_id)
            ws.cell(row=row_idx, column=3, value=student.get_full_name())
            ws.cell(row=row_idx, column=4, value=student.email)
            ws.cell(row=row_idx, column=5, value=student.phone or '')
            ws.cell(row=row_idx, column=6, value=str(student.group) if student.group else '')
            ws.cell(row=row_idx, column=7, value=f"{student.course} курс")
            ws.cell(row=row_idx, column=8, value=student.get_study_status_display())
            ws.cell(row=row_idx, column=9, value=student.username or '')
            
            # Статус аккаунта
            if student.has_system_access():
                account_status = 'Активен' if student.is_active_account else 'Заблокирован'
            else:
                account_status = 'Нет доступа'
            ws.cell(row=row_idx, column=10, value=account_status)
        
        # Автоширина колонок
        for column in ws.columns:
            max_length = max(len(str(cell.value or '')) for cell in column)
            ws.column_dimensions[column[0].column_letter].width = min(max_length + 2, 50)
        
        # Сохраняем в память
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        # Отправляем файл
        response = HttpResponse(
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        filename = f'students_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        if selected_ids:
            filename = f'selected_students_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        messages.error(request, f'Ошибка при экспорте: {str(e)}')
        return redirect('admin_students')
