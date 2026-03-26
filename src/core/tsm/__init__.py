"""TSM (Task Strategy Management) 模块。

核心组件:
    - TaskStrategy: V2 策略模型
    - StrategyLoader: 策略加载器
"""

from src.core.tsm.loader import (
    StrategyLoader,
    get_strategy_loader,
    init_strategy_loader,
)
from src.core.tsm.models import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    CreationLifecycle,
    DEFAULT_STRATEGY,
    ComparisonOp,
    EnvType,
    ExecutionContext,
    InstanceResult,
    LogicOp,
    MatchCondition,
    MatchGroup,
    OrchestratorResult,
    MatchConfig,
    RetryPolicy,
    ResourceConfig,
    SelectionStrategy,
    TaskStrategy,
    TeardownAction,
    TeardownPolicy,
    ValueType,
)

__all__ = [
    # V2 策略模型
    "TaskStrategy",
    "ResourceConfig",
    "AcquisitionConfig",
    "MatchConfig",
    "CreationConfig",
    "RetryPolicy",
    "TeardownPolicy",
    "ExecutionContext",
    "AcquisitionMode",
    "CreationLifecycle",
    "EnvType",
    "SelectionStrategy",
    "TeardownAction",
    "DEFAULT_STRATEGY",
    "InstanceResult",
    "OrchestratorResult",
    # Rule AST
    "LogicOp",
    "ComparisonOp",
    "ValueType",
    "MatchCondition",
    "MatchGroup",
    # 策略加载
    "StrategyLoader",
    "get_strategy_loader",
    "init_strategy_loader",
]
