"""ATM 运行配置模型。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field


class EnvType(str, Enum):
    CHROME = "chrome"
    ANDROID = "android"
    BIT_BROWSER = "bit_browser"
    VIRTUAL_BROWSER = "virtual_browser"
    DEBUG_DUMMY = "debug_dummy"


class SelectionStrategy(str, Enum):
    RANDOM = "random"
    FIFO = "fifo"
    LIFO = "lifo"
    BEST_FIT = "best_fit"


class TeardownAction(str, Enum):
    DESTROY = "destroy"
    RECYCLE = "recycle"
    HIBERNATE = "hibernate"
    KEEP_ALIVE = "keep_alive"
    NONE = "none"


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
    STATIC = "static"
    FIELD = "field"
    PARAM = "param"


class MatchCondition(BaseModel):
    field: str
    op: ComparisonOp
    value: Any
    value_type: ValueType = ValueType.STATIC


class MatchGroup(BaseModel):
    logic: LogicOp
    conditions: List[Union["MatchGroup", MatchCondition]] = Field(default_factory=list)


class AcquisitionMode(str, Enum):
    MATCH = "match"
    CREATE = "create"


class CreationLifecycle(str, Enum):
    EPHEMERAL = "ephemeral"
    PERSISTENT = "persistent"


class CreationConfig(BaseModel):
    lifecycle: CreationLifecycle = Field(default=CreationLifecycle.EPHEMERAL)
    params: Dict[str, Any] = Field(default_factory=dict)


class MatchConfig(BaseModel):
    tags: Dict[str, str] = Field(default_factory=dict)
    status: str = Field(default="ready")
    sort_strategy: SelectionStrategy = Field(default=SelectionStrategy.FIFO)
    wait_timeout: int = Field(default=60, ge=0)
    env_type: EnvType = Field(default=EnvType.CHROME)
    match_expressions: List[str] = Field(default_factory=list)
    match_rules: Optional[MatchGroup] = Field(default=None)


class AcquisitionConfig(BaseModel):
    mode: AcquisitionMode = Field(default=AcquisitionMode.MATCH)
    selector: MatchConfig = Field(default_factory=MatchConfig)
    creation: CreationConfig = Field(default_factory=CreationConfig)


class ResourceConfig(BaseModel):
    provider: str = Field(default="playwright_local")
    acquisition: AcquisitionConfig = Field(default_factory=AcquisitionConfig)


class ExecutionContext(BaseModel):
    module: str
    workflow: str = "default"
    hooks_module: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    timeout: int = Field(default=600, ge=0)


class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=1, ge=1)
    retry_on_condition: List[str] = Field(default_factory=list)
    new_env_on_retry: bool = Field(default=True)


class TeardownPolicy(BaseModel):
    on_success: TeardownAction = Field(default=TeardownAction.RECYCLE)
    success_workflow: Optional[str] = Field(default=None)
    on_failure: TeardownAction = Field(default=TeardownAction.KEEP_ALIVE)
    failure_workflow: Optional[str] = Field(default=None)
    on_timeout: TeardownAction = Field(default=TeardownAction.DESTROY)
    timeout_workflow: Optional[str] = Field(default=None)


class RunProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource: ResourceConfig = Field(default_factory=ResourceConfig)
    execution: Optional[ExecutionContext] = None
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    teardown: TeardownPolicy = Field(default_factory=TeardownPolicy)

    def to_yaml(self) -> str:
        return yaml.dump(self.model_dump(mode="json"), allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "RunProfile":
        data = yaml.safe_load(yaml_content)
        return cls(**data)
