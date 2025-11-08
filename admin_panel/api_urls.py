# admin_panel/api_urls.py
from django.urls import path
from . import api_views

urlpatterns = [
    # === АУТЕНТИФИКАЦИЯ ===
    path('auth/password-recovery/', api_views.password_recovery_request_api, name='password_recovery_request_api'),
    path('auth/password-recovery/<int:request_id>/process/', api_views.password_recovery_process_api, name='password_recovery_process_api'),

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

    # === ПРЕПОДАВАТЕЛИ API ===
    path('teachers/<int:teacher_id>/delete/', api_views.teacher_delete_api, name='teacher_delete_api'),
    path('teachers/<int:teacher_id>/toggle-status/', api_views.teacher_toggle_status_api, name='teacher_toggle_status_api'),
    path('teachers/<int:teacher_id>/create-access/', api_views.teacher_create_access_api, name='teacher_create_access_api'),
    path('teachers/<int:teacher_id>/reset-password/', api_views.teacher_reset_password_api, name='teacher_reset_password_api'),
    path('teachers/bulk-activate/', api_views.teacher_bulk_activate_api, name='teacher_bulk_activate_api'),
    path('teachers/bulk-deactivate/', api_views.teacher_bulk_deactivate_api, name='teacher_bulk_deactivate_api'),
    path('teachers/bulk-delete/', api_views.teacher_bulk_delete_api, name='teacher_bulk_delete_api'),
    path('teachers/bulk-create-access/', api_views.teacher_bulk_create_access_api, name='teacher_bulk_create_access_api'),
    path('teachers/export/', api_views.teacher_export_view, name='teacher_export'),
    path('teachers/list/', api_views.teacher_list_api, name='teacher_list_api'),

    # === ФАКУЛЬТЕТЫ API ===
    path('faculties/<int:faculty_id>/delete/', api_views.faculty_delete_api, name='faculty_delete_api'),
    path('faculties/<int:faculty_id>/toggle-status/', api_views.faculty_toggle_status_api, name='faculty_toggle_status_api'),
    
    # Массовые операции факультетов
    path('faculties/bulk-activate/', api_views.faculty_bulk_activate_api, name='faculty_bulk_activate_api'),
    path('faculties/bulk-deactivate/', api_views.faculty_bulk_deactivate_api, name='faculty_bulk_deactivate_api'),
    path('faculties/bulk-delete/', api_views.faculty_bulk_delete_api, name='faculty_bulk_delete_api'),
    
    # Экспорт факультетов
    path('faculties/export/', api_views.faculty_export_view, name='faculty_export'),

    # === ГРУППЫ API ===
    path('groups/', api_views.group_list_api, name='group_list_api'),
    path('groups/create/', api_views.group_create_api, name='group_create_api'),
    path('groups/<int:group_id>/', api_views.group_detail_api, name='group_detail_api'),
    path('groups/<int:group_id>/update/', api_views.group_update_api, name='group_update_api'),
    path('groups/<int:group_id>/delete/', api_views.group_delete_api, name='group_delete_api'),
    path('groups/transfer-student/', api_views.transfer_student_api, name='group_transfer_student_api'),

    # === ПРЕДМЕТЫ API ===
    path('subjects/', api_views.subject_list_api, name='subject_list_api'),
    path('subjects/create/', api_views.subject_create_api, name='subject_create_api'),
    path('subjects/<int:subject_id>/', api_views.subject_detail_api, name='subject_detail_api'),
    path('subjects/<int:subject_id>/update/', api_views.subject_update_api, name='subject_update_api'),
    path('subjects/<int:subject_id>/toggle-status/', api_views.subject_toggle_status_api, name='subject_toggle_status_api'),
    path('subjects/<int:subject_id>/delete/', api_views.subject_delete_api, name='subject_delete_api'),
]
