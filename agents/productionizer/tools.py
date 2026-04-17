"""
Tool implementations exposed to the Gemini agent -- infraportal edition.
Three tools: read_file, write_file, run_shell.
All paths are relative to the infraportal/ root.
"""

import pathlib
import subprocess

from google.genai import types

# ---------------------------------------------------------------------------
# Workspace root
# ---------------------------------------------------------------------------

_PORTFOLIO_ROOT = pathlib.Path(__file__).parent.parent.parent
INFRAPORTAL_ROOT = _PORTFOLIO_ROOT / "infraportal"

# ---------------------------------------------------------------------------
# Guard lists
# ---------------------------------------------------------------------------

_FORBIDDEN_WRITE_SUBSTRINGS = [
    "package.json",
    "package-lock.json",
    ".github/",
    "node_modules/",
    "dist/",
    "tsconfig",
    "vite.config",
    "eslint.config",
    "tailwind.config",
    "postcss.config",
    "index.html",
    "public/",
]

_BLOCKED_SHELL_PREFIXES = [
    "git ",
    "rm ",
    "mv ",
    "cp ",
    "curl ",
    "wget ",
    "sudo ",
    "npm install",
    "npm run dev",
    "npm run build",
    "npx vite",
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def read_file(path: str) -> str:
    """Read a file from the infraportal workspace."""
    target = INFRAPORTAL_ROOT / path
    try:
        return target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"ERROR: file not found: {path}"
    except Exception as exc:
        return f"ERROR reading {path}: {exc}"


def write_file(path: str, content: str, allowed_file: str) -> str:
    """Write (overwrite) the assigned page file in the infraportal workspace.

    Guards:
    - Forbidden path substrings (package.json, .github/, etc.)
    - Must be exactly the allowed_file for this task
    """
    # Guard: forbidden paths
    for forbidden in _FORBIDDEN_WRITE_SUBSTRINGS:
        if forbidden in path:
            return f"ERROR: writes to paths containing '{forbidden}' are forbidden by policy."

    # Guard: must be the assigned page file
    if path != allowed_file:
        return (
            f"ERROR: only '{allowed_file}' may be written for this task. "
            f"Path given: {path}"
        )

    # Sanitize Unicode smart quotes that LLMs sometimes emit.
    content = (
        content
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )

    target = INFRAPORTAL_ROOT / path
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} bytes to {path}"
    except Exception as exc:
        return f"ERROR writing {path}: {exc}"


def run_shell(command: str) -> str:
    """Run an inspection or verification command inside the infraportal/ directory."""
    stripped = command.strip()
    for blocked in _BLOCKED_SHELL_PREFIXES:
        if stripped.startswith(blocked):
            return (
                f"ERROR: '{blocked.strip()}' commands are blocked by policy. "
                "Use read_file / write_file for file operations."
            )

    try:
        result = subprocess.run(
            stripped,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(INFRAPORTAL_ROOT),
            timeout=120,
        )
        output = (result.stdout + result.stderr)[:8000]
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 120 seconds"
    except Exception as exc:
        return f"ERROR running shell command: {exc}"


# ---------------------------------------------------------------------------
# Gemini tool definitions (google.genai types)
# ---------------------------------------------------------------------------

def build_tool_declaration() -> types.Tool:
    """Return the Gemini Tool describing the three agent tools."""
    return types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="read_file",
            description=(
                "Read the complete contents of a file in the infraportal workspace. "
                "Paths are relative to the infraportal/ root. "
                "Always read ALL relevant files before making any writes."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Relative path from infraportal/ root, e.g. "
                            "'src/pages/AuditPage.tsx' or 'src/types.ts'"
                        ),
                    }
                },
                "required": ["path"],
            },
        ),
        types.FunctionDeclaration(
            name="write_file",
            description=(
                "Write (overwrite) the COMPLETE contents of the assigned page file. "
                "Always provide the entire file, never a diff or partial content. "
                "Only the assigned page file may be written. "
                "Paths are relative to the infraportal/ root."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from infraportal/ root.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete file contents to write.",
                    },
                },
                "required": ["path", "content"],
            },
        ),
        types.FunctionDeclaration(
            name="run_shell",
            description=(
                "Run a shell command inside the infraportal/ directory. "
                "Use for: `npx tsc --noEmit` (type-check all files), "
                "`npx eslint src/pages/<File>.tsx --max-warnings=0` (lint one file), "
                "`grep -n 'pattern' src/pages/<File>.tsx` (search). "
                "Do NOT use git, rm, mv, cp, curl, wget, npm install, or npm run build."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run.",
                    }
                },
                "required": ["command"],
            },
        ),
    ])


def make_dispatch(allowed_file: str) -> dict:
    """Return a dispatch dict that closes over allowed_file for write_file."""
    return {
        "read_file": lambda args: read_file(args["path"]),
        "write_file": lambda args: write_file(args["path"], args["content"], allowed_file),
        "run_shell": lambda args: run_shell(args["command"]),
    }
