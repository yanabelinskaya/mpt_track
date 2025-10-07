from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render

def home_view(request):
    """Главная страница проекта"""
    return render(request, 'home.html')

urlpatterns = [
    path('', include('admin_panel.urls')),
]

# Для статических файлов в режиме разработки  
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
