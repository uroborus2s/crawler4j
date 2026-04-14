"""ATM 数据模型定义 (V2)。

规格参考: docs/03-solution/reference-design/task-engine-v2.md

定义核心实体:
    - Job: 作业定义 (期望状态)
    - Task: 任务实例 (实际状态)
"""

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict

from src.core.atm.run_profile import RunProfile

# =============================================================================
# Enums
# =============================================================================

class JobType(str, enum.Enum):
    """作业类型。"""
    BATCH = "batch"       # 批处理 (有限次执行)
    SERVICE = "service"   # 常驻服务 (无限执行)

class JobState(str, enum.Enum):
    """作业生命周期状态。"""
    ACTIVE = "active"     # 启用中 (Controller 会调度)
    PAUSED = "paused"     # 已暂停 (Controller 忽略)
    COMPLETED = "completed" # 已完成 (仅 Batch)
    ERROR = "error"       # 异常停止

class TriggerType(str, enum.Enum):
    """触发器类型。"""
    MANUAL = "manual"
    CRON = "cron"
    ALWAYS_ON = "always_on"  # 仅用于 SERVICE 类型

class TaskStatus(str, enum.Enum):
    """任务运行状态。"""
    PENDING = "pending"      # 等待资源 (排队中)
    RUNNING = "running"      # 执行中
    SUCCEEDED = "succeeded"  # 成功
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 取消

# =============================================================================
# Aggregate Roots
# =============================================================================

@dataclass
class TriggerConfig:
    """触发规则配置。"""
    type: TriggerType = TriggerType.MANUAL
    cron_expr: str | None = None

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = TriggerType(self.type)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "cron_expr": self.cron_expr
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriggerConfig":
        return cls(
            type=TriggerType(data.get("type", "manual")),
            cron_expr=data.get("cron_expr")
        )

@dataclass
class Job:
    """作业 (Job)。定义'期望状态'。"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: JobType = JobType.BATCH
    run_profile: RunProfile | None = None
    
    # 调度配置
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    concurrency_target: int = 1  # 期望并发数
    
    # 运行时参数 (覆盖 RunProfile 默认值)
    params: Dict[str, Any] = field(default_factory=dict)
    
    # 状态
    state: JobState = JobState.PAUSED
    
    # 元数据
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = JobType(self.type)
        if isinstance(self.trigger, dict):
            self.trigger = TriggerConfig.from_dict(self.trigger)
        if isinstance(self.state, str):
            self.state = JobState(self.state)
        if isinstance(self.run_profile, dict):
            self.run_profile = RunProfile.model_validate(self.run_profile)

@dataclass
class Task:
    """任务 (Task)。定义'实际状态'。"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    
    # 状态
    status: TaskStatus = TaskStatus.PENDING
    
    # 资源绑定
    env_id: str | None = None
    lease_id: str | None = None
    
    # 执行结果
    message: str = ""
    error: str = ""
    
    # 时间戳
    created_at: int = field(default_factory=lambda: int(time.time()))
    started_at: int | None = None
    finished_at: int | None = None
