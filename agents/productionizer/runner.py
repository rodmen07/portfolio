#!/usr/bin/env python3
"""
Standalone productionizer runner — decoupled from GitHub Actions.

Handles the full task loop (all 30 tasks or until error), including:
  - Task selection and branching
  - Agent invocation per task
  - PR creation and push
  - README update
  - State persistence

Usage:
  GOOGLE_API_KEY=...  INFRAPORTAL_PAT=...  python runner.py [--force-page X] [--force-gap Y]

Environment variables:
  GOOGLE_API_KEY        required, Gemini API key
  INFRAPORTAL_PAT       required, GitHub token with full repo access
  FORCE_PAGE            optional, override page selection
  FORCE_GAP             optional, override gap selection

Exit codes:
  0 = completed all tasks or reached stop condition gracefully
  1 = unrecoverable error
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import pathlib
import subprocess
import sys

from tasks import build_task_queue, pick_next_task
from update_readme import build_progress_section

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("productionizer-runner")

# Paths
AGENT_DIR = pathlib.Path(__file__).resolve().parent
STATE_FILE = AGENT_DIR / "state.json"
OUTPUT_FILE = AGENT_DIR / ".productionizer-output.json"
INFRAPORTAL_ROOT = AGENT_DIR.parent.parent / "infraportal"
PORTFOLIO_ROOT = AGENT_DIR.parent.parent.parent


def load_state() -> dict:
    """Load completion state from state.json."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"completed": [], "recent_summaries": [], "last_run": None}


def save_state(state: dict) -> None:
    """Persist state to state.json."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


def run_shell_cmd(
    cmd: list[str], cwd: str | pathlib.Path | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command and return result."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=check,
        )
        return result
    except subprocess.CalledProcessError as e:
        log.error("Command failed: %s\nstderr: %s", " ".join(cmd), e.stderr)
        raise


def run_task(page: str, gap: str) -> int:
    """
    Run a single task via main.py.
    Returns exit code from main.py (0, 1, 2, or 3).
    """
    env = os.environ.copy()
    env["FORCE_PAGE"] = page
    env["FORCE_GAP"] = gap
    
    log.info("Running task: %s / %s", page, gap)
    result = subprocess.run(
        [sys.executable, str(AGENT_DIR / "main.py")],
        env=env,
        capture_output=True,
        text=True,
    )
    
    return result.returncode


def push_pr_and_update_readme(state: dict) -> bool:
    """
    Read output.json (if it exists), push branch, create PR, update README.
    Returns True if all succeeded.
    """
    if not OUTPUT_FILE.exists():
        log.warning("No output file found — skipping PR creation")
        return True
    
    try:
        output = json.loads(OUTPUT_FILE.read_text())
        branch = output.get("branch")
        title = output.get("pr_title")
        body = output.get("pr_body")
        
        if not all([branch, title, body]):
            log.error("Incomplete output.json: %s", output)
            return False
        
        pat = os.environ.get("INFRAPORTAL_PAT", "").strip()
        if not pat:
            log.error("INFRAPORTAL_PAT not set")
            return False
        
        # Push branch
        log.info("Pushing branch: %s", branch)
        git_url = f"https://x-access-token:{pat}@github.com/rodmen07/infraportal.git"
        try:
            run_shell_cmd(
                ["git", "-C", str(INFRAPORTAL_ROOT), "push", git_url, f"{branch}:{branch}"],
                check=False,
            )
        except Exception as e:
            log.error("Failed to push branch: %s", e)
            return False
        
        # Create PR using gh
        log.info("Creating PR: %s", title)
        try:
            run_shell_cmd([
                "gh", "pr", "create",
                "--repo", "rodmen07/infraportal",
                "--base", "main",
                "--head", branch,
                "--title", title,
                "--body", body,
            ], check=False)
        except Exception as e:
            log.warning("Failed to create PR (may already exist): %s", e)
        
        # Update README
        log.info("Updating infraportal README")
        try:
            run_shell_cmd(["git", "-C", str(INFRAPORTAL_ROOT), "fetch", "origin", "main"])
            run_shell_cmd(["git", "-C", str(INFRAPORTAL_ROOT), "checkout", "main"])
            
            # Generate new README content
            readme_file = INFRAPORTAL_ROOT / "README.md"
            if readme_file.exists():
                readme = readme_file.read_text()
                new_section = build_progress_section(state)
                
                # Update between markers
                marker_start = "<!-- PRODUCTIONIZER:START -->"
                marker_end = "<!-- PRODUCTIONIZER:END -->"
                if marker_start in readme and marker_end in readme:
                    start_idx = readme.index(marker_start)
                    end_idx = readme.index(marker_end) + len(marker_end)
                    new_readme = readme[:start_idx] + new_section + readme[end_idx:]
                else:
                    new_readme = readme.rstrip() + "\n\n" + new_section + "\n"
                
                readme_file.write_text(new_readme)
                
                # Commit README if changed
                run_shell_cmd(["git", "-C", str(INFRAPORTAL_ROOT), "add", "README.md"], check=False)
                status = run_shell_cmd(
                    ["git", "-C", str(INFRAPORTAL_ROOT), "diff", "--cached", "--quiet"],
                    check=False,
                )
                if status.returncode != 0:  # Files were staged
                    run_shell_cmd([
                        "git", "-C", str(INFRAPORTAL_ROOT),
                        "commit", "-m", "docs: productionizer progress update [skip ci]"
                    ], check=False)
                    run_shell_cmd([
                        "git", "-C", str(INFRAPORTAL_ROOT), "push", git_url, "main:main"
                    ], check=False)
        except Exception as e:
            log.warning("Failed to update README: %s", e)
        
        OUTPUT_FILE.unlink()
        return True
    
    except Exception as e:
        log.error("Error in push_pr_and_update_readme: %s", e)
        return False


def main() -> None:
    """
    Main runner loop: process all remaining tasks until completion or error.
    """
    state = load_state()
    
    # Check for forced task
    force_page = os.environ.get("FORCE_PAGE", "").strip()
    force_gap = os.environ.get("FORCE_GAP", "").strip()
    
    if force_page and force_gap:
        # Single forced task
        log.info("Running forced task: %s / %s", force_page, force_gap)
        exit_code = run_task(force_page, force_gap)
        
        if exit_code == 0:
            push_pr_and_update_readme(state)
        
        sys.exit(0)
    
    # Full loop: process all remaining tasks
    task_queue = build_task_queue()
    completed_set = {(page, gap) for page, gap in state.get("completed", [])}
    
    log.info("Starting productionizer loop: %d tasks total, %d completed", 
             len(task_queue), len(completed_set))
    
    open_pr_count = 0
    tasks_this_run = 0
    max_open_prs = 25
    
    for page, gap in task_queue:
        if (page, gap) in completed_set:
            continue  # Already done
        
        log.info("=== Processing task %d/%d: %s / %s ===", 
                 len(completed_set) + 1, len(task_queue), page, gap)
        
        # Check open PR count
        try:
            result = run_shell_cmd([
                "gh", "pr", "list",
                "--repo", "rodmen07/infraportal",
                "--state", "open",
                "--json", "number",
                "--jq", "length"
            ], check=False)
            open_pr_count = int(result.stdout.strip()) if result.stdout.strip() else 0
            
            if open_pr_count >= max_open_prs:
                log.warning("Open PRs (%d) >= max (%d). Pausing.", open_pr_count, max_open_prs)
                break
        except Exception as e:
            log.warning("Could not check PR count: %s", e)
        
        # Run task
        exit_code = run_task(page, gap)
        
        if exit_code == 1:
            log.error("Task reported error — stopping")
            sys.exit(1)
        
        if exit_code == 3:
            log.info("Task reported all done (shouldn't happen in loop)")
            break
        
        if exit_code == 0:
            # Task succeeded — push PR and update README
            if push_pr_and_update_readme(state):
                tasks_this_run += 1
                # Reload state for next iteration
                state = load_state()
                completed_set = {(page, gap) for page, gap in state.get("completed", [])}
        
        # exit_code == 2 means skip; state already updated in main.py
        if exit_code == 2:
            state = load_state()
            completed_set = {(page, gap) for page, gap in state.get("completed", [])}
    
    log.info("Productionizer loop complete. Processed %d tasks this run.", tasks_this_run)
    
    # Final state save
    state["last_run"] = datetime.datetime.now(datetime.UTC).isoformat()
    save_state(state)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
