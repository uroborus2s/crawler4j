"""Shared execution kernel for ATM tasks and future debug sessions."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from crawler4j_contracts import TaskContext
from src.core.atm.models import Task, TaskStatus
from src.core.atm.runtime_capabilities import (
    RuntimeCapabilities,
    build_runtime_capabilities,
)
from src.core.foundation.logging import logger
from src.core.mms.service import ModuleService, get_module_service
from src.core.rem.manager import EnvironmentManager, get_environment_manager
from src.core.rem.models import EnvKind, EnvRequirement
from src.core.atm.run_profile import AcquisitionMode, CreationLifecycle

TaskUpdateCallback = Callable[[Task], Awaitable[None]]
StopRequestedCallback = Callable[[], bool]
ContextReadyCallback = Callable[[TaskContext], None]


class TaskStopRequested(Exception):
    """任务收到停止请求。"""


def _deep_merge_dict(base: dict | None, override: dict | None) -> dict:
    """递归合并字典，override 优先。"""
    result = dict(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class ExecutionRequest:
    """ExecutionRunner 的通用输入。"""

    task: Task
    module_name: str
    hooks_module: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    provider_name: str = ""
    acquisition_mode: AcquisitionMode = AcquisitionMode.MATCH
    selector_wait_timeout: int = 60
    creation_params: dict[str, Any] = field(default_factory=dict)
    creation_lifecycle: CreationLifecycle = CreationLifecycle.EPHEMERAL
    execution_timeout: int = 0
    runtime_capabilities: RuntimeCapabilities | None = None


@dataclass
class ExecutionResult:
    """ExecutionRunner 的执行结果。"""

    task: Task
    task_context: TaskContext | None = None
    result: Any = None
    env_id: int | None = None
    env_created: bool = False
    prepare_result: dict[str, Any] | None = None


class ExecutionRunner:
    """共享执行内核。

    负责资源获取、TaskContext 注入、hooks 调用、模块执行与资源回收。
    """

    def __init__(
        self,
        *,
        rem: EnvironmentManager | None = None,
        mms: ModuleService | None = None,
        runtime_capabilities_factory: Callable[[str], RuntimeCapabilities] = build_runtime_capabilities,
    ):
        self.rem = rem or get_environment_manager()
        self.mms = mms or get_module_service()
        self._runtime_capabilities_factory = runtime_capabilities_factory

    async def run(
        self,
        request: ExecutionRequest,
        *,
        on_task_update: TaskUpdateCallback | None = None,
        on_context_ready: ContextReadyCallback | None = None,
        is_stop_requested: StopRequestedCallback | None = None,
    ) -> ExecutionResult:
        """执行一次完整的模块运行生命周期。"""

        task = request.task
        module_name = request.module_name
        hooks_module = request.hooks_module or module_name
        runtime_caps = request.runtime_capabilities or self._runtime_capabilities_factory(module_name)

        prepare_context = TaskContext(
            env_id=0,
            task_name=module_name,
            config=request.params.copy(),
            tools=runtime_caps.tools,
            state=dict(request.state),
        )

        prepare_result_raw = await self.mms.call_hook(hooks_module, "prepare_env", prepare_context)
        if prepare_result_raw is not None and not isinstance(prepare_result_raw, dict):
            raise ValueError("prepare_env must return dict or None")

        prepare_result = dict(prepare_result_raw or {})
        prepare_creation_params = prepare_result.get("creation_params", {})

        env_lease = None
        env_id = None
        env_created = False
        task_context = None
        result = None

        try:
            self._ensure_not_stopped(is_stop_requested)

            wait_timeout = int(prepare_result.get("wait_timeout", request.selector_wait_timeout))

            if request.acquisition_mode == AcquisitionMode.MATCH:
                req = EnvRequirement(
                    task_run_id=task.id,
                    kind=EnvKind.BROWSER,
                    timeout=wait_timeout,
                )
                env_lease = await self.rem.acquire_atomic(req, timeout=req.timeout)
                env_id = int(env_lease.env_id)
                task.lease_id = env_lease.id
                logger.info(f"[ATM] Task {task.id} acquired existing env {env_id}")
            elif request.acquisition_mode == AcquisitionMode.CREATE:
                merged_creation_params = _deep_merge_dict(
                    request.creation_params,
                    prepare_creation_params,
                )
                create_params = {
                    "creation_params": merged_creation_params,
                    "env_name": f"task-{task.id}-{int(time.time())}",
                }
                env = await self.rem.create_env(
                    provider_name=request.provider_name,
                    env_name=create_params["env_name"],
                    config=create_params,
                    post_action="none",
                    ensure_runtime=False,
                )
                env_id = env.id
                env_created = True
                logger.info(f"[ATM] Task {task.id} created env {env_id}")

                env_lease = await self.rem.lease_manager.acquire(env, task.id)
                task.lease_id = env_lease.id
            else:
                raise ValueError(
                    f"Unsupported acquisition mode for ATM runtime: {request.acquisition_mode.value}. "
                    "Only 'create' and 'match' are supported."
                )

            task.env_id = str(env_id)
            task.started_at = int(time.time())
            task.status = TaskStatus.RUNNING
            await self._publish_task_update(task, on_task_update)

            if not await self.rem.start_env(env_id):
                raise RuntimeError(f"Failed to start env {env_id}")

            self._ensure_not_stopped(is_stop_requested)
        except Exception as e:
            await self._cleanup_failed_acquisition(
                task=task,
                error=e,
                env_lease=env_lease,
                env_id=env_id,
                env_created=env_created,
                on_task_update=on_task_update,
            )
            return ExecutionResult(
                task=task,
                env_id=env_id,
                env_created=env_created,
                prepare_result=prepare_result,
            )

        try:
            page = None
            browser_ctx = None
            if task.env_id:
                env = await self.rem.get_env(int(task.env_id))
                if env and env.handle:
                    page = env.handle.page
                    browser_ctx = env.handle.context

            task_context = TaskContext(
                env_id=int(task.env_id) if task.env_id else 0,
                task_name=module_name,
                config=request.params.copy(),
                page=page,
                context=browser_ctx,
                tools=runtime_caps.tools,
                state=dict(request.state),
            )
            if on_context_ready:
                on_context_ready(task_context)

            await self.mms.call_hook(hooks_module, "init_env", task_context)
            await self.mms.call_hook(hooks_module, "before_run", task_context)

            if request.execution_timeout and request.execution_timeout > 0:
                result = await asyncio.wait_for(
                    self.mms.run_module(module_name, task_context),
                    timeout=request.execution_timeout,
                )
            else:
                result = await self.mms.run_module(module_name, task_context)

            if task_context.should_stop() or self._is_stop_requested(is_stop_requested):
                raise TaskStopRequested("Job paused during execution")

            task.message = str(result)
            task.status = TaskStatus.SUCCEEDED
            await self.mms.call_hook(hooks_module, "on_success", task_context, result)
        except asyncio.TimeoutError:
            logger.error(f"[ATM] Task {task.id} execution timed out")
            task.error = f"Execution Timeout: {request.execution_timeout}s"
            task.status = TaskStatus.FAILED
            if task_context:
                await self.mms.call_hook(hooks_module, "on_timeout", task_context)
        except TaskStopRequested as e:
            logger.info(f"[ATM] Task {task.id} cancelled: {e}")
            task.error = str(e)
            task.status = TaskStatus.CANCELLED
        except Exception as e:
            logger.error(f"[ATM] Task {task.id} execution failed: {e}")
            task.error = f"Execution Error: {str(e)}"
            task.status = TaskStatus.FAILED
            if task_context:
                await self.mms.call_hook(hooks_module, "on_failure", task_context, e)
        finally:
            task.finished_at = int(time.time())

            if task_context:
                try:
                    await self.mms.call_hook(hooks_module, "on_cleanup", task_context)
                except Exception as e:
                    logger.error(f"[ATM] Task {task.id} cleanup hook failed: {e}")

            if env_lease:
                try:
                    await self.rem.release(env_lease)
                    if env_created and request.creation_lifecycle == CreationLifecycle.EPHEMERAL:
                        logger.info(f"[ATM] Teardown: Destroying ephemeral env {env_id}")
                        await self.rem.destroy_env(int(task.env_id))
                except Exception as e:
                    logger.error(f"[ATM] Failed to release/destroy env {task.env_id}: {e}")

            await self._publish_task_update(task, on_task_update)

        return ExecutionResult(
            task=task,
            task_context=task_context,
            result=result,
            env_id=env_id,
            env_created=env_created,
            prepare_result=prepare_result,
        )

    async def _cleanup_failed_acquisition(
        self,
        *,
        task: Task,
        error: Exception,
        env_lease,
        env_id: int | None,
        env_created: bool,
        on_task_update: TaskUpdateCallback | None,
    ) -> None:
        if env_lease:
            try:
                await self.rem.release(env_lease)
            except Exception as release_error:
                logger.error(
                    f"[ATM] Task {task.id} failed to release lease during acquisition error: {release_error}"
                )

        if env_created and env_id is not None:
            try:
                await self.rem.destroy_env(int(env_id))
            except Exception as destroy_error:
                logger.error(
                    f"[ATM] Task {task.id} failed to destroy created env during acquisition error: {destroy_error}"
                )

        if isinstance(error, TaskStopRequested):
            task.status = TaskStatus.CANCELLED
            task.error = str(error)
        else:
            logger.warning(f"[ATM] Task {task.id} resource acquisition failed: {error}")
            task.status = TaskStatus.FAILED
            task.error = f"Resource Error: {str(error)}"

        task.finished_at = int(time.time())
        await self._publish_task_update(task, on_task_update)

    async def _publish_task_update(
        self,
        task: Task,
        callback: TaskUpdateCallback | None,
    ) -> None:
        if callback:
            await callback(task)

    def _ensure_not_stopped(self, callback: StopRequestedCallback | None) -> None:
        if self._is_stop_requested(callback):
            raise TaskStopRequested("Job paused")

    def _is_stop_requested(self, callback: StopRequestedCallback | None) -> bool:
        if not callback:
            return False
        return bool(callback())
