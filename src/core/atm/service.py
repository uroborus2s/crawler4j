"""任务服务 (V2).

ATM 的统一门面，负责作业(Job)的管理和查询。
核心逻辑已下沉至 JobController 和 TaskDispatcher。
"""

import asyncio
from typing import Any, List

from src.core.atm.controller import JobController, get_job_controller
from src.core.atm.models import Job, JobState, JobType, Task, TaskStatus, TriggerConfig
from src.core.atm.repository import TaskRepository, get_task_repository
from src.core.foundation.logging import logger


class TaskService:
    """任务服务 (V2)。"""
    
    def __init__(self):
        self._repo = get_task_repository()
        self._controller = get_job_controller()
        self._started = False

    async def start(self):
        """启动 ATM 服务 (Controller)。"""
        if self._started:
            return
        
        logger.info("[ATM] Starting TaskService V2...")
        self._started = True
        await self._controller.start()

    async def stop(self):
        """停止 ATM 服务。"""
        self._started = False
        await self._controller.stop()

    # === Job Management ===

    async def create_job(
        self,
        name: str,
        job_type: str = JobType.BATCH,
        trigger_config: dict | None = None,
        strategy_id: str = "",
        params: dict | None = None,
        concurrency: int = 1,
    ) -> str:
        """创建新作业。"""
        # TODO: Validate strategy_id with MMS/Loader
        
        trigger = TriggerConfig(**(trigger_config or {}))
        
        job = Job(
            name=name,
            type=JobType(job_type),
            strategy_id=strategy_id,
            trigger=trigger,
            params=params or {},
            concurrency_target=concurrency,
            state=JobState.PAUSED, # 默认暂停
        )
        await self._repo.save_job(job)
        logger.info(f"[ATM] Created job: {job.id} ({job.name})")
        return job.id

    async def update_job(
        self,
        job_id: str,
        name: str | None = None,
        job_type: str | None = None,
        trigger_config: dict | None = None,
        strategy_id: str | None = None,
        params: dict | None = None,
        concurrency: int | None = None,
    ) -> bool:
        """更新作业配置。"""
        job = await self._repo.get_job(job_id)
        if not job:
            return False

        if name is not None:
            job.name = name
        if job_type is not None:
            job.type = JobType(job_type)
        if strategy_id is not None:
            job.strategy_id = strategy_id
        if trigger_config is not None:
            job.trigger = TriggerConfig(**trigger_config)
        if params is not None:
            job.params = params
        if concurrency is not None:
            job.concurrency_target = concurrency

        job.updated_at = int(asyncio.get_running_loop().time()) # Or simple time.time()
        import time
        job.updated_at = int(time.time())

        await self._repo.save_job(job)
        
        # 如果作业是活跃的，虽然不需要立即重启，但他会在下一次 reconcile 时生效
        # 为了即时性，可以触发一次 reconcile
        if job.state == JobState.ACTIVE:
             asyncio.create_task(self._controller.reconcile())

        logger.info(f"[ATM] Updated job: {job.id}")
        return True

    async def list_jobs(self) -> List[Job]:
        """列出所有作业。"""
        return await self._repo.list_jobs()

    async def get_job(self, job_id: str) -> Job | None:
        """获取作业详情。"""
        return await self._repo.get_job(job_id)

    async def start_job(self, job_id: str) -> bool:
        """启动/激活作业。"""
        job = await self._repo.get_job(job_id)
        if not job:
            return False
        
        job.state = JobState.ACTIVE
        await self._repo.save_job(job)
        # 立即尝试一次调度 (Optional optimization)
        asyncio.create_task(self._controller.reconcile())
        logger.info(f"[ATM] Job active: {job.id}")
        return True

    async def pause_job(self, job_id: str) -> bool:
        """暂停作业。"""
        job = await self._repo.get_job(job_id)
        if not job:
            return False
        
        job.state = JobState.PAUSED
        await self._repo.save_job(job)
        logger.info(f"[ATM] Job paused: {job.id}")
        return True

    async def delete_job(self, job_id: str) -> bool:
        """删除作业。"""
        await self._repo.delete_job(job_id)
        logger.info(f"[ATM] Job deleted: {job_id}")
        return True

    # === Task Query ===

    async def list_tasks(self, job_id: str) -> List[Task]:
        """列出作业下的所有任务实例。"""
        return await self._repo.list_tasks_by_job(job_id)

    async def get_task(self, task_id: str) -> Task | None:
        """获取任务实例详情。"""
        return await self._repo.get_task(task_id)


# Global Singleton
_service: TaskService | None = None

def get_task_service() -> TaskService:
    global _service
    if _service is None:
        _service = TaskService()
    return _service
