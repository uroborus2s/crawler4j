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

from src.core.atm.job_runtime import resolve_job_run_profile
from src.core.atm.execution_runner import (
    ExecutionRequest,
    ExecutionRunner,
    TaskStopRequested,
)
from src.core.atm.models import Job, JobType, Task, TaskStatus
from src.core.atm.repository import get_task_repository
from src.core.foundation.context import current_task_id
from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.core.foundation.logging import logger
from src.core.mms.models import ModuleSource
from src.core.rem.manager import get_environment_manager

# MMS Service lazy load to avoid circular import
# from src.core.mms.service import get_module_service


class TaskDispatcher:
    """任务分发器。"""

    def __init__(self):
        self.repo = get_task_repository()
        self.rem = get_environment_manager()
        # MMS Service lazy load to avoid circular import
        self._mms = None
        self._active_tasks: set[asyncio.Task] = set()
        self._task_loops: dict[str, asyncio.Task] = {}
        self._task_jobs: dict[str, str] = {}
        self._task_contexts: dict[str, object] = {}
        self._job_stop_requests: set[str] = set()

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

        # 2. 异步执行 (Fire & Forget but Tracked)
        loop_task = asyncio.create_task(self._run_safe(task, job))
        self._active_tasks.add(loop_task)
        loop_task.add_done_callback(self._active_tasks.discard)
        self._task_loops[task.id] = loop_task
        self._task_jobs[task.id] = job.id
        loop_task.add_done_callback(lambda _: self._cleanup_runtime_refs(task.id))
        
        return task.id

    async def resume_task(self, task: Task, job: Job) -> bool:
        """恢复一个已存在的等待任务。"""
        if task.status != TaskStatus.PENDING:
            return False
        if task.id in self._task_loops:
            return False

        loop_task = asyncio.create_task(self._run_safe(task, job))
        self._active_tasks.add(loop_task)
        loop_task.add_done_callback(self._active_tasks.discard)
        self._task_loops[task.id] = loop_task
        self._task_jobs[task.id] = job.id
        loop_task.add_done_callback(lambda _: self._cleanup_runtime_refs(task.id))
        return True

    def has_live_task_loop(self, task_id: str) -> bool:
        loop_task = self._task_loops.get(task_id)
        return loop_task is not None and not loop_task.done()

    async def wait_for_completion(self):
        """等待所有正在执行的任务完成 (Graceful Shutdown)。"""
        if not self._active_tasks:
            return
            
        logger.info(f"[ATM] Dispatcher waiting for {len(self._active_tasks)} actively running tasks to complete gracefully...")
        # 给予仍在 RUNNING/PENDING 状态的脚本正常跑完并回收资源的生命周期
        await asyncio.gather(*self._active_tasks, return_exceptions=True)
        logger.info("[ATM] All actively dispatched tasks completed.")

    async def request_stop_for_job(self, job_id: str):
        """向某个 Job 下的所有活动 Task 请求停止。"""
        self._job_stop_requests.add(job_id)
        live_task_ids: list[str] = []
        for task_id, running_job_id in list(self._task_jobs.items()):
            if running_job_id != job_id:
                continue
            live_task_ids.append(task_id)
            task_context = self._task_contexts.get(task_id)
            if task_context and hasattr(task_context, "request_stop"):
                task_context.request_stop()

        if hasattr(self.repo, "cancel_pending_tasks_without_resources"):
            cancelled_tasks = await self.repo.cancel_pending_tasks_without_resources(
                job_id,
                cancel_message="Job paused",
                result_message="Job paused before resource acquired",
                exclude_task_ids=live_task_ids,
            )
            for task in cancelled_tasks:
                logger.info(f"[ATM] Task {task.id} cancelled without resource acquisition: {task.error}")
                self._publish_task_event(task)

    def clear_stop_for_job(self, job_id: str):
        """清除 Job 的停止请求标记（用于恢复运行）。"""
        self._job_stop_requests.discard(job_id)

    async def _run_safe(self, task: Task, job: Job):
        """异常安全的执行包装。"""
        token = current_task_id.set(task.id)
        try:
            await self._run_logic(task, job)
        except TaskStopRequested as e:
            logger.info(f"[ATM] Task {task.id} cancelled before start: {e}")
            task.status = TaskStatus.CANCELLED
            task.error = str(e)
            task.finished_at = int(time.time())
            await self.repo.save_task(task)
        except Exception as e:
            logger.error(f"[ATM] Task {task.id} unhandled exception: {e}\n{traceback.format_exc()}")
            task.status = TaskStatus.FAILED
            task.error = f"System Error: {str(e)}"
            task.finished_at = int(time.time())
            await self.repo.save_task(task)
        finally:
            self._publish_task_event(task)
            current_task_id.reset(token)

    async def _run_logic(self, task: Task, job: Job):
        """核心执行逻辑。"""
        run_profile = resolve_job_run_profile(job)
        
        if self._is_stop_requested(job.id):
            raise TaskStopRequested("Job paused before task started")

        if not run_profile.execution:
            raise ValueError(f"Job {job.id} missing run_profile.execution")

        module_name = run_profile.execution.module
        if not module_name:
            raise ValueError("Execution module name is empty. Cannot dispatch task.")

        workflow_name = run_profile.execution.workflow or "default"
        is_dev_link = self._is_dev_link_module(module_name)

        request = ExecutionRequest(
            task=task,
            module_name=module_name,
            workflow_name=workflow_name,
            object_bindings=dict(run_profile.execution.object_bindings),
            object_params=dict(run_profile.execution.object_params),
            devel_mode=is_dev_link,
            state={
                "job_id": job.id,
                "task_id": task.id,
            },
            provider_name=run_profile.resource.acquisition.provider,
            fixed_env_id=run_profile.resource.acquisition.env_id,
            candidates_name=run_profile.resource.acquisition.candidates,
            candidate_params=dict(run_profile.resource.acquisition.candidate_params),
            acquisition_mode=run_profile.resource.acquisition.mode,
            wait_timeout=run_profile.resource.acquisition.wait_timeout,
            wait_for_resource=(
                job.type == JobType.SERVICE
                and run_profile.resource.acquisition.mode.value == "select"
                and bool(str(run_profile.resource.acquisition.candidates or "").strip())
            ),
            creation_params=dict(run_profile.resource.acquisition.creation.params),
            creation_lifecycle=run_profile.resource.acquisition.creation.lifecycle,
            execution_timeout=run_profile.execution.timeout,
        )

        runner = ExecutionRunner(rem=self.rem, mms=self.mms)

        def _remember_context(context):
            self._task_contexts[task.id] = context

        await runner.run(
            request,
            on_task_update=self._save_task_update,
            on_context_ready=_remember_context,
            is_stop_requested=lambda: self._is_stop_requested(job.id),
        )
        logger.info(f"[ATM] Task {task.id} finished: {task.status}")

    def _is_stop_requested(self, job_id: str) -> bool:
        return job_id in self._job_stop_requests

    def _is_dev_link_module(self, module_name: str) -> bool:
        registry = getattr(self.mms, "registry", None)
        if not registry or not hasattr(registry, "get_module"):
            return False

        module_root = module_name.split(".")[0]
        module = registry.get_module(module_name) or registry.get_module(module_root)
        return bool(module and getattr(module, "source", None) == ModuleSource.DEV_LINK)

    def _cleanup_runtime_refs(self, task_id: str):
        self._task_loops.pop(task_id, None)
        job_id = self._task_jobs.pop(task_id, None)
        self._task_contexts.pop(task_id, None)
        if job_id and all(current_job_id != job_id for current_job_id in self._task_jobs.values()):
            self._job_stop_requests.discard(job_id)

    def _publish_task_event(self, task: Task):
        if task.status == TaskStatus.SUCCEEDED:
            event_type = EventType.TASK_FINISHED
        elif task.status == TaskStatus.CANCELLED:
            event_type = EventType.TASK_CANCELLED
        elif task.status == TaskStatus.FAILED:
            event_type = EventType.TASK_FAILED
        else:
            return

        get_event_bus().publish(
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

    async def _save_task_update(self, task: Task) -> None:
        await self.repo.save_task(task)
        if task.status == TaskStatus.PENDING and task.message == "环境启动中":
            event_type = EventType.TASK_PROGRESS
            data = {
                "phase": "environment_starting",
                "task_id": task.id,
                "job_id": task.job_id,
                "status": task.status.value,
                "env_id": task.env_id,
                "message": task.message,
            }
        elif task.status == TaskStatus.RUNNING:
            event_type = EventType.TASK_STARTED
            data = {
                "task_id": task.id,
                "job_id": task.job_id,
                "status": task.status.value,
                "env_id": task.env_id,
            }
        else:
            return
        get_event_bus().publish(
            Event(
                type=event_type,
                task_run_id=task.id,
                data=data,
            )
        )


# Singleton
_dispatcher: TaskDispatcher | None = None

def get_task_dispatcher() -> TaskDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = TaskDispatcher()
    return _dispatcher
