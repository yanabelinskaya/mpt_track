# admin_panel/urls.py
from django.urls import path, include
from . import views, api_views

urlpatterns = [
    # === ГЛАВНАЯ СТРАНИЦА ===
    path('', views.dashboard_view, name='home'),  # Главная страница с перенаправлением
    path('admin-panel/', views.admin_dashboard_view, name='admin_dashboard'),  # Админ-панель
    path('student-cabinet/', views.student_dashboard_view, name='student_dashboard'),  # Кабинет студента
    path('accounts/', include('django.contrib.auth.urls')),
    
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
]
