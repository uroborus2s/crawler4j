"""SDK 导出：TaskContext 与相关契约类型。"""

from __future__ import annotations

from typing import Any

from crawler4j_contracts.context import (
    BBox,
    ClickCaptchaDebugInfo,
    ClickCaptchaMatchResult,
    ClickCaptchaOrderedTarget,
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
from crawler4j_contracts.signal import EnvAction, TaskSignal, TaskSignalAction


class DefaultHttpClient:
    """SDK 默认 HTTP 客户端实现，供模块显式注入使用。"""

    async def get(self, url: str, **kwargs: Any) -> dict[str, Any]:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(url, **kwargs) as response:
                return await response.json()

    async def post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, **kwargs) as response:
                return await response.json()

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
    "EnvCandidate",
]
