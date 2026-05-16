"""
Observability collector for the productionizer agent.

Tracks metrics per task and across the entire run:
- Task outcomes (success, skip, error)
- Execution timing
- LLM API usage (tokens, estimated cost) - supports both Claude and GPT models
- Tool invocation patterns
- Error diagnostics

Writes structured JSON output to .observability.json for analysis.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import pathlib
import time
from typing import Any

log = logging.getLogger("observability")

AGENT_DIR = pathlib.Path(__file__).parent


def get_model_pricing(model: str) -> tuple[float, float]:
    """Get pricing (input_cost, output_cost) per 1M tokens for a model."""
    # GPT models
    if "gpt-4o-mini" in model:
        return 0.15, 0.60  # $0.15 per 1M input, $0.60 per 1M output
    elif "gpt-4" in model:
        return 30.00, 60.00
    elif "gpt-3.5-turbo" in model:
        return 0.50, 1.50
    
    # Claude models
    elif "claude-opus" in model:
        return 15.00, 75.00
    elif "claude-3-5-sonnet" in model or "claude-3-sonnet" in model:
        return 3.00, 15.00
    elif "claude-haiku" in model:
        return 0.80, 4.00
    
    # Fallback to GPT-4o Mini pricing if unknown
    else:
        log.warning(f"Unknown model {model}, using GPT-4o Mini pricing")
        return 0.15, 0.60


@dataclasses.dataclass
class TaskMetrics:
    """Per-task observability data."""
    task_id: str
    task_title: str
    exit_code: int | None = None
    elapsed_sec: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    tool_calls: int = 0
    tool_calls_failed: int = 0
    verification_passed: bool = False
    error_message: str | None = None
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def record_tool_call(self, tool_name: str, success: bool = True) -> None:
        """Record a tool call for this task."""
        self.tool_calls += 1
        if not success:
            self.tool_calls_failed += 1
        log.debug("Task %s tool call: %s (success=%s)", self.task_id, tool_name, success)

    def record_error(self, error_type: str, error_message: str) -> None:
        """Record an error for this task."""
        self.error_type = error_type
        self.error_message = error_message[:500]
        log.debug("Task %s error: %s: %s", self.task_id, error_type, error_message)

    def record_verification(self, passed: bool, error_message: str | None = None) -> None:
        """Record verification result."""
        self.verification_passed = passed
        if not passed and error_message:
            self.error_message = error_message[:500]
            self.error_type = "verification_failed"
        log.debug("Task %s verification: passed=%s", self.task_id, passed)


@dataclasses.dataclass
class RunSummary:
    """Summary statistics for the entire run."""
    total_tasks_attempted: int = 0
    total_tasks_completed: int = 0
    total_tasks_succeeded: int = 0
    total_tasks_skipped: int = 0
    total_tasks_failed: int = 0
    total_elapsed_sec: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_estimated_cost_usd: float = 0.0
    avg_task_time_sec: float = 0.0
    success_rate: float = 0.0
    tool_calls_total: int = 0
    tool_calls_failed_total: int = 0


class Observability:
    """Collects and manages observability metrics throughout productionizer execution."""

    def __init__(self, model: str | None = None):
        self.tasks: list[TaskMetrics] = []
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.run_summary = RunSummary()
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")

    def start_run(self) -> None:
        """Mark the start of a productionizer run."""
        self.start_time = time.time()
        log.info("Observability run started")

    def start_task(self, task_id: str, task_title: str) -> TaskMetrics:
        """Start tracking a new task."""
        metrics = TaskMetrics(task_id=task_id, task_title=task_title)
        self.tasks.append(metrics)
        log.debug("Task %s started", task_id)
        return metrics

    def record_task_complete(
        self,
        metrics: TaskMetrics,
        exit_code: int,
        elapsed_sec: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Record task completion with metrics."""
        metrics.exit_code = exit_code
        metrics.elapsed_sec = elapsed_sec
        metrics.input_tokens = input_tokens
        metrics.output_tokens = output_tokens
        metrics.total_tokens = input_tokens + output_tokens
        metrics.estimated_cost_usd = self._estimate_cost(input_tokens, output_tokens)

        log.debug(
            "Task %s completed: exit_code=%d elapsed=%0.1fs tokens=%d cost=$%0.4f",
            metrics.task_id,
            exit_code,
            elapsed_sec,
            metrics.total_tokens,
            metrics.estimated_cost_usd,
        )

    def record_verification(
        self,
        metrics: TaskMetrics,
        passed: bool,
        error_message: str | None = None,
    ) -> None:
        """Record verification result."""
        metrics.verification_passed = passed
        if not passed and error_message:
            metrics.error_message = error_message[:500]  # Truncate long errors
            metrics.error_type = "verification_failed"
        log.debug("Task %s verification: passed=%s", metrics.task_id, passed)

    def end_run(self) -> None:
        """Mark the end of a productionizer run and compute summary."""
        self.end_time = time.time()
        self._compute_summary()
        log.info("Observability run ended")

    def _compute_summary(self) -> None:
        """Compute aggregate run statistics."""
        self.run_summary.total_tasks_attempted = len(self.tasks)

        for task in self.tasks:
            if task.exit_code == 0:
                self.run_summary.total_tasks_succeeded += 1
                self.run_summary.total_tasks_completed += 1
            elif task.exit_code == 2:
                self.run_summary.total_tasks_skipped += 1
                self.run_summary.total_tasks_completed += 1
            elif task.exit_code in (1, 3):
                # 3 is backlog complete, 1 is error — both end the run
                self.run_summary.total_tasks_failed += 1
            else:
                self.run_summary.total_tasks_failed += 1

            self.run_summary.total_elapsed_sec += task.elapsed_sec
            self.run_summary.total_input_tokens += task.input_tokens
            self.run_summary.total_output_tokens += task.output_tokens
            self.run_summary.total_tokens += task.total_tokens
            self.run_summary.total_estimated_cost_usd += task.estimated_cost_usd
            self.run_summary.tool_calls_total += task.tool_calls
            self.run_summary.tool_calls_failed_total += task.tool_calls_failed

        if self.run_summary.total_tasks_completed > 0:
            self.run_summary.avg_task_time_sec = (
                self.run_summary.total_elapsed_sec / self.run_summary.total_tasks_completed
            )
            self.run_summary.success_rate = (
                self.run_summary.total_tasks_succeeded / self.run_summary.total_tasks_completed
            )

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost (USD) for token usage based on configured model."""
        input_cost_per_m, output_cost_per_m = get_model_pricing(self.model)
        input_cost = (input_tokens / 1_000_000) * input_cost_per_m
        output_cost = (output_tokens / 1_000_000) * output_cost_per_m
        return input_cost + output_cost

    def save(self) -> bool:
        """Write observability data to .observability.json."""
        output_file = AGENT_DIR / ".observability.json"
        try:
            data = {
                "tasks": [task.to_dict() for task in self.tasks],
                "summary": dataclasses.asdict(self.run_summary),
                "run_start": self.start_time,
                "run_end": self.end_time,
            }
            output_file.write_text(json.dumps(data, indent=2))
            log.info("Observability data saved to %s", output_file)
            return True
        except Exception as exc:
            log.error("Failed to save observability data: %s", exc)
            return False

    def print_summary(self) -> None:
        """Print a human-readable summary to the log."""
        s = self.run_summary
        log.info("━" * 60)
        log.info("OBSERVABILITY SUMMARY")
        log.info("━" * 60)
        log.info("Tasks:        %d attempted, %d completed (%d success, %d skip, %d fail)",
                 s.total_tasks_attempted, s.total_tasks_completed,
                 s.total_tasks_succeeded, s.total_tasks_skipped, s.total_tasks_failed)
        log.info("Success Rate: %0.1f%%", s.success_rate * 100 if s.total_tasks_completed > 0 else 0)
        log.info("Timing:       %0.1fs total, %0.1fs avg per task",
                 s.total_elapsed_sec, s.avg_task_time_sec)
        log.info("Tokens:       %d input, %d output, %d total",
                 s.total_input_tokens, s.total_output_tokens, s.total_tokens)
        log.info("Cost:         $%0.2f USD", s.total_estimated_cost_usd)
        log.info("Tool Calls:   %d total, %d failed",
                 s.tool_calls_total, s.tool_calls_failed_total)
        log.info("━" * 60)
