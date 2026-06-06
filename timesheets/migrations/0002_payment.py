import timesheets.models
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timesheets", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("payment_date", models.DateField()),
                ("reference", models.CharField(blank=True, help_text="Transaction ID / cheque number", max_length=255)),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("disputed", "Disputed")],
                    default="confirmed", max_length=20,
                )),
                ("notes", models.TextField(blank=True)),
                ("document", models.FileField(
                    blank=True, null=True,
                    help_text="Receipt, bank statement, or invoice (PDF/PNG/JPG)",
                    upload_to=timesheets.models.payment_document_path,
                )),
                ("paid_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="payments_made",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("paid_to", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="payments_received",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("entries", models.ManyToManyField(
                    blank=True, related_name="payments", to="timesheets.timeentry"
                )),
            ],
            options={"ordering": ["-payment_date", "-created_at"]},
        ),
        migrations.AddField(
            model_name="timeentry",
            name="is_paid",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="timeentry",
            name="paid_at",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="timeentry",
            name="payment",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="paid_entries",
                to="timesheets.payment",
            ),
        ),
    ]
