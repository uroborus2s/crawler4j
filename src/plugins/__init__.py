"""任务插件系统模块。

提供可扩展的任务插件架构，支持：
- 任务模板和配置管理
- 任务流编排
- 环境生命周期Hooks
"""

from src.plugins.flow_engine import ExecutionOptions, TaskFlowEngine
from src.plugins.hooks import HooksManager, get_hooks_manager
from src.plugins.models import (
    EnvironmentHook,
    FlowResult,
    HandlerType,
    HookType,
    TaskConfig,
    TaskContext,
    TaskFlow,
    TaskFlowNode,
    TaskPhase,
    TaskResult,
    TaskStepResult,
    TaskTemplate,
)
from src.plugins.repositories import (
    EnvironmentHooksRepository,
    EnvironmentTasksRepository,
    TaskConfigRepository,
    TaskFlowRepository,
    TaskTemplateRepository,
)

__all__ = [
    # 数据模型
    "TaskTemplate",
    "TaskConfig",
    "TaskFlow",
    "TaskFlowNode",
    "EnvironmentHook",
    "HookType",
    "HandlerType",
    "TaskPhase",
    "TaskContext",
    "TaskResult",
    "TaskStepResult",
    "FlowResult",
    # Repository
    "TaskTemplateRepository",
    "TaskConfigRepository",
    "TaskFlowRepository",
    "EnvironmentHooksRepository",
    "EnvironmentTasksRepository",
    # 核心引擎
    "HooksManager",
    "get_hooks_manager",
    "TaskFlowEngine",
    "ExecutionOptions",
]
