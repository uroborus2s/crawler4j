"""已有环境导入执行服务。"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field

from src.core.atm.dispatcher import TaskDispatcher, get_task_dispatcher
from src.core.atm.models import Job, JobState, JobType, TaskStatus, TriggerConfig, TriggerType
from src.core.atm.repository import TaskRepository, get_task_repository
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    CreationLifecycle,
    EnvType,
    ExecutionContext,
    ResourceConfig,
    RunProfile,
)
from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.core.foundation.logging import logger
from src.core.mms.models import ModuleStatus
from src.core.mms.registry import ModuleRegistry, get_module_registry
from src.core.rem.manager import EnvironmentManager, get_environment_manager
from src.core.rem.models import Environment


_LOGIN_REQUIRED_ERRORS = {"not_logged_in", "login_required", "requires_login"}


@dataclass
class ExistingEnvImportRunResult:
    """导入并执行启动结果。"""

    env: Environment
    job_id: str
    task_id: str
    envs: list[Environment] = field(default_factory=list)
    task_ids: list[str] = field(default_factory=list)


class ExistingEnvImportJobService:
    """把已有环境导入宿主后，关联已有手动批次任务执行模块 workflow。"""

    def __init__(
        self,
        *,
        rem: EnvironmentManager | None = None,
        registry: ModuleRegistry | None = None,
        repo: TaskRepository | None = None,
        dispatcher: TaskDispatcher | None = None,
    ) -> None:
        self.rem = rem or get_environment_manager()
        self.registry = registry or get_module_registry()
        self.repo = repo or get_task_repository()
        self.dispatcher = dispatcher or get_task_dispatcher()
        self._watch_tasks: set[asyncio.Task[None]] = set()

    async def import_and_run(
        self,
        *,
        provider_name: str,
        env_name: str,
        module_name: str,
        workflow_name: str,
    ) -> ExistingEnvImportRunResult:
        """导入来源环境并启动后台执行。"""
        module = self.registry.get_module(module_name)
        if not module or module.status != ModuleStatus.ENABLED:
            raise ValueError(f"目标模块不可用: {module_name}")

        workflow_names = {workflow.name for workflow in self.registry.get_workflows(module_name)}
        if workflow_name not in workflow_names:
            raise ValueError(f"目标 workflow 不存在: {module_name}/{workflow_name}")

        env = await self.rem.import_existing_env(provider_name, env_name)
        creation_params = _build_existing_env_creation_params(env)

        job = Job(
            id=f"existing-env-import-{uuid.uuid4().hex[:12]}",
            name=f"已有环境导入/{module_name}/{workflow_name}/{env.name or env.id}",
            type=JobType.BATCH,
            run_profile=RunProfile(
                resource=ResourceConfig(
                    acquisition=AcquisitionConfig(
                        mode=AcquisitionMode.SELECT,
                        provider=provider_name,
                        env_type=_resolve_env_type(provider_name),
                        env_id=int(env.id),
                        creation=CreationConfig(
                            lifecycle=CreationLifecycle.PERSISTENT,
                            params=creation_params,
                        ),
                    )
                ),
                execution=ExecutionContext(
                    module=module_name,
                    workflow=workflow_name,
                ),
            ),
            trigger=TriggerConfig(type=TriggerType.MANUAL),
            state=JobState.PAUSED,
            updated_at=int(time.time()),
        )
        await self.repo.save_job(job)

        try:
            task_id = await self.dispatcher.dispatch(job)
        except Exception as exc:
            await self.rem.mark_existing_env_import_state(
                int(env.id),
                status="import_failed",
                module_name=module_name,
                workflow_name=workflow_name,
                error=str(exc),
                message="后台导入执行任务启动失败",
            )
            raise

        await self.rem.mark_existing_env_import_state(
            int(env.id),
            status="import_running",
            module_name=module_name,
            workflow_name=workflow_name,
            task_id=task_id,
            message="后台导入执行任务已启动",
        )

        self._track_watch_task(
            self._watch_task_terminal_state(
                env_id=int(env.id),
                job_id=job.id,
                task_id=task_id,
                module_name=module_name,
                workflow_name=workflow_name,
                update_job_state=True,
            )
        )
        return ExistingEnvImportRunResult(env=env, job_id=job.id, task_id=task_id, envs=[env], task_ids=[task_id])

    async def import_and_run_with_job(
        self,
        *,
        provider_name: str,
        env_names: list[str],
        job_id: str,
    ) -> ExistingEnvImportRunResult:
        """导入来源环境，并把执行实例挂到已有手动批次 Job 下。"""
        normalized_env_names = [str(name or "").strip() for name in env_names if str(name or "").strip()]
        if not normalized_env_names:
            raise ValueError("至少选择一个来源环境")

        job = await self.repo.get_job(job_id)
        if not job:
            raise ValueError(f"目标任务不存在: {job_id}")
        self._validate_manual_import_job(job)

        envs = [
            await self.rem.import_existing_env(provider_name, env_name)
            for env_name in normalized_env_names
        ]
        task_ids = await self._dispatch_available_import_envs(job, envs)
        dispatched_count = len(task_ids)
        remaining = envs[dispatched_count:]
        if remaining:
            self._publish_import_queue_progress(job, queued_count=len(remaining))
            self._track_watch_task(self._schedule_remaining_import_envs(job.id, remaining))
        else:
            self._publish_import_queue_progress(job, queued_count=0)

        return ExistingEnvImportRunResult(
            env=envs[0],
            job_id=job.id,
            task_id=task_ids[0] if task_ids else "",
            envs=envs,
            task_ids=task_ids,
        )

    def _validate_manual_import_job(self, job: Job) -> None:
        if job.type != JobType.BATCH or job.trigger.type != TriggerType.MANUAL:
            raise ValueError("已有环境导入只能关联“执行一次”的批次任务")
        if not job.run_profile or not job.run_profile.execution:
            raise ValueError("关联任务必须配置运行模板")
        module_name = str(job.run_profile.execution.module or "").strip()
        workflow_name = str(job.run_profile.execution.workflow or "default").strip()
        if not module_name:
            raise ValueError("关联任务运行模板缺少模块名")

        module = self.registry.get_module(module_name)
        if not module or module.status != ModuleStatus.ENABLED:
            raise ValueError(f"目标模块不可用: {module_name}")
        workflow_names = {workflow.name for workflow in self.registry.get_workflows(module_name)}
        if workflow_name not in workflow_names:
            raise ValueError(f"目标 workflow 不存在: {module_name}/{workflow_name}")

    async def _dispatch_available_import_envs(self, job: Job, envs: list[Environment]) -> list[str]:
        if not envs:
            return []
        slots = await self._available_import_slots(job)
        task_ids: list[str] = []
        for env in envs[:slots]:
            task_ids.append(await self._dispatch_import_env(job, env))
        return task_ids

    async def _available_import_slots(self, job: Job) -> int:
        target = max(1, int(job.concurrency_target or 1))
        active_count = await self.repo.count_active_tasks(job.id)
        return max(0, target - int(active_count))

    async def _schedule_remaining_import_envs(self, job_id: str, envs: list[Environment]) -> None:
        pending = list(envs)
        while pending:
            job = await self.repo.get_job(job_id)
            if not job:
                logger.warning(f"[REM] 导入执行队列缺少关联 Job 记录: {job_id}")
                self._publish_import_queue_progress_for_job_id(job_id, queued_count=0)
                return
            try:
                self._validate_manual_import_job(job)
            except Exception as exc:
                logger.warning(f"[REM] 导入执行队列停止: job={job_id} error={exc}")
                self._publish_import_queue_progress(job, queued_count=0)
                return

            slots = await self._available_import_slots(job)
            if slots <= 0:
                await asyncio.sleep(0.2)
                continue

            batch = pending[:slots]
            pending = pending[slots:]
            for env in batch:
                try:
                    await self._dispatch_import_env(job, env)
                except Exception as exc:
                    logger.warning(f"[REM] 导入执行队列跳过失败环境: job={job_id} env={env.id} error={exc}")
            self._publish_import_queue_progress(job, queued_count=len(pending))

    async def _dispatch_import_env(self, job: Job, env: Environment) -> str:
        fixed_env_job = self._build_fixed_env_job(job, env)
        module_name, workflow_name = self._job_module_workflow(fixed_env_job)
        try:
            task_id = await self.dispatcher.dispatch(fixed_env_job)
        except Exception as exc:
            await self.rem.mark_existing_env_import_state(
                int(env.id),
                status="import_failed",
                module_name=module_name,
                workflow_name=workflow_name,
                error=str(exc),
                message="关联任务启动失败",
            )
            raise

        await self.rem.mark_existing_env_import_state(
            int(env.id),
            status="import_running",
            module_name=module_name,
            workflow_name=workflow_name,
            task_id=task_id,
            message="已关联任务并启动执行",
        )
        self._track_watch_task(
            self._watch_task_terminal_state(
                env_id=int(env.id),
                job_id=job.id,
                task_id=task_id,
                module_name=module_name,
                workflow_name=workflow_name,
                update_job_state=False,
            )
        )
        return task_id

    def _build_fixed_env_job(self, job: Job, env: Environment) -> Job:
        run_profile = job.run_profile.model_copy(deep=True) if job.run_profile else RunProfile()
        run_profile.resource.acquisition = AcquisitionConfig(
            mode=AcquisitionMode.SELECT,
            provider=env.provider,
            env_type=_resolve_env_type(env.provider),
            env_id=int(env.id),
            wait_timeout=run_profile.resource.acquisition.wait_timeout,
            creation=CreationConfig(
                lifecycle=CreationLifecycle.PERSISTENT,
                params=_build_existing_env_creation_params(env),
            ),
        )
        return Job(
            id=job.id,
            name=job.name,
            type=job.type,
            run_profile=run_profile,
            trigger=job.trigger,
            concurrency_target=job.concurrency_target,
            params=dict(job.params),
            state=job.state,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    @staticmethod
    def _job_module_workflow(job: Job) -> tuple[str, str]:
        if not job.run_profile or not job.run_profile.execution:
            return "", ""
        return (
            str(job.run_profile.execution.module or "").strip(),
            str(job.run_profile.execution.workflow or "default").strip(),
        )

    def _track_watch_task(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._watch_tasks.add(task)
        task.add_done_callback(self._watch_tasks.discard)

    @staticmethod
    def _publish_import_queue_progress(job: Job, *, queued_count: int) -> None:
        ExistingEnvImportJobService._publish_import_queue_progress_for_job_id(
            job.id,
            queued_count=queued_count,
            job_name=job.name,
        )

    @staticmethod
    def _publish_import_queue_progress_for_job_id(
        job_id: str,
        *,
        queued_count: int,
        job_name: str = "",
    ) -> None:
        get_event_bus().publish(
            Event(
                type=EventType.TASK_PROGRESS,
                data={
                    "phase": "queued",
                    "job_id": job_id,
                    "job_name": job_name or job_id,
                    "queued_count": max(0, int(queued_count)),
                },
            )
        )

    async def _watch_task_terminal_state(
        self,
        *,
        env_id: int,
        job_id: str,
        task_id: str,
        module_name: str,
        workflow_name: str,
        update_job_state: bool,
    ) -> None:
        while True:
            task = await self.repo.get_task(task_id)
            if task and task.status in {
                TaskStatus.SUCCEEDED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                await self._sync_terminal_state(
                    env_id=env_id,
                    job_id=job_id,
                    task=task,
                    module_name=module_name,
                    workflow_name=workflow_name,
                    update_job_state=update_job_state,
                )
                return
            await asyncio.sleep(0.2)

    async def _sync_terminal_state(
        self,
        *,
        env_id: int,
        job_id: str,
        task,
        module_name: str,
        workflow_name: str,
        update_job_state: bool,
    ) -> None:
        if task.status == TaskStatus.SUCCEEDED:
            await self.rem.mark_existing_env_import_state(
                env_id,
                status="import_succeeded",
                module_name=module_name,
                workflow_name=workflow_name,
                task_id=task.id,
                message=task.message or "已有环境导入执行成功",
            )
            if update_job_state:
                await self._update_job_state(job_id, JobState.COMPLETED)
            return

        if task.status == TaskStatus.CANCELLED:
            await self.rem.mark_existing_env_import_state(
                env_id,
                status="import_cancelled",
                module_name=module_name,
                workflow_name=workflow_name,
                task_id=task.id,
                error=task.error,
                message=task.message or "已有环境导入执行已取消",
            )
            if update_job_state:
                await self._update_job_state(job_id, JobState.PAUSED)
            return

        failed_status = "import_failed_not_logged_in" if _is_not_logged_in(task.error, task.message) else "import_failed"
        await self.rem.mark_existing_env_import_state(
            env_id,
            status=failed_status,
            module_name=module_name,
            workflow_name=workflow_name,
            task_id=task.id,
            error=task.error,
            message=task.message or "已有环境导入执行失败",
        )
        if update_job_state:
            await self._update_job_state(job_id, JobState.ERROR)

    async def _update_job_state(self, job_id: str, state: JobState) -> None:
        job = await self.repo.get_job(job_id)
        if not job:
            logger.warning(f"[REM] 导入执行后台任务缺少 Job 记录: {job_id}")
            return
        job.state = state
        job.updated_at = int(time.time())
        await self.repo.save_job(job)


def _resolve_env_type(provider_name: str) -> EnvType:
    normalized = str(provider_name or "").strip().lower()
    if normalized == "virtualbrowser":
        return EnvType.VIRTUAL_BROWSER
    if normalized == "bitbrowser":
        return EnvType.BIT_BROWSER
    return EnvType.CHROME


def _build_existing_env_creation_params(env: Environment) -> dict[str, str]:
    return {
        "provider": str(env.provider or ""),
        "name": str(env.name or ""),
        "provider_env_id": str(env.external_id or ""),
        "provider_env_name": str(env.name or ""),
        "import_mode": "existing_env",
    }


def _is_not_logged_in(error: str | None, message: str | None) -> bool:
    error_text = str(error or "").strip().lower()
    message_text = str(message or "").strip().lower()
    if error_text in _LOGIN_REQUIRED_ERRORS:
        return True
    if "未登录" in str(error or "") or "未登录" in str(message or ""):
        return True
    return "not logged" in error_text or "not logged" in message_text


_service: ExistingEnvImportJobService | None = None


def get_existing_env_import_job_service() -> ExistingEnvImportJobService:
    global _service
    if _service is None:
        _service = ExistingEnvImportJobService()
    return _service
