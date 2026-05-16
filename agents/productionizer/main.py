"""
Productionizer agent — single task executor.

Each invocation:
  1. Picks the next pending task from backlog.yaml (or uses FORCE_TASK_ID)
  2. Creates git branches in all affected repos
  3. Runs the agentic loop with configured LLM (Claude or GPT) reading/writing files via tools
  4. Verifies each affected repo with its language-appropriate verification command
  5. On success: commits changes, writes .productionizer-output.json
  6. Updates task status in backlog.yaml

Exit codes:
  0 = task completed and committed; output file written; push + PR needed
  1 = unrecoverable error; stop the loop
  2 = task skipped (no changes or verification failed); continue to next
  3 = backlog empty; stop the loop

Usage:
  # Using GPT-4o Mini (default, cheapest)
  OPENAI_API_KEY=...  python main.py
  
  # Using Claude Haiku
  ANTHROPIC_API_KEY=...  LLM_MODEL=claude-haiku-4-5-20251001  python main.py
  
  # Force a specific task
  OPENAI_API_KEY=...  FORCE_TASK_ID=frontend-ui-ux-abc12345  python main.py

Environment variables:
  OPENAI_API_KEY          — Required for GPT models
  ANTHROPIC_API_KEY       — Required for Claude models
  LLM_MODEL               — Model to use (default: gpt-4o-mini)
  FORCE_TASK_ID           — Force execution of specific task ID
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import pathlib
import subprocess
import sys
import time

from llm_client import UnifiedLLMClient

from observability import Observability, TaskMetrics
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

# Model selection (can be overridden via LLM_MODEL env var)
# Options: "gpt-4o-mini" (recommended, cheapest), "claude-haiku-3-5-sonnet-20241022", etc.
AGENT_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")


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

def agent_loop(task: Task, metrics: TaskMetrics) -> str | None:
    model = AGENT_MODEL
    log.info("Model: %s", model)

    client = UnifiedLLMClient(model)
    log.info("Provider: %s", client.provider)
    
    dispatch = make_dispatch()
    system_prompt = build_system_prompt(task.repos)
    user_prompt = build_task_prompt(task)

    messages: list[dict] = [{"role": "user", "content": user_prompt}]
    summary: str | None = None

    for round_num in range(MAX_TOOL_ROUNDS):
        response = client.create_message(
            system=system_prompt,
            messages=messages,
            tools=TOOL_DEFINITIONS if TOOL_DEFINITIONS else None,
            max_tokens=8096,
        )

        # Track token usage
        metrics.input_tokens += response.input_tokens
        metrics.output_tokens += response.output_tokens

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                    summary = block["text"].strip()
                    break
                elif hasattr(block, "text") and block.text and block.text.strip():
                    summary = block.text.strip()
                    break
            log.info("Agent concluded after %d rounds", round_num + 1)
            break

        if response.stop_reason != "tool_use":
            log.warning("Unexpected stop_reason: %s", response.stop_reason)
            break

        tool_results = []
        for block in response.content:
            block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
            if block_type != "tool_use":
                continue
            
            fn_name = block.get("name") if isinstance(block, dict) else getattr(block, "name", None)
            fn_input = block.get("input") if isinstance(block, dict) else getattr(block, "input", {})
            fn_args = dict(fn_input) if fn_input else {}
            block_id = block.get("id") if isinstance(block, dict) else getattr(block, "id", None)
            
            log.info("  [%d] %s(%s)", round_num + 1, fn_name, list(fn_args.keys()))

            success = True
            try:
                result_text = dispatch[fn_name](fn_args) if fn_name in dispatch else f"ERROR: unknown tool '{fn_name}'"
                if result_text.startswith("ERROR"):
                    success = False
            except Exception as exc:
                result_text = f"ERROR: {fn_name} raised {exc}"
                success = False

            metrics.record_tool_call(fn_name, success)
            log.debug("  result: %.300s", result_text)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block_id,
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
    obs = Observability(model=AGENT_MODEL)
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

    # Create metrics tracker for this task
    metrics = obs.start_task(task.id, task.title)
    start_time = time.time()
    exit_code = EXIT_ERROR

    try:
        summary = agent_loop(task, metrics)

        affected_repos = [r for r in task.repos if has_changes(r)]

        if not affected_repos:
            log.info("No file changes — skipping")
            task.status = "skipped"
            task.completed_at = datetime.datetime.now(datetime.UTC).isoformat()
            save_backlog(backlog)
            exit_code = EXIT_SKIP
        elif summary and summary.upper().startswith("SKIP:"):
            log.info("Agent reported already satisfied: %s", summary)
            revert_all(task.repos)
            task.status = "skipped"
            task.completed_at = datetime.datetime.now(datetime.UTC).isoformat()
            save_backlog(backlog)
            exit_code = EXIT_SKIP
        else:
            if not summary:
                summary = f"Completed: {task.title}"

            verification_ok = True
            for repo_name in affected_repos:
                ok, error_msg = verify_repo(repo_name)
                metrics.record_verification(ok, error_msg)
                if not ok:
                    verification_ok = False
                    break

            if not verification_ok:
                revert_all(task.repos)
                task.status = "skipped"
                task.completed_at = datetime.datetime.now(datetime.UTC).isoformat()
                save_backlog(backlog)
                exit_code = EXIT_SKIP
            else:
                for repo_name in affected_repos:
                    if not commit_changes(repo_name, task):
                        revert_all(task.repos)
                        exit_code = EXIT_ERROR
                        break

                if exit_code != EXIT_ERROR:
                    write_output(task, branch, affected_repos, summary)
                    task.status = "done"
                    task.completed_at = datetime.datetime.now(datetime.UTC).isoformat()
                    task.summary = summary
                    save_backlog(backlog)
                    log.info("Done: %s", task.title)
                    exit_code = EXIT_COMMITTED

    except subprocess.CalledProcessError as exc:
        log.exception("Git command failed: %s", exc.stderr)
        revert_all(task.repos)
        task.status = "pending"
        save_backlog(backlog)
        metrics.record_error("git_error", str(exc.stderr)[:500])
        exit_code = EXIT_ERROR

    except Exception as exc:
        # Detect transient errors for both providers
        is_transient = False
        
        # Anthropic errors
        try:
            import anthropic
            is_transient = (
                isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500
            ) or isinstance(exc, anthropic.RateLimitError)
        except ImportError:
            pass
        
        # OpenAI errors
        try:
            import openai
            is_transient = (
                isinstance(exc, openai.APIStatusError) and exc.status_code >= 500
            ) or isinstance(exc, openai.RateLimitError)
        except ImportError:
            pass

        if is_transient:
            log.warning("Transient API error — will retry next run: %s", exc)
            revert_all(task.repos)
            task.status = "pending"
            save_backlog(backlog)
            metrics.record_error("transient_api_error", str(exc))
            exit_code = EXIT_SKIP
        else:
            log.exception("Unexpected error: %s", exc)
            revert_all(task.repos)
            task.status = "pending"
            save_backlog(backlog)
            metrics.record_error("unexpected_error", str(exc)[:500])
            exit_code = EXIT_ERROR

    finally:
        # Record metrics and save observability
        elapsed = time.time() - start_time
        obs.record_task_complete(
            metrics,
            exit_code,
            elapsed,
            metrics.input_tokens,
            metrics.output_tokens,
        )
        obs.save()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
