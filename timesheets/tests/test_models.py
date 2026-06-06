from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from timesheets.models import Client, Project, Tag, TimeEntry


class TimeEntryModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test@example.com", email="test@example.com")
        self.client_obj = Client.objects.create(name="Acme Corp")
        self.project = Project.objects.create(
            name="Website Redesign",
            client=self.client_obj,
            default_hourly_rate=Decimal("120.00"),
        )

    def test_amount_calculated_from_project_rate(self):
        entry = TimeEntry.objects.create(
            user=self.user,
            project=self.project,
            date=date.today(),
            hours=Decimal("2.5"),
        )
        self.assertEqual(entry.amount, Decimal("300.00"))

    def test_soft_delete_excludes_from_default_manager(self):
        entry = TimeEntry.objects.create(
            user=self.user, project=self.project,
            date=date.today(), hours=Decimal("1.00"),
        )
        entry.soft_delete()
        self.assertEqual(TimeEntry.objects.filter(id=entry.id).count(), 0)
        self.assertEqual(TimeEntry.all_objects.filter(id=entry.id).count(), 1)

    def test_hours_inherited_from_project(self):
        entry = TimeEntry(
            user=self.user, project=self.project,
            date=date.today(), hours=Decimal("3.00"),
        )
        entry.save()
        self.assertEqual(entry.hourly_rate, Decimal("120.00"))
