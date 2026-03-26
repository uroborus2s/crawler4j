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


@runtime_checkable
class DatabaseCapability(Protocol):
    """Core 注入给脚本的基础数据能力契约。"""

    def list_records(self, dataset: str) -> list[dict[str, Any]]:
        """读取模块数据集。"""
        ...

    def replace_records(self, dataset: str, records: list[dict[str, Any]]) -> bool:
        """全量覆盖模块数据集。"""
        ...

    def acquire_lock(
        self,
        scope: str,
        key: str,
        *,
        ttl: int,
        owner: dict[str, Any] | None = None,
    ) -> bool:
        """获取数据锁（幂等互斥）。"""
        ...

    def release_lock(self, scope: str, key: str) -> bool:
        """释放数据锁。"""
        ...

    def is_locked(self, scope: str, key: str) -> bool:
        """查询数据锁状态。"""
        ...

    def get_state(self, key: str) -> Any:
        """读取运行时状态。"""
        ...

    def set_state(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """写入运行时状态。"""
        ...

    def exists_state(self, key: str) -> bool:
        """检查运行时状态键是否存在。"""
        ...


@runtime_checkable
class IPPoolCapability(Protocol):
    """Core 注入给脚本的 IP 池能力契约。"""

    def pick_proxy(self, criteria: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """按条件挑选可用 IP/代理。"""
        ...


@runtime_checkable
class EnvOpsCapability(Protocol):
    """Core 注入给脚本的环境操作能力契约。"""

    async def set_proxy(
        self,
        env_id: int,
        *,
        proxy_value: str | None = None,
        proxy_pool_id: str | None = None,
    ) -> bool:
        """为当前环境设置代理。"""
        ...


@runtime_checkable
class UICapability(Protocol):
    """Core 注入给脚本的 UI 声明能力契约。"""

    def declare_data_table(self, view_id: str, schema: dict[str, Any]) -> bool:
        """声明模块数据表视图元数据。"""
        ...

    def get_data_table(self, view_id: str) -> dict[str, Any]:
        """读取模块数据表视图元数据。"""
        ...


@dataclass
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
    db: DatabaseCapability | None = None
    ip_pool: IPPoolCapability | None = None
    env_ops: EnvOpsCapability | None = None
    ui: UICapability | None = None

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
