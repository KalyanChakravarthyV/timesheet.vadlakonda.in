from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken import views as auth_views

from . import views

router = DefaultRouter()
router.register("clients", views.ClientViewSet, basename="client")
router.register("projects", views.ProjectViewSet, basename="project")
router.register("time-entries", views.TimeEntryViewSet, basename="timeentry")
router.register("tags", views.TagViewSet, basename="tag")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/token/", auth_views.obtain_auth_token, name="api-token"),
    path("profile/", views.UserProfileView.as_view(), name="user-profile"),
    path("weekly-reports/", views.WeeklyReportListView.as_view(), name="weekly-reports"),
]
