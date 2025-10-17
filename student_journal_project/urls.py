# student_journal_project/urls.py
from django.contrib import admin
from django.urls import path, include
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from django.http import HttpResponse
from django.views.decorators.http import require_GET

@require_GET
def favicon_view(request):
    return HttpResponse(status=204)

# Swagger настройки
schema_view = get_schema_view(
    openapi.Info(
        title="МПТ Журнал API",
        default_version='v1',
        description="API для управления студентами и факультетами",
        contact=openapi.Contact(email="admin@mpt.ru"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('admin_panel.urls')),
    path('api/', include('admin_panel.api_urls')),
    
    # Swagger UI
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
