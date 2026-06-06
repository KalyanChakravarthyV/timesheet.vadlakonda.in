from django.urls import path
from . import views

app_name = "ui"

urlpatterns = [
    path("login/",  views.UILoginView.as_view(),  name="login"),
    path("logout/", views.UILogoutView.as_view(), name="logout"),

    path("", views.dashboard, name="dashboard"),

    path("entries/",            views.entry_list,   name="entry_list"),
    path("entries/add/",        views.entry_add,    name="entry_add"),
    path("entries/<uuid:pk>/",  views.entry_edit,   name="entry_edit"),
    path("entries/<uuid:pk>/delete/", views.entry_delete, name="entry_delete"),

    path("projects/",           views.project_list, name="project_list"),
    path("projects/add/",       views.project_add,  name="project_add"),
    path("projects/<uuid:pk>/", views.project_edit, name="project_edit"),

    path("clients/",            views.client_list,  name="client_list"),
    path("clients/add/",        views.client_add,   name="client_add"),
    path("clients/<uuid:pk>/",  views.client_edit,  name="client_edit"),

    path("reports/weekly/",       views.weekly_report, name="weekly_report"),
    path("reports/weekly/export/",views.weekly_export, name="weekly_export"),
    path("reports/weekly/send/",  views.weekly_send,   name="weekly_send"),
]
