"""外部状态同步模块。

设计参考: docs/design/module-01-runtime-environment.md §5.3

提供外部指纹浏览器服务的状态同步功能：
    - ExternalSyncManager: 外部状态同步管理器
"""

import asyncio
from typing import TYPE_CHECKING

from src.core.foundation.logging import logger
from src.core.rem.models import EnvStatus

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
    ) -> None:
        """初始化同步管理器。
        
        Args:
            pool: 环境池
            sync_interval: 同步间隔（秒）
        """
        self._pool = pool
        self._sync_interval = sync_interval
        self._running = False
        self._sync_task: asyncio.Task | None = None
        self._providers: dict[str, "BaseProvider"] = {}
    
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
        """执行全量同步。
        
        Returns:
            每个 provider 的同步数量
        """
        results = {}
        for provider_name, provider in self._providers.items():
            try:
                count = await self._sync_provider(provider)
                results[provider_name] = count
                if count > 0:
                    logger.info(f"[Sync] 同步 {provider_name}: {count} 个环境状态变化")
            except Exception as e:
                logger.error(f"[Sync] 同步 {provider_name} 失败: {e}")
                results[provider_name] = -1
        return results
    
    async def _sync_provider(self, provider: "BaseProvider") -> int:
        """同步单个 Provider 的状态。
        
        Args:
            provider: Provider 实例
            
        Returns:
            状态变化的环境数量
        """
        changed_count = 0
        
        # 获取该 Provider 的所有环境
        envs = [
            env for env in await self._pool.list_all()
            if env.provider == provider.name and env.external_id
        ]
        
        for env in envs:
            try:
                # 检查外部状态
                is_running = await provider.is_running(env)
                
                if env.status == EnvStatus.BUSY and not is_running:
                    # 外部已停止但本地仍为 BUSY
                    logger.warning(
                        f"[Sync] 环境外部已停止: id={env.id}... external={env.external_id}"
                    )
                    await self._pool.update_status(env.id, EnvStatus.ERROR)
                    changed_count += 1
                    
                elif env.status == EnvStatus.READY and not is_running:
                    # READY 状态但外部已停止
                    logger.warning(
                        f"[Sync] 环境外部不存在: id={env.id}... external={env.external_id}"
                    )
                    await self._pool.update_status(env.id, EnvStatus.DEAD)
                    changed_count += 1
                    
            except Exception as e:
                logger.error(f"[Sync] 检查环境状态失败: id={env.id}... error={e}")
        
        return changed_count
    
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
