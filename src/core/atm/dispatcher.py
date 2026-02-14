"""Task Dispatcher (V2).

负责单任务的生命周期管理:
1. 资源申请 (Atomic Leasing)
2. 模块执行 (Module Execution)
3. 状态更新 (State Transition)
4. 资源释放 (Resource Release)
"""

import asyncio
import time
import traceback
from typing import Any

from src.core.atm.models import Job, Task, TaskStatus
from src.core.atm.repository import get_task_repository
from src.core.foundation.logging import logger
from src.core.rem.manager import get_environment_manager
from src.core.rem.models import EnvKind, EnvRequirement

# MMS import placeholder - will be fixed after checking init
# from src.core.mms.service import get_module_service 

class TaskDispatcher:
    """任务分发器。"""

    def __init__(self):
        self.repo = get_task_repository()
        self.rem = get_environment_manager()
        # MMS Service lazy load to avoid circular import
        self._mms = None

    @property
    def mms(self):
        if not self._mms:
             # Assume factory exists
             from src.core.mms.service import get_module_service
             self._mms = get_module_service()
        return self._mms

    async def dispatch(self, job: Job) -> str:
        """分发并执行一个新任务。
        
        Args:
            job: 作业配置
        
        Returns:
            task_id: 创建的任务 ID
        """
        # 1. 创建任务记录 (PENDING)
        task = Task(job_id=job.id, status=TaskStatus.PENDING)
        await self.repo.save_task(task)
        logger.debug(f"[ATM] Dispatching Task {task.id} (Job: {job.id})")

        # 2. 异步执行 (Fire & Forget)
        asyncio.create_task(self._run_safe(task, job))
        
        return task.id

    async def _run_safe(self, task: Task, job: Job):
        """异常安全的执行包装。"""
        try:
            await self._run_logic(task, job)
        except Exception as e:
            logger.error(f"[ATM] Task {task.id} unhandled exception: {e}\n{traceback.format_exc()}")
            task.status = TaskStatus.FAILED
            task.error = f"System Error: {str(e)}"
            task.finished_at = int(time.time())
            await self.repo.save_task(task)

    async def _run_logic(self, task: Task, job: Job):
        """核心执行逻辑。"""
        # 0. 加载策略
        from src.core.tsm import get_strategy_loader
        loader = get_strategy_loader()
        strategy = loader.get(job.strategy_id)
        if not strategy:
            # 如果没有策略，尝试加载默认策略或报错
            # 这里为了健壮性，若无策略则抛出错误
            logger.warning(f"[ATM] Strategy {job.strategy_id} not found, using default resource config")
            # raise ValueError(f"Strategy {job.strategy_id} not found")
        
        # 1. 申请资源 (Atomic)
        env_kind = EnvKind.BROWSER # Default
        wait_timeout = 60
        
        if strategy:
            env_kind = EnvKind(strategy.selector.env_type.value)
            wait_timeout = strategy.selector.wait_timeout or 60

        req = EnvRequirement(
            task_run_id=task.id, 
            kind=env_kind,
            timeout=wait_timeout
        )
        
        lease = None
        try:
            lease = await self.rem.acquire_atomic(req, timeout=wait_timeout)
            
            task.env_id = str(lease.env_id) # Ensure str
            task.lease_id = lease.id
            task.started_at = int(time.time())
            task.status = TaskStatus.RUNNING
            await self.repo.save_task(task)
            
            logger.info(f"[ATM] Task {task.id} acquired env {task.env_id} ({env_kind})")
            
        except Exception as e:
            logger.warning(f"[ATM] Task {task.id} failed to acquire resource: {e}")
            task.status = TaskStatus.FAILED
            task.error = f"Resource Error: {str(e)}"
            task.finished_at = int(time.time())
            await self.repo.save_task(task)
            return

        # 2. 执行模块
        try:
            module_name = "example_module"
            params = job.params
            
            if strategy and strategy.execution:
                module_name = strategy.execution.module
                params = {**strategy.execution.params, **job.params}
            
            logger.info(f"[ATM] Task {task.id} executing module {module_name}")
            
            # 使用 MMS 执行 (Mock)
            # from src.core.mms.service import get_module_service
            # mms = get_module_service()
            # result = await mms.run_module(module_name, params)
            
            # Mock Execution
            await asyncio.sleep(2)
            result = {"status": "success", "mock": True, "module": module_name}
            
            task.message = str(result)
            task.status = TaskStatus.SUCCEEDED
            
        except Exception as e:
            logger.error(f"[ATM] Task {task.id} execution failed: {e}")
            task.error = f"Execution Error: {str(e)}"
            task.status = TaskStatus.FAILED
        finally:
            task.finished_at = int(time.time())
            
            # 3. 释放/清理资源
            if lease:
                try:
                    # TODO: Implement Teardown Policy from strategy
                    await self.rem.release(lease) # Correct method signature
                except Exception as e:
                    logger.error(f"[ATM] Failed to release lease {task.lease_id}: {e}")
            
            await self.repo.save_task(task)
            logger.info(f"[ATM] Task {task.id} finished: {task.status}")


# Singleton
_dispatcher: TaskDispatcher | None = None

def get_task_dispatcher() -> TaskDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = TaskDispatcher()
    return _dispatcher
