"""TSM 数据模型 (V2)。

规格参考: docs/srs/05-framework-core/05-3-task-strategy-management.md

定义核心策略模型:
    - ResourceSelector: 资源选择
        - MatchGroup/MatchCondition: 规则 AST
    - ScalingPolicy: 弹性伸缩
    - RetryPolicy: 容错策略
    - TeardownPolicy: 清理策略
    - TaskStrategy: 策略主类

运行时结果模型:
    - InstanceResult: 单实例执行结果
    - OrchestratorResult: 编排总结果
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field

# =============================================================================
# Enums
# =============================================================================

class EnvType(str, Enum):
    CHROME = "chrome"
    ANDROID = "android"
    BIT_BROWSER = "bit_browser"
    VIRTUAL_BROWSER = "virtual_browser"
    DEBUG_DUMMY = "debug_dummy"  # 调试用


class SelectionStrategy(str, Enum):
    RANDOM = "random"
    FIFO = "fifo"      # 最早空闲
    LIFO = "lifo"      # 最近使用
    BEST_FIT = "best_fit" # 基于健康度/评分


class ScalingMode(str, Enum):
    STRICT = "strict"    # 仅使用现有资源
    ELASTIC = "elastic"  # 允许自动创建


class TeardownAction(str, Enum):
    DESTROY = "destroy"
    RECYCLE = "recycle"   # 软重置后复用
    HIBERNATE = "hibernate"
    KEEP_ALIVE = "keep_alive"

# --- Rule Engine Enums ---

class LogicOp(str, Enum):
    AND = "AND"
    OR = "OR"

class ComparisonOp(str, Enum):
    EQ = "=="
    NEQ = "!="
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    CONTAINS = "contains"
    IN = "in"

class ValueType(str, Enum):
    STATIC = "static"   # 静态值
    FIELD = "field"     # 字段引用
    PARAM = "param"     # 外部参数引用

# =============================================================================
# Rule AST Models
# =============================================================================

class MatchCondition(BaseModel):
    """单个规则条件 (叶子节点)。"""
    field: str              # 左值字段
    op: ComparisonOp        # 操作符
    value: Any              # 右值
    value_type: ValueType = ValueType.STATIC

class MatchGroup(BaseModel):
    """逻辑规则组 (中间节点)。"""
    logic: LogicOp
    # 使用 ForwardRef 或直接引用，Pydantic 支持递归
    conditions: List[Union["MatchGroup", MatchCondition]] = Field(default_factory=list)

# =============================================================================
# Sub-Policies
# =============================================================================

class ResourceSelector(BaseModel):
    """资源选择策略。解决'找到最合适的环境'。"""
    env_type: EnvType = Field(..., description="环境类型")
    match_labels: Dict[str, str] = Field(default_factory=dict, description="精确匹配标签")
    
    # 旧的简单表达式列表 (Deprecated or Simple Mode)
    match_expressions: List[str] = Field(default_factory=list, description="简单逻辑表达式")
    
    # 新的 AST 规则树 (Advanced Mode)
    match_rules: Optional[MatchGroup] = Field(None, description="结构化匹配规则树")
    
    sort_strategy: SelectionStrategy = Field(default=SelectionStrategy.FIFO)
    wait_timeout: int = Field(default=60, ge=0, description="等待资源的超时时间(秒)")


class ScalingPolicy(BaseModel):
    """弹性伸缩策略。解决'资源不足时的决策'。"""
    mode: ScalingMode = Field(default=ScalingMode.STRICT)
    max_concurrency: int = Field(default=1, ge=1, description="最大并发/实例数")
    min_idle: int = Field(default=0, ge=0, description="保持最小空闲实例数(预热)")
    init_workflow: Optional[str] = Field(None, description="新环境初始化工作流(e.g., login)")
    creation_timeout: int = Field(default=120, ge=0, description="创建新环境超时(秒)")


class ExecutionContext(BaseModel):
    """执行目标上下文。"""
    module: str
    workflow: str = "default"
    params: Dict[str, Any] = Field(default_factory=dict)
    timeout: int = Field(default=600, ge=0, description="执行超时(秒)")


class RetryPolicy(BaseModel):
    """容错重试策略。解决'运行时的稳定性'。"""
    max_attempts: int = Field(default=1, ge=1)
    retry_on_condition: List[str] = Field(default_factory=list, description="触发重试的错误条件")
    new_env_on_retry: bool = Field(default=True, description="重试时是否更换环境")


class TeardownPolicy(BaseModel):
    """生命周期清理策略。解决'任务结束后的处置'。"""
    on_success: TeardownAction = Field(default=TeardownAction.RECYCLE)
    on_failure: TeardownAction = Field(default=TeardownAction.KEEP_ALIVE)
    on_timeout: TeardownAction = Field(default=TeardownAction.DESTROY)


# =============================================================================
# Main Strategy
# =============================================================================

class TaskStrategy(BaseModel):
    """TSM 核心策略定义 (V2)。"""
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = ""

    # 1. 资源选择
    selector: ResourceSelector

    # 2. 弹性伸缩
    scaling: ScalingPolicy = Field(default_factory=ScalingPolicy)

    # 3. 目标执行
    execution: Optional[ExecutionContext] = None

    # 4. 容错控制
    retry: RetryPolicy = Field(default_factory=RetryPolicy)

    # 5. 清理策略
    teardown: TeardownPolicy = Field(default_factory=TeardownPolicy)

    def to_yaml(self) -> str:
        """转换为 YAML 字符串。"""
        return yaml.dump(self.model_dump(mode="json"), allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "TaskStrategy":
        """从 YAML 加载。"""
        data = yaml.safe_load(yaml_content)
        return cls(**data)


# 默认空策略 (用于占位)
DEFAULT_STRATEGY = TaskStrategy(
    id="default",
    name="Default Strategy",
    selector=ResourceSelector(env_type=EnvType.DEBUG_DUMMY),
)


# =============================================================================
# Runtime Results
# =============================================================================

@dataclass
class InstanceResult:
    """单实例执行结果。"""
    env_id: str
    success: bool
    message: str = ""
    error: str = ""
    started_at: int = 0
    ended_at: int = 0


@dataclass
class OrchestratorResult:
    """编排总结果。"""
    strategy_id: str
    success: bool
    total_instances: int
    succeeded_instances: int
    failed_instances: int
    results: List[InstanceResult] = field(default_factory=list)
    started_at: int = 0
    ended_at: int = 0
