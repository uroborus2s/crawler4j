"""环境管理器 - 统一门面。

规格参考: docs/srs/05-framework-core/05-2-runtime-environment-management.md

EnvironmentManager 是 REM 的统一入口，提供：
    - acquire: 申请环境租约
    - release: 释放环境租约
    - startup: 初始化与崩溃恢复
    - run_gc: 垃圾回收
"""

import asyncio
import time

from src.core.foundation.logging import logger
from src.core.rem.models import (
    EnvCleanupFailedError,
    Environment,
    EnvKind,
    EnvLease,
    EnvRequirement,
    EnvStatus,
    EnvUnavailableError,
    EnvUnhealthyError,
)
from src.core.rem.pool import EnvPool, LeaseManager
from src.core.rem.provider import BaseProvider, get_provider, register_provider


class EnvironmentManager:
    """环境管理器。
    
    规格 5.2.1.2: 核心承诺是为每一次任务运行提供满足约束的环境租约。
    
    Usage:
        manager = EnvironmentManager()
        await manager.startup()
        
        # 申请环境
        requirement = EnvRequirement(kind=EnvKind.BROWSER)
        lease = await manager.acquire(requirement)
        
        # 使用环境...
        env = await manager.get_env(lease.env_id)
        
        # 释放环境
        await manager.release(lease)
    """
    
    def __init__(
        self,
        max_instances: int = 10,
        gc_interval: int = 60,
    ):
        """初始化环境管理器。
        
        Args:
            max_instances: 最大环境实例数
            gc_interval: 垃圾回收间隔（秒）
        """
        self.pool = EnvPool(max_instances=max_instances)
        self.lease_manager = LeaseManager(self.pool)
        self._gc_interval = gc_interval
        self._gc_task: asyncio.Task | None = None
        self._running = False
    
    async def startup(self) -> None:
        """启动环境管理器。
        
        执行：
            1. 从数据库恢复环境状态
            2. 处理崩溃残留
            3. 启动 GC 循环
        """
        logger.info("[REM] 环境管理器启动中...")
        
        # 从数据库恢复
        await self.pool.load_from_db()
        
        # 处理崩溃残留
        await self._recover_crashed()
        
        # 启动 GC
        self._running = True
        self._gc_task = asyncio.create_task(self._gc_loop())
        
        logger.info(f"[REM] 环境管理器启动完成, 环境数: {len(await self.pool.list_all())}")
    
    async def shutdown(self) -> None:
        """关闭环境管理器。"""
        logger.info("[REM] 环境管理器关闭中...")
        
        self._running = False
        if self._gc_task:
            self._gc_task.cancel()
            try:
                await self._gc_task
            except asyncio.CancelledError:
                pass
        
        # 释放所有环境
        for env in await self.pool.list_all():
            await self._destroy_env(env)
        
        logger.info("[REM] 环境管理器已关闭")
    
    async def acquire(
        self,
        requirement: EnvRequirement,
        default_provider: str = "playwright_local",
    ) -> EnvLease:
        """申请环境租约。
        
        规格 5.2.3.3 Acquire 流程：
            1. 在 READY 实例中挑选匹配项
            2. 若无匹配，按策略 spawn 新实例
            3. 发放租约，将实例置为 BUSY
        
        Args:
            requirement: 环境需求
            default_provider: 默认提供者
        
        Returns:
            环境租约
        
        Raises:
            EnvUnavailableError: 无可用环境
        """
        # 1. 查找可用环境
        env = await self.pool.find_available(requirement)
        
        # 2. 无可用环境则尝试创建
        if not env:
            if not self.pool.can_create():
                raise EnvUnavailableError(
                    "无可用环境且达到配额上限",
                    stage="ACQUIRE",
                    hint="请等待其他任务完成或增加配额"
                )
            
            provider = get_provider(default_provider)
            if not provider:
                raise EnvUnavailableError(
                    f"Provider 未注册: {default_provider}",
                    stage="CREATE",
                    hint="请检查 Provider 配置"
                )
            
            env = await self._create_env(provider)
        
        # 3. 发放租约
        lease = await self.lease_manager.acquire(
            env,
            requirement.task_run_id,
            timeout=requirement.timeout,
        )
        
        return lease
    
    async def release(self, lease: EnvLease, dirty: bool = False) -> bool:
        """释放环境租约。
        
        规格 5.2.3.3 Release 流程：
            1. 验证令牌
            2. 执行清理
            3. 健康检查
            4. 成功则回到 READY，失败则标记 UNHEALTHY
        
        Args:
            lease: 租约
            dirty: 是否标记为脏（需要重新创建）
        
        Returns:
            是否释放成功
        """
        env = await self.lease_manager.release(lease, lease.token)
        if not env:
            return False
        
        if dirty:
            # 直接标记为不健康
            await self.pool.update_status(env.id, EnvStatus.UNHEALTHY)
            return True
        
        # 执行清理
        provider = get_provider(env.provider)
        if provider:
            try:
                success = await provider.reset(env)
                if not success:
                    await self.pool.update_status(env.id, EnvStatus.UNHEALTHY)
                    return True
            except Exception as e:
                logger.warning(f"[REM] 环境清理失败: {e}")
                await self.pool.update_status(env.id, EnvStatus.UNHEALTHY)
                return True
        
        # 健康检查
        if provider:
            try:
                healthy = await provider.health_check(env)
                if not healthy:
                    await self.pool.update_status(env.id, EnvStatus.UNHEALTHY)
                    return True
            except Exception as e:
                logger.warning(f"[REM] 健康检查失败: {e}")
                await self.pool.update_status(env.id, EnvStatus.UNHEALTHY)
                return True
        
        # 回到 READY
        await self.pool.update_status(env.id, EnvStatus.READY)
        return True
    
    async def get_env(self, env_id: str) -> Environment | None:
        """获取环境实例。"""
        return await self.pool.get(env_id)
    
    async def list_envs(self) -> list[Environment]:
        """列出所有环境。"""
        return await self.pool.list_all()
    
    async def run_gc(self) -> int:
        """手动触发垃圾回收。
        
        Returns:
            回收的环境数量
        """
        return await self._gc_once()
    
    # === 私有方法 ===
    
    async def _create_env(self, provider: BaseProvider) -> Environment:
        """创建环境。"""
        logger.info(f"[REM] 创建环境: provider={provider.name}")
        
        env = await provider.create()
        await self.pool.add(env)
        
        logger.info(f"[REM] 环境创建完成: id={env.id[:8]}...")
        return env
    
    async def _destroy_env(self, env: Environment) -> None:
        """销毁环境。"""
        logger.info(f"[REM] 销毁环境: id={env.id[:8]}...")
        
        await self.pool.update_status(env.id, EnvStatus.TERMINATING)
        
        provider = get_provider(env.provider)
        if provider:
            try:
                await provider.destroy(env)
            except Exception as e:
                logger.warning(f"[REM] 环境销毁失败: {e}")
        
        await self.pool.remove(env.id)
        logger.info(f"[REM] 环境已销毁: id={env.id[:8]}...")
    
    async def _recover_crashed(self) -> None:
        """崩溃恢复：处理非稳态环境。
        
        规格 5.2（崩溃恢复）：
            查询 BUSY/CLEANING/CREATING 状态的环境，标记为僵尸并清理。
        """
        unstable_statuses = {EnvStatus.BUSY, EnvStatus.CREATING}
        
        for env in await self.pool.list_all():
            if env.status in unstable_statuses:
                logger.warning(f"[REM] 发现僵尸环境: id={env.id[:8]}... status={env.status}")
                await self.pool.update_status(env.id, EnvStatus.UNHEALTHY)
    
    async def _gc_loop(self) -> None:
        """GC 循环。"""
        while self._running:
            try:
                await asyncio.sleep(self._gc_interval)
                await self._gc_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[REM] GC 异常: {e}")
    
    async def _gc_once(self) -> int:
        """执行一次 GC。
        
        Returns:
            回收的环境数量
        """
        count = 0
        
        # 回收 UNHEALTHY 和 DEAD 环境
        for env in await self.pool.list_by_status(EnvStatus.UNHEALTHY):
            await self._destroy_env(env)
            count += 1
        
        for env in await self.pool.list_by_status(EnvStatus.DEAD):
            await self._destroy_env(env)
            count += 1
        
        # 检查过期租约
        for lease in await self.lease_manager.list_expired():
            logger.warning(f"[REM] 租约过期，强制回收: lease={lease.id[:8]}...")
            env = await self.pool.get(lease.env_id)
            if env:
                await self.pool.update_status(env.id, EnvStatus.UNHEALTHY)
        
        if count > 0:
            logger.info(f"[REM] GC 完成: 回收 {count} 个环境")
        
        return count


# 全局单例
_manager: EnvironmentManager | None = None


def get_environment_manager() -> EnvironmentManager:
    """获取全局 EnvironmentManager 实例。"""
    global _manager
    if _manager is None:
        _manager = EnvironmentManager()
    return _manager
