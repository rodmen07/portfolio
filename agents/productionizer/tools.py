"""
Agent tools for the fullstack productionizer — multi-repo, Claude API format.
"""
from __future__ import annotations

import pathlib
import subprocess

from repos import REPOS


def _sanitize(content: str) -> str:
    return (
        content
        .replace("“", '"').replace("”", '"')
        .replace("‘", "'").replace("’", "'")
        .replace("«", '"').replace("»", '"')
        .replace("‹", "'").replace("›", "'")
        .replace("–", "-").replace("—", "-")
        .replace("…", "...").replace(" ", " ")
        .replace("​", "").replace("‌", "")
        .replace("‍", "").replace("﻿", "")
    )


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def read_file(repo: str, path: str) -> str:
    cfg = REPOS.get(repo)
    if not cfg:
        return f"ERROR: unknown repo '{repo}'. Available: {sorted(REPOS)}"
    target = cfg.path / path
    try:
        return target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"ERROR: file not found: {repo}/{path}"
    except Exception as exc:
        return f"ERROR reading {repo}/{path}: {exc}"


def write_file(repo: str, path: str, content: str) -> str:
    cfg = REPOS.get(repo)
    if not cfg:
        return f"ERROR: unknown repo '{repo}'"

    for forbidden in cfg.forbidden_write_paths:
        if forbidden in path:
            return f"ERROR: writes to paths containing '{forbidden}' are forbidden in {repo}."

    lower = path.lower()
    if any(s in lower for s in [".env", "secret", "credential", "id_rsa", "id_ed25519"]):
        return f"ERROR: writing to '{path}' is forbidden (potential secrets file)."

    content = _sanitize(content)
    target = cfg.path / path
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} bytes to {repo}/{path}"
    except Exception as exc:
        return f"ERROR writing {repo}/{path}: {exc}"


def list_files(repo: str, path: str = ".") -> str:
    cfg = REPOS.get(repo)
    if not cfg:
        return f"ERROR: unknown repo '{repo}'"
    target = cfg.path / path
    try:
        entries = sorted(target.iterdir(), key=lambda e: (e.is_file(), e.name))
        lines = []
        for e in entries:
            rel = e.relative_to(cfg.path)
            lines.append(f"{rel}{'/' if e.is_dir() else ''}")
        return "\n".join(lines) or "(empty directory)"
    except FileNotFoundError:
        return f"ERROR: path not found: {repo}/{path}"
    except Exception as exc:
        return f"ERROR listing {repo}/{path}: {exc}"


def run_shell(repo: str, command: str) -> str:
    cfg = REPOS.get(repo)
    if not cfg:
        return f"ERROR: unknown repo '{repo}'"

    stripped = command.strip()
    for blocked in cfg.forbidden_shell_prefixes:
        if stripped.startswith(blocked):
            return f"ERROR: '{blocked.strip()}' commands are blocked in {repo}."

    try:
        result = subprocess.run(
            stripped,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(cfg.path),
            timeout=180,
        )
        output = (result.stdout + result.stderr)[:10_000]
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 180 seconds"
    except Exception as exc:
        return f"ERROR running command: {exc}"


# ---------------------------------------------------------------------------
# Claude API tool definitions
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": (
            "Read the complete contents of a file from any repo in the portfolio. "
            "Always read relevant files before making any writes. "
            "Read related files (types, interfaces, models, routes) for full context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": f"Repo name. One of: {sorted(REPOS)}",
                },
                "path": {
                    "type": "string",
                    "description": (
                        "Path relative to the repo root. "
                        "e.g. 'src/pages/Dashboard.tsx', 'src/handlers/accounts.rs', 'internal/proxy/proxy.go'"
                    ),
                },
            },
            "required": ["repo", "path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write (overwrite) a file in any repo. "
            "Always provide COMPLETE file contents — never partial diffs, snippets, or "
            "'rest of file unchanged' placeholders. "
            "Read the file first if it already exists. "
            "After writing, verify with run_shell (tsc, cargo check, go build, py_compile)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repo name."},
                "path": {"type": "string", "description": "Path relative to repo root."},
                "content": {"type": "string", "description": "Complete file contents."},
            },
            "required": ["repo", "path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": (
            "List files and directories at a path within a repo. "
            "Use to explore codebase structure before reading specific files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repo name."},
                "path": {
                    "type": "string",
                    "description": "Directory path relative to repo root. Default: '.' (repo root).",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "run_shell",
        "description": (
            "Run a shell command inside a repo directory. "
            "Use for verification: 'npx tsc --noEmit', 'cargo check', 'go build ./...', "
            "'go vet ./...', 'python -m py_compile <file>'. "
            "Use for exploration: 'grep -rn pattern src/', 'find src -name *.rs', 'cat Cargo.toml'. "
            "Do NOT use: git, rm, mv, cp, curl, wget, sudo, npm install, pip install, cargo install."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repo name."},
                "command": {"type": "string", "description": "Shell command to run."},
            },
            "required": ["repo", "command"],
        },
    },
]


def make_dispatch() -> dict:
    return {
        "read_file":  lambda args: read_file(args["repo"], args["path"]),
        "write_file": lambda args: write_file(args["repo"], args["path"], args["content"]),
        "list_files": lambda args: list_files(args["repo"], args.get("path", ".")),
        "run_shell":  lambda args: run_shell(args["repo"], args["command"]),
    }
