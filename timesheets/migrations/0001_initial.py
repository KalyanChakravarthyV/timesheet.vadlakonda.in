from decimal import Decimal
import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Client",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("contact_person", models.CharField(blank=True, max_length=255)),
                ("address", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=64, unique=True)),
                ("color", models.CharField(default="#6B7280", max_length=7)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Project",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(
                    choices=[("active", "Active"), ("paused", "Paused"), ("completed", "Completed"), ("archived", "Archived")],
                    default="active", max_length=20,
                )),
                ("color", models.CharField(default="#3B82F6", max_length=7)),
                ("default_hourly_rate", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
                ("budget_hours", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("is_billable", models.BooleanField(default=True)),
                ("client", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="projects", to="timesheets.client")),
                ("members", models.ManyToManyField(blank=True, related_name="projects", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                ("default_hourly_rate", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
                ("weekly_report_email", models.BooleanField(default=True)),
                ("avatar", models.ImageField(blank=True, null=True, upload_to="avatars/")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="TimeEntry",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("date", models.DateField()),
                ("hours", models.DecimalField(
                    decimal_places=2, max_digits=5,
                    validators=[
                        django.core.validators.MinValueValidator(Decimal("0.01")),
                        django.core.validators.MaxValueValidator(Decimal("24.00")),
                    ],
                )),
                ("description", models.TextField(blank=True)),
                ("is_billable", models.BooleanField(default=True)),
                ("hourly_rate", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("stopped_at", models.DateTimeField(blank=True, null=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="time_entries", to="timesheets.project")),
                ("tags", models.ManyToManyField(blank=True, related_name="time_entries", to="timesheets.tag")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="time_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-date", "-created_at"]},
        ),
        migrations.AddIndex(
            model_name="timeentry",
            index=models.Index(fields=["user", "date"], name="timesheets__user_id_date_idx"),
        ),
        migrations.AddIndex(
            model_name="timeentry",
            index=models.Index(fields=["project", "date"], name="timesheets__project_date_idx"),
        ),
        migrations.AddIndex(
            model_name="timeentry",
            index=models.Index(fields=["date"], name="timesheets__date_idx"),
        ),
        migrations.CreateModel(
            name="WeeklyReport",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("week_start", models.DateField()),
                ("week_end", models.DateField()),
                ("total_hours", models.DecimalField(decimal_places=2, max_digits=8)),
                ("sent_at", models.DateTimeField(auto_now_add=True)),
                ("email_provider", models.CharField(default="sendgrid", max_length=20)),
                ("recipient_email", models.EmailField(max_length=254)),
                ("attachment_name", models.CharField(blank=True, max_length=255)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="weekly_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-week_start"]},
        ),
        migrations.AlterUniqueTogether(
            name="weeklyreport",
            unique_together={("user", "week_start")},
        ),
    ]
