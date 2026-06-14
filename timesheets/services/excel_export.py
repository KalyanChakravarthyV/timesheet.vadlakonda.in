"""Build a styled weekly timesheet Excel workbook using openpyxl."""

import io
from collections import defaultdict
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Side, numbers,
)
from openpyxl.utils import get_column_letter

# ── Palette ────────────────────────────────────────────────────────────────────
COLOR_HEADER_BG = "1E3A5F"   # deep navy
COLOR_HEADER_FG = "FFFFFF"
COLOR_SECTION_BG = "2563EB"  # blue
COLOR_SECTION_FG = "FFFFFF"
COLOR_SUBTOTAL_BG = "EFF6FF"
COLOR_TOTAL_BG = "DBEAFE"
COLOR_ALT_ROW = "F8FAFC"
COLOR_BORDER = "CBD5E1"

thin = Side(style="thin", color=COLOR_BORDER)
thick = Side(style="medium", color="94A3B8")
BORDER_THIN = Border(left=thin, right=thin, top=thin, bottom=thin)
BORDER_THICK = Border(left=thick, right=thick, top=thick, bottom=thick)


def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)


def _font(bold=False, size=11, color="000000") -> Font:
    return Font(name="Calibri", bold=bold, size=size, color=color)


def _align(h="left", v="center", wrap=False) -> Alignment:
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)


def build_entries_excel(
    user,
    entries,
    date_from: date | None = None,
    date_to: date | None = None,
) -> bytes:
    """Return raw bytes of a .xlsx workbook for an arbitrary set of time entries."""
    dates = [e.date for e in entries] if entries else []
    d_from = date_from or (min(dates) if dates else date.today())
    d_to = date_to or (max(dates) if dates else date.today())
    return build_weekly_excel(user, entries, d_from, d_to)


def build_weekly_excel(
    user,
    entries,
    week_start: date,
    week_end: date,
) -> bytes:
    """Return raw bytes of a .xlsx workbook summarising the given time entries."""

    wb = Workbook()

    _build_summary_sheet(wb.active, user, entries, week_start, week_end)
    _build_detail_sheet(wb.create_sheet("Daily Detail"), user, entries, week_start, week_end)
    _build_project_sheet(wb.create_sheet("By Project"), entries)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Summary sheet ──────────────────────────────────────────────────────────────

def _build_summary_sheet(ws, user, entries, week_start, week_end):
    ws.title = "Weekly Summary"
    ws.sheet_view.showGridLines = False

    # Column widths
    col_widths = [3, 22, 28, 14, 14, 14, 14, 3]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── Header banner ─────────────────────────────────────────────────────────
    ws.merge_cells("B1:G1")
    ws["B1"] = "WEEKLY TIMESHEET"
    ws["B1"].font = _font(bold=True, size=18, color=COLOR_HEADER_FG)
    ws["B1"].fill = _fill(COLOR_HEADER_BG)
    ws["B1"].alignment = _align("center")
    ws.row_dimensions[1].height = 36

    ws.merge_cells("B2:G2")
    full_name = user.get_full_name() or user.email
    ws["B2"] = (
        f"{full_name}  |  "
        f"{week_start.strftime('%d %b %Y')} – {week_end.strftime('%d %b %Y')}"
    )
    ws["B2"].font = _font(size=12, color=COLOR_HEADER_FG)
    ws["B2"].fill = _fill(COLOR_HEADER_BG)
    ws["B2"].alignment = _align("center")
    ws.row_dimensions[2].height = 22

    # ── Column headings ───────────────────────────────────────────────────────
    headers = ["Date", "Project", "Client", "Hours", "Rate", "Amount", "Billable"]
    row = 4
    for col, h in enumerate(headers, 2):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = _font(bold=True, size=11, color=COLOR_SECTION_FG)
        cell.fill = _fill(COLOR_SECTION_BG)
        cell.alignment = _align("center")
        cell.border = BORDER_THIN
    ws.row_dimensions[row].height = 20

    # ── Data rows ─────────────────────────────────────────────────────────────
    total_hours = Decimal("0")
    total_amount = Decimal("0")
    row = 5

    sorted_entries = sorted(entries, key=lambda e: (e.date, e.project.name))

    for idx, entry in enumerate(sorted_entries):
        bg = COLOR_ALT_ROW if idx % 2 else "FFFFFF"
        row_data = [
            entry.date.strftime("%a %d %b"),
            entry.project.name,
            entry.project.client.name if entry.project.client else "—",
            float(entry.hours),
            float(entry.hourly_rate or 0),
            float(entry.amount),
            "Yes" if entry.is_billable else "No",
        ]
        for col, val in enumerate(row_data, 2):
            cell = ws.cell(row=row, column=col, value=val)
            cell.font = _font(size=10)
            cell.fill = _fill(bg)
            cell.border = BORDER_THIN
            cell.alignment = _align("center" if col in (2, 5, 7, 8) else "left")
            if col in (5, 6):  # rate, amount
                cell.number_format = '"$"#,##0.00'
            if col == 4:       # hours
                cell.number_format = "0.00"
        ws.row_dimensions[row].height = 18
        total_hours += entry.hours
        total_amount += entry.amount
        row += 1

    # ── Totals row ────────────────────────────────────────────────────────────
    ws.merge_cells(f"B{row}:D{row}")
    tc = ws.cell(row=row, column=2, value="TOTAL")
    tc.font = _font(bold=True, size=11, color="1E3A5F")
    tc.fill = _fill(COLOR_TOTAL_BG)
    tc.alignment = _align("right")
    tc.border = BORDER_THICK

    hours_cell = ws.cell(row=row, column=5, value=float(total_hours))
    hours_cell.font = _font(bold=True)
    hours_cell.fill = _fill(COLOR_TOTAL_BG)
    hours_cell.number_format = "0.00"
    hours_cell.border = BORDER_THICK

    ws.cell(row=row, column=6)  # rate — blank
    amount_cell = ws.cell(row=row, column=7, value=float(total_amount))
    amount_cell.font = _font(bold=True)
    amount_cell.fill = _fill(COLOR_TOTAL_BG)
    amount_cell.number_format = '"$"#,##0.00'
    amount_cell.border = BORDER_THICK

    ws.row_dimensions[row].height = 22

    # ── Auto-filter ───────────────────────────────────────────────────────────
    ws.auto_filter.ref = f"B4:H{row - 1}"

    # ── Freeze panes below header ─────────────────────────────────────────────
    ws.freeze_panes = "B5"


# ── Daily detail sheet ─────────────────────────────────────────────────────────

def _build_detail_sheet(ws, user, entries, week_start, week_end):
    ws.sheet_view.showGridLines = False

    col_widths = [3, 16, 28, 38, 10, 10, 10, 10, 3]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Title
    ws.merge_cells("B1:H1")
    ws["B1"] = f"Daily Detail — {week_start.strftime('%d %b')} to {week_end.strftime('%d %b %Y')}"
    ws["B1"].font = _font(bold=True, size=14, color=COLOR_HEADER_FG)
    ws["B1"].fill = _fill(COLOR_HEADER_BG)
    ws["B1"].alignment = _align("center")
    ws.row_dimensions[1].height = 30

    headers = ["Date", "Project", "Description", "Tags", "Hours", "Rate", "Amount", "Billable"]
    row = 3
    for col, h in enumerate(headers, 2):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = _font(bold=True, color=COLOR_SECTION_FG)
        cell.fill = _fill(COLOR_SECTION_BG)
        cell.alignment = _align("center")
        cell.border = BORDER_THIN

    row = 4
    sorted_entries = sorted(entries, key=lambda e: (e.date, e.project.name))

    # Group by date
    by_date = defaultdict(list)
    for e in sorted_entries:
        by_date[e.date].append(e)

    for day_date, day_entries in sorted(by_date.items()):
        day_label = day_date.strftime("%A\n%d %b")
        first_row = row

        for idx, entry in enumerate(day_entries):
            bg = COLOR_ALT_ROW if idx % 2 else "FFFFFF"
            tag_str = ", ".join(t.name for t in entry.tags.all())
            row_data = [
                day_label if idx == 0 else None,
                entry.project.name,
                entry.description or "—",
                tag_str or "—",
                float(entry.hours),
                float(entry.hourly_rate or 0),
                float(entry.amount),
                "Yes" if entry.is_billable else "No",
            ]
            for col, val in enumerate(row_data, 2):
                cell = ws.cell(row=row, column=col, value=val)
                cell.font = _font(size=10)
                cell.fill = _fill(bg)
                cell.border = BORDER_THIN
                cell.alignment = _align(wrap=True)
                if col in (6, 7):
                    cell.number_format = '"$"#,##0.00'
                if col == 5:
                    cell.number_format = "0.00"
            ws.row_dimensions[row].height = 30
            row += 1

        # Day subtotal
        day_hours = sum(e.hours for e in day_entries)
        day_amount = sum(e.amount for e in day_entries)
        ws.merge_cells(f"B{row}:E{row}")
        sc = ws.cell(row=row, column=2, value=f"Day total — {day_date.strftime('%A')}")
        sc.font = _font(bold=True, size=10, color="1E3A5F")
        sc.fill = _fill(COLOR_SUBTOTAL_BG)
        sc.border = BORDER_THIN
        ws.cell(row=row, column=6, value=float(day_hours)).number_format = "0.00"
        ws.cell(row=row, column=7).fill = _fill(COLOR_SUBTOTAL_BG)
        amt_cell = ws.cell(row=row, column=8, value=float(day_amount))
        amt_cell.number_format = '"$"#,##0.00'
        amt_cell.fill = _fill(COLOR_SUBTOTAL_BG)
        for col in range(2, 10):
            ws.cell(row=row, column=col).border = BORDER_THIN
        row += 1

    ws.freeze_panes = "B4"


# ── By-project sheet ───────────────────────────────────────────────────────────

def _build_project_sheet(ws, entries):
    ws.sheet_view.showGridLines = False

    col_widths = [3, 30, 22, 12, 12, 12, 3]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.merge_cells("B1:F1")
    ws["B1"] = "Hours by Project"
    ws["B1"].font = _font(bold=True, size=14, color=COLOR_HEADER_FG)
    ws["B1"].fill = _fill(COLOR_HEADER_BG)
    ws["B1"].alignment = _align("center")
    ws.row_dimensions[1].height = 30

    headers = ["Project", "Client", "Total Hours", "Billable Hours", "Amount"]
    row = 3
    for col, h in enumerate(headers, 2):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = _font(bold=True, color=COLOR_SECTION_FG)
        cell.fill = _fill(COLOR_SECTION_BG)
        cell.alignment = _align("center")
        cell.border = BORDER_THIN

    by_project = defaultdict(lambda: {"hours": Decimal("0"), "billable": Decimal("0"), "amount": Decimal("0"), "client": ""})
    for e in entries:
        key = e.project.name
        by_project[key]["client"] = e.project.client.name if e.project.client else "—"
        by_project[key]["hours"] += e.hours
        if e.is_billable:
            by_project[key]["billable"] += e.hours
        by_project[key]["amount"] += e.amount

    row = 4
    for idx, (project_name, data) in enumerate(sorted(by_project.items())):
        bg = COLOR_ALT_ROW if idx % 2 else "FFFFFF"
        row_data = [
            project_name, data["client"],
            float(data["hours"]), float(data["billable"]), float(data["amount"]),
        ]
        for col, val in enumerate(row_data, 2):
            cell = ws.cell(row=row, column=col, value=val)
            cell.font = _font(size=10)
            cell.fill = _fill(bg)
            cell.border = BORDER_THIN
            cell.alignment = _align()
            if col in (4, 5):
                cell.number_format = "0.00"
            if col == 6:
                cell.number_format = '"$"#,##0.00'
        ws.row_dimensions[row].height = 18
        row += 1

    # Grand total
    total_h = sum(d["hours"] for d in by_project.values())
    total_b = sum(d["billable"] for d in by_project.values())
    total_a = sum(d["amount"] for d in by_project.values())
    ws.merge_cells(f"B{row}:C{row}")
    ws.cell(row=row, column=2, value="TOTAL").font = _font(bold=True)
    ws.cell(row=row, column=2).fill = _fill(COLOR_TOTAL_BG)
    ws.cell(row=row, column=4, value=float(total_h)).number_format = "0.00"
    ws.cell(row=row, column=5, value=float(total_b)).number_format = "0.00"
    ws.cell(row=row, column=6, value=float(total_a)).number_format = '"$"#,##0.00'
    for col in range(2, 7):
        c = ws.cell(row=row, column=col)
        c.font = _font(bold=True)
        c.fill = _fill(COLOR_TOTAL_BG)
        c.border = BORDER_THICK
