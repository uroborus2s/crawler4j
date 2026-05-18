"""Workflow/object lifecycle contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from crawler4j_contracts.result import TaskResult

TaskOutcomeStatus = Literal["succeeded", "failed", "timed_out", "cancelled"]


@dataclass(frozen=True)
class WorkflowLifecycleInfo:
    """Workflow metadata passed to object lifecycle methods."""

    module_name: str
    workflow_name: str
    workflow_label: str = ""
    workflow_description: str = ""
    workflow_module_name: str = ""
    workflow_symbol: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TaskOutcome:
    """Terminal outcome passed to workflow/object ``cleanup`` methods."""

    status: TaskOutcomeStatus
    workflow: WorkflowLifecycleInfo | None = None
    result: TaskResult | None = None
    error: str = ""
    error_type: str = ""
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["workflow"] = self.workflow.to_dict() if self.workflow else None
        data["result"] = self.result.to_dict() if self.result else None
        return data


__all__ = ["TaskOutcome", "TaskOutcomeStatus", "WorkflowLifecycleInfo"]
