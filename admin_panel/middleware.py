# admin_panel/middleware.py
from django.shortcuts import redirect
from django.contrib import messages

class RoleBasedRedirectMiddleware:
    """Middleware для перенаправления пользователей по ролям"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Пути админ-панели
        self.admin_paths = [
            '/admin-panel/',
            '/students/',
            '/faculties/',
        ]
        # Пути для студентов
        self.student_paths = [
            '/student-cabinet/',
        ]
        # Исключения
        self.exempt_paths = [
            '/accounts/',
            '/admin/',
            '/static/',
            '/media/',
        ]

    def __call__(self, request):
        if request.user.is_authenticated and request.path not in self.exempt_paths:
            # Проверяем админские пути
            if any(request.path.startswith(path) for path in self.admin_paths):
                if not (request.user.is_staff or request.user.is_superuser):
                    messages.error(request, 'У вас нет прав доступа к админ-панели')
                    return redirect('student_dashboard' if hasattr(request.user, 'student_profile') else 'login')
            
            # Проверяем студенческие пути
            elif any(request.path.startswith(path) for path in self.student_paths):
                if not hasattr(request.user, 'student_profile'):
                    messages.error(request, 'У вас нет доступа к студенческому кабинету')
                    return redirect('admin_dashboard' if (request.user.is_staff or request.user.is_superuser) else 'login')

        response = self.get_response(request)
        return response
