"""任务服务 (V2).

ATM 的统一门面，负责作业(Job)的管理和查询。
核心逻辑已下沉至 JobController 和 TaskDispatcher。
"""

import asyncio
import time
from typing import List

from apscheduler.triggers.cron import CronTrigger

from src.core.atm.job_runtime import resolve_job_run_profile
from src.core.atm.run_profile import RunProfile
from src.core.atm.controller import get_job_controller
from src.core.atm.models import Job, JobState, JobType, Task, TriggerConfig, TriggerType
from src.core.atm.repository import get_task_repository
from src.core.foundation.logging import logger


_UNSET = object()


class TaskService:
    """任务服务 (V2)。"""
    
    def __init__(self):
        self._repo = get_task_repository()
        self._controller = get_job_controller()
        self._started = False
        self._delete_job_wait_timeout_seconds = 5.0
        self._delete_job_poll_interval_seconds = 0.1

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

        if trigger.type == TriggerType.MANUAL:
            return TriggerConfig(type=TriggerType.MANUAL, cron_expr=None)
        if trigger.type != TriggerType.CRON or not trigger.cron_expr:
            raise ValueError("批次作业必须配置为执行一次或有效的 Cron 表达式")
        try:
            CronTrigger.from_crontab(trigger.cron_expr)
        except ValueError as e:
            raise ValueError(f"批次作业 Cron 表达式无效: {e}") from e

        return trigger

    @staticmethod
    def _normalize_run_profile(run_profile: RunProfile | dict | None) -> RunProfile | None:
        if run_profile is None:
            return None
        if isinstance(run_profile, RunProfile):
            return run_profile
        return RunProfile.model_validate(run_profile)

    @staticmethod
    def _validate_runtime_source(run_profile: RunProfile | None) -> None:
        if run_profile:
            return
        raise ValueError("作业必须配置运行模板")

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
        run_profile: RunProfile | dict | None = None,
        params: dict | None = None,
        concurrency: int = 1,
    ) -> str:
        """创建新作业。"""
        job_type_enum = JobType(job_type)
        trigger = self._normalize_trigger(job_type_enum, trigger_config)
        run_profile_model = self._normalize_run_profile(run_profile)
        self._validate_runtime_source(run_profile_model)
        
        job = Job(
            name=name,
            type=job_type_enum,
            run_profile=run_profile_model,
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
        run_profile: RunProfile | dict | None | object = _UNSET,
        params: dict | None = None,
        concurrency: int | None = None,
    ) -> bool:
        """更新作业配置。"""
        job = await self._repo.get_job(job_id)
        if not job:
            return False
        previous_state = job.state

        if name is not None:
            job.name = name
        if job_type is not None:
            job.type = JobType(job_type)
        if run_profile is not _UNSET:
            job.run_profile = self._normalize_run_profile(run_profile)
        if trigger_config is not None:
            job.trigger = TriggerConfig(**trigger_config)
        if params is not None:
            job.params = params
        if concurrency is not None:
            job.concurrency_target = concurrency

        job.trigger = self._normalize_trigger(job.type, job.trigger)
        self._validate_runtime_source(job.run_profile)
        if job.type == JobType.BATCH and job.trigger.type == TriggerType.MANUAL:
            job.state = JobState.PAUSED

        job.updated_at = int(time.time())

        await self._repo.save_job(job)

        if previous_state == JobState.ACTIVE and job.state != JobState.ACTIVE:
            await self._controller.request_job_stop(job.id)
        elif job.state == JobState.ACTIVE:
            # 触发该 Job 的一次定向调和，保证配置即时生效
            asyncio.create_task(self._controller.reconcile_job(job.id))

        logger.info(f"[ATM] Updated job: {job.id}")
        return True

    async def list_jobs(self) -> List[Job]:
        """列出所有作业。"""
        return await self._repo.list_jobs()

    async def get_job(self, job_id: str) -> Job | None:
        """获取作业详情。"""
        return await self._repo.get_job(job_id)

    async def count_active_tasks(self, job_id: str) -> int:
        """统计作业当前仍在执行生命周期内的任务数。"""
        return await self._repo.count_active_tasks(job_id)

    async def run_job_once(self, job_id: str) -> bool:
        """立即执行一次手动批次作业，不改变作业的长期调度状态。"""
        job = await self._repo.get_job(job_id)
        if not job:
            return False
        if job.type != JobType.BATCH or job.trigger.type != TriggerType.MANUAL:
            raise ValueError("只有“执行一次”模式的批次任务支持手动执行。")

        try:
            resolve_job_run_profile(job)
            await self._controller.ensure_job_runtime_ready(job.id)
        except Exception as e:
            logger.error(f"[ATM] Run-once blocked by runtime precheck ({job.id}): {e}")
            return False

        current_count = await self._repo.count_active_tasks(job.id)
        if current_count > 0:
            logger.info(
                f"[ATM] Job {job.id} run-once ignored because {current_count} tasks are still active"
            )
            return False

        try:
            await self._controller.ensure_job_runtime_ready(job.id)
        except Exception as e:
            logger.error(f"[ATM] Run-once blocked by final runtime precheck ({job.id}): {e}")
            return False

        logger.info(f"[ATM] Job run once: {job.id} (concurrency={job.concurrency_target})")
        for _ in range(job.concurrency_target):
            await self._controller.dispatcher.dispatch(job)
        return True

    async def stop_run_once(self, job_id: str) -> bool:
        """停止一次手动批次执行；环境由宿主统一回收。"""
        job = await self._repo.get_job(job_id)
        if not job:
            return False
        if job.type != JobType.BATCH or job.trigger.type != TriggerType.MANUAL:
            raise ValueError("只有“执行一次”模式的批次任务支持手动中止。")

        current_count = await self._repo.count_active_tasks(job.id)
        if current_count <= 0:
            logger.info(f"[ATM] Job {job.id} stop ignored because no active tasks are running")
            return False

        await self._controller.request_job_stop(job.id)
        logger.info(f"[ATM] Job stop requested: {job.id}")
        return True

    async def start_job(self, job_id: str) -> bool:
        """启动/激活作业。"""
        job = await self._repo.get_job(job_id)
        if not job:
            return False
        if job.type == JobType.BATCH and job.trigger.type == TriggerType.MANUAL:
            return await self.run_job_once(job_id)

        try:
            resolve_job_run_profile(job)
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

    async def _wait_for_job_active_tasks_to_finish(self, job_id: str) -> bool:
        active_count = await self._repo.count_active_tasks(job_id)
        if active_count <= 0:
            return True

        deadline = time.monotonic() + self._delete_job_wait_timeout_seconds
        while active_count > 0 and time.monotonic() < deadline:
            await asyncio.sleep(self._delete_job_poll_interval_seconds)
            active_count = await self._repo.count_active_tasks(job_id)
        return active_count <= 0

    async def delete_job(self, job_id: str) -> bool:
        """删除作业。"""
        job = await self._repo.get_job(job_id)
        if not job:
            return False

        if job.state != JobState.PAUSED:
            job.state = JobState.PAUSED
            job.updated_at = int(time.time())
            await self._repo.save_job(job)

        await self._controller.request_job_stop(job.id)
        if not await self._wait_for_job_active_tasks_to_finish(job.id):
            logger.warning(f"[ATM] Job delete blocked because active tasks are still stopping: {job.id}")
            return False

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
