from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.utils import timezone

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .filters import TimeEntryFilter, ProjectFilter
from .models import Client, Project, TimeEntry, Tag, UserProfile, WeeklyReport, Payment
from .serializers import (
    ClientSerializer, ProjectSerializer, TimeEntrySerializer,
    TimeEntryBulkSerializer, TagSerializer, UserProfileSerializer,
    WeeklySummarySerializer, WeeklyReportSerializer, PaymentSerializer,
)
from .services.excel_export import build_weekly_excel
from .services.email_service import send_weekly_report


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Client.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = ProjectFilter
    search_fields = ["name", "client__name", "description"]
    ordering_fields = ["name", "created_at", "status"]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Project.objects.select_related("client").all()
        return Project.objects.select_related("client").filter(members=user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TimeEntryViewSet(viewsets.ModelViewSet):
    serializer_class = TimeEntrySerializer
    permission_classes = [IsAuthenticated]
    filterset_class = TimeEntryFilter
    search_fields = ["description", "project__name"]
    ordering_fields = ["date", "hours", "created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = TimeEntry.objects.select_related("user", "project", "project__client").prefetch_related("tags")
        if not user.is_staff:
            qs = qs.filter(user=user)
        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_create(self, request):
        serializer = TimeEntryBulkSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        entries = serializer.save()
        return Response(
            TimeEntrySerializer(entries, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="summary/weekly")
    def weekly_summary(self, request):
        """Return aggregated totals for a given week (defaults to current week)."""
        week_str = request.query_params.get("week")
        if week_str:
            try:
                ref_date = date.fromisoformat(week_str)
            except ValueError:
                return Response({"error": "week must be YYYY-MM-DD"}, status=400)
        else:
            ref_date = date.today()

        monday = ref_date - timedelta(days=ref_date.weekday())
        sunday = monday + timedelta(days=6)

        qs = self.get_queryset().filter(date__gte=monday, date__lte=sunday)

        totals = qs.aggregate(
            total_hours=Sum("hours"),
            total_amount=Sum("hours"),  # placeholder — computed below
        )
        total_hours = totals["total_hours"] or Decimal("0.00")

        # Per-project breakdown
        breakdown = []
        for project_id in qs.values_list("project", flat=True).distinct():
            project_entries = qs.filter(project_id=project_id)
            project = project_entries.first().project
            ph = project_entries.aggregate(h=Sum("hours"))["h"] or Decimal("0.00")
            pa = sum(e.amount for e in project_entries)
            breakdown.append({
                "project_id": str(project.id),
                "project_name": project.name,
                "client_name": project.client.name if project.client else None,
                "hours": float(ph),
                "amount": float(pa),
            })

        total_amount = sum(b["amount"] for b in breakdown)

        return Response({
            "week_start": monday.isoformat(),
            "week_end": sunday.isoformat(),
            "total_hours": float(total_hours),
            "total_amount": total_amount,
            "project_breakdown": breakdown,
        })

    @action(detail=False, methods=["get"], url_path="export/weekly")
    def export_weekly_excel(self, request):
        """Stream a weekly Excel file for the authenticated user."""
        week_str = request.query_params.get("week")
        if week_str:
            try:
                ref_date = date.fromisoformat(week_str)
            except ValueError:
                return Response({"error": "week must be YYYY-MM-DD"}, status=400)
        else:
            ref_date = date.today()

        monday = ref_date - timedelta(days=ref_date.weekday())
        sunday = monday + timedelta(days=6)

        entries = (
            TimeEntry.objects
            .filter(user=request.user, date__gte=monday, date__lte=sunday, is_deleted=False)
            .select_related("project", "project__client")
            .prefetch_related("tags")
            .order_by("date", "project__name")
        )

        workbook_bytes = build_weekly_excel(request.user, entries, monday, sunday)
        filename = f"timesheet_{monday.strftime('%Y-%m-%d')}.xlsx"

        response = HttpResponse(
            workbook_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=["post"], url_path="send/weekly")
    def send_weekly_email(self, request):
        """Trigger a weekly timesheet email for the authenticated user."""
        week_str = request.data.get("week")
        recipient = request.data.get("email", request.user.email)

        if week_str:
            try:
                ref_date = date.fromisoformat(week_str)
            except ValueError:
                return Response({"error": "week must be YYYY-MM-DD"}, status=400)
        else:
            ref_date = date.today()

        monday = ref_date - timedelta(days=ref_date.weekday())
        sunday = monday + timedelta(days=6)

        entries = (
            TimeEntry.objects
            .filter(user=request.user, date__gte=monday, date__lte=sunday, is_deleted=False)
            .select_related("project", "project__client")
            .prefetch_related("tags")
            .order_by("date", "project__name")
        )

        result = send_weekly_report(
            user=request.user,
            entries=list(entries),
            week_start=monday,
            week_end=sunday,
            recipient_email=recipient,
        )

        if result["success"]:
            return Response({"message": "Weekly report sent successfully.", "provider": result["provider"]})
        return Response({"error": result["error"]}, status=500)


class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]
    queryset = Tag.objects.all()
    search_fields = ["name"]


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class WeeklyReportListView(generics.ListAPIView):
    serializer_class = WeeklyReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return WeeklyReport.objects.select_related("user").all()
        return WeeklyReport.objects.filter(user=user)


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["reference", "notes", "paid_to__email"]
    ordering_fields = ["payment_date", "amount", "created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = Payment.objects.select_related("paid_to", "paid_by").prefetch_related("entries")
        if not user.is_staff:
            qs = qs.filter(paid_to=user)
        return qs

    def get_parsers(self):
        # Accept multipart (file upload) and JSON
        from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
        return [MultiPartParser(), FormParser(), JSONParser()]

    def destroy(self, request, *args, **kwargs):
        payment = self.get_object()
        # Unmark all covered entries before deleting
        payment.entries.filter(is_deleted=False).update(
            is_paid=False, paid_at=None, payment=None
        )
        payment.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="unpaid-entries")
    def unpaid_entries(self, request):
        """List all unpaid entries for the current user — used to build payment form."""
        user = request.user
        qs = (
            TimeEntry.objects
            .filter(user=user, is_paid=False, is_deleted=False)
            .select_related("project", "project__client")
            .order_by("-date")
        )
        return Response(TimeEntrySerializer(qs, many=True, context={"request": request}).data)
