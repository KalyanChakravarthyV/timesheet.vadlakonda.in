from django import forms
from django.contrib.auth.models import User
from timesheets.models import Client, Project, TimeEntry, Tag, Payment


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


class PaymentForm(forms.Form):
    paid_to = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("first_name", "email"),
        label="Pay To",
    )
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    payment_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reference = forms.CharField(max_length=255, required=False)
    status = forms.ChoiceField(choices=Payment.Status.choices)
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    document = forms.FileField(required=False)
    entry_ids = forms.MultipleChoiceField(required=False)
