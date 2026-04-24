#!/usr/bin/env python3
"""
weekly_digest.py — runs every Friday at 09:05 Amsterdam time.

Pulls live pipeline stats from Notion and sends a clean
weekly summary email with response rate, success rate,
and a breakdown of where everything stands.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from notion_client import get_pipeline_stats, query_database, read_title, read_select, read_date, read_text
from email_utils import send_html_email, email_wrapper

STOP_SERVICE = os.environ.get("STOP_SERVICE", "false").lower()


def stat_card(label: str, value, color: str = "#111") -> str:
    return f"""
<div style="flex:1;min-width:120px;background:#f9fafb;border-radius:8px;
            padding:14px 16px;text-align:center;">
  <p style="margin:0 0 4px;font-size:12px;color:#6b7280;">{label}</p>
  <p style="margin:0;font-size:24px;font-weight:600;color:{color};">{value}</p>
</div>"""


def pipeline_row(status: str, count: int, color: str) -> str:
    if count == 0:
        return ""
    return f"""
<tr>
  <td style="padding:8px 0;font-size:13px;color:#374151;">{status}</td>
  <td style="padding:8px 0;text-align:right;">
    <span style="background:{color};font-size:12px;font-weight:600;
                 padding:2px 10px;border-radius:20px;">{count}</span>
  </td>
</tr>"""


def recent_activity_html() -> str:
    """Show the 5 most recently updated leads."""
    pages = query_database(
        sorts=[{"property": "Date suggested", "direction": "descending"}]
    )
    rows = ""
    for p in pages[:5]:
        company = read_title(p, "Company")
        status  = read_select(p, "Status")
        date    = read_date(p, "Date suggested")
        date_str = date.strftime("%d %b") if date else "—"
        status_colors = {
            "Suggested":              ("#f3f4f6", "#374151"),
            "Contacted":              ("#dbeafe", "#1e40af"),
            "Follow-up needed":       ("#fef3c7", "#92400e"),
            "Interested":             ("#d1fae5", "#065f46"),
            "Not interested":         ("#fee2e2", "#991b1b"),
            "Rejected – do not contact": ("#fee2e2", "#7f1d1d"),
        }
        bg, fg = status_colors.get(status, ("#f3f4f6", "#374151"))
        rows += f"""
<tr>
  <td style="padding:8px 0;font-size:13px;color:#111;">{company}</td>
  <td style="padding:8px 0;text-align:center;font-size:12px;color:#6b7280;">{date_str}</td>
  <td style="padding:8px 0;text-align:right;">
    <span style="background:{bg};color:{fg};font-size:11px;font-weight:600;
                 padding:2px 8px;border-radius:20px;">{status}</span>
  </td>
</tr>"""
    return f"""
<table style="width:100%;border-collapse:collapse;">{rows}</table>"""


def main():
    if STOP_SERVICE == "true":
        print("STOP_SERVICE is true — exiting.")
        sys.exit(0)

    print("Fetching pipeline stats from Notion…")
    s = get_pipeline_stats()

    today_str = datetime.now().strftime("%A, %d %B %Y")
    week_num  = datetime.now().isocalendar()[1]

    # Top stat cards
    stats_html = f"""
<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px;">
  {stat_card("Open suggestions", s['suggested'])}
  {stat_card("Contacted", s['contacted'] + s['follow_up'])}
  {stat_card("Response rate", f"{s['response_rate']}%", "#1e40af")}
  {stat_card("Success rate", f"{s['success_rate']}%", "#065f46")}
</div>"""

    # Pipeline breakdown table
    pipeline_html = f"""
<p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#111;">Pipeline breakdown</p>
<table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
  {pipeline_row("Suggested (not yet contacted)", s['suggested'],      "#f3f4f6")}
  {pipeline_row("Contacted — awaiting reply",    s['contacted'],      "#dbeafe")}
  {pipeline_row("Follow-up needed",              s['follow_up'],      "#fef3c7")}
  {pipeline_row("Interested",                    s['interested'],     "#d1fae5")}
  {pipeline_row("Not interested",                s['not_interested'], "#fee2e2")}
  {pipeline_row("Rejected – do not contact",     s['rejected'],       "#fecaca")}
</table>"""

    # Recent activity
    recent_html = f"""
<p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#111;">5 most recent leads</p>
{recent_activity_html()}"""

    body = f"""
<p style="margin:0 0 20px;font-size:13px;color:#6b7280;">
  Week {week_num} pipeline summary. All data pulled live from your Notion CRM.
</p>
{stats_html}
<hr style="border:none;border-top:1px solid #e5e7eb;margin:0 0 20px;">
{pipeline_html}
<hr style="border:none;border-top:1px solid #e5e7eb;margin:0 0 20px;">
{recent_html}"""

    html = email_wrapper(
        title=f"Weekly pipeline — week {week_num}",
        subtitle=today_str,
        body_html=body,
        footer_note="Open Notion to update statuses and edit email drafts. &nbsp;|&nbsp; ",
    )

    print("Sending weekly digest…")
    send_html_email(
        subject=f"📊 Weekly pipeline — week {week_num} · {datetime.now().strftime('%d %b %Y')}",
        html_body=html,
    )
    print("Done.")


if __name__ == "__main__":
    main()
