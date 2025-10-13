# admin_panel/urls.py
from django.urls import path, include
from . import views, api_views

urlpatterns = [
    # === ГЛАВНАЯ СТРАНИЦА ===
    path('', views.dashboard_view, name='admin_dashboard'),
    path('accounts/', include('django.contrib.auth.urls')),
    
    # === ОСНОВНЫЕ HTML СТРАНИЦЫ ===
    # Факультеты
    path('faculties/', views.faculties_list_view, name='admin_faculties'),
    path('faculties/create/', views.faculty_create_view, name='admin_faculty_create'),
    path('faculties/import/', views.faculty_import_view, name='admin_faculty_import'),
    
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
    
    # === API ENDPOINTS ДЛЯ ФАКУЛЬТЕТОВ (заглушки) ===
    # Одиночные операции
    path('faculties/<int:faculty_id>/delete/', api_views.faculty_delete_api, name='faculty_delete_api'),
    path('faculties/<int:faculty_id>/toggle-status/', api_views.faculty_toggle_status_api, name='faculty_toggle_status_api'),
    
    # Массовые операции факультетов
    path('faculties/bulk-activate/', api_views.faculty_bulk_activate_api, name='faculty_bulk_activate_api'),
    path('faculties/bulk-deactivate/', api_views.faculty_bulk_deactivate_api, name='faculty_bulk_deactivate_api'),
    path('faculties/bulk-delete/', api_views.faculty_bulk_delete_api, name='faculty_bulk_delete_api'),
    
    # Экспорт факультетов
    path('faculties/export/', api_views.faculty_export_view, name='faculty_export'),
]
