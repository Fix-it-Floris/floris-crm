"""
Notion API helpers — shared across all scripts.
Handles all reads and writes to the CRM database.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

NOTION_TOKEN   = os.environ["NOTION_TOKEN"]
DATABASE_ID    = os.environ["NOTION_DATABASE_ID"]

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# ── Status values (must match your Notion select options exactly) ─────────────
STATUS_SUGGESTED      = "Suggested"
STATUS_CONTACTED      = "Contacted"
STATUS_FOLLOW_UP      = "Follow-up needed"
STATUS_INTERESTED     = "Interested"
STATUS_NOT_INTERESTED = "Not interested"
STATUS_REJECTED       = "Rejected – do not contact"
STATUS_ARCHIVED       = "Archived"


def _request(method: str, url: str, data: Optional[dict] = None) -> dict:
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Notion API error {e.code}: {e.read().decode()}") from e


def query_database(filter_body: Optional[dict] = None, sorts: Optional[list] = None) -> list:
    """Return all pages matching a filter (handles Notion pagination)."""
    url     = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {}
    if filter_body:
        payload["filter"] = filter_body
    if sorts:
        payload["sorts"] = sorts

    pages, cursor = [], None
    while True:
        if cursor:
            payload["start_cursor"] = cursor
        resp   = _request("POST", url, payload)
        pages += resp.get("results", [])
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return pages


def create_page(properties: dict) -> dict:
    """Create a new page (row) in the database."""
    return _request("POST", "https://api.notion.com/v1/pages", {
        "parent": {"database_id": DATABASE_ID},
        "properties": properties,
    })


def update_page(page_id: str, properties: dict) -> dict:
    """Update properties of an existing page."""
    return _request("PATCH", f"https://api.notion.com/v1/pages/{page_id}", {
        "properties": properties,
    })


# ── Property builders ─────────────────────────────────────────────────────────

def prop_title(text: str) -> dict:
    return {"title": [{"text": {"content": text[:2000]}}]}

def prop_text(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:2000]}}]}

def prop_select(option: str) -> dict:
    return {"select": {"name": option}}

def prop_date(dt: datetime) -> dict:
    return {"date": {"start": dt.strftime("%Y-%m-%d")}}

def prop_url(url: str) -> dict:
    return {"url": url}

def prop_multi_select(options: list[str]) -> dict:
    return {"multi_select": [{"name": o} for o in options]}


# ── Property readers ──────────────────────────────────────────────────────────

def read_title(page: dict, key: str) -> str:
    items = page["properties"].get(key, {}).get("title", [])
    return "".join(t.get("plain_text", "") for t in items)

def read_text(page: dict, key: str) -> str:
    items = page["properties"].get(key, {}).get("rich_text", [])
    return "".join(t.get("plain_text", "") for t in items)

def read_select(page: dict, key: str) -> str:
    sel = page["properties"].get(key, {}).get("select")
    return sel["name"] if sel else ""

def read_date(page: dict, key: str) -> Optional[datetime]:
    d = page["properties"].get(key, {}).get("date")
    if not d or not d.get("start"):
        return None
    return datetime.fromisoformat(d["start"]).replace(tzinfo=timezone.utc)

def read_url(page: dict, key: str) -> str:
    return page["properties"].get(key, {}).get("url") or ""

def read_multi_select(page: dict, key: str) -> list[str]:
    items = page["properties"].get(key, {}).get("multi_select", [])
    return [i["name"] for i in items]


# ── Convenience queries ───────────────────────────────────────────────────────

def get_all_company_names() -> set[str]:
    """Return the set of all company names already in the database."""
    pages = query_database()
    return {read_title(p, "Company").lower().strip() for p in pages}


def get_edited_email_examples(limit: int = 3) -> list[dict]:
    """
    Return the most recent entries where the user has filled in
    'Email edited' — used as tone examples for Claude.
    """
    pages = query_database(
        filter_body={
            "property": "Email edited",
            "rich_text": {"is_not_empty": True},
        },
        sorts=[{"property": "Date suggested", "direction": "descending"}],
    )
    results = []
    for p in pages[:limit]:
        results.append({
            "company": read_title(p, "Company"),
            "email":   read_text(p, "Email edited"),
        })
    return results


def get_pages_needing_followup(days: int = 14) -> list[dict]:
    """Return Contacted pages where no response was received in `days` days."""
    pages = query_database(
        filter_body={
            "property": "Status",
            "select": {"equals": STATUS_CONTACTED},
        }
    )
    now     = datetime.now(timezone.utc)
    results = []
    for p in pages:
        contacted = read_date(p, "Date contacted")
        if not contacted:
            continue
        delta = (now - contacted).days
        if delta >= days:
            results.append({"page": p, "days_since": delta})
    return results


def get_pipeline_stats() -> dict:
    """Return counts per status for the weekly digest."""
    pages  = query_database()
    counts = {}
    for p in pages:
        s = read_select(p, "Status")
        counts[s] = counts.get(s, 0) + 1

    total_contacted  = sum(counts.get(s, 0) for s in [
        STATUS_CONTACTED, STATUS_FOLLOW_UP,
        STATUS_INTERESTED, STATUS_NOT_INTERESTED, STATUS_REJECTED,
    ])
    total_responded  = sum(counts.get(s, 0) for s in [
        STATUS_INTERESTED, STATUS_NOT_INTERESTED, STATUS_REJECTED,
    ])
    response_rate    = (total_responded / total_contacted * 100) if total_contacted else 0
    success_rate     = (counts.get(STATUS_INTERESTED, 0) / total_responded * 100) if total_responded else 0

    return {
        "suggested":      counts.get(STATUS_SUGGESTED, 0),
        "contacted":      counts.get(STATUS_CONTACTED, 0),
        "follow_up":      counts.get(STATUS_FOLLOW_UP, 0),
        "interested":     counts.get(STATUS_INTERESTED, 0),
        "not_interested": counts.get(STATUS_NOT_INTERESTED, 0),
        "rejected":       counts.get(STATUS_REJECTED, 0),
        "archived":       counts.get(STATUS_ARCHIVED, 0),
        "total_contacted": total_contacted,
        "response_rate":  round(response_rate, 1),
        "success_rate":   round(success_rate, 1),
    }
