from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Client, Project, TimeEntry, Tag, UserProfile, WeeklyReport, Payment


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "date_joined"]
        read_only_fields = ["date_joined"]


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id", "user", "timezone", "default_hourly_rate",
            "weekly_report_email", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]


class ClientSerializer(serializers.ModelSerializer):
    project_count = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            "id", "name", "email", "contact_person", "address",
            "notes", "project_count", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_project_count(self, obj):
        return obj.projects.filter(is_deleted=False).count()


class ProjectSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    total_hours_logged = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Project
        fields = [
            "id", "name", "client", "client_name", "description", "status",
            "color", "default_hourly_rate", "budget_hours", "is_billable",
            "total_hours_logged", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class TimeEntrySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    client_name = serializers.CharField(source="project.client.name", read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.all(), write_only=True,
        source="tags", required=False,
    )
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = TimeEntry
        fields = [
            "id", "user", "project", "project_name", "client_name",
            "date", "hours", "description", "tags", "tag_ids",
            "is_billable", "hourly_rate", "amount",
            "is_paid", "paid_at", "payment",
            "started_at", "stopped_at", "created_at", "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at", "amount", "is_paid", "paid_at", "payment"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class TimeEntryBulkSerializer(serializers.Serializer):
    """Validate and create multiple entries in one request."""
    entries = TimeEntrySerializer(many=True)

    def create(self, validated_data):
        user = self.context["request"].user
        created = []
        for entry_data in validated_data["entries"]:
            tags = entry_data.pop("tags", [])
            entry = TimeEntry.objects.create(user=user, **entry_data)
            if tags:
                entry.tags.set(tags)
            created.append(entry)
        return created


class WeeklySummarySerializer(serializers.Serializer):
    """Read-only summary of a week's entries."""
    week_start = serializers.DateField()
    week_end = serializers.DateField()
    total_hours = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    project_breakdown = serializers.ListField()


class WeeklyReportSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = WeeklyReport
        fields = [
            "id", "user", "week_start", "week_end", "total_hours",
            "sent_at", "email_provider", "recipient_email", "attachment_name",
        ]
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    paid_to = UserSerializer(read_only=True)
    paid_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="paid_to", write_only=True
    )
    paid_by = UserSerializer(read_only=True)
    entry_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=TimeEntry.objects.all(),
        source="entries", write_only=True, required=False,
    )
    entries_summary = serializers.SerializerMethodField()
    document_url = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "paid_to", "paid_to_id", "paid_by",
            "amount", "payment_date", "reference", "status", "notes",
            "document", "document_url", "entry_ids", "entries_summary",
            "created_at", "updated_at",
        ]
        read_only_fields = ["paid_by", "created_at", "updated_at", "document_url"]
        extra_kwargs = {"document": {"write_only": True, "required": False}}

    def get_document_url(self, obj):
        if obj.document:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.document.url) if request else obj.document.url
        return None

    def get_entries_summary(self, obj):
        return [
            {
                "id": str(e.id),
                "date": e.date,
                "hours": float(e.hours),
                "amount": float(e.amount),
                "description": e.description,
                "project": e.project.name,
            }
            for e in obj.entries.filter(is_deleted=False).select_related("project")
        ]

    def create(self, validated_data):
        entries = validated_data.pop("entries", [])
        validated_data["paid_by"] = self.context["request"].user
        payment = super().create(validated_data)
        if entries:
            payment.entries.set(entries)
            payment.entries.filter(is_deleted=False).update(
                is_paid=True, paid_at=payment.payment_date, payment=payment
            )
        return payment

    def update(self, instance, validated_data):
        entries = validated_data.pop("entries", None)
        payment = super().update(instance, validated_data)
        if entries is not None:
            old_entry_ids = set(payment.entries.values_list("id", flat=True))
            new_entry_ids = {e.id for e in entries}
            # Unmark removed entries
            removed = old_entry_ids - new_entry_ids
            TimeEntry.objects.filter(id__in=removed).update(
                is_paid=False, paid_at=None, payment=None
            )
            payment.entries.set(entries)
            payment.entries.filter(is_deleted=False).update(
                is_paid=True, paid_at=payment.payment_date, payment=payment
            )
        return payment
