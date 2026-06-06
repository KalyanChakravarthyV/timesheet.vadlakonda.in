"""Celery tasks — weekly timesheet emails are scheduled here."""

from datetime import date, timedelta

from celery import shared_task
from django.contrib.auth.models import User

from .models import TimeEntry, UserProfile
from .services.email_service import send_weekly_report


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_weekly_timesheets_task(self, week_start_iso: str | None = None):
    """
    Send weekly timesheet emails for all opted-in users.
    Scheduled every Monday at 08:00 UTC via django-celery-beat.
    """
    if week_start_iso:
        monday = date.fromisoformat(week_start_iso)
    else:
        today = date.today()
        monday = today - timedelta(days=today.weekday() + 7)

    sunday = monday + timedelta(days=6)

    opted_in_ids = (
        UserProfile.objects.filter(weekly_report_email=True, is_deleted=False)
        .values_list("user_id", flat=True)
    )
    users = User.objects.filter(is_active=True, id__in=opted_in_ids)

    results = []
    for user in users:
        entries = list(
            TimeEntry.objects
            .filter(user=user, date__gte=monday, date__lte=sunday, is_deleted=False)
            .select_related("project", "project__client")
            .prefetch_related("tags")
        )
        if not entries:
            results.append({"user": user.email, "status": "skipped", "reason": "no entries"})
            continue

        result = send_weekly_report(
            user=user,
            entries=entries,
            week_start=monday,
            week_end=sunday,
        )
        results.append({
            "user": user.email,
            "status": "sent" if result["success"] else "failed",
            "provider": result.get("provider"),
            "error": result.get("error"),
        })

    return results
