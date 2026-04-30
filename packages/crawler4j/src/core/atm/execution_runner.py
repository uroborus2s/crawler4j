"""Shared execution kernel for ATM tasks and future debug sessions."""

from __future__ import annotations

import asyncio
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from crawler4j_contracts import EnvAction, EnvCandidate, TaskContext, TaskResult, TaskSignal, TaskSignalAction
from src.core.atm.models import Task, TaskStatus
from src.core.atm.run_profile import AcquisitionMode, CreationLifecycle
from src.core.atm.runtime_capabilities import (
    RUNTIME_SURFACE_ENV_CANDIDATES,
    RuntimeCapabilities,
    build_runtime_capabilities,
)
from src.core.foundation.logging import logger
from src.core.mms.settings_store import ModuleSettingsStore, get_module_settings_store
from src.core.mms.service import ModuleService, get_module_service
from src.core.rem.manager import EnvironmentManager, get_environment_manager
from src.core.rem.models import (
    Environment,
    EnvKind,
    EnvLease,
    EnvRequirement,
    EnvStatus,
    EnvUnavailableError,
    ProxyConfig,
    ProxyMode,
)
from src.core.system.config_center import ConfigCenterService, get_config_center

TaskUpdateCallback = Callable[[Task], Awaitable[None]]
StopRequestedCallback = Callable[[], bool]
StopEnvActionCallback = Callable[[], EnvAction | None]
ContextReadyCallback = Callable[[TaskContext], None]
CANDIDATE_OWNER_METADATA_NAMESPACE = "scheduler.env_candidates"
CANDIDATE_OWNER_METADATA_KEY = "module_name"
CANDIDATE_EVALUATION_TIMEOUT_SECONDS = 10.0


class TaskStopRequested(Exception):
    """任务收到停止请求。"""


@dataclass
class ExecutionRequest:
    """ExecutionRunner 的通用输入。"""

    task: Task
    module_name: str
    workflow_name: str = "default"
    object_bindings: dict[str, str] = field(default_factory=dict)
    object_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    devel_mode: bool = False
    state: dict[str, Any] = field(default_factory=dict)
    provider_name: str = ""
    fixed_env_id: int | None = None
    candidates_name: str = ""
    candidate_params: dict[str, Any] = field(default_factory=dict)
    acquisition_mode: AcquisitionMode = AcquisitionMode.SELECT
    wait_timeout: int = 60
    wait_for_resource: bool = False
    creation_params: dict[str, Any] = field(default_factory=dict)
    creation_lifecycle: CreationLifecycle = CreationLifecycle.PERSISTENT
    execution_timeout: int = 0
    default_env_action: EnvAction | None = None
    runtime_capabilities: RuntimeCapabilities | None = None


@dataclass
class ExecutionResult:
    """ExecutionRunner 的执行结果。"""

    task: Task
    task_context: TaskContext | None = None
    result: TaskResult | None = None
    env_id: int | None = None
    env_created: bool = False
    env_lease_id: str | None = None
    signal: TaskSignal | None = None
    creation_lifecycle: CreationLifecycle = CreationLifecycle.PERSISTENT


class ExecutionRunner:
    """共享执行内核。

    负责资源获取、TaskContext 注入、模块执行与资源回收。
    """

    def __init__(
        self,
        *,
        rem: EnvironmentManager | None = None,
        mms: ModuleService | None = None,
        settings_store: ModuleSettingsStore | None = None,
        config: ConfigCenterService | None = None,
        runtime_capabilities_factory: Callable[[str], RuntimeCapabilities] = build_runtime_capabilities,
    ):
        self.rem = rem or get_environment_manager()
        self.mms = mms or get_module_service()
        self._settings_store = settings_store or get_module_settings_store()
        self._config = config or get_config_center()
        self._runtime_capabilities_factory = runtime_capabilities_factory
        self._module_poll_interval = 0.1
        self._env_action_timeout_seconds = self._get_timeout_budget("atm.env_action_timeout_seconds")
        logger.debug(
            "[ATM] ExecutionRunner timeout budgets loaded: "
            f"env_action={self._env_action_timeout_seconds:.1f}s"
        )

    def _get_timeout_budget(self, key: str) -> float:
        try:
            return float(self._config.get(key))
        except Exception as exc:
            logger.warning(f"[ATM] Failed to load timeout config {key}: {exc}")
            return float(self._config.registry.get_item(key).default)

    def _build_runtime_payload(self, request: ExecutionRequest) -> dict[str, Any]:
        return {
            "module_name": request.module_name,
            "workflow": request.workflow_name or "default",
            "devel_mode": bool(request.devel_mode),
            "object_bindings": deepcopy(request.object_bindings),
            "object_params": deepcopy(request.object_params),
            "provider_name": request.provider_name,
            "fixed_env_id": request.fixed_env_id,
            "candidates": request.candidates_name,
            "candidate_params": deepcopy(request.candidate_params),
            "acquisition_mode": request.acquisition_mode.value,
            "wait_timeout": request.wait_timeout,
            "wait_for_resource": bool(request.wait_for_resource),
            "creation_params": deepcopy(request.creation_params),
            "execution_timeout": request.execution_timeout,
        }

    async def run(
        self,
        request: ExecutionRequest,
        *,
        on_task_update: TaskUpdateCallback | None = None,
        on_context_ready: ContextReadyCallback | None = None,
        is_stop_requested: StopRequestedCallback | None = None,
        resolve_stop_env_action: StopEnvActionCallback | None = None,
    ) -> ExecutionResult:
        """执行一次完整的模块运行生命周期。"""

        task = request.task
        module_name = request.module_name
        runtime_caps = request.runtime_capabilities or self._runtime_capabilities_factory(module_name)
        task_config = self._settings_store.build_task_config(module_name, request.workflow_name)

        acquisition_context = TaskContext(
            env_id=0,
            task_name=module_name,
            config=deepcopy(task_config),
            logger=logger,
            tools=runtime_caps.tools,
            db=runtime_caps.db,
            state=dict(request.state),
            runtime=self._build_runtime_payload(request),
        )

        env_lease = None
        env_id = None
        env_created = False
        task_context = None
        result: TaskResult | None = None
        signal: TaskSignal | None = None
        effective_creation_params = deepcopy(request.creation_params)

        try:
            self._ensure_not_stopped(is_stop_requested)

            wait_timeout = int(request.wait_timeout)

            if request.acquisition_mode == AcquisitionMode.SELECT:
                if request.fixed_env_id is not None:
                    selected_env_id = int(request.fixed_env_id)
                    env = await self.rem.get_env(selected_env_id)
                    if not env:
                        raise RuntimeError(f"指定环境不存在: {selected_env_id}")
                    await self._assert_env_claimable_by_module(selected_env_id, request.module_name)
                    if env.status == EnvStatus.RUNNING and env.lease_id is None:
                        env_lease = await self.rem.lease_manager.claim_created_env(
                            env,
                            task.id,
                            timeout=wait_timeout,
                        )
                    else:
                        env_lease = await self.rem.lease_manager.acquire(env, task.id, timeout=wait_timeout)
                    await self._bind_env_to_module(selected_env_id, request.module_name)
                    env_id = int(env_lease.env_id)
                    task.lease_id = env_lease.id
                    logger.info(f"[ATM] Task {task.id} selected fixed env {env_id}")
                else:
                    candidate_env_ids = await self._resolve_candidate_env_ids(
                        module_name=request.module_name,
                        context=acquisition_context,
                        candidates_name=request.candidates_name,
                        candidate_params=request.candidate_params,
                    )
                    candidates = await self._list_ready_env_candidates(
                        candidate_env_ids=candidate_env_ids,
                        module_name=request.module_name,
                    )
                    if not candidates and request.wait_for_resource:
                        return await self._return_waiting_for_resource(
                            task=task,
                            candidates_name=request.candidates_name,
                            on_task_update=on_task_update,
                            creation_lifecycle=request.creation_lifecycle,
                        )
                    allocatable_candidate_ids = {int(candidate.env_id) for candidate in candidates}

                    selected_env_id = candidates[0].env_id if candidates else None

                    if selected_env_id is None:
                        if request.wait_for_resource:
                            return await self._return_waiting_for_resource(
                                task=task,
                                candidates_name=request.candidates_name,
                                on_task_update=on_task_update,
                                creation_lifecycle=request.creation_lifecycle,
                            )
                        raise RuntimeError("没有可用环境可供选择")

                    selected_env_id = int(selected_env_id)
                    selected_from_candidates = selected_env_id in allocatable_candidate_ids

                    env = await self.rem.get_env(selected_env_id)
                    if not env:
                        if request.wait_for_resource and selected_from_candidates:
                            logger.debug(f"[ATM] Task {task.id} lost candidate env {selected_env_id} before lease; requeueing.")
                            return await self._return_waiting_for_resource(
                                task=task,
                                candidates_name=request.candidates_name,
                                on_task_update=on_task_update,
                                creation_lifecycle=request.creation_lifecycle,
                            )
                        raise RuntimeError(f"选择到的环境不存在: {selected_env_id}")

                    try:
                        env_lease = await self.rem.lease_manager.acquire(env, task.id, timeout=wait_timeout)
                    except EnvUnavailableError:
                        if request.wait_for_resource and selected_from_candidates:
                            logger.debug(f"[ATM] Task {task.id} lost candidate env {selected_env_id} lease race; requeueing.")
                            return await self._return_waiting_for_resource(
                                task=task,
                                candidates_name=request.candidates_name,
                                on_task_update=on_task_update,
                                creation_lifecycle=request.creation_lifecycle,
                            )
                        raise
                    if request.wait_for_resource and selected_from_candidates:
                        still_allocatable = await self._is_candidate_env_allocatable(
                            env_id=selected_env_id,
                            module_name=request.module_name,
                            context=acquisition_context,
                            candidates_name=request.candidates_name,
                            candidate_params=request.candidate_params,
                        )
                        if not still_allocatable:
                            logger.debug(
                                f"[ATM] Task {task.id} found candidate env {selected_env_id} no longer allocatable after lease; requeueing."
                            )
                            await self.rem.release(env_lease)
                            return await self._return_waiting_for_resource(
                                task=task,
                                candidates_name=request.candidates_name,
                                on_task_update=on_task_update,
                                creation_lifecycle=request.creation_lifecycle,
                            )
                    env_id = int(env_lease.env_id)
                    task.lease_id = env_lease.id
                    logger.info(f"[ATM] Task {task.id} selected env {env_id}")
            elif request.acquisition_mode == AcquisitionMode.CREATE:
                merged_creation_params = dict(request.creation_params)
                effective_creation_params = deepcopy(merged_creation_params)
                acquisition_context.runtime["creation_params"] = deepcopy(merged_creation_params)
                proxy_config = self._extract_proxy_config(merged_creation_params)
                create_params = {
                    "creation_params": merged_creation_params,
                    "env_name": f"task-{task.id}-{int(time.time())}",
                }
                env = await self.rem.create_env(
                    provider_name=request.provider_name,
                    env_name=create_params["env_name"],
                    config=create_params,
                    requirement=EnvRequirement(proxy_config=proxy_config) if proxy_config else None,
                    ensure_runtime=False,
                )
                env_id = env.id
                env_created = True
                await self._bind_env_to_module(env_id, request.module_name)
                logger.info(f"[ATM] Task {task.id} created env {env_id}")

                env_lease = await self.rem.lease_manager.claim_created_env(env, task.id)
                task.lease_id = env_lease.id
            else:
                raise ValueError(
                    f"Unsupported acquisition mode for ATM runtime: {request.acquisition_mode.value}. "
                    "Only 'create' and 'select' are supported."
                )

            task.env_id = str(env_id)
            task.started_at = int(time.time())
            task.waiting_since = None
            if not env_created:
                task.message = "环境启动中"
                task.status = TaskStatus.PENDING
                await self._publish_task_update(task, on_task_update)

            if not env_created and not await self.rem.start_env(env_id):
                raise RuntimeError(f"Failed to start env {env_id}")

            self._ensure_not_stopped(is_stop_requested)
            task.message = ""
            task.status = TaskStatus.RUNNING
            await self._publish_task_update(task, on_task_update)
        except Exception as e:
            await self._cleanup_failed_acquisition(
                task=task,
                error=e,
                env_lease=env_lease,
                env_id=env_id,
                env_created=env_created,
                creation_lifecycle=request.creation_lifecycle,
                resolve_stop_env_action=resolve_stop_env_action,
                on_task_update=on_task_update,
            )
            return ExecutionResult(
                task=task,
                env_id=env_id,
                env_created=env_created,
                env_lease_id=env_lease.id if env_lease else None,
                creation_lifecycle=request.creation_lifecycle,
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
                config=deepcopy(task_config),
                page=page,
                context=browser_ctx,
                logger=logger,
                tools=runtime_caps.tools,
                db=runtime_caps.db,
                state=dict(request.state),
                runtime=self._build_runtime_payload(request),
            )
            task_context.runtime.update(
                {
                    "creation_params": deepcopy(effective_creation_params),
                    "env_created": env_created,
                    "creation_lifecycle": request.creation_lifecycle.value,
                }
            )
            if on_context_ready:
                on_context_ready(task_context)

            if task.status == TaskStatus.RUNNING:
                task_context.set_signal_phase("run_module")
                try:
                    raw_result = await self._run_module_with_stop_guard(
                        module_name=module_name,
                        task_context=task_context,
                        execution_timeout=request.execution_timeout,
                        is_stop_requested=is_stop_requested,
                    )
                finally:
                    task_context.set_signal_phase(None)

                if task_context.should_stop() or self._is_stop_requested(is_stop_requested):
                    raise TaskStopRequested("Job paused during execution")

                result = self._normalize_task_result(raw_result)
                signal = self._resolve_task_signal(task_context, result)
                if signal:
                    self._apply_signal_outcome(task, signal, result)
                elif result.success:
                    task.message = result.message or str(result.data or raw_result)
                    task.error = ""
                    task.status = TaskStatus.SUCCEEDED
                else:
                    task.message = result.message
                    task.error = result.error or result.message
                    task.status = TaskStatus.FAILED

            self._record_runtime_outcome(task_context, task, result, signal)

            if task.status == TaskStatus.WAITING_CONFIRMATION:
                await self._publish_task_update(task, on_task_update)
                return ExecutionResult(
                    task=task,
                    task_context=task_context,
                    result=result,
                    env_id=env_id,
                    env_created=env_created,
                    env_lease_id=env_lease.id if env_lease else None,
                    signal=signal,
                    creation_lifecycle=request.creation_lifecycle,
                )
        except asyncio.TimeoutError:
            logger.error(f"[ATM] Task {task.id} execution timed out")
            task.error = f"Execution Timeout: {request.execution_timeout}s"
            task.message = ""
            task.status = TaskStatus.FAILED
            if task_context:
                task_context.runtime["final_status"] = task.status.value
                task_context.runtime["task_error"] = task.error
        except asyncio.CancelledError as e:
            if task_context and (task_context.should_stop() or self._is_stop_requested(is_stop_requested)):
                logger.info(f"[ATM] Task {task.id} cancelled: {e}")
                task.error = str(e) or "Job paused during execution"
                task.message = ""
                task.status = TaskStatus.CANCELLED
            else:
                raise
        except TaskStopRequested as e:
            logger.info(f"[ATM] Task {task.id} cancelled: {e}")
            task.error = str(e)
            task.message = ""
            task.status = TaskStatus.CANCELLED
        except Exception as e:
            logger.error(f"[ATM] Task {task.id} execution failed: {e}")
            task.error = f"Execution Error: {str(e)}"
            task.message = ""
            task.status = TaskStatus.FAILED
            if task_context:
                task_context.runtime["final_status"] = task.status.value
                task_context.runtime["task_error"] = task.error

        task.finished_at = int(time.time())

        resolved_env_action = None
        if task_context:
            task_context.runtime["final_status"] = task.status.value
            task_context.runtime["task_error"] = task.error
            resolved_env_action = self._resolve_requested_env_action(
                task=task,
                signal=signal,
                env_created=env_created,
                creation_lifecycle=request.creation_lifecycle,
                default_env_action=request.default_env_action,
                resolve_stop_env_action=resolve_stop_env_action,
            )
            if env_lease and resolved_env_action:
                task_context.runtime["env_action"] = {
                    "action": resolved_env_action.value,
                    "env_id": int(task.env_id) if task.env_id else None,
                    "success": None,
                }

        if env_lease:
            resolved_env_action = resolved_env_action or self._resolve_requested_env_action(
                task=task,
                signal=signal,
                env_created=env_created,
                creation_lifecycle=request.creation_lifecycle,
                default_env_action=request.default_env_action,
                resolve_stop_env_action=resolve_stop_env_action,
            )
            env_action_info = await self._apply_env_action(
                env_lease=env_lease,
                env_action=resolved_env_action,
                env_id=int(task.env_id) if task.env_id else None,
            )
            if task_context:
                task_context.runtime["env_action"] = env_action_info

        await self._publish_task_update(task, on_task_update)

        return ExecutionResult(
            task=task,
            task_context=task_context,
            result=result,
            env_id=env_id,
            env_created=env_created,
            env_lease_id=env_lease.id if env_lease else None,
            signal=signal,
            creation_lifecycle=request.creation_lifecycle,
        )

    async def finalize_waiting(
        self,
        *,
        task: Task,
        task_context: TaskContext,
        env_lease: EnvLease | None,
        env_created: bool,
        creation_lifecycle: CreationLifecycle,
        confirmed: bool,
        confirmation_message: str = "",
        on_task_update: TaskUpdateCallback | None = None,
    ) -> ExecutionResult:
        """完成等待人工确认的任务。"""

        if task.status != TaskStatus.WAITING_CONFIRMATION:
            raise ValueError(f"Task {task.id} is not waiting for confirmation")

        if confirmed:
            result = TaskResult.ok(message=confirmation_message or task.message or "人工确认成功")
            task.status = TaskStatus.SUCCEEDED
            task.message = result.message
            task.error = ""
        else:
            result = TaskResult.fail(
                message=confirmation_message or task.message or "人工确认失败",
                error=confirmation_message or "user_confirmation_failed",
            )
            task.status = TaskStatus.FAILED
            task.message = result.message
            task.error = result.error or result.message

        task.finished_at = int(time.time())
        self._record_runtime_outcome(task_context, task, result, None)

        if env_lease:
            task_context.runtime["env_action"] = {
                "action": self._default_env_action(env_created, creation_lifecycle).value,
                "env_id": int(task.env_id) if task.env_id else None,
                "success": None,
            }
        if env_lease:
            env_action_info = await self._apply_env_action(
                env_lease=env_lease,
                env_action=self._default_env_action(env_created, creation_lifecycle),
                env_id=int(task.env_id) if task.env_id else None,
            )
            task_context.runtime["env_action"] = env_action_info
        await self._publish_task_update(task, on_task_update)

        return ExecutionResult(
            task=task,
            task_context=task_context,
            result=result,
            env_id=int(task.env_id) if task.env_id else None,
            env_created=env_created,
            env_lease_id=env_lease.id if env_lease else None,
            signal=None,
            creation_lifecycle=creation_lifecycle,
        )

    async def cancel_waiting(
        self,
        *,
        task: Task,
        task_context: TaskContext,
        env_lease: EnvLease | None,
        env_created: bool,
        creation_lifecycle: CreationLifecycle,
        env_action: EnvAction | None = None,
        cancel_message: str = "Job paused",
        on_task_update: TaskUpdateCallback | None = None,
    ) -> ExecutionResult:
        """取消等待人工确认的任务，并执行统一 cleanup / 环境收口。"""

        if task.status != TaskStatus.WAITING_CONFIRMATION:
            raise ValueError(f"Task {task.id} is not waiting for confirmation")

        result = TaskResult.fail(message=cancel_message, error=cancel_message)
        task.status = TaskStatus.CANCELLED
        task.message = ""
        task.error = cancel_message
        task.finished_at = int(time.time())
        self._record_runtime_outcome(task_context, task, result, None)

        resolved_env_action = env_action or self._default_env_action(env_created, creation_lifecycle)
        if env_lease:
            task_context.runtime["env_action"] = {
                "action": resolved_env_action.value,
                "env_id": int(task.env_id) if task.env_id else None,
                "success": None,
            }

        if env_lease:
            env_action_info = await self._apply_env_action(
                env_lease=env_lease,
                env_action=resolved_env_action,
                env_id=int(task.env_id) if task.env_id else None,
            )
            task_context.runtime["env_action"] = env_action_info

        await self._publish_task_update(task, on_task_update)

        return ExecutionResult(
            task=task,
            task_context=task_context,
            result=result,
            env_id=int(task.env_id) if task.env_id else None,
            env_created=env_created,
            env_lease_id=env_lease.id if env_lease else None,
            signal=None,
            creation_lifecycle=creation_lifecycle,
        )

    def _extract_proxy_config(self, creation_params: dict[str, Any]) -> ProxyConfig | None:
        raw_proxy = creation_params.pop("proxy", None)
        if not isinstance(raw_proxy, dict):
            return None

        mode_raw = raw_proxy.get("mode", ProxyMode.NONE.value)
        try:
            mode = ProxyMode(mode_raw)
        except ValueError:
            mode = ProxyMode.NONE

        return ProxyConfig(
            mode=mode,
            pool_id=raw_proxy.get("pool_id"),
            bind_strategy=raw_proxy.get("bind_strategy"),
            static_value=raw_proxy.get("static_value"),
            current_ip=raw_proxy.get("current_ip"),
        )

    async def _list_ready_env_candidates(
        self,
        *,
        candidate_env_ids: list[int],
        module_name: str,
    ) -> list[EnvCandidate]:
        if not candidate_env_ids:
            return []
        wanted = [int(env_id) for env_id in candidate_env_ids]
        wanted_set = set(wanted)
        by_id = {int(env.id): env for env in await self.rem.list_envs() if int(env.id) in wanted_set}
        candidates: list[EnvCandidate] = []
        for env_id in wanted:
            env = by_id.get(env_id)
            if env is None:
                continue
            if env.kind != EnvKind.BROWSER or env.status != EnvStatus.READY:
                continue
            if getattr(env, "lease_id", None):
                continue
            if not await self._is_env_candidate_authorized(env.id, module_name):
                logger.warning(
                    f"[ATM] Candidate env {env.id} ignored because it is not bound to module {module_name}"
                )
                continue
            candidates.append(self._to_env_candidate(env))
        return candidates

    async def _resolve_candidate_env_ids(
        self,
        *,
        module_name: str,
        context: TaskContext,
        candidates_name: str,
        candidate_params: dict[str, Any],
    ) -> list[int]:
        candidate_caps = build_runtime_capabilities(module_name, surface=RUNTIME_SURFACE_ENV_CANDIDATES)
        candidate_context = TaskContext(
            env_id=0,
            task_name=module_name,
            config=deepcopy(context.config),
            logger=context.logger,
            tools=candidate_caps.tools,
            db=candidate_caps.db,
            state=dict(context.state),
            runtime=deepcopy(context.runtime),
        )
        resolver = getattr(self.mms, "resolve_env_candidates_async", None)
        if callable(resolver):
            return await resolver(
                module_name,
                candidate_context,
                candidates_name,
                candidate_params,
                timeout=CANDIDATE_EVALUATION_TIMEOUT_SECONDS,
            )
        return self.mms.resolve_env_candidates(module_name, candidate_context, candidates_name, candidate_params)

    async def _is_candidate_env_allocatable(
        self,
        *,
        env_id: int,
        module_name: str,
        context: TaskContext,
        candidates_name: str,
        candidate_params: dict[str, Any],
    ) -> bool:
        candidate_env_ids = await self._resolve_candidate_env_ids(
            module_name=module_name,
            context=context,
            candidates_name=candidates_name,
            candidate_params=candidate_params,
        )
        if int(env_id) not in {int(candidate_id) for candidate_id in candidate_env_ids}:
            return False
        return await self._is_env_candidate_authorized(int(env_id), module_name)

    async def _get_env_owner_module(self, env_id: int) -> str:
        get_metadata = getattr(self.rem, "get_metadata", None)
        if not callable(get_metadata):
            return ""
        owner = await get_metadata(
            env_id,
            CANDIDATE_OWNER_METADATA_NAMESPACE,
            CANDIDATE_OWNER_METADATA_KEY,
        )
        return str(owner or "").strip()

    async def _assert_env_claimable_by_module(self, env_id: int, module_name: str) -> None:
        owner = await self._get_env_owner_module(int(env_id))
        if owner and owner != module_name:
            raise RuntimeError(f"环境 {env_id} 已绑定到模块 {owner}，不能被 {module_name} 使用")

    async def _bind_env_to_module(self, env_id: int, module_name: str) -> None:
        set_metadata = getattr(self.rem, "set_metadata", None)
        if not callable(set_metadata):
            return
        await self._assert_env_claimable_by_module(int(env_id), module_name)
        await set_metadata(
            int(env_id),
            CANDIDATE_OWNER_METADATA_NAMESPACE,
            CANDIDATE_OWNER_METADATA_KEY,
            module_name,
            "string",
        )

    async def _is_env_candidate_authorized(self, env_id: int, module_name: str) -> bool:
        get_metadata = getattr(self.rem, "get_metadata", None)
        if not callable(get_metadata):
            return True
        owner = await self._get_env_owner_module(int(env_id))
        return owner == module_name

    async def _mark_task_waiting_for_resource(
        self,
        task: Task,
        candidates_name: str,
        *,
        on_task_update: TaskUpdateCallback | None,
    ) -> None:
        candidates_label = str(candidates_name or "").strip() or "default"
        task.status = TaskStatus.PENDING
        task.env_id = None
        task.lease_id = None
        task.message = f"等待环境候选可用: {candidates_label}"
        task.error = ""
        task.waiting_since = task.waiting_since or int(time.time())
        task.started_at = None
        task.finished_at = None
        await self._publish_task_update(task, on_task_update)

    async def _return_waiting_for_resource(
        self,
        *,
        task: Task,
        candidates_name: str,
        on_task_update: TaskUpdateCallback | None,
        creation_lifecycle: CreationLifecycle,
    ) -> ExecutionResult:
        await self._mark_task_waiting_for_resource(
            task,
            candidates_name,
            on_task_update=on_task_update,
        )
        return ExecutionResult(
            task=task,
            env_id=None,
            env_created=False,
            env_lease_id=None,
            creation_lifecycle=creation_lifecycle,
        )

    def _to_env_candidate(self, env: Environment) -> EnvCandidate:
        return EnvCandidate(
            env_id=int(env.id),
            name=env.name,
            provider=env.provider,
            status=env.status.value if env.status else "",
            external_id=env.external_id,
            capabilities=tuple(sorted(env.capabilities)),
            proxy=env.proxy_config.to_dict() if env.proxy_config else None,
        )

    async def _cleanup_failed_acquisition(
        self,
        *,
        task: Task,
        error: Exception,
        env_lease,
        env_id: int | None,
        env_created: bool,
        creation_lifecycle: CreationLifecycle,
        resolve_stop_env_action: StopEnvActionCallback | None,
        on_task_update: TaskUpdateCallback | None,
    ) -> None:
        stop_env_action = None
        if isinstance(error, TaskStopRequested):
            stop_env_action = (
                resolve_stop_env_action() if resolve_stop_env_action else None
            ) or self._default_env_action(env_created, creation_lifecycle)

        if env_lease:
            try:
                if stop_env_action is not None:
                    await self._apply_env_action(
                        env_lease=env_lease,
                        env_action=stop_env_action,
                        env_id=env_id,
                    )
                else:
                    await self.rem.release(env_lease)
            except Exception as release_error:
                logger.error(
                    f"[ATM] Task {task.id} failed to release lease during acquisition error: {release_error}"
                )

        elif env_created and env_id is not None:
            try:
                await self._apply_created_env_stop_action_without_lease(
                    env_id=int(env_id),
                    env_action=stop_env_action or self._default_env_action(env_created, creation_lifecycle),
                )
            except Exception as reset_error:
                logger.error(
                    f"[ATM] Task {task.id} failed to clean env during acquisition error: {reset_error}"
                )

        if isinstance(error, TaskStopRequested):
            task.status = TaskStatus.CANCELLED
            task.error = str(error)
        else:
            logger.warning(f"[ATM] Task {task.id} resource acquisition failed: {error}")
            task.status = TaskStatus.FAILED
            task.error = f"Resource Error: {str(error)}"

        task.message = ""
        task.waiting_since = None
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

    async def _run_module_with_stop_guard(
        self,
        *,
        module_name: str,
        task_context: TaskContext,
        execution_timeout: int,
        is_stop_requested: StopRequestedCallback | None,
    ) -> Any:
        module_task = asyncio.create_task(self.mms.run_module(module_name, task_context))
        deadline = time.monotonic() + execution_timeout if execution_timeout and execution_timeout > 0 else None

        try:
            while True:
                self._ensure_task_context_running(task_context, is_stop_requested)

                wait_timeout = self._module_poll_interval
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        await self._cancel_asyncio_task(module_task)
                        raise asyncio.TimeoutError
                    wait_timeout = min(wait_timeout, remaining)

                try:
                    return await asyncio.wait_for(asyncio.shield(module_task), timeout=wait_timeout)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError as exc:
                    if task_context.should_stop() or self._is_stop_requested(is_stop_requested):
                        await self._cancel_asyncio_task(module_task)
                        raise TaskStopRequested("Job paused during execution") from exc
                    raise
        except BaseException:
            if not module_task.done():
                await self._cancel_asyncio_task(module_task)
            raise

    async def _cancel_asyncio_task(self, task: asyncio.Task[Any]) -> None:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    def _ensure_task_context_running(
        self,
        task_context: TaskContext,
        is_stop_requested: StopRequestedCallback | None,
    ) -> None:
        if task_context.should_stop() or self._is_stop_requested(is_stop_requested):
            raise TaskStopRequested("Job paused during execution")

    def _normalize_task_result(self, result: Any) -> TaskResult:
        if isinstance(result, TaskResult):
            return result
        if result is None:
            return TaskResult.ok()
        if isinstance(result, dict):
            return TaskResult.ok(message=str(result), data=result)
        return TaskResult.ok(message=str(result), data={"value": result})

    def _resolve_task_signal(
        self,
        task_context: TaskContext,
        task_result: TaskResult | None,
    ) -> TaskSignal | None:
        emitted_signal = task_context.get_signal()
        result_signal = task_result.signal if task_result else None
        if emitted_signal and result_signal and emitted_signal != result_signal:
            raise ValueError("TaskContext.emit_signal 与 TaskResult.signal 同时存在且不一致")
        task_context.clear_signal()
        return result_signal or emitted_signal

    def _signal_to_task_result(self, signal: TaskSignal) -> TaskResult:
        if signal.action == TaskSignalAction.FAIL:
            return TaskResult.fail(
                message=signal.message or "任务失败",
                error=signal.error,
                data=dict(signal.payload),
                signal=signal,
            )
        return TaskResult.ok(
            message=signal.message or "任务完成",
            data=dict(signal.payload),
            signal=signal,
        )

    def _apply_signal_outcome(
        self,
        task: Task,
        signal: TaskSignal,
        result: TaskResult,
    ) -> None:
        task.signal = signal.to_dict()
        task.message = signal.message or result.message
        if signal.action == TaskSignalAction.SUCCEED:
            task.error = ""
            task.status = TaskStatus.SUCCEEDED
            return
        if signal.action == TaskSignalAction.FAIL:
            task.error = signal.error or result.error or signal.message or result.message
            task.status = TaskStatus.FAILED
            return
        if signal.action == TaskSignalAction.CANCEL:
            task.error = signal.error or signal.message or ""
            task.status = TaskStatus.CANCELLED
            return
        if signal.action == TaskSignalAction.WAIT_FOR_CONFIRMATION:
            if signal.env_action not in {None, EnvAction.KEEP_ALIVE}:
                raise ValueError("wait_for_confirmation 信号仅支持 keep_alive 环境语义")
            task.error = ""
            task.status = TaskStatus.WAITING_CONFIRMATION
            return
        raise ValueError(f"Unsupported task signal action: {signal.action}")

    def _record_runtime_outcome(
        self,
        task_context: TaskContext,
        task: Task,
        result: TaskResult | None,
        signal: TaskSignal | None,
    ) -> None:
        if signal:
            task.signal = signal.to_dict()
        elif task.status != TaskStatus.WAITING_CONFIRMATION:
            task.signal = None
        if task.status != TaskStatus.PENDING:
            task.waiting_since = None
        task_context.runtime["final_status"] = task.status.value
        task_context.runtime["task_error"] = task.error
        if result:
            task_context.runtime["task_result"] = result.to_dict()
        if signal:
            task_context.runtime["task_signal"] = signal.to_dict()

    def _default_env_action(
        self,
        _env_created: bool,
        _creation_lifecycle: CreationLifecycle,
    ) -> EnvAction:
        # 默认仅关闭并回收环境；显式 DESTROY 信号才允许删除。
        return EnvAction.RECYCLE

    async def _await_env_action_step(self, label: str, operation: Awaitable[Any]) -> Any:
        started_at = time.monotonic()
        try:
            result = await asyncio.wait_for(
                operation,
                timeout=self._env_action_timeout_seconds,
            )
            logger.debug(
                f"[ATM] Env action step finished: step={label} "
                f"budget={self._env_action_timeout_seconds:.1f}s "
                f"duration={time.monotonic() - started_at:.3f}s"
            )
            return result
        except asyncio.TimeoutError as exc:
            logger.error(
                f"[ATM] Env action step timeout: step={label} "
                f"budget={self._env_action_timeout_seconds:.1f}s "
                f"duration={time.monotonic() - started_at:.3f}s"
            )
            raise TimeoutError(
                f"{label} timed out after {self._env_action_timeout_seconds:.1f}s"
            ) from exc

    async def _apply_env_action(
        self,
        *,
        env_lease: EnvLease,
        env_action: EnvAction,
        env_id: int | None,
    ) -> dict[str, Any]:
        info = {
            "action": env_action.value,
            "env_id": env_id,
            "success": False,
        }
        logger.info(
            f"[ATM] Applying env action: env_id={env_id} action={env_action.value} "
            f"budget={self._env_action_timeout_seconds:.1f}s"
        )
        try:
            if env_action == EnvAction.RECYCLE:
                info["success"] = await self._await_env_action_step(
                    "release",
                    self.rem.release(env_lease),
                )
                logger.info(
                    f"[ATM] Env action finished: env_id={env_id} "
                    f"action={env_action.value} success={info['success']}"
                )
                return info
            if env_action == EnvAction.KEEP_ALIVE:
                info["success"] = await self._await_env_action_step(
                    "release_keep_alive",
                    self.rem.release_keep_alive(env_lease),
                )
                logger.info(
                    f"[ATM] Env action finished: env_id={env_id} "
                    f"action={env_action.value} success={info['success']}"
                )
                return info
            if env_action == EnvAction.DESTROY:
                released = await self._await_env_action_step(
                    "release_keep_alive",
                    self.rem.release_keep_alive(env_lease),
                )
                destroyed = (
                    released
                    and bool(env_id is not None)
                    and await self._await_env_action_step(
                        "destroy_env",
                        self.rem.destroy_env(int(env_id)),
                    )
                )
                info["success"] = released and destroyed
                info["released"] = released
                info["destroyed"] = destroyed
                logger.info(
                    f"[ATM] Env action finished: env_id={env_id} action={env_action.value} "
                    f"success={info['success']} released={released} destroyed={destroyed}"
                )
                return info
        except Exception as e:
            logger.error(f"[ATM] Failed to apply env action {env_action.value} for env {env_id}: {e}")
            info["error"] = str(e)
            return info
        raise ValueError(f"Unsupported env action: {env_action}")

    def _task_log_id(self, task_context: TaskContext) -> str:
        runtime = getattr(task_context, "runtime", {}) or {}
        return str(runtime.get("task_id") or runtime.get("job_id") or task_context.task_name)

    def _resolve_requested_env_action(
        self,
        *,
        task: Task,
        signal: TaskSignal | None,
        env_created: bool,
        creation_lifecycle: CreationLifecycle,
        default_env_action: EnvAction | None,
        resolve_stop_env_action: StopEnvActionCallback | None,
    ) -> EnvAction:
        if signal and signal.env_action is not None:
            return signal.env_action
        if task.status == TaskStatus.CANCELLED and resolve_stop_env_action:
            requested = resolve_stop_env_action()
            if requested is not None:
                return requested
        if default_env_action is not None:
            return default_env_action
        return self._default_env_action(env_created, creation_lifecycle)

    async def _apply_created_env_stop_action_without_lease(
        self,
        *,
        env_id: int,
        env_action: EnvAction,
    ) -> None:
        if env_action == EnvAction.KEEP_ALIVE:
            return
        if env_action == EnvAction.DESTROY:
            await self._await_env_action_step(
                "destroy_env",
                self.rem.destroy_env(env_id),
            )
            return
        env = await self._await_env_action_step(
            "get_env",
            self.rem.get_env(env_id),
        )
        if env:
            await self._await_env_action_step(
                "recycle_env",
                self.rem.recycle_env(env),
            )
