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
import shutil
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
OBS_ACCUMULATOR_FILE = AGENT_DIR / ".obs-accumulator.json"

MAX_OPEN_PRS_PER_REPO = 15


def run_shell(cmd: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def run_task(task_id: str | None = None) -> int:
    env = os.environ.copy()
    if task_id:
        env["FORCE_TASK_ID"] = task_id
    proc = subprocess.Popen(
        [sys.executable, str(AGENT_DIR / "main.py")],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout
    for line in proc.stdout:
        log.info("  │ %s", line.rstrip())
    proc.wait()
    return proc.returncode


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
            repo_slug = pr["repo"]
            repo_branch = pr["branch"]
            title = pr["title"]

            cfg = next((c for c in REPOS.values() if c.github_repo == repo_slug), None)
            if not cfg:
                log.warning("No local repo found for %s — skipping push", repo_slug)
                continue

            git_url = f"https://x-access-token:{pat}@github.com/{repo_slug}.git"

            log.info("  → pushing branch %s to %s", repo_branch, repo_slug)
            push_result = run_shell(
                ["git", "-C", str(cfg.path), "push", git_url, f"{repo_branch}:{repo_branch}"],
                check=False,
            )
            if push_result.returncode != 0:
                log.warning("    push stderr: %s", push_result.stderr.strip()[:300])

            log.info("  → opening PR: %s", title)
            pr_result = run_shell([
                "gh", "pr", "create",
                "--repo", repo_slug,
                "--base", "main",
                "--head", repo_branch,
                "--title", title,
                "--body", pr["body"],
            ], check=False)
            if pr_result.returncode == 0:
                url = pr_result.stdout.strip()
                log.info("  ✓ PR opened: %s", url)
            else:
                log.warning("  PR creation output: %s", (pr_result.stdout + pr_result.stderr).strip()[:300])

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


def accumulate_observability() -> None:
    """Accumulate observability data from .observability.json into accumulator."""
    if not OUTPUT_FILE.parent.joinpath(".observability.json").exists():
        return

    try:
        obs_file = OUTPUT_FILE.parent.joinpath(".observability.json")
        obs_data = json.loads(obs_file.read_text())

        # Load or initialize accumulator
        if OBS_ACCUMULATOR_FILE.exists():
            acc_data = json.loads(OBS_ACCUMULATOR_FILE.read_text())
        else:
            acc_data = {
                "tasks": [],
                "run_start": obs_data.get("run_start"),
                "summary": {
                    "total_tasks_attempted": 0,
                    "total_tasks_completed": 0,
                    "total_tasks_succeeded": 0,
                    "total_tasks_skipped": 0,
                    "total_tasks_failed": 0,
                    "total_elapsed_sec": 0.0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_tokens": 0,
                    "total_estimated_cost_usd": 0.0,
                    "avg_task_time_sec": 0.0,
                    "success_rate": 0.0,
                    "tool_calls_total": 0,
                    "tool_calls_failed_total": 0,
                },
            }

        # Add new tasks to accumulator
        for task in obs_data.get("tasks", []):
            acc_data["tasks"].append(task)

        # Update summary (simplified — just sum the metrics)
        s = acc_data["summary"]
        s["total_tasks_attempted"] = len(acc_data["tasks"])
        for task in acc_data["tasks"]:
            if task.get("exit_code") == 0:
                s["total_tasks_succeeded"] += 1
            elif task.get("exit_code") == 2:
                s["total_tasks_skipped"] += 1
            elif task.get("exit_code") in (1, 3):
                s["total_tasks_failed"] += 1

            s["total_elapsed_sec"] += task.get("elapsed_sec", 0)
            s["total_input_tokens"] += task.get("input_tokens", 0)
            s["total_output_tokens"] += task.get("output_tokens", 0)
            s["total_tokens"] += task.get("total_tokens", 0)
            s["total_estimated_cost_usd"] += task.get("estimated_cost_usd", 0)
            s["tool_calls_total"] += task.get("tool_calls", 0)
            s["tool_calls_failed_total"] += task.get("tool_calls_failed", 0)

        s["total_tasks_completed"] = s["total_tasks_succeeded"] + s["total_tasks_skipped"]
        if s["total_tasks_completed"] > 0:
            s["avg_task_time_sec"] = s["total_elapsed_sec"] / s["total_tasks_completed"]
            s["success_rate"] = s["total_tasks_succeeded"] / s["total_tasks_completed"]

        acc_data["run_end"] = datetime.datetime.now(datetime.UTC).timestamp()

        OBS_ACCUMULATOR_FILE.write_text(json.dumps(acc_data, indent=2))
        log.debug("Observability accumulator updated")
    except Exception as exc:
        log.warning("Failed to accumulate observability: %s", exc)


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
        log.info("Forced task: %s", args.force_task_id)
        log.info("─" * 60)
        exit_code = run_task(args.force_task_id)
        log.info("─" * 60)
        if exit_code == 0:
            push_and_create_prs(pat)
        accumulate_observability()
        if OBS_ACCUMULATOR_FILE.exists():
            shutil.copy(OBS_ACCUMULATOR_FILE, OUTPUT_FILE.parent / ".observability.json")
        sys.exit(0)

    # Full loop
    tasks_this_run = 0
    task_num = 0

    while True:
        backlog = load_backlog()
        pending = pending_count(backlog)
        done = done_count(backlog)
        total = len(backlog)

        if pending == 0:
            log.info("Backlog empty — done=%d/%d. Run planner.py to generate more.", done, total)
            break

        next_task = next((t for t in backlog if t.status == "pending"), None)
        if not next_task:
            break

        task_num += 1
        log.info("━" * 60)
        log.info("Task %d  [%s]", task_num, next_task.id)
        log.info("  title:      %s", next_task.title)
        log.info("  dimension:  %s", next_task.dimension)
        log.info("  repos:      %s", ", ".join(next_task.repos))
        log.info("  complexity: %s", next_task.complexity)
        log.info("  backlog:    %d pending, %d done / %d total", pending, done, total)
        log.info("─" * 60)

        # PR guard
        for repo_name in next_task.repos:
            cfg = REPOS.get(repo_name)
            if cfg:
                count = open_pr_count(cfg.github_repo)
                log.info("  open PRs in %s: %d", cfg.github_repo, count)
                if count >= MAX_OPEN_PRS_PER_REPO:
                    log.warning("  ⚠ %s has %d open PRs (limit %d) — pausing", cfg.github_repo, count, MAX_OPEN_PRS_PER_REPO)
                    save_run_state()
                    obs.end_run()
                    obs.save()
                    obs.print_summary()
                    sys.exit(0)

        start = datetime.datetime.now()
        exit_code = run_task()
        elapsed = (datetime.datetime.now() - start).seconds

        log.info("─" * 60)
        if exit_code == 0:
            log.info("  ✓ committed  (%ds)", elapsed)
            push_and_create_prs(pat)
            accumulate_observability()
            tasks_this_run += 1
            update_readme({})
        elif exit_code == 2:
            log.info("  ↷ skipped    (%ds)", elapsed)
            accumulate_observability()
        elif exit_code == 3:
            log.info("  ✓ backlog complete")
            accumulate_observability()
            break
        else:
            log.error("  ✗ error (exit %d) — stopping", exit_code)
            accumulate_observability()
            # Save accumulated result before exiting
            if OBS_ACCUMULATOR_FILE.exists():
                shutil.copy(OBS_ACCUMULATOR_FILE, OUTPUT_FILE.parent / ".observability.json")
            sys.exit(1)

    save_run_state()
    # Copy final accumulated data to .observability.json
    if OBS_ACCUMULATOR_FILE.exists():
        shutil.copy(OBS_ACCUMULATOR_FILE, OUTPUT_FILE.parent / ".observability.json")
        # Log summary
        acc_data = json.loads(OBS_ACCUMULATOR_FILE.read_text())
        s = acc_data["summary"]
        log.info("━" * 60)
        log.info("OBSERVABILITY SUMMARY")
        log.info("━" * 60)
        log.info("Tasks:        %d attempted, %d completed (%d success, %d skip, %d fail)",
                 s["total_tasks_attempted"], s["total_tasks_completed"],
                 s["total_tasks_succeeded"], s["total_tasks_skipped"], s["total_tasks_failed"])
        if s["total_tasks_completed"] > 0:
            log.info("Success Rate: %0.1f%%", s["success_rate"] * 100)
        log.info("Timing:       %0.1fs total, %0.1fs avg per task",
                 s["total_elapsed_sec"], s["avg_task_time_sec"])
        log.info("Tokens:       %d input, %d output, %d total",
                 s["total_input_tokens"], s["total_output_tokens"], s["total_tokens"])
        log.info("Cost:         $%0.2f USD", s["total_estimated_cost_usd"])
        log.info("Tool Calls:   %d total, %d failed",
                 s["tool_calls_total"], s["tool_calls_failed_total"])
        log.info("━" * 60)
    log.info("Runner finished. Committed %d task(s) this run.", tasks_this_run)
    sys.exit(0)


if __name__ == "__main__":
    main()
