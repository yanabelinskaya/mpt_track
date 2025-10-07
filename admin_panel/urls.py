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
]
