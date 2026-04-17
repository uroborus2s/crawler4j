"""Crawler4j Contracts - Core <-> SDK 共享契约包。

本包只承载稳定契约类型，不包含运行时实现。
"""

from crawler4j_contracts.context import (
    BBox,
    ClickCaptchaDebugInfo,
    ClickCaptchaMatchResult,
    ClickCaptchaOrderedTarget,
    DefaultHttpClient,
    EnvCandidate,
    HttpClient,
    ImageInput,
    Point,
    SliderCaptchaDebugInfo,
    SliderCaptchaMatchResult,
    TaskContext,
    ToolSpec,
    ToolsCapability,
)
from crawler4j_contracts.result import TaskResult
from crawler4j_contracts.signal import EnvAction, TaskSignal, TaskSignalAction

__all__ = [
    "TaskContext",
    "TaskResult",
    "TaskSignal",
    "TaskSignalAction",
    "EnvAction",
    "HttpClient",
    "DefaultHttpClient",
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
