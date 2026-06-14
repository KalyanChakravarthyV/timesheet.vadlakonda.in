import json
import mimetypes
import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from timesheets.models import Client, Payment, Project, Tag, TimeEntry, WeeklyReport
from timesheets.services.email_service import send_weekly_report
from timesheets.services.excel_export import build_weekly_excel
from .forms import ClientForm, PaymentForm, ProjectForm, TimeEntryForm


# ── Helpers ────────────────────────────────────────────────────────────────────

def _week_bounds(request):
    week_str = request.GET.get("week")
    if week_str:
        try:
            ref = date.fromisoformat(week_str)
        except ValueError:
            ref = date.today()
    else:
        ref = date.today()
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _context_base(request):
    from django.conf import settings
    return {"company_name": settings.COMPANY_NAME}


# ── Auth ───────────────────────────────────────────────────────────────────────

class UILoginView(LoginView):
    template_name = "ui/login.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_context_base(self.request))
        return ctx


class UILogoutView(LogoutView):
    next_page = "ui:login"


# ── Dashboard ─────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    monday, sunday = _week_bounds(request)
    entries = (
        TimeEntry.objects
        .filter(user=request.user, date__gte=monday, date__lte=sunday)
        .select_related("project", "project__client")
    )

    total_hours = entries.aggregate(h=Sum("hours"))["h"] or Decimal("0")
    total_amount = sum(e.amount for e in entries)
    entry_count = entries.count()

    # Per-project breakdown
    project_breakdown = []
    seen = {}
    for e in entries:
        key = str(e.project_id)
        if key not in seen:
            seen[key] = {"project_name": e.project.name,
                         "client_name": e.project.client.name if e.project.client else None,
                         "hours": Decimal("0"), "amount": Decimal("0")}
        seen[key]["hours"] += e.hours
        seen[key]["amount"] += e.amount
    project_breakdown = list(seen.values())

    recent_entries = (
        TimeEntry.objects
        .filter(user=request.user)
        .select_related("project")
        .order_by("-date", "-created_at")[:8]
    )

    if request.user.is_staff:
        projects = Project.objects.filter(is_deleted=False).order_by("name")
    else:
        projects = Project.objects.filter(members=request.user, is_deleted=False).order_by("name")

    ctx = {
        **_context_base(request),
        "week_start": monday,
        "week_end": sunday,
        "prev_week": (monday - timedelta(days=7)).isoformat(),
        "next_week": (monday + timedelta(days=7)).isoformat(),
        "total_hours": total_hours,
        "total_amount": total_amount,
        "project_count": len(project_breakdown),
        "entry_count": entry_count,
        "project_breakdown": project_breakdown,
        "recent_entries": recent_entries,
        "projects": projects,
        "today": date.today().isoformat(),
    }
    return render(request, "ui/dashboard.html", ctx)


# ── Time Entries ───────────────────────────────────────────────────────────────

@login_required
def entry_list(request):
    qs = TimeEntry.objects.filter(user=request.user).select_related("project", "project__client").prefetch_related("tags")

    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    project_id = request.GET.get("project")

    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if project_id:
        qs = qs.filter(project_id=project_id)

    entries = qs.order_by("-date", "-created_at")
    total_hours = entries.aggregate(h=Sum("hours"))["h"] or Decimal("0")
    total_amount = sum(e.amount for e in entries)

    if request.user.is_staff:
        projects = Project.objects.filter(is_deleted=False).order_by("name")
    else:
        projects = Project.objects.filter(members=request.user, is_deleted=False).order_by("name")

    today_d = date.today()
    week_mon = today_d - timedelta(days=today_d.weekday())
    week_sun = week_mon + timedelta(days=6)
    this_week_qs = (
        TimeEntry.objects
        .filter(user=request.user, date__gte=week_mon, date__lte=week_sun)
        .select_related("project", "project__client")
        .order_by("-date", "-created_at")
    )
    this_week_json = json.dumps([
        {
            "date": e.date.isoformat(),
            "date_display": e.date.strftime("%d %b"),
            "project_name": e.project.name,
            "client_name": e.project.client.name if e.project.client else "",
            "hours": float(e.hours),
            "amount": float(e.amount),
        }
        for e in this_week_qs
    ])

    return render(request, "ui/entries.html", {
        **_context_base(request),
        "entries": entries,
        "projects": projects,
        "total_hours": total_hours,
        "total_amount": total_amount,
        "this_week_json": this_week_json,
        "week_start": week_mon,
        "week_end": week_sun,
    })


@login_required
def entry_add(request):
    if request.user.is_staff:
        projects = Project.objects.filter(is_deleted=False).order_by("name")
    else:
        projects = Project.objects.filter(members=request.user, is_deleted=False).order_by("name")

    if request.method == "POST":
        form = TimeEntryForm(request.user, request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            form.save_m2m()
            # HTMX quick-log response
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    '<p class="text-green-600 font-medium">✓ Logged successfully!</p>'
                )
            messages.success(request, f"Logged {entry.hours}h on {entry.project.name}.")
            if request.POST.get("redirect_to") == "dashboard":
                return redirect("ui:dashboard")
            return redirect("ui:entry_list")
        if request.headers.get("HX-Request"):
            return HttpResponse('<p class="text-red-600">Please fix errors and try again.</p>')
    else:
        initial = {"date": date.today(), "is_billable": True}
        form = TimeEntryForm(request.user, initial=initial)

    return render(request, "ui/entry_form.html", {
        **_context_base(request),
        "form": form,
        "projects": projects,
        "tags": Tag.objects.all(),
        "selected_tag_ids": [],
        "today": date.today().isoformat(),
    })


@login_required
def entry_edit(request, pk):
    entry = get_object_or_404(TimeEntry, pk=pk, user=request.user)

    if request.user.is_staff:
        projects = Project.objects.filter(is_deleted=False).order_by("name")
    else:
        projects = Project.objects.filter(members=request.user, is_deleted=False).order_by("name")

    if request.method == "POST":
        form = TimeEntryForm(request.user, request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, "Entry updated.")
            return redirect("ui:entry_list")
    else:
        form = TimeEntryForm(request.user, instance=entry)

    return render(request, "ui/entry_form.html", {
        **_context_base(request),
        "form": form,
        "entry": entry,
        "projects": projects,
        "tags": Tag.objects.all(),
        "selected_tag_ids": list(entry.tags.values_list("id", flat=True)),
        "today": date.today().isoformat(),
    })


@login_required
@require_http_methods(["DELETE"])
def entry_delete(request, pk):
    entry = get_object_or_404(TimeEntry, pk=pk, user=request.user)
    entry.soft_delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")  # removes the row
    messages.success(request, "Entry deleted.")
    return redirect("ui:entry_list")


# ── Projects ──────────────────────────────────────────────────────────────────

@login_required
def project_list(request):
    if request.user.is_staff:
        projects = Project.objects.filter(is_deleted=False).select_related("client").order_by("name")
    else:
        projects = Project.objects.filter(members=request.user, is_deleted=False).select_related("client").order_by("name")
    return render(request, "ui/projects.html", {**_context_base(request), "projects": projects})


@login_required
def project_add(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            project.members.add(request.user)
            messages.success(request, f'Project "{project.name}" created.')
            return redirect("ui:project_list")
    else:
        form = ProjectForm(initial={"color": "#3B82F6", "status": "active", "is_billable": True})

    return render(request, "ui/project_form.html", {
        **_context_base(request),
        "form": form,
        "clients": Client.objects.filter(is_deleted=False).order_by("name"),
        "status_choices": Project.Status.choices,
    })


@login_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk, is_deleted=False)
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Project updated.")
            return redirect("ui:project_list")
    else:
        form = ProjectForm(instance=project)

    return render(request, "ui/project_form.html", {
        **_context_base(request),
        "form": form,
        "project": project,
        "clients": Client.objects.filter(is_deleted=False).order_by("name"),
        "status_choices": Project.Status.choices,
    })


# ── Clients ───────────────────────────────────────────────────────────────────

@login_required
def client_list(request):
    clients = Client.objects.filter(is_deleted=False).order_by("name")
    for c in clients:
        c.project_count = c.projects.filter(is_deleted=False).count()
    return render(request, "ui/clients.html", {**_context_base(request), "clients": clients})


@login_required
def client_add(request):
    if request.method == "POST":
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Client "{client.name}" created.')
            return redirect("ui:client_list")
    else:
        form = ClientForm()
    return render(request, "ui/client_form.html", {**_context_base(request), "form": form})


@login_required
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk, is_deleted=False)
    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, "Client updated.")
            return redirect("ui:client_list")
    else:
        form = ClientForm(instance=client)
    return render(request, "ui/client_form.html", {**_context_base(request), "form": form, "client": client})


# ── Weekly Report ─────────────────────────────────────────────────────────────

@login_required
def weekly_report(request):
    from django.conf import settings
    monday, sunday = _week_bounds(request)

    entries = list(
        TimeEntry.objects
        .filter(user=request.user, date__gte=monday, date__lte=sunday)
        .select_related("project", "project__client")
        .order_by("date", "project__name")
    )

    total_hours = sum(e.hours for e in entries)
    total_amount = sum(e.amount for e in entries)

    seen = {}
    for e in entries:
        key = str(e.project_id)
        if key not in seen:
            seen[key] = {"project_name": e.project.name,
                         "client_name": e.project.client.name if e.project.client else None,
                         "hours": Decimal("0"), "amount": Decimal("0")}
        seen[key]["hours"] += e.hours
        seen[key]["amount"] += e.amount

    past_reports = WeeklyReport.objects.filter(user=request.user).order_by("-week_start")[:5]

    return render(request, "ui/weekly_report.html", {
        **_context_base(request),
        "week_start": monday,
        "week_end": sunday,
        "prev_week": (monday - timedelta(days=7)).isoformat(),
        "next_week": (monday + timedelta(days=7)).isoformat(),
        "entries": entries,
        "total_hours": total_hours,
        "total_amount": total_amount,
        "project_count": len(seen),
        "project_breakdown": list(seen.values()),
        "past_reports": past_reports,
        "email_provider": settings.EMAIL_PROVIDER,
    })


@login_required
def weekly_export(request):
    monday, sunday = _week_bounds(request)
    entries = list(
        TimeEntry.objects
        .filter(user=request.user, date__gte=monday, date__lte=sunday)
        .select_related("project", "project__client")
        .prefetch_related("tags")
        .order_by("date", "project__name")
    )
    wb_bytes = build_weekly_excel(request.user, entries, monday, sunday)
    filename = f"timesheet_{monday.strftime('%Y-%m-%d')}.xlsx"
    response = HttpResponse(
        wb_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def weekly_send(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    week_str = data.get("week")
    if week_str:
        try:
            ref = date.fromisoformat(week_str)
        except ValueError:
            ref = date.today()
    else:
        ref = date.today()

    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    recipient = data.get("email") or request.user.email

    entries = list(
        TimeEntry.objects
        .filter(user=request.user, date__gte=monday, date__lte=sunday)
        .select_related("project", "project__client")
        .prefetch_related("tags")
    )

    result = send_weekly_report(
        user=request.user, entries=entries,
        week_start=monday, week_end=sunday,
        recipient_email=recipient,
    )
    if result["success"]:
        return JsonResponse({"message": "Sent!", "provider": result["provider"]})
    return JsonResponse({"error": result.get("error", "Failed to send.")}, status=500)


# ── Payments ──────────────────────────────────────────────────────────────────

@login_required
def payment_list(request):
    if request.user.is_staff:
        payments = Payment.objects.select_related("paid_to", "paid_by").all()
    else:
        payments = Payment.objects.select_related("paid_to", "paid_by").filter(paid_to=request.user)
    total_paid = sum(p.amount for p in payments)
    return render(request, "ui/payments.html", {
        **_context_base(request),
        "payments": payments,
        "total_paid": total_paid,
    })


@login_required
def payment_add(request):
    from django.conf import settings

    if request.user.is_staff:
        users = User.objects.filter(is_active=True).order_by("first_name", "email")
        target_user_id = request.GET.get("for_user") or request.POST.get("paid_to")
        if target_user_id:
            try:
                target_user_id = int(target_user_id)
                unpaid_entries = (
                    TimeEntry.objects
                    .filter(user_id=target_user_id, is_paid=False, is_deleted=False)
                    .select_related("project")
                    .order_by("-date")
                )
            except (ValueError, TypeError):
                unpaid_entries = TimeEntry.objects.none()
        else:
            unpaid_entries = (
                TimeEntry.objects
                .filter(is_paid=False, is_deleted=False)
                .select_related("project", "user")
                .order_by("-date")
            )
    else:
        users = User.objects.filter(pk=request.user.pk)
        unpaid_entries = (
            TimeEntry.objects
            .filter(user=request.user, is_paid=False, is_deleted=False)
            .select_related("project")
            .order_by("-date")
        )

    entries_list = list(unpaid_entries)
    entry_choices = [
        (
            str(e.id),
            f"{e.date} | {e.project.name} | {e.hours}h | ${e.amount:.2f}"
            + (f" | {e.description[:40]}" if e.description else ""),
        )
        for e in entries_list
    ]
    entries_for_js = [
        {
            "id": str(e.id),
            "project": e.project.name,
            "date": e.date.isoformat(),
            "description": e.description or "",
            "hours": float(e.hours),
            "amount": float(e.amount),
        }
        for e in entries_list
    ]
    unique_projects = sorted({e["project"] for e in entries_for_js})
    unpaid_entries_json = json.dumps(entries_for_js)

    if request.method == "POST":
        form = PaymentForm(request.POST, request.FILES)
        form.fields["entry_ids"].choices = entry_choices
        if form.is_valid():
            entry_ids = form.cleaned_data.get("entry_ids", [])
            entries_qs = TimeEntry.objects.filter(id__in=entry_ids, is_deleted=False)
            payment = Payment.objects.create(
                paid_by=request.user,
                paid_to=form.cleaned_data["paid_to"],
                amount=form.cleaned_data["amount"],
                payment_date=form.cleaned_data["payment_date"],
                reference=form.cleaned_data.get("reference", ""),
                status=form.cleaned_data["status"],
                notes=form.cleaned_data.get("notes", ""),
                document=form.cleaned_data.get("document"),
            )
            if entry_ids:
                payment.entries.set(entries_qs)
                entries_qs.update(
                    is_paid=True,
                    paid_at=payment.payment_date,
                    payment=payment,
                )
            messages.success(request, f"Payment of ${payment.amount} recorded successfully.")
            return redirect("ui:payment_detail", pk=payment.pk)
    else:
        form = PaymentForm(initial={"payment_date": date.today(), "status": "confirmed"})
        form.fields["entry_ids"].choices = entry_choices

    return render(request, "ui/payment_form.html", {
        **_context_base(request),
        "form": form,
        "users": users,
        "entries_for_js": entries_for_js,
        "unique_projects": unique_projects,
        "total_unpaid": len(entries_list),
    })


@login_required
def payment_detail(request, pk):
    if request.user.is_staff:
        payment = get_object_or_404(Payment, pk=pk)
    else:
        payment = get_object_or_404(Payment, pk=pk, paid_to=request.user)
    entries = payment.entries.filter(is_deleted=False).select_related("project")
    total_hours = sum(e.hours for e in entries)
    total_amount = sum(e.amount for e in entries)
    return render(request, "ui/payment_detail.html", {
        **_context_base(request),
        "payment": payment,
        "entries": entries,
        "total_hours": total_hours,
        "total_amount": total_amount,
    })


@login_required
def payment_document(request, pk):
    from django.conf import settings
    if request.user.is_staff:
        payment = get_object_or_404(Payment, pk=pk)
    else:
        payment = get_object_or_404(Payment, pk=pk, paid_to=request.user)

    if not payment.document:
        raise Http404

    file_path = os.path.join(settings.MEDIA_ROOT, payment.document.name)
    if not os.path.exists(file_path):
        raise Http404

    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"
    filename = os.path.basename(payment.document.name)

    with open(file_path, "rb") as f:
        response = HttpResponse(f.read(), content_type=mime_type)
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
