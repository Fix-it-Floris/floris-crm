#!/usr/bin/env python3
"""
followup_checker.py — runs daily at 09:05 Amsterdam time.

Finds all "Contacted" companies with no response after 14 days,
flips their status to "Follow-up needed", generates a follow-up
email draft using Claude (learning from Floris's tone), and sends
an alert email listing everything that needs attention.
"""

import json
import os
import sys
from datetime import datetime

import anthropic

sys.path.insert(0, os.path.dirname(__file__))
from notion_client import (
    get_pages_needing_followup,
    get_edited_email_examples,
    update_page,
    read_title, read_text,
    prop_select, prop_text,
    STATUS_FOLLOW_UP,
)
from email_utils import send_html_email, email_wrapper

STOP_SERVICE      = os.environ.get("STOP_SERVICE", "false").lower()
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
FOLLOWUP_DAYS     = int(os.environ.get("FOLLOWUP_DAYS", "14"))


FOLLOWUP_PROMPT = """
You are writing a follow-up cold email for Floris Witte (floriswitte.com),
a freelance mechanical engineer.

He previously sent a cold email to {company} ({role}) but received no reply after {days} days.

ORIGINAL COLD EMAIL HE SENT:
{original_email}

TONE EXAMPLES (Floris's edited emails — match this voice exactly):
{tone_examples}

Write a short, confident follow-up email. Rules:
- Subject line on first line prefixed "Subject: "
- Reference the previous email briefly ("I reached out X weeks ago about…")
- Add one new angle or piece of value — don't just repeat the original
- Even shorter than the original: 80–120 words max
- Not apologetic. Direct and respectful.
- Same sign-off as his original emails.

Return ONLY the email text. No explanation.
""".strip()

FOLLOWUP_DEFAULT_TONE = """
Direct, confident, no fluff. Short follow-up that adds one new angle.
Not apologetic. Professional but human. Sign off: Floris Witte | Fix-it Floris Engineering | floriswitte.com
"""


def draft_followup(company: str, role: str, days: int,
                   original_email: str, examples: list) -> str:
    if examples:
        tone = "\n\n---\n\n".join(
            f"Company: {e['company']}\n\n{e['email']}" for e in examples
        )
    else:
        tone = FOLLOWUP_DEFAULT_TONE

    prompt = FOLLOWUP_PROMPT.format(
        company=company,
        role=role,
        days=days,
        original_email=original_email or "(no draft stored)",
        tone_examples=tone,
    )
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def alert_card(company: str, days: int, notion_url: str, followup_draft: str) -> str:
    escaped = followup_draft.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    return f"""
<div style="margin-bottom:24px;padding:16px;border:1px solid #fde68a;
            border-left:4px solid #f59e0b;border-radius:8px;background:#fffbeb;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
    <p style="margin:0;font-size:15px;font-weight:600;color:#111;">{company}</p>
    <span style="background:#fef3c7;color:#92400e;font-size:11px;font-weight:600;
                 padding:3px 10px;border-radius:20px;">{days} days — no reply</span>
  </div>
  <p style="margin:0 0 12px;font-size:13px;color:#6b7280;">
    Follow-up draft saved to Notion. Copy, edit, and send.
  </p>
  <div style="background:#fff;border:1px solid #e5e7eb;border-radius:6px;
              padding:12px;font-size:12px;color:#374151;line-height:1.7;
              margin-bottom:12px;white-space:pre-wrap;">{escaped}</div>
  <a href="{notion_url}" style="display:inline-block;background:#111;color:#fff;
     font-size:12px;padding:6px 14px;border-radius:6px;text-decoration:none;">
    Open in Notion &rarr;
  </a>
</div>"""


def main():
    if STOP_SERVICE == "true":
        print("STOP_SERVICE is true — exiting.")
        sys.exit(0)

    print("Checking for companies needing follow-up…")
    stale = get_pages_needing_followup(days=FOLLOWUP_DAYS)

    if not stale:
        print("No follow-ups needed today.")
        sys.exit(0)

    print(f"  {len(stale)} companies need follow-up.")

    print("Fetching tone examples…")
    examples = get_edited_email_examples(limit=3)

    cards_html = ""
    for item in stale:
        page        = item["page"]
        days        = item["days_since"]
        page_id     = page["id"]
        notion_url  = page.get("url", "")
        company     = read_title(page, "Company")
        role        = read_text(page, "Contact role")
        orig_email  = read_text(page, "Email edited") or read_text(page, "Email draft")

        print(f"  Drafting follow-up for '{company}' ({days} days)…")
        followup = draft_followup(company, role, days, orig_email, examples)

        # Update Notion: flip status + save follow-up draft
        update_page(page_id, {
            "Status":           prop_select(STATUS_FOLLOW_UP),
            "Follow-up draft":  prop_text(followup),
        })

        cards_html += alert_card(company, days, notion_url, followup)

    today_str = datetime.now().strftime("%A, %d %B %Y")
    body = f"""
<p style="margin:0 0 20px;font-size:13px;color:#6b7280;">
  {len(stale)} {'company' if len(stale)==1 else 'companies'} 
  {'has' if len(stale)==1 else 'have'} been waiting {FOLLOWUP_DAYS}+ days for a reply.
  Follow-up drafts are ready — edit in Notion and send.
</p>
{cards_html}"""

    html = email_wrapper(
        title=f"Follow-up needed — {today_str}",
        subtitle=f"{len(stale)} companies awaiting your follow-up email",
        body_html=body,
        footer_note="Mark as 'Interested', 'Not interested', or 'Rejected' in Notion after they reply. &nbsp;|&nbsp; ",
    )

    print("Sending follow-up alert email…")
    send_html_email(
        subject=f"⏰ Follow-up needed: {len(stale)} companies — {datetime.now().strftime('%d %b %Y')}",
        html_body=html,
    )
    print("Done.")


if __name__ == "__main__":
    main()
