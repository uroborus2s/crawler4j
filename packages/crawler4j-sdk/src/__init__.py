"""Crawler4j SDK - 任务脚本开发工具包。

本包聚合导出模块开发所需的稳定契约与基类，供标准模块直接依赖。
稳定契约类型由 `crawler4j-contracts` 提供，SDK 负责补充 TaskScript、
TaskFlow 与 ModuleAssembler 等开发入口。
"""

from crawler4j_sdk._version import get_version
from crawler4j_sdk.base import TaskScript
from crawler4j_sdk.workflow import TaskFlow
from crawler4j_sdk.assembler import ModuleAssembler
from crawler4j_sdk.env_selector import EnvSelectorInfo, env_selector
from crawler4j_sdk.resource_pool import (
    bind_resource_pool,
    mark_resource_pool_eligible,
    mark_resource_pool_ineligible,
    remove_resource_pool,
    replace_resource_pool_snapshot,
)
from crawler4j_contracts import (
    BBox,
    ClickCaptchaDebugInfo,
    ClickCaptchaMatchResult,
    ClickCaptchaOrderedTarget,
    EnvCandidate,
    EnvAction,
    ImageInput,
    Point,
    SliderCaptchaDebugInfo,
    SliderCaptchaMatchResult,
    TaskContext,
    TaskResult,
    TaskSignal,
    TaskSignalAction,
    ToolSpec,
    ToolsCapability,
)

__version__ = get_version()

# 稳定导出列表（同 MAJOR 版本内冻结）
__all__ = [
    # 核心契约类型
    "TaskScript",
    "TaskFlow",
    "ModuleAssembler",
    "env_selector",
    "EnvSelectorInfo",
    "bind_resource_pool",
    "mark_resource_pool_eligible",
    "mark_resource_pool_ineligible",
    "remove_resource_pool",
    "replace_resource_pool_snapshot",
    "TaskContext",
    "TaskResult",
    "TaskSignal",
    "TaskSignalAction",
    "EnvAction",
    "ImageInput",
    "BBox",
    "Point",
    "ToolSpec",
    "ToolsCapability",
    "SliderCaptchaDebugInfo",
    "SliderCaptchaMatchResult",
    "ClickCaptchaDebugInfo",
    "ClickCaptchaOrderedTarget",
    "ClickCaptchaMatchResult",
    "EnvCandidate",
]
