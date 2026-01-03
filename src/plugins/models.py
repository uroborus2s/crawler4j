"""任务插件系统数据模型。

定义任务模板、任务配置、任务流、Hooks等核心数据结构。
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HookType(str, Enum):
    """环境生命周期钩子类型"""
    BEFORE_CREATE = "before_create"
    AFTER_CREATE = "after_create"
    BEFORE_START = "before_start"
    AFTER_START = "after_start"
    BEFORE_STOP = "before_stop"
    AFTER_STOP = "after_stop"
    BEFORE_DESTROY = "before_destroy"
    AFTER_DESTROY = "after_destroy"


class HandlerType(str, Enum):
    """钩子处理器类型"""
    PREDEFINED = "predefined"  # 预定义动作
    CUSTOM = "custom"          # 自定义代码


class TaskPhase(Enum):
    """任务执行阶段"""
    INIT = "init"
    AUTH = "auth"
    ACQUIRE = "acquire"
    PROCESS = "process"
    SUBMIT = "submit"
    CLEANUP = "cleanup"


@dataclass
class TaskTemplate:
    """任务模板"""
    id: int | None = None
    name: str = ""
    display_name: str = ""
    description: str = ""
    plugin_type: str = ""
    default_config: dict = field(default_factory=dict)
    is_system: bool = False
    created_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "TaskTemplate":
        default_config = data.get("default_config", "{}")
        if isinstance(default_config, str):
            default_config = json.loads(default_config) if default_config else {}
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            plugin_type=data.get("plugin_type", ""),
            default_config=default_config,
            is_system=bool(data.get("is_system", 0)),
            created_at=data.get("created_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "plugin_type": self.plugin_type,
            "default_config": json.dumps(self.default_config, ensure_ascii=False),
            "is_system": 1 if self.is_system else 0,
        }


@dataclass
class TaskConfig:
    """任务配置"""
    id: int | None = None
    name: str = ""
    template_id: int | None = None
    config: dict = field(default_factory=dict)
    enabled: bool = True
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "TaskConfig":
        config = data.get("config", "{}")
        if isinstance(config, str):
            config = json.loads(config) if config else {}
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            template_id=data.get("template_id"),
            config=config,
            enabled=bool(data.get("enabled", 1)),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "template_id": self.template_id,
            "config": json.dumps(self.config, ensure_ascii=False),
            "enabled": 1 if self.enabled else 0,
        }


@dataclass
class TaskFlowNode:
    """任务流节点"""
    id: str                          # 节点唯一ID
    task_config_id: int              # 关联的任务配置
    position: tuple[int, int] = (0, 0)  # UI位置
    next_on_success: str | None = None  # 成功后下一节点
    next_on_failure: str | None = None  # 失败后动作
    retry_count: int = 3

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_config_id": self.task_config_id,
            "position": list(self.position),
            "next_on_success": self.next_on_success,
            "next_on_failure": self.next_on_failure,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskFlowNode":
        pos = data.get("position", [0, 0])
        return cls(
            id=data["id"],
            task_config_id=data["task_config_id"],
            position=tuple(pos) if isinstance(pos, list) else pos,
            next_on_success=data.get("next_on_success"),
            next_on_failure=data.get("next_on_failure"),
            retry_count=data.get("retry_count", 3),
        )


@dataclass
class TaskFlow:
    """任务流"""
    id: int | None = None
    name: str = ""
    description: str = ""
    nodes: list[TaskFlowNode] = field(default_factory=list)
    start_node_id: str | None = None
    enabled: bool = True
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "TaskFlow":
        flow_data = data.get("flow_data", "{}")
        if isinstance(flow_data, str):
            flow_data = json.loads(flow_data) if flow_data else {}
        
        nodes = [TaskFlowNode.from_dict(n) for n in flow_data.get("nodes", [])]
        
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            nodes=nodes,
            start_node_id=flow_data.get("start_node_id"),
            enabled=bool(data.get("enabled", 1)),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def to_dict(self) -> dict:
        flow_data = {
            "nodes": [n.to_dict() for n in self.nodes],
            "start_node_id": self.start_node_id,
        }
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "flow_data": json.dumps(flow_data, ensure_ascii=False),
            "enabled": 1 if self.enabled else 0,
        }


@dataclass
class EnvironmentHook:
    """环境生命周期钩子"""
    id: int | None = None
    environment_id: int | None = None  # None表示全局模板
    hook_type: HookType = HookType.BEFORE_START
    handler_type: HandlerType = HandlerType.PREDEFINED
    handler_code: str = ""
    priority: int = 0
    enabled: bool = True
    created_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "EnvironmentHook":
        return cls(
            id=data.get("id"),
            environment_id=data.get("environment_id"),
            hook_type=HookType(data.get("hook_type", "before_start")),
            handler_type=HandlerType(data.get("handler_type", "predefined")),
            handler_code=data.get("handler_code", ""),
            priority=data.get("priority", 0),
            enabled=bool(data.get("enabled", 1)),
            created_at=data.get("created_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "environment_id": self.environment_id,
            "hook_type": self.hook_type.value,
            "handler_type": self.handler_type.value,
            "handler_code": self.handler_code,
            "priority": self.priority,
            "enabled": 1 if self.enabled else 0,
        }


@dataclass
class TaskContext:
    """任务执行上下文"""
    env_id: int | None
    page: Any  # Playwright Page
    context: Any  # Playwright BrowserContext
    config: dict[str, Any] = field(default_factory=dict)
    is_auto_mode: bool = True
    input_callback: Any = None


@dataclass
class TaskStepResult:
    """单步执行结果"""
    success: bool
    message: str = ""
    data: Any = None
    should_retry: bool = False
    should_abort: bool = False


@dataclass
class TaskResult:
    """任务最终结果"""
    success: bool
    tasks_completed: int = 0
    message: str = ""
    error_code: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class FlowResult:
    """任务流执行结果"""
    success: bool
    completed_nodes: int = 0
    message: str = ""
