import django_filters
from .models import TimeEntry, Project


class TimeEntryFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    week = django_filters.DateFilter(method="filter_week")
    project = django_filters.UUIDFilter(field_name="project__id")
    client = django_filters.UUIDFilter(field_name="project__client__id")
    is_billable = django_filters.BooleanFilter()
    tags = django_filters.CharFilter(field_name="tags__name", lookup_expr="icontains")

    class Meta:
        model = TimeEntry
        fields = ["date_from", "date_to", "week", "project", "client", "is_billable"]

    def filter_week(self, queryset, name, value):
        # value = any date in the desired week; filter Mon–Sun
        from datetime import timedelta
        monday = value - timedelta(days=value.weekday())
        sunday = monday + timedelta(days=6)
        return queryset.filter(date__gte=monday, date__lte=sunday)


class ProjectFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status")
    client = django_filters.UUIDFilter(field_name="client__id")
    is_billable = django_filters.BooleanFilter()

    class Meta:
        model = Project
        fields = ["status", "client", "is_billable"]
