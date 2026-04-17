#!/usr/bin/env python3
"""
daily_leads.py — runs every weekday at 09:00 Amsterdam time.

1. Fetches all existing company names from Notion (deduplication).
2. Fetches up to 3 of Floris's edited emails (tone learning).
3. Asks Claude for 5 new leads across Europe, with cold email drafts.
4. Writes each lead as a new page in Notion.
5. Sends a daily digest email to Floris.
"""

import json
import os
import sys
from datetime import datetime, timezone

import anthropic

sys.path.insert(0, os.path.dirname(__file__))
from notion_client import (
    get_all_company_names,
    get_edited_email_examples,
    create_page,
    prop_title, prop_text, prop_select, prop_date, prop_url, prop_multi_select,
    STATUS_SUGGESTED,
)
from email_utils import send_html_email, email_wrapper

STOP_SERVICE = os.environ.get("STOP_SERVICE", "false").lower()
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]


LEAD_PROMPT = """
You are a recruiter for Floris Witte — a freelance mechanical engineer. Check (www.floriswitte.com).
Clear your history of past suggestions and start from scratch.

FLORIS'S PROFILE:
- Specialises in machine design, mechanical product development, industrial factory line optimisation,
- Past clients: Engineering firms, leading corrugated packaging machine maker, Philips Drachten 
- Past projects: automated packaging machines, automated potato filler, cobot End of arm tools, part of assembly and manufacturing lines,
- Engagement preference: 1–3 month fixed-price packages (€80–100/hr basis)
- Works 100% remote

ALREADY IN HIS DATABASE (do NOT suggest any of these):
{existing_companies}

TODAY: {today}

TASK: Find exactly 5 companies in Europe that need Floris his expertise regularly.
- Prefer companies that do mechanical engineering, like manufacturing, machine design and product design
- NO battery-, electrical-, programming-, and chemistry themed companies
- Mix of sectors: cleantech/sustainable energy, industrial automation/machinery, consumer hardware startups
- Prefer companies that are manufacturing products in-house, scaling production, or have upcoming deadlines
- Suggest at least two companies from the Netherlands

For each company return a JSON object with these exact keys:
- company_name (string)
- country (string)
- city (string)  
- sector (string — one of: "Cleantech", "Industrial automation", "Consumer hardware")
- what_they_do (string — one sentence max)
- why_floris_fits (string — 2 sentences, specific, reference his past work where relevant)
- contact_role (string — job title to target, e.g. "Head of Engineering")
- linkedin_tip (string — how to find them on LinkedIn)
- fit_tags (array of 3–4 strings)
- fit_level (string — one of: "Strong", "Good", "Interesting")
- cold_email_draft (string — full cold email body, see tone instructions below)

COLD EMAIL TONE INSTRUCTIONS:
{tone_instructions}

Return ONLY a valid JSON array of 5 objects. No preamble, no explanation, no markdown fences.
""".strip()

TONE_DEFAULT = """
Write a confident, direct cold email. Short paragraphs, no fluff.
- Subject line included as first line prefixed with "Subject: "
- 3–4 short paragraphs: hook → specific relevance → what Floris offers → clear CTA
- Tone: professional but human, not corporate
- Length: 150–200 words max
- Sign off as: Floris Witte | Fix-it Floris Engineering | floriswitte.com
"""

TONE_FROM_EXAMPLES = """
Match the tone and style of these emails that Floris has sent and edited himself.
Use them as direct style references — same paragraph length, vocabulary, directness, and sign-off format.

{examples}

Write the new cold email in exactly this voice.
"""


def build_prompt(existing: set, examples: list) -> str:
    existing_str = "\n".join(f"- {name}" for name in sorted(existing)) if existing else "None yet"

    if examples:
        examples_str = "\n\n---\n\n".join(
            f"Company: {e['company']}\n\n{e['email']}" for e in examples
        )
        tone = TONE_FROM_EXAMPLES.format(examples=examples_str)
    else:
        tone = TONE_DEFAULT

    return LEAD_PROMPT.format(
        existing_companies=existing_str,
        today=datetime.now().strftime("%A, %d %B %Y"),
        tone_instructions=tone,
    )


def fetch_leads(prompt: str) -> list:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    # Strip any accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw)


def write_to_notion(lead: dict) -> str:
    """Create a Notion page for the lead. Returns the page URL."""
    today = datetime.now(timezone.utc)
    page = create_page({
        "Company":          prop_title(lead["company_name"]),
        "Country":          prop_text(lead["country"]),
        "City":             prop_text(lead["city"]),
        "Sector":           prop_select(lead["sector"]),
        "What they do":     prop_text(lead["what_they_do"]),
        "Why Floris fits":  prop_text(lead["why_floris_fits"]),
        "Contact role":     prop_text(lead["contact_role"]),
        "LinkedIn tip":     prop_text(lead["linkedin_tip"]),
        "Fit tags":         prop_multi_select(lead.get("fit_tags", [])),
        "Fit level":        prop_select(lead["fit_level"]),
        "Status":           prop_select(STATUS_SUGGESTED),
        "Date suggested":   prop_date(today),
        "Email draft":      prop_text(lead.get("cold_email_draft", "")),
        "Email edited":     prop_text(""),   # you fill this in after editing
        "Notes":            prop_text(""),
    })
    return page.get("url", "")


def card_html(lead: dict, notion_url: str) -> str:
    fit_colors = {
        "Strong":      ("d1fae5", "065f46"),
        "Good":        ("dbeafe", "1e40af"),
        "Interesting": ("fef3c7", "92400e"),
    }
    bg, fg = fit_colors.get(lead["fit_level"], ("f3f4f6", "374151"))
    tags = "".join(
        f'<span style="background:#f3f4f6;color:#374151;font-size:11px;'
        f'padding:2px 8px;border-radius:20px;margin-right:4px;">{t}</span>'
        for t in lead.get("fit_tags", [])
    )
    return f"""
<div style="margin-bottom:20px;padding:16px;border:1px solid #e5e7eb;border-radius:8px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
    <div>
      <p style="margin:0 0 2px;font-size:15px;font-weight:600;color:#111;">
        {lead['company_name']}
      </p>
      <p style="margin:0;font-size:13px;color:#6b7280;">
        {lead['city']}, {lead['country']} &middot; {lead['sector']}
      </p>
    </div>
    <span style="background:#{bg};color:#{fg};font-size:11px;font-weight:600;
                 padding:3px 10px;border-radius:20px;white-space:nowrap;">
      {lead['fit_level']} fit
    </span>
  </div>
  <p style="margin:0 0 6px;font-size:13px;color:#374151;line-height:1.6;">
    {lead['why_floris_fits']}
  </p>
  <p style="margin:0 0 10px;font-size:12px;color:#6b7280;">
    <strong>Contact:</strong> {lead['contact_role']} &nbsp;|&nbsp;
    <strong>Find:</strong> {lead['linkedin_tip']}
  </p>
  <div style="margin-bottom:12px;">{tags}</div>
  <a href="{notion_url}" style="display:inline-block;background:#111;color:#fff;
     font-size:12px;padding:6px 14px;border-radius:6px;text-decoration:none;">
    Open in Notion &rarr;
  </a>
</div>"""


def main():
    if STOP_SERVICE == "true":
        print("STOP_SERVICE is true — exiting.")
        sys.exit(0)

    print("Fetching existing companies from Notion…")
    existing = get_all_company_names()
    print(f"  {len(existing)} companies already in database.")

    print("Fetching tone examples from Notion…")
    examples = get_edited_email_examples(limit=3)
    print(f"  {len(examples)} edited email(s) found for tone learning.")

    print("Asking Claude for 5 leads…")
    prompt = build_prompt(existing, examples)
    leads  = fetch_leads(prompt)
    print(f"  Got {len(leads)} leads.")

    cards_html = ""
    for lead in leads:
        print(f"  Writing '{lead['company_name']}' to Notion…")
        notion_url  = write_to_notion(lead)
        cards_html += card_html(lead, notion_url)

    today_str = datetime.now().strftime("%A, %d %B %Y")
    body = f"""
<p style="margin:0 0 20px;font-size:13px;color:#6b7280;">
  5 fresh leads across Europe — deduplicated against your existing {len(existing)} companies.
  Cold email drafts are waiting in each Notion page. Edit them there to train your tone.
</p>
{cards_html}"""

    html = email_wrapper(
        title=f"Your 5 leads for {today_str}",
        subtitle="Open each card in Notion to see the cold email draft.",
        body_html=body,
        footer_note="Update the status in Notion once you've sent an email. &nbsp;|&nbsp; ",
    )

    print("Sending email…")
    send_html_email(
        subject=f"🔧 5 new leads — {datetime.now().strftime('%d %b %Y')}",
        html_body=html,
    )
    print("Done.")


if __name__ == "__main__":
    main()
