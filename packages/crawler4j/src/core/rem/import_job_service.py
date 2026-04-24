"""已有环境导入执行服务。"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass

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


class ExistingEnvImportJobService:
    """把已有环境导入宿主后，以一次性后台任务执行模块 workflow。"""

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
        provider_env_id: str,
        module_name: str,
        workflow_name: str,
    ) -> ExistingEnvImportRunResult:
        """导入来源环境并启动后台执行。"""
        module = self.registry.get_module(module_name)
        if not module or module.status != ModuleStatus.ENABLED:
            raise ValueError(f"目标模块不可用: {module_name}")

        workflow_names = {workflow.name for workflow in module.manifest.workflows}
        if workflow_name not in workflow_names:
            raise ValueError(f"目标 workflow 不存在: {module_name}/{workflow_name}")

        env = await self.rem.import_existing_env(provider_name, provider_env_id)
        creation_params = {
            "provider": env.provider,
            "provider_env_id": str(env.provider_env_id or env.external_id or ""),
            "provider_env_name": env.provider_env_name or env.name,
            "provider_group": env.provider_group or "",
            "provider_proxy": env.provider_proxy or {},
            "import_mode": "existing_env",
        }

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
            )
        )
        return ExistingEnvImportRunResult(env=env, job_id=job.id, task_id=task_id)

    def _track_watch_task(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._watch_tasks.add(task)
        task.add_done_callback(self._watch_tasks.discard)

    async def _watch_task_terminal_state(
        self,
        *,
        env_id: int,
        job_id: str,
        task_id: str,
        module_name: str,
        workflow_name: str,
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
