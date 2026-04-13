#!/usr/bin/env python3
"""
Gmail → projects-service email sync agent.

Fetches Gmail threads related to each active project and upserts them into
projects-service via POST /api/v1/projects/{id}/emails/sync.

Usage:
  python3 agents/gmail-sync/sync_project_emails.py

Environment variables required:
  VITE_PROJECTS_API_BASE_URL  — base URL of projects-service
  ADMIN_JWT                   — admin JWT for projects-service auth

This script is intended to be run via Claude Code (which has Gmail MCP tools
available) or on a schedule in a Claude Code session with Gmail MCP configured.

Gmail MCP tools used:
  mcp__claude_ai_Gmail__search_threads  — search Gmail threads by query
  mcp__claude_ai_Gmail__get_thread      — fetch full thread content
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone


PROJECTS_API = os.getenv("VITE_PROJECTS_API_BASE_URL", "").rstrip("/")
ADMIN_JWT = os.getenv("ADMIN_JWT", os.getenv("VITE_ADMIN_JWT", ""))
SEARCH_DAYS = int(os.getenv("GMAIL_SYNC_DAYS", "30"))


def _api(method: str, path: str, body: dict | None = None) -> dict:
    """Call the projects-service API."""
    url = f"{PROJECTS_API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ADMIN_JWT}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {body_text}") from e


def _strip_html(html: str) -> str:
    """Very basic HTML tag stripper for snippet extraction."""
    return re.sub(r"<[^>]+>", "", html or "")


def _extract_body_html(parts: list) -> str | None:
    """Recursively extract text/html part from Gmail thread parts."""
    for part in parts:
        mime = part.get("mimeType", "")
        if mime == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                import base64
                return base64.urlsafe_b64decode(data + "==").decode(errors="replace")
        if "parts" in part:
            found = _extract_body_html(part["parts"])
            if found:
                return found
    return None


def _received_at(internal_date_ms: str) -> str:
    """Convert Gmail internalDate (ms epoch string) to ISO UTC string."""
    ts = int(internal_date_ms) / 1000
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sync_project(project: dict, mcp_search, mcp_get_thread) -> int:
    """Sync Gmail threads for one project. Returns number of emails upserted."""
    project_id = project["id"]
    project_name = project["name"]

    query = f'subject:"{project_name}" newer_than:{SEARCH_DAYS}d'
    print(f"  Searching Gmail: {query!r}")

    search_result = mcp_search(query=query, max_results=50)
    threads = search_result.get("threads", [])
    if not threads:
        print(f"  No threads found for project '{project_name}'")
        return 0

    emails = []
    for thread_meta in threads:
        thread_id = thread_meta.get("id")
        if not thread_id:
            continue

        thread = mcp_get_thread(thread_id=thread_id)
        messages = thread.get("messages", [])
        if not messages:
            continue

        # Use the first message of the thread for metadata
        first_msg = messages[0]
        headers = {h["name"]: h["value"] for h in first_msg.get("payload", {}).get("headers", [])}

        subject = headers.get("Subject", "(no subject)")
        from_email = headers.get("From", "unknown")
        internal_date = first_msg.get("internalDate", "0")
        received_at = _received_at(internal_date)

        # Extract HTML body from the last message (most recent reply)
        last_msg = messages[-1]
        payload = last_msg.get("payload", {})
        parts = payload.get("parts", [payload])
        body_html = _extract_body_html(parts)

        snippet = thread_meta.get("snippet") or first_msg.get("snippet") or ""
        if snippet:
            snippet = snippet[:500]

        emails.append({
            "thread_id": thread_id,
            "subject": subject,
            "from_email": from_email,
            "snippet": snippet or None,
            "body_html": body_html,
            "received_at": received_at,
        })

    if not emails:
        return 0

    print(f"  Syncing {len(emails)} thread(s) for project '{project_name}'")
    result = _api("POST", f"/api/v1/projects/{project_id}/emails/sync", {"emails": emails})
    upserted = result.get("upserted", len(emails))
    print(f"  Upserted {upserted} email(s)")
    return upserted


def main():
    if not PROJECTS_API:
        print("ERROR: VITE_PROJECTS_API_BASE_URL is not set", file=sys.stderr)
        sys.exit(1)
    if not ADMIN_JWT:
        print("ERROR: ADMIN_JWT (or VITE_ADMIN_JWT) is not set", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching active projects from {PROJECTS_API}...")
    projects_raw = _api("GET", "/api/v1/projects")

    # API returns list or paged response
    if isinstance(projects_raw, list):
        projects = projects_raw
    else:
        projects = projects_raw.get("data", [])

    active = [p for p in projects if p.get("status") not in ("cancelled", "completed")]
    print(f"Found {len(active)} active project(s)")

    if not active:
        print("Nothing to sync.")
        return

    # -------------------------------------------------------------------
    # Gmail MCP tool wrappers
    # These are resolved at runtime when this script is executed inside
    # a Claude Code agent session that has the Gmail MCP connector loaded.
    # Outside Claude Code, they can be mocked for local testing.
    # -------------------------------------------------------------------
    try:
        # When running inside Claude Code, these are injected as builtins
        # via the MCP tool bridge. The names must match exactly.
        mcp_search = mcp__claude_ai_Gmail__search_threads  # type: ignore[name-defined]  # noqa: F821
        mcp_get = mcp__claude_ai_Gmail__get_thread          # type: ignore[name-defined]  # noqa: F821
    except NameError:
        # Outside Claude Code: print instructions instead of crashing
        print(
            "\nGmail MCP tools are not available in this environment.\n"
            "Run this script inside a Claude Code session with the Gmail MCP\n"
            "connector configured, or use the /gmail-sync command.\n"
        )
        sys.exit(0)

    total = 0
    for project in active:
        print(f"\nProject: {project['name']} ({project['id']})")
        try:
            total += sync_project(project, mcp_search, mcp_get)
        except Exception as exc:
            print(f"  ERROR: {exc}")

    print(f"\nDone. Total emails upserted: {total}")


if __name__ == "__main__":
    main()
