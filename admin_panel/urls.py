from django.urls import path
from . import views

urlpatterns = [
    # Главная страница
    path('', views.dashboard_view, name='admin_dashboard'),
    
    # Студенты
    path('students/', views.students_list_view, name='admin_students'),
    path('students/create/', views.student_create_view, name='admin_student_create'),
    path('students/<int:pk>/', views.student_detail_view, name='admin_student_detail'),
    path('students/<int:pk>/edit/', views.student_edit_view, name='admin_student_edit'),
    path('students/<int:pk>/delete/', views.student_delete_view, name='admin_student_delete'),
    path('students/<int:pk>/toggle-status/', views.student_toggle_status_view, name='admin_student_toggle_status'),
    
    # Массовые операции со студентами
    path('students/bulk-delete/', views.students_bulk_delete_view, name='admin_students_bulk_delete'),
    path('students/bulk-create-access/', views.students_bulk_create_access_view, name='admin_students_bulk_create_access'),
    path('students/bulk-update-status/', views.students_bulk_update_status_view, name='admin_students_bulk_update_status'),
    
    # Импорт/Экспорт студентов
    path('students/import/', views.student_import_view, name='admin_student_import'),
    path('students/export/', views.students_export_view, name='admin_students_export'),
    
    # Образец Excel файла
    path('download-sample-excel/', views.download_sample_excel, name='download_sample_excel'),

    # Факультеты
    path('faculties/', views.faculties_list_view, name='admin_faculties'),
    path('faculties/create/', views.faculty_create_view, name='admin_faculty_create'),
    path('faculties/import/', views.faculty_import_view, name='admin_faculty_import'),
    path('faculties/download-sample/', views.download_faculty_sample_excel, name='download_faculty_sample_excel'),
    path('faculties/<int:pk>/', views.faculty_detail_view, name='admin_faculty_detail'),
    path('faculties/<int:pk>/edit/', views.faculty_edit_view, name='admin_faculty_edit'),
    path('faculties/<int:pk>/delete/', views.faculty_delete_view, name='admin_faculty_delete'),
    path('faculties/<int:pk>/toggle-status/', views.faculty_toggle_status_view, name='admin_faculty_toggle_status'),
    
    # Массовые операции с факультетами
    path('faculties/bulk-delete/', views.faculties_bulk_delete_view, name='admin_faculties_bulk_delete'),
    path('faculties/bulk-update-status/', views.faculties_bulk_update_status_view, name='admin_faculties_bulk_update_status'),
    
    # Экспорт факультетов
    path('faculties/export/', views.faculties_export_view, name='admin_faculties_export'),
]
