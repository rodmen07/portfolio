#!/usr/bin/env python3
"""
Update the productionizer progress section in infraportal/README.md.
Reads agents/productionizer/state.json and rewrites the content between
<!-- PRODUCTIONIZER:START --> / <!-- PRODUCTIONIZER:END --> markers.

Run from the GitHub Actions workspace:
  python agents/productionizer/update_readme.py
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import sys

# Resolve paths regardless of cwd
_SCRIPT_DIR = pathlib.Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))
from tasks import PAGES, GAPS  # noqa: E402

TOTAL = len(PAGES) * len(GAPS)

MARKER_START = "<!-- PRODUCTIONIZER:START -->"
MARKER_END   = "<!-- PRODUCTIONIZER:END -->"

# In Actions: GITHUB_WORKSPACE points to the checked-out portfolio repo.
# Locally: fall back to three levels up from this script.
_WORKSPACE = pathlib.Path(
    os.environ.get("GITHUB_WORKSPACE")
    or str(_SCRIPT_DIR.parent.parent.parent)
)
STATE_FILE  = _SCRIPT_DIR / "state.json"
README_FILE = _WORKSPACE / "infraportal" / "README.md"


def _progress_bar(pct: int, width: int = 30) -> str:
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _page_short(page: str) -> str:
    """Abbreviate page names for the table header."""
    return page.replace("Page", "")


def _fmt_run(iso: str | None) -> str:
    if not iso:
        return "never"
    try:
        dt = datetime.datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso


def build_progress_section(state: dict) -> str:
    completed_set = {(p, g) for p, g in state.get("completed", [])}
    n = len(completed_set)
    pct = int(n / TOTAL * 100) if TOTAL > 0 else 0
    bar = _progress_bar(pct)

    # Task matrix table
    header = "| Gap | " + " | ".join(_page_short(p) for p in PAGES) + " |"
    sep    = "|-----|" + "|".join([":---:"] * len(PAGES)) + "|"
    rows   = []
    for gap in GAPS:
        cells = ["✅" if (page, gap) in completed_set else "⬜" for page in PAGES]
        rows.append(f"| `{gap}` | " + " | ".join(cells) + " |")

    # Next task
    next_task = "**All tasks complete!** 🎉"
    for gap in GAPS:
        for page in PAGES:
            if (page, gap) not in completed_set:
                next_task = f"`{page}` / `{gap}`"
                break
        else:
            continue
        break

    # Recent completions
    recent_summaries = state.get("recent_summaries", [])
    if recent_summaries:
        recent_lines = "\n".join(
            f"- **{s['page']}** / `{s['gap']}` — {s['summary']}"
            for s in reversed(recent_summaries[-5:])
        )
    else:
        recent_lines = "*(none yet)*"

    last_run = _fmt_run(state.get("last_run"))

    return (
        f"{MARKER_START}\n"
        f"## Productionizer Agent\n\n"
        f"Near-autonomous UI/UX improvement agent powered by **Gemini 2.5 Flash**. "
        f"Each workflow run picks the next pending task from the matrix below, applies the fix, "
        f"verifies with `tsc` + `eslint`, and opens a PR against this repo.\n\n"
        f"**Source**: [rodmen07/portfolio — agents/productionizer](https://github.com/rodmen07/portfolio/tree/main/agents/productionizer) "
        f"· Triggered manually via `workflow_dispatch` · Runs in 15–60 min windows\n\n"
        f"---\n\n"
        f"### Progress\n\n"
        f"**{n} / {TOTAL} tasks complete** ({pct}%)\n\n"
        f"`{bar}`\n\n"
        f"### Task Matrix\n\n"
        f"{header}\n"
        f"{sep}\n"
        f"\n".join(rows) + "\n\n"
        f"> ✅ = PR opened (or task already satisfied) · ⬜ = pending\n\n"
        f"### Next task\n\n"
        f"{next_task}\n\n"
        f"### Recently completed\n\n"
        f"{recent_lines}\n\n"
        f"### Stop conditions\n\n"
        f"The agent pauses automatically when:\n"
        f"- ⏱ The configured time window (15 / 30 / 45 / 60 min) is exhausted\n"
        f"- ⚠️ 25 or more open PRs are awaiting review\n"
        f"- ❌ An unrecoverable error occurs\n\n"
        f"### Last run\n\n"
        f"{last_run}\n\n"
        f"*Updated automatically by productionizer-bot · Do not edit between these markers*\n"
        f"{MARKER_END}"
    )


def main() -> None:
    if not STATE_FILE.exists():
        print("state.json not found — skipping README update", file=sys.stderr)
        sys.exit(0)

    if not README_FILE.exists():
        print(f"README not found at {README_FILE} — skipping", file=sys.stderr)
        sys.exit(0)

    state  = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    readme = README_FILE.read_text(encoding="utf-8")

    new_section = build_progress_section(state)

    if MARKER_START in readme and MARKER_END in readme:
        start = readme.index(MARKER_START)
        end   = readme.index(MARKER_END) + len(MARKER_END)
        new_readme = readme[:start] + new_section + readme[end:]
    else:
        new_readme = readme.rstrip() + "\n\n" + new_section + "\n"

    README_FILE.write_text(new_readme, encoding="utf-8")

    n = len({(p, g) for p, g in state.get("completed", [])})
    print(f"README updated: {n} / {TOTAL} tasks complete ({int(n/TOTAL*100)}%)")


if __name__ == "__main__":
    main()
