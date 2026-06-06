from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


def api_root(request):
    return JsonResponse({
        "service": "Timesheet API",
        "version": "1.0.0",
        "endpoints": {
            "admin": "/admin/",
            "auth_token": "/api/auth/token/",
            "clients": "/api/clients/",
            "projects": "/api/projects/",
            "time_entries": "/api/time-entries/",
            "time_entries_bulk": "/api/time-entries/bulk/",
            "weekly_summary": "/api/time-entries/summary/weekly/",
            "weekly_export": "/api/time-entries/export/weekly/",
            "weekly_email": "/api/time-entries/send/weekly/",
            "tags": "/api/tags/",
            "profile": "/api/profile/",
            "weekly_reports": "/api/weekly-reports/",
        },
    })


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("timesheets.urls")),
    path("api/info/", api_root),
    path("", include("ui.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
