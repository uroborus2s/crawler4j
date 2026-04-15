"""Job Controller (V2).

负责作业(Job)生命周期管理：
1. Batch: 注册 Cron 调度
2. Service: 任务结束事件驱动并发补齐
3. 触发 Dispatcher
"""

import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.atm.job_runtime import resolve_job_run_profile
from src.core.atm.dispatcher import get_task_dispatcher
from src.core.atm.models import Job, JobState, JobType, TriggerType
from src.core.atm.repository import get_task_repository
from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.core.foundation.logging import logger


class JobController:
    """作业控制器。"""
    
    def __init__(self):
        self.repo = get_task_repository()
        self.dispatcher = get_task_dispatcher()
        self._running = False
        self._timezone = datetime.now().astimezone().tzinfo
        self._scheduler = AsyncIOScheduler(timezone=self._timezone)
        self._scheduler_started = False
        self._batch_job_ids: dict[str, str] = {}
        self._event_bus = get_event_bus()
        self._event_handlers_registered = False
        
    async def start(self):
        """启动控制器循环。"""
        if self._running:
            return
        self._running = True
        
        # 1. 开机自检 (Crash Recovery)
        try:
            await self._recover_zombies()
        except Exception as e:
            logger.error(f"[ATM] Failed to recover zombie tasks: {e}")
            
        self._start_scheduler()
        self._subscribe_task_events()
        await self._bootstrap_active_jobs()
        logger.info("[ATM] JobController started")
        
    async def stop(self):
        """停止控制器。"""
        self._running = False
        self._unsubscribe_task_events()
        self._stop_scheduler()
            
        # 安全等待 Dispatcher 中的所有任务跑完并回收
        if hasattr(self.dispatcher, "wait_for_completion"):
            await self.dispatcher.wait_for_completion()
            
        logger.info("[ATM] JobController stopped")

    async def request_job_stop(self, job_id: str):
        """停止某个 Job 的后续调度，并向活动 Task 请求停止。"""
        self._remove_batch_schedule(job_id)
        if hasattr(self.dispatcher, "request_stop_for_job"):
            await self.dispatcher.request_stop_for_job(job_id)

    async def request_job_resume(self, job_id: str):
        """恢复某个 Job 的调度状态。"""
        if hasattr(self.dispatcher, "clear_stop_for_job"):
            self.dispatcher.clear_stop_for_job(job_id)

    async def ensure_job_runtime_ready(self, job_id: str):
        """按 Job 运行配置检查外部运行时依赖（如指纹浏览器）是否就绪。"""
        job = await self.repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        await self._ensure_runtime_for_job(job)

    async def _ensure_runtime_for_job(self, job: Job):
        run_profile = resolve_job_run_profile(job)

        provider_name = run_profile.resource.provider if run_profile.resource else ""
        if not provider_name:
            return

        from src.core.rem.manager import get_environment_manager
        await get_environment_manager().ensure_provider_runtime(provider_name)
        
    async def _recover_zombies(self):
        """识别并清理上一轮非正常退出遗留的僵尸任务。"""
        stuck_tasks = await self.repo.get_running_tasks()
        if not stuck_tasks:
            return
        
        logger.warning(f"[ATM] Found {len(stuck_tasks)} unfinished tasks from previous run. Recovering...")
        
        # 1. 清理对应的环境泄漏
        from src.core.rem.manager import get_environment_manager
        rem = get_environment_manager()
        
        for task in stuck_tasks:
            if task.env_id:
                try:
                    env = await rem.get_env(int(task.env_id))
                    if env:
                        await rem.reset(env)
                except Exception as e:
                    logger.warning(f"[ATM] Failed to clean up leaked env {task.env_id} for zombie task {task.id}: {e}")
                    
        # 2. 批量将状态置为 FAILED
        task_ids = [t.id for t in stuck_tasks]
        await self.repo.mark_tasks_failed(task_ids, "Engine Crashed / Unexpected Power-off")
        logger.info(f"[ATM] Recovered {len(stuck_tasks)} unfinished tasks to FAILED state.")
        
    async def reconcile_job(self, job_id: str):
        """仅调和指定 Job（用于启动/更新时即时触发）。"""
        try:
            job = await self.repo.get_job(job_id)
        except Exception as e:
            logger.error(f"[ATM] Failed to load job {job_id} for targeted reconcile: {e}")
            return

        if not job:
            return
        if job.state != JobState.ACTIVE:
            return

        try:
            await self._reconcile_job(job)
        except Exception as e:
            logger.error(f"[ATM] Failed to reconcile target job {job.id}: {e}")
            
    async def _reconcile_job(self, job: Job):
        """调和单个 Job 的并发状态。"""
        if job.type == JobType.BATCH:
            self._ensure_batch_schedule(job)
            return
        await self._reconcile_service_job(job)

    async def _reconcile_service_job(self, job: Job):
        """常驻并发型 Job：始终维持目标并发。"""
        current_count = await self.repo.count_active_tasks(job.id)
        target = job.concurrency_target
        needed = target - current_count

        if needed > 0:
            logger.debug(f"[ATM] Job {job.id} scaling up: {current_count} -> {target} (+{needed})")
            for _ in range(needed):
                await self.dispatcher.dispatch(job)

    async def _on_batch_cron_fire(self, job_id: str):
        """Cron 触发批次执行：上一批未结束则跳过。"""
        job = await self.repo.get_job(job_id)
        if not job or job.state != JobState.ACTIVE or job.type != JobType.BATCH:
            return

        current_count = await self.repo.count_active_tasks(job.id)
        if current_count > 0:
            logger.info(f"[ATM] Job {job.id} skipped scheduled batch because {current_count} tasks are still active")
            return

        logger.info(f"[ATM] Job {job.id} firing scheduled batch with concurrency={job.concurrency_target}")
        for _ in range(job.concurrency_target):
            await self.dispatcher.dispatch(job)

    async def _bootstrap_active_jobs(self):
        jobs = await self.repo.list_active_jobs()
        for job in jobs:
            try:
                await self._ensure_runtime_for_job(job)
            except Exception as e:
                logger.error(f"[ATM] Job {job.id} runtime precheck failed at bootstrap: {e}")
                continue
            await self._reconcile_job(job)

    def _start_scheduler(self):
        if self._scheduler_started:
            return
        self._scheduler.start()
        self._scheduler_started = True

    def _stop_scheduler(self):
        if not self._scheduler_started:
            return
        self._scheduler.shutdown(wait=False)
        self._scheduler = AsyncIOScheduler(timezone=self._timezone)
        self._scheduler_started = False
        self._batch_job_ids.clear()

    def _ensure_batch_schedule(self, job: Job):
        if job.type != JobType.BATCH:
            return
        if job.trigger.type != TriggerType.CRON or not job.trigger.cron_expr:
            self._remove_batch_schedule(job.id)
            return

        schedule_id = f"batch:{job.id}"
        try:
            trigger = CronTrigger.from_crontab(job.trigger.cron_expr, timezone=self._timezone)
        except ValueError as e:
            logger.error(f"[ATM] Job {job.id} invalid cron expression '{job.trigger.cron_expr}': {e}")
            self._remove_batch_schedule(job.id)
            return
        self._scheduler.add_job(
            self._on_batch_cron_fire,
            trigger=trigger,
            args=[job.id],
            id=schedule_id,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        self._batch_job_ids[job.id] = schedule_id

    def _remove_batch_schedule(self, job_id: str):
        schedule_id = self._batch_job_ids.pop(job_id, None)
        if not schedule_id:
            return
        try:
            self._scheduler.remove_job(schedule_id)
        except Exception:
            pass

    def _subscribe_task_events(self):
        if self._event_handlers_registered:
            return
        self._event_bus.subscribe(EventType.TASK_FINISHED, self._on_task_terminal_event)
        self._event_bus.subscribe(EventType.TASK_FAILED, self._on_task_terminal_event)
        self._event_bus.subscribe(EventType.TASK_CANCELLED, self._on_task_terminal_event)
        self._event_handlers_registered = True

    def _unsubscribe_task_events(self):
        if not self._event_handlers_registered:
            return
        self._event_bus.unsubscribe(EventType.TASK_FINISHED, self._on_task_terminal_event)
        self._event_bus.unsubscribe(EventType.TASK_FAILED, self._on_task_terminal_event)
        self._event_bus.unsubscribe(EventType.TASK_CANCELLED, self._on_task_terminal_event)
        self._event_handlers_registered = False

    def _on_task_terminal_event(self, event: Event):
        """任务结束后，定向补齐对应 Service Job 并发。"""
        if not self._running:
            return
        job_id = event.data.get("job_id")
        if not job_id:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.reconcile_job(job_id))

# Singleton
_controller: JobController | None = None

def get_job_controller() -> JobController:
    global _controller
    if _controller is None:
        _controller = JobController()
    return _controller
