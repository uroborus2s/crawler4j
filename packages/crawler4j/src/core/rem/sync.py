"""外部状态同步模块。

当前外部状态调和统一委托给 REM GC，避免再维护一套平行状态机。
"""

import asyncio
from typing import TYPE_CHECKING, Awaitable, Callable

from src.core.foundation.logging import logger
from src.core.rem.manager import get_environment_manager

if TYPE_CHECKING:
    from src.core.rem.pool import EnvPool
    from src.core.rem.provider import BaseProvider


class ExternalSyncManager:
    """外部状态同步管理器。
    
    设计文档 5.3: 外部状态同步
    
    解决以下问题：
        - 外部手动关闭浏览器 → 程序状态仍为 BUSY
        - 程序崩溃 → 外部环境仍在运行
        - 外部删除环境 → 程序环境失效
    """
    
    def __init__(
        self,
        pool: "EnvPool",
        sync_interval: int = 30,
        gc_runner: Callable[[], Awaitable[int]] | None = None,
    ) -> None:
        """初始化同步管理器。"""
        self._pool = pool
        self._sync_interval = sync_interval
        self._running = False
        self._sync_task: asyncio.Task | None = None
        self._providers: dict[str, "BaseProvider"] = {}
        self._gc_runner = gc_runner or get_environment_manager().run_gc
    
    def register_provider(self, provider: "BaseProvider") -> None:
        """注册需要同步的 Provider。"""
        self._providers[provider.name] = provider
    
    async def startup(self) -> None:
        """启动同步管理器。"""
        if self._running:
            return
        
        self._running = True
        
        # 启动时执行全量同步
        await self.full_sync()
        
        # 启动后台同步任务
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("[Sync] 外部状态同步已启动")
    
    async def shutdown(self) -> None:
        """关闭同步管理器。"""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("[Sync] 外部状态同步已关闭")
    
    async def full_sync(self) -> dict[str, int]:
        """执行全量同步。"""
        try:
            count = await self._gc_runner()
        except Exception as e:
            logger.error(f"[Sync] 执行 REM GC 同步失败: {e}")
            return {"gc": -1}

        if count > 0:
            logger.info(f"[Sync] 通过 REM GC 收口 {count} 个环境漂移")
        return {"gc": count}
    
    async def _sync_loop(self) -> None:
        """后台同步循环。"""
        while self._running:
            try:
                await asyncio.sleep(self._sync_interval)
                if self._running:
                    await self.full_sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Sync] 同步循环异常: {e}")
