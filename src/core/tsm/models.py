"""TSM 策略模型定义。

规格参考: docs/srs/05-framework-core/05-3-task-strategy-management.md

定义策略管理的核心数据实体：
    - ConcurrencyConfig: 并发控制
    - ProvisioningConfig: 资源供应
    - SchedulingConfig: 调度优先级
    - ReliabilityConfig: 可靠性
    - StrategyProfile: 完整策略配置
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProvisioningMode(StrEnum):
    """资源供应模式。
    
    规格 5.3.2 [B]:
        - static: 仅池化（只使用已有环境）
        - dynamic: 仅新建（每次创建新环境）
        - hybrid: 优先池化，不足新建
    """
    STATIC = "static"
    DYNAMIC = "dynamic"
    HYBRID = "hybrid"


class ReusePolicy(StrEnum):
    """环境复用策略。
    
    规格 5.3.2 [B]:
        - dirty: 直接复用
        - clean: 清理后复用
        - ephemeral: 用完销毁
    """
    DIRTY = "dirty"
    CLEAN = "clean"
    EPHEMERAL = "ephemeral"


class BackoffStrategy(StrEnum):
    """退避策略。
    
    规格 5.3.2 [D]:
        - fixed: 固定间隔
        - exponential: 指数退避
    """
    FIXED = "fixed"
    EXPONENTIAL = "exponential"


@dataclass
class ConcurrencyConfig:
    """并发控制配置。
    
    规格 5.3.2 [A] Concurrency & Quota
    
    Attributes:
        global_max: 全局最大并发数
        group_buckets: 分组桶配额，如 {"module:ctrip": 2, "priority:high": 5}
    """
    global_max: int = 10
    group_buckets: dict[str, int] = field(default_factory=dict)


@dataclass
class ProvisioningConfig:
    """资源供应配置。
    
    规格 5.3.2 [B] Resource Provisioning
    
    Attributes:
        mode: 供应模式
        auto_create_limit: 允许动态创建的最大数量
        reuse_policy: 环境复用策略
        environment_template: 新建环境时的模板参数
    """
    mode: ProvisioningMode = ProvisioningMode.HYBRID
    auto_create_limit: int = 5
    reuse_policy: ReusePolicy = ReusePolicy.CLEAN
    environment_template: dict[str, Any] = field(default_factory=dict)


@dataclass
class SchedulingConfig:
    """调度配置。
    
    规格 5.3.2 [C] Scheduling
    
    Attributes:
        default_priority: 默认优先级（数值越大优先级越高）
        timeout_seconds: 排队超时时间
    """
    default_priority: int = 100
    timeout_seconds: int = 300


@dataclass
class ReliabilityConfig:
    """可靠性配置。
    
    规格 5.3.2 [D] Reliability
    
    Attributes:
        max_retries: 最大重试次数
        backoff_strategy: 退避策略
        backoff_factor: 退避因子（用于指数退避）
        backoff_base_seconds: 退避基础时间（秒）
    """
    max_retries: int = 3
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_factor: float = 2.0
    backoff_base_seconds: int = 5


@dataclass
class StrategyMetadata:
    """策略元数据。"""
    name: str = "default"
    version: str = "1.0"
    description: str = ""


@dataclass
class StrategyProfile:
    """完整策略配置。
    
    规格 5.3.2: EvolutionaryStrategy 核心配置对象
    
    Attributes:
        metadata: 策略元数据
        concurrency: 并发控制
        provisioning: 资源供应
        scheduling: 调度配置
        reliability: 可靠性配置
    """
    metadata: StrategyMetadata = field(default_factory=StrategyMetadata)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    provisioning: ProvisioningConfig = field(default_factory=ProvisioningConfig)
    scheduling: SchedulingConfig = field(default_factory=SchedulingConfig)
    reliability: ReliabilityConfig = field(default_factory=ReliabilityConfig)
    
    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "metadata": {
                "name": self.metadata.name,
                "version": self.metadata.version,
                "description": self.metadata.description,
            },
            "concurrency": {
                "global_max": self.concurrency.global_max,
                "group_buckets": self.concurrency.group_buckets,
            },
            "provisioning": {
                "mode": self.provisioning.mode.value,
                "auto_create_limit": self.provisioning.auto_create_limit,
                "reuse_policy": self.provisioning.reuse_policy.value,
                "environment_template": self.provisioning.environment_template,
            },
            "scheduling": {
                "default_priority": self.scheduling.default_priority,
                "timeout_seconds": self.scheduling.timeout_seconds,
            },
            "reliability": {
                "max_retries": self.reliability.max_retries,
                "backoff_strategy": self.reliability.backoff_strategy.value,
                "backoff_factor": self.reliability.backoff_factor,
                "backoff_base_seconds": self.reliability.backoff_base_seconds,
            },
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrategyProfile":
        """从字典反序列化。"""
        metadata_data = data.get("metadata", {})
        concurrency_data = data.get("concurrency", {})
        provisioning_data = data.get("provisioning", {})
        scheduling_data = data.get("scheduling", {})
        reliability_data = data.get("reliability", {})
        
        return cls(
            metadata=StrategyMetadata(
                name=metadata_data.get("name", "default"),
                version=metadata_data.get("version", "1.0"),
                description=metadata_data.get("description", ""),
            ),
            concurrency=ConcurrencyConfig(
                global_max=concurrency_data.get("global_max", 10),
                group_buckets=concurrency_data.get("group_buckets", {}),
            ),
            provisioning=ProvisioningConfig(
                mode=ProvisioningMode(provisioning_data.get("mode", "hybrid")),
                auto_create_limit=provisioning_data.get("auto_create_limit", 5),
                reuse_policy=ReusePolicy(provisioning_data.get("reuse_policy", "clean")),
                environment_template=provisioning_data.get("environment_template", {}),
            ),
            scheduling=SchedulingConfig(
                default_priority=scheduling_data.get("default_priority", 100),
                timeout_seconds=scheduling_data.get("timeout_seconds", 300),
            ),
            reliability=ReliabilityConfig(
                max_retries=reliability_data.get("max_retries", 3),
                backoff_strategy=BackoffStrategy(reliability_data.get("backoff_strategy", "exponential")),
                backoff_factor=reliability_data.get("backoff_factor", 2.0),
                backoff_base_seconds=reliability_data.get("backoff_base_seconds", 5),
            ),
        )
    
    def merge(self, override: "StrategyProfile") -> "StrategyProfile":
        """合并策略（override 优先）。
        
        规格 5.3.2 策略生效范围: Task > Module > Global
        """
        # 简单的字段覆盖合并
        return StrategyProfile(
            metadata=override.metadata if override.metadata.name != "default" else self.metadata,
            concurrency=ConcurrencyConfig(
                global_max=override.concurrency.global_max if override.concurrency.global_max != 10 else self.concurrency.global_max,
                group_buckets={**self.concurrency.group_buckets, **override.concurrency.group_buckets},
            ),
            provisioning=override.provisioning if override.provisioning.mode != ProvisioningMode.HYBRID else self.provisioning,
            scheduling=override.scheduling if override.scheduling.default_priority != 100 else self.scheduling,
            reliability=override.reliability if override.reliability.max_retries != 3 else self.reliability,
        )


# 默认策略
DEFAULT_STRATEGY = StrategyProfile(
    metadata=StrategyMetadata(name="default_conservative", version="1.0"),
    concurrency=ConcurrencyConfig(global_max=10),
    provisioning=ProvisioningConfig(mode=ProvisioningMode.HYBRID),
)
