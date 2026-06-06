from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import TestCase

from timesheets.services.excel_export import build_weekly_excel


class ExcelExportTest(TestCase):
    def test_build_weekly_excel_returns_bytes(self):
        user = MagicMock(spec=User)
        user.get_full_name.return_value = "Jane Doe"
        user.email = "jane@example.com"

        project = MagicMock()
        project.name = "Internal Tools"
        project.client.name = "Acme"

        entry = MagicMock()
        entry.date = date(2026, 6, 2)
        entry.project = project
        entry.hours = Decimal("4.0")
        entry.hourly_rate = Decimal("100.00")
        entry.amount = Decimal("400.00")
        entry.is_billable = True
        entry.description = "API development"
        entry.tags.all.return_value = []

        result = build_weekly_excel(
            user, [entry],
            week_start=date(2026, 6, 1),
            week_end=date(2026, 6, 7),
        )
        # xlsx magic bytes
        self.assertTrue(result[:4] == b"PK\x03\x04")
