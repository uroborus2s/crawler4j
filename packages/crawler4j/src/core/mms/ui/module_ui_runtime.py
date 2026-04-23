"""模块宿主页运行时桥接。"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from crawler4j_contracts import TaskContext

from src.core.atm.runtime_capabilities import (
    HostedUIDeclarationBuffer,
    RUNTIME_SURFACE_FULL,
    RUNTIME_SURFACE_HOSTED_UI_DECLARE,
    RUNTIME_SURFACE_HOSTED_UI_READONLY,
    build_runtime_capabilities,
)
from src.core.foundation.logging import logger
from src.core.mms.models import ModuleInfo, ModuleSource
from src.core.mms.module_loader import load_root_module_from_path
from src.core.mms.service import get_module_service
from src.core.mms.settings_store import get_module_settings_store


@dataclass
class _HookSession:
    context: TaskContext
    root_module: Any | None


class ModuleUIRuntimeBridge:
    """复用模块宿主页同步 hook 调用与 DevLink reload 语义。"""

    def __init__(self, module_name: str, module_info: ModuleInfo | None = None):
        self._module_name = module_name
        self._module_info = module_info
        self._mms = get_module_service()
        self._active_session: _HookSession | None = None
        self._declared_page_schemas: dict[str, dict[str, Any]] = {}

    def _resolve_module_info(self) -> ModuleInfo | None:
        return self._module_info or self._mms.registry.get_module(self._module_name)

    def _is_dev_link(self) -> bool:
        module = self._resolve_module_info()
        return bool(module and module.source == ModuleSource.DEV_LINK)

    def build_task_context(
        self,
        *,
        runtime_extra: dict[str, Any] | None = None,
        ui_declaration_buffer: HostedUIDeclarationBuffer | None = None,
        capability_surface: str = RUNTIME_SURFACE_FULL,
        declared_page_schemas: dict[str, dict[str, Any]] | None = None,
    ) -> TaskContext:
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
            tools=build_runtime_capabilities(
                self._module_name,
                ui_declaration_buffer=ui_declaration_buffer,
                surface=capability_surface,
                declared_page_schemas=declared_page_schemas,
            ).tools,
            runtime=runtime,
        )

    def _load_root_module(self, *, force_reload: bool) -> Any | None:
        module = self._resolve_module_info()
        if not module or not module.path:
            return None
        return load_root_module_from_path(
            module.name,
            Path(module.path),
            force_reload=force_reload,
        )

    def _create_session(
        self,
        *,
        force_reload: bool,
        ui_declaration_buffer: HostedUIDeclarationBuffer | None = None,
        capability_surface: str = RUNTIME_SURFACE_FULL,
        declared_page_schemas: dict[str, dict[str, Any]] | None = None,
    ) -> _HookSession:
        return _HookSession(
            context=self.build_task_context(
                ui_declaration_buffer=ui_declaration_buffer,
                capability_surface=capability_surface,
                declared_page_schemas=declared_page_schemas,
            ),
            root_module=self._load_root_module(force_reload=force_reload),
        )

    def _set_context_tools(
        self,
        context: TaskContext,
        *,
        ui_declaration_buffer: HostedUIDeclarationBuffer | None = None,
        capability_surface: str = RUNTIME_SURFACE_FULL,
        declared_page_schemas: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        context.tools = build_runtime_capabilities(
            self._module_name,
            ui_declaration_buffer=ui_declaration_buffer,
            surface=capability_surface,
            declared_page_schemas=declared_page_schemas,
        ).tools

    def _run_hook(
        self,
        session: _HookSession,
        handler_name: str,
        *args: Any,
        runtime_extra: dict[str, Any] | None = None,
    ) -> Any:
        runtime = session.context.runtime
        previous_runtime: dict[str, Any] = {}
        missing_keys: set[str] = set()
        if runtime_extra:
            for key, value in runtime_extra.items():
                if key in runtime:
                    previous_runtime[key] = runtime[key]
                else:
                    missing_keys.add(key)
                runtime[key] = value

        try:
            module = self._resolve_module_info()
            if module and module.path:
                root_module = session.root_module
                if root_module is None:
                    raise RuntimeError(f"Module '{module.name}' has no loaded runtime module")
                if not hasattr(root_module, handler_name):
                    logger.debug(f"[MMS] Hook not implemented: {module.name}.{handler_name}")
                    return None
                hook = getattr(root_module, handler_name)
                logger.info(f"[MMS] Executing local hook: {module.name}.{handler_name}")
                if inspect.iscoroutinefunction(hook):
                    raise RuntimeError(
                        f"Module hook '{module.name}.{handler_name}' is async and cannot be executed from a sync caller"
                    )
                return hook(session.context, *args)

            return self._mms.call_local_hook(self._module_name, handler_name, session.context, *args)
        finally:
            for key in missing_keys:
                runtime.pop(key, None)
            runtime.update(previous_runtime)

    def call_local_hook(
        self,
        handler_name: str,
        *args: Any,
        runtime_extra: dict[str, Any] | None = None,
        capability_surface: str | None = None,
    ) -> Any:
        if capability_surface is None:
            capability_surface = (
                RUNTIME_SURFACE_HOSTED_UI_DECLARE
                if handler_name == "declare_ui"
                else RUNTIME_SURFACE_HOSTED_UI_READONLY
            )
        if handler_name == "declare_ui":
            buffer = HostedUIDeclarationBuffer()
            session = self._create_session(
                force_reload=self._is_dev_link(),
                ui_declaration_buffer=buffer,
                capability_surface=capability_surface,
            )
            try:
                result = self._run_hook(session, handler_name, *args, runtime_extra=runtime_extra)
                self._declared_page_schemas = {
                    str(page_id): dict(schema)
                    for page_id, schema in buffer.page_schemas.items()
                    if isinstance(schema, dict)
                }
                self._set_context_tools(
                    session.context,
                    capability_surface=RUNTIME_SURFACE_HOSTED_UI_READONLY,
                    declared_page_schemas=self._declared_page_schemas,
                )
            finally:
                buffer.seal()
            self._active_session = session
            return result

        session = self._active_session
        if session is None:
            session = self._create_session(
                force_reload=self._is_dev_link(),
                capability_surface=capability_surface,
                declared_page_schemas=self._declared_page_schemas or None,
            )
        else:
            self._set_context_tools(
                session.context,
                capability_surface=capability_surface,
                declared_page_schemas=self._declared_page_schemas or None,
            )
        try:
            return self._run_hook(session, handler_name, *args, runtime_extra=runtime_extra)
        finally:
            if self._active_session is session:
                self._active_session = None

    def get_declared_page(self, page_id: str) -> dict[str, Any]:
        return dict(self._declared_page_schemas.get(str(page_id or "").strip(), {}))

    def declare_ui(
        self,
        *,
        page_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        runtime_extra: dict[str, Any] = {}
        if page_id:
            runtime_extra["page_id"] = page_id
        if params is not None:
            runtime_extra["params"] = dict(params)
        return self.call_local_hook(
            "declare_ui",
            runtime_extra=runtime_extra or None,
            capability_surface=RUNTIME_SURFACE_HOSTED_UI_DECLARE,
        )

    def call_page_handler(
        self,
        handler_name: str,
        page_id: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        normalized_params = dict(params) if isinstance(params, dict) else None
        return self.call_local_hook(
            handler_name,
            page_id,
            normalized_params,
            runtime_extra={
                "page_id": page_id,
                "params": normalized_params,
            },
            capability_surface=RUNTIME_SURFACE_HOSTED_UI_READONLY,
        )

    def call_query_handler(
        self,
        handler_name: str,
        table_id: str,
        query: dict[str, Any] | None,
        params: dict[str, Any] | None = None,
        *,
        page_id: str,
    ) -> Any:
        normalized_query = dict(query or {})
        normalized_params = dict(params) if isinstance(params, dict) else None
        return self.call_local_hook(
            handler_name,
            table_id,
            normalized_query,
            normalized_params,
            runtime_extra={
                "page_id": page_id,
                "table_id": table_id,
                "params": normalized_params,
            },
            capability_surface=RUNTIME_SURFACE_HOSTED_UI_READONLY,
        )
