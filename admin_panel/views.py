# admin_panel/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, F, Sum, Avg
from django.db.models.functions import TruncMonth
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
import json
import secrets
import string
import pandas as pd
import io
import re
import uuid
from datetime import datetime, timedelta, date
from importlib import import_module
from urllib.parse import urlencode
import tempfile
import os
import csv
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.sessions.models import Session
from collections import defaultdict

ATTENDANCE_STATUS_META = {
    'order': ['', 'absent', 'late', 'excused'],
    'map': {
        '': {
            'label': 'Присутствие',
            'short': '',
            'class': 'status-present',
        },
        'absent': {
            'label': 'Отсутствовал',
            'short': 'Н',
            'class': 'status-absent',
        },
        'late': {
            'label': 'Опоздал',
            'short': 'О',
            'class': 'status-late',
        },
        'excused': {
            'label': 'Уважительная причина',
            'short': 'У',
            'class': 'status-excused',
        },
    },
}


# Безопасная проверка импорта моделей
try:
    from .models import (
        Student,
        Group,
        Faculty,
        Teacher,
        Subject,
        SubjectAssignment,
        ActivityLog,
        ScheduleWeek,
        ScheduleTeacherSlot,
        PasswordResetRequest,
        GradeRecord,
        GradeColumnContext,
        AttendanceRecord,
    )
    MODELS_AVAILABLE = True
except:
    MODELS_AVAILABLE = False

from .activity import log_activity, serialize_activity_log


MONTH_LABELS_RU = [
    'Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
    'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек',
]


def format_month_label(value):
    """Возвращает локализованный ярлык месяца."""
    if not value:
        return ''
    if isinstance(value, datetime):
        value = value.date()
    try:
        return f"{MONTH_LABELS_RU[value.month - 1]} {value.year}"
    except (AttributeError, IndexError):
        return value.strftime('%Y-%m')


def parse_date_param(value):
    """Парсинг даты из строки формата YYYY-MM-DD."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def get_period_from_request(request, default_days=180):
    """Получает диапазон дат из GET-параметров с дефолтом."""
    today = timezone.now().date()
    default_start = today - timedelta(days=default_days)
    start_date = parse_date_param(request.GET.get('start_date')) or default_start
    end_date = parse_date_param(request.GET.get('end_date')) or today
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return start_date, end_date


def build_filter_query(params):
    """Формирует query string с непустыми параметрами."""
    cleaned = {key: value for key, value in params.items() if value not in [None, '', []]}
    return urlencode(cleaned)


def build_statistics_dataset(start_date, end_date):
    """Формирует набор данных для страницы статистики."""
    if not MODELS_AVAILABLE:
        return {'available': False}

    students_qs = Student.objects.all()
    grades_qs = GradeRecord.objects.filter(
        lesson_date__range=(start_date, end_date)
    )
    attendance_qs = AttendanceRecord.objects.filter(
        lesson_date__range=(start_date, end_date)
    )

    summary = {
        'total_students': students_qs.count(),
        'active_students': students_qs.filter(study_status='active').count(),
        'new_students': students_qs.filter(
            enrollment_date__range=(start_date, end_date)
        ).count(),
        'groups_total': Group.objects.count(),
        'teachers_total': Teacher.objects.count(),
        'subjects_total': Subject.objects.count(),
    }

    avg_grade = grades_qs.aggregate(value=Avg('value'))['value'] or 0
    grade_overview = {
        'avg_grade': round(avg_grade, 2) if avg_grade else 0,
        'grade_volume': grades_qs.count(),
    }

    grade_distribution_counts = {
        row['value']: row['total']
        for row in grades_qs.values('value').annotate(total=Count('id'))
    }
    grade_distribution = [
        {
            'grade': value,
            'total': grade_distribution_counts.get(value, 0),
        }
        for value in range(1, 6)
    ]

    status_counts = {
        row['study_status']: row['total']
        for row in students_qs.values('study_status').annotate(total=Count('id'))
    }
    status_distribution = [
        {
            'status': key,
            'label': label,
            'total': status_counts.get(key, 0),
        }
        for key, label in Student.STUDY_STATUS_CHOICES
    ]

    faculty_distribution = []
    faculty_rows = (
        students_qs.filter(group__faculty__isnull=False)
        .values('group__faculty__name', 'group__faculty__code')
        .annotate(total=Count('id'))
        .order_by('-total', 'group__faculty__name')
    )
    for row in faculty_rows:
        faculty_distribution.append({
            'name': row['group__faculty__name'],
            'code': row['group__faculty__code'],
            'total': row['total'],
        })

    enrollment_trend = []
    enrollment_rows = (
        Student.objects.filter(
            enrollment_date__isnull=False,
            enrollment_date__range=(start_date, end_date),
        )
        .annotate(month=TruncMonth('enrollment_date'))
        .values('month')
        .annotate(total=Count('id'))
        .order_by('month')
    )
    for row in enrollment_rows:
        month_dt = row['month']
        enrollment_trend.append({
            'month': month_dt.strftime('%Y-%m-01') if month_dt else '',
            'label': format_month_label(month_dt),
            'total': row['total'],
        })

    attendance_summary_values = attendance_qs.aggregate(
        total=Count('id'),
        present=Count('id', filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
        absences=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        late=Count('id', filter=Q(status=AttendanceRecord.STATUS_LATE)),
        excused=Count('id', filter=Q(status=AttendanceRecord.STATUS_EXCUSED)),
    )
    attendance_summary = {
        'total': attendance_summary_values.get('total') or 0,
        'present': attendance_summary_values.get('present') or 0,
        'absent': attendance_summary_values.get('absences') or 0,
        'late': attendance_summary_values.get('late') or 0,
        'excused': attendance_summary_values.get('excused') or 0,
    }
    if attendance_summary['total']:
        attendance_summary['rate'] = round(
            attendance_summary['present'] / attendance_summary['total'] * 100, 2
        )
    else:
        attendance_summary['rate'] = 0

    attendance_trend = []
    attendance_rows = (
        attendance_qs.annotate(month=TruncMonth('lesson_date'))
        .values('month')
        .annotate(
            total=Count('id'),
            absent=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
            late=Count('id', filter=Q(status=AttendanceRecord.STATUS_LATE)),
            excused=Count('id', filter=Q(status=AttendanceRecord.STATUS_EXCUSED)),
        )
        .order_by('month')
    )
    for row in attendance_rows:
        month_dt = row['month']
        attendance_trend.append({
            'month': month_dt.strftime('%Y-%m-01') if month_dt else '',
            'label': format_month_label(month_dt),
            'total': row['total'],
            'absent': row['absent'],
            'late': row['late'],
            'excused': row['excused'],
        })

    top_subjects = []
    top_subject_rows = (
        grades_qs.filter(subject__isnull=False)
        .values('subject__name')
        .annotate(
            avg_value=Avg('value'),
            total=Count('id'),
        )
        .order_by('-total')[:5]
    )
    for row in top_subject_rows:
        top_subjects.append({
            'subject': row['subject__name'] or 'Без названия',
            'avg': round(row['avg_value'], 2) if row['avg_value'] else 0,
            'total': row['total'],
        })

    return {
        'available': True,
        'summary': summary,
        'grade_overview': grade_overview,
        'grade_distribution': grade_distribution,
        'status_distribution': status_distribution,
        'faculty_distribution': faculty_distribution,
        'enrollment_trend': enrollment_trend,
        'attendance_summary': attendance_summary,
        'attendance_trend': attendance_trend,
        'top_subjects': top_subjects,
    }


def build_analytics_dataset(start_date, end_date, faculty_id=None):
    """Формирует расширенный набор аналитики."""
    base_result = {
        'available': MODELS_AVAILABLE,
        'faculty_summary': [],
        'teacher_load': [],
        'grade_distribution': [],
        'overview': {},
    }
    if not MODELS_AVAILABLE:
        return base_result

    faculties_qs = Faculty.objects.filter(is_active=True)
    if faculty_id:
        faculties_qs = faculties_qs.filter(id=faculty_id)
    faculties = list(faculties_qs)

    if not faculties:
        base_result['overview'] = {
            'students_total': 0,
            'active_students': 0,
            'new_students': 0,
            'avg_grade': 0,
            'attendance_rate': 0,
            'teachers_total': 0,
            'groups_total': 0,
        }
        return base_result

    faculty_ids = [faculty.id for faculty in faculties]
    faculty_summary_map = {
        faculty.id: {
            'id': faculty.id,
            'name': faculty.name,
            'code': faculty.code,
            'students_total': 0,
            'active_students': 0,
            'avg_grade': 0,
            'grade_volume': 0,
            'attendance_rate': 0,
            'attendance_total': 0,
            'attendance_breakdown': {
                'absent': 0,
                'late': 0,
                'excused': 0,
            },
        }
        for faculty in faculties
    }

    students_qs = Student.objects.filter(group__faculty_id__in=faculty_ids)
    student_counts = (
        students_qs
        .values('group__faculty_id')
        .annotate(
            total=Count('id'),
            active=Count('id', filter=Q(study_status='active')),
        )
    )
    for row in student_counts:
        summary = faculty_summary_map.get(row['group__faculty_id'])
        if summary:
            summary['students_total'] = row['total']
            summary['active_students'] = row['active']

    grade_filters = {
        'lesson_date__range': (start_date, end_date),
        'group__faculty_id__in': faculty_ids,
    }
    grades_qs = GradeRecord.objects.filter(**grade_filters)
    grade_stats = (
        grades_qs
        .values('group__faculty_id')
        .annotate(
            avg_value=Avg('value'),
            total=Count('id'),
        )
    )
    for row in grade_stats:
        summary = faculty_summary_map.get(row['group__faculty_id'])
        if summary:
            summary['avg_grade'] = round(row['avg_value'], 2) if row['avg_value'] else 0
            summary['grade_volume'] = row['total']

    attendance_filters = {
        'lesson_date__range': (start_date, end_date),
        'group__faculty_id__in': faculty_ids,
    }
    attendance_qs = AttendanceRecord.objects.filter(**attendance_filters)
    attendance_stats = (
        attendance_qs
        .values('group__faculty_id')
        .annotate(
            total=Count('id'),
            absent=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
            late=Count('id', filter=Q(status=AttendanceRecord.STATUS_LATE)),
            excused=Count('id', filter=Q(status=AttendanceRecord.STATUS_EXCUSED)),
        )
    )
    for row in attendance_stats:
        summary = faculty_summary_map.get(row['group__faculty_id'])
        if not summary:
            continue
        total = row['total'] or 0
        summary['attendance_total'] = total
        summary['attendance_breakdown'] = {
            'absent': row['absent'],
            'late': row['late'],
            'excused': row['excused'],
        }
        present = max(total - row['absent'], 0)
        summary['attendance_rate'] = round(
            (present / total) * 100, 2
        ) if total else 0

    grade_distribution_counts = {
        row['value']: row['total']
        for row in grades_qs.values('value').annotate(total=Count('id'))
    }
    grade_distribution = [
        {'grade': value, 'total': grade_distribution_counts.get(value, 0)}
        for value in range(1, 6)
    ]

    teacher_qs = Teacher.objects.filter(groups__faculty_id__in=faculty_ids).distinct()
    teacher_load = list(
        teacher_qs.annotate(
            groups_total=Count('groups', distinct=True),
            subjects_total=Count('subjects', distinct=True),
            students_total=Count('groups__students', distinct=True),
        )
        .order_by('-groups_total', '-students_total', 'last_name')[:8]
    )

    groups_total = Group.objects.filter(faculty_id__in=faculty_ids).count()
    teachers_total = teacher_qs.count()
    overall_attendance = attendance_qs.aggregate(
        total=Count('id'),
        absent=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
    )
    total_attendance = overall_attendance.get('total') or 0
    absences = overall_attendance.get('absent') or 0
    attendance_rate = round(
        (max(total_attendance - absences, 0) / total_attendance) * 100, 2
    ) if total_attendance else 0

    overall_grade_avg = grades_qs.aggregate(avg=Avg('value'))['avg']
    overview = {
        'students_total': students_qs.count(),
        'active_students': students_qs.filter(study_status='active').count(),
        'new_students': students_qs.filter(
            enrollment_date__range=(start_date, end_date)
        ).count(),
        'avg_grade': round(overall_grade_avg or 0, 2) if overall_grade_avg else 0,
        'attendance_rate': attendance_rate,
        'teachers_total': teachers_total,
        'groups_total': groups_total,
    }

    groups_queryset = (
        Group.objects.filter(faculty_id__in=faculty_ids)
        .select_related('faculty')
        .annotate(
            students_total=Count('students', distinct=True),
            active_students_total=Count('students', filter=Q(students__study_status='active'), distinct=True),
        )
    )
    course_summary_map = {}
    group_summary = []
    for group in groups_queryset:
        course_num = group.current_course or 1
        summary_row = course_summary_map.setdefault(course_num, {
            'course': course_num,
            'groups_total': 0,
            'students_total': 0,
            'active_students_total': 0,
        })
        summary_row['groups_total'] += 1
        summary_row['students_total'] += group.students_total or 0
        summary_row['active_students_total'] += group.active_students_total or 0

        group_summary.append({
            'code': group.code,
            'faculty': group.faculty.name if group.faculty else '',
            'profession': group.profession,
            'course': course_num,
            'students_total': group.students_total or 0,
            'active_students_total': group.active_students_total or 0,
            'status': group.status_display,
        })

    course_summary = sorted(course_summary_map.values(), key=lambda item: item['course'])
    for row in course_summary:
        groups_total = row.get('groups_total') or 0
        students_total = row.get('students_total') or 0
        row['avg_group_size'] = round(students_total / groups_total, 2) if groups_total else 0
    group_summary = sorted(group_summary, key=lambda item: (-item['students_total'], item['code']))[:10]

    base_result.update({
        'faculty_summary': list(faculty_summary_map.values()),
        'teacher_load': [
            {
                'name': teacher.get_full_name(),
                'groups_total': teacher.groups_total,
                'subjects_total': teacher.subjects_total,
                'students_total': teacher.students_total,
            }
            for teacher in teacher_load
        ],
        'grade_distribution': grade_distribution,
        'overview': overview,
        'course_summary': course_summary,
        'group_summary': group_summary,
    })
    return base_result

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

    # Если преподаватель - перенаправляем в кабинет преподавателя
    try:
        teacher = request.user.teacher_profile
        return redirect('teacher_dashboard')
    except AttributeError:
        pass
    
    # Если обычный пользователь без роли
    messages.warning(request, 'У вас нет назначенной роли в системе. Обратитесь к администратору.')
    return redirect('login')

@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def admin_dashboard_view(request):
    """Админ-панель - только для администраторов"""
    students_count = 0
    groups_count = 0
    faculties_count = 0
    recent_logs = []

    if MODELS_AVAILABLE:
        try:
            students_count = Student.objects.count()
            groups_count = Group.objects.filter(is_active=True).count()
            faculties_count = Faculty.objects.filter(is_active=True).count()
        except Exception as exc:
            print(f"Ошибка получения статистики: {str(exc)}")

        try:
            now = timezone.now()
            recent_logs_queryset = ActivityLog.objects.select_related('user').order_by('-created_at')[:10]
            recent_logs = [serialize_activity_log(log, now) for log in recent_logs_queryset]
        except Exception as exc:
            print(f"Ошибка получения логов: {str(exc)}")
            recent_logs = []

    context = {
        'students_count': students_count,
        'groups_count': groups_count,
        'faculties_count': faculties_count,
        'recent_logs': recent_logs,
        'activity_log_add_url': reverse('activity_log_add'),
        'activity_log_remove_url': reverse('activity_log_remove'),
        'activity_log_clear_url': reverse('activity_log_clear'),
    }

    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def statistics_view(request):
    """Подробная статистика с графиками."""
    start_date, end_date = get_period_from_request(request)
    dataset = build_statistics_dataset(start_date, end_date)

    filter_query = build_filter_query({
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
    })

    context = {
        'filters': {
            'start_date': start_date,
            'end_date': end_date,
        },
        'filter_query': filter_query,
        'statistics': dataset,
    }
    return render(request, 'admin_panel/statistics.html', context)


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def statistics_export_view(request):
    """Экспорт статистики в CSV."""
    start_date, end_date = get_period_from_request(request)
    dataset = build_statistics_dataset(start_date, end_date)
    if not dataset.get('available'):
        return HttpResponse('Данные недоступны', status=400)

    response = HttpResponse(content_type='text/csv')
    filename = f"statistics_{start_date.isoformat()}_{end_date.isoformat()}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Период', start_date.isoformat(), end_date.isoformat()])
    writer.writerow([])

    summary = dataset.get('summary', {})
    writer.writerow(['Общая сводка'])
    writer.writerow(['Всего студентов', summary.get('total_students', 0)])
    writer.writerow(['Активных студентов', summary.get('active_students', 0)])
    writer.writerow(['Новых за период', summary.get('new_students', 0)])
    writer.writerow(['Групп', summary.get('groups_total', 0)])
    writer.writerow(['Преподавателей', summary.get('teachers_total', 0)])
    writer.writerow(['Дисциплин', summary.get('subjects_total', 0)])
    writer.writerow([])

    grade_data = dataset.get('grade_overview', {})
    writer.writerow(['Оценки'])
    writer.writerow(['Средний балл', grade_data.get('avg_grade', 0)])
    writer.writerow(['Количество оценок', grade_data.get('grade_volume', 0)])
    writer.writerow([])

    writer.writerow(['Динамика поступлений'])
    writer.writerow(['Месяц', 'Студентов'])
    for row in dataset.get('enrollment_trend', []):
        writer.writerow([row.get('label', ''), row.get('total', 0)])
    writer.writerow([])

    writer.writerow(['Посещаемость по месяцам'])
    writer.writerow(['Месяц', 'Всего отметок', 'Отсутствий', 'Опозданий', 'Уважительных'])
    for row in dataset.get('attendance_trend', []):
        writer.writerow([
            row.get('label', ''),
            row.get('total', 0),
            row.get('absent', 0),
            row.get('late', 0),
            row.get('excused', 0),
        ])
    writer.writerow([])

    writer.writerow(['Распределение по статусам'])
    writer.writerow(['Статус', 'Количество'])
    for row in dataset.get('status_distribution', []):
        writer.writerow([row.get('label', ''), row.get('total', 0)])
    writer.writerow([])

    writer.writerow(['Распределение по специальностям'])
    writer.writerow(['Специальность', 'Код', 'Студентов'])
    for row in dataset.get('faculty_distribution', []):
        writer.writerow([row.get('name', ''), row.get('code', ''), row.get('total', 0)])
    writer.writerow([])

    writer.writerow(['ТОП дисциплин по оценкам'])
    writer.writerow(['Предмет', 'Средний балл', 'Количество оценок'])
    for row in dataset.get('top_subjects', []):
        writer.writerow([row.get('subject', ''), row.get('avg', 0), row.get('total', 0)])

    return response


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def analytics_view(request):
    """Расширенная аналитика с визуализациями и таблицами."""
    start_date, end_date = get_period_from_request(request, default_days=365)
    faculty_param = request.GET.get('faculty')
    try:
        faculty_id = int(faculty_param) if faculty_param else None
    except (TypeError, ValueError):
        faculty_id = None

    dataset = build_analytics_dataset(start_date, end_date, faculty_id)
    filter_query = build_filter_query({
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'faculty': faculty_param,
    })

    faculty_options = Faculty.objects.filter(is_active=True).order_by('name') if MODELS_AVAILABLE else []

    context = {
        'filters': {
            'start_date': start_date,
            'end_date': end_date,
            'faculty': faculty_param,
        },
        'filter_query': filter_query,
        'analytics': dataset,
        'faculty_options': faculty_options,
        'selected_faculty': faculty_param,
    }
    return render(request, 'admin_panel/analytics.html', context)


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def analytics_export_view(request):
    """Экспорт расширенной аналитики в CSV."""
    start_date, end_date = get_period_from_request(request, default_days=365)
    faculty_param = request.GET.get('faculty')
    try:
        faculty_id = int(faculty_param) if faculty_param else None
    except (TypeError, ValueError):
        faculty_id = None

    dataset = build_analytics_dataset(start_date, end_date, faculty_id)
    if not dataset.get('available'):
        return HttpResponse('Данные недоступны', status=400)

    response = HttpResponse(content_type='text/csv')
    filename = f"analytics_{start_date.isoformat()}_{end_date.isoformat()}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response, delimiter=';')

    writer.writerow(['Период', start_date.isoformat(), end_date.isoformat()])
    if faculty_param:
        writer.writerow(['Фильтр по специальности', faculty_param])
    writer.writerow([])

    overview = dataset.get('overview', {})
    writer.writerow(['Сводные показатели'])
    writer.writerow(['Студентов', overview.get('students_total', 0)])
    writer.writerow(['Активных студентов', overview.get('active_students', 0)])
    writer.writerow(['Новых студентов', overview.get('new_students', 0)])
    writer.writerow(['Средний балл', overview.get('avg_grade', 0)])
    writer.writerow(['Посещаемость %', overview.get('attendance_rate', 0)])
    writer.writerow(['Преподавателей', overview.get('teachers_total', 0)])
    writer.writerow(['Групп', overview.get('groups_total', 0)])
    writer.writerow([])

    writer.writerow(['Показатели по специальностям'])
    writer.writerow(['Специальность', 'Код', 'Студентов', 'Активных', 'Средний балл', 'Посещаемость %'])
    for row in dataset.get('faculty_summary', []):
        writer.writerow([
            row.get('name', ''),
            row.get('code', ''),
            row.get('students_total', 0),
            row.get('active_students', 0),
            row.get('avg_grade', 0),
            row.get('attendance_rate', 0),
        ])
    writer.writerow([])

    writer.writerow(['Нагрузка преподавателей'])
    writer.writerow(['Преподаватель', 'Групп', 'Предметов', 'Студентов'])
    for row in dataset.get('teacher_load', []):
        writer.writerow([
            row.get('name', ''),
            row.get('groups_total', 0),
            row.get('subjects_total', 0),
            row.get('students_total', 0),
        ])
    writer.writerow([])

    writer.writerow(['Распределение оценок'])
    writer.writerow(['Оценка', 'Количество'])
    for row in dataset.get('grade_distribution', []):
        writer.writerow([
            row.get('grade', ''),
            row.get('total', 0),
        ])

    return response


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
@require_POST
def activity_log_add_view(request):
    if not MODELS_AVAILABLE:
        return JsonResponse({'success': False, 'error': 'Журнал недоступен'}, status=400)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)

    description = (payload.get('description') or '').strip()
    if not description:
        return JsonResponse({'success': False, 'error': 'Описание обязательно'}, status=400)

    action_type = (payload.get('action_type') or ActivityLog.ACTION_OTHER).strip()
    valid_types = {choice[0] for choice in ActivityLog.ACTION_CHOICES}
    if action_type not in valid_types:
        action_type = ActivityLog.ACTION_OTHER

    icon = (payload.get('icon') or '').strip()
    metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else None

    log = ActivityLog.objects.create(
        user=request.user,
        action_type=action_type,
        description=description,
        icon=icon,
        metadata=metadata,
    )

    return JsonResponse({'success': True, 'log': serialize_activity_log(log)})


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
@require_POST
def activity_log_remove_view(request):
    if not MODELS_AVAILABLE:
        return JsonResponse({'success': False, 'error': 'Журнал недоступен'}, status=400)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
        log_id = int(payload.get('log_id'))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Некорректный идентификатор'}, status=400)

    deleted, _ = ActivityLog.objects.filter(id=log_id).delete()
    return JsonResponse({'success': True, 'deleted': deleted})


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
@require_POST
def activity_log_clear_view(request):
    if not MODELS_AVAILABLE:
        return JsonResponse({'success': False, 'error': 'Журнал недоступен'}, status=400)

    ActivityLog.objects.all().delete()
    return JsonResponse({'success': True})

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
            tokens = [token for token in re.split(r'[\s,;]+', search) if token]
            for token in tokens:
                students = students.filter(
                    Q(first_name__icontains=token) |
                    Q(last_name__icontains=token) |
                    Q(middle_name__icontains=token) |
                    Q(email__icontains=token) |
                    Q(student_id__icontains=token) |
                    Q(user__username__icontains=token) |
                    Q(group__code__icontains=token)
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
        
        password_requests = PasswordResetRequest.objects.select_related('student').filter(
            role=PasswordResetRequest.ROLE_STUDENT,
            status=PasswordResetRequest.STATUS_PENDING
        ).order_by('created_at')

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
            },
            'password_reset_requests': password_requests,
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


@login_required
def teachers_list_view(request):
    """Список преподавателей с фильтрацией и поиском"""
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции.')
        return redirect('admin_dashboard')

    try:
        search = request.GET.get('search', '').strip()
        subject_filter = request.GET.get('subject', '').strip()
        status_filter = request.GET.get('status', '').strip()

        teachers = Teacher.objects.select_related('user').prefetch_related(
            'subjects',
            'groups',
            'groups__faculty'
        ).all()

        if search:
            tokens = [token for token in re.split(r'[\s,;]+', search) if token]
            for token in tokens:
                teachers = teachers.filter(
                    Q(first_name__icontains=token) |
                    Q(last_name__icontains=token) |
                    Q(middle_name__icontains=token) |
                    Q(email__icontains=token) |
                    Q(phone__icontains=token) |
                    Q(subjects__name__icontains=token) |
                    Q(subjects__short_name__icontains=token)
                )

        if subject_filter:
            teachers = teachers.filter(subjects__id=subject_filter)

        if status_filter == 'active':
            teachers = teachers.filter(user__isnull=False, user__is_active=True)
        elif status_filter == 'inactive':
            teachers = teachers.filter(Q(user__isnull=True) | Q(user__is_active=False))
        elif status_filter == 'curator':
            teachers = teachers.filter(is_curator=True)

        teachers = teachers.distinct().order_by('last_name', 'first_name')
        subjects = Subject.objects.filter(is_active=True).order_by('name')

        total_teachers = teachers.count()
        paginator = Paginator(teachers, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        active_filters = 0
        if subject_filter:
            active_filters += 1
        if status_filter:
            active_filters += 1

        password_requests = PasswordResetRequest.objects.select_related('teacher').filter(
            role=PasswordResetRequest.ROLE_TEACHER,
            status=PasswordResetRequest.STATUS_PENDING
        ).order_by('created_at')

        context = {
            'page_obj': page_obj,
            'subjects': subjects,
            'search': search,
            'subject_filter': subject_filter,
            'status_filter': status_filter,
            'total_teachers': total_teachers,
            'active_filters': active_filters,
            'current_filters': {
                'search': search,
                'subject': subject_filter,
                'status': status_filter,
            },
            'password_reset_requests': password_requests,
        }

        return render(request, 'admin_panel/teachers/list.html', context)

    except Exception as e:
        import logging, traceback
        logging.exception("Ошибка загрузки списка преподавателей")
        trace = traceback.format_exc()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': str(e),
                'traceback': trace,
            }, status=500)
        messages.error(request, f'Ошибка загрузки преподавателей: {str(e)}')
        return render(request, 'admin_panel/teachers/error.html', {
            'error': str(e),
            'traceback': trace,
        }, status=500)


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def teacher_create_view(request):
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции.')
        return redirect('admin_dashboard')

    subjects_qs = Subject.objects.filter(is_active=True).order_by('name')
    assignments_qs = SubjectAssignment.objects.select_related('subject', 'faculty').filter(
        subject__in=subjects_qs,
        is_active=True
    )

    group_cache = {}
    subject_assignments_map = defaultdict(list)

    for assignment in assignments_qs:
        group_key = (assignment.faculty_id, assignment.profession)
        if group_key not in group_cache:
            related_groups = Group.objects.filter(
                faculty_id=assignment.faculty_id,
                profession=assignment.profession,
                is_active=True
            ).order_by('code')
            group_cache[group_key] = [
                {
                    'id': group.id,
                    'code': group.code,
                    'profession': group.profession,
                    'course': group.current_course,
                }
                for group in related_groups
            ]

        groups_for_assignment = [
            {
                'id': group['id'],
                'code': group['code'],
                'profession': group['profession'],
            }
            for group in group_cache[group_key]
            if group['course'] == assignment.course
        ]

        subject_assignments_map[assignment.subject_id].append({
            'id': assignment.id,
            'course': assignment.get_course_display(),
            'profession': assignment.profession,
            'faculty': assignment.faculty.name,
            'faculty_code': assignment.faculty.code,
            'groups': groups_for_assignment,
        })

    subjects_data = [
        {
            'id': subject.id,
            'name': subject.name,
            'short_name': subject.short_name or '',
            'assignments': subject_assignments_map.get(subject.id, []),
        }
        for subject in subjects_qs
    ]

    selected_subject_ids = []
    selected_group_ids = []

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        middle_name = request.POST.get('middle_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        position = request.POST.get('position', '').strip() or 'Преподаватель'
        hire_date = request.POST.get('hire_date')
        notes = request.POST.get('notes', '').strip()
        subject_ids = [int(pk) for pk in request.POST.getlist('subjects') if pk.isdigit()]
        group_ids = [int(pk) for pk in request.POST.getlist('groups') if pk.isdigit()]
        selected_subject_ids = [str(pk) for pk in subject_ids]
        selected_group_ids = [str(pk) for pk in group_ids]
        is_curator = request.POST.get('is_curator') == 'on'
        is_active = request.POST.get('is_active') != 'off'
        create_account = request.POST.get('create_account') == 'on'
        send_email_flag = request.POST.get('send_email') == 'on'

        errors = {}
        if not first_name:
            errors['first_name'] = 'Имя обязательно для заполнения'
        if not last_name:
            errors['last_name'] = 'Фамилия обязательна для заполнения'
        if not email:
            errors['email'] = 'Email обязателен для заполнения'
        elif Teacher.objects.filter(email=email).exists():
            errors['email'] = 'Преподаватель с таким email уже существует'

        hire_date_value = None
        if hire_date:
            try:
                hire_date_value = datetime.strptime(hire_date, '%Y-%m-%d').date()
            except ValueError:
                errors['hire_date'] = 'Неверный формат даты приема'

        if errors:
            for msg in errors.values():
                messages.error(request, msg)
            context = {
                'subjects_data': subjects_data,
                'form_data': request.POST,
                'errors': errors,
                'selected_subjects': selected_subject_ids,
                'selected_groups': selected_group_ids,
            }
            return render(request, 'admin_panel/teachers/create.html', context)

        try:
            with transaction.atomic():
                teacher = Teacher.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=middle_name,
                    email=email,
                    phone=phone,
                    position=position,
                    hire_date=hire_date_value,
                    notes=notes,
                    is_curator=is_curator,
                    is_active=is_active,
                    created_by=request.user
                )

                if subject_ids:
                    teacher.subjects.set(Subject.objects.filter(id__in=subject_ids))
                if group_ids:
                    teacher.groups.set(Group.objects.filter(id__in=group_ids))

                if create_account:
                    username = generate_username(first_name, last_name)
                    password = generate_password()
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                    )
                    user.is_active = True
                    user.save()
                    teacher.user = user
                    teacher.save()

                    if send_email_flag:
                        send_teacher_credentials_email(teacher, username, password)

            messages.success(request, f'Преподаватель "{teacher.get_full_name()}" успешно создан')
            log_activity(
                request.user,
                ActivityLog.ACTION_CREATE,
                f'Добавлен преподаватель "{teacher.get_full_name()}"',
                'bi-person-workspace',
                {'teacher_id': teacher.id}
            )
            return redirect('admin_teachers')

        except Exception as exc:
            messages.error(request, f'Ошибка при создании преподавателя: {str(exc)}')
            context = {
                'subjects_data': subjects_data,
                'form_data': request.POST,
                'errors': {'common': str(exc)},
                'selected_subjects': selected_subject_ids,
                'selected_groups': selected_group_ids,
            }
            return render(request, 'admin_panel/teachers/create.html', context)

    context = {
        'subjects_data': subjects_data,
        'selected_subjects': [],
        'selected_groups': [],
        'form_data': {},
    }
    return render(request, 'admin_panel/teachers/create.html', context)


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def teacher_edit_view(request, teacher_id):
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции.')
        return redirect('admin_dashboard')

    teacher = get_object_or_404(Teacher, id=teacher_id)

    subjects_qs = Subject.objects.filter(is_active=True).order_by('name')
    assignments_qs = SubjectAssignment.objects.select_related('subject', 'faculty').filter(
        subject__in=subjects_qs,
        is_active=True
    )

    group_cache = {}
    subject_assignments_map = defaultdict(list)

    for assignment in assignments_qs:
        group_key = (assignment.faculty_id, assignment.profession)
        if group_key not in group_cache:
            related_groups = Group.objects.filter(
                faculty_id=assignment.faculty_id,
                profession=assignment.profession,
                is_active=True
            ).order_by('code')
            group_cache[group_key] = [
                {
                    'id': group.id,
                    'code': group.code,
                    'profession': group.profession,
                    'course': group.current_course,
                }
                for group in related_groups
            ]

        groups_for_assignment = [
            {
                'id': group['id'],
                'code': group['code'],
                'profession': group['profession'],
            }
            for group in group_cache[group_key]
            if group['course'] == assignment.course
        ]

        subject_assignments_map[assignment.subject_id].append({
            'id': assignment.id,
            'course': assignment.get_course_display(),
            'profession': assignment.profession,
            'faculty': assignment.faculty.name,
            'faculty_code': assignment.faculty.code,
            'groups': groups_for_assignment,
        })

    subjects_data = [
        {
            'id': subject.id,
            'name': subject.name,
            'short_name': subject.short_name or '',
            'assignments': subject_assignments_map.get(subject.id, []),
        }
        for subject in subjects_qs
    ]

    selected_subject_ids = [str(pk) for pk in teacher.subjects.values_list('id', flat=True)]
    selected_group_ids = [str(pk) for pk in teacher.groups.values_list('id', flat=True)]

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        middle_name = request.POST.get('middle_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        position = request.POST.get('position', '').strip() or teacher.position or 'Преподаватель'
        hire_date = request.POST.get('hire_date')
        notes = request.POST.get('notes', '').strip()
        subject_ids = [int(pk) for pk in request.POST.getlist('subjects') if pk.isdigit()]
        group_ids = [int(pk) for pk in request.POST.getlist('groups') if pk.isdigit()]
        selected_subject_ids = [str(pk) for pk in subject_ids]
        selected_group_ids = [str(pk) for pk in group_ids]
        is_curator = request.POST.get('is_curator') == 'on'
        is_active = request.POST.get('is_active') != 'off'
        create_account = request.POST.get('create_account') == 'on'
        send_email_flag = request.POST.get('send_email') == 'on'

        errors = {}
        if not first_name:
            errors['first_name'] = 'Имя обязательно для заполнения'
        if not last_name:
            errors['last_name'] = 'Фамилия обязательна для заполнения'
        if not email:
            errors['email'] = 'Email обязателен для заполнения'
        elif Teacher.objects.filter(email=email).exclude(id=teacher.id).exists():
            errors['email'] = 'Преподаватель с таким email уже существует'

        hire_date_value = None
        if hire_date:
            try:
                hire_date_value = datetime.strptime(hire_date, '%Y-%m-%d').date()
            except ValueError:
                errors['hire_date'] = 'Неверный формат даты приема'

        if errors:
            for msg in errors.values():
                messages.error(request, msg)
            context = {
                'teacher': teacher,
                'subjects_data': subjects_data,
                'form_data': request.POST,
                'errors': errors,
                'selected_subjects': selected_subject_ids,
                'selected_groups': selected_group_ids,
            }
            return render(request, 'admin_panel/teachers/edit.html', context)

        try:
            with transaction.atomic():
                teacher.first_name = first_name
                teacher.last_name = last_name
                teacher.middle_name = middle_name
                teacher.email = email
                teacher.phone = phone
                teacher.hire_date = hire_date_value
                teacher.position = position
                teacher.notes = notes
                teacher.is_curator = is_curator
                teacher.is_active = is_active
                teacher.save()

                teacher.subjects.set(Subject.objects.filter(id__in=subject_ids))
                teacher.groups.set(Group.objects.filter(id__in=group_ids))

                if create_account and not teacher.user:
                    username = generate_username(first_name, last_name)
                    password = generate_password()
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                    )
                    user.is_active = True
                    user.save()
                    teacher.user = user
                    teacher.save()

                    if send_email_flag:
                        send_teacher_credentials_email(teacher, username, password)
                elif teacher.user:
                    teacher.user.email = email
                    teacher.user.first_name = first_name
                    teacher.user.last_name = last_name
                    teacher.user.is_active = is_active
                    teacher.user.save()

            messages.success(request, f'Преподаватель "{teacher.get_full_name()}" успешно обновлен')
            log_activity(
                request.user,
                ActivityLog.ACTION_UPDATE,
                f'Обновлен преподаватель "{teacher.get_full_name()}"',
                'bi-person-workspace',
                {'teacher_id': teacher.id}
            )
            return redirect('admin_teacher_detail', teacher_id=teacher.id)

        except Exception as exc:
            messages.error(request, f'Ошибка при сохранении преподавателя: {str(exc)}')
            context = {
                'teacher': teacher,
                'subjects_data': subjects_data,
                'form_data': request.POST,
                'errors': {'common': str(exc)},
                'selected_subjects': selected_subject_ids,
                'selected_groups': selected_group_ids,
            }
            return render(request, 'admin_panel/teachers/edit.html', context)

    context = {
        'teacher': teacher,
        'subjects_data': subjects_data,
        'selected_subjects': selected_subject_ids,
        'selected_groups': selected_group_ids,
        'form_data': {},
    }
    return render(request, 'admin_panel/teachers/edit.html', context)


@login_required
def teacher_detail_view(request, teacher_id):
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции.')
        return redirect('admin_dashboard')

    teacher = get_object_or_404(
        Teacher.objects.select_related('user').prefetch_related('subjects', 'groups', 'groups__faculty'),
        id=teacher_id
    )

    context = {
        'teacher': teacher,
        'subjects': teacher.subjects.all(),
        'groups': teacher.groups.all(),
    }
    return render(request, 'admin_panel/teachers/detail.html', context)


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def teacher_import_view(request):
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции.')
        return redirect('admin_dashboard')

    context = {
        'subjects': Subject.objects.filter(is_active=True).order_by('name'),
        'groups': Group.objects.filter(is_active=True).order_by('code'),
    }

    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            messages.error(request, 'Выберите файл для импорта')
            return render(request, 'admin_panel/teachers/import.html', context, status=400)

        try:
            df = pd.read_excel(file)
        except Exception as exc:
            messages.error(request, f'Не удалось прочитать файл: {str(exc)}')
            return render(request, 'admin_panel/teachers/import.html', context, status=400)

        original_columns = list(df.columns)
        df.columns = [str(col).strip().lower() for col in df.columns]

        def resolve_column(possible_names):
            for name in possible_names:
                if name in df.columns:
                    return name
            return None

        full_name_column = resolve_column(['full_name', 'fio', 'фио'])
        last_name_column = resolve_column(['last_name', 'фамилия', 'surname', 'last'])
        first_name_column = resolve_column(['first_name', 'имя', 'name', 'first'])
        middle_name_column = resolve_column(['middle_name', 'middlename', 'отчество', 'middle', 'second_name'])
        email_column = resolve_column(['email', 'e-mail', 'почта', 'электронная почта'])
        phone_column = resolve_column(['phone', 'телефон', 'tel', 'telephone'])

        missing_columns = []
        if not full_name_column and not (last_name_column and first_name_column):
            missing_columns.append('ФИО или (Фамилия и Имя)')
        if not email_column:
            missing_columns.append('Email')
        import_result = {
            'file_name': file.name,
            'columns': original_columns,
            'rows_total': len(df.index),
            'created_count': 0,
            'updated_count': 0,
            'unchanged_count': 0,
            'errors_count': 0,
            'created': [],
            'updated': [],
            'unchanged': [],
            'errors': [],
            'processed_count': 0,
            'status': 'pending',
            'summary': '',
        }

        if missing_columns:
            messages.error(
                request,
                f"Отсутствуют обязательные столбцы: {', '.join(missing_columns)}"
            )
            import_result['errors'].append({
                'row': 0,
                'message': f"Нет обязательных столбцов: {', '.join(missing_columns)}"
            })
            import_result['errors_count'] = len(import_result['errors'])
            import_result['status'] = 'error'
            import_result['summary'] = 'Импорт не выполнен из-за отсутствия обязательных столбцов'
            context['import_result'] = import_result
            return render(request, 'admin_panel/teachers/import.html', context, status=400)

        def clean_value(value):
            if pd.isna(value):
                return ''
            return str(value).strip()

        def split_full_name(full_name):
            parts = [part for part in full_name.replace(',', ' ').split() if part]
            if not parts:
                return '', '', ''
            if len(parts) == 1:
                return parts[0], 'Имя', ''
            last_name = parts[0]
            first_name = parts[1]
            middle_name = ' '.join(parts[2:]) if len(parts) > 2 else ''
            return last_name, first_name, middle_name

        for index, row in df.iterrows():
            try:
                if full_name_column:
                    full_name = clean_value(row.get(full_name_column, ''))
                    last_name, first_name, middle_name = split_full_name(full_name)
                else:
                    last_name = clean_value(row.get(last_name_column, '') if last_name_column else '')
                    first_name = clean_value(row.get(first_name_column, '') if first_name_column else '')
                    middle_name = clean_value(row.get(middle_name_column, '') if middle_name_column else '')
                    full_name = ' '.join(filter(None, [last_name, first_name, middle_name]))

                email = clean_value(row.get(email_column, ''))
                email = email.lower()
                phone = clean_value(row.get(phone_column, '')) if phone_column else ''

                row_number = index + 2  # Excel header row offset
                if full_name_column:
                    if not full_name:
                        import_result['errors'].append({
                            'row': row_number,
                            'message': 'ФИО обязательно для заполнения'
                        })
                        continue
                else:
                    if not last_name or not first_name:
                        import_result['errors'].append({
                            'row': row_number,
                            'message': 'Необходимо указать фамилию и имя в отдельных столбцах'
                        })
                        continue

                if not email:
                    import_result['errors'].append({
                        'row': row_number,
                        'message': 'Email обязателен для заполнения'
                    })
                    continue

                if full_name_column and (not last_name or not first_name):
                    import_result['errors'].append({
                        'row': row_number,
                        'message': f'Не удалось распознать фамилию и имя в значении "{full_name}"'
                    })
                    continue

                teacher = Teacher.objects.filter(email__iexact=email).first()
                created_flag = False

                if not teacher:
                    teacher = Teacher(
                        email=email,
                        first_name=first_name or 'Имя',
                        last_name=last_name or 'Фамилия',
                        middle_name=middle_name,
                        phone=phone,
                        is_active=True,
                        created_by=request.user,
                    )
                    teacher.save()
                    created_flag = True
                else:
                    fields_changed = []
                    if teacher.email != email:
                        teacher.email = email
                        fields_changed.append('Email')
                    if first_name and teacher.first_name != first_name:
                        teacher.first_name = first_name
                        fields_changed.append('Имя')
                    if last_name and teacher.last_name != last_name:
                        teacher.last_name = last_name
                        fields_changed.append('Фамилия')
                    if middle_name != teacher.middle_name:
                        teacher.middle_name = middle_name
                        if middle_name:
                            fields_changed.append('Отчество')
                    if phone != teacher.phone:
                        teacher.phone = phone
                        if phone:
                            fields_changed.append('Телефон')

                    if fields_changed:
                        teacher.save()
                        import_result['updated_count'] += 1
                        import_result['updated'].append({
                            'row': row_number,
                            'name': teacher.get_full_name(),
                            'email': teacher.email,
                            'fields': fields_changed,
                        })
                    else:
                        import_result['unchanged_count'] += 1
                        import_result['unchanged'].append({
                            'row': row_number,
                            'name': teacher.get_full_name(),
                            'email': teacher.email,
                        })
                if created_flag:
                    import_result['created_count'] += 1
                    import_result['created'].append({
                        'row': row_number,
                        'name': teacher.get_full_name(),
                        'email': teacher.email,
                    })

            except Exception as row_exc:
                import_result['errors'].append({
                    'row': index + 2,
                    'message': str(row_exc)
                })

        import_result['errors_count'] = len(import_result['errors'])
        processed_count = import_result['created_count'] + import_result['updated_count'] + import_result['unchanged_count']
        import_result['processed_count'] = processed_count
        if import_result['rows_total'] == 0:
            import_result['status'] = 'warning'
            import_result['summary'] = 'Файл не содержит данных для импорта.'
        elif import_result['errors_count'] and processed_count == 0:
            import_result['status'] = 'error'
            import_result['summary'] = 'Импорт не удалось выполнить. Проверьте ошибки и попробуйте снова.'
        elif import_result['errors_count']:
            import_result['status'] = 'warning'
            import_result['summary'] = 'Импорт выполнен, но часть записей содержит ошибки.'
        else:
            import_result['status'] = 'success'
            import_result['summary'] = 'Импорт успешно выполнен.'

        if import_result['created_count']:
            messages.success(request, f'Создано преподавателей: {import_result["created_count"]}')
        if import_result['updated_count']:
            messages.info(request, f'Обновлено преподавателей: {import_result["updated_count"]}')
        if import_result['errors_count']:
            error_message = f'Ошибок при импорте: {import_result["errors_count"]}'
            if processed_count == 0:
                messages.error(request, error_message)
            else:
                messages.warning(request, error_message)

        if import_result['created_count'] or import_result['updated_count']:
            log_activity(
                request.user,
                ActivityLog.ACTION_CREATE if import_result['created_count'] else ActivityLog.ACTION_UPDATE,
                f'Импорт преподавателей: создано {import_result["created_count"]}, обновлено {import_result["updated_count"]}, ошибок {import_result["errors_count"]}',
                'bi-cloud-upload',
                {
                    'created': import_result['created_count'],
                    'updated': import_result['updated_count'],
                    'errors': import_result['errors_count'],
                    'file_name': import_result['file_name'],
                }
            )

        context['import_result'] = import_result
        return render(request, 'admin_panel/teachers/import.html', context)

    return render(request, 'admin_panel/teachers/import.html', context)


@login_required
def download_teacher_sample(request):
    """Скачать образец Excel-файла для импорта преподавателей"""
    data = {
        'last_name': ['Иванов', 'Петрова'],
        'first_name': ['Иван', 'Мария'],
        'middle_name': ['Петрович', 'Ивановна'],
        'email': ['ivanov@example.com', 'petrova@example.com'],
        'phone': ['+7 (900) 123-45-67', '+7 (900) 234-56-78'],
    }

    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Преподаватели', index=False)
    buffer.seek(0)

    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="teachers_import_sample.xlsx"'
    return response

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

                log_activity(
                    request.user,
                    ActivityLog.ACTION_UPDATE,
                    f'Обновлены данные студента "{student.get_full_name()}"',
                    'bi-person-check',
                    {'student_id': student.id}
                )
                
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
            log_activity(
                request.user,
                ActivityLog.ACTION_CREATE,
                f'Добавлен студент \"{student.get_full_name()}\"',
                'bi-person-plus',
                {'student_id': student.id}
            )
            
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


def start_of_week(value):
    """Старт недели (понедельник)"""
    if not value:
        return None
    return value - timedelta(days=value.weekday())


def get_academic_year_start_week(reference_date):
    """Начало учебного года (первая неделя сентября)"""
    if reference_date.month >= 9:
        year = reference_date.year
    else:
        year = reference_date.year - 1
    september_first = date(year, 9, 1)
    return start_of_week(september_first)


def collect_week_starts(range_start, range_end):
    """Список стартов недель между двумя датами включительно"""
    starts = []
    cursor = start_of_week(range_start)
    if cursor is None or range_end < cursor:
        return starts
    while cursor <= range_end:
        starts.append(cursor)
        cursor += timedelta(days=7)
    return starts


def build_academic_year_week_starts(reference_date):
    """Генерируем список недель академического года"""
    if reference_date.month >= 9:
        year = reference_date.year
    else:
        year = reference_date.year - 1

    fall_start = start_of_week(date(year, 9, 1))
    fall_end = date(year, 12, 31)
    spring_start = start_of_week(date(year + 1, 1, 8))
    spring_end = date(year + 1, 7, 5)

    weeks = []
    if fall_start and fall_start <= fall_end:
        weeks.extend(collect_week_starts(fall_start, fall_end))
    if spring_start and spring_start <= spring_end:
        weeks.extend(collect_week_starts(spring_start, spring_end))

    return weeks


def calculate_week_parity(week_start_date):
    """На основе академических недель определяем, числитель или знаменатель"""
    if not week_start_date:
        return 'numerator'
    academic_weeks = build_academic_year_week_starts(week_start_date)
    try:
        index = academic_weeks.index(week_start_date)
        return 'numerator' if index % 2 == 0 else 'denominator'
    except ValueError:
        base_week = get_academic_year_start_week(week_start_date)
        if not base_week:
            return 'numerator'
        weeks_diff = (week_start_date - base_week).days // 7
        weeks_diff = abs(weeks_diff)
        return 'numerator' if weeks_diff % 2 == 0 else 'denominator'


LESSON_TYPE_LABELS = {
    'lesson': 'Пара',
    'lecture': 'Лекция',
    'practice': 'Практика',
    'lab': 'Лабораторная',
    'consultation': 'Консультация',
    'other': 'Другое',
}

GRADE_DAY_INDEX = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}

GRADE_DAY_LABELS = {
    'monday': 'Понедельник',
    'tuesday': 'Вторник',
    'wednesday': 'Среда',
    'thursday': 'Четверг',
    'friday': 'Пятница',
    'saturday': 'Суббота',
    'sunday': 'Воскресенье',
}

GRADE_DAY_SHORT_LABELS = {
    'monday': 'Пн',
    'tuesday': 'Вт',
    'wednesday': 'Ср',
    'thursday': 'Чт',
    'friday': 'Пт',
    'saturday': 'Сб',
    'sunday': 'Вс',
}

GRADE_SLOT_CONFIG = {
    'slot1': {'order': 1, 'label': '1-я пара', 'time_range': '08:30 – 10:00'},
    'slot2': {'order': 2, 'label': '2-я пара', 'time_range': '10:10 – 11:40'},
    'slot3': {'order': 3, 'label': '3-я пара', 'time_range': '12:00 – 13:30'},
    'slot4': {'order': 4, 'label': '4-я пара', 'time_range': '13:50 – 15:20'},
    'slot5': {'order': 5, 'label': '5-я пара', 'time_range': '15:30 – 17:00'},
}



BUILDING_DISPLAY = {
    'nakhimovsky': 'Нахимовский',
    'nezhinskaya': 'Нежинская',
}


@login_required
def teacher_dashboard_view(request):
    """Личный кабинет преподавателя"""
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        messages.error(request, 'У вас нет доступа к кабинету преподавателя')
        return redirect('login')

    groups = teacher.groups.filter(is_active=True).select_related('faculty').annotate(student_total=Count('students')).order_by('code')
    subjects = teacher.subjects.filter(is_active=True).order_by('name')
    students_count = Student.objects.filter(group__in=groups).count() if groups else 0

    day_map = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }

    base_weekday_order = [
        {'key': 'monday', 'label': 'Понедельник', 'short': 'Пн'},
        {'key': 'tuesday', 'label': 'Вторник', 'short': 'Вт'},
        {'key': 'wednesday', 'label': 'Среда', 'short': 'Ср'},
        {'key': 'thursday', 'label': 'Четверг', 'short': 'Чт'},
        {'key': 'friday', 'label': 'Пятница', 'short': 'Пт'},
        {'key': 'saturday', 'label': 'Суббота', 'short': 'Сб'},
    ]

    time_slots = [
        {'id': 'slot1', 'order': 1, 'start': '08:30', 'end': '10:00'},
        {'id': 'slot2', 'order': 2, 'start': '10:10', 'end': '11:40'},
        {'id': 'slot3', 'order': 3, 'start': '12:00', 'end': '13:30'},
        {'id': 'slot4', 'order': 4, 'start': '13:50', 'end': '15:20'},
        {'id': 'slot5', 'order': 5, 'start': '15:30', 'end': '17:00'},
    ]

    weekday_keys = [day['key'] for day in base_weekday_order]
    today = timezone.localdate()
    week_start = start_of_week(today) or today
    week_end = week_start + timedelta(days=5)
    week_range_label = f"{week_start.strftime('%d.%m')} – {week_end.strftime('%d.%m')}"
    week_parity = calculate_week_parity(week_start)
    parity_labels = {
        'numerator': 'Числитель',
        'denominator': 'Знаменатель',
    }
    week_parity_label = parity_labels.get(week_parity, 'Всегда')
    today_index = today.weekday()
    today_key = weekday_keys[today_index] if today_index < len(weekday_keys) else 'sunday'
    today_label = f"{day_map.get(today_key, today.strftime('%A'))}, {today.strftime('%d.%m')}"

    day_buildings_map = {key: 'nakhimovsky' for key in weekday_keys}
    if groups:
        schedule_weeks = ScheduleWeek.objects.filter(group__in=groups, week_start=week_start).only('day_buildings')
        for week in schedule_weeks:
            buildings = week.day_buildings or {}
            for raw_day, building_value in buildings.items():
                normalized_day = (raw_day or '').lower()
                normalized_building = (building_value or '').lower()
                if normalized_day in day_buildings_map and normalized_building in BUILDING_DISPLAY:
                    day_buildings_map[normalized_day] = normalized_building

    day_buildings_display = {
        key: BUILDING_DISPLAY.get(day_buildings_map.get(key), BUILDING_DISPLAY['nakhimovsky'])
        for key in weekday_keys
    }

    weekday_order = [
        {**day, 'building_label': day_buildings_display.get(day['key'], BUILDING_DISPLAY['nakhimovsky'])}
        for day in base_weekday_order
    ]

    week_slots = list(
        teacher.schedule_slots.filter(
            week__week_start=week_start,
            parity=week_parity
        ).select_related('group', 'subject', 'week')
    )

    lessons_by_day_slot = {}
    for slot in week_slots:
        day_key = (slot.day_key or '').lower()
        if day_key not in day_buildings_map:
            continue
        subject_label = ''
        if slot.subject:
            subject_label = slot.subject.short_name or slot.subject.name
        subject_label = subject_label or slot.subject_short or slot.subject_name or 'Пара'
        lesson_type_key = (slot.lesson_type or '').strip().lower()
        lesson_type_label = LESSON_TYPE_LABELS.get(lesson_type_key, slot.lesson_type)
        lessons_by_day_slot.setdefault(day_key, {})[slot.slot_id] = {
            'subject': subject_label,
            'group_code': slot.group.code if slot.group else 'Группа',
            'lesson_type': lesson_type_label or 'Занятие',
            'building_label': day_buildings_display.get(day_key, BUILDING_DISPLAY['nakhimovsky']),
            'parity_label': slot.get_parity_display(),
        }

    week_grid_rows = []
    for slot in time_slots:
        cells = []
        for day in weekday_order:
            lesson = lessons_by_day_slot.get(day['key'], {}).get(slot['id'])
            cells.append({
                'day_key': day['key'],
                'slot_id': slot['id'],
                'lesson': lesson,
            })
        week_grid_rows.append({
            'slot': slot,
            'cells': cells,
        })

    group_subject_map = {}
    for slot in teacher.schedule_slots.select_related('group', 'subject'):
        if slot.group_id and slot.subject and slot.group_id not in group_subject_map:
            subject_name = slot.subject.short_name or slot.subject.name
            group_subject_map[slot.group_id] = subject_name

    group_cards = []
    first_subject = teacher.subjects.first()
    first_subject_name = (first_subject.short_name if first_subject else '') or (first_subject.name if first_subject else '')
    for group in groups:
        course = getattr(group, 'current_course', None) or getattr(group, 'course', None)
        group_cards.append({
            'group': group,
            'subject_name': group_subject_map.get(group.id, first_subject_name),
            'course': course
        })

    context = {
        'teacher': teacher,
        'groups': groups,
        'subjects': subjects,
        'students_count': students_count,
        'stats': {
            'groups': groups.count(),
            'subjects': subjects.count(),
            'students': students_count,
            'is_curator': teacher.is_curator,
        },
        'group_cards': group_cards,
        'weekday_order': weekday_order,
        'time_slots': time_slots,
        'week_grid_rows': week_grid_rows,
        'today_label': today_label,
        'week_range_label': week_range_label,
        'week_parity': week_parity,
        'week_parity_label': week_parity_label,
    }

    return render(request, 'teacher/dashboard.html', context)


@login_required
def teacher_schedule_view(request):
    """Расписание преподавателя"""
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        messages.error(request, 'У вас нет доступа к кабинету преподавателя')
        return redirect('login')

    today = timezone.localdate()
    week_param = request.GET.get('week')

    week_start = start_of_week(today) or today
    if week_param:
        try:
            parsed_week = datetime.strptime(week_param, '%Y-%m-%d').date()
            normalized = start_of_week(parsed_week)
            if normalized:
                week_start = normalized
        except (TypeError, ValueError):
            pass

    week_end = week_start + timedelta(days=5)
    week_range_label = f"{week_start.strftime('%d.%m')} – {week_end.strftime('%d.%m')}"
    week_parity_key = calculate_week_parity(week_start)
    week_parity_label = 'Числитель' if week_parity_key == 'numerator' else 'Знаменатель'
    week_prev = week_start - timedelta(days=7)
    week_next = week_start + timedelta(days=7)
    share_link = request.build_absolute_uri()

    base_weekday_order = [
        {'key': 'monday', 'label': 'Понедельник', 'short': 'Пн'},
        {'key': 'tuesday', 'label': 'Вторник', 'short': 'Вт'},
        {'key': 'wednesday', 'label': 'Среда', 'short': 'Ср'},
        {'key': 'thursday', 'label': 'Четверг', 'short': 'Чт'},
        {'key': 'friday', 'label': 'Пятница', 'short': 'Пт'},
        {'key': 'saturday', 'label': 'Суббота', 'short': 'Сб'},
    ]

    time_slots = [
        {'id': 'slot1', 'order': 1, 'start': '08:30', 'end': '10:00'},
        {'id': 'slot2', 'order': 2, 'start': '10:10', 'end': '11:40'},
        {'id': 'slot3', 'order': 3, 'start': '12:00', 'end': '13:30'},
        {'id': 'slot4', 'order': 4, 'start': '13:50', 'end': '15:20'},
        {'id': 'slot5', 'order': 5, 'start': '15:30', 'end': '17:00'},
    ]

    lessons_qs = teacher.schedule_slots.select_related('group', 'subject', 'week').filter(
        week__week_start=week_start,
        parity=week_parity_key
    )

    lessons = list(lessons_qs)
    weekday_keys = {day['key'] for day in base_weekday_order}
    lessons_map = defaultdict(lambda: defaultdict(list))
    groups_set = set()
    day_building_labels = {}

    for lesson in lessons:
        day_key = (lesson.day_key or '').lower()
        slot_id = lesson.slot_id
        if day_key not in weekday_keys or not slot_id:
            continue
        group_code = lesson.group.code if lesson.group else '—'
        groups_set.add(group_code)

        # subject name tracking removed—parity-driven view does not expose multi-parity info

        week_buildings = (lesson.week.day_buildings or {}) if lesson.week else {}
        building_key = (week_buildings.get(day_key) or '').lower()
        building_label = BUILDING_DISPLAY.get(building_key, BUILDING_DISPLAY['nakhimovsky'])
        if day_key not in day_building_labels:
            day_building_labels[day_key] = building_label

        lesson_type_key = (lesson.lesson_type or '').strip().lower()
        lesson_type_label = LESSON_TYPE_LABELS.get(lesson_type_key, lesson.lesson_type) or 'Занятие'

        subject_label = ''
        if lesson.subject:
            subject_label = lesson.subject.short_name or lesson.subject.name
        subject_label = subject_label or lesson.subject_short or lesson.subject_name or 'Пара'

        lessons_map[day_key][slot_id].append({
            'subject': subject_label,
            'group_code': group_code,
            'lesson_type': lesson_type_label,
            'building_label': building_label,
            'parity_label': lesson.get_parity_display(),
            'parity_key': lesson.parity,
        })

    parity_order = {'numerator': 0, 'denominator': 1, None: 2}
    for day_slots in lessons_map.values():
        for slot_details in day_slots.values():
            slot_details.sort(key=lambda detail: parity_order.get(detail.get('parity_key')))

    week_grid_rows = []
    for slot in time_slots:
        cells = []
        for day in base_weekday_order:
            cells.append({
                'day_key': day['key'],
                'lesson_details': lessons_map.get(day['key'], {}).get(slot['id'], []),
            })
        week_grid_rows.append({'slot': slot, 'cells': cells})

    weekday_order = [
        {**day, 'building_label': day_building_labels.get(day['key'], BUILDING_DISPLAY['nakhimovsky'])}
        for day in base_weekday_order
    ]

    total_hours = len(lessons) * 2

    week_end_iso = week_end.strftime('%Y-%m-%d')

    context = {
        'teacher': teacher,
        'weekday_order': weekday_order,
        'time_slots': time_slots,
        'week_grid_rows': week_grid_rows,
        'week_range_label': week_range_label,
        'week_parity_label': week_parity_label,
        'current_date': today,
        'week_start_iso': week_start.strftime('%Y-%m-%d'),
        'week_end_iso': week_end_iso,
        'week_prev_iso': week_prev.strftime('%Y-%m-%d'),
        'week_next_iso': week_next.strftime('%Y-%m-%d'),
        'total_lessons': len(lessons),
        'total_hours': total_hours,
        'unique_groups_count': len(groups_set),
        'share_link': share_link,
    }

    return render(request, 'teacher/schedule.html', context)


@login_required
def get_teacher_groups_with_stats(teacher):
    if not teacher:
        return Group.objects.none()

    return (
        teacher.groups.select_related('faculty')
        .annotate(
            students_total=Count('students', distinct=True),
            active_students=Count(
                'students',
                filter=Q(students__study_status='active'),
                distinct=True,
            ),
        )
        .order_by('code')
    )


@login_required
def teacher_groups_view(request):
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        messages.error(request, 'У вас нет доступа к кабинету преподавателя')
        return redirect('login')

    teacher_groups = list(get_teacher_groups_with_stats(teacher))
    total_students = sum(getattr(group, 'students_total', 0) for group in teacher_groups)
    total_active_students = sum(getattr(group, 'active_students', 0) for group in teacher_groups)

    context = {
        'teacher': teacher,
        'teacher_groups': teacher_groups,
        'total_groups': len(teacher_groups),
        'total_students': total_students,
        'total_active_students': total_active_students,
    }
    return render(request, 'teacher/groups.html', context)


@login_required
def teacher_group_detail_view(request, group_id):
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        messages.error(request, 'У вас нет доступа к кабинету преподавателя')
        return redirect('login')

    group = get_object_or_404(Group, id=group_id)
    if not teacher.groups.filter(id=group.id).exists():
        messages.error(request, 'У вас нет доступа к этой группе')
        return redirect('teacher_groups')

    context = _build_teacher_group_detail_context(teacher, group)
    context.update({
        'active_nav': 'teacher_groups',
        'back_link_url': reverse('teacher_groups'),
        'back_link_label': 'Вернуться к списку',
        'detail_view_mode': 'groups',
    })
    return render(request, 'teacher/group_detail.html', context)


def _build_teacher_group_cards_context(teacher):
    teacher_groups = list(get_teacher_groups_with_stats(teacher))
    students_count = Student.objects.filter(group__in=teacher_groups).count() if teacher_groups else 0
    subjects = teacher.subjects.filter(is_active=True).order_by('name')

    first_subject = subjects.first()
    first_subject_name = (first_subject.short_name if first_subject else '') or (first_subject.name if first_subject else '')
    first_subject_id = first_subject.id if first_subject else None

    group_subject_map = {}
    group_subject_ids = {}
    for slot in teacher.schedule_slots.select_related('group', 'subject'):
        if slot.group_id and slot.group_id not in group_subject_map:
            subject_name = ''
            if slot.subject:
                subject_name = slot.subject.name
            subject_name = subject_name or slot.subject_short or slot.subject_name or ''
            group_subject_map[slot.group_id] = subject_name
            group_subject_ids[slot.group_id] = slot.subject_id

    group_cards = []
    for group in teacher_groups:
        course = getattr(group, 'current_course', None) or getattr(group, 'course', None)
        display_subject_name = group_subject_map.get(group.id) or first_subject_name or 'Предмет не указан'
        group_cards.append({
            'group': group,
            'subject_name': display_subject_name,
            'subject_id': group_subject_ids.get(group.id) or first_subject_id,
            'course': course,
        })

    course_options = sorted({card['course'] for card in group_cards if card['course']}, key=lambda value: (str(value)))

    return {
        'teacher_groups': teacher_groups,
        'group_cards': group_cards,
        'subjects': subjects,
        'course_options': course_options,
        'stats': {
            'groups': len(teacher_groups),
            'subjects': subjects.count(),
            'students': students_count,
        },
    }


def _build_grade_columns_for_group(teacher, group, lookahead_weeks=4):
    """Определяем даты занятий для оценочной таблицы (с начала учебного года)"""
    today = timezone.localdate()
    lookahead_span = timedelta(days=7 * lookahead_weeks)
    start_week = get_academic_year_start_week(today) or today

    if group.enrollment_date:
        enrollment_start = start_of_week(group.enrollment_date)
        if enrollment_start and enrollment_start < start_week:
            start_week = enrollment_start

    end_week = start_of_week(today + lookahead_span) or today
    default_subject_id = teacher.subjects.values_list('id', flat=True).first()

    slots = ScheduleTeacherSlot.objects.filter(
        teacher=teacher,
        group=group,
        week__week_start__gte=start_week,
        week__week_start__lte=end_week,
    ).select_related('week')

    columns_map = {}
    for slot in slots:
        day_key = (slot.day_key or '').lower()
        day_index = GRADE_DAY_INDEX.get(day_key)
        if day_index is None or not slot.week or not slot.week.week_start:
            continue

        date_value = slot.week.week_start + timedelta(days=day_index)
        slot_info = GRADE_SLOT_CONFIG.get(slot.slot_id, {'order': 0, 'label': slot.slot_id, 'time_range': ''})
        column_key = (date_value, slot.slot_id, slot_info['order'])
        # keep first slot for duplicated dates/slottings
        if column_key in columns_map:
            continue
        slot_identifier = slot.slot_id or f"slot-{slot.pk}"
        slot_identifier = str(slot_identifier)
        subject_id = slot.subject_id or default_subject_id

        columns_map[column_key] = {
            'date': date_value,
            'date_iso': date_value.isoformat(),
            'day_label': GRADE_DAY_LABELS.get(day_key, ''),
            'day_short': GRADE_DAY_SHORT_LABELS.get(day_key, ''),
            'slot_label': slot_info['label'],
            'time_range': slot_info['time_range'],
            'slot_order': slot_info['order'],
            'is_future': date_value > today,
            'is_today': date_value == today,
            'slot_id': slot_identifier,
            'subject_id': subject_id,
            'column_key': f"{date_value.isoformat()}|{slot_identifier}",
            'is_past': date_value < today,
        }

    sorted_columns = sorted(columns_map.values(), key=lambda column: (column['date'], column['slot_order']))
    return sorted_columns


def _build_teacher_group_detail_context(teacher, group):
    students = list(Student.objects.filter(group=group).order_by('last_name', 'first_name'))
    grade_columns = _build_grade_columns_for_group(teacher, group)
    grade_values_map = {}
    column_context_map = {}

    if grade_columns:
        column_dates = {column['date'] for column in grade_columns}
        slot_ids = {str(column['slot_id'] or '') for column in grade_columns}
        grade_records = GradeRecord.objects.filter(
            group=group,
            teacher=teacher,
            lesson_date__in=column_dates,
            student__in=students,
        ).only('student_id', 'lesson_date', 'slot_id', 'value', 'comment', 'grade_type', 'lesson_topic')

        for record in grade_records:
            student_map = grade_values_map.setdefault(record.student_id, {})
            key = f"{record.lesson_date.isoformat()}|{record.slot_id or ''}"
            student_map[key] = {
                'value': record.value,
                'comment': record.comment or '',
                'grade_type': record.grade_type or '',
                'lesson_topic': record.lesson_topic or '',
            }
            column_context = column_context_map.setdefault(key, {
                'lesson_topic': '',
                'grade_type': '',
            })
            if not column_context['lesson_topic'] and record.lesson_topic:
                column_context['lesson_topic'] = record.lesson_topic
            if not column_context['grade_type'] and record.grade_type:
                column_context['grade_type'] = record.grade_type

        column_meta = GradeColumnContext.objects.filter(
            teacher=teacher,
            group=group,
            lesson_date__in=column_dates,
            slot_id__in=slot_ids,
        )
        for meta in column_meta:
            key = f"{meta.lesson_date.isoformat()}|{meta.slot_id or ''}"
            column_context = column_context_map.setdefault(key, {
                'lesson_topic': '',
                'grade_type': '',
            })
            if meta.lesson_topic:
                column_context['lesson_topic'] = meta.lesson_topic
            if meta.grade_type:
                column_context['grade_type'] = meta.grade_type

    for student in students:
        grade_values_map.setdefault(student.id, {})

    attendance_context = _build_attendance_group_detail_context(
        teacher,
        group,
        students=students,
        columns=grade_columns,
    )

    return {
        'teacher': teacher,
        'group': group,
        'students': students,
        'grade_columns': grade_columns,
        'grade_today': timezone.localdate(),
        'grade_values_map': grade_values_map,
        'grade_type_choices': GradeRecord.GRADE_TYPE_CHOICES,
        'column_context_map': column_context_map,
        'attendance_columns': attendance_context.get('attendance_columns', []),
        'attendance_values_map': attendance_context.get('attendance_values_map', {}),
        'attendance_today': attendance_context.get('attendance_today'),
        'absence_totals': attendance_context.get('absence_totals', {}),
        'attendance_status_meta': attendance_context.get('attendance_status_meta', ATTENDANCE_STATUS_META),
    }


def _build_attendance_group_detail_context(teacher, group, students=None, columns=None):
    students_qs = students if students is not None else Student.objects.filter(group=group).order_by('last_name', 'first_name')
    students_list = list(students_qs)
    attendance_columns = columns if columns is not None else _build_grade_columns_for_group(teacher, group)
    attendance_values_map = {}
    absence_totals = {student.id: 0 for student in students_list}

    if attendance_columns:
        column_dates = {column['date'] for column in attendance_columns}
        slot_ids = {str(column['slot_id'] or '') for column in attendance_columns}
        attendance_records = AttendanceRecord.objects.filter(
            group=group,
            teacher=teacher,
            lesson_date__in=column_dates,
            slot_id__in=slot_ids,
            student__in=students_list,
        ).only('student_id', 'lesson_date', 'slot_id', 'status', 'comment')

        for record in attendance_records:
            student_map = attendance_values_map.setdefault(record.student_id, {})
            key = f"{record.lesson_date.isoformat()}|{record.slot_id or ''}"
            student_map[key] = {
                'status': record.status or '',
                'comment': record.comment or '',
            }
            if record.status == AttendanceRecord.STATUS_ABSENT:
                absence_totals[record.student_id] = absence_totals.get(record.student_id, 0) + 1

    for student in students_list:
        attendance_values_map.setdefault(student.id, {})
        absence_totals.setdefault(student.id, 0)

    return {
        'teacher': teacher,
        'group': group,
        'students': students_list,
        'attendance_columns': attendance_columns,
        'attendance_values_map': attendance_values_map,
        'attendance_today': timezone.localdate(),
        'absence_totals': absence_totals,
        'attendance_status_meta': ATTENDANCE_STATUS_META,
    }


@login_required
def teacher_journals_view(request):
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        messages.error(request, 'У вас нет доступа к кабинету преподавателя')
        return redirect('login')

    context = _build_teacher_group_cards_context(teacher)
    context['teacher'] = teacher
    return render(request, 'teacher/journals.html', context)


@login_required
def teacher_journal_detail_view(request, group_id):
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        messages.error(request, 'У вас нет доступа к кабинету преподавателя')
        return redirect('login')

    group = get_object_or_404(Group, id=group_id)
    if not teacher.groups.filter(id=group.id).exists():
        messages.error(request, 'У вас нет доступа к этой группе')
        return redirect('teacher_journals')

    context = _build_teacher_group_detail_context(teacher, group)
    context.update({
        'active_nav': 'teacher_journals',
        'back_link_url': reverse('teacher_journals'),
        'back_link_label': 'Назад к списку журналов',
        'detail_view_mode': 'journal',
    })
    return render(request, 'teacher/group_detail.html', context)


@login_required
def teacher_attendance_detail_view(request, group_id):
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        messages.error(request, 'У вас нет доступа к кабинету преподавателя')
        return redirect('login')

    group = get_object_or_404(Group, id=group_id)
    if not teacher.groups.filter(id=group.id).exists():
        messages.error(request, 'У вас нет доступа к этой группе')
        return redirect('teacher_attendance')

    context = _build_attendance_group_detail_context(teacher, group)
    context.update({
        'active_nav': 'teacher_attendance',
        'back_link_url': reverse('teacher_attendance'),
        'back_link_label': 'Назад к списку посещаемости',
    })
    return render(request, 'teacher/attendance_detail.html', context)


@login_required
@require_POST
def teacher_journal_save_api(request, group_id):
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        return JsonResponse({'success': False, 'error': 'У вас нет доступа к кабинету преподавателя'}, status=403)

    group = get_object_or_404(Group, id=group_id)
    if not teacher.groups.filter(id=group.id).exists():
        return JsonResponse({'success': False, 'error': 'У вас нет доступа к этой группе'}, status=403)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Некорректный формат данных'}, status=400)

    entries = payload.get('grades') if isinstance(payload, dict) else payload
    column_entries = payload.get('columns', []) if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        return JsonResponse({'success': False, 'error': 'Некорректный список оценок'}, status=400)
    if not isinstance(column_entries, list):
        return JsonResponse({'success': False, 'error': 'Некорректные параметры занятия'}, status=400)

    saved = 0
    deleted = 0
    errors = []
    students_cache = {}
    valid_grade_types = {choice[0] for choice in GradeRecord.GRADE_TYPE_CHOICES}
    column_updates = {}

    def set_column_update(lesson_date_value, slot_value, topic_value, grade_type_value, force=False):
        if not isinstance(lesson_date_value, date):
            return
        normalized_slot = str(slot_value or '')[:20]
        column_updates[(lesson_date_value, normalized_slot)] = {
            'lesson_topic': topic_value,
            'grade_type': grade_type_value,
            'force': force,
        }

    for index, entry in enumerate(entries):
        student_raw = entry.get('student_id') or entry.get('student')
        date_str = entry.get('date') or entry.get('column_date')
        slot_id = (entry.get('slot_id') or '').strip()
        subject_raw = entry.get('subject_id') or entry.get('subject')
        value_raw = entry.get('value')
        comment_raw = entry.get('comment') or ''
        grade_type_raw = (entry.get('grade_type') or '').strip()
        lesson_topic_raw = entry.get('lesson_topic') or ''

        try:
            student_id = int(student_raw)
        except (TypeError, ValueError):
            errors.append(f'#{index + 1}: некорректный студент')
            continue

        if not date_str or not slot_id:
            errors.append(f'#{index + 1}: не указаны дата или слот')
            continue

        student = students_cache.get(student_id)
        if not student:
            student = Student.objects.filter(id=student_id, group=group).first()
            if not student:
                errors.append(f'#{index + 1}: студент не найден в группе')
                continue
            students_cache[student_id] = student

        try:
            lesson_date = date.fromisoformat(date_str)
        except ValueError:
            errors.append(f'#{index + 1}: неверный формат даты')
            continue

        subject_id = None
        if subject_raw:
            try:
                subject_id = int(subject_raw)
            except (TypeError, ValueError):
                errors.append(f'#{index + 1}: некорректный предмет')
                continue

        if value_raw in (None, ''):
            deleted_count, _ = GradeRecord.objects.filter(
                student=student,
                group=group,
                teacher=teacher,
                lesson_date=lesson_date,
                slot_id=slot_id,
            ).delete()
            if deleted_count:
                deleted += deleted_count
            continue

        try:
            value_int = int(value_raw)
        except (TypeError, ValueError):
            errors.append(f'#{index + 1}: неверное значение оценки')
            continue

        if not 1 <= value_int <= 5:
            errors.append(f'#{index + 1}: оценка вне диапазона 1-5')
            continue

        if grade_type_raw and grade_type_raw not in valid_grade_types:
            errors.append(f'#{index + 1}: неизвестный тип оценки')
            continue

        comment_value = comment_raw.strip()[:255]
        lesson_topic_value = lesson_topic_raw.strip()[:255]
        grade_type_value = grade_type_raw if grade_type_raw in valid_grade_types else ''

        GradeRecord.objects.update_or_create(
            student=student,
            group=group,
            teacher=teacher,
            lesson_date=lesson_date,
            slot_id=slot_id,
            defaults={
                'value': value_int,
                'subject_id': subject_id,
                'updated_by': request.user,
                'comment': comment_value,
                'grade_type': grade_type_value,
                'lesson_topic': lesson_topic_value,
                'work_type': grade_type_value or '',
            }
        )
        saved += 1
        if lesson_topic_value or grade_type_value:
            set_column_update(lesson_date, slot_id, lesson_topic_value, grade_type_value)

    for index, entry in enumerate(column_entries):
        date_str = entry.get('date') or entry.get('column_date')
        slot_id = (entry.get('slot_id') or '').strip()
        grade_type_raw = (entry.get('grade_type') or '').strip()
        lesson_topic_raw = entry.get('lesson_topic') or ''

        if not date_str or not slot_id:
            errors.append(f'Контекст #{index + 1}: не указаны дата или слот')
            continue

        try:
            lesson_date = date.fromisoformat(date_str)
        except ValueError:
            errors.append(f'Контекст #{index + 1}: неверный формат даты')
            continue

        if grade_type_raw and grade_type_raw not in valid_grade_types:
            errors.append(f'Контекст #{index + 1}: неизвестный тип оценки')
            continue

        topic_value = lesson_topic_raw.strip()[:255]
        grade_type_value = grade_type_raw if grade_type_raw in valid_grade_types else ''
        set_column_update(lesson_date, slot_id, topic_value, grade_type_value, force=True)

    for (lesson_date, slot_id), meta in column_updates.items():
        topic_value = (meta.get('lesson_topic') or '').strip()[:255]
        grade_type_value = meta.get('grade_type') if meta.get('grade_type') in valid_grade_types else ''
        force_update = meta.get('force', False)
        filters = {
            'teacher': teacher,
            'group': group,
            'lesson_date': lesson_date,
            'slot_id': slot_id,
        }
        if topic_value or grade_type_value:
            GradeColumnContext.objects.update_or_create(
                defaults={
                    'lesson_topic': topic_value,
                    'grade_type': grade_type_value,
                    'updated_by': request.user,
                },
                **filters,
            )
        elif force_update:
            GradeColumnContext.objects.filter(**filters).delete()

    status_code = 200 if not errors else 207
    return JsonResponse({
        'success': not errors,
        'saved': saved,
        'deleted': deleted,
        'errors': errors,
    }, status=status_code)


@login_required
@require_POST
def teacher_attendance_save_api(request, group_id):
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        return JsonResponse({'success': False, 'error': 'У вас нет доступа к кабинету преподавателя'}, status=403)

    group = get_object_or_404(Group, id=group_id)
    if not teacher.groups.filter(id=group.id).exists():
        return JsonResponse({'success': False, 'error': 'У вас нет доступа к этой группе'}, status=403)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Некорректный формат данных'}, status=400)

    entries = payload.get('entries', []) if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        return JsonResponse({'success': False, 'error': 'Некорректный список посещаемости'}, status=400)

    valid_statuses = {choice[0] for choice in AttendanceRecord.STATUS_CHOICES}
    saved = 0
    deleted = 0
    errors = []
    students_cache = {}

    for index, entry in enumerate(entries):
        student_raw = entry.get('student_id') or entry.get('student')
        date_str = entry.get('date') or entry.get('lesson_date')
        slot_id = (entry.get('slot_id') or '').strip()
        status_raw = (entry.get('status') or '').strip()
        comment_raw = (entry.get('comment') or '').strip()
        subject_raw = entry.get('subject_id') or entry.get('subject')

        try:
            student_id = int(student_raw)
        except (TypeError, ValueError):
            errors.append(f'#{index + 1}: некорректный студент')
            continue

        if not date_str or not slot_id:
            errors.append(f'#{index + 1}: не указаны дата или слот')
            continue

        student = students_cache.get(student_id)
        if not student:
            student = Student.objects.filter(id=student_id, group=group).first()
            if not student:
                errors.append(f'#{index + 1}: студент не найден в группе')
                continue
            students_cache[student_id] = student

        try:
            lesson_date = date.fromisoformat(date_str)
        except ValueError:
            errors.append(f'#{index + 1}: неверный формат даты')
            continue

        if status_raw not in valid_statuses:
            errors.append(f'#{index + 1}: неизвестный статус посещаемости')
            continue

        subject_id = None
        if subject_raw:
            try:
                subject_id = int(subject_raw)
            except (TypeError, ValueError):
                errors.append(f'#{index + 1}: некорректный предмет')
                continue

        comment_value = comment_raw[:255]

        if not status_raw:
            AttendanceRecord.objects.update_or_create(
                student=student,
                group=group,
                teacher=teacher,
                lesson_date=lesson_date,
                slot_id=slot_id,
                defaults={
                    'status': AttendanceRecord.STATUS_PRESENT,
                    'subject_id': subject_id,
                    'comment': '',
                    'updated_by': request.user,
                }
            )
            saved += 1
            continue

        AttendanceRecord.objects.update_or_create(
            student=student,
            group=group,
            teacher=teacher,
            lesson_date=lesson_date,
            slot_id=slot_id,
            defaults={
                'status': status_raw,
                'subject_id': subject_id,
                'comment': comment_value,
                'updated_by': request.user,
            }
        )
        saved += 1

    status_code = 200 if not errors else 207
    return JsonResponse({
        'success': not errors,
        'saved': saved,
        'deleted': deleted,
        'errors': errors,
    }, status=status_code)


@login_required
def teacher_attendance_view(request):
    try:
        teacher = request.user.teacher_profile
    except AttributeError:
        messages.error(request, 'У вас нет доступа к кабинету преподавателя')
        return redirect('login')

    context = _build_teacher_group_cards_context(teacher)
    context['teacher'] = teacher
    return render(request, 'teacher/attendance.html', context)


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

    # Если преподаватель
    try:
        teacher = request.user.teacher_profile
        return redirect('teacher_dashboard')
    except AttributeError:
        pass
    
    # Если обычный пользователь без роли
    messages.warning(request, 'У вас нет назначенной роли в системе. Обратитесь к администратору.')
    return redirect('login')




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


def send_teacher_credentials_email(teacher, username, password):
    """Отправка учетных данных преподавателю"""
    try:
        subject = 'Доступ к системе МПТ Журнал'
        message = f'''
Здравствуйте, {teacher.get_full_name()}!

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
            [teacher.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Ошибка отправки email преподавателю: {e}")
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
            log_activity(
                request.user,
                ActivityLog.ACTION_CREATE,
                f'Создана специальность "{faculty.name}"',
                'bi-building-add',
                {'faculty_id': faculty.id, 'professions_count': len(professions_list)}
            )
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
                    log_activity(
                        request.user,
                        ActivityLog.ACTION_UPDATE,
                        f'Обновлена специальность "{faculty.name}"',
                        'bi-building',
                        {'faculty_id': faculty.id, 'professions_count': len(professions_list)}
                    )
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
            log_activity(
                request.user,
                ActivityLog.ACTION_DELETE,
                f'Удалена специальность "{faculty_name}"',
                'bi-trash',
                {'faculty_id': faculty_id}
            )
            
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
        backup_service = BackupService()
        stale_result = backup_service.expire_stale_backups()
        restored_count = stale_result.get('completed', 0)
        failed_count = stale_result.get('failed', 0)
        if restored_count or failed_count:
            notice_parts = []
            if restored_count:
                notice_parts.append(f'исправлено {restored_count} зависших копий')
            if failed_count:
                notice_parts.append(f'{failed_count} помечены с ошибкой')
            messages.warning(
                request,
                'Обновлена история бэкапов: ' + ', '.join(notice_parts) + '.'
            )
        # Получаем все бэкапы
        backups = Backup.objects.all().order_by('-created_at')
        
        # Пагинация
        paginator = Paginator(backups, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Статистика
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
                log_activity(
                    request.user,
                    ActivityLog.ACTION_CREATE,
                    f'Создана резервная копия "{backup.name}"',
                    'bi-hdd-stack',
                    {'backup_id': backup.id}
                )
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
                log_activity(
                    request.user,
                    ActivityLog.ACTION_DELETE,
                    f'Удалена резервная копия #{backup_id}',
                    'bi-trash'
                )
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
@user_passes_test(is_admin_user, login_url='/accounts/login/')
@require_POST
def backup_restore_view(request, backup_id):
    """Восстановление базы данных из резервной копии"""
    try:
        session_engine = import_module(settings.SESSION_ENGINE)
        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key
        session_data = dict(request.session.items())
        expiry_date = request.session.get_expiry_date()
        
        backup_service = BackupService()
        backup = backup_service.restore_backup(backup_id)
        
        log_activity(
            request.user,
            ActivityLog.ACTION_UPDATE,
            f'Восстановлена резервная копия "{backup.name}"',
            'bi-arrow-counterclockwise',
            {'backup_id': backup.id}
        )
        
        try:
            session_store = session_engine.SessionStore()
            encoded_data = session_store.encode(session_data)
            Session.objects.update_or_create(
                session_key=session_key,
                defaults={
                    'session_data': encoded_data,
                    'expire_date': expiry_date
                }
            )
            request.session._session_cache = session_data
            request.session.modified = False
        except Exception as exc:
            print(f'[admin_panel] Не удалось восстановить сессию после отката: {exc}')
        
        return JsonResponse({
            'success': True,
            'message': f'Резервная копия "{backup.name}" успешно восстановлена'
        })
    except Backup.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Резервная копия не найдена'
        }, status=404)
    except FileNotFoundError as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=404)
    except BackupRestoreError as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при восстановлении: {str(e)}'
        }, status=500)
# admin_panel/views.py - добавьте в конец файла

from admin_panel.services.backup_service import BackupService, BackupRestoreError
from admin_panel.models import Backup

@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def backups_list_view(request):
    """Список резервных копий"""
    print("=== backups_list_view вызван ===")
    
    try:
        backup_service = BackupService()
        stale_count = backup_service.expire_stale_backups()
        if stale_count:
            messages.warning(
                request,
                f'Обновлено зависших резервных копий: {stale_count}. Проверьте сообщения об ошибках.'
            )
        # Получаем все бэкапы
        backups = Backup.objects.all().order_by('-created_at')
        
        # Пагинация
        paginator = Paginator(backups, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Статистика
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
def subjects_main_view(request):
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции.')
        return redirect('admin_dashboard')

    search_query = request.GET.get('search', '').strip()
    specialty_filter = request.GET.get('specialty', '').strip()
    course_filter = request.GET.get('course', '').strip() or '1'

    faculties = list(Faculty.objects.filter(is_active=True).order_by('name'))
    faculty_ids = [faculty.id for faculty in faculties]

    # Профессии для каждого факультета (для фильтра и выпадающих списков)
    faculty_professions_map = {
        faculty.id: set(filter(None, faculty.get_professions_list() or []))
        for faculty in faculties
    }

    if faculty_ids:
        for faculty_id, profession in (
            SubjectAssignment.objects.filter(faculty_id__in=faculty_ids)
            .values_list('faculty_id', 'profession')
            .distinct()
        ):
            if profession:
                faculty_professions_map.setdefault(faculty_id, set()).add(profession)

    base_assignments = SubjectAssignment.objects.select_related('subject', 'faculty').prefetch_related('teachers')
    assignments_qs = base_assignments.filter(is_active=True)

    total_assignments = assignments_qs.count()
    total_unique_subjects = assignments_qs.values('subject_id').distinct().count()
    total_teachers = assignments_qs.filter(teachers__isnull=False).values('teachers').distinct().count()

    assignments_list = list(
        assignments_qs.order_by('faculty__name', 'profession', 'subject__name', 'subject__short_name')
    )

    courses = sorted({assignment.course for assignment in assignments_list if assignment.course})

    assignments_by_faculty = {}
    for assignment in assignments_list:
        faculty_bucket = assignments_by_faculty.setdefault(assignment.faculty_id, {})
        faculty_bucket.setdefault(assignment.profession, []).append(assignment)

    subjects_data = []
    for faculty in faculties:
        professions = sorted(faculty_professions_map.get(faculty.id, []))
        faculty_assignments = assignments_by_faculty.get(faculty.id, {})

        profession_entries = []
        for profession in professions:
            assignments_for_profession = faculty_assignments.get(profession, [])
            profession_entries.append({
                'name': profession,
                'assignments': assignments_for_profession,
                'assignments_count': len(assignments_for_profession),
            })

        subjects_data.append({
            'faculty': faculty,
            'professions': profession_entries,
        })

    # JSON для frontend
    specialties_meta = {
        str(faculty.id): {
            'name': faculty.name,
            'professions': sorted(faculty_professions_map.get(faculty.id, []))
        }
        for faculty in faculties
    }

    current_filters = {
        'search': search_query,
        'specialty': specialty_filter,
        'course': course_filter,
    }

    context = {
        'faculties': faculties,
        'all_faculties': faculties,
        'subjects_data': subjects_data,
        'search_query': search_query,
        'specialty_filter': specialty_filter,
        'course_filter': course_filter,
        'total_faculties': len(faculties),
        'total_assignments': total_assignments,
        'total_subjects': total_unique_subjects,
        'total_teachers': total_teachers,
        'courses': courses,
        'subjects_map_json': json.dumps(specialties_meta, ensure_ascii=False),
        'current_filters_json': json.dumps(current_filters, ensure_ascii=False),
    }

    return render(request, 'admin_panel/subjects/subjects_main.html', context)


@login_required
def subject_create_view(request):
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции.')
        return redirect('admin_dashboard')

    faculties = Faculty.objects.filter(is_active=True).order_by('name')
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')
    subjects_data = [
        {
            'id': subject.id,
            'name': subject.name,
            'short_name': subject.short_name or '',
            'description': subject.description or '',
        }
        for subject in subjects
    ]

    faculty_professions = {
        faculty.id: sorted(filter(None, faculty.get_professions_list() or []))
        for faculty in faculties
    }

    if request.method == 'POST':
        faculty_id = request.POST.get('faculty')
        profession = request.POST.get('profession', '').strip()
        course = request.POST.get('course')
        subject_id = request.POST.get('subject')
        subject_name = request.POST.get('subject_name', '').strip()
        subject_short_name = request.POST.get('subject_short_name', '').strip()
        subject_description = request.POST.get('subject_description', '').strip()
        teacher_ids = [pk for pk in request.POST.getlist('teachers') if pk.isdigit()]

        if not faculty_id or not profession or not course:
            messages.error(request, 'Заполните специальность, профессию и курс.')
            return redirect('admin_subject_create')

        faculty = get_object_or_404(Faculty, id=faculty_id)

        try:
            course_value = int(course)
        except (TypeError, ValueError):
            messages.error(request, 'Некорректное значение курса.')
            return redirect('admin_subject_create')

        if subject_id:
            subject = get_object_or_404(Subject, id=subject_id)
        elif subject_name:
            subject, created = Subject.objects.get_or_create(
                name=subject_name,
                defaults={
                    'short_name': subject_short_name or subject_name,
                    'description': subject_description,
                    'created_by': request.user,
                }
            )
            if not created:
                updated_fields = []
                if subject_short_name and subject.short_name != subject_short_name:
                    subject.short_name = subject_short_name
                    updated_fields.append('short_name')
                if subject_description and not subject.description:
                    subject.description = subject_description
                    updated_fields.append('description')
                if updated_fields:
                    subject.save(update_fields=updated_fields)
        else:
            messages.error(request, 'Выберите существующий предмет или укажите новое название.')
            return redirect('admin_subject_create')

        try:
            assignment, created = SubjectAssignment.objects.get_or_create(
                subject=subject,
                faculty=faculty,
                profession=profession,
                course=course_value,
                defaults={'created_by': request.user}
            )

            if teacher_ids:
                assignment.teachers.set(Teacher.objects.filter(id__in=teacher_ids))
            else:
                assignment.teachers.clear()

            teacher_union = Teacher.objects.filter(
                subject_assignments__subject=subject
            ).distinct()
            subject.teachers.set(teacher_union)

            if created:
                messages.success(
                    request,
                    f'Предмет "{subject}" добавлен для {faculty.name} — {profession} ({assignment.get_course_display()}).'
                )
                log_activity(
                    request.user,
                    ActivityLog.ACTION_CREATE,
                    f'Назначен предмет "{subject}" для {faculty.name} — {profession} ({assignment.get_course_display()})',
                    'bi-journal-plus',
                    {
                        'assignment_id': assignment.id,
                        'subject_id': subject.id,
                        'faculty_id': faculty.id,
                        'course': course_value,
                    }
                )
            else:
                messages.warning(
                    request,
                    'Такой предмет уже был назначен этой специальности и курсу. Преподаватели обновлены.'
                )
                log_activity(
                    request.user,
                    ActivityLog.ACTION_UPDATE,
                    f'Обновлены преподаватели предмета "{subject}" для {faculty.name} — {profession} ({assignment.get_course_display()})',
                    'bi-journal-check',
                    {
                        'assignment_id': assignment.id,
                        'subject_id': subject.id,
                        'faculty_id': faculty.id,
                        'course': course_value,
                    }
                )

            return redirect('admin_subjects')

        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        except Exception as exc:
            messages.error(request, f'Ошибка при добавлении предмета: {exc}')

    context = {
        'faculties': faculties,
        'subjects': subjects,
        'teachers': teachers,
        'course_choices': SubjectAssignment.COURSE_CHOICES,
        'professions_json': json.dumps(faculty_professions, ensure_ascii=False),
        'subjects_data_json': json.dumps(subjects_data, ensure_ascii=False),
    }
    return render(request, 'admin_panel/subjects/subject_create.html', context)


@login_required
def subject_detail_view(request, subject_id):
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции.')
        return redirect('admin_dashboard')

    subject = get_object_or_404(
        Subject.objects.prefetch_related('teachers', 'assignments__faculty', 'assignments__teachers'),
        id=subject_id
    )

    assignments = list(
        subject.assignments.select_related('faculty').prefetch_related('teachers').order_by('faculty__name', 'profession', 'course')
    )

    return_course = str(assignments[0].course) if assignments else ''

    teacher_assignments_map = defaultdict(list)
    for assignment in assignments:
        for teacher in assignment.teachers.all():
            teacher_assignments_map[teacher.id].append(assignment)

    teacher_map = {teacher.id: teacher for teacher in subject.teachers.all()}
    for assignment in assignments:
        for teacher in assignment.teachers.all():
            teacher_map.setdefault(teacher.id, teacher)

    sorted_teachers = sorted(
        teacher_map.values(),
        key=lambda t: (
            t.last_name.lower(),
            t.first_name.lower(),
            t.middle_name.lower() if t.middle_name else ''
        )
    )

    teacher_cards = []
    for teacher in sorted_teachers:
        assigned = teacher_assignments_map.get(teacher.id, [])
        teacher_cards.append({
            'teacher': teacher,
            'assignments': assigned,
            'assignment_count': len(assigned),
        })

    context = {
        'subject': subject,
        'assignments': assignments,
        'teacher_cards': teacher_cards,
        'return_course': return_course,
    }
    return render(request, 'admin_panel/subjects/subject_detail.html', context)


@login_required
def subject_edit_view(request, subject_id):
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции.')
        return redirect('admin_dashboard')

    subject = get_object_or_404(
        Subject.objects.prefetch_related('teachers', 'assignments__faculty', 'assignments__teachers'),
        id=subject_id
    )
    assignments = list(
        subject.assignments.select_related('faculty').prefetch_related('teachers').order_by('faculty__name', 'profession', 'course')
    )
    teachers = list(Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name', 'middle_name'))

    assignment_lookup = {assignment.id: assignment for assignment in assignments}
    teacher_lookup = {teacher.id: teacher for teacher in teachers}
    selected_teacher_ids_context = set(subject.teachers.values_list('id', flat=True))
    override_teacher_assignments = None

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        short_name = request.POST.get('short_name', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        teacher_ids = [int(pk) for pk in request.POST.getlist('selected_teachers') if pk.isdigit()]

        teacher_selected_assignments = {}
        for teacher_id in teacher_ids:
            field_name = f'teacher_assignments_{teacher_id}'
            assignment_ids = [
                int(pk)
                for pk in request.POST.getlist(field_name)
                if pk.isdigit() and int(pk) in assignment_lookup
            ]
            teacher_selected_assignments[teacher_id] = assignment_ids

        selected_teacher_ids_context = set(teacher_ids)
        override_teacher_assignments = teacher_selected_assignments

        if not name:
            messages.error(request, 'Название предмета обязательно.')
        else:
            try:
                with transaction.atomic():
                    subject.name = name
                    subject.short_name = short_name
                    subject.description = description
                    subject.is_active = is_active
                    subject.save()

                    subject.teachers.set(Teacher.objects.filter(id__in=teacher_ids))

                    assignment_teacher_map = {assignment_id: set() for assignment_id in assignment_lookup}
                    for teacher_id, assignment_ids in teacher_selected_assignments.items():
                        teacher_obj = teacher_lookup.get(teacher_id)
                        if not teacher_obj:
                            continue
                        for assignment_id in assignment_ids:
                            assignment_teacher_map.setdefault(assignment_id, set()).add(teacher_obj)

                    for assignment_id, teachers_set in assignment_teacher_map.items():
                        assignment_lookup[assignment_id].teachers.set(teachers_set)

                messages.success(request, 'Предмет обновлён.')
                return redirect('admin_subject_detail', subject_id=subject.id)
            except Exception as exc:
                messages.error(request, f'Ошибка при сохранении предмета: {exc}')

    if override_teacher_assignments is None:
        teacher_assignments_map = defaultdict(list)
        for assignment in assignments:
            for teacher in assignment.teachers.all():
                teacher_assignments_map[teacher.id].append(assignment)
    else:
        teacher_assignments_map = {
            teacher_id: [assignment_lookup[assignment_id] for assignment_id in assignment_ids]
            for teacher_id, assignment_ids in override_teacher_assignments.items()
        }

    teacher_cards = []
    for teacher in teachers:
        assigned = teacher_assignments_map.get(teacher.id, [])
        teacher_cards.append({
            'teacher': teacher,
            'assignments': assigned,
            'assignment_ids': [assignment.id for assignment in assigned],
            'assignment_count': len(assigned),
            'is_selected': teacher.id in selected_teacher_ids_context or bool(assigned),
        })

    selected_count = sum(1 for card in teacher_cards if card['is_selected'])
    active_teacher_id = next((card['teacher'].id for card in teacher_cards if card['is_selected']), None)
    if active_teacher_id is None and teacher_cards:
        active_teacher_id = teacher_cards[0]['teacher'].id

    assignment_options = [
        {
            'id': assignment.id,
            'label': f"{assignment.get_course_display()} / {assignment.profession} / {assignment.faculty.name} ({assignment.faculty.code})",
            'course': assignment.get_course_display(),
            'profession': assignment.profession,
            'faculty': assignment.faculty.name,
            'faculty_code': assignment.faculty.code,
        }
        for assignment in assignments
    ]

    context = {
        'subject': subject,
        'assignments': assignments,
        'teacher_cards': teacher_cards,
        'assignment_options': assignment_options,
        'selected_count': selected_count,
        'has_assignments': bool(assignments),
        'active_teacher_id': active_teacher_id,
    }
    return render(request, 'admin_panel/subjects/subject_edit.html', context)


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

    all_groups_index = []
    all_groups_queryset = Group.objects.filter(is_active=True).select_related('faculty').order_by('code')
    for group in all_groups_queryset:
        all_groups_index.append({
            'id': group.id,
            'code': group.code,
            'name': group.name,
            'profession': group.profession or '',
            'course': group.current_course,
            'faculty_id': group.faculty_id,
            'faculty_name': group.faculty.name if group.faculty else '',
            'status': group.status,
        })

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
        'groups_index_json': json.dumps(all_groups_index, ensure_ascii=False),
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
            log_activity(
                request.user,
                ActivityLog.ACTION_CREATE,
                f'Создана группа "{group.code}"',
                'bi-people',
                {'group_id': group.id}
            )
            
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
            log_activity(
                request.user,
                ActivityLog.ACTION_UPDATE,
                f'Обновлена группа "{group.code}"',
                'bi-people',
                {'group_id': group.id}
            )
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


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def schedule_overview_view(request):
    """Каталог расписаний по группам с фильтрами и статусами"""
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции перед работой с расписанием.')
        return redirect('admin_dashboard')

    search_query = request.GET.get('search', '').strip()
    faculty_filter = request.GET.get('faculty', '').strip()
    profession_filter = request.GET.get('profession', '').strip()
    profession_filter_lower = profession_filter.lower()
    status_filter = request.GET.get('status', '').strip()
    if status_filter and status_filter not in {'ready', 'needs_schedule'}:
        status_filter = ''
    course_filter = request.GET.get('course', '').strip()

    try:
        faculties = list(Faculty.objects.filter(is_active=True).order_by('name'))
        groups_qs = (
            Group.objects.filter(is_active=True)
            .select_related('faculty')
            .annotate(
            students_total=Count('students', distinct=True)
        )
            .order_by('faculty__name', 'profession', 'code')
        )

        if faculty_filter:
            groups_qs = groups_qs.filter(faculty_id=faculty_filter)

        groups = list(groups_qs)
    except Exception as exc:
        messages.error(request, f'Не удалось загрузить данные: {exc}')
        faculties = []
        groups = []

    faculty_ids = {group.faculty_id for group in groups}
    assignment_map = defaultdict(list)
    faculty_professions_map = defaultdict(set)

    for group in groups:
        if group.profession:
            faculty_professions_map[group.faculty_id].add(group.profession.strip())

    if faculty_ids:
        assignments_qs = SubjectAssignment.objects.filter(
            is_active=True,
            faculty_id__in=faculty_ids
        ).select_related('subject').prefetch_related('teachers')

        for assignment in assignments_qs:
            key = (
                assignment.faculty_id,
                (assignment.profession or '').strip().lower(),
                int(assignment.course) if assignment.course else None,
            )
            assignment_map[key].append(assignment)

    status_meta = {
        'ready': {
            'label': 'Готово',
            'description': 'Все предметы назначены и закреплены преподаватели',
            'badge': 'status-chip status-chip--ready',
        },
        'needs_schedule': {
            'label': 'Нет расписания',
            'description': 'Необходимо заполнить сетку расписания или закрепить преподавателей',
            'badge': 'status-chip status-chip--warning',
        },
    }

    course_set = set()
    catalog_items = []

    for group in groups:
        course = group.current_course
        course_str = str(course) if course is not None else ''
        if course_str:
            course_set.add(course_str)

        assignment_key = (
            group.faculty_id,
            (group.profession or '').strip().lower(),
            course,
        )
        related_assignments = assignment_map.get(assignment_key, [])

        subjects_total = len(related_assignments)
        subjects_with_teachers = 0
        subjects_without_teacher = 0
        teacher_ids = set()
        for assignment in related_assignments:
            assignment_teachers = list(assignment.teachers.all())
            if assignment_teachers:
                subjects_with_teachers += 1
                for teacher in assignment_teachers:
                    teacher_ids.add(teacher.id)
            else:
                subjects_without_teacher += 1

        # TODO: заменить на реальный подсчет занятий, когда сохранение расписания будет подключено
        lessons_total = 0
        teachers_total = len(teacher_ids)

        schedule_status = 'needs_schedule'
        if subjects_total > 0 and subjects_without_teacher == 0 and (subjects_with_teachers > 0 or lessons_total > 0):
            schedule_status = 'ready'

        catalog_items.append({
            'group': group,
            'faculty': group.faculty,
            'course': course,
            'students_total': getattr(group, 'students_total', group.students.count()),
            'subjects_total': subjects_total,
            'subjects_with_teachers': subjects_with_teachers,
            'teachers_total': teachers_total,
            'subjects_without_teacher': subjects_without_teacher,
            'lessons_total': lessons_total,
            'status_key': schedule_status,
            'status_meta': status_meta.get(schedule_status, status_meta['needs_schedule']),
            'search_blob': ' '.join(filter(None, [
                group.code,
                group.name,
                group.profession,
                group.faculty.name if group.faculty else '',
            ])).lower(),
        })

    available_courses = sorted(course_set, key=int) if course_set else []

    filtered_items = []

    for item in catalog_items:
        if profession_filter_lower and (item['group'].profession or '').strip().lower() != profession_filter_lower:
            continue
        if status_filter and item['status_key'] != status_filter:
            continue
        if search_query and lookup_search not in item['search_blob']:
            continue
        filtered_items.append(item)

    available_courses = sorted({str(item['course']) for item in filtered_items if item['course']}, key=int)

    if course_filter and course_filter not in course_set:
        course_filter = ''

    if not course_filter and available_courses:
        course_filter = available_courses[0]

    totals = {
        'all': len(catalog_items),
        'filtered': len(filtered_items),
        'ready': sum(1 for item in catalog_items if item['status_key'] == 'ready'),
        'needs_schedule': sum(1 for item in catalog_items if item['status_key'] == 'needs_schedule'),
    }

    status_keys = list(status_meta.keys())

    def init_status_counter():
        return {key: 0 for key in status_keys}

    def build_summary(counts):
        summary = []
        for key in status_keys:
            value = counts.get(key, 0)
            if value:
                meta = status_meta.get(key, {})
                summary.append({
                    'key': key,
                    'label': meta.get('label', key),
                    'badge': meta.get('badge', ''),
                    'count': value,
                })
        return summary

    faculty_sections = []
    for faculty in faculties:
        faculty_items = [item for item in filtered_items if item['faculty'].id == faculty.id]
        if not faculty_items:
            continue

        faculty_counts = init_status_counter()
        profession_map = {}

        for item in faculty_items:
            profession_name = item['group'].profession or 'Без профессии'
            course_number = item['course']

            profession_entry = profession_map.setdefault(profession_name, {
                'name': profession_name,
                'courses': defaultdict(lambda: {
                    'course': None,
                    'groups': [],
                    'status_counts': init_status_counter(),
                }),
                'status_counts': init_status_counter(),
            })

            course_entry = profession_entry['courses'][course_number]
            if course_entry['course'] is None:
                course_entry['course'] = course_number

            course_entry['groups'].append(item)
            course_entry['status_counts'][item['status_key']] += 1

            profession_entry['status_counts'][item['status_key']] += 1
            faculty_counts[item['status_key']] += 1

        professions = []
        total_groups_in_faculty = 0

        for prof_name, prof_data in sorted(profession_map.items(), key=lambda entry: entry[0].lower()):
            courses = []
            groups_in_profession = 0

            for course_number, course_data in sorted(prof_data['courses'].items(), key=lambda entry: entry[0]):
                course_groups = sorted(course_data['groups'], key=lambda item: item['group'].code)
                course_stats = {
                    'course': course_number,
                    'groups': course_groups,
                    'status_counts': course_data['status_counts'],
                    'summary': build_summary(course_data['status_counts']),
                    'groups_total': len(course_groups),
                }
                courses.append(course_stats)
                groups_in_profession += len(course_groups)

            professions.append({
                'name': prof_name,
                'courses': courses,
                'status_counts': prof_data['status_counts'],
                'summary': build_summary(prof_data['status_counts']),
                'groups_total': groups_in_profession,
            })
        total_groups_in_faculty += groups_in_profession

        faculty_sections.append({
            'faculty': faculty,
            'professions': professions,
            'status_counts': faculty_counts,
            'summary': build_summary(faculty_counts),
            'groups_total': total_groups_in_faculty,
        })

    faculty_professions = {
        str(faculty_id): sorted({prof for prof in professions if prof})
        for faculty_id, professions in faculty_professions_map.items()
    }

    current_filters = {
        'search': search_query,
        'faculty': faculty_filter,
        'profession': profession_filter,
        'status': status_filter,
        'course': course_filter,
    }

    selected_professions = []
    if faculty_filter:
        selected_professions = sorted(faculty_professions.get(str(faculty_filter), []))

    context = {
        'faculties': faculties,
        'faculty_sections': faculty_sections,
        'items': filtered_items,
        'search_query': search_query,
        'faculty_filter': faculty_filter,
        'profession_filter': profession_filter,
        'status_filter': status_filter,
        'course_filter': course_filter,
        'filter_badge_count': sum(1 for value in [faculty_filter, profession_filter, status_filter] if value),
        'status_meta': status_meta,
        'selected_status_meta': status_meta.get(status_filter) if status_filter else None,
        'available_courses': available_courses,
        'course_tabs': ['1', '2', '3', '4'],
        'totals': totals,
        'status_order': status_keys,
        'faculty_professions_json': json.dumps(faculty_professions, ensure_ascii=False),
        'current_filters_json': json.dumps(current_filters, ensure_ascii=False),
        'status_filter_options': [
            {'key': key, 'label': meta.get('label', key)}
            for key, meta in status_meta.items()
        ],
        'selected_professions': selected_professions,
    }

    try:
        log_activity(
            request.user,
            ActivityLog.ACTION_VIEW,
            'Просмотр каталога расписаний',
            'bi-calendar3'
        )
    except Exception:
        pass

    return render(request, 'admin_panel/schedule/schedule_overview.html', context)


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
def schedule_constructor_view(request, group_id):
    """Конструктор расписания для конкретной группы"""
    if not MODELS_AVAILABLE:
        messages.error(request, 'Модели не загружены. Выполните миграции перед работой с расписанием.')
        return redirect('admin_dashboard')

    group = get_object_or_404(
        Group.objects.select_related('faculty'),
        id=group_id
    )

    try:
        faculties = list(Faculty.objects.filter(is_active=True).order_by('name'))
        groups = list(
            Group.objects.filter(is_active=True)
            .select_related('faculty')
            .order_by('code')
        )
        assignments_for_group = list(
            SubjectAssignment.objects.filter(
                faculty=group.faculty,
                profession=group.profession,
                course=group.current_course,
                is_active=True
            ).select_related('subject').prefetch_related('teachers')
        )

        assigned_teachers_map = {}
        teacher_subjects_map = defaultdict(set)
        library_items = []
        seen_subject_ids = set()

        for assignment in assignments_for_group:
            subject = assignment.subject
            if not subject:
                continue

            teacher_objects = list(assignment.teachers.all())
            teacher_ids = [str(teacher.id) for teacher in teacher_objects]
            teacher_names = [
                teacher.get_short_name() or teacher.get_full_name()
                for teacher in teacher_objects
            ]

            if subject.id not in seen_subject_ids:
                seen_subject_ids.add(subject.id)
                library_items.append({
                    'id': subject.id,
                    'name': subject.name,
                    'short_name': subject.short_name or subject.name,
                    'teacher_names': teacher_names,
                    'teacher_ids': teacher_ids,
                })

            for teacher in teacher_objects:
                assigned_teachers_map[teacher.id] = teacher
                teacher_subjects_map[teacher.id].add(subject.id)

        if assigned_teachers_map:
            teachers = sorted(
                assigned_teachers_map.values(),
                key=lambda t: (t.last_name.lower(), t.first_name.lower(), t.middle_name.lower() if t.middle_name else '')
            )
        else:
            teachers = list(
                Teacher.objects.filter(is_active=True)
                .prefetch_related('subjects')
                .order_by('last_name', 'first_name')
            )
            for teacher in teachers:
                for subject_id in teacher.subjects.values_list('id', flat=True):
                    teacher_subjects_map[teacher.id].add(subject_id)
    except Exception as exc:
        messages.error(request, f'Не удалось загрузить данные для расписания: {exc}')
        faculties = []
        groups = []
        teachers = []
        assignments_for_group = []
        library_items = []
        teacher_subjects_map = defaultdict(set)

    now = timezone.localdate()
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=5)

    weekday_order = [
        {'key': 'monday', 'label': 'Понедельник', 'short': 'Пн'},
        {'key': 'tuesday', 'label': 'Вторник', 'short': 'Вт'},
        {'key': 'wednesday', 'label': 'Среда', 'short': 'Ср'},
        {'key': 'thursday', 'label': 'Четверг', 'short': 'Чт'},
        {'key': 'friday', 'label': 'Пятница', 'short': 'Пт'},
        {'key': 'saturday', 'label': 'Суббота', 'short': 'Сб'},
    ]

    time_slots = [
        {'id': 'slot1', 'order': 1, 'start': '08:30', 'end': '10:00'},
        {'id': 'slot2', 'order': 2, 'start': '10:10', 'end': '11:40'},
        {'id': 'slot3', 'order': 3, 'start': '12:00', 'end': '13:30'},
        {'id': 'slot4', 'order': 4, 'start': '13:50', 'end': '15:20'},
        {'id': 'slot5', 'order': 5, 'start': '15:30', 'end': '17:00'},
    ]
    default_day_buildings = {day['key']: 'nakhimovsky' for day in weekday_order}
    week_buildings_payload = {}
    week_lessons_payload = {}

    schedule_weeks = ScheduleWeek.objects.filter(group=group).order_by('week_start')
    for schedule_week in schedule_weeks:
        week_key = schedule_week.week_start.strftime('%Y-%m-%d')
        lessons_payload = schedule_week.lessons or {}
        buildings_payload = schedule_week.day_buildings or {}
        week_lessons_payload[week_key] = {
            'lessons': lessons_payload,
            'dayBuildings': buildings_payload,
        }
        if schedule_week.day_buildings:
            week_buildings_payload[week_key] = schedule_week.day_buildings

    groups_payload = [
        {
            'id': group.id,
            'code': group.code,
            'name': group.name,
            'display': f"{group.code} — {group.profession or ''}".strip(' —'),
            'faculty_id': group.faculty_id,
            'faculty': group.faculty.name if group.faculty else '',
            'profession': group.profession or '',
            'course': group.current_course,
        }
        for group in groups
    ]

    teachers_payload = []
    for teacher in teachers:
        teachers_payload.append({
            'id': teacher.id,
            'name': teacher.get_full_name(),
            'short_name': teacher.get_short_name(),
            'subjects': sorted({int(subject_id) for subject_id in teacher_subjects_map.get(teacher.id, set())}),
        })

    subjects_payload = [
        {
            'id': item['id'],
            'name': item['name'],
            'short_name': item['short_name'],
            'teacherIds': [int(tid) for tid in item['teacher_ids']],
            'is_active': True,
        }
        for item in library_items
    ]

    subjects_total = len(assignments_for_group)
    subjects_with_teachers = 0
    subjects_without_teacher = 0
    teacher_ids = set()
    for assignment in assignments_for_group:
        teachers_for_assignment = list(assignment.teachers.all())
        if teachers_for_assignment:
            subjects_with_teachers += 1
            for teacher in teachers_for_assignment:
                teacher_ids.add(teacher.id)
        else:
            subjects_without_teacher += 1

    group_schedule_stats = {
        'subjects_total': subjects_total,
        'subjects_with_teachers': subjects_with_teachers,
        'subjects_without_teacher': subjects_without_teacher,
        'teachers_total': len(teacher_ids),
        'students_total': group.students.count(),
    }

    context = {
        'faculties': faculties,
        'groups': groups,
        'teachers': teachers,
        'weekday_order': weekday_order,
        'time_slots': time_slots,
        'week_start': week_start,
        'week_end': week_end,
        'current_date': now,
        'week_range_label': f"{week_start.strftime('%d.%m')} – {week_end.strftime('%d.%m')}",
        'active_group': group,
        'group_schedule_stats': group_schedule_stats,
        'groups_json': json.dumps(groups_payload, ensure_ascii=False),
        'teachers_json': json.dumps(teachers_payload, ensure_ascii=False),
        'subjects_json': json.dumps(subjects_payload, ensure_ascii=False),
        'weekday_order_json': json.dumps(weekday_order, ensure_ascii=False),
        'time_slots_json': json.dumps(time_slots, ensure_ascii=False),
        'week_lessons_json': json.dumps(week_lessons_payload, ensure_ascii=False),
        'day_buildings_json': json.dumps(default_day_buildings, ensure_ascii=False),
        'week_buildings_json': json.dumps(week_buildings_payload, ensure_ascii=False),
        'active_group_json': json.dumps({
            'id': group.id,
            'code': group.code,
            'name': group.name,
            'course': group.current_course,
            'faculty': group.faculty.name if group.faculty else '',
            'profession': group.profession or '',
        }, ensure_ascii=False),
        'overview_url': reverse('admin_schedule'),
        'group_detail_url': reverse('group_detail', args=[group.id]),
        'library_items': library_items,
        'schedule_save_url': reverse('schedule_save_api', args=[group.id]),
        'schedule_conflict_check_url': reverse('schedule_check_conflict_api', args=[group.id]),
    }

    try:
        log_activity(
            request.user,
            ActivityLog.ACTION_VIEW,
            f'Конструктор расписания для группы {group.code}',
            'bi-calendar-week',
            {
                'group_id': group.id,
                'faculty_id': group.faculty_id,
                'course': group.current_course,
            }
        )
    except Exception:
        pass

    return render(request, 'admin_panel/schedule/schedule_main.html', context)


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
@require_POST
def schedule_save_api(request, group_id):
    if not MODELS_AVAILABLE:
        return JsonResponse({'success': False, 'error': 'Модели недоступны'}, status=500)

    group = get_object_or_404(Group, id=group_id)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Некорректный формат данных'}, status=400)

    weeks_payload = payload.get('weeks')
    if not isinstance(weeks_payload, dict) or not weeks_payload:
        return JsonResponse({'success': False, 'error': 'Нет данных для сохранения'}, status=400)

    def parse_week_start(value):
        try:
            parsed = datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None
        return parsed - timedelta(days=parsed.weekday())

    def normalize_lesson(raw_lesson):
        if not isinstance(raw_lesson, dict):
            return None
        subject_id = raw_lesson.get('subjectId') or raw_lesson.get('subject_id')
        if subject_id is None:
            return None
        try:
            subject_id = int(subject_id)
        except (TypeError, ValueError):
            return None

        teacher_ids = []
        for value in raw_lesson.get('teacherIds', []):
            try:
                teacher_ids.append(int(value))
            except (TypeError, ValueError):
                continue
        dedup_teacher_ids = []
        seen_teachers = set()
        for teacher_id in teacher_ids:
            if teacher_id not in seen_teachers:
                dedup_teacher_ids.append(teacher_id)
                seen_teachers.add(teacher_id)

        teacher_rooms_raw = raw_lesson.get('teacherRooms') or {}
        teacher_rooms = {}
        for teacher_id in dedup_teacher_ids:
            room_value = teacher_rooms_raw.get(str(teacher_id))
            if room_value is None:
                room_value = teacher_rooms_raw.get(teacher_id)
            teacher_rooms[str(teacher_id)] = str(room_value).strip() if room_value is not None else ''

        lesson_type = (raw_lesson.get('type') or 'lesson').strip() or 'lesson'

        return {
            'subjectId': subject_id,
            'subjectName': (raw_lesson.get('subjectName') or '').strip(),
            'subjectShort': (raw_lesson.get('subjectShort') or '').strip(),
            'teacherIds': dedup_teacher_ids,
            'teacherRooms': teacher_rooms,
            'type': lesson_type,
        }

    def normalize_entry(raw_entry):
        if not isinstance(raw_entry, dict):
            return None
        normalized = {'both': None, 'numerator': None, 'denominator': None}
        has_data = False
        for parity_key in normalized.keys():
            lesson = normalize_lesson(raw_entry.get(parity_key))
            if lesson:
                normalized[parity_key] = lesson
                has_data = True
        return normalized if has_data else None

    def sanitize_day_buildings(raw):
        if not isinstance(raw, dict):
            return {}
        sanitized = {}
        for day_key, value in raw.items():
            if not value:
                continue
            sanitized[str(day_key)] = str(value)
        return sanitized

    parsed_weeks = {}
    slots_by_week = {}
    subject_ids = set()
    teacher_ids = set()
    conflict_keys = set()

    for week_key, week_value in weeks_payload.items():
        week_start = parse_week_start(week_key)
        if not week_start:
            continue

        lessons_payload = {}
        day_buildings_raw = {}
        if isinstance(week_value, dict):
            lessons_payload = week_value.get('lessons') or {}
            day_buildings_raw = week_value.get('dayBuildings') or {}
        if not isinstance(lessons_payload, dict):
            lessons_payload = {}
        if not isinstance(day_buildings_raw, dict):
            day_buildings_raw = {}

        normalized_lessons = {}
        slot_refs = []

        for cell_key, entry in lessons_payload.items():
            if not isinstance(cell_key, str) or '__' not in cell_key:
                continue
            day_key, slot_id = cell_key.split('__', 1)
            normalized_entry = normalize_entry(entry)
            if not normalized_entry:
                continue
            normalized_lessons[cell_key] = normalized_entry

            for parity_key in ('both', 'numerator', 'denominator'):
                lesson = normalized_entry.get(parity_key)
                if not lesson:
                    continue
                subject_ids.add(lesson['subjectId'])
                if lesson['teacherIds']:
                    parities = ['numerator', 'denominator'] if parity_key == 'both' else [parity_key]
                    for teacher_id in lesson['teacherIds']:
                        teacher_ids.add(teacher_id)
                        for parity in parities:
                            conflict_keys.add((teacher_id, week_start, day_key, slot_id, parity))
                            slot_refs.append({
                                'lesson': lesson,
                                'teacher_id': teacher_id,
                                'parity': parity,
                                'day_key': day_key,
                                'slot_id': slot_id,
                            })

        parsed_weeks[week_start] = {
            'lessons': normalized_lessons,
            'day_buildings': sanitize_day_buildings(day_buildings_raw),
        }
        slots_by_week[week_start] = slot_refs

    if not parsed_weeks:
        return JsonResponse({'success': False, 'error': 'Не удалось определить недели для сохранения'}, status=400)

    subjects_map = {}
    if subject_ids:
        subjects_map = {subject.id: subject for subject in Subject.objects.filter(id__in=subject_ids)}

    teachers_map = {}
    if teacher_ids:
        teachers_map = {teacher.id: teacher for teacher in Teacher.objects.filter(id__in=teacher_ids)}

    for week_data in parsed_weeks.values():
        for entry in week_data['lessons'].values():
            for parity_key in ('both', 'numerator', 'denominator'):
                lesson = entry.get(parity_key)
                if not lesson:
                    continue
                subject = subjects_map.get(lesson['subjectId'])
                if subject:
                    if not lesson['subjectName']:
                        lesson['subjectName'] = subject.name
                    if not lesson['subjectShort']:
                        lesson['subjectShort'] = subject.short_name or subject.name

    conflicts_payload = []
    recorded_conflicts = set()
    if conflict_keys:
        teachers_to_check = [teacher_id for teacher_id, _, _, _, _ in conflict_keys]
        teachers_to_check_set = set(teachers_to_check)
        weeks_to_check = [week_start for _, week_start, _, _, _ in conflict_keys]
        days_to_check = [day_key for _, _, day_key, _, _ in conflict_keys]
        slots_to_check = [slot_id for _, _, _, slot_id, _ in conflict_keys]
        desired_keys = set(conflict_keys)
        week_targets = set(weeks_to_check)

        existing_slots = ScheduleTeacherSlot.objects.filter(
            teacher_id__in=teachers_to_check_set,
            week__week_start__in=week_targets,
            day_key__in=set(days_to_check),
            slot_id__in=set(slots_to_check),
            parity__in=[
                ScheduleTeacherSlot.PARITY_NUMERATOR,
                ScheduleTeacherSlot.PARITY_DENOMINATOR,
            ],
        ).exclude(week__group=group).select_related('teacher', 'week__group')

        for slot in existing_slots:
            conflict_key = (slot.teacher_id, slot.week.week_start, slot.day_key, slot.slot_id, slot.parity)
            if conflict_key in desired_keys and conflict_key not in recorded_conflicts:
                conflicts_payload.append({
                    'teacher': slot.teacher.get_short_name() if slot.teacher else 'Преподаватель',
                    'group': slot.week.group.code,
                    'week': slot.week.week_start.strftime('%Y-%m-%d'),
                    'day': slot.day_key,
                    'slot': slot.slot_id,
                    'parity': slot.parity,
                })
                recorded_conflicts.add(conflict_key)

        if not conflicts_payload:
            conflicting_weeks = ScheduleWeek.objects.filter(
                week_start__in=week_targets
            ).exclude(group=group).select_related('group')
            for other_week in conflicting_weeks:
                lessons_blob = other_week.lessons or {}
                if not isinstance(lessons_blob, dict):
                    continue
                for cell_key, entry in lessons_blob.items():
                    if not isinstance(entry, dict) or '__' not in cell_key:
                        continue
                    day_key, slot_id = cell_key.split('__', 1)
                    parity_map = {
                        'both': ['numerator', 'denominator'],
                        'numerator': ['numerator'],
                        'denominator': ['denominator'],
                    }
                    for parity_key, parities in parity_map.items():
                        lesson = entry.get(parity_key)
                        if not lesson:
                            continue
                        lesson_teachers = lesson.get('teacherIds') or lesson.get('teacher_ids') or []
                        for teacher_id in lesson_teachers:
                            try:
                                teacher_id_int = int(teacher_id)
                            except (TypeError, ValueError):
                                continue
                            if teacher_id_int not in teachers_to_check_set:
                                continue
                            for parity in parities:
                                conflict_key = (teacher_id_int, other_week.week_start, day_key, slot_id, parity)
                                if conflict_key in desired_keys and conflict_key not in recorded_conflicts:
                                    teacher_obj = teachers_map.get(teacher_id_int)
                                    conflicts_payload.append({
                                        'teacher': teacher_obj.get_short_name() if teacher_obj else 'Преподаватель',
                                        'group': other_week.group.code if other_week.group else '',
                                        'week': other_week.week_start.strftime('%Y-%m-%d'),
                                        'day': day_key,
                                        'slot': slot_id,
                                        'parity': parity,
                                    })
                                    recorded_conflicts.add(conflict_key)
                                    break
                            if conflicts_payload:
                                break
                        if conflicts_payload:
                            break
                    if conflicts_payload:
                        break
                if conflicts_payload:
                    break

    if conflicts_payload:
        return JsonResponse({
            'success': False,
            'error': 'Некоторые преподаватели заняты в других группах в выбранное время.',
            'conflicts': conflicts_payload,
        }, status=400)

    saved_week_keys = []

    with transaction.atomic():
        for week_start, data in parsed_weeks.items():
            week_obj, created = ScheduleWeek.objects.update_or_create(
                group=group,
                week_start=week_start,
                defaults={
                    'lessons': data['lessons'],
                    'day_buildings': data['day_buildings'],
                    'updated_by': request.user,
                },
            )
            if created and not week_obj.created_by_id:
                week_obj.created_by = request.user
                week_obj.save(update_fields=['created_by'])

            saved_week_keys.append(week_obj.week_start.strftime('%Y-%m-%d'))

            ScheduleTeacherSlot.objects.filter(week=week_obj).delete()

            slot_entries = []
            for slot in slots_by_week.get(week_start, []):
                lesson = slot['lesson']
                slot_entries.append(ScheduleTeacherSlot(
                    week=week_obj,
                    group=group,
                    teacher_id=slot['teacher_id'],
                    day_key=slot['day_key'],
                    slot_id=slot['slot_id'],
                    parity=slot['parity'],
                    subject_id=lesson['subjectId'],
                    subject_name=lesson['subjectName'],
                    subject_short=lesson['subjectShort'],
                    lesson_type=lesson['type'],
                ))
            if slot_entries:
                ScheduleTeacherSlot.objects.bulk_create(slot_entries)

    try:
        log_activity(
            request.user,
            ActivityLog.ACTION_UPDATE,
            f'Сохранение расписания для группы {group.code}',
            'bi-calendar-week',
            {'group_id': group.id, 'weeks': saved_week_keys}
        )
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'message': 'Расписание сохранено.',
        'savedWeeks': saved_week_keys,
    })


@login_required
@user_passes_test(is_admin_user, login_url='/accounts/login/')
@require_POST
def schedule_check_conflict_api(request, group_id):
    if not MODELS_AVAILABLE:
        return JsonResponse({'success': False, 'error': 'Модели недоступны'}, status=500)

    group = get_object_or_404(Group, id=group_id)
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Некорректный формат данных'}, status=400)

    week_start_raw = payload.get('weekStart')
    day_key = payload.get('dayKey')
    slot_key = payload.get('slotKey')
    parity_key = payload.get('parity') or 'both'
    teacher_ids_raw = payload.get('teacherIds') or []

    if not week_start_raw or not day_key or not slot_key:
        return JsonResponse({'success': False, 'error': 'Недостаточно данных для проверки'}, status=400)

    try:
        week_start = datetime.strptime(week_start_raw, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Некорректная дата недели'}, status=400)

    week_start -= timedelta(days=week_start.weekday())

    teacher_ids = []
    for value in teacher_ids_raw:
        try:
            teacher_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    if not teacher_ids:
        return JsonResponse({'success': True})

    parities = ['numerator', 'denominator'] if parity_key == 'both' else [parity_key]

    conflicts_payload = []

    teacher_objects = {
        teacher.id: teacher
        for teacher in Teacher.objects.filter(id__in=teacher_ids)
    }

    teacher_slots = ScheduleTeacherSlot.objects.filter(
        teacher_id__in=teacher_ids,
        week__week_start=week_start,
        day_key=day_key,
        slot_id=slot_key,
        parity__in=parities,
    ).exclude(week__group=group).select_related('teacher', 'week__group')

    for slot in teacher_slots:
        conflicts_payload.append({
            'teacher': slot.teacher.get_short_name() if slot.teacher else 'Преподаватель',
            'group': slot.week.group.code if slot.week and slot.week.group else '',
            'week': slot.week.week_start.strftime('%Y-%m-%d'),
            'day': slot.day_key,
            'slot': slot.slot_id,
            'parity': slot.parity,
        })

    if not conflicts_payload:
        other_weeks = ScheduleWeek.objects.filter(
            week_start=week_start
        ).exclude(group=group).select_related('group')

        parities_map = {
            'both': ['numerator', 'denominator'],
            'numerator': ['numerator'],
            'denominator': ['denominator'],
        }
        allowed_parities = parities_map.get(parity_key, ['numerator', 'denominator'])

        cell_key = f'{day_key}__{slot_key}'
        for week_entry in other_weeks:
            lessons_blob = week_entry.lessons or {}
            if not isinstance(lessons_blob, dict):
                continue
            entry = lessons_blob.get(cell_key)
            if not isinstance(entry, dict):
                continue
            for parity_option in allowed_parities:
                lesson = entry.get(parity_option) or (entry.get('both') if parity_option in ('numerator', 'denominator') else None)
                if not lesson:
                    continue
                lesson_teachers = lesson.get('teacherIds') or lesson.get('teacher_ids') or []
                for teacher_id in lesson_teachers:
                    try:
                        teacher_id_int = int(teacher_id)
                    except (TypeError, ValueError):
                        continue
                    if teacher_id_int not in teacher_ids:
                        continue
                    teacher_obj = teacher_objects.get(teacher_id_int)
                    conflicts_payload.append({
                        'teacher': teacher_obj.get_short_name() if teacher_obj else 'Преподаватель',
                        'group': week_entry.group.code if week_entry.group else '',
                        'week': week_entry.week_start.strftime('%Y-%m-%d'),
                        'day': day_key,
                        'slot': slot_key,
                        'parity': parity_option,
                    })
                    break
                if conflicts_payload:
                    break
            if conflicts_payload:
                break

    if conflicts_payload:
        message = 'Преподаватель занят в другой группе в это время.'
        return JsonResponse({'success': False, 'error': message, 'conflicts': conflicts_payload}, status=400)

    return JsonResponse({'success': True})


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
