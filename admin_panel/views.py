from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
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
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import tempfile
import os

# Р‘РµР·РѕРїР°СЃРЅР°СЏ РїСЂРѕРІРµСЂРєР° РёРјРїРѕСЂС‚Р° РјРѕРґРµР»РµР№
try:
    from .models import Student, Group, Faculty
    MODELS_AVAILABLE = True
except:
    MODELS_AVAILABLE = False

def dashboard_view(request):
    """Р“Р»Р°РІРЅР°СЏ СЃС‚СЂР°РЅРёС†Р° Р°РґРјРёРЅРєРё"""
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
    """РЎРїРёСЃРѕРє СЃС‚СѓРґРµРЅС‚РѕРІ СЃ С„РёР»СЊС‚СЂР°С†РёРµР№ Рё РїРѕРёСЃРєРѕРј"""
    if not MODELS_AVAILABLE:
        messages.error(request, 'РњРѕРґРµР»Рё РЅРµ Р·Р°РіСЂСѓР¶РµРЅС‹. Р’С‹РїРѕР»РЅРёС‚Рµ РјРёРіСЂР°С†РёРё.')
        return redirect('admin_dashboard')
    
    try:
        # РџРѕР»СѓС‡Р°РµРј РїР°СЂР°РјРµС‚СЂС‹ С„РёР»СЊС‚СЂР°С†РёРё
        search = request.GET.get('search', '').strip()
        group_filter = request.GET.get('group', '')
        status_filter = request.GET.get('status', '')
        course_filter = request.GET.get('course', '')
        
        # РќРћР’РћР•: РџРѕР»СѓС‡Р°РµРј РІС‹Р±СЂР°РЅРЅС‹С… СЃС‚СѓРґРµРЅС‚РѕРІ РёР· РїР°СЂР°РјРµС‚СЂРѕРІ
        selected_students = request.GET.get('selected', '').strip()
        selected_ids = []
        if selected_students:
            try:
                selected_ids = [int(x) for x in selected_students.split(',') if x.strip()]
            except ValueError:
                selected_ids = []
        
        # Р‘Р°Р·РѕРІС‹Р№ queryset
        students = Student.objects.select_related('user', 'group', 'group__faculty').all()
        
        # РџРѕРёСЃРє РїРѕ РёРјРµРЅРё, С„Р°РјРёР»РёРё, email, СЃС‚СѓРґРµРЅС‡РµСЃРєРѕРјСѓ Р±РёР»РµС‚Сѓ
        if search:
            students = students.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(middle_name__icontains=search) |
                Q(email__icontains=search) |
                Q(student_id__icontains=search) |
                Q(user__username__icontains=search)
            )
        
        # Р¤РёР»СЊС‚СЂ РїРѕ РіСЂСѓРїРїРµ
        if group_filter:
            students = students.filter(group_id=group_filter)
        
        # Р¤РёР»СЊС‚СЂ РїРѕ СЃС‚Р°С‚СѓСЃСѓ
        if status_filter == 'active':
            students = students.filter(user__is_active=True, study_status='active')
        elif status_filter == 'inactive':
            students = students.filter(user__is_active=False)
        elif status_filter:
            students = students.filter(study_status=status_filter)
        
        # Р¤РёР»СЊС‚СЂ РїРѕ РєСѓСЂСЃСѓ
        if course_filter:
            students = students.filter(course=course_filter)
        
        # РЎРѕСЂС‚РёСЂРѕРІРєР°
        students = students.order_by('last_name', 'first_name')
        
        # РќРћР’РћР•: РЎРѕС…СЂР°РЅСЏРµРј РѕР±С‰РёР№ queryset РґР»СЏ РїРѕРґСЃС‡РµС‚Р°
        total_students = students.count()
        
        # РџР°РіРёРЅР°С†РёСЏ
        paginator = Paginator(students, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # РџРѕР»СѓС‡Р°РµРј СЃРїРёСЃРѕРє РіСЂСѓРїРї РґР»СЏ С„РёР»СЊС‚СЂР°
        groups = Group.objects.filter(is_active=True).select_related('faculty').order_by('name')
        
        # Р”РѕР±Р°РІР»СЏРµРј РєРѕР»РёС‡РµСЃС‚РІРѕ СЃС‚СѓРґРµРЅС‚РѕРІ РІ РєР°Р¶РґРѕР№ РіСЂСѓРїРїРµ
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
            'total_students': total_students,  # РќРћР’РћР•
            'selected_students': selected_ids,  # РќРћР’РћР•
            'current_filters': {  # РќРћР’РћР•
                'search': search,
                'group': group_filter,
                'status': status_filter,
                'course': course_filter,
            }
        }
        
        return render(request, 'admin_panel/students/list.html', context)
    
    except Exception as e:
        messages.error(request, f'РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё СЃС‚СѓРґРµРЅС‚РѕРІ: {str(e)}')
        return redirect('admin_dashboard')

def student_detail_view(request, pk):
    """Р”РµС‚Р°Р»СЊРЅР°СЏ РёРЅС„РѕСЂРјР°С†РёСЏ Рѕ СЃС‚СѓРґРµРЅС‚Рµ"""
    if not MODELS_AVAILABLE:
        messages.error(request, 'РњРѕРґРµР»Рё РЅРµ Р·Р°РіСЂСѓР¶РµРЅС‹.')
        return redirect('admin_dashboard')
    
    try:
        student = get_object_or_404(Student, pk=pk)
        return render(request, 'admin_panel/students/detail.html', {'student': student})
    except:
        messages.error(request, 'РЎС‚СѓРґРµРЅС‚ РЅРµ РЅР°Р№РґРµРЅ.')
        return redirect('admin_students')

def student_create_view(request):
    """РЎРѕР·РґР°РЅРёРµ РЅРѕРІРѕРіРѕ СЃС‚СѓРґРµРЅС‚Р°"""
    if request.method == 'POST':
        try:
            # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РёР· С„РѕСЂРјС‹
            last_name = request.POST.get('last_name', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            middle_name = request.POST.get('middle_name', '').strip()
            email = request.POST.get('email', '').strip().lower()
            
            # Р’Р°Р»РёРґР°С†РёСЏ
            errors = {}
            
            if not last_name:
                errors['last_name'] = ['Р¤Р°РјРёР»РёСЏ РѕР±СЏР·Р°С‚РµР»СЊРЅР° РґР»СЏ Р·Р°РїРѕР»РЅРµРЅРёСЏ']
            
            if not first_name:
                errors['first_name'] = ['РРјСЏ РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ РґР»СЏ Р·Р°РїРѕР»РЅРµРЅРёСЏ']
            
            if not email:
                errors['email'] = ['Email РѕР±СЏР·Р°С‚РµР»РµРЅ РґР»СЏ Р·Р°РїРѕР»РЅРµРЅРёСЏ']
            elif '@' not in email:
                errors['email'] = ['Р’РІРµРґРёС‚Рµ РєРѕСЂСЂРµРєС‚РЅС‹Р№ email Р°РґСЂРµСЃ']
            elif Student.objects.filter(email=email).exists():
                errors['email'] = ['РЎС‚СѓРґРµРЅС‚ СЃ С‚Р°РєРёРј email СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚']
            
            # Р•СЃР»Рё РµСЃС‚СЊ РѕС€РёР±РєРё, РІРѕР·РІСЂР°С‰Р°РµРј РёС…
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                    'message': 'РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РёСЃРїСЂР°РІСЊС‚Рµ РѕС€РёР±РєРё РІ С„РѕСЂРјРµ'
                })
            
            # РЎРѕР·РґР°РµРј СЃС‚СѓРґРµРЅС‚Р°
            with transaction.atomic():
                created_by = request.user if request.user.is_authenticated else None
                
                student = Student.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=middle_name,
                    email=email,
                    created_by=created_by
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'РЎС‚СѓРґРµРЅС‚ {student.get_full_name()} СѓСЃРїРµС€РЅРѕ СЃРѕР·РґР°РЅ',
                    'redirect_url': reverse('admin_students')
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё СЃС‚СѓРґРµРЅС‚Р°: {str(e)}'
            })
    
    # GET Р·Р°РїСЂРѕСЃ - РїРѕРєР°Р·С‹РІР°РµРј С„РѕСЂРјСѓ
    groups = Group.objects.filter(is_active=True).select_related('faculty').order_by('name')
    
    context = {
        'groups': groups,
    }
    
    return render(request, 'admin_panel/students/create.html', context)

def student_edit_view(request, pk):
    """Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ СЃС‚СѓРґРµРЅС‚Р°"""
    try:
        student = Student.objects.select_related('group', 'group__faculty').get(pk=pk)
    except Student.DoesNotExist:
        messages.error(request, 'РЎС‚СѓРґРµРЅС‚ РЅРµ РЅР°Р№РґРµРЅ.')
        return redirect('admin_students')
    
    if request.method == 'POST':
        try:
            # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РёР· С„РѕСЂРјС‹
            last_name = request.POST.get('last_name', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            middle_name = request.POST.get('middle_name', '').strip()
            email = request.POST.get('email', '').strip().lower()
            phone = request.POST.get('phone', '').strip()
            group_id = request.POST.get('group')
            date_of_birth = request.POST.get('date_of_birth') or None
            gender = request.POST.get('gender', '')
            address = request.POST.get('address', '').strip()
            notes = request.POST.get('notes', '').strip()
            
            # Р’Р°Р»РёРґР°С†РёСЏ
            errors = {}
            
            if not last_name:
                errors['last_name'] = ['Р¤Р°РјРёР»РёСЏ РѕР±СЏР·Р°С‚РµР»СЊРЅР° РґР»СЏ Р·Р°РїРѕР»РЅРµРЅРёСЏ']
            
            if not first_name:
                errors['first_name'] = ['РРјСЏ РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ РґР»СЏ Р·Р°РїРѕР»РЅРµРЅРёСЏ']
            
            if not email:
                errors['email'] = ['Email РѕР±СЏР·Р°С‚РµР»РµРЅ РґР»СЏ Р·Р°РїРѕР»РЅРµРЅРёСЏ']
            elif '@' not in email:
                errors['email'] = ['Р’РІРµРґРёС‚Рµ РєРѕСЂСЂРµРєС‚РЅС‹Р№ email Р°РґСЂРµСЃ']
            elif Student.objects.filter(email=email).exclude(pk=student.pk).exists():
                errors['email'] = ['РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ СЃ С‚Р°РєРёРј email СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚']
            
            # Р•СЃР»Рё РµСЃС‚СЊ РѕС€РёР±РєРё, РІРѕР·РІСЂР°С‰Р°РµРј РёС…
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                    'message': 'РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РёСЃРїСЂР°РІСЊС‚Рµ РѕС€РёР±РєРё РІ С„РѕСЂРјРµ'
                })
            
            # РћР±РЅРѕРІР»СЏРµРј РґР°РЅРЅС‹Рµ СЃС‚СѓРґРµРЅС‚Р°
            with transaction.atomic():
                # РџРѕР»СѓС‡Р°РµРј РіСЂСѓРїРїСѓ
                group = None
                if group_id:
                    try:
                        group = Group.objects.get(id=group_id)
                    except Group.DoesNotExist:
                        pass
                
                # РћР±РЅРѕРІР»СЏРµРј РїРѕР»СЏ СЃС‚СѓРґРµРЅС‚Р°
                student.first_name = first_name
                student.last_name = last_name
                student.middle_name = middle_name
                student.email = email
                student.phone = phone
                student.group = group
                student.date_of_birth = date_of_birth
                student.gender = gender
                student.address = address
                student.notes = notes
                student.save()
                
                # РћР±РЅРѕРІР»СЏРµРј СЃРІСЏР·Р°РЅРЅРѕРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РµСЃР»Рё РµСЃС‚СЊ
                if hasattr(student, 'user') and student.user:
                    student.user.first_name = first_name
                    student.user.last_name = last_name
                    student.user.email = email
                    student.user.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Р”Р°РЅРЅС‹Рµ СЃС‚СѓРґРµРЅС‚Р° {student.get_full_name()} СѓСЃРїРµС€РЅРѕ РѕР±РЅРѕРІР»РµРЅС‹',
                    'student': {
                        'full_name': student.get_full_name(),
                        'email': student.email
                    }
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'РћС€РёР±РєР° РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РґР°РЅРЅС‹С…: {str(e)}'
            })
    
    # GET Р·Р°РїСЂРѕСЃ - РїРѕРєР°Р·С‹РІР°РµРј С„РѕСЂРјСѓ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ
    groups = Group.objects.filter(is_active=True).select_related('faculty').order_by('name')
    
    context = {
        'student': student,
        'groups': groups,
    }
    
    return render(request, 'admin_panel/students/edit.html', context)

@require_http_methods(["DELETE"])
def student_delete_view(request, pk):
    """РЈРґР°Р»РµРЅРёРµ СЃС‚СѓРґРµРЅС‚Р°"""
    print(f"=== DELETE REQUEST RECEIVED ===")
    print(f"Student ID: {pk}")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    
    if not MODELS_AVAILABLE:
        print("Models not available")
        return JsonResponse({'success': False, 'error': 'РњРѕРґРµР»Рё РЅРµ Р·Р°РіСЂСѓР¶РµРЅС‹'})
    
    try:
        student = get_object_or_404(Student, pk=pk)
        student_name = student.get_full_name()
        print(f"Found student: {student_name}")
        
        # РЎРѕС…СЂР°РЅСЏРµРј ID РїРµСЂРµРґ СѓРґР°Р»РµРЅРёРµРј
        student_id = student.id
        
        # РЈРґР°Р»СЏРµРј СЃРІСЏР·Р°РЅРЅРѕРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РµСЃР»Рё РµСЃС‚СЊ
        if hasattr(student, 'user') and student.user:
            print(f"Deleting related user: {student.user.username}")
            student.user.delete()
        
        # РЈРґР°Р»СЏРµРј СЃС‚СѓРґРµРЅС‚Р°
        student.delete()
        print(f"Student {student_name} deleted successfully")
        
        response_data = {
            'success': True, 
            'message': f'РЎС‚СѓРґРµРЅС‚ {student_name} СѓРґР°Р»РµРЅ',
            'student_id': student_id
        }
        print(f"Returning response: {response_data}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error deleting student: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


def teachers_list_view(request):
    """Р’СЂРµРјРµРЅРЅР°СЏ Р·Р°РіР»СѓС€РєР° РґР»СЏ РїСЂРµРїРѕРґР°РІР°С‚РµР»РµР№"""
    messages.info(request, 'Р Р°Р·РґРµР» РїСЂРµРїРѕРґР°РІР°С‚РµР»РµР№ РІ СЂР°Р·СЂР°Р±РѕС‚РєРµ')
    return redirect('admin_dashboard')

def student_import_view(request):
    """РРјРїРѕСЂС‚ СЃС‚СѓРґРµРЅС‚РѕРІ РёР· Excel"""
    if request.method == 'POST' and request.FILES.get('excel_file'):
        try:
            excel_file = request.FILES['excel_file']
            
            # Р§РёС‚Р°РµРј Excel С„Р°Р№Р»
            if excel_file.name.endswith('.xlsx') or excel_file.name.endswith('.xls'):
                df = pd.read_excel(excel_file)
            else:
                messages.error(request, 'РџРѕРґРґРµСЂР¶РёРІР°СЋС‚СЃСЏ С‚РѕР»СЊРєРѕ С„Р°Р№Р»С‹ .xlsx Рё .xls')
                return redirect('admin_student_import')
            
            # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ РЅРµРѕР±С…РѕРґРёРјС‹С… РєРѕР»РѕРЅРѕРє
            required_columns = ['surname', 'name', 'patronymic', 'email']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                messages.error(request, f'РћС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ РєРѕР»РѕРЅРєРё: {", ".join(missing_columns)}')
                return redirect('admin_student_import')
            
            # РџСЂРµРґРІР°СЂРёС‚РµР»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР° РґР°РЅРЅС‹С…
            errors = []
            students_data = []
            
            for index, row in df.iterrows():
                row_num = index + 2
                
                # РџСЂРѕРІРµСЂРєР° РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РїРѕР»РµР№
                if pd.isna(row['surname']) or not str(row['surname']).strip():
                    errors.append(f'РЎС‚СЂРѕРєР° {row_num}: РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ С„Р°РјРёР»РёСЏ')
                    continue
                    
                if pd.isna(row['name']) or not str(row['name']).strip():
                    errors.append(f'РЎС‚СЂРѕРєР° {row_num}: РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РёРјСЏ')
                    continue
                
                # РџРѕРґРіРѕС‚Р°РІР»РёРІР°РµРј РґР°РЅРЅС‹Рµ
                student_data = {
                    'surname': str(row['surname']).strip(),
                    'name': str(row['name']).strip(),
                    'patronymic': str(row['patronymic']).strip() if not pd.isna(row['patronymic']) else '',
                    'email': str(row['email']).strip().lower() if not pd.isna(row['email']) else '',
                    'row_num': row_num
                }
                
                # РџСЂРѕРІРµСЂРєР° email
                if student_data['email']:
                    if '@' not in student_data['email']:
                        errors.append(f'РЎС‚СЂРѕРєР° {row_num}: РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ email')
                        continue
                    
                    # РџСЂРѕРІРµСЂСЏРµРј СѓРЅРёРєР°Р»СЊРЅРѕСЃС‚СЊ email
                    if Student.objects.filter(email=student_data['email']).exists():
                        errors.append(f'РЎС‚СЂРѕРєР° {row_num}: email {student_data["email"]} СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚')
                        continue
                
                students_data.append(student_data)
            
            # Р•СЃР»Рё РµСЃС‚СЊ РѕС€РёР±РєРё, РїРѕРєР°Р·С‹РІР°РµРј РёС…
            if errors:
                for error in errors[:10]:
                    messages.error(request, error)
                if len(errors) > 10:
                    messages.error(request, f'Р РµС‰Рµ {len(errors) - 10} РѕС€РёР±РѕРє...')
                return redirect('admin_student_import')
            
            # Р•СЃР»Рё РґР°РЅРЅС‹С… РЅРµС‚
            if not students_data:
                messages.error(request, 'РќРµС‚ РєРѕСЂСЂРµРєС‚РЅС‹С… РґР°РЅРЅС‹С… РґР»СЏ РёРјРїРѕСЂС‚Р°')
                return redirect('admin_student_import')
            
            # РРјРїРѕСЂС‚РёСЂСѓРµРј СЃС‚СѓРґРµРЅС‚РѕРІ
            with transaction.atomic():
                success_count = 0
                error_count = 0
                
                for student_data in students_data:
                    try:
                        # РЎРѕР·РґР°РµРј СЃС‚СѓРґРµРЅС‚Р° Р‘Р•Р— User РѕР±СЉРµРєС‚Р°
                        student = Student.objects.create(
                            first_name=student_data['name'],
                            last_name=student_data['surname'],
                            middle_name=student_data['patronymic'],
                            email=student_data['email'],
                            study_status='active',
                        )
                        
                        success_count += 1
                        
                    except Exception as e:
                        error_count += 1
                        messages.error(request, f'РћС€РёР±РєР° РІ СЃС‚СЂРѕРєРµ {student_data["row_num"]}: {str(e)}')
                
                if success_count > 0:
                    messages.success(request, f'РЈСЃРїРµС€РЅРѕ РёРјРїРѕСЂС‚РёСЂРѕРІР°РЅРѕ {success_count} СЃС‚СѓРґРµРЅС‚РѕРІ')
                
                if error_count > 0:
                    messages.warning(request, f'РћС€РёР±РѕРє РїСЂРё РёРјРїРѕСЂС‚Рµ: {error_count}')
                
                return redirect('admin_students')
                
        except Exception as e:
            messages.error(request, f'РћС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ С„Р°Р№Р»Р°: {str(e)}')
            return redirect('admin_student_import')
    
    # GET Р·Р°РїСЂРѕСЃ - РїРѕРєР°Р·С‹РІР°РµРј С„РѕСЂРјСѓ
    context = {
        'sample_data': [
            {'surname': 'РРІР°РЅРѕРІ', 'name': 'РРІР°РЅ', 'patronymic': 'РџРµС‚СЂРѕРІРёС‡', 'email': 'ivanov@example.com'},
            {'surname': 'РџРµС‚СЂРѕРІ', 'name': 'РџРµС‚СЂ', 'patronymic': 'РРІР°РЅРѕРІРёС‡', 'email': 'petrov@example.com'},
            {'surname': 'РЎРёРґРѕСЂРѕРІР°', 'name': 'РђРЅРЅР°', 'patronymic': 'РЎРµСЂРіРµРµРІРЅР°', 'email': 'sidorova@example.com'},
        ]
    }
    
    return render(request, 'admin_panel/students/import.html', context)

def download_sample_excel(request):
    """РЎРєР°С‡РёРІР°РЅРёРµ РѕР±СЂР°Р·С†Р° Excel С„Р°Р№Р»Р°"""
    # РЎРѕР·РґР°РµРј РѕР±СЂР°Р·РµС† РґР°РЅРЅС‹С…
    sample_data = {
        'surname': ['РРІР°РЅРѕРІ', 'РџРµС‚СЂРѕРІ', 'РЎРёРґРѕСЂРѕРІР°'],
        'name': ['РРІР°РЅ', 'РџРµС‚СЂ', 'РђРЅРЅР°'], 
        'patronymic': ['РџРµС‚СЂРѕРІРёС‡', 'РРІР°РЅРѕРІРёС‡', 'РЎРµСЂРіРµРµРІРЅР°'],
        'email': ['ivanov@example.com', 'petrov@example.com', 'sidorova@example.com']
    }
    
    df = pd.DataFrame(sample_data)
    
    # РЎРѕР·РґР°РµРј Excel С„Р°Р№Р» РІ РїР°РјСЏС‚Рё
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='РЎС‚СѓРґРµРЅС‚С‹')
    
    output.seek(0)
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="sample_students.xlsx"'
    
    return response

def generate_username(first_name, last_name):
    """Р“РµРЅРµСЂР°С†РёСЏ Р»РѕРіРёРЅР° РёР· Р¤РРћ"""
    transliteration = {
        'Р°': 'a', 'Р±': 'b', 'РІ': 'v', 'Рі': 'g', 'Рґ': 'd', 'Рµ': 'e', 'С‘': 'e',
        'Р¶': 'zh', 'Р·': 'z', 'Рё': 'i', 'Р№': 'y', 'Рє': 'k', 'Р»': 'l', 'Рј': 'm',
        'РЅ': 'n', 'Рѕ': 'o', 'Рї': 'p', 'СЂ': 'r', 'СЃ': 's', 'С‚': 't', 'Сѓ': 'u',
        'С„': 'f', 'С…': 'h', 'С†': 'c', 'С‡': 'ch', 'С€': 'sh', 'С‰': 'sch',
        'СЉ': '', 'С‹': 'y', 'СЊ': '', 'СЌ': 'e', 'СЋ': 'yu', 'СЏ': 'ya',
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
    """Р“РµРЅРµСЂР°С†РёСЏ СЃР»СѓС‡Р°Р№РЅРѕРіРѕ РїР°СЂРѕР»СЏ"""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def send_access_email(student, username, password, is_reset=False):
    """РћС‚РїСЂР°РІРєР° email СЃ РґР°РЅРЅС‹РјРё РґР»СЏ РґРѕСЃС‚СѓРїР°"""
    try:
        subject = 'РЎР±СЂРѕСЃ РїР°СЂРѕР»СЏ - MPT Journal' if is_reset else 'Р”РѕСЃС‚СѓРї Рє СЃРёСЃС‚РµРјРµ - MPT Journal'
        
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        
        message = f"""
Р—РґСЂР°РІСЃС‚РІСѓР№С‚Рµ, {student.get_full_name()}!

{'Р’Р°С€ РїР°СЂРѕР»СЊ Р±С‹Р» СЃР±СЂРѕС€РµРЅ.' if is_reset else 'Р’Р°Рј СЃРѕР·РґР°РЅ РґРѕСЃС‚СѓРї Рє СЃРёСЃС‚РµРјРµ MPT Journal.'}

Р”Р°РЅРЅС‹Рµ РґР»СЏ РІС…РѕРґР°:
Р›РѕРіРёРЅ: {username}
{'РќРѕРІС‹Р№ РїР°СЂРѕР»СЊ' if is_reset else 'РџР°СЂРѕР»СЊ'}: {password}

Р’РѕР№РґРёС‚Рµ РІ СЃРёСЃС‚РµРјСѓ РїРѕ Р°РґСЂРµСЃСѓ: {site_url}

РџСЂРё РїРµСЂРІРѕРј РІС…РѕРґРµ СЂРµРєРѕРјРµРЅРґСѓРµРј СЃРјРµРЅРёС‚СЊ РїР°СЂРѕР»СЊ РЅР° Р±РѕР»РµРµ СѓРґРѕР±РЅС‹Р№.

РЎ СѓРІР°Р¶РµРЅРёРµРј,
РђРґРјРёРЅРёСЃС‚СЂР°С†РёСЏ РњРџРў
        """
        
        print(f"РћС‚РїСЂР°РІРєР° email РґР»СЏ {student.get_full_name()} РЅР° Р°РґСЂРµСЃ: {student.email}")
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student.email],
            fail_silently=False,
        )
        
        print("Email СѓСЃРїРµС€РЅРѕ РѕС‚РїСЂР°РІР»РµРЅ!")
        return True
        
    except Exception as e:
        print(f"РћС€РёР±РєР° РѕС‚РїСЂР°РІРєРё email: {e}")
        import traceback
        traceback.print_exc()
        return False

@require_http_methods(["POST"])
def student_create_access_view(request, pk):
    """РЎРѕР·РґР°РЅРёРµ РґРѕСЃС‚СѓРїР° Рє СЃРёСЃС‚РµРјРµ РґР»СЏ СЃС‚СѓРґРµРЅС‚Р°"""
    try:
        student = Student.objects.get(pk=pk)
    except Student.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'РЎС‚СѓРґРµРЅС‚ РЅРµ РЅР°Р№РґРµРЅ'
        })
    
    # РџСЂРѕРІРµСЂСЏРµРј, РЅРµС‚ Р»Рё СѓР¶Рµ РґРѕСЃС‚СѓРїР°
    if hasattr(student, 'user') and student.user:
        return JsonResponse({
            'success': False,
            'error': 'Р”РѕСЃС‚СѓРї СѓР¶Рµ СЃРѕР·РґР°РЅ РґР»СЏ СЌС‚РѕРіРѕ СЃС‚СѓРґРµРЅС‚Р°'
        })
    
    try:
        with transaction.atomic():
            # Р“РµРЅРµСЂРёСЂСѓРµРј Р»РѕРіРёРЅ Рё РїР°СЂРѕР»СЊ
            username = generate_username(student.first_name, student.last_name)
            password = generate_password()
            
            # РЎРѕР·РґР°РµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
            user = User.objects.create_user(
                username=username,
                email=student.email,
                password=password,
                first_name=student.first_name,
                last_name=student.last_name,
                is_active=True,
            )
            
            # РЎРІСЏР·С‹РІР°РµРј СЃС‚СѓРґРµРЅС‚Р° СЃ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј
            student.user = user
            student.save()
            
            # РћС‚РїСЂР°РІР»СЏРµРј email
            email_sent = send_access_email(student, username, password)
            
            return JsonResponse({
                'success': True,
                'message': 'Р”РѕСЃС‚СѓРї Рє СЃРёСЃС‚РµРјРµ СЃРѕР·РґР°РЅ',
                'email_sent': email_sent,
                'username': username
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё РґРѕСЃС‚СѓРїР°: {str(e)}'
        })

@require_http_methods(["POST"])
def student_reset_password_view(request, pk):
    """РЎР±СЂРѕСЃ РїР°СЂРѕР»СЏ СЃС‚СѓРґРµРЅС‚Р°"""
    try:
        student = Student.objects.get(pk=pk)
    except Student.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'РЎС‚СѓРґРµРЅС‚ РЅРµ РЅР°Р№РґРµРЅ'
        })
    
    # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ РґРѕСЃС‚СѓРїР°
    if not hasattr(student, 'user') or not student.user:
        return JsonResponse({
            'success': False,
            'error': 'Р”РѕСЃС‚СѓРї Рє СЃРёСЃС‚РµРјРµ РЅРµ СЃРѕР·РґР°РЅ'
        })
    
    try:
        # Р“РµРЅРµСЂРёСЂСѓРµРј РЅРѕРІС‹Р№ РїР°СЂРѕР»СЊ
        new_password = generate_password()
        
        # РћР±РЅРѕРІР»СЏРµРј РїР°СЂРѕР»СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
        user = student.user
        user.set_password(new_password)
        user.save()
        
        # РћС‚РїСЂР°РІР»СЏРµРј email
        email_sent = send_access_email(student, user.username, new_password, is_reset=True)
        
        return JsonResponse({
            'success': True,
            'message': 'РџР°СЂРѕР»СЊ СЃР±СЂРѕС€РµРЅ',
            'email_sent': email_sent
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'РћС€РёР±РєР° РїСЂРё СЃР±СЂРѕСЃРµ РїР°СЂРѕР»СЏ: {str(e)}'
        })

@require_http_methods(["POST"])
def student_toggle_status_view(request, pk):
    """РР·РјРµРЅРµРЅРёРµ СЃС‚Р°С‚СѓСЃР° Р°РєС‚РёРІРЅРѕСЃС‚Рё СЃС‚СѓРґРµРЅС‚Р°"""
    try:
        student = Student.objects.get(pk=pk)
    except Student.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'РЎС‚СѓРґРµРЅС‚ РЅРµ РЅР°Р№РґРµРЅ'
        })
    
    # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
    if not hasattr(student, 'user') or not student.user:
        return JsonResponse({
            'success': False,
            'error': 'Р”РѕСЃС‚СѓРї Рє СЃРёСЃС‚РµРјРµ РЅРµ СЃРѕР·РґР°РЅ'
        })
    
    try:
        # РџРµСЂРµРєР»СЋС‡Р°РµРј СЃС‚Р°С‚СѓСЃ
        user = student.user
        user.is_active = not user.is_active
        user.save()
        
        status_text = 'Р°РєС‚РёРІРёСЂРѕРІР°РЅ' if user.is_active else 'Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅ'
        
        return JsonResponse({
            'success': True,
            'message': f'Р”РѕСЃС‚СѓРї {status_text}',
            'is_active': user.is_active,
            'status_text': 'РђРєС‚РёРІРµРЅ' if user.is_active else 'Р—Р°Р±Р»РѕРєРёСЂРѕРІР°РЅ'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'РћС€РёР±РєР° РїСЂРё РёР·РјРµРЅРµРЅРёРё СЃС‚Р°С‚СѓСЃР°: {str(e)}'
        })

@require_http_methods(["POST"])
def students_bulk_create_access_view(request):
    """РњР°СЃСЃРѕРІРѕРµ СЃРѕР·РґР°РЅРёРµ РґРѕСЃС‚СѓРїР° Рє СЃРёСЃС‚РµРјРµ"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ РґР°РЅРЅС‹С…'
        })
    
    try:
        if data.get('all'):
            # Р’С‹Р±СЂР°РЅС‹ РІСЃРµ СЃС‚СѓРґРµРЅС‚С‹ СЃ СѓС‡РµС‚РѕРј С„РёР»СЊС‚СЂРѕРІ
            students = Student.objects.all()
            
            # РџСЂРёРјРµРЅСЏРµРј С„РёР»СЊС‚СЂС‹
            filters = data.get('filters', {})
            if filters.get('search'):
                search_query = filters['search']
                students = students.filter(
                    Q(first_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(email__icontains=search_query)
                )
            
            if filters.get('group'):
                students = students.filter(group_id=filters['group'])
            
            if filters.get('status') == 'active':
                students = students.filter(user__is_active=True)
            elif filters.get('status') == 'inactive':
                students = students.filter(user__is_active=False)
        else:
            # Р’С‹Р±СЂР°РЅС‹ РєРѕРЅРєСЂРµС‚РЅС‹Рµ СЃС‚СѓРґРµРЅС‚С‹
            student_ids = data.get('ids', [])
            students = Student.objects.filter(id__in=student_ids)
        
        created_count = 0
        emails_sent = 0
        errors = []
        
        for student in students:
            # РџСЂРѕРїСѓСЃРєР°РµРј СЃС‚СѓРґРµРЅС‚РѕРІ, Сѓ РєРѕС‚РѕСЂС‹С… СѓР¶Рµ РµСЃС‚СЊ РґРѕСЃС‚СѓРї
            if hasattr(student, 'user') and student.user:
                continue
            
            try:
                with transaction.atomic():
                    # Р“РµРЅРµСЂРёСЂСѓРµРј РґР°РЅРЅС‹Рµ РґР»СЏ РґРѕСЃС‚СѓРїР°
                    username = generate_username(student.first_name, student.last_name)
                    password = generate_password()
                    
                    # РЎРѕР·РґР°РµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
                    user = User.objects.create_user(
                        username=username,
                        email=student.email,
                        password=password,
                        first_name=student.first_name,
                        last_name=student.last_name,
                        is_active=True,
                    )
                    
                    # РЎРІСЏР·С‹РІР°РµРј СЃС‚СѓРґРµРЅС‚Р° СЃ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј
                    student.user = user
                    student.save()
                    
                    created_count += 1
                    
                    # РћС‚РїСЂР°РІР»СЏРµРј email
                    if send_access_email(student, username, password):
                        emails_sent += 1
                    
            except Exception as e:
                errors.append(f"{student.get_full_name()}: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'created_count': created_count,
            'emails_sent': emails_sent,
            'errors': errors
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'РћС€РёР±РєР° РїСЂРё РјР°СЃСЃРѕРІРѕРј СЃРѕР·РґР°РЅРёРё РґРѕСЃС‚СѓРїР°: {str(e)}'
        })

@require_http_methods(["POST"])
def students_bulk_update_status_view(request):
    """РњР°СЃСЃРѕРІРѕРµ РёР·РјРµРЅРµРЅРёРµ СЃС‚Р°С‚СѓСЃР° СЃС‚СѓРґРµРЅС‚РѕРІ"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ РґР°РЅРЅС‹С…'
        })
    
    try:
        is_active = data.get('is_active', True)
        
        if data.get('all'):
            # Р’С‹Р±СЂР°РЅС‹ РІСЃРµ СЃС‚СѓРґРµРЅС‚С‹ СЃ СѓС‡РµС‚РѕРј С„РёР»СЊС‚СЂРѕРІ
            students = Student.objects.filter(user__isnull=False)
            
            # РџСЂРёРјРµРЅСЏРµРј С„РёР»СЊС‚СЂС‹
            filters = data.get('filters', {})
            if filters.get('search'):
                search_query = filters['search']
                students = students.filter(
                    Q(first_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(email__icontains=search_query)
                )
            
            if filters.get('group'):
                students = students.filter(group_id=filters['group'])
        else:
            # Р’С‹Р±СЂР°РЅС‹ РєРѕРЅРєСЂРµС‚РЅС‹Рµ СЃС‚СѓРґРµРЅС‚С‹
            student_ids = data.get('ids', [])
            students = Student.objects.filter(
                id__in=student_ids,
                user__isnull=False
            )
        
        # РћР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚СѓСЃ РІСЃРµС… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№
        updated_count = 0
        for student in students:
            if student.user:
                student.user.is_active = is_active
                student.user.save()
                updated_count += 1
        
        return JsonResponse({
            'success': True,
            'updated_count': updated_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'РћС€РёР±РєР° РїСЂРё РјР°СЃСЃРѕРІРѕРј РѕР±РЅРѕРІР»РµРЅРёРё СЃС‚Р°С‚СѓСЃР°: {str(e)}'
        })

@require_http_methods(["POST"])
def students_bulk_delete_view(request):
    """РњР°СЃСЃРѕРІРѕРµ СѓРґР°Р»РµРЅРёРµ СЃС‚СѓРґРµРЅС‚РѕРІ"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ РґР°РЅРЅС‹С…'
        })
    
    try:
        deleted_students_ids = []  # РЎРїРёСЃРѕРє ID СѓРґР°Р»РµРЅРЅС‹С… СЃС‚СѓРґРµРЅС‚РѕРІ
        
        if data.get('all'):
            # Р’С‹Р±СЂР°РЅС‹ РІСЃРµ СЃС‚СѓРґРµРЅС‚С‹ СЃ СѓС‡РµС‚РѕРј С„РёР»СЊС‚СЂРѕРІ
            students = Student.objects.all()
            
            # РџСЂРёРјРµРЅСЏРµРј С„РёР»СЊС‚СЂС‹
            filters = data.get('filters', {})
            if filters.get('search'):
                search_query = filters['search']
                students = students.filter(
                    Q(first_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(email__icontains=search_query)
                )
            
            if filters.get('group'):
                students = students.filter(group_id=filters['group'])
        else:
            # Р’С‹Р±СЂР°РЅС‹ РєРѕРЅРєСЂРµС‚РЅС‹Рµ СЃС‚СѓРґРµРЅС‚С‹
            student_ids = data.get('ids', [])
            students = Student.objects.filter(id__in=student_ids)
        
        # РЈРґР°Р»СЏРµРј СЃС‚СѓРґРµРЅС‚РѕРІ
        deleted_count = 0
        for student in students:
            try:
                with transaction.atomic():
                    student_id = student.id  # РЎРѕС…СЂР°РЅСЏРµРј ID РїРµСЂРµРґ СѓРґР°Р»РµРЅРёРµРј
                    
                    # РЈРґР°Р»СЏРµРј СЃРІСЏР·Р°РЅРЅРѕРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ, РµСЃР»Рё РµСЃС‚СЊ
                    if student.user:
                        student.user.delete()
                    
                    # РЈРґР°Р»СЏРµРј СЃС‚СѓРґРµРЅС‚Р°
                    student.delete()
                    deleted_count += 1
                    deleted_students_ids.append(student_id)  # Р”РѕР±Р°РІР»СЏРµРј РІ СЃРїРёСЃРѕРє СѓРґР°Р»РµРЅРЅС‹С…
                    
            except Exception as e:
                print(f"РћС€РёР±РєР° РїСЂРё СѓРґР°Р»РµРЅРёРё СЃС‚СѓРґРµРЅС‚Р° {student.get_full_name()}: {e}")
        
        return JsonResponse({
            'success': True,
            'deleted_count': deleted_count,
            'deleted_ids': deleted_students_ids  # Р’РѕР·РІСЂР°С‰Р°РµРј СЃРїРёСЃРѕРє ID РґР»СЏ СѓРґР°Р»РµРЅРёСЏ РёР· DOM
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'РћС€РёР±РєР° РїСЂРё РјР°СЃСЃРѕРІРѕРј СѓРґР°Р»РµРЅРёРё: {str(e)}'
        })

@require_http_methods(["POST"])
def students_export_view(request):
    """Р­РєСЃРїРѕСЂС‚ РІС‹Р±СЂР°РЅРЅС‹С… СЃС‚СѓРґРµРЅС‚РѕРІ РІ Excel РёР»Рё PDF"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ РґР°РЅРЅС‹С…'
        })
    
    try:
        format_type = data.get('format', 'excel')  # 'excel' РёР»Рё 'pdf'
        
        if data.get('all'):
            # Р’С‹Р±СЂР°РЅС‹ РІСЃРµ СЃС‚СѓРґРµРЅС‚С‹ СЃ СѓС‡РµС‚РѕРј С„РёР»СЊС‚СЂРѕРІ
            students = Student.objects.select_related('user', 'group', 'group__faculty').all()
            
            # РџСЂРёРјРµРЅСЏРµРј С„РёР»СЊС‚СЂС‹
            filters = data.get('filters', {})
            if filters.get('search'):
                search_query = filters['search']
                students = students.filter(
                    Q(first_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(middle_name__icontains=search_query) |
                    Q(email__icontains=search_query)
                )
            
            if filters.get('group'):
                students = students.filter(group_id=filters['group'])
            
            if filters.get('status') == 'active':
                students = students.filter(user__is_active=True, study_status='active')
            elif filters.get('status') == 'inactive':
                students = students.filter(user__is_active=False)
            elif filters.get('status'):
                students = students.filter(study_status=filters['status'])
                
            if filters.get('course'):
                students = students.filter(course=filters['course'])
        else:
            # Р’С‹Р±СЂР°РЅС‹ РєРѕРЅРєСЂРµС‚РЅС‹Рµ СЃС‚СѓРґРµРЅС‚С‹
            student_ids = data.get('ids', [])
            students = Student.objects.select_related('user', 'group', 'group__faculty').filter(id__in=student_ids)
        
        # РЎРѕСЂС‚РёСЂРѕРІРєР°
        students = students.order_by('last_name', 'first_name')
        
        if not students.exists():
            return JsonResponse({
                'success': False,
                'error': 'РќРµС‚ СЃС‚СѓРґРµРЅС‚РѕРІ РґР»СЏ СЌРєСЃРїРѕСЂС‚Р°'
            })
        
        # Р“РµРЅРµСЂРёСЂСѓРµРј С„Р°Р№Р»
        if format_type == 'excel':
            file_path = generate_excel_export(students)
            filename = f'students_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:  # PDF
            file_path = generate_pdf_export(students)
            filename = f'students_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            content_type = 'application/pdf'
        
        # Р’РѕР·РІСЂР°С‰Р°РµРј С„Р°Р№Р»
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=content_type,
            as_attachment=True,
            filename=filename
        )
        
        # РЈРґР°Р»СЏРµРј РІСЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р» РїРѕСЃР»Рµ РѕС‚РїСЂР°РІРєРё
        def cleanup_file():
            try:
                os.unlink(file_path)
            except:
                pass
        
        # РџР»Р°РЅРёСЂСѓРµРј СѓРґР°Р»РµРЅРёРµ С„Р°Р№Р»Р°
        import threading
        threading.Timer(60, cleanup_file).start()
        
        return response
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'РћС€РёР±РєР° РїСЂРё СЌРєСЃРїРѕСЂС‚Рµ: {str(e)}'
        })


def generate_excel_export(students):
    """Р“РµРЅРµСЂР°С†РёСЏ Excel С„Р°Р№Р»Р° СЃ РґР°РЅРЅС‹РјРё СЃС‚СѓРґРµРЅС‚РѕРІ"""
    # РџРѕРґРіРѕС‚Р°РІР»РёРІР°РµРј РґР°РЅРЅС‹Рµ
    data = []
    for student in students:
        row = {
            'Р¤Р°РјРёР»РёСЏ': student.last_name,
            'РРјСЏ': student.first_name,
            'РћС‚С‡РµСЃС‚РІРѕ': student.middle_name or '',
            'Email': student.email,
            'РўРµР»РµС„РѕРЅ': student.phone or '',
            'Р“СЂСѓРїРїР°': student.group.name if student.group else '',
            'Р¤Р°РєСѓР»СЊС‚РµС‚': student.group.faculty.name if student.group and student.group.faculty else '',
            'РљСѓСЂСЃ': dict(Student._meta.get_field('course').choices).get(student.course, '') if student.course else '',
            'РЎС‚Р°С‚СѓСЃ РѕР±СѓС‡РµРЅРёСЏ': dict(Student._meta.get_field('study_status').choices).get(student.study_status, ''),
            'Р”РѕСЃС‚СѓРї Рє СЃРёСЃС‚РµРјРµ': 'Р•СЃС‚СЊ' if hasattr(student, 'user') and student.user else 'РќРµС‚',
            'РђРєС‚РёРІРµРЅ': 'Р”Р°' if hasattr(student, 'user') and student.user and student.user.is_active else 'РќРµС‚',
            'Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ': student.created_at.strftime('%d.%m.%Y %H:%M') if hasattr(student, 'created_at') and student.created_at else '',
        }
        data.append(row)
    
    # РЎРѕР·РґР°РµРј DataFrame
    df = pd.DataFrame(data)
    
    # РЎРѕР·РґР°РµРј РІСЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р»
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    
    # Р—Р°РїРёСЃС‹РІР°РµРј РІ Excel СЃ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµРј
    with pd.ExcelWriter(temp_file.name, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='РЎС‚СѓРґРµРЅС‚С‹')
        
        # РџРѕР»СѓС‡Р°РµРј worksheet РґР»СЏ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ
        worksheet = writer.sheets['РЎС‚СѓРґРµРЅС‚С‹']
        
        # РђРІС‚РѕС€РёСЂРёРЅР° РєРѕР»РѕРЅРѕРє
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
        
        # РЎС‚РёР»СЊ Р·Р°РіРѕР»РѕРІРєРѕРІ
        from openpyxl.styles import Font, PatternFill
        
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        
        for cell in worksheet[1]:
            cell.font = header_font
            cell.fill = header_fill
    
    temp_file.close()
    return temp_file.name


def generate_pdf_export(students):
    """Р“РµРЅРµСЂР°С†РёСЏ PDF С„Р°Р№Р»Р° СЃ РґР°РЅРЅС‹РјРё СЃС‚СѓРґРµРЅС‚РѕРІ"""
    # РЎРѕР·РґР°РµРј РІСЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р»
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    
    # РЎРѕР·РґР°РµРј PDF РґРѕРєСѓРјРµРЅС‚
    doc = SimpleDocTemplate(temp_file.name, pagesize=A4)
    story = []
    
    # РЎС‚РёР»Рё
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=18,
        textColor=colors.HexColor('#366092'),
        alignment=1  # С†РµРЅС‚СЂРёСЂРѕРІР°РЅРёРµ
    )
    
    # Р—Р°РіРѕР»РѕРІРѕРє
    title = Paragraph(f"РЎРїРёСЃРѕРє СЃС‚СѓРґРµРЅС‚РѕРІ", title_style)
    story.append(title)
    story.append(Spacer(1, 20))
    
    # РРЅС„РѕСЂРјР°С†РёСЏ РѕР± СЌРєСЃРїРѕСЂС‚Рµ
    info_text = f"""
    <b>Р”Р°С‚Р° СЌРєСЃРїРѕСЂС‚Р°:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}<br/>
    <b>РљРѕР»РёС‡РµСЃС‚РІРѕ СЃС‚СѓРґРµРЅС‚РѕРІ:</b> {students.count()}<br/>
    """
    info_paragraph = Paragraph(info_text, styles['Normal'])
    story.append(info_paragraph)
    story.append(Spacer(1, 20))
    
    # РџРѕРґРіРѕС‚Р°РІР»РёРІР°РµРј РґР°РЅРЅС‹Рµ РґР»СЏ С‚Р°Р±Р»РёС†С‹
    table_data = [
        ['в„–', 'Р¤РРћ', 'Email', 'Р“СЂСѓРїРїР°', 'РЎС‚Р°С‚СѓСЃ', 'Р”РѕСЃС‚СѓРї']
    ]
    
    for i, student in enumerate(students, 1):
        full_name = f"{student.last_name} {student.first_name}"
        if student.middle_name:
            full_name += f" {student.middle_name}"
        
        group_name = student.group.name if student.group else 'РќРµ СѓРєР°Р·Р°РЅР°'
        
        status = dict(Student._meta.get_field('study_status').choices).get(
            student.study_status, 'РќРµ СѓРєР°Р·Р°РЅ'
        )
        
        access = 'Р•СЃС‚СЊ' if hasattr(student, 'user') and student.user else 'РќРµС‚'
        
        table_data.append([
            str(i),
            full_name,
            student.email or 'РќРµ СѓРєР°Р·Р°РЅ',
            group_name,
            status,
            access
        ])
    
    # РЎРѕР·РґР°РµРј С‚Р°Р±Р»РёС†Сѓ
    table = Table(table_data, repeatRows=1)
    
    # РЎС‚РёР»СЊ С‚Р°Р±Р»РёС†С‹
    table_style = TableStyle([
        # Р—Р°РіРѕР»РѕРІРѕРє
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#366092')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Р”Р°РЅРЅС‹Рµ
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        
        # Р§РµСЂРµРґСѓСЋС‰РёРµСЃСЏ СЃС‚СЂРѕРєРё
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
    ])
    
    table.setStyle(table_style)
    story.append(table)
    
    # Р“РµРЅРµСЂРёСЂСѓРµРј PDF
    doc.build(story)
    
    temp_file.close()
    return temp_file.name
