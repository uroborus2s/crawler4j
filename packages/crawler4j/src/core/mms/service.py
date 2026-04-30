from pathlib import Path
from typing import Any

from crawler4j_contracts import TaskContext, TaskResult

from src.core.foundation.logging import logger
from src.core.mms.models import ModuleInfo, ModuleSource, ModuleStatus
from src.core.mms.object_container_v2 import ObjectContainerV2
from src.core.mms.registry import get_module_registry
from src.core.mms.runtime_descriptor import (
    ModuleRuntimeDescriptor,
    ModuleRuntimeDescriptorV2,
    invoke_runtime_callable,
    load_hosted_page_descriptor,
    load_runtime_descriptor_v2,
    normalize_result_payload,
)


class ModuleService:
    """模块服务。

    负责模块描述发现、执行和生命周期管理。
    """

    def __init__(self):
        self.registry = get_module_registry()
        self._page_descriptor_cache: dict[str, ModuleRuntimeDescriptor] = {}
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

    def _load_hosted_page_descriptor(
        self,
        module_name: str,
        context: TaskContext | None = None,
        *,
        force_reload: bool = False,
    ) -> ModuleRuntimeDescriptor:
        module_info = self._get_module_info(module_name)
        force_reload = force_reload or self._should_force_reload(module_info.name, context)

        if force_reload or module_info.name not in self._page_descriptor_cache:
            descriptor = load_hosted_page_descriptor(
                module_info.name,
                Path(module_info.path),
                force_reload=force_reload or module_info.source != ModuleSource.BUILTIN,
            )
            self._page_descriptor_cache[module_info.name] = descriptor

        return self._page_descriptor_cache[module_info.name]

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
                force_reload=force_reload or module_info.source != ModuleSource.BUILTIN,
            )
            self._descriptor_cache_v2[module_info.name] = descriptor

        return self._descriptor_cache_v2[module_info.name]

    def get_runtime_descriptor(
        self,
        module_name: str,
        context: TaskContext | None = None,
        *,
        force_reload: bool = False,
    ) -> ModuleRuntimeDescriptor:
        return self._load_hosted_page_descriptor(module_name, context, force_reload=force_reload)

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
    ) -> ModuleRuntimeDescriptor:
        return self._load_hosted_page_descriptor(module_name, context, force_reload=force_reload)

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
        container = ObjectContainerV2(
            descriptor,
            workflow_name,
            object_bindings=self._runtime_mapping(context, "object_bindings"),
            object_params=self._runtime_mapping(context, "object_params"),
        )
        workflow = container.build_workflow()
        run = getattr(workflow, "run", None)
        if run is None:
            raise ValueError(f"Workflow has no run method: {workflow_name}")
        result = await invoke_runtime_callable(run, context)
        return normalize_result_payload(result, context)

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

    async def call_hook(self, module_name: str, hook_name: str, context: TaskContext, *args) -> Any:
        """调用模块中的可选 hook；未实现时返回 None。"""
        module_info = self._get_module_info(module_name)
        if str(module_info.manifest.runtime_api or "").strip() == "core-native-v2":
            logger.debug(f"[MMS] core-native-v2 does not use legacy hook: {module_name}.{hook_name}")
            return None
        raise ValueError("Legacy module hooks are removed in crawler4j 0.4.0")

    def call_local_hook(self, module_name: str, hook_name: str, context: TaskContext, *args) -> Any:
        """在同步调用方中执行本地模块 hook。"""
        module_info = self._get_module_info(module_name)
        if str(module_info.manifest.runtime_api or "").strip() == "core-native-v2":
            logger.debug(f"[MMS] core-native-v2 does not use legacy local hook: {module_name}.{hook_name}")
            return None
        raise ValueError("Legacy module hooks are removed in crawler4j 0.4.0")

    async def run_env_selector(
        self,
        module_name: str,
        selector_name: str,
        context: TaskContext,
        candidates: list[Any],
    ) -> Any:
        module_info = self._get_module_info(module_name)
        if str(module_info.manifest.runtime_api or "").strip() == "core-native-v2":
            raise ValueError("core-native-v2 不支持旧 env_selector 入口")
        raise ValueError("Legacy env_selector entries are removed in crawler4j 0.4.0")

    def list_env_selectors(self, module_name: str) -> list[Any]:
        """列出模块声明的环境选择器。"""
        module_info = self._get_module_info(module_name)
        if str(module_info.manifest.runtime_api or "").strip() == "core-native-v2":
            return []
        raise ValueError("Legacy env_selector entries are removed in crawler4j 0.4.0")


# Global Singleton
_service: ModuleService | None = None


def get_module_service() -> ModuleService:
    global _service
    if _service is None:
        _service = ModuleService()
    return _service
