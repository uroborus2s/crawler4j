"""ATM 数据模型定义。

规格参考: docs/srs/05-framework-core/05-4-automation-task-management.md

定义任务管理的核心数据实体：
    - TaskStatus: 任务状态（状态机）
    - TaskInstance: 任务实例
    - TaskRequest: 任务提交请求
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    """任务状态。
    
    规格 5.4.2 状态机:
        PENDING -> QUEUED -> RUNNING -> SUCCEEDED/FAILED/CANCELLED
    """
    PENDING = "pending"        # 等待中
    QUEUED = "queued"          # 入队等待调度
    RUNNING = "running"        # 运行中
    SUCCEEDED = "succeeded"    # 成功完成
    FAILED = "failed"          # 执行失败
    CANCELLED = "cancelled"    # 已取消
    INTERRUPTED = "interrupted"  # 中断（崩溃恢复用）


@dataclass
class TaskRequest:
    """任务提交请求。
    
    规格 5.4.3 FR-ATM-001:
        输入: module_name, task_name, params
    """
    module_name: str
    task_name: str
    workflow_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    timeout: int = 300  # 超时时间（秒）


@dataclass
class TaskResult:
    """任务结果。"""
    success: bool = True
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    tasks_completed: int = 0
    tasks_failed: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskResult":
        return cls(
            success=data.get("success", True),
            message=data.get("message", ""),
            data=data.get("data", {}),
            tasks_completed=data.get("tasks_completed", 0),
            tasks_failed=data.get("tasks_failed", 0),
        )


@dataclass
class TaskInstance:
    """任务实例。
    
    规格 5.4.2: 任务实体，持有 TaskContext 和状态。
    
    Attributes:
        id: 任务唯一标识 (UUID)
        module: 模块名
        name: 任务名
        workflow: 工作流名
        status: 当前状态
        params: 任务参数
        result: 执行结果
        error: 错误信息
        env_id: 关联的环境ID
        created_at: 创建时间
        started_at: 开始执行时间
        ended_at: 结束时间
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    module: str = ""
    name: str = ""
    workflow: str = ""
    status: TaskStatus = TaskStatus.PENDING
    params: dict[str, Any] = field(default_factory=dict)
    result: TaskResult | None = None
    error: str = ""
    env_id: str | None = None
    lease_id: str | None = None
    priority: int = 100
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 3
    created_at: int = field(default_factory=lambda: int(time.time()))
    started_at: int | None = None
    ended_at: int | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于持久化）。"""
        return {
            "id": self.id,
            "module": self.module,
            "name": self.name,
            "workflow": self.workflow,
            "status": self.status.value,
            "params": self.params,
            "result": self.result.to_dict() if self.result else None,
            "error": self.error,
            "env_id": self.env_id,
            "lease_id": self.lease_id,
            "priority": self.priority,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskInstance":
        """从字典反序列化。"""
        result_data = data.get("result")
        result = TaskResult.from_dict(result_data) if result_data else None
        
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            module=data.get("module", ""),
            name=data.get("name", ""),
            workflow=data.get("workflow", ""),
            status=TaskStatus(data.get("status", "pending")),
            params=data.get("params", {}),
            result=result,
            error=data.get("error", ""),
            env_id=data.get("env_id"),
            lease_id=data.get("lease_id"),
            priority=data.get("priority", 100),
            timeout=data.get("timeout", 300),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            created_at=data.get("created_at", int(time.time())),
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
        )
    
    @classmethod
    def from_request(cls, request: TaskRequest) -> "TaskInstance":
        """从请求创建任务实例。"""
        return cls(
            module=request.module_name,
            name=request.task_name,
            workflow=request.workflow_name,
            params=request.params,
            priority=request.priority,
            timeout=request.timeout,
        )
    
    # === 状态机方法 ===
    
    def can_transition_to(self, target: TaskStatus) -> bool:
        """检查是否可以转换到目标状态。"""
        valid_transitions = {
            TaskStatus.PENDING: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
            TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
            TaskStatus.RUNNING: {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED},
            TaskStatus.FAILED: {TaskStatus.PENDING},  # 重试
        }
        
        return target in valid_transitions.get(self.status, set())
    
    def enqueue(self) -> bool:
        """入队。"""
        if self.can_transition_to(TaskStatus.QUEUED):
            self.status = TaskStatus.QUEUED
            return True
        return False
    
    def start(self, env_id: str | None = None, lease_id: str | None = None) -> bool:
        """开始执行。"""
        if self.can_transition_to(TaskStatus.RUNNING):
            self.status = TaskStatus.RUNNING
            self.started_at = int(time.time())
            self.env_id = env_id
            self.lease_id = lease_id
            return True
        return False
    
    def succeed(self, result: TaskResult) -> bool:
        """成功完成。"""
        if self.can_transition_to(TaskStatus.SUCCEEDED):
            self.status = TaskStatus.SUCCEEDED
            self.result = result
            self.ended_at = int(time.time())
            return True
        return False
    
    def fail(self, error: str) -> bool:
        """执行失败。"""
        if self.can_transition_to(TaskStatus.FAILED):
            self.status = TaskStatus.FAILED
            self.error = error
            self.ended_at = int(time.time())
            return True
        return False
    
    def cancel(self) -> bool:
        """取消任务。"""
        if self.can_transition_to(TaskStatus.CANCELLED):
            self.status = TaskStatus.CANCELLED
            self.ended_at = int(time.time())
            return True
        return False
    
    def retry(self) -> bool:
        """重试任务。"""
        if self.status == TaskStatus.FAILED and self.retry_count < self.max_retries:
            self.status = TaskStatus.PENDING
            self.retry_count += 1
            self.error = ""
            self.started_at = None
            self.ended_at = None
            return True
        return False


class TaskError(Exception):
    """任务错误基类。"""
    pass


class TaskNotFoundError(TaskError):
    """任务不存在。"""
    pass


class TaskExecutionError(TaskError):
    """任务执行错误。"""
    pass
