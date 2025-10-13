# admin_panel/api_urls.py
from django.urls import path
from . import api_views

urlpatterns = [
    # === СТУДЕНТЫ API ===
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
    
    # === ФАКУЛЬТЕТЫ API ===
    path('faculties/<int:faculty_id>/delete/', api_views.faculty_delete_api, name='faculty_delete_api'),
    path('faculties/<int:faculty_id>/toggle-status/', api_views.faculty_toggle_status_api, name='faculty_toggle_status_api'),
    
    # Массовые операции факультетов
    path('faculties/bulk-activate/', api_views.faculty_bulk_activate_api, name='faculty_bulk_activate_api'),
    path('faculties/bulk-deactivate/', api_views.faculty_bulk_deactivate_api, name='faculty_bulk_deactivate_api'),
    path('faculties/bulk-delete/', api_views.faculty_bulk_delete_api, name='faculty_bulk_delete_api'),
    
    # Экспорт факультетов
    path('faculties/export/', api_views.faculty_export_view, name='faculty_export'),
]
