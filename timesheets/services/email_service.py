"""Send weekly timesheet emails via SendGrid or Resend.

Selection is controlled by the EMAIL_PROVIDER setting (sendgrid | resend).
Falls back to the other provider automatically if the primary call fails.
"""

import base64
import logging
from datetime import date
from decimal import Decimal
from typing import Literal

from django.conf import settings
from django.template.loader import render_to_string

from .excel_export import build_entries_excel, build_weekly_excel
from ..models import WeeklyReport

logger = logging.getLogger(__name__)


def send_weekly_report(
    user,
    entries: list,
    week_start: date,
    week_end: date,
    recipient_email: str | None = None,
) -> dict:
    """
    Build the Excel workbook, render the HTML email, and dispatch via the
    configured provider. Returns {"success": True, "provider": "..."} or
    {"success": False, "error": "..."}.
    """
    recipient = recipient_email or user.email
    if not recipient:
        return {"success": False, "error": "No recipient email address available."}

    total_hours = sum(e.hours for e in entries)
    total_amount = sum(e.amount for e in entries)
    filename = f"timesheet_{week_start.strftime('%Y-%m-%d')}.xlsx"

    workbook_bytes = build_weekly_excel(user, entries, week_start, week_end)

    # Build per-project summary for the email body
    project_summary: dict[str, dict] = {}
    for entry in entries:
        key = entry.project.name
        if key not in project_summary:
            project_summary[key] = {
                "name": key,
                "client": entry.project.client.name if entry.project.client else "—",
                "hours": Decimal("0"),
                "amount": Decimal("0"),
            }
        project_summary[key]["hours"] += entry.hours
        project_summary[key]["amount"] += entry.amount

    context = {
        "user": user,
        "week_start": week_start,
        "week_end": week_end,
        "total_hours": total_hours,
        "total_amount": total_amount,
        "project_summary": list(project_summary.values()),
        "company_name": settings.COMPANY_NAME,
        "filename": filename,
    }

    subject = (
        f"Timesheet — week of {week_start.strftime('%d %b %Y')} "
        f"({total_hours:.2f}h)"
    )
    html_body = render_to_string("email/weekly_report.html", context)
    text_body = render_to_string("email/weekly_report.txt", context)

    provider = settings.EMAIL_PROVIDER
    result = _dispatch(
        provider=provider,
        recipient=recipient,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        attachment_bytes=workbook_bytes,
        filename=filename,
    )

    if not result["success"] and provider == "sendgrid":
        logger.warning("SendGrid failed, retrying with Resend: %s", result.get("error"))
        result = _dispatch(
            provider="resend",
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            attachment_bytes=workbook_bytes,
            filename=filename,
        )
    elif not result["success"] and provider == "resend":
        logger.warning("Resend failed, retrying with SendGrid: %s", result.get("error"))
        result = _dispatch(
            provider="sendgrid",
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            attachment_bytes=workbook_bytes,
            filename=filename,
        )

    if result["success"]:
        WeeklyReport.objects.update_or_create(
            user=user,
            week_start=week_start,
            defaults={
                "week_end": week_end,
                "total_hours": total_hours,
                "email_provider": result["provider"],
                "recipient_email": recipient,
                "attachment_name": filename,
            },
        )

    return result


def send_entries_report(
    user,
    entries: list,
    date_from: date | None = None,
    date_to: date | None = None,
    recipient_email: str | None = None,
) -> dict:
    """
    Build an Excel workbook for arbitrary-range entries, render the email, and
    dispatch via the configured provider. Returns {"success": True, "provider": "..."}.
    """
    recipient = recipient_email or user.email
    if not recipient:
        return {"success": False, "error": "No recipient email address available."}

    total_hours = sum(e.hours for e in entries)
    total_amount = sum(e.amount for e in entries)

    if date_from and date_to:
        range_label = f"{date_from.strftime('%Y-%m-%d')}_{date_to.strftime('%Y-%m-%d')}"
    elif date_from:
        range_label = f"from_{date_from.strftime('%Y-%m-%d')}"
    elif date_to:
        range_label = f"to_{date_to.strftime('%Y-%m-%d')}"
    else:
        range_label = "all"
    filename = f"entries_{range_label}.xlsx"

    workbook_bytes = build_entries_excel(user, entries, date_from, date_to)

    project_summary: dict[str, dict] = {}
    for entry in entries:
        key = entry.project.name
        if key not in project_summary:
            project_summary[key] = {
                "name": key,
                "client": entry.project.client.name if entry.project.client else "—",
                "hours": Decimal("0"),
                "amount": Decimal("0"),
            }
        project_summary[key]["hours"] += entry.hours
        project_summary[key]["amount"] += entry.amount

    context = {
        "user": user,
        "date_from": date_from,
        "date_to": date_to,
        "total_hours": total_hours,
        "total_amount": total_amount,
        "project_summary": list(project_summary.values()),
        "company_name": settings.COMPANY_NAME,
        "filename": filename,
    }

    if date_from and date_to:
        date_range_str = f"{date_from.strftime('%d %b %Y')} – {date_to.strftime('%d %b %Y')}"
    elif date_from:
        date_range_str = f"from {date_from.strftime('%d %b %Y')}"
    elif date_to:
        date_range_str = f"up to {date_to.strftime('%d %b %Y')}"
    else:
        date_range_str = "all time"

    subject = f"Time Entries — {date_range_str} ({total_hours:.2f}h)"
    html_body = render_to_string("email/entries_report.html", context)
    text_body = render_to_string("email/entries_report.txt", context)

    provider = settings.EMAIL_PROVIDER
    result = _dispatch(
        provider=provider,
        recipient=recipient,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        attachment_bytes=workbook_bytes,
        filename=filename,
    )

    if not result["success"] and provider == "sendgrid":
        logger.warning("SendGrid failed, retrying with Resend: %s", result.get("error"))
        result = _dispatch(
            provider="resend",
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            attachment_bytes=workbook_bytes,
            filename=filename,
        )
    elif not result["success"] and provider == "resend":
        logger.warning("Resend failed, retrying with SendGrid: %s", result.get("error"))
        result = _dispatch(
            provider="sendgrid",
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            attachment_bytes=workbook_bytes,
            filename=filename,
        )

    return result


def _dispatch(
    provider: str,
    recipient: str,
    subject: str,
    html_body: str,
    text_body: str,
    attachment_bytes: bytes,
    filename: str,
) -> dict:
    if provider == "sendgrid":
        return _send_sendgrid(recipient, subject, html_body, text_body, attachment_bytes, filename)
    if provider == "resend":
        return _send_resend(recipient, subject, html_body, attachment_bytes, filename)
    return {"success": False, "error": f"Unknown provider: {provider}"}


def _send_sendgrid(
    recipient: str,
    subject: str,
    html_body: str,
    text_body: str,
    attachment_bytes: bytes,
    filename: str,
) -> dict:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (
            Attachment, ContentId, Disposition,
            FileContent, FileName, FileType, Mail,
        )

        api_key = settings.SENDGRID_API_KEY
        from_email = settings.SENDGRID_FROM_EMAIL
        from_name = settings.SENDGRID_FROM_NAME

        if not api_key or not from_email:
            return {"success": False, "error": "SendGrid not configured (missing API key or from email)."}

        message = Mail(
            from_email=(from_email, from_name),
            to_emails=recipient,
            subject=subject,
            plain_text_content=text_body,
            html_content=html_body,
        )

        encoded = base64.b64encode(attachment_bytes).decode()
        attachment = Attachment(
            FileContent(encoded),
            FileName(filename),
            FileType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            Disposition("attachment"),
        )
        message.attachment = attachment

        client = SendGridAPIClient(api_key)
        response = client.send(message)

        if response.status_code in (200, 202):
            return {"success": True, "provider": "sendgrid"}
        return {
            "success": False,
            "error": f"SendGrid returned status {response.status_code}: {response.body}",
        }

    except Exception as exc:
        logger.exception("SendGrid error")
        return {"success": False, "error": str(exc)}


def _send_resend(
    recipient: str,
    subject: str,
    html_body: str,
    attachment_bytes: bytes,
    filename: str,
) -> dict:
    try:
        import resend

        api_key = settings.RESEND_API_KEY
        from_email = settings.RESEND_FROM_EMAIL

        if not api_key or not from_email:
            return {"success": False, "error": "Resend not configured (missing API key or from email)."}

        resend.api_key = api_key

        params: resend.Emails.SendParams = {
            "from": from_email,
            "to": [recipient],
            "subject": subject,
            "html": html_body,
            "attachments": [
                {
                    "filename": filename,
                    "content": list(attachment_bytes),
                }
            ],
        }

        response = resend.Emails.send(params)

        if response.get("id"):
            return {"success": True, "provider": "resend"}
        return {"success": False, "error": f"Resend error: {response}"}

    except Exception as exc:
        logger.exception("Resend error")
        return {"success": False, "error": str(exc)}
