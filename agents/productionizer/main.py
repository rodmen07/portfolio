"""
Productionizer agent — single task executor.

Each invocation:
  1. Picks the next pending task from backlog.yaml (or uses FORCE_TASK_ID)
  2. Creates git branches in all affected repos
  3. Runs the Claude agentic loop (reads/writes files via tools)
  4. Verifies each affected repo with its language-appropriate verification command
  5. On success: commits changes, writes .productionizer-output.json
  6. Updates task status in backlog.yaml

Exit codes:
  0 = task completed and committed; output file written; push + PR needed
  1 = unrecoverable error; stop the loop
  2 = task skipped (no changes or verification failed); continue to next
  3 = backlog empty; stop the loop

Usage:
  ANTHROPIC_API_KEY=...  python main.py
  ANTHROPIC_API_KEY=...  FORCE_TASK_ID=frontend-ui-ux-abc12345  python main.py
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import pathlib
import subprocess
import sys

import anthropic

from prompts import build_system_prompt, build_task_prompt
from repos import REPOS
from tasks import Task, load_backlog, save_backlog, pick_next_task
from tools import TOOL_DEFINITIONS, make_dispatch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("productionizer")

AGENT_DIR = pathlib.Path(__file__).parent
OUTPUT_FILE = AGENT_DIR / ".productionizer-output.json"
MAX_TOOL_ROUNDS = 60

EXIT_COMMITTED = 0
EXIT_ERROR     = 1
EXIT_SKIP      = 2
EXIT_DONE      = 3

MODEL_MAP = {
    "low":    "claude-haiku-4-5-20251001",
    "medium": "claude-sonnet-4-6",
    "high":   "claude-opus-4-7",
}


# ---------------------------------------------------------------------------
# Git helpers (per-repo)
# ---------------------------------------------------------------------------

def git(repo_name: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cfg = REPOS[repo_name]
    return subprocess.run(
        ["git", *args],
        cwd=str(cfg.path),
        capture_output=True,
        text=True,
        check=check,
    )


def branch_name(task: Task) -> str:
    date = datetime.date.today().strftime("%Y%m%d")
    slug = task.title.lower()[:50]
    slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")
    slug = "-".join(p for p in slug.split("-") if p)[:45]
    return f"productionizer/{date}/{slug}"


def branch_exists_on_remote(repo_name: str, branch: str) -> bool:
    result = git(repo_name, "ls-remote", "--heads", "origin", branch, check=False)
    return bool(result.stdout.strip())


def create_branch(repo_name: str, branch: str) -> bool:
    log.info("[%s] creating branch: %s", repo_name, branch)
    try:
        git(repo_name, "fetch", "origin", "main")
        git(repo_name, "checkout", "-B", branch, "origin/main")
        return True
    except subprocess.CalledProcessError as exc:
        log.error("[%s] branch creation failed: %s", repo_name, exc.stderr)
        return False


def has_changes(repo_name: str) -> bool:
    result = git(repo_name, "status", "--porcelain", check=False)
    return bool(result.stdout.strip())


def commit_changes(repo_name: str, task: Task) -> bool:
    try:
        git(repo_name, "add", "-A")
        msg = (
            f"feat({task.dimension}): {task.title}\n\n"
            f"Automated fullstack change by the productionizer agent.\n"
            f"Task ID: {task.id}\n"
            f"Repos: {', '.join(task.repos)}"
        )
        git(repo_name, "commit", "-m", msg)
        log.info("[%s] committed", repo_name)
        return True
    except subprocess.CalledProcessError as exc:
        log.error("[%s] commit failed: %s", repo_name, exc.stderr)
        return False


def revert_all(repos: list[str]) -> None:
    for repo_name in repos:
        try:
            git(repo_name, "checkout", "HEAD", "--", ".", check=False)
            git(repo_name, "clean", "-fd", check=False)
            log.info("[%s] reverted", repo_name)
        except Exception as exc:
            log.warning("[%s] revert failed: %s", repo_name, exc)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_repo(repo_name: str) -> tuple[bool, str]:
    cfg = REPOS[repo_name]
    for cmd in cfg.verify_commands:
        log.info("[%s] verifying: %s", repo_name, cmd)
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(cfg.path),
                timeout=300,
            )
            output = (result.stdout + result.stderr)[:10_000]
            if result.returncode != 0:
                log.error("[%s] FAILED (%s):\n%s", repo_name, cmd, output)
                return False, output
            log.info("[%s] ✓ %s", repo_name, cmd)
        except subprocess.TimeoutExpired:
            msg = f"[{repo_name}] timed out: {cmd}"
            log.error(msg)
            return False, msg
    return True, ""


# ---------------------------------------------------------------------------
# Claude agentic loop
# ---------------------------------------------------------------------------

def agent_loop(task: Task) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set")
        return None

    model = MODEL_MAP.get(task.complexity, MODEL_MAP["medium"])
    log.info("Model: %s (complexity=%s)", model, task.complexity)

    client = anthropic.Anthropic(api_key=api_key)
    dispatch = make_dispatch()
    system_prompt = build_system_prompt(task.repos)
    user_prompt = build_task_prompt(task)

    messages: list[dict] = [{"role": "user", "content": user_prompt}]
    summary: str | None = None

    for round_num in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=model,
            max_tokens=8096,
            system=system_prompt,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text") and block.text.strip():
                    summary = block.text.strip()
                    break
            log.info("Agent concluded after %d rounds", round_num + 1)
            break

        if response.stop_reason != "tool_use":
            log.warning("Unexpected stop_reason: %s", response.stop_reason)
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            fn_name = block.name
            fn_args = dict(block.input) if block.input else {}
            log.info("  [%d] %s(%s)", round_num + 1, fn_name, list(fn_args.keys()))

            try:
                result_text = dispatch[fn_name](fn_args) if fn_name in dispatch else f"ERROR: unknown tool '{fn_name}'"
            except Exception as exc:
                result_text = f"ERROR: {fn_name} raised {exc}"

            log.debug("  result: %.300s", result_text)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })

        messages.append({"role": "user", "content": tool_results})
    else:
        log.error("Agent exhausted %d rounds without concluding", MAX_TOOL_ROUNDS)

    return summary


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_output(task: Task, branch: str, affected_repos: list[str], summary: str) -> None:
    prs = []
    for repo_name in affected_repos:
        cfg = REPOS[repo_name]
        verify_lines = "\n".join(f"- `{cmd}` passed" for cmd in cfg.verify_commands)
        prs.append({
            "repo": cfg.github_repo,
            "branch": branch,
            "title": f"feat({task.dimension}): {task.title}",
            "body": (
                f"## Summary\n\n{summary}\n\n"
                f"## Task\n\n"
                f"- **ID**: `{task.id}`\n"
                f"- **Dimension**: `{task.dimension}`\n"
                f"- **Repos**: {', '.join(f'`{r}`' for r in task.repos)}\n\n"
                f"## Verification\n\n{verify_lines}\n\n"
                f"> Generated by the productionizer agent — review before merging."
            ),
        })
    OUTPUT_FILE.write_text(json.dumps({
        "task_id": task.id,
        "branch": branch,
        "summary": summary,
        "prs": prs,
    }, indent=2))
    log.info("Output written to %s", OUTPUT_FILE)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    backlog = load_backlog()

    force_id = os.environ.get("FORCE_TASK_ID", "").strip()
    if force_id:
        task = next((t for t in backlog if t.id == force_id), None)
        if not task:
            log.error("Task not found: %s", force_id)
            sys.exit(EXIT_ERROR)
        log.info("Forced task: [%s] %s", task.id, task.title)
    else:
        task = pick_next_task(backlog)
        if task is None:
            log.info("Backlog empty. Run `python planner.py` to generate more tasks.")
            sys.exit(EXIT_DONE)
        log.info("Next task: [%s] %s", task.id, task.title)

    missing = [r for r in task.repos if r not in REPOS]
    if missing:
        log.error("Unknown repos in task %s: %s", task.id, missing)
        sys.exit(EXIT_ERROR)

    branch = branch_name(task)

    if all(branch_exists_on_remote(r, branch) for r in task.repos):
        log.warning("Branch %s already exists everywhere — marking done", branch)
        task.status = "done"
        save_backlog(backlog)
        sys.exit(EXIT_SKIP)

    for repo_name in task.repos:
        if not create_branch(repo_name, branch):
            revert_all(task.repos)
            sys.exit(EXIT_ERROR)

    task.status = "in_progress"
    save_backlog(backlog)

    try:
        summary = agent_loop(task)

        affected_repos = [r for r in task.repos if has_changes(r)]

        if not affected_repos:
            log.info("No file changes — skipping")
            task.status = "skipped"
            task.completed_at = datetime.datetime.now(datetime.UTC).isoformat()
            save_backlog(backlog)
            sys.exit(EXIT_SKIP)

        if summary and summary.upper().startswith("SKIP:"):
            log.info("Agent reported already satisfied: %s", summary)
            revert_all(task.repos)
            task.status = "skipped"
            task.completed_at = datetime.datetime.now(datetime.UTC).isoformat()
            save_backlog(backlog)
            sys.exit(EXIT_SKIP)

        if not summary:
            summary = f"Completed: {task.title}"

        for repo_name in affected_repos:
            ok, _ = verify_repo(repo_name)
            if not ok:
                revert_all(task.repos)
                task.status = "skipped"
                task.completed_at = datetime.datetime.now(datetime.UTC).isoformat()
                save_backlog(backlog)
                sys.exit(EXIT_SKIP)

        for repo_name in affected_repos:
            if not commit_changes(repo_name, task):
                revert_all(task.repos)
                sys.exit(EXIT_ERROR)

        write_output(task, branch, affected_repos, summary)

        task.status = "done"
        task.completed_at = datetime.datetime.now(datetime.UTC).isoformat()
        task.summary = summary
        save_backlog(backlog)
        log.info("Done: %s", task.title)

    except subprocess.CalledProcessError as exc:
        log.exception("Git command failed: %s", exc.stderr)
        revert_all(task.repos)
        task.status = "pending"
        save_backlog(backlog)
        sys.exit(EXIT_ERROR)

    except Exception as exc:
        is_transient = (
            isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500
        ) or isinstance(exc, anthropic.RateLimitError)

        if is_transient:
            log.warning("Transient API error — will retry next run: %s", exc)
            revert_all(task.repos)
            task.status = "pending"
            save_backlog(backlog)
            sys.exit(EXIT_SKIP)

        log.exception("Unexpected error: %s", exc)
        revert_all(task.repos)
        task.status = "pending"
        save_backlog(backlog)
        sys.exit(EXIT_ERROR)


if __name__ == "__main__":
    main()
