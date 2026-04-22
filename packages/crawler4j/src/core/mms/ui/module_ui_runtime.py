"""模块宿主页运行时桥接。"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from crawler4j_contracts import TaskContext

from src.core.atm.runtime_capabilities import build_runtime_capabilities
from src.core.foundation.logging import logger
from src.core.mms.models import ModuleInfo, ModuleSource
from src.core.mms.module_loader import load_root_module_from_path
from src.core.mms.service import get_module_service
from src.core.mms.settings_store import get_module_settings_store
from src.core.persistence import get_module_data_store


class ModuleUIRuntimeBridge:
    """复用模块宿主页同步 hook 调用与 DevLink reload 语义。"""

    def __init__(self, module_name: str, module_info: ModuleInfo | None = None):
        self._module_name = module_name
        self._module_info = module_info
        self._mms = get_module_service()
        self._data_store = get_module_data_store()

    def _resolve_module_info(self) -> ModuleInfo | None:
        return self._module_info or self._mms.registry.get_module(self._module_name)

    def _is_dev_link(self) -> bool:
        module = self._resolve_module_info()
        return bool(module and module.source == ModuleSource.DEV_LINK)

    def build_task_context(self, *, runtime_extra: dict[str, Any] | None = None) -> TaskContext:
        config = get_module_settings_store().read_module_settings(self._module_name)
        runtime: dict[str, Any] = {}
        if self._is_dev_link():
            runtime["devel_mode"] = True
        if runtime_extra:
            runtime.update(runtime_extra)

        return TaskContext(
            env_id=0,
            task_name=self._module_name,
            config=config,
            logger=logger,
            tools=build_runtime_capabilities(self._module_name).tools,
            runtime=runtime,
        )

    def call_local_hook(
        self,
        handler_name: str,
        *args: Any,
        runtime_extra: dict[str, Any] | None = None,
    ) -> Any:
        if handler_name == "declare_ui":
            self._data_store.clear_declared_ui(self._module_name)
        context = self.build_task_context(runtime_extra=runtime_extra)
        module = self._resolve_module_info()
        if module and module.path:
            root_module = load_root_module_from_path(
                module.name,
                Path(module.path),
                force_reload=self._is_dev_link(),
            )
            if not hasattr(root_module, handler_name):
                logger.debug(f"[MMS] Hook not implemented: {module.name}.{handler_name}")
                return None
            hook = getattr(root_module, handler_name)
            logger.info(f"[MMS] Executing local hook: {module.name}.{handler_name}")
            if inspect.iscoroutinefunction(hook):
                raise RuntimeError(
                    f"Module hook '{module.name}.{handler_name}' is async and cannot be executed from a sync caller"
                )
            return hook(context, *args)
        return self._mms.call_local_hook(self._module_name, handler_name, context, *args)

    def declare_ui(self) -> Any:
        return self.call_local_hook("declare_ui")
