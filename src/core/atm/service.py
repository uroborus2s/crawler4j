"""任务服务 (V2).

ATM 的统一门面，负责作业(Job)的管理和查询。
核心逻辑已下沉至 JobController 和 TaskDispatcher。
"""

import asyncio
import time
from typing import List

from apscheduler.triggers.cron import CronTrigger

from src.core.atm.controller import get_job_controller
from src.core.atm.models import Job, JobState, JobType, Task, TriggerConfig, TriggerType
from src.core.atm.repository import get_task_repository
from src.core.foundation.logging import logger


class TaskService:
    """任务服务 (V2)。"""
    
    def __init__(self):
        self._repo = get_task_repository()
        self._controller = get_job_controller()
        self._started = False

    @staticmethod
    def _normalize_trigger(job_type: JobType, trigger_config: dict | TriggerConfig | None) -> TriggerConfig:
        """根据 Job 模式规范化触发器配置。"""
        trigger = (
            trigger_config
            if isinstance(trigger_config, TriggerConfig)
            else TriggerConfig(**(trigger_config or {}))
        )

        if job_type == JobType.SERVICE:
            return TriggerConfig(type=TriggerType.MANUAL, cron_expr=None)

        if trigger.type != TriggerType.CRON or not trigger.cron_expr:
            raise ValueError("定时批次作业必须配置有效的 Cron 表达式")
        try:
            CronTrigger.from_crontab(trigger.cron_expr)
        except ValueError as e:
            raise ValueError(f"定时批次作业 Cron 表达式无效: {e}") from e

        return trigger

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
        job_type_enum = JobType(job_type)
        trigger = self._normalize_trigger(job_type_enum, trigger_config)
        
        job = Job(
            name=name,
            type=job_type_enum,
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

        job.trigger = self._normalize_trigger(job.type, job.trigger)

        job.updated_at = int(time.time())

        await self._repo.save_job(job)
        
        # 触发该 Job 的一次定向调和，保证配置即时生效
        if job.state == JobState.ACTIVE:
            asyncio.create_task(self._controller.reconcile_job(job.id))

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

        # 启动作业前按策略检查运行时依赖（如指纹浏览器）是否就绪。
        if job.strategy_id:
            try:
                await self._controller.ensure_job_runtime_ready(job.id)
            except Exception as e:
                logger.error(f"[ATM] Job start blocked by runtime precheck ({job.id}): {e}")
                return False
        
        job.state = JobState.ACTIVE
        await self._repo.save_job(job)
        await self._controller.request_job_resume(job.id)
        # 立即触发该 Job 的一次定向调和
        asyncio.create_task(self._controller.reconcile_job(job.id))
        logger.info(f"[ATM] Job active: {job.id}")
        return True

    async def pause_job(self, job_id: str) -> bool:
        """暂停作业。"""
        job = await self._repo.get_job(job_id)
        if not job:
            return False
        
        job.state = JobState.PAUSED
        await self._repo.save_job(job)
        await self._controller.request_job_stop(job.id)
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
