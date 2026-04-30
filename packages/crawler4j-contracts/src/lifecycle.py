"""Workflow/object lifecycle contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from crawler4j_contracts.result import TaskResult

TaskOutcomeStatus = Literal["succeeded", "failed", "timed_out", "cancelled"]


@dataclass(frozen=True)
class TaskOutcome:
    """Terminal outcome passed to workflow/object ``cleanup`` methods."""

    status: TaskOutcomeStatus
    result: TaskResult | None = None
    error: str = ""
    error_type: str = ""
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["result"] = self.result.to_dict() if self.result else None
        return data


__all__ = ["TaskOutcome", "TaskOutcomeStatus"]
