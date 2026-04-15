"""TaskSignal 模块到 ATM 的控制信号契约。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class TaskSignalAction(StrEnum):
    """模块请求 ATM 执行的流程动作。"""

    SUCCEED = "succeed"
    FAIL = "fail"
    WAIT_FOR_CONFIRMATION = "wait_for_confirmation"
    CANCEL = "cancel"


class EnvAction(StrEnum):
    """任务结束后 ATM 对运行环境执行的动作。"""

    RECYCLE = "recycle"
    KEEP_ALIVE = "keep_alive"
    DESTROY = "destroy"


@dataclass(frozen=True)
class TaskSignal:
    """模块向 ATM 发出的结构化控制信号。"""

    action: TaskSignalAction
    message: str = ""
    reason: str = ""
    error: str | None = None
    env_action: EnvAction | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def succeed(
        cls,
        *,
        message: str = "",
        reason: str = "",
        env_action: EnvAction | None = None,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "TaskSignal":
        merged_payload = dict(payload or {})
        if kwargs:
            merged_payload.update(kwargs)
        return cls(
            action=TaskSignalAction.SUCCEED,
            message=message,
            reason=reason,
            env_action=env_action,
            payload=merged_payload,
        )

    @classmethod
    def fail(
        cls,
        *,
        message: str,
        reason: str = "",
        error: str | None = None,
        env_action: EnvAction | None = None,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "TaskSignal":
        merged_payload = dict(payload or {})
        if kwargs:
            merged_payload.update(kwargs)
        return cls(
            action=TaskSignalAction.FAIL,
            message=message,
            reason=reason,
            error=error,
            env_action=env_action,
            payload=merged_payload,
        )

    @classmethod
    def wait_for_confirmation(
        cls,
        *,
        message: str,
        reason: str = "",
        env_action: EnvAction | None = EnvAction.KEEP_ALIVE,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "TaskSignal":
        merged_payload = dict(payload or {})
        if kwargs:
            merged_payload.update(kwargs)
        return cls(
            action=TaskSignalAction.WAIT_FOR_CONFIRMATION,
            message=message,
            reason=reason,
            env_action=env_action,
            payload=merged_payload,
        )

    @classmethod
    def cancel(
        cls,
        *,
        message: str = "",
        reason: str = "",
        env_action: EnvAction | None = None,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "TaskSignal":
        merged_payload = dict(payload or {})
        if kwargs:
            merged_payload.update(kwargs)
        return cls(
            action=TaskSignalAction.CANCEL,
            message=message,
            reason=reason,
            env_action=env_action,
            payload=merged_payload,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["action"] = self.action.value
        data["env_action"] = self.env_action.value if self.env_action else None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskSignal":
        return cls(
            action=TaskSignalAction(data["action"]),
            message=data.get("message", ""),
            reason=data.get("reason", ""),
            error=data.get("error"),
            env_action=EnvAction(data["env_action"]) if data.get("env_action") else None,
            payload=dict(data.get("payload") or {}),
        )
