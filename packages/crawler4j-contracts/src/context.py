"""TaskContext 任务执行上下文契约。

本模块定义 Crawler4j Core 与 SDK 共享的稳定契约：TaskContext。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page


@runtime_checkable
class HttpClient(Protocol):
    """HTTP 客户端协议。"""

    async def get(self, url: str, **kwargs: Any) -> dict[str, Any]:
        ...

    async def post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        ...


ImageInput = str | Path | bytes
BBox = tuple[int, int, int, int]
Point = tuple[int, int]


@dataclass(frozen=True)
class ToolSpec:
    """Core 注入工具的元数据描述。"""

    name: str
    description: str
    is_async: bool = False


@runtime_checkable
class ToolsCapability(Protocol):
    """Core 注入给脚本的统一工具入口。"""

    def has_tool(self, tool_name: str) -> bool:
        """检查工具是否存在。"""
        ...

    def list_tools(self) -> list[ToolSpec]:
        """列出当前可用工具。"""
        ...

    def call(self, tool_name: str, /, **kwargs: Any) -> Any:
        """调用 Core 工具；异步工具返回 awaitable。"""
        ...


@dataclass(frozen=True)
class SliderCaptchaDebugInfo:
    """滑块验证码调试信息。"""

    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClickCaptchaDebugInfo:
    """点选验证码调试信息。"""

    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SliderCaptchaMatchResult:
    """滑块验证码匹配结果。"""

    target_center: Point
    target_bbox: BBox
    puzzle_piece_offset: Point | None = None
    debug: SliderCaptchaDebugInfo | None = None


@dataclass(frozen=True)
class ClickCaptchaOrderedTarget:
    """点选验证码排序后的单个目标。"""

    query_order: int
    center: Point
    class_id: int
    class_name: str
    score: float


@dataclass(frozen=True)
class ClickCaptchaMatchResult:
    """点选验证码匹配结果。"""

    ordered_target_centers: list[Point]
    ordered_targets: list[ClickCaptchaOrderedTarget]
    missing_query_orders: list[int] = field(default_factory=list)
    ambiguous_query_orders: list[int] = field(default_factory=list)
    debug: ClickCaptchaDebugInfo | None = None


class DefaultHttpClient:
    """默认 HTTP 客户端实现，基于 aiohttp。"""

    async def get(self, url: str, **kwargs: Any) -> dict[str, Any]:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(url, **kwargs) as resp:
                return await resp.json()

    async def post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, **kwargs) as resp:
                return await resp.json()


@dataclass
class TaskContext:
    """任务执行上下文。"""

    env_id: int
    task_name: str
    config: dict[str, Any] = field(default_factory=dict)

    page: "Page | None" = None
    context: "BrowserContext | None" = None

    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("task"))
    http: HttpClient = field(default_factory=DefaultHttpClient)
    tools: ToolsCapability | None = None

    captured_data: list[Any] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)

    _stop_requested: bool = field(default=False, repr=False)
    _subtask_executor: Callable[..., Any] | None = field(default=None, repr=False)

    async def wait(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    async def screenshot(self, name: str) -> str:
        if not self.page:
            raise RuntimeError("Page 未初始化，无法截图")

        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = screenshots_dir / f"{name}_{timestamp}.png"

        await self.page.screenshot(path=str(path))
        self.logger.info(f"📸 截图已保存: {path}")
        return str(path)

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def should_stop(self) -> bool:
        return self._stop_requested

    def request_stop(self) -> None:
        self._stop_requested = True
        self.logger.info("已请求停止工作流")

    async def run_subtask(self, task_name: str, **kwargs: Any) -> Any:
        if not self._subtask_executor:
            raise RuntimeError("子任务执行器未注入，请确保通过框架运行")

        if kwargs:
            self.state.update(kwargs)

        self.logger.info(f"▶ 执行子任务: {task_name}")
        result = await self._subtask_executor(task_name, self)

        if result and hasattr(result, "data"):
            if result.data:
                return result.data
            if hasattr(result, "success"):
                return bool(result.success)
        return result
