"""
Repo registry — maps repo names to their on-disk paths, languages, and verification commands.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

PORTFOLIO_ROOT = pathlib.Path(__file__).parent.parent.parent

_COMMON_FORBIDDEN_SHELL = [
    "rm ", "rm\t",
    "git ",
    "sudo ",
    "curl ",
    "wget ",
    "ssh ",
    "scp ",
]


@dataclass
class RepoConfig:
    name: str
    path: pathlib.Path
    language: str               # "typescript" | "rust" | "go" | "python"
    github_repo: str            # "owner/repo"
    verify_commands: list[str]  # run in order; ALL must pass
    forbidden_write_paths: list[str] = field(default_factory=list)
    forbidden_shell_prefixes: list[str] = field(default_factory=list)


REPOS: dict[str, RepoConfig] = {
    "infraportal": RepoConfig(
        name="infraportal",
        path=PORTFOLIO_ROOT / "infraportal",
        language="typescript",
        github_repo="rodmen07/infraportal",
        verify_commands=[
            "npx tsc --noEmit",
            "npx eslint src --max-warnings=0",
        ],
        forbidden_write_paths=[
            "package.json", "package-lock.json",
            ".github/", "node_modules/", "dist/",
            "tsconfig", "vite.config", "eslint.config",
            "tailwind.config", "postcss.config", "index.html",
        ],
        forbidden_shell_prefixes=_COMMON_FORBIDDEN_SHELL + [
            "npm install", "npm run build", "npm run dev", "npx vite",
        ],
    ),
    "microservices": RepoConfig(
        name="microservices",
        path=PORTFOLIO_ROOT / "microservices",
        language="rust",
        github_repo="rodmen07/microservices",
        verify_commands=["cargo check --workspace"],
        forbidden_write_paths=["Cargo.lock", ".github/"],
        forbidden_shell_prefixes=_COMMON_FORBIDDEN_SHELL + ["cargo install"],
    ),
    "backend-service": RepoConfig(
        name="backend-service",
        path=PORTFOLIO_ROOT / "backend-service",
        language="rust",
        github_repo="rodmen07/backend-service",
        verify_commands=["cargo check"],
        forbidden_write_paths=["Cargo.lock", ".github/"],
        forbidden_shell_prefixes=_COMMON_FORBIDDEN_SHELL + ["cargo install"],
    ),
    "go-gateway": RepoConfig(
        name="go-gateway",
        path=PORTFOLIO_ROOT / "go-gateway",
        language="go",
        github_repo="rodmen07/go-gateway",
        verify_commands=["go build ./...", "go vet ./..."],
        forbidden_write_paths=["go.sum", ".github/"],
        forbidden_shell_prefixes=_COMMON_FORBIDDEN_SHELL,
    ),
    "auth-service": RepoConfig(
        name="auth-service",
        path=PORTFOLIO_ROOT / "auth-service",
        language="python",
        github_repo="rodmen07/auth-service",
        verify_commands=[
            "find . -name '*.py' -not -path './.venv/*' -not -path './node_modules/*' "
            "| head -60 | xargs python -m py_compile",
        ],
        forbidden_write_paths=[".github/", ".env", "requirements.txt"],
        forbidden_shell_prefixes=_COMMON_FORBIDDEN_SHELL + ["pip install"],
    ),
    "ai-orchestrator-service": RepoConfig(
        name="ai-orchestrator-service",
        path=PORTFOLIO_ROOT / "ai-orchestrator-service",
        language="python",
        github_repo="rodmen07/ai-orchestrator-service",
        verify_commands=[
            "find app -name '*.py' | xargs python -m py_compile",
        ],
        forbidden_write_paths=[".github/", ".env", "requirements.txt"],
        forbidden_shell_prefixes=_COMMON_FORBIDDEN_SHELL + ["pip install"],
    ),
    "event-stream-service": RepoConfig(
        name="event-stream-service",
        path=PORTFOLIO_ROOT / "event-stream-service",
        language="go",
        github_repo="rodmen07/event-stream-service",
        verify_commands=["go build ./...", "go vet ./..."],
        forbidden_write_paths=["go.sum", ".github/"],
        forbidden_shell_prefixes=_COMMON_FORBIDDEN_SHELL,
    ),
    "observaboard": RepoConfig(
        name="observaboard",
        path=PORTFOLIO_ROOT / "observaboard",
        language="python",
        github_repo="rodmen07/observaboard",
        verify_commands=[
            "find . -name '*.py' -not -path './.venv/*' -not -path './node_modules/*' "
            "| head -60 | xargs python -m py_compile",
        ],
        forbidden_write_paths=[".github/", ".env"],
        forbidden_shell_prefixes=_COMMON_FORBIDDEN_SHELL + ["pip install"],
    ),
    "projects-service": RepoConfig(
        name="projects-service",
        path=PORTFOLIO_ROOT / "projects-service",
        language="rust",
        github_repo="rodmen07/projects-service",
        verify_commands=["cargo check"],
        forbidden_write_paths=["Cargo.lock", ".github/"],
        forbidden_shell_prefixes=_COMMON_FORBIDDEN_SHELL + ["cargo install"],
    ),
    "dynamodb_prototype": RepoConfig(
        name="dynamodb_prototype",
        path=PORTFOLIO_ROOT / "dynamodb_prototype",
        language="rust",
        github_repo="rodmen07/dynamodb_prototype",
        verify_commands=["cargo check"],
        forbidden_write_paths=["Cargo.lock", ".github/"],
        forbidden_shell_prefixes=_COMMON_FORBIDDEN_SHELL + ["cargo install"],
    ),
}


def get_repo(name: str) -> RepoConfig:
    if name not in REPOS:
        raise ValueError(f"Unknown repo: {name!r}. Available: {sorted(REPOS)}")
    return REPOS[name]
