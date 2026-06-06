from django import forms
from timesheets.models import Client, Project, TimeEntry, Tag


class TimeEntryForm(forms.ModelForm):
    class Meta:
        model = TimeEntry
        fields = ["date", "project", "hours", "description", "is_billable", "hourly_rate", "tags"]

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if user.is_staff:
            self.fields["project"].queryset = Project.objects.filter(is_deleted=False)
        else:
            self.fields["project"].queryset = Project.objects.filter(
                members=user, is_deleted=False
            )


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "client", "description", "status", "color", "default_hourly_rate", "budget_hours", "is_billable"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.filter(is_deleted=False)


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "contact_person", "email", "address", "notes"]
