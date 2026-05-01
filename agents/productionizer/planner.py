"""
Planner — generates concrete implementable tasks from development dimensions.

Reads dimensions.yaml, scans the relevant repos, and asks Claude (Opus) to
produce a specific, actionable task list. Appends new tasks to backlog.yaml.

Usage:
  ANTHROPIC_API_KEY=...  python planner.py
  ANTHROPIC_API_KEY=...  python planner.py --dimension frontend-ui-ux
  ANTHROPIC_API_KEY=...  python planner.py --count 10
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
import pathlib
import uuid

import anthropic
import yaml

from repos import REPOS
from tasks import Task, load_backlog, save_backlog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("planner")

AGENT_DIR = pathlib.Path(__file__).parent
DIMENSIONS_FILE = AGENT_DIR / "dimensions.yaml"
PLANNER_MODEL = "claude-opus-4-7"


def load_dimensions() -> list[dict]:
    raw = yaml.safe_load(DIMENSIONS_FILE.read_text())
    return raw.get("dimensions", [])


def scan_repo_structure(repo_name: str) -> str:
    cfg = REPOS.get(repo_name)
    if not cfg or not cfg.path.exists():
        return f"(repo '{repo_name}' not found on disk at {REPOS.get(repo_name, object()).path if repo_name in REPOS else 'unknown'})"  # type: ignore[union-attr]

    _SKIP = {"node_modules", "dist", "target", ".git", "__pycache__", ".venv", "vendor"}

    lines = [f"### {repo_name} ({cfg.language}) — {cfg.github_repo}"]
    try:
        for item in sorted(cfg.path.iterdir()):
            if item.name.startswith(".") or item.name in _SKIP:
                continue
            rel = item.relative_to(cfg.path)
            if item.is_dir():
                lines.append(f"  {rel}/")
                try:
                    for sub in sorted(item.iterdir())[:12]:
                        if not sub.name.startswith(".") and sub.name not in _SKIP:
                            lines.append(f"    {sub.name}{'/' if sub.is_dir() else ''}")
                except PermissionError:
                    pass
            else:
                lines.append(f"  {item.name}")
            if len(lines) > 50:
                lines.append("  ... (truncated)")
                break
    except Exception as exc:
        lines.append(f"  ERROR: {exc}")

    return "\n".join(lines)


def generate_tasks(
    client: anthropic.Anthropic,
    dimension: dict,
    existing_titles: set[str],
    count: int,
) -> list[Task]:
    repo_overviews = "\n\n".join(scan_repo_structure(r) for r in dimension["repos"])
    existing_str = "\n".join(f"- {t}" for t in sorted(existing_titles)) or "(none)"

    prompt = f"""You are planning a development sprint for a software portfolio project.

## Dimension: {dimension['name']}

{dimension['description'].strip()}

## Target repos: {dimension['repos']}

## Current repo structure:
{repo_overviews}

## Already-queued tasks (do NOT duplicate):
{existing_str}

## Your task:
Generate exactly {count} concrete, implementable development tasks for this dimension.

Requirements for each task:
1. Specific and immediately actionable — a developer can start without clarification
2. Scoped to ~1-5 file changes (not a multi-week project)
3. Independently implementable (no dependency on other generated tasks)
4. Genuinely valuable (not trivial, not already present from the repo scan)
5. Grounded in the actual repo structure shown above — name real files/dirs where relevant

Complexity guide:
  low    = 1-2 files, clear scope, no design decisions → claude-haiku-4-5
  medium = 2-5 files, moderate decisions, single repo  → claude-sonnet-4-6
  high   = 5+ files, cross-repo, architectural choices → claude-opus-4-7

Return ONLY a YAML block (no other text):
```yaml
tasks:
  - title: "Short action-oriented title (imperative verb)"
    description: |
      Detailed implementation instructions.
      Name specific files, functions, components, endpoints, or types where known.
      Describe expected behavior, edge cases to handle, and any conventions to follow.
    repos:
      - repo_name
    complexity: low|medium|high
```"""

    log.info("Generating %d tasks for: %s", count, dimension["id"])
    response = client.messages.create(
        model=PLANNER_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text  # type: ignore[union-attr]

    if "```yaml" in text:
        start = text.index("```yaml") + 7
        end = text.index("```", start)
        yaml_text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        yaml_text = text[start:end].strip()
    else:
        yaml_text = text.strip()

    raw = yaml.safe_load(yaml_text)
    tasks_raw = raw.get("tasks", [])

    tasks: list[Task] = []
    today = datetime.date.today().isoformat()
    for item in tasks_raw:
        task = Task(
            id=f"{dimension['id']}-{uuid.uuid4().hex[:8]}",
            dimension=dimension["id"],
            title=item["title"],
            description=item["description"].strip(),
            repos=item["repos"],
            complexity=item.get("complexity", "medium"),
            status="pending",
            created_at=today,
        )
        tasks.append(task)
        log.info("  [%s] %s", task.complexity, task.title)

    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate tasks from development dimensions")
    parser.add_argument("--dimension", help="Only process this dimension ID")
    parser.add_argument("--count", type=int, default=8, help="Tasks per dimension (default: 8)")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY is not set")
        raise SystemExit(1)

    client = anthropic.Anthropic(api_key=api_key)
    dimensions = load_dimensions()

    if args.dimension:
        dimensions = [d for d in dimensions if d["id"] == args.dimension]
        if not dimensions:
            log.error("Dimension not found: %s", args.dimension)
            raise SystemExit(1)

    backlog = load_backlog()
    existing_titles = {t.title for t in backlog}
    new_tasks: list[Task] = []

    for dim in dimensions:
        try:
            tasks = generate_tasks(client, dim, existing_titles, count=args.count)
            new_tasks.extend(tasks)
            existing_titles.update(t.title for t in tasks)
        except Exception as exc:
            log.error("Failed for dimension %s: %s", dim["id"], exc)

    backlog.extend(new_tasks)
    save_backlog(backlog)

    pending = sum(1 for t in backlog if t.status == "pending")
    log.info("Added %d tasks. Backlog: %d total, %d pending.", len(new_tasks), len(backlog), pending)


if __name__ == "__main__":
    main()
