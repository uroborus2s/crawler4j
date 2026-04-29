import inspect
from pathlib import Path
from typing import Any

from crawler4j_contracts import EnvSelectorSpec, TaskContext, TaskResult

from src.core.foundation.logging import logger
from src.core.mms.models import ModuleInfo, ModuleSource, ModuleStatus
from src.core.mms.registry import get_module_registry
from src.core.mms.runtime_descriptor import (
    ModuleRuntimeDescriptor,
    TaskRuntimeEntry,
    WorkflowRuntimeEntry,
    invoke_runtime_callable,
    load_runtime_descriptor,
    normalize_result_payload,
)


class ModuleService:
    """模块服务。

    负责模块描述发现、执行和生命周期管理。
    """

    def __init__(self):
        self.registry = get_module_registry()
        self._descriptor_cache: dict[str, ModuleRuntimeDescriptor] = {}

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

    @staticmethod
    def _inject_manifest_runtime(module_info: ModuleInfo, context: TaskContext | None) -> None:
        if context is None:
            return
        if not isinstance(context.runtime, dict):
            context.runtime = {}
        context.runtime["declared_resource_pools"] = [
            pool.to_dict()
            for pool in getattr(module_info.manifest, "resource_pools", [])
        ]

    def _load_descriptor(
        self,
        module_name: str,
        context: TaskContext | None = None,
        *,
        force_reload: bool = False,
    ) -> ModuleRuntimeDescriptor:
        module_info = self._get_module_info(module_name)
        self._inject_manifest_runtime(module_info, context)
        force_reload = force_reload or self._should_force_reload(module_info.name, context)

        if force_reload or module_info.name not in self._descriptor_cache:
            descriptor = load_runtime_descriptor(
                module_info.name,
                Path(module_info.path),
                module_info.manifest,
                force_reload=force_reload or module_info.source != ModuleSource.BUILTIN,
            )
            self._descriptor_cache[module_info.name] = descriptor

        return self._descriptor_cache[module_info.name]

    def get_runtime_descriptor(
        self,
        module_name: str,
        context: TaskContext | None = None,
        *,
        force_reload: bool = False,
    ) -> ModuleRuntimeDescriptor:
        return self._load_descriptor(module_name, context, force_reload=force_reload)

    @staticmethod
    def _resolve_workflow_name(context: TaskContext, default_workflow: str) -> str:
        runtime = getattr(context, "runtime", None)
        if isinstance(runtime, dict):
            workflow_name = runtime.get("workflow")
            if isinstance(workflow_name, str) and workflow_name.strip():
                return workflow_name
        return default_workflow

    async def _run_task_entry(self, task: TaskRuntimeEntry, context: TaskContext) -> TaskResult:
        result = await invoke_runtime_callable(task.execute, context)
        return normalize_result_payload(result, context)

    async def _run_workflow_entry(
        self,
        descriptor: ModuleRuntimeDescriptor,
        workflow: WorkflowRuntimeEntry,
        context: TaskContext,
    ) -> TaskResult:
        context._subtask_executor = lambda task_name, ctx: self._run_subtask(descriptor, task_name, ctx)
        result = await invoke_runtime_callable(workflow.run, context)
        return normalize_result_payload(result, context)

    async def _run_subtask(
        self,
        descriptor: ModuleRuntimeDescriptor,
        task_name: str,
        context: TaskContext,
    ) -> TaskResult:
        task = descriptor.tasks.get(task_name)
        if not task:
            raise ValueError(f"Unknown subtask: {task_name}")
        return await self._run_task_entry(task, context)

    async def run_module(self, module_name: str, context: TaskContext) -> Any:
        """运行模块默认工作流或任务。"""
        try:
            descriptor = self._load_descriptor(module_name, context)
            workflow_name = self._resolve_workflow_name(context, descriptor.default_workflow)
            logger.info(f"[MMS] Executing module: {module_name} workflow={workflow_name}")

            workflow = descriptor.workflows.get(workflow_name)
            if workflow:
                return await self._run_workflow_entry(descriptor, workflow, context)

            raise ValueError(f"Workflow not found: {workflow_name or '<empty>'}")
        except Exception as e:
            logger.error(f"[MMS] Failed to execute module {module_name}: {e}")
            raise e

    async def call_hook(self, module_name: str, hook_name: str, context: TaskContext, *args) -> Any:
        """调用模块中的可选 hook；未实现时返回 None。"""
        descriptor = self._load_descriptor(module_name, context)
        hook = descriptor.hooks.get(hook_name)
        if not hook:
            logger.debug(f"[MMS] Hook not implemented: {module_name}.{hook_name}")
            return None

        logger.info(f"[MMS] Executing hook: {module_name}.{hook_name}")
        return await invoke_runtime_callable(hook, context, *args)

    def call_local_hook(self, module_name: str, hook_name: str, context: TaskContext, *args) -> Any:
        """在同步调用方中执行本地模块 hook。"""
        descriptor = self._load_descriptor(module_name, context)
        hook = descriptor.hooks.get(hook_name)
        if not hook:
            logger.debug(f"[MMS] Hook not implemented: {module_name}.{hook_name}")
            return None

        logger.info(f"[MMS] Executing local hook: {module_name}.{hook_name}")
        if inspect.iscoroutinefunction(hook):
            raise RuntimeError(
                f"Module hook '{module_name}.{hook_name}' is async and cannot be executed from a sync caller"
            )
        return hook(context, *args)

    async def run_env_selector(
        self,
        module_name: str,
        selector_name: str,
        context: TaskContext,
        candidates: list[Any],
    ) -> Any:
        descriptor = self._load_descriptor(module_name, context)
        selector = descriptor.env_selectors.get(selector_name)
        if not selector:
            raise ValueError(f"Env selector not found: {selector_name}")
        logger.info(f"[MMS] Executing env selector: {module_name}.{selector_name}")
        return await invoke_runtime_callable(selector.select, context, candidates)

    def list_env_selectors(self, module_name: str) -> list[EnvSelectorSpec]:
        """列出模块声明的环境选择器。"""
        descriptor = self._load_descriptor(module_name)
        return [
            descriptor.env_selectors[name].spec
            for name in sorted(descriptor.env_selectors)
        ]


# Global Singleton
_service: ModuleService | None = None


def get_module_service() -> ModuleService:
    global _service
    if _service is None:
        _service = ModuleService()
    return _service
