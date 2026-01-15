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


class ProxyMode(StrEnum):
    """代理配置模式。
    
    设计文档 5.2.4: 代理配置模式
    """
    NONE = "none"           # 无代理
    STATIC = "static"       # 固定代理地址
    POOL = "pool"           # 从 IP 池自动分配
    SYSTEM = "system"       # 使用系统代理


@dataclass
class ProxyConfig:
    """代理配置。
    
    Attributes:
        mode: 代理模式
        pool_id: IP 池 ID（当 mode=POOL 时使用）
        static_value: 固定代理地址（当 mode=STATIC 时使用）
        current_ip: 当前使用的 IP 地址
    """
    mode: ProxyMode = ProxyMode.NONE
    pool_id: str | None = None
    static_value: str | None = None
    current_ip: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "mode": self.mode.value,
            "pool_id": self.pool_id,
            "static_value": self.static_value,
            "current_ip": self.current_ip,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProxyConfig":
        """从字典反序列化。"""
        return cls(
            mode=ProxyMode(data.get("mode", "none")),
            pool_id=data.get("pool_id"),
            static_value=data.get("static_value"),
            current_ip=data.get("current_ip"),
        )


@dataclass
class FingerprintConfig:
    """指纹配置。
    
    Attributes:
        provider_type: Provider 类型 ("bitbrowser" | "virtualbrowser")
        config_data: Provider 特定的配置数据
    """
    provider_type: str = ""
    config_data: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "provider_type": self.provider_type,
            "config_data": self.config_data,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FingerprintConfig":
        """从字典反序列化。"""
        return cls(
            provider_type=data.get("provider_type", ""),
            config_data=data.get("config_data", {}),
        )


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
        external_id: 外部系统环境 ID（用于状态同步）
        labels: 静态标签 (如 {"browser": "chromium", "os": "mac"})
        capabilities: 能力集合 (如 {"page", "cookies", "screenshot"})
        handle: 物理句柄 (内存对象，不序列化)
        lease_id: 当前租约ID (若 BUSY)
        task_run_id: 关联的任务运行ID
        last_used_at: 最后使用时间戳
        daily_usage_count: 当天使用次数
        daily_usage_date: 使用统计日期 (YYYY-MM-DD)
        proxy_config: 代理配置
        fingerprint_config: 指纹配置
        created_at: 创建时间戳
        updated_at: 最后更新时间戳
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    kind: EnvKind = EnvKind.BROWSER
    provider: str = ""
    status: EnvStatus = EnvStatus.CREATING
    external_id: str | None = None
    labels: dict[str, str] = field(default_factory=dict)
    capabilities: set[str] = field(default_factory=set)
    handle: Any = field(default=None, repr=False)
    lease_id: str | None = None
    task_run_id: str | None = None
    # 统计字段
    last_used_at: int | None = None
    daily_usage_count: int = 0
    daily_usage_date: str = ""
    # 配置字段
    proxy_config: ProxyConfig | None = None
    fingerprint_config: FingerprintConfig | None = None
    # 时间戳
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))
    
    def increment_usage(self) -> None:
        """增加使用次数，跨日自动清零。"""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        if self.daily_usage_date != today:
            self.daily_usage_date = today
            self.daily_usage_count = 1
        else:
            self.daily_usage_count += 1
        self.last_used_at = int(time.time())
        self.updated_at = int(time.time())
    
    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于持久化）。"""
        return {
            "id": self.id,
            "kind": self.kind.value,
            "provider": self.provider,
            "status": self.status.value,
            "external_id": self.external_id,
            "labels": self.labels,
            "capabilities": list(self.capabilities),
            "lease_id": self.lease_id,
            "task_run_id": self.task_run_id,
            "last_used_at": self.last_used_at,
            "daily_usage_count": self.daily_usage_count,
            "daily_usage_date": self.daily_usage_date,
            "proxy_config": self.proxy_config.to_dict() if self.proxy_config else None,
            "fingerprint_config": self.fingerprint_config.to_dict() if self.fingerprint_config else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Environment":
        """从字典反序列化。"""
        proxy_config = None
        if data.get("proxy_config"):
            proxy_config = ProxyConfig.from_dict(data["proxy_config"])
        
        fingerprint_config = None
        if data.get("fingerprint_config"):
            fingerprint_config = FingerprintConfig.from_dict(data["fingerprint_config"])
        
        return cls(
            id=data["id"],
            kind=EnvKind(data["kind"]),
            provider=data["provider"],
            status=EnvStatus(data["status"]),
            external_id=data.get("external_id"),
            labels=data.get("labels", {}),
            capabilities=set(data.get("capabilities", [])),
            lease_id=data.get("lease_id"),
            task_run_id=data.get("task_run_id"),
            last_used_at=data.get("last_used_at"),
            daily_usage_count=data.get("daily_usage_count", 0),
            daily_usage_date=data.get("daily_usage_date", ""),
            proxy_config=proxy_config,
            fingerprint_config=fingerprint_config,
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
