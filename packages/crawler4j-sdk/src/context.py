"""SDK 导出：TaskContext 与相关契约类型。"""

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
from crawler4j_contracts.signal import EnvAction, TaskSignal, TaskSignalAction

__all__ = [
    "TaskContext",
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
]
