# admin_panel/urls.py
from django.urls import path, include
from . import views, api_views

urlpatterns = [
    # === ГЛАВНАЯ СТРАНИЦА ===
    path('', views.dashboard_view, name='home'),  # Главная страница с перенаправлением
    path('admin-panel/', views.admin_dashboard_view, name='admin_dashboard'),  # Админ-панель
    path('student-cabinet/', views.student_dashboard_view, name='student_dashboard'),  # Кабинет студента
    path('teacher-cabinet/', views.teacher_dashboard_view, name='teacher_dashboard'),  # Кабинет преподавателя
    path('accounts/', include('django.contrib.auth.urls')),
    path('activity-logs/add/', views.activity_log_add_view, name='activity_log_add'),
    path('activity-logs/remove/', views.activity_log_remove_view, name='activity_log_remove'),
    path('activity-logs/clear/', views.activity_log_clear_view, name='activity_log_clear'),
    
    # === ОСНОВНЫЕ HTML СТРАНИЦЫ ===
    # Факультеты
    path('faculties/', views.faculties_list_view, name='admin_faculties'),
    path('faculties/create/', views.faculty_create_view, name='admin_faculty_create'),
    path('faculties/<int:faculty_id>/', views.faculty_detail_view, name='admin_faculty_detail'),  # ДОБАВЛЕНО
    path('faculties/<int:faculty_id>/edit/', views.faculty_edit_view, name='admin_faculty_edit'),  # ДОБАВЛЕНО
    
    # Студенты
    path('students/', views.students_list_view, name='admin_students'),
    path('students/create/', views.student_create_view, name='admin_student_create'),
    path('students/import/', views.student_import_view, name='admin_student_import'),
    path('students/<int:student_id>/', views.student_detail_view, name='admin_student_detail'),
    path('students/<int:student_id>/edit/', views.student_edit_view, name='admin_student_edit'),

    # Преподаватели
    path('teachers/', views.teachers_list_view, name='admin_teachers'),
    path('teachers/create/', views.teacher_create_view, name='admin_teacher_create'),
    path('teachers/import/', views.teacher_import_view, name='admin_teacher_import'),
    path('teachers/import/sample/', views.download_teacher_sample, name='download_teacher_sample'),
    path('teachers/<int:teacher_id>/', views.teacher_detail_view, name='admin_teacher_detail'),
    path('teachers/<int:teacher_id>/edit/', views.teacher_edit_view, name='admin_teacher_edit'),

    # === ЗАГРУЗКА ФАЙЛОВ ===
    path('download/students-sample/', views.download_sample_excel, name='download_sample_excel'),
    
    # === API ENDPOINTS ДЛЯ СТУДЕНТОВ ===
    # Одиночные операции
    path('students/<int:student_id>/delete/', api_views.student_delete_api, name='student_delete_api'),
    path('students/<int:student_id>/toggle-status/', api_views.student_toggle_status_api, name='student_toggle_status_api'),
    path('students/<int:student_id>/create-access/', api_views.student_create_access_api, name='student_create_access_api'),
    path('students/<int:student_id>/reset-password/', api_views.student_reset_password_api, name='student_reset_password_api'),
    
    # Массовые операции студентов
    path('students/bulk-activate/', api_views.student_bulk_activate_api, name='student_bulk_activate_api'),
    path('students/bulk-deactivate/', api_views.student_bulk_deactivate_api, name='student_bulk_deactivate_api'),
    path('students/bulk-delete/', api_views.student_bulk_delete_api, name='student_bulk_delete_api'),
    path('students/bulk-create-access/', api_views.student_bulk_create_access_api, name='student_bulk_create_access_api'),
    
    # Экспорт и список студентов
    path('students/export/', api_views.student_export_view, name='student_export'),
    path('students/list/', api_views.student_list_api, name='student_list_api'),
    
    # === API ENDPOINTS ДЛЯ ФАКУЛЬТЕТОВ ===
    # Одиночные операции
    path('faculties/<int:faculty_id>/delete/', api_views.faculty_delete_api, name='faculty_delete_api'),
    path('faculties/<int:faculty_id>/toggle-status/', api_views.faculty_toggle_status_api, name='faculty_toggle_status_api'),
    
    # Массовые операции факультетов
    path('faculties/bulk-activate/', api_views.faculty_bulk_activate_api, name='faculty_bulk_activate_api'),
    path('faculties/bulk-deactivate/', api_views.faculty_bulk_deactivate_api, name='faculty_bulk_deactivate_api'),
    path('faculties/bulk-delete/', api_views.faculty_bulk_delete_api, name='faculty_bulk_delete_api'),
    
    # список факультетов
    path('faculties/list/', api_views.faculty_list_api, name='faculty_list_api'),  # ДОБАВЛЕНО

    # Резервные копии
    path('backups/', views.backups_list_view, name='admin_backups'),
    path('backups/create/', views.backup_create_view, name='admin_backup_create'),
    path('backups/<int:backup_id>/delete/', views.backup_delete_view, name='admin_backup_delete'),
    path('backups/<int:backup_id>/download/', views.backup_download_view, name='admin_backup_download'),
    path('backups/<int:backup_id>/restore/', views.backup_restore_view, name='admin_backup_restore'),


    path('groups/', views.groups_main_view, name='groups_main'),
    path('groups/<int:group_id>/edit/', views.group_edit_view, name='group_edit'),
    path('groups/<int:group_id>/', views.group_detail_view, name='group_detail'),
    path('groups/create/', views.group_create_view, name='group_create'),

    # Расписание
    path('schedule/', views.schedule_overview_view, name='admin_schedule'),
    path('schedule/<int:group_id>/constructor/', views.schedule_constructor_view, name='admin_schedule_group'),
    path('schedule/<int:group_id>/save/', views.schedule_save_api, name='schedule_save_api'),
    path('schedule/<int:group_id>/check-conflict/', views.schedule_check_conflict_api, name='schedule_check_conflict_api'),
    path('teacher-schedule/', views.teacher_schedule_view, name='teacher_schedule'),

    # Предметы
    path('subjects/', views.subjects_main_view, name='admin_subjects'),
    path('subjects/create/', views.subject_create_view, name='admin_subject_create'),
    path('subjects/<int:subject_id>/', views.subject_detail_view, name='admin_subject_detail'),
    path('subjects/<int:subject_id>/edit/', views.subject_edit_view, name='admin_subject_edit'),

    # API endpoints example:
    path('groups/transfer-student/', views.transfer_student_api, name='transfer_student_api'),
    path('groups/remove-student/', views.remove_student_from_group_api, name='remove_student_api'),
    path('groups/<int:group_id>/add-student/', views.add_student_to_group_api, name='add_student_to_group_api'),
]
