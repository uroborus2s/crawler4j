import importlib
import inspect
from pathlib import Path
from typing import Any

from crawler4j_sdk import EnvSelectorInfo
from crawler4j_contracts import TaskContext, TaskResult
from src.core.foundation.logging import logger
from src.core.mms.module_loader import load_root_module_from_path
from src.core.mms.models import ModuleInfo, ModuleSource
from src.core.mms.registry import get_module_registry


class ModuleService:
    """模块服务。

    负责模块的执行和生命周期管理。
    """

    def __init__(self):
        self.registry = get_module_registry()

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

        if not module_info.path:
            raise ValueError(f"Module '{module_name}' has no valid path")
        return module_info

    def _load_module(
        self,
        module_name: str,
        context: TaskContext | None = None,
        *,
        force_reload: bool = False,
    ):
        """加载模块并返回 Python module 对象。"""
        module_info = self._get_module_info(module_name)

        force_reload = force_reload or self._should_force_reload(module_info.name, context)
        try:
            root_module = load_root_module_from_path(
                module_info.name,
                Path(module_info.path),
                force_reload=force_reload,
            )
        except FileNotFoundError as exc:
            raise ValueError(f"Module '{module_name}' is missing __init__.py: {exc.args[0]}") from exc
        except ImportError as exc:
            raise ValueError(f"Module '{module_name}' could not be loaded from: {module_info.path}") from exc

        if module_name == module_info.name:
            return root_module

        if not module_name.startswith(f"{module_info.name}."):
            raise ValueError(
                f"Module request '{module_name}' does not match registered module '{module_info.name}'"
            )

        return importlib.import_module(module_name)

    async def run_module(self, module_name: str, context: TaskContext) -> Any:
        """运行模块主入口。"""
        try:
            module = self._load_module(module_name, context)
            if not hasattr(module, "run"):
                raise ValueError(f"Module '{module_name}' does not export a 'run' function")

            run_func = getattr(module, "run")
            logger.info(f"[MMS] Executing module: {module_name}")

            if inspect.iscoroutinefunction(run_func):
                result = await run_func(context)
            else:
                result = run_func(context)

            if not isinstance(result, TaskResult):
                logger.warning(f"[MMS] Module {module_name} returned non-TaskResult type: {type(result)}")

            return result
        except Exception as e:
            logger.error(f"[MMS] Failed to return module {module_name}: {e}")
            raise e

    async def call_hook(self, module_name: str, hook_name: str, context: TaskContext, *args) -> Any:
        """调用模块中的可选 hook；未实现时返回 None。"""
        module = self._load_module(module_name, context)
        if not hasattr(module, hook_name):
            logger.debug(f"[MMS] Hook not implemented: {module_name}.{hook_name}")
            return None

        hook = getattr(module, hook_name)
        logger.info(f"[MMS] Executing hook: {module_name}.{hook_name}")

        if inspect.iscoroutinefunction(hook):
            return await hook(context, *args)
        return hook(context, *args)

    def call_local_hook(self, module_name: str, hook_name: str, context: TaskContext, *args) -> Any:
        """在同步调用方中执行本地模块 hook。"""
        module = self._load_module(module_name, context)
        if not hasattr(module, hook_name):
            logger.debug(f"[MMS] Hook not implemented: {module_name}.{hook_name}")
            return None

        hook = getattr(module, hook_name)
        logger.info(f"[MMS] Executing local hook: {module_name}.{hook_name}")
        if inspect.iscoroutinefunction(hook):
            raise RuntimeError(
                f"Module hook '{module_name}.{hook_name}' is async and cannot be executed from a sync caller"
            )
        return hook(context, *args)

    def list_env_selectors(self, module_name: str) -> list[EnvSelectorInfo]:
        """列出模块声明的环境选择器。"""
        module_info = self._get_module_info(module_name)
        module = self._load_module(
            module_name,
            force_reload=module_info.source != ModuleSource.BUILTIN,
        )
        assembler = getattr(module, "assembler", None)
        if not assembler or not hasattr(assembler, "list_env_selectors"):
            return []
        return list(assembler.list_env_selectors())


# Global Singleton
_service: ModuleService | None = None


def get_module_service() -> ModuleService:
    global _service
    if _service is None:
        _service = ModuleService()
    return _service
