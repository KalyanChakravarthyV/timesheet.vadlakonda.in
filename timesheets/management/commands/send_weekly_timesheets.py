"""Django management command to send weekly timesheets to all users.

Usage:
    # Send for last completed Mon–Sun week (default)
    python manage.py send_weekly_timesheets

    # Send for a specific week
    python manage.py send_weekly_timesheets --week 2026-06-01

    # Dry-run (show what would be sent without dispatching emails)
    python manage.py send_weekly_timesheets --dry-run

    # Send only for a specific user
    python manage.py send_weekly_timesheets --user kalyan@kontracts.pro

    # Override recipient (useful for testing)
    python manage.py send_weekly_timesheets --recipient test@example.com
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from timesheets.models import TimeEntry, UserProfile
from timesheets.services.email_service import send_weekly_report


class Command(BaseCommand):
    help = "Send weekly timesheet summary emails to users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--week",
            type=str,
            help="Any date within the desired week, format YYYY-MM-DD. Defaults to last Mon–Sun.",
        )
        parser.add_argument(
            "--user",
            type=str,
            dest="user_email",
            help="Send only for this user email.",
        )
        parser.add_argument(
            "--recipient",
            type=str,
            help="Override recipient email (useful for testing).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be sent without dispatching emails.",
        )

    def handle(self, *args, **options):
        # Resolve target week
        week_str = options.get("week")
        if week_str:
            try:
                ref_date = date.fromisoformat(week_str)
            except ValueError:
                raise CommandError("--week must be YYYY-MM-DD")
        else:
            today = date.today()
            # Default: the most recently completed Mon–Sun week
            ref_date = today - timedelta(days=today.weekday() + 7)

        monday = ref_date - timedelta(days=ref_date.weekday())
        sunday = monday + timedelta(days=6)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Weekly timesheet dispatch: {monday} → {sunday}"
            )
        )

        # Resolve user(s)
        if options["user_email"]:
            try:
                users = [User.objects.get(email=options["user_email"])]
            except User.DoesNotExist:
                raise CommandError(f"User not found: {options['user_email']}")
        else:
            # Only active users who have opted in
            opted_in_ids = (
                UserProfile.objects.filter(weekly_report_email=True, is_deleted=False)
                .values_list("user_id", flat=True)
            )
            users = list(User.objects.filter(is_active=True, id__in=opted_in_ids))

        if not users:
            self.stdout.write(self.style.WARNING("No eligible users found."))
            return

        sent = 0
        skipped = 0
        failed = 0

        for user in users:
            entries = list(
                TimeEntry.objects
                .filter(user=user, date__gte=monday, date__lte=sunday, is_deleted=False)
                .select_related("project", "project__client")
                .prefetch_related("tags")
                .order_by("date", "project__name")
            )

            total_hours = sum(e.hours for e in entries)
            recipient = options.get("recipient") or user.email

            label = f"{user.email} ({total_hours:.2f}h, {len(entries)} entries)"

            if not entries:
                self.stdout.write(f"  SKIP  {user.email} — no entries for this week")
                skipped += 1
                continue

            if options["dry_run"]:
                self.stdout.write(f"  DRY   would send to {recipient}: {label}")
                sent += 1
                continue

            result = send_weekly_report(
                user=user,
                entries=entries,
                week_start=monday,
                week_end=sunday,
                recipient_email=recipient,
            )

            if result["success"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  SENT  {label} → {recipient} via {result['provider']}"
                    )
                )
                sent += 1
            else:
                self.stdout.write(
                    self.style.ERROR(f"  FAIL  {label}: {result['error']}")
                )
                failed += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done — sent: {sent}, skipped: {skipped}, failed: {failed}"
            )
        )
