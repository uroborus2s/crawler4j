"""REM 数据模型定义。

规格参考: docs/srs/05-framework-core/05-2-runtime-environment-management.md

定义环境管理的核心数据实体：
    - EnvKind: 环境类型
    - EnvStatus: 环境状态
    - Environment: 环境实例
    - EnvLease: 环境租约
    - EnvRequirement: 环境申请请求
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EnvKind(StrEnum):
    """环境类型。
    
    规格 5.2.3.2: browser | http | desktop | external
    """
    BROWSER = "browser"
    HTTP = "http"
    DESKTOP = "desktop"
    EXTERNAL = "external"


class EnvStatus(StrEnum):
    """环境状态。
    
    规格 5.2.3.2: CREATING | READY | BUSY | PAUSED | UNHEALTHY | TERMINATING | DEAD
    """
    CREATING = "creating"
    READY = "ready"
    BUSY = "busy"
    PAUSED = "paused"
    UNHEALTHY = "unhealthy"
    TERMINATING = "terminating"
    DEAD = "dead"


@dataclass
class Environment:
    """环境实例。
    
    规格 5.2.3.2 EnvMeta:
        - env_id: 环境实例唯一标识
        - kind: 环境类型
        - provider: 提供者标识
        - labels: 静态标签
        - capabilities: 能力集合
        - state: 环境状态
    
    Attributes:
        id: 环境唯一标识 (UUID)
        kind: 环境类型
        provider: 提供者标识 (如 "playwright_local", "fingerprint_browser")
        status: 当前状态
        labels: 静态标签 (如 {"browser": "chromium", "os": "mac"})
        capabilities: 能力集合 (如 {"page", "cookies", "screenshot"})
        handle: 物理句柄 (内存对象，不序列化)
        lease_id: 当前租约ID (若 BUSY)
        task_run_id: 关联的任务运行ID
        created_at: 创建时间戳
        updated_at: 最后更新时间戳
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    kind: EnvKind = EnvKind.BROWSER
    provider: str = ""
    status: EnvStatus = EnvStatus.CREATING
    labels: dict[str, str] = field(default_factory=dict)
    capabilities: set[str] = field(default_factory=set)
    handle: Any = field(default=None, repr=False)
    lease_id: str | None = None
    task_run_id: str | None = None
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于持久化）。"""
        return {
            "id": self.id,
            "kind": self.kind.value,
            "provider": self.provider,
            "status": self.status.value,
            "labels": self.labels,
            "capabilities": list(self.capabilities),
            "lease_id": self.lease_id,
            "task_run_id": self.task_run_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Environment":
        """从字典反序列化。"""
        return cls(
            id=data["id"],
            kind=EnvKind(data["kind"]),
            provider=data["provider"],
            status=EnvStatus(data["status"]),
            labels=data.get("labels", {}),
            capabilities=set(data.get("capabilities", [])),
            lease_id=data.get("lease_id"),
            task_run_id=data.get("task_run_id"),
            created_at=data.get("created_at", int(time.time())),
            updated_at=data.get("updated_at", int(time.time())),
        )


@dataclass
class EnvLease:
    """环境租约。
    
    规格 5.2.3.2 EnvLease:
        - lease_id: 租约唯一标识
        - env_id: 环境ID
        - task_run_id: 任务运行ID
        - acquired_at: 获取时间
        - expires_at: 过期时间（可选，用于强制回收）
    
    Attributes:
        id: 租约唯一标识
        env_id: 关联的环境ID
        task_run_id: 关联的任务运行ID
        acquired_at: 获取时间戳
        expires_at: 过期时间戳（可选）
        token: 验证令牌（防止越权释放）
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    env_id: str = ""
    task_run_id: str = ""
    acquired_at: int = field(default_factory=lambda: int(time.time()))
    expires_at: int | None = None
    token: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def is_expired(self) -> bool:
        """检查租约是否已过期。"""
        if self.expires_at is None:
            return False
        return int(time.time()) > self.expires_at


@dataclass
class EnvRequirement:
    """环境申请请求。
    
    规格 5.2.3.3: kind + capabilities + labels(可选)
    
    Attributes:
        kind: 需要的环境类型
        capabilities: 需要的能力集合
        labels: 需要匹配的标签
        task_run_id: 任务运行ID
        timeout: 等待超时（秒）
    """
    kind: EnvKind = EnvKind.BROWSER
    capabilities: set[str] = field(default_factory=set)
    labels: dict[str, str] = field(default_factory=dict)
    task_run_id: str = ""
    timeout: int = 60
    
    def matches(self, env: Environment) -> bool:
        """检查环境是否满足需求。"""
        # 类型匹配
        if env.kind != self.kind:
            return False
        
        # 能力匹配（需求的能力必须是环境能力的子集）
        if not self.capabilities.issubset(env.capabilities):
            return False
        
        # 标签匹配
        for key, value in self.labels.items():
            if env.labels.get(key) != value:
                return False
        
        return True


class EnvError(Exception):
    """环境管理错误基类。
    
    规格 5.2.3.4: 错误应包含 stage 和 hint
    """
    def __init__(self, message: str, stage: str = "", hint: str = ""):
        super().__init__(message)
        self.stage = stage
        self.hint = hint


class EnvUnavailableError(EnvError):
    """无可用环境。"""
    pass


class EnvUnhealthyError(EnvError):
    """环境不健康。"""
    pass


class EnvCleanupFailedError(EnvError):
    """环境清理失败。"""
    pass
