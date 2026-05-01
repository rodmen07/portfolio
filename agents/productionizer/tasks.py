"""
Task model and backlog management for the fullstack productionizer.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Literal

import yaml

AGENT_DIR = pathlib.Path(__file__).parent
BACKLOG_FILE = AGENT_DIR / "backlog.yaml"

Complexity = Literal["low", "medium", "high"]
Status = Literal["pending", "in_progress", "done", "skipped"]


@dataclass
class Task:
    id: str
    dimension: str
    title: str
    description: str
    repos: list[str]
    complexity: Complexity
    status: Status = "pending"
    created_at: str = ""
    completed_at: str | None = None
    summary: str | None = None


def load_backlog() -> list[Task]:
    if not BACKLOG_FILE.exists():
        return []
    raw = yaml.safe_load(BACKLOG_FILE.read_text()) or {}
    tasks = []
    for item in raw.get("tasks", []) or []:
        tasks.append(Task(
            id=item["id"],
            dimension=item["dimension"],
            title=item["title"],
            description=item["description"],
            repos=item["repos"],
            complexity=item.get("complexity", "medium"),
            status=item.get("status", "pending"),
            created_at=item.get("created_at", ""),
            completed_at=item.get("completed_at"),
            summary=item.get("summary"),
        ))
    return tasks


def save_backlog(tasks: list[Task]) -> None:
    items = []
    for t in tasks:
        items.append({
            "id": t.id,
            "dimension": t.dimension,
            "title": t.title,
            "description": t.description,
            "repos": t.repos,
            "complexity": t.complexity,
            "status": t.status,
            "created_at": t.created_at,
            "completed_at": t.completed_at,
            "summary": t.summary,
        })
    BACKLOG_FILE.write_text(
        yaml.dump({"tasks": items}, default_flow_style=False, allow_unicode=True, sort_keys=False)
    )


def pick_next_task(tasks: list[Task]) -> Task | None:
    for task in tasks:
        if task.status == "pending":
            return task
    return None


def pending_count(tasks: list[Task]) -> int:
    return sum(1 for t in tasks if t.status == "pending")


def done_count(tasks: list[Task]) -> int:
    return sum(1 for t in tasks if t.status == "done")
