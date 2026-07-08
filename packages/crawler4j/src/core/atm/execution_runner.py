"""Shared execution kernel for ATM tasks and future debug sessions."""

from __future__ import annotations

import asyncio
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from crawler4j_contracts import EnvCandidate, TaskContext, TaskResult
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
from src.core.rem.env_claims import (
    CLAIM_CLAIMED,
    get_env_claim,
    is_env_bound_by_module,
    release_bound_run_status_after_task,
    refresh_env_claim_after_task,
    set_claimed_env_claim,
    set_pending_env_claim,
)
from src.core.rem.manager import EnvironmentManager, get_environment_manager
from src.core.rem.fingerprint_validation import (
    FINGERPRINT_VALIDATION_NAMESPACE,
    is_fingerprint_validation_risk,
)
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
ContextReadyCallback = Callable[[TaskContext], None]
CANDIDATE_EVALUATION_TIMEOUT_SECONDS = 10.0


class TaskStopRequested(Exception):
    """任务收到停止请求。"""


@dataclass
class ExecutionRequest:
    """ExecutionRunner 的通用输入。"""

    task: Task
    module_name: str
    workflow_name: str = ""
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
        self._env_recycle_timeout_seconds = self._get_timeout_budget("atm.env_recycle_timeout_seconds")
        logger.debug(
            "[ATM] ExecutionRunner timeout budgets loaded: "
            f"env_recycle={self._env_recycle_timeout_seconds:.1f}s"
        )

    def _get_timeout_budget(self, key: str) -> float:
        try:
            return float(self._config.get(key))
        except Exception as exc:
            logger.warning(f"[ATM] Failed to load timeout config {key}: {exc}")
            return float(self._config.registry.get_item(key).default)

    def _build_runtime_payload(self, request: ExecutionRequest) -> dict[str, Any]:
        runtime_payload = {
            "module_name": request.module_name,
            "workflow": str(request.workflow_name or "").strip(),
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
        if "import_payload" in request.creation_params:
            runtime_payload["import_payload"] = deepcopy(request.creation_params["import_payload"])
        return runtime_payload

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
        env: Environment | None = None
        env_id = None
        env_created = False
        env_claim_refresh_required = False
        task_context = None
        result: TaskResult | None = None
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
                    if await self._is_env_fingerprint_validation_risk(selected_env_id):
                        raise RuntimeError(f"环境 {selected_env_id} 指纹风险待复检")
                    await self._assert_env_claimable_by_module(selected_env_id, request.module_name)
                    if env.status == EnvStatus.RUNNING and env.lease_id is None:
                        env_lease = await self.rem.lease_manager.claim_created_env(
                            env,
                            task.id,
                            timeout=wait_timeout,
                        )
                    else:
                        env_lease = await self.rem.lease_manager.acquire(env, task.id, timeout=wait_timeout)
                    await self._claim_fixed_env_for_module(selected_env_id, request.module_name, task.id)
                    env_claim_refresh_required = True
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
                await set_pending_env_claim(
                    self.rem,
                    env_id,
                    owner_module=request.module_name,
                    task_id=task.id,
                )
                env_claim_refresh_required = True
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
                env_claim_refresh_required=env_claim_refresh_required,
                acquisition_context=acquisition_context,
                module_name=request.module_name,
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
                raw_result = await self._run_module_with_stop_guard(
                    module_name=module_name,
                    task_context=task_context,
                    execution_timeout=request.execution_timeout,
                    is_stop_requested=is_stop_requested,
                )

                if task_context.should_stop() or self._is_stop_requested(is_stop_requested):
                    raise TaskStopRequested("Job paused during execution")

                result = self._normalize_task_result(raw_result)
                if result.success:
                    self._mark_bound_ip_used(env)
                    task.message = result.message or str(result.data or raw_result)
                    task.error = ""
                    task.status = TaskStatus.SUCCEEDED
                else:
                    task.message = result.message
                    task.error = result.error or result.message
                    task.status = TaskStatus.FAILED

            self._record_runtime_outcome(task_context, task, result)
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

        if task_context:
            task_context.runtime["final_status"] = task.status.value
            task_context.runtime["task_error"] = task.error

        if env_lease:
            recycle_info = await self._recycle_env_lease(
                env_lease=env_lease,
                env_id=int(task.env_id) if task.env_id else None,
            )
            if task_context:
                task_context.runtime["env_recycle"] = recycle_info

        if task_context and task.env_id:
            self._release_bound_run_status_after_task(
                env_id=int(task.env_id),
                module_name=module_name,
                context=task_context,
            )

        if env_claim_refresh_required and task.env_id:
            await self._refresh_env_claim_after_task(
                env_id=int(task.env_id),
                module_name=module_name,
                task_id=task.id,
                context=task_context or acquisition_context,
            )

        await self._publish_task_update(task, on_task_update)

        return ExecutionResult(
            task=task,
            task_context=task_context,
            result=result,
            env_id=env_id,
            env_created=env_created,
            env_lease_id=env_lease.id if env_lease else None,
            creation_lifecycle=request.creation_lifecycle,
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

    def _mark_bound_ip_used(self, env: Environment | None) -> None:
        proxy_config = getattr(env, "proxy_config", None)
        entry_id = str(getattr(proxy_config, "ip_entry_id", "") or "").strip()
        if not entry_id:
            return
        try:
            from src.core.rem.ip_pool import get_ip_pool_manager

            get_ip_pool_manager().mark_entry_used(entry_id)
        except Exception as exc:
            logger.warning(f"[ATM] Failed to refresh IP usage time: env_id={getattr(env, 'id', '')} error={exc}")

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
            if await self._is_env_fingerprint_validation_risk(env.id):
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
        if await self._is_env_fingerprint_validation_risk(int(env_id)):
            return False
        return await self._is_env_candidate_authorized(int(env_id), module_name)

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

    async def _get_env_owner_module(self, env_id: int) -> str:
        claim = await get_env_claim(self.rem, int(env_id))
        return claim.owner_module

    async def _assert_env_claimable_by_module(self, env_id: int, module_name: str) -> None:
        claim = await get_env_claim(self.rem, int(env_id))
        owner = claim.owner_module
        if owner and owner != module_name:
            raise RuntimeError(f"环境 {env_id} 已绑定到模块 {owner}，不能被 {module_name} 使用")

    async def _claim_fixed_env_for_module(self, env_id: int, module_name: str, task_id: str) -> None:
        await self._assert_env_claimable_by_module(int(env_id), module_name)
        claim = await get_env_claim(self.rem, int(env_id))
        if not claim.owner_module:
            await set_claimed_env_claim(self.rem, int(env_id), owner_module=module_name, task_id=task_id)

    async def _is_env_candidate_authorized(self, env_id: int, module_name: str) -> bool:
        claim = await get_env_claim(self.rem, int(env_id))
        if claim.owner_module != module_name or claim.state != CLAIM_CLAIMED:
            return False
        try:
            return is_env_bound_by_module(int(env_id), module_name, module_service=self.mms)
        except Exception as exc:
            logger.warning(
                f"[ATM] Candidate env {env_id} binding check failed for module {module_name}: {exc}"
            )
            return False

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
        env_claim_refresh_required: bool,
        acquisition_context: TaskContext,
        module_name: str,
        on_task_update: TaskUpdateCallback | None,
    ) -> None:
        if env_lease:
            try:
                await self._recycle_env_lease(env_lease=env_lease, env_id=env_id)
            except Exception as release_error:
                logger.error(
                    f"[ATM] Task {task.id} failed to release lease during acquisition error: {release_error}"
                )

        elif env_created and env_id is not None:
            try:
                await self._recycle_created_env_without_lease(env_id=int(env_id))
            except Exception as reset_error:
                logger.error(
                    f"[ATM] Task {task.id} failed to clean env during acquisition error: {reset_error}"
                )

        if env_claim_refresh_required and env_id is not None:
            try:
                await self._refresh_env_claim_after_task(
                    env_id=int(env_id),
                    module_name=module_name,
                    task_id=task.id,
                    context=acquisition_context,
                )
            except Exception as claim_error:
                logger.warning(f"[ATM] Task {task.id} failed to refresh env claim: {claim_error}")

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
                        task_context.runtime["_module_cancel_reason"] = "timed_out"
                        await self._cancel_asyncio_task(module_task)
                        raise asyncio.TimeoutError
                    wait_timeout = min(wait_timeout, remaining)

                try:
                    return await asyncio.wait_for(asyncio.shield(module_task), timeout=wait_timeout)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError as exc:
                    if task_context.should_stop() or self._is_stop_requested(is_stop_requested):
                        task_context.runtime["_module_cancel_reason"] = "cancelled"
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
            task_context.runtime["_module_cancel_reason"] = "cancelled"
            raise TaskStopRequested("Job paused during execution")

    def _normalize_task_result(self, result: Any) -> TaskResult:
        if isinstance(result, TaskResult):
            return result
        if result is None:
            return TaskResult.ok()
        if isinstance(result, dict):
            return TaskResult.ok(message=str(result), data=result)
        return TaskResult.ok(message=str(result), data={"value": result})

    def _record_runtime_outcome(
        self,
        task_context: TaskContext,
        task: Task,
        result: TaskResult | None,
    ) -> None:
        if task.status != TaskStatus.PENDING:
            task.waiting_since = None
        task_context.runtime["final_status"] = task.status.value
        task_context.runtime["task_error"] = task.error
        if result:
            task_context.runtime["task_result"] = result.to_dict()

    async def _await_env_recycle_step(self, label: str, operation: Awaitable[Any]) -> Any:
        started_at = time.monotonic()
        try:
            result = await asyncio.wait_for(
                operation,
                timeout=self._env_recycle_timeout_seconds,
            )
            logger.debug(
                f"[ATM] Env recycle step finished: step={label} "
                f"budget={self._env_recycle_timeout_seconds:.1f}s "
                f"duration={time.monotonic() - started_at:.3f}s"
            )
            return result
        except asyncio.TimeoutError as exc:
            logger.error(
                f"[ATM] Env recycle step timeout: step={label} "
                f"budget={self._env_recycle_timeout_seconds:.1f}s "
                f"duration={time.monotonic() - started_at:.3f}s"
            )
            raise TimeoutError(
                f"{label} timed out after {self._env_recycle_timeout_seconds:.1f}s"
            ) from exc

    async def _recycle_env_lease(
        self,
        *,
        env_lease: EnvLease,
        env_id: int | None,
    ) -> dict[str, Any]:
        info = {
            "action": "recycle",
            "env_id": env_id,
            "success": False,
        }
        logger.info(
            f"[ATM] Recycling env after task: env_id={env_id} "
            f"budget={self._env_recycle_timeout_seconds:.1f}s"
        )
        try:
            info["success"] = await self._await_env_recycle_step(
                "release",
                self.rem.release(env_lease),
            )
            logger.info(
                f"[ATM] Env recycle finished: env_id={env_id} success={info['success']}"
            )
            return info
        except Exception as e:
            logger.error(f"[ATM] Failed to recycle env {env_id}: {e}")
            info["error"] = str(e)
            return info

    def _task_log_id(self, task_context: TaskContext) -> str:
        runtime = getattr(task_context, "runtime", {}) or {}
        return str(runtime.get("task_id") or runtime.get("job_id") or task_context.task_name)

    async def _recycle_created_env_without_lease(
        self,
        *,
        env_id: int,
    ) -> None:
        env = await self._await_env_recycle_step(
            "get_env",
            self.rem.get_env(env_id),
        )
        if env:
            await self._await_env_recycle_step(
                "recycle_env",
                self.rem.recycle_env(env),
            )

    async def _refresh_env_claim_after_task(
        self,
        *,
        env_id: int,
        module_name: str,
        task_id: str,
        context: TaskContext,
    ) -> None:
        claim = await refresh_env_claim_after_task(
            self.rem,
            env_id,
            module_name=module_name,
            task_id=task_id,
            module_service=self.mms,
            context=context,
        )
        logger.info(
            f"[ATM] Env claim refreshed after task: env_id={env_id} "
            f"module={module_name} state={claim.state}"
        )

    def _release_bound_run_status_after_task(
        self,
        *,
        env_id: int,
        module_name: str,
        context: TaskContext,
    ) -> None:
        released = release_bound_run_status_after_task(
            module_name,
            env_id,
            context=context,
            module_service=self.mms,
        )
        if released:
            logger.info(
                f"[ATM] Released bound run_status after task: "
                f"env_id={env_id} module={module_name} records={released}"
            )
