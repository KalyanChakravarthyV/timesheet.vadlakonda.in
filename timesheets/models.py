import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.save(update_fields=["is_deleted", "updated_at"])


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class UserProfile(TimestampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    timezone = models.CharField(max_length=64, default="UTC")
    default_hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    weekly_report_email = models.BooleanField(default=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} profile"


class Client(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Project(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    client = models.ForeignKey(
        Client, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects"
    )
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    color = models.CharField(max_length=7, default="#3B82F6")  # hex color for UI
    default_hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    budget_hours = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    members = models.ManyToManyField(User, related_name="projects", blank=True)
    is_billable = models.BooleanField(default=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def total_hours_logged(self):
        return self.time_entries.filter(is_deleted=False).aggregate(
            total=models.Sum("hours")
        )["total"] or Decimal("0.00")


class Tag(models.Model):
    name = models.CharField(max_length=64, unique=True)
    color = models.CharField(max_length=7, default="#6B7280")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TimeEntry(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="time_entries")
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="time_entries"
    )
    date = models.DateField()
    hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("24.00"))],
    )
    description = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="time_entries")
    is_billable = models.BooleanField(default=True)
    hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    # Timer support
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["project", "date"]),
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.project.name} — {self.date} ({self.hours}h)"

    def save(self, *args, **kwargs):
        # Inherit rate from project if not explicitly set
        if self.hourly_rate is None and self.project_id:
            self.hourly_rate = self.project.default_hourly_rate
        super().save(*args, **kwargs)

    @property
    def amount(self):
        rate = self.hourly_rate or Decimal("0.00")
        return (self.hours * rate).quantize(Decimal("0.01"))


class WeeklyReport(TimestampedModel):
    """Tracks which weekly reports have been sent."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="weekly_reports")
    week_start = models.DateField()
    week_end = models.DateField()
    total_hours = models.DecimalField(max_digits=8, decimal_places=2)
    sent_at = models.DateTimeField(auto_now_add=True)
    email_provider = models.CharField(max_length=20, default="sendgrid")
    recipient_email = models.EmailField()
    attachment_name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-week_start"]
        unique_together = [["user", "week_start"]]

    def __str__(self):
        return f"{self.user.email} — week of {self.week_start}"
