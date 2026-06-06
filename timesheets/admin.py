from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import Client, Project, TimeEntry, Tag, UserProfile, WeeklyReport, Payment


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "timezone", "default_hourly_rate", "weekly_report_email"]
    list_filter = ["weekly_report_email", "timezone"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    raw_id_fields = ["user"]


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "contact_person", "project_count", "created_at"]
    search_fields = ["name", "email", "contact_person"]
    readonly_fields = ["created_at", "updated_at"]

    def project_count(self, obj):
        return obj.projects.filter(is_deleted=False).count()

    project_count.short_description = "Projects"


class ProjectMemberInline(admin.TabularInline):
    model = Project.members.through
    extra = 1
    verbose_name = "Team Member"
    verbose_name_plural = "Team Members"


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "name", "client", "status", "color_preview", "is_billable",
        "default_hourly_rate", "total_hours", "created_at",
    ]
    list_filter = ["status", "is_billable", "client"]
    search_fields = ["name", "client__name", "description"]
    readonly_fields = ["created_at", "updated_at", "total_hours"]
    inlines = [ProjectMemberInline]
    exclude = ["members"]

    def color_preview(self, obj):
        return format_html(
            '<span style="background:{};padding:2px 12px;border-radius:3px;">&nbsp;</span>',
            obj.color,
        )

    color_preview.short_description = "Color"

    def total_hours(self, obj):
        return obj.total_hours_logged

    total_hours.short_description = "Total Hours"


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "color_preview"]
    search_fields = ["name"]

    def color_preview(self, obj):
        return format_html(
            '<span style="background:{};padding:2px 12px;border-radius:3px;">&nbsp;</span>',
            obj.color,
        )

    color_preview.short_description = "Color"


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = [
        "user", "project", "date", "hours", "is_billable",
        "hourly_rate", "amount_display", "description_short",
    ]
    list_filter = ["is_billable", "date", "project__client", "project"]
    search_fields = ["user__email", "project__name", "description"]
    readonly_fields = ["created_at", "updated_at", "amount_display"]
    date_hierarchy = "date"
    raw_id_fields = ["user", "project"]
    filter_horizontal = ["tags"]

    def description_short(self, obj):
        return (obj.description[:60] + "…") if len(obj.description) > 60 else obj.description

    description_short.short_description = "Description"

    def amount_display(self, obj):
        return f"${obj.amount:,.2f}"

    amount_display.short_description = "Amount"

    def get_queryset(self, request):
        return self.model.all_objects.all()


class PaymentEntryInline(admin.TabularInline):
    model = Payment.entries.through
    extra = 0
    verbose_name = "Time Entry"
    verbose_name_plural = "Covered Time Entries"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "short_id", "paid_to", "paid_by", "amount", "payment_date",
        "status", "reference", "document_link", "entry_count", "created_at",
    ]
    list_filter = ["status", "payment_date"]
    search_fields = ["paid_to__email", "paid_by__email", "reference", "notes"]
    readonly_fields = ["created_at", "updated_at", "document_link"]
    date_hierarchy = "payment_date"
    raw_id_fields = ["paid_to", "paid_by"]
    filter_horizontal = ["entries"]

    def short_id(self, obj):
        return str(obj.id)[:8].upper()
    short_id.short_description = "ID"

    def document_link(self, obj):
        if obj.document:
            return format_html('<a href="{}" target="_blank">Download ↗</a>', obj.document.url)
        return "—"
    document_link.short_description = "Document"

    def entry_count(self, obj):
        return obj.entries.count()
    entry_count.short_description = "Entries"


@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display = [
        "user", "week_start", "week_end", "total_hours",
        "recipient_email", "email_provider", "sent_at",
    ]
    list_filter = ["email_provider", "week_start"]
    search_fields = ["user__email", "recipient_email"]
    readonly_fields = ["sent_at", "created_at", "updated_at"]
    date_hierarchy = "week_start"
