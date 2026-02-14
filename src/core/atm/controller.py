"""Job Controller (V2).

负责作业(Job)的生命周期管理:
1. 监控 Active Jobs
2. 协调并发数 (Reconciliation Loop)
3. 触发 Dispatcher
"""
import asyncio
import time

from src.core.atm.dispatcher import get_task_dispatcher
from src.core.atm.models import Job, JobState, TaskStatus
from src.core.atm.repository import get_task_repository
from src.core.foundation.logging import logger


class JobController:
    """作业控制器。"""
    
    def __init__(self):
        self.repo = get_task_repository()
        self.dispatcher = get_task_dispatcher()
        self._running = False
        self._loop_task: asyncio.Task | None = None
        
    async def start(self):
        """启动控制器循环。"""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._control_loop())
        logger.info("[ATM] JobController started")
        
    async def stop(self):
        """停止控制器。"""
        self._running = False
        if self._loop_task:
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
        logger.info("[ATM] JobController stopped")
        
    async def _control_loop(self):
        """主控制循环。"""
        while self._running:
            try:
                await self.reconcile()
            except Exception as e:
                logger.error(f"[ATM] Reconcile loop error: {e}")
            
            # TODO: Configurable interval
            await asyncio.sleep(1.0) 
            
    async def reconcile(self):
        """调和所有 Active Jobs。"""
        # 1. 获取所有 Active Jobs
        try:
            jobs = await self.repo.list_active_jobs()
            if not jobs:
                return
        except Exception as e:
            logger.error(f"[ATM] Failed to list active jobs: {e}")
            return
        
        for job in jobs:
            try:
                await self._reconcile_job(job)
            except Exception as e:
                logger.error(f"[ATM] Failed to reconcile job {job.id}: {e}")
            
    async def _reconcile_job(self, job: Job):
        """调和单个 Job 的并发状态。"""
        # 1. 统计当前正在运行的任务 (Running + Pending)
        # 1. 统计当前正在运行的任务 (Running + Pending)
        current_count = await self.repo.count_active_tasks(job.id)
        
        target = job.concurrency_target
        
        # 2. 计算差额
        needed = target - current_count
        
        if needed > 0:
            logger.debug(f"[ATM] Job {job.id} scaling up: {current_count} -> {target} (+{needed})")
            for _ in range(needed):
                # 触发 Dispatcher
                await self.dispatcher.dispatch(job)
        elif needed < 0:
            # Scale down logic (Optional for now)
            # 简单策略: 等待多余任务自然结束，或在此处 Cancel
            pass

# Singleton
_controller: JobController | None = None

def get_job_controller() -> JobController:
    global _controller
    if _controller is None:
        _controller = JobController()
    return _controller
