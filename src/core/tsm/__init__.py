"""任务策略管理 (Task Strategy Management)。

规格参考: docs/srs/05-framework-core/05-3-task-strategy-management.md

导出:
    - StrategyProfile, ConcurrencyConfig, etc.: 策略模型
    - AdmissionController, AdmissionDecision: 准入控制
    - StrategyLoader: 策略加载
"""

from src.core.tsm.admission import (
    AdmissionController,
    AdmissionDecision,
    AdmissionResult,
    TaskSubmission,
    get_admission_controller,
)
from src.core.tsm.loader import (
    StrategyLoader,
    get_strategy_loader,
)
from src.core.tsm.models import (
    DEFAULT_STRATEGY,
    BackoffStrategy,
    ConcurrencyConfig,
    ProvisioningConfig,
    ProvisioningMode,
    ReliabilityConfig,
    ReusePolicy,
    SchedulingConfig,
    StrategyMetadata,
    StrategyProfile,
)

__all__ = [
    # 策略模型
    "StrategyProfile",
    "StrategyMetadata",
    "ConcurrencyConfig",
    "ProvisioningConfig",
    "SchedulingConfig",
    "ReliabilityConfig",
    "ProvisioningMode",
    "ReusePolicy",
    "BackoffStrategy",
    "DEFAULT_STRATEGY",
    # 准入控制
    "AdmissionController",
    "AdmissionDecision",
    "AdmissionResult",
    "TaskSubmission",
    "get_admission_controller",
    # 策略加载
    "StrategyLoader",
    "get_strategy_loader",
]
