"""TaskResult 任务执行结果契约。"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TaskResult:
    """任务执行结果模型。"""

    success: bool = False
    tasks_completed: int = 0
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def ok(
        cls,
        tasks_completed: int = 1,
        message: str = "成功",
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "TaskResult":
        payload: dict[str, Any] = {}
        if data:
            payload.update(data)
        if kwargs:
            payload.update(kwargs)
        return cls(
            success=True,
            tasks_completed=tasks_completed,
            message=message,
            data=payload,
        )

    @classmethod
    def fail(
        cls,
        message: str,
        error: str | None = None,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "TaskResult":
        payload: dict[str, Any] = {}
        if data:
            payload.update(data)
        if kwargs:
            payload.update(kwargs)
        return cls(
            success=False,
            tasks_completed=0,
            message=message,
            data=payload,
            error=error,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskResult":
        return cls(
            success=data.get("success", False),
            tasks_completed=data.get("tasks_completed", 0),
            message=data.get("message", ""),
            data=data.get("data", {}),
            error=data.get("error"),
        )
