"""Crawler4j Contracts - Core <-> SDK 共享契约包。

本包只承载稳定契约类型，不包含运行时实现。
"""

from crawler4j_contracts.context import (
    BBox,
    ClickCaptchaDebugInfo,
    ClickCaptchaMatchResult,
    ClickCaptchaOrderedTarget,
    DefaultHttpClient,
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

__version__ = "1.1.0"

__all__ = [
    "TaskContext",
    "TaskResult",
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
]
