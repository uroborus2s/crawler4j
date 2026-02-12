"""ATM 数据模型定义。

规格参考: docs/srs/05-framework-core/05-4-automation-task-management.md

定义任务管理的核心数据实体：
    - TaskStatus: 任务运行状态
    - AutomationTask: 任务配置（持久化）
    - TaskRun: 任务运行记录（执行历史）
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional


class TriggerType(StrEnum):
    """触发器类型。"""
    CRON = "cron"
    INTERVAL = "interval"
    RANDOM = "random"


@dataclass
class TriggerConfig:
    """触发器配置。"""
    type: TriggerType = TriggerType.CRON
    cron_expr: str | None = None          # For CRON
    interval_seconds: int | None = None   # For INTERVAL / RANDOM
    random_range: int | None = None       # For RANDOM (jitter +/- seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "cron_expr": self.cron_expr,
            "interval_seconds": self.interval_seconds,
            "random_range": self.random_range,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TriggerConfig":
        return cls(
            type=TriggerType(data.get("type", "cron")),
            cron_expr=data.get("cron_expr"),
            interval_seconds=data.get("interval_seconds"),
            random_range=data.get("random_range"),
        )


class TaskStatus(StrEnum):
    """任务运行状态。
    
    规格 5.4.2 状态机:
        IDLE (初始) -> STARTING (启动中) -> RUNNING (运行中)
        -> SUCCEEDED (成功) / FAILED (失败) / CANCELLED (取消)
    """
    IDLE = "idle"              # 初始状态
    STARTING = "starting"      # 正在启动（请求 TSM）
    RUNNING = "running"        # 正在执行
    SUCCEEDED = "succeeded"    # 执行成功
    FAILED = "failed"          # 执行失败
    CANCELLED = "cancelled"    # 已取消
    INTERRUPTED = "interrupted" # 异常中断（如进程崩溃）


@dataclass
class AutomationTask:
    """自动化任务配置。
    
    用户定义的任务元数据，不包含运行时状态。
    
    Attributes:
        id: 任务唯一标识 (UUID)
        name: 任务名称
        strategy_id: 关联的 TSM 策略 ID
        cron_expression: 定时执行表达式 (可选)
        default_params: 默认执行参数
        created_at: 创建时间
        updated_at: 更新时间
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy_id: str = ""
    trigger_config: TriggerConfig | None = None
    default_params: dict[str, Any] = field(default_factory=dict)
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "strategy_id": self.strategy_id,
            "trigger_config": self.trigger_config.to_dict() if self.trigger_config else None,
            "default_params": self.default_params,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutomationTask":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            strategy_id=data.get("strategy_id", ""),
            trigger_config=TriggerConfig.from_dict(data["trigger_config"]) if data.get("trigger_config") else None,
            default_params=data.get("default_params", {}),
            created_at=data.get("created_at", int(time.time())),
            updated_at=data.get("updated_at", int(time.time())),
        )


@dataclass
class TaskResult:
    """任务执行结果。"""
    success: bool = True
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskResult":
        return cls(
            success=data.get("success", True),
            message=data.get("message", ""),
            data=data.get("data", {}),
        )


@dataclass
class TaskRun:
    """任务运行记录。
    
    一次具体的任务执行历史。
    
    Attributes:
        id: 运行记录 ID (UUID)
        task_id: 关联的任务配置 ID
        status: 运行状态
        trigger_type: 触发方式 (manual/cron/api)
        env_id: 实际运行的环境 ID (由 TSM 分配)
        result: 执行结果
        error: 错误信息
        start_time: 开始时间
        end_time: 结束时间
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    status: TaskStatus = TaskStatus.IDLE
    trigger_type: str = "manual"
    env_id: str | None = None
    result: TaskResult | None = None
    error: str = ""
    start_time: int | None = None
    end_time: int | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "status": self.status.value,
            "trigger_type": self.trigger_type,
            "env_id": self.env_id,
            "result": self.result.to_dict() if self.result else None,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskRun":
        result_data = data.get("result")
        result = TaskResult.from_dict(result_data) if result_data else None
        
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            task_id=data.get("task_id", ""),
            status=TaskStatus(data.get("status", "idle")),
            trigger_type=data.get("trigger_type", "manual"),
            env_id=data.get("env_id"),
            result=result,
            error=data.get("error", ""),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
        )

    # === Helper Methods ===

    def start(self) -> None:
        self.status = TaskStatus.RUNNING
        self.start_time = int(time.time())

    def finish(self, success: bool, message: str = "") -> None:
        self.status = TaskStatus.SUCCEEDED if success else TaskStatus.FAILED
        self.end_time = int(time.time())
        if not self.result:
            self.result = TaskResult(success=success, message=message)
        else:
            self.result.success = success
            self.result.message = message

    def cancel(self) -> None:
        self.status = TaskStatus.CANCELLED
        self.end_time = int(time.time())


class TaskError(Exception):
    """任务模块基础异常。"""
    pass


class TaskNotFoundError(TaskError):
    """任务不存在。"""
    pass
