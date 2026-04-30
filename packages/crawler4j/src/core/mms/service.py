import asyncio
import inspect
import time
from functools import partial
from pathlib import Path
from typing import Any

from crawler4j_contracts import EnvCandidates, TaskContext, TaskOutcome, TaskResult

from src.core.foundation.logging import logger
from src.core.mms.models import ModuleInfo, ModuleSource, ModuleStatus
from src.core.mms.object_container_v2 import ObjectContainerV2
from src.core.mms.registry import get_module_registry
from src.core.mms.runtime_descriptor import (
    ModuleRuntimeDescriptorV2,
    invoke_runtime_callable,
    load_runtime_descriptor_v2,
    normalize_result_payload,
)

ENV_CANDIDATE_EVALUATION_TIMEOUT_SECONDS = 10.0
OBJECT_CLEANUP_TIMEOUT_SECONDS = 30.0


class ModuleService:
    """模块服务。

    负责模块描述发现、执行和生命周期管理。
    """

    def __init__(self):
        self.registry = get_module_registry()
        self._descriptor_cache_v2: dict[str, ModuleRuntimeDescriptorV2] = {}

    def _should_force_reload(self, module_name: str, context: TaskContext | None = None) -> bool:
        if not context or not context.runtime.get("devel_mode", False):
            return False

        reloaded_modules = context.runtime.get("_reloaded_modules")
        if not isinstance(reloaded_modules, dict):
            reloaded_modules = {}
            context.runtime["_reloaded_modules"] = reloaded_modules

        if reloaded_modules.get(module_name):
            return False

        reloaded_modules[module_name] = True
        return True

    def _get_module_info(self, module_name: str) -> ModuleInfo:
        module_root = module_name.split(".")[0]
        module_info = self.registry.get_module(module_name) or self.registry.get_module(module_root)
        if not module_info:
            raise ValueError(f"Module '{module_name}' not found")

        if module_info.status != ModuleStatus.ENABLED:
            detail = module_info.error or f"status={module_info.status.value}"
            raise ValueError(f"Module '{module_info.name}' is not loadable: {detail}")

        if not module_info.path:
            raise ValueError(f"Module '{module_name}' has no valid path")
        return module_info

    def _load_descriptor_v2(
        self,
        module_name: str,
        context: TaskContext | None = None,
        *,
        force_reload: bool = False,
    ) -> ModuleRuntimeDescriptorV2:
        module_info = self._get_module_info(module_name)
        force_reload = force_reload or self._should_force_reload(module_info.name, context)

        if force_reload or module_info.name not in self._descriptor_cache_v2:
            descriptor = load_runtime_descriptor_v2(
                module_info.name,
                Path(module_info.path),
                module_info.manifest,
                force_reload=force_reload or module_info.source == ModuleSource.DEV_LINK,
            )
            self._descriptor_cache_v2[module_info.name] = descriptor

        return self._descriptor_cache_v2[module_info.name]

    def get_runtime_descriptor(
        self,
        module_name: str,
        context: TaskContext | None = None,
        *,
        force_reload: bool = False,
    ) -> ModuleRuntimeDescriptorV2:
        return self._load_descriptor_v2(module_name, context, force_reload=force_reload)

    def get_runtime_descriptor_v2(
        self,
        module_name: str,
        context: TaskContext | None = None,
        *,
        force_reload: bool = False,
    ) -> ModuleRuntimeDescriptorV2:
        return self._load_descriptor_v2(module_name, context, force_reload=force_reload)

    def get_hosted_page_descriptor(
        self,
        module_name: str,
        context: TaskContext | None = None,
        *,
        force_reload: bool = False,
    ) -> ModuleRuntimeDescriptorV2:
        return self._load_descriptor_v2(module_name, context, force_reload=force_reload)

    def resolve_env_candidates(
        self,
        module_name: str,
        context: TaskContext,
        candidates_name: str,
        params: dict[str, Any] | None = None,
    ) -> list[int]:
        """Run a core-native-v2 pure environment candidate provider."""
        descriptor = self._load_descriptor_v2(module_name, context)
        normalized_name = str(candidates_name or "").strip()
        if not normalized_name:
            raise ValueError("环境候选函数不能为空")
        entry = descriptor.env_candidates.get(normalized_name)
        if entry is None:
            raise RuntimeError(f"env_candidates 不存在: {normalized_name}")

        result = self._invoke_env_candidates(entry.target, context, dict(params or {}))
        return self._normalize_env_id_provider_result(result, context, label="env_candidates")

    async def resolve_env_candidates_async(
        self,
        module_name: str,
        context: TaskContext,
        candidates_name: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = ENV_CANDIDATE_EVALUATION_TIMEOUT_SECONDS,
    ) -> list[int]:
        """Run env candidates outside the main async loop with a hard timeout."""

        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(
            None,
            partial(self.resolve_env_candidates, module_name, context, candidates_name, params),
        )
        try:
            if timeout is None or timeout <= 0:
                return await task
            return await asyncio.wait_for(task, timeout=float(timeout))
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"env_candidates 执行超时: {candidates_name} ({timeout:g}s)") from exc

    @staticmethod
    def _invoke_env_candidates(target: Any, context: TaskContext, params: dict[str, Any]) -> Any:
        return ModuleService._invoke_env_id_provider(target, context, params, label="env_candidates")

    def resolve_env_cleanup_candidates(
        self,
        module_name: str,
        context: TaskContext,
        cleanup_name: str,
        params: dict[str, Any] | None = None,
    ) -> list[int]:
        """Run a core-native-v2 pure environment cleanup candidate provider."""
        descriptor = self._load_descriptor_v2(module_name, context)
        normalized_name = str(cleanup_name or "").strip()
        if not normalized_name:
            raise ValueError("环境清理候选函数不能为空")
        entry = descriptor.env_cleanup_candidates.get(normalized_name)
        if entry is None:
            raise RuntimeError(f"env_cleanup_candidates 不存在: {normalized_name}")

        result = self._invoke_env_id_provider(
            entry.target,
            context,
            dict(params or {}),
            label="env_cleanup_candidates",
        )
        return self._normalize_env_id_provider_result(result, context, label="env_cleanup_candidates")

    async def resolve_env_cleanup_candidates_async(
        self,
        module_name: str,
        context: TaskContext,
        cleanup_name: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = ENV_CANDIDATE_EVALUATION_TIMEOUT_SECONDS,
    ) -> list[int]:
        """Run env cleanup candidates outside the main async loop with a hard timeout."""

        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(
            None,
            partial(self.resolve_env_cleanup_candidates, module_name, context, cleanup_name, params),
        )
        try:
            if timeout is None or timeout <= 0:
                return await task
            return await asyncio.wait_for(task, timeout=float(timeout))
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"env_cleanup_candidates 执行超时: {cleanup_name} ({timeout:g}s)") from exc

    @staticmethod
    def _invoke_env_id_provider(
        target: Any,
        context: TaskContext,
        params: dict[str, Any],
        *,
        label: str,
    ) -> Any:
        if inspect.iscoroutinefunction(target):
            raise RuntimeError(f"{label} 必须是同步纯函数")
        signature = inspect.signature(target)
        kwargs: dict[str, Any] = {}
        for parameter in signature.parameters.values():
            if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
                raise RuntimeError(f"{label} 不支持仅位置参数")
            if parameter.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
                raise RuntimeError(f"{label} 不支持 *args 或 **kwargs")
            if parameter.name in {"ctx", "context"}:
                kwargs[parameter.name] = context
            elif parameter.name == "params":
                kwargs[parameter.name] = params
            elif parameter.default is inspect.Parameter.empty:
                raise RuntimeError(f"{label} 包含不支持的必填参数: {parameter.name}")
        return target(**kwargs)

    @staticmethod
    def _normalize_env_id_provider_result(result: Any, context: TaskContext, *, label: str) -> list[int]:
        if isinstance(result, EnvCandidates):
            return result.list(context)
        if isinstance(result, (list, tuple, set)):
            return [int(item) for item in result]
        raise RuntimeError(f"{label} 必须返回 EnvCandidates 或 env_id 列表")

    @staticmethod
    def _resolve_v2_workflow_name(context: TaskContext, descriptor: ModuleRuntimeDescriptorV2) -> str:
        runtime = getattr(context, "runtime", None)
        if isinstance(runtime, dict):
            workflow_name = runtime.get("workflow")
            if isinstance(workflow_name, str) and workflow_name.strip():
                return workflow_name.strip()
        if len(descriptor.workflows) == 1:
            return next(iter(descriptor.workflows))
        if "main_workflow" in descriptor.workflows:
            return "main_workflow"
        raise ValueError("Workflow not specified for core-native-v2 module")

    @staticmethod
    def _runtime_mapping(context: TaskContext, key: str) -> dict[str, Any]:
        runtime = getattr(context, "runtime", None)
        value = runtime.get(key) if isinstance(runtime, dict) else None
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError(f"context.runtime[{key}] must be a mapping")
        return dict(value)

    async def _run_v2_workflow(self, descriptor: ModuleRuntimeDescriptorV2, context: TaskContext) -> TaskResult:
        workflow_name = self._resolve_v2_workflow_name(context, descriptor)
        started_at = time.monotonic()
        container = ObjectContainerV2(
            descriptor,
            workflow_name,
            object_bindings=self._runtime_mapping(context, "object_bindings"),
            object_params=self._runtime_mapping(context, "object_params"),
        )
        previous_page_action_executor = getattr(context, "_page_action_executor", None)
        outcome: TaskOutcome | None = None

        async def _run_page_action(action_name: str, action_context: TaskContext, **kwargs: Any) -> Any:
            page_action = descriptor.page_actions.get(str(action_name or "").strip())
            if page_action is None:
                raise RuntimeError(f"page_action 不存在: {action_name}")
            return await invoke_runtime_callable(page_action.target, action_context, **kwargs)

        try:
            context._page_action_executor = _run_page_action
            workflow = container.build_workflow()
            run = getattr(workflow, "run", None)
            if run is None:
                raise ValueError(f"Workflow has no run method: {workflow_name}")
            result = await invoke_runtime_callable(run, context)
            normalized_result = normalize_result_payload(result, context)
            outcome = self._outcome_from_result(normalized_result, started_at=started_at)
            return normalized_result
        except asyncio.CancelledError as exc:
            outcome = self._outcome_from_cancelled(context, exc, started_at=started_at)
            raise
        except Exception as exc:
            outcome = self._outcome_from_exception(exc, started_at=started_at)
            raise
        finally:
            context._page_action_executor = previous_page_action_executor
            await container.cleanup(
                context,
                outcome or self._outcome_from_exception(
                    RuntimeError("workflow exited before outcome was resolved"),
                    started_at=started_at,
                ),
                timeout_seconds=OBJECT_CLEANUP_TIMEOUT_SECONDS,
            )

    @staticmethod
    def _duration_since(*, started_at: float) -> float:
        return max(time.monotonic() - started_at, 0.0)

    def _outcome_from_result(self, result: TaskResult, *, started_at: float) -> TaskOutcome:
        return TaskOutcome(
            status="succeeded" if result.success else "failed",
            result=result,
            error=result.error or "",
            error_type="",
            duration_seconds=self._duration_since(started_at=started_at),
        )

    def _outcome_from_exception(self, exc: Exception, *, started_at: float) -> TaskOutcome:
        return TaskOutcome(
            status="failed",
            error=str(exc),
            error_type=exc.__class__.__name__,
            duration_seconds=self._duration_since(started_at=started_at),
        )

    def _outcome_from_cancelled(
        self,
        context: TaskContext,
        exc: asyncio.CancelledError,
        *,
        started_at: float,
    ) -> TaskOutcome:
        cancel_reason = str(context.runtime.get("_module_cancel_reason") or "").strip()
        status = "timed_out" if cancel_reason == "timed_out" else "cancelled"
        return TaskOutcome(
            status=status,
            error=str(exc),
            error_type=exc.__class__.__name__,
            duration_seconds=self._duration_since(started_at=started_at),
        )

    async def run_module(self, module_name: str, context: TaskContext) -> Any:
        """运行模块默认工作流或任务。"""
        try:
            module_info = self._get_module_info(module_name)
            if str(module_info.manifest.runtime_api or "").strip() == "core-native-v2":
                descriptor_v2 = self._load_descriptor_v2(module_name, context)
                logger.info(f"[MMS] Executing v2 module: {module_name}")
                return await self._run_v2_workflow(descriptor_v2, context)

            raise ValueError("Only core-native-v2 modules are executable in crawler4j 0.4.0")
        except Exception as e:
            logger.error(f"[MMS] Failed to execute module {module_name}: {e}")
            raise e

# Global Singleton
_service: ModuleService | None = None


def get_module_service() -> ModuleService:
    global _service
    if _service is None:
        _service = ModuleService()
    return _service
