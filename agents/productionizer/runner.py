"""
Productionizer runner — full task loop across the entire backlog.

Handles: task selection, agent invocation, multi-repo PR creation, README update.

Usage:
  ANTHROPIC_API_KEY=...  GITHUB_PAT=...  python runner.py
  ANTHROPIC_API_KEY=...  GITHUB_PAT=...  python runner.py --force-task-id <id>

Environment:
  ANTHROPIC_API_KEY   required — Claude API key
  GITHUB_PAT          required — GitHub token with repo write access (all submodules)
  FORCE_TASK_ID       optional — run exactly this task ID
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import pathlib
import subprocess
import sys

from repos import REPOS
from tasks import load_backlog, pending_count, done_count

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("runner")

AGENT_DIR = pathlib.Path(__file__).parent
OUTPUT_FILE = AGENT_DIR / ".productionizer-output.json"
STATE_FILE = AGENT_DIR / "state.json"

MAX_OPEN_PRS_PER_REPO = 15


def run_shell(cmd: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def run_task(task_id: str | None = None) -> int:
    env = os.environ.copy()
    if task_id:
        env["FORCE_TASK_ID"] = task_id
    result = subprocess.run(
        [sys.executable, str(AGENT_DIR / "main.py")],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        log.info(result.stdout.strip())
    if result.stderr:
        log.info(result.stderr.strip())
    return result.returncode


def open_pr_count(github_repo: str) -> int:
    try:
        result = run_shell([
            "gh", "pr", "list",
            "--repo", github_repo,
            "--state", "open",
            "--json", "number",
            "--jq", "length",
        ], check=False)
        return int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
    except Exception:
        return 0


def push_and_create_prs(pat: str) -> bool:
    if not OUTPUT_FILE.exists():
        log.warning("No output file — skipping PR creation")
        return True

    try:
        output = json.loads(OUTPUT_FILE.read_text())
        prs = output.get("prs", [])
        branch = output.get("branch", "")

        if not prs or not branch:
            log.error("Incomplete output file: %s", output)
            return False

        for pr in prs:
            repo_slug = pr["repo"]          # e.g. "rodmen07/infraportal"
            repo_branch = pr["branch"]
            title = pr["title"]
            body = pr["body"]

            # Find local repo path from the slug
            cfg = next((c for c in REPOS.values() if c.github_repo == repo_slug), None)
            if not cfg:
                log.warning("No local repo found for %s — skipping push", repo_slug)
                continue

            git_url = f"https://x-access-token:{pat}@github.com/{repo_slug}.git"

            log.info("Pushing %s → %s", repo_branch, repo_slug)
            run_shell(
                ["git", "-C", str(cfg.path), "push", git_url, f"{repo_branch}:{repo_branch}"],
                check=False,
            )

            log.info("Creating PR: %s", title)
            run_shell([
                "gh", "pr", "create",
                "--repo", repo_slug,
                "--base", "main",
                "--head", repo_branch,
                "--title", title,
                "--body", body,
            ], check=False)

        OUTPUT_FILE.unlink(missing_ok=True)
        return True

    except Exception as exc:
        log.error("push_and_create_prs failed: %s", exc)
        return False


def update_readme(backlog_state: dict) -> None:
    try:
        result = run_shell(
            [sys.executable, str(AGENT_DIR / "update_readme.py")],
            check=False,
        )
        if result.returncode == 0:
            log.info("README updated")
        else:
            log.warning("README update failed: %s", result.stderr[:500])
    except Exception as exc:
        log.warning("README update exception: %s", exc)


def save_run_state() -> None:
    state = {"last_run": datetime.datetime.now(datetime.UTC).isoformat()}
    STATE_FILE.write_text(json.dumps(state, indent=2))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-task-id", help="Run exactly this task ID once")
    args = parser.parse_args()

    pat = os.environ.get("GITHUB_PAT") or os.environ.get("INFRAPORTAL_PAT", "")
    if not pat:
        log.error("GITHUB_PAT not set")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    if args.force_task_id:
        log.info("Running forced task: %s", args.force_task_id)
        exit_code = run_task(args.force_task_id)
        if exit_code == 0:
            push_and_create_prs(pat)
        sys.exit(0)

    # Full loop
    tasks_this_run = 0

    while True:
        backlog = load_backlog()
        pending = pending_count(backlog)
        done = done_count(backlog)

        if pending == 0:
            log.info("No pending tasks. Done=%d. Run planner.py to generate more.", done)
            break

        log.info("Backlog: %d pending, %d done", pending, done)

        # Check open PR count across repos of the next task
        next_task = next((t for t in backlog if t.status == "pending"), None)
        if next_task:
            for repo_name in next_task.repos:
                cfg = REPOS.get(repo_name)
                if cfg:
                    count = open_pr_count(cfg.github_repo)
                    if count >= MAX_OPEN_PRS_PER_REPO:
                        log.warning("%s has %d open PRs (>= %d) — pausing", cfg.github_repo, count, MAX_OPEN_PRS_PER_REPO)
                        save_run_state()
                        sys.exit(0)

        exit_code = run_task()

        if exit_code == 1:
            log.error("Unrecoverable error — stopping")
            sys.exit(1)

        if exit_code == 3:
            log.info("Backlog complete")
            break

        if exit_code == 0:
            push_and_create_prs(pat)
            tasks_this_run += 1
            update_readme({})

    save_run_state()
    log.info("Runner complete. Processed %d tasks this run.", tasks_this_run)
    sys.exit(0)


if __name__ == "__main__":
    main()
