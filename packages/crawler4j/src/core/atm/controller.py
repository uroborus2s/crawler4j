"""Job Controller (V2).

负责作业(Job)生命周期管理：
1. Batch: 注册 Cron 调度
2. Service: 任务结束事件驱动并发补齐
3. 触发 Dispatcher
"""

import asyncio
import time
from copy import deepcopy
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from crawler4j_contracts import TaskContext
from src.core.atm.job_runtime import resolve_job_run_profile
from src.core.atm.dispatcher import get_task_dispatcher
from src.core.atm.models import Job, JobState, JobType, TaskStatus, TriggerType
from src.core.atm.run_profile import AcquisitionMode
from src.core.atm.runtime_capabilities import RUNTIME_SURFACE_ENV_CANDIDATES, build_runtime_capabilities
from src.core.atm.repository import get_task_repository
from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.core.foundation.logging import logger
from src.core.mms.release_service import assert_module_upgrade_unlocked
from src.core.mms.settings_store import get_module_settings_store
from src.core.mms.service import get_module_service
from src.core.rem.env_claims import CLAIM_CLAIMED, get_env_claim, is_env_bound_by_module, recover_pending_env_claims
from src.core.rem.fingerprint_validation import (
    FINGERPRINT_VALIDATION_NAMESPACE,
    is_fingerprint_validation_risk,
)
from src.core.rem.manager import RECOVERY_PROVIDER_RUNTIME_TIMEOUT, get_environment_manager

CANDIDATE_EVALUATION_TIMEOUT_SECONDS = 10.0


class InvalidJobConfigurationError(ValueError):
    """作业运行模板组合无效。"""


class JobController:
    """作业控制器。"""
    
    def __init__(self):
        self.repo = get_task_repository()
        self.dispatcher = get_task_dispatcher()
        self.rem = get_environment_manager()
        self._running = False
        self._timezone = datetime.now().astimezone().tzinfo
        self._scheduler = AsyncIOScheduler(timezone=self._timezone)
        self._scheduler_started = False
        self._batch_job_ids: dict[str, str] = {}
        self._event_bus = get_event_bus()
        self._event_handlers_registered = False
        self._service_job_reconcile_locks: dict[str, asyncio.Lock] = {}
        self._service_reconcile_interval_seconds = 5.0
        self._service_reconcile_timeout_seconds = 45.0
        self._service_reconcile_task: asyncio.Task[None] | None = None
        
    async def start(self):
        """启动控制器循环。"""
        if self._running:
            return
        self._running = True
        
        # 1. 开机自检 (Crash Recovery)
        try:
            await self._recover_zombies()
            await recover_pending_env_claims(self.rem)
        except Exception as e:
            logger.error(f"[ATM] Failed to recover zombie tasks: {e}")
            
        self._start_scheduler()
        self._subscribe_task_events()
        await self._bootstrap_active_jobs()
        self._start_service_reconcile_loop()
        logger.info("[ATM] JobController started")
        
    async def stop(self):
        """停止控制器。"""
        self._running = False
        self._unsubscribe_task_events()
        self._stop_scheduler()
        await self._stop_service_reconcile_loop()
            
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

    @staticmethod
    def _validate_candidates_declaration(run_profile) -> None:
        acquisition = run_profile.resource.acquisition if run_profile.resource else None
        if not acquisition:
            return

        candidates_name = str(acquisition.candidates or "").strip()
        if not candidates_name:
            return

        module_name = str(run_profile.execution.module or "").strip() if run_profile.execution else ""
        if not module_name:
            return

        descriptor = get_module_service().get_runtime_descriptor_v2(module_name)
        if candidates_name not in descriptor.env_candidates:
            raise InvalidJobConfigurationError(f"env_candidates 未声明: {module_name}.{candidates_name}")

    async def _pause_job_after_invalid_precheck(self, job: Job, error: Exception, *, source: str) -> bool:
        if not isinstance(error, InvalidJobConfigurationError):
            return False
        if job.state != JobState.ACTIVE:
            return False

        job.state = JobState.PAUSED
        job.updated_at = int(time.time())
        await self.repo.save_job(job)
        await self.request_job_stop(job.id)
        logger.error(
            f"[ATM] Job {job.id} paused due to invalid runtime configuration during {source}: {error}"
        )
        return True

    async def _ensure_runtime_for_job(
        self,
        job: Job,
        *,
        runtime_timeout: int | None = None,
    ):
        run_profile = resolve_job_run_profile(job)
        self._validate_candidates_declaration(run_profile)
        module_name = str(run_profile.execution.module or "").strip() if run_profile.execution else ""
        if module_name:
            assert_module_upgrade_unlocked(module_name)

        if run_profile.resource.acquisition.mode != AcquisitionMode.CREATE:
            return

        provider_name = run_profile.resource.acquisition.provider if run_profile.resource else ""
        if not provider_name:
            return

        rem = get_environment_manager()
        if runtime_timeout is None:
            await rem.ensure_provider_runtime(provider_name)
        else:
            await rem.ensure_provider_runtime(provider_name, timeout=runtime_timeout)
        
    async def _recover_zombies(self):
        """识别并清理上一轮非正常退出遗留的僵尸任务。"""
        stuck_tasks = await self.repo.get_running_tasks()
        if not stuck_tasks:
            return

        waiting_tasks = [
            task
            for task in stuck_tasks
            if task.status == TaskStatus.PENDING and task.waiting_since is not None
        ]
        stuck_tasks = [
            task
            for task in stuck_tasks
            if not (task.status == TaskStatus.PENDING and task.waiting_since is not None)
        ]
        if waiting_tasks:
            logger.info(
                "[ATM] Preserving %s env-candidate waiting tasks across restart recovery.",
                len(waiting_tasks),
            )
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
                        await rem.recycle_env(env)
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
        lock = self._service_job_reconcile_locks.setdefault(job.id, asyncio.Lock())
        async with lock:
            if hasattr(self.repo, "get_job"):
                persisted_job = await self.repo.get_job(job.id)
                if not persisted_job or persisted_job.type != JobType.SERVICE or persisted_job.state != JobState.ACTIVE:
                    return
                job = persisted_job

            await self._fail_expired_candidate_waiting_tasks(job)
            await self._resume_candidate_waiting_tasks(job)

            current_count = await self.repo.count_active_tasks(job.id)
            target = job.concurrency_target
            needed = target - current_count

            if needed > 0:
                try:
                    await self._ensure_runtime_for_job(job)
                except Exception as e:
                    if await self._pause_job_after_invalid_precheck(job, e, source="service_reconcile"):
                        return
                    logger.warning(f"[ATM] Job {job.id} scale-up blocked by runtime precheck: {e}")
                    return
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

        try:
            await self._ensure_runtime_for_job(job)
        except Exception as e:
            logger.warning(f"[ATM] Job {job.id} scheduled batch blocked by runtime precheck: {e}")
            return

        logger.info(f"[ATM] Job {job.id} firing scheduled batch with concurrency={job.concurrency_target}")
        for _ in range(job.concurrency_target):
            await self.dispatcher.dispatch(job)

    async def _bootstrap_active_jobs(self):
        jobs = await self.repo.list_active_jobs()
        for job in jobs:
            try:
                await self._ensure_runtime_for_job(
                    job,
                    runtime_timeout=RECOVERY_PROVIDER_RUNTIME_TIMEOUT,
                )
            except Exception as e:
                if await self._pause_job_after_invalid_precheck(job, e, source="bootstrap"):
                    continue
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

    def _start_service_reconcile_loop(self):
        task = self._service_reconcile_task
        if task is not None and not task.done():
            return
        self._service_reconcile_task = asyncio.create_task(
            self._service_reconcile_loop(),
            name="atm-service-reconcile-loop",
        )

    async def _stop_service_reconcile_loop(self):
        task = self._service_reconcile_task
        if task is None:
            return
        self._service_reconcile_task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _service_reconcile_loop(self):
        current_task = asyncio.current_task()
        next_tick_at = time.monotonic() + self._service_reconcile_interval_seconds
        try:
            while self._running:
                sleep_seconds = max(next_tick_at - time.monotonic(), 0.0)
                if sleep_seconds > 0:
                    await asyncio.sleep(sleep_seconds)
                if not self._running:
                    break
                tick_started_at = time.monotonic()
                await self._run_service_reconcile_tick()
                next_tick_at = tick_started_at + self._service_reconcile_interval_seconds
                if not self._running:
                    break
        except asyncio.CancelledError:
            logger.debug("[ATM] Service reconcile loop cancelled")
            raise
        finally:
            if self._service_reconcile_task is current_task:
                self._service_reconcile_task = None

    async def _run_service_reconcile_tick(self):
        try:
            await self._reconcile_active_service_jobs()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[ATM] Service reconcile tick failed unexpectedly: {e}")

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

    def _publish_task_terminal_event(self, task) -> None:
        if task.status == TaskStatus.SUCCEEDED:
            event_type = EventType.TASK_FINISHED
        elif task.status == TaskStatus.CANCELLED:
            event_type = EventType.TASK_CANCELLED
        elif task.status == TaskStatus.FAILED:
            event_type = EventType.TASK_FAILED
        else:
            return

        self._event_bus.publish(
            Event(
                type=event_type,
                task_run_id=task.id,
                data={
                    "task_id": task.id,
                    "job_id": task.job_id,
                    "status": task.status.value,
                    "env_id": task.env_id,
                    "error": task.error,
                },
            )
        )

    async def _reconcile_active_service_jobs(self):
        jobs = await self.repo.list_active_jobs()
        for job in jobs:
            if job.type != JobType.SERVICE:
                continue
            try:
                await asyncio.wait_for(
                    self._reconcile_service_job(job),
                    timeout=self._service_reconcile_timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "[ATM] Service reconcile job %s timed out after %.1fs; cancelling only this job and continuing sweep",
                    job.id,
                    self._service_reconcile_timeout_seconds,
                )
            except Exception as e:
                logger.error(f"[ATM] Failed to reconcile service job {job.id} on periodic tick: {e}")

    def _candidate_binding(self, job: Job) -> tuple[str, str, dict] | None:
        if job.type != JobType.SERVICE:
            return None
        try:
            run_profile = resolve_job_run_profile(job)
        except Exception:
            return None
        if not run_profile.execution or not run_profile.execution.module:
            return None
        acquisition = run_profile.resource.acquisition
        candidates_name = str(acquisition.candidates or "").strip()
        if acquisition.mode != AcquisitionMode.SELECT or not candidates_name:
            return None
        module_name = str(run_profile.execution.module or "").strip()
        if not module_name:
            return None
        return module_name, candidates_name, dict(acquisition.candidate_params)

    async def _count_candidate_capacity(self, job: Job) -> int:
        binding = self._candidate_binding(job)
        if not binding:
            return 0
        module_name, candidates_name, candidate_params = binding
        run_profile = resolve_job_run_profile(job)
        context = self._build_candidate_context(job, run_profile, module_name, candidates_name, candidate_params)
        service = get_module_service()
        try:
            resolver = getattr(service, "resolve_env_candidates_async", None)
            if callable(resolver):
                candidate_ids = await resolver(
                    module_name,
                    context,
                    candidates_name,
                    candidate_params,
                    timeout=CANDIDATE_EVALUATION_TIMEOUT_SECONDS,
                )
            else:
                candidate_ids = service.resolve_env_candidates(
                    module_name,
                    context,
                    candidates_name,
                    candidate_params,
                )
        except Exception as exc:
            logger.warning(f"[ATM] Failed to evaluate env candidates {module_name}.{candidates_name}: {exc}")
            return 0
        wanted = {int(env_id) for env_id in candidate_ids}
        capacity = 0
        for env in await self.rem.list_envs():
            if int(env.id) not in wanted:
                continue
            if str(getattr(getattr(env, "kind", None), "value", getattr(env, "kind", ""))) != "browser":
                continue
            if str(getattr(getattr(env, "status", None), "value", getattr(env, "status", ""))) != "ready":
                continue
            if getattr(env, "lease_id", None):
                continue
            if await self._is_env_fingerprint_validation_risk(int(env.id)):
                continue
            if not await self._is_env_candidate_authorized(int(env.id), module_name):
                continue
            capacity += 1
        return capacity

    async def _is_env_fingerprint_validation_risk(self, env_id: int) -> bool:
        list_metadata = getattr(self.rem, "list_metadata", None)
        if not callable(list_metadata):
            return False
        try:
            metadata = await list_metadata(int(env_id), FINGERPRINT_VALIDATION_NAMESPACE)
        except Exception as exc:
            logger.warning(f"[ATM] 环境指纹风险读取失败: env_id={env_id} error={exc}")
            return False
        return is_fingerprint_validation_risk(metadata)

    def _build_candidate_context(
        self,
        job: Job,
        run_profile,
        module_name: str,
        candidates_name: str,
        candidate_params: dict,
    ) -> TaskContext:
        execution = run_profile.execution
        acquisition = run_profile.resource.acquisition
        workflow_name = execution.workflow
        task_config = get_module_settings_store().build_task_config(module_name, workflow_name)
        caps = build_runtime_capabilities(module_name, surface=RUNTIME_SURFACE_ENV_CANDIDATES)
        runtime = {
            "module_name": module_name,
            "workflow": workflow_name,
            "devel_mode": False,
            "object_bindings": deepcopy(execution.object_bindings),
            "object_params": deepcopy(execution.object_params),
            "provider_name": acquisition.provider,
            "fixed_env_id": acquisition.env_id,
            "candidates": candidates_name,
            "candidate_params": deepcopy(candidate_params),
            "acquisition_mode": acquisition.mode.value,
            "wait_timeout": acquisition.wait_timeout,
            "wait_for_resource": True,
            "creation_params": deepcopy(acquisition.creation.params),
            "execution_timeout": execution.timeout,
        }
        return TaskContext(
            env_id=0,
            task_name=module_name,
            config=deepcopy(task_config),
            tools=caps.tools,
            db=caps.db,
            state={"job_id": job.id},
            runtime=runtime,
        )

    async def _is_env_candidate_authorized(self, env_id: int, module_name: str) -> bool:
        claim = await get_env_claim(self.rem, int(env_id))
        if claim.owner_module != module_name or claim.state != CLAIM_CLAIMED:
            return False
        return is_env_bound_by_module(int(env_id), module_name, module_service=get_module_service())

    async def _fail_expired_candidate_waiting_tasks(self, job: Job) -> None:
        binding = self._candidate_binding(job)
        if not binding or not hasattr(self.repo, "get_oldest_waiting_tasks_before"):
            return

        wait_timeout = int(resolve_job_run_profile(job).resource.acquisition.wait_timeout)
        if wait_timeout <= 0:
            return

        candidates_name = binding[1]
        expired_tasks = await self.repo.get_oldest_waiting_tasks_before(
            job.id,
            [TaskStatus.PENDING],
            waiting_since_before=int(time.time()) - wait_timeout,
        )
        if not expired_tasks:
            return

        expired_task_ids: list[str] = []
        for task in expired_tasks:
            if hasattr(self.dispatcher, "has_live_task_loop") and self.dispatcher.has_live_task_loop(task.id):
                continue
            expired_task_ids.append(task.id)

        if not expired_task_ids:
            return

        failed_tasks = await self.repo.mark_tasks_failed(
            expired_task_ids,
            f"等待环境候选超时: {candidates_name} ({wait_timeout}s)",
        )
        for task in failed_tasks:
            self._publish_task_terminal_event(task)

    async def _resume_candidate_waiting_tasks(self, job: Job) -> None:
        binding = self._candidate_binding(job)
        if not binding:
            return

        capacity = await self._count_candidate_capacity(job)
        running_like_count = await self.repo.count_tasks_by_statuses(
            job.id,
            [TaskStatus.RUNNING],
        )
        remaining_target = job.concurrency_target - running_like_count
        resumable = min(max(remaining_target, 0), capacity)
        if resumable <= 0:
            return

        if hasattr(self.repo, "get_oldest_waiting_tasks"):
            pending_tasks = await self.repo.get_oldest_waiting_tasks(
                job.id,
                [TaskStatus.PENDING],
                limit=resumable,
            )
        else:
            pending_tasks = await self.repo.get_oldest_tasks_by_status(
                job.id,
                [TaskStatus.PENDING],
                limit=resumable,
            )
        resumed = 0
        for task in pending_tasks:
            if resumed >= resumable:
                break
            if hasattr(self.dispatcher, "has_live_task_loop") and self.dispatcher.has_live_task_loop(task.id):
                continue
            await self.dispatcher.resume_task(task, job)
            resumed += 1

# Singleton
_controller: JobController | None = None

def get_job_controller() -> JobController:
    global _controller
    if _controller is None:
        _controller = JobController()
    return _controller
