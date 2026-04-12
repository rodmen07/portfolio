"""
Tool implementations exposed to the Gemini agent.
Three tools: read_file, write_file, run_shell.
All paths are relative to the microservices/ root.
"""

import os
import pathlib
import subprocess

import google.generativeai as genai

# ---------------------------------------------------------------------------
# Workspace root
# ---------------------------------------------------------------------------

_PORTFOLIO_ROOT = pathlib.Path(__file__).parent.parent.parent
MICROSERVICES_ROOT = _PORTFOLIO_ROOT / "microservices"

# ---------------------------------------------------------------------------
# Guard lists
# ---------------------------------------------------------------------------

_FORBIDDEN_WRITE_SUBSTRINGS = [
    "auth.rs",
    "Cargo.toml",
    "Cargo.lock",
    ".github/",
]

_BLOCKED_SHELL_PREFIXES = [
    "git ",
    "cargo build",
    "cargo install",
    "rm ",
    "mv ",
    "cp ",
    "curl ",
    "wget ",
    "sudo ",
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def read_file(path: str) -> str:
    """Read a file from the microservices workspace."""
    target = MICROSERVICES_ROOT / path
    try:
        return target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"ERROR: file not found: {path}"
    except Exception as exc:
        return f"ERROR reading {path}: {exc}"


def write_file(path: str, content: str, allowed_service: str) -> str:
    """Write (overwrite) a complete file in the microservices workspace.

    Guards:
    - Forbidden path substrings (auth.rs, Cargo.toml, etc.)
    - Must be within allowed_service/ directory or tests/ directory
    """
    # Guard: forbidden paths
    for forbidden in _FORBIDDEN_WRITE_SUBSTRINGS:
        if forbidden in path:
            return f"ERROR: writes to paths containing '{forbidden}' are forbidden by policy."

    # Guard: must be within the assigned service directory
    if not (path.startswith(f"{allowed_service}/") or path.startswith("tests/")):
        return (
            f"ERROR: writes outside {allowed_service}/ are forbidden for this task. "
            f"Path given: {path}"
        )

    target = MICROSERVICES_ROOT / path
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} bytes to {path}"
    except Exception as exc:
        return f"ERROR writing {path}: {exc}"


def run_shell(command: str) -> str:
    """Run a read-only inspection command inside the microservices/ directory."""
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
            cwd=str(MICROSERVICES_ROOT),
            timeout=60,
        )
        output = (result.stdout + result.stderr)[:8000]
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 60 seconds"
    except Exception as exc:
        return f"ERROR running shell command: {exc}"


# ---------------------------------------------------------------------------
# Gemini tool definitions (genai.protos format)
# ---------------------------------------------------------------------------

def build_tool_declaration() -> genai.protos.Tool:
    """Return the Gemini Tool proto describing the three agent tools."""
    S = genai.protos.Schema
    T = genai.protos.Type

    return genai.protos.Tool(
        function_declarations=[
            genai.protos.FunctionDeclaration(
                name="read_file",
                description=(
                    "Read the complete contents of a file in the microservices workspace. "
                    "Paths are relative to the microservices/ root. "
                    "Always read ALL relevant files before making any writes."
                ),
                parameters=S(
                    type=T.OBJECT,
                    properties={
                        "path": S(
                            type=T.STRING,
                            description=(
                                "Relative path from microservices/ root, e.g. "
                                "'accounts-service/src/lib/handlers/accounts.rs'"
                            ),
                        )
                    },
                    required=["path"],
                ),
            ),
            genai.protos.FunctionDeclaration(
                name="write_file",
                description=(
                    "Write (overwrite) the COMPLETE contents of a file. "
                    "Always provide the entire file, never a diff or partial content. "
                    "Only write files within the assigned service directory. "
                    "Paths are relative to the microservices/ root."
                ),
                parameters=S(
                    type=T.OBJECT,
                    properties={
                        "path": S(
                            type=T.STRING,
                            description="Relative path from microservices/ root.",
                        ),
                        "content": S(
                            type=T.STRING,
                            description="Complete file contents to write.",
                        ),
                    },
                    required=["path", "content"],
                ),
            ),
            genai.protos.FunctionDeclaration(
                name="run_shell",
                description=(
                    "Run a read-only shell command inside the microservices/ directory. "
                    "Use ONLY for inspection: grep, ls, cargo check --message-format=short. "
                    "Do NOT use git, rm, mv, cp, curl, or wget."
                ),
                parameters=S(
                    type=T.OBJECT,
                    properties={
                        "command": S(
                            type=T.STRING,
                            description="Shell command to run (read-only operations only).",
                        )
                    },
                    required=["command"],
                ),
            ),
        ]
    )


def make_dispatch(allowed_service: str) -> dict:
    """Return a dispatch dict that closes over allowed_service for write_file."""
    return {
        "read_file": lambda args: read_file(args["path"]),
        "write_file": lambda args: write_file(args["path"], args["content"], allowed_service),
        "run_shell": lambda args: run_shell(args["command"]),
    }
