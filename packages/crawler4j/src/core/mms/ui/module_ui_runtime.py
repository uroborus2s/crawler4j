"""模块宿主页运行时桥接。"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from dataclasses import dataclass
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
from src.core.mms.runtime_descriptor import ModuleRuntimeDescriptor, PageRuntimeEntry
from src.core.mms.service import get_module_service
from src.core.mms.settings_store import get_module_settings_store


@dataclass
class _HookSession:
    context: TaskContext
    descriptor: ModuleRuntimeDescriptor


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

        capabilities = build_runtime_capabilities(
            self._module_name,
            ui_declaration_buffer=ui_declaration_buffer,
            surface=capability_surface,
            declared_page_schemas=declared_page_schemas,
        )
        return TaskContext(
            env_id=0,
            task_name=self._module_name,
            config=config,
            logger=logger,
            tools=capabilities.tools,
            db=capabilities.db,
            runtime=runtime,
        )

    def _create_session(
        self,
        *,
        force_reload: bool,
        ui_declaration_buffer: HostedUIDeclarationBuffer | None = None,
        capability_surface: str = RUNTIME_SURFACE_FULL,
        declared_page_schemas: dict[str, dict[str, Any]] | None = None,
    ) -> _HookSession:
        context = self.build_task_context(
            ui_declaration_buffer=ui_declaration_buffer,
            capability_surface=capability_surface,
            declared_page_schemas=declared_page_schemas,
        )
        descriptor = self._mms.get_runtime_descriptor(
            self._module_name,
            context,
            force_reload=force_reload,
        )
        return _HookSession(context=context, descriptor=descriptor)

    def _set_context_tools(
        self,
        context: TaskContext,
        *,
        ui_declaration_buffer: HostedUIDeclarationBuffer | None = None,
        capability_surface: str = RUNTIME_SURFACE_FULL,
        declared_page_schemas: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        capabilities = build_runtime_capabilities(
            self._module_name,
            ui_declaration_buffer=ui_declaration_buffer,
            surface=capability_surface,
            declared_page_schemas=declared_page_schemas,
        )
        context.tools = capabilities.tools
        context.db = capabilities.db

    @contextmanager
    def _override_runtime(self, context: TaskContext, runtime_extra: dict[str, Any] | None = None):
        runtime = context.runtime
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
            yield
        finally:
            for key in missing_keys:
                runtime.pop(key, None)
            runtime.update(previous_runtime)

    def _run_sync_callable(
        self,
        func: Any,
        *,
        owner: str,
        context: TaskContext,
        args: tuple[Any, ...],
    ) -> Any:
        if func is None or not callable(func):
            raise RuntimeError(f"{owner} 未定义或不可调用")
        if inspect.iscoroutinefunction(func):
            raise RuntimeError(f"{owner} 是 async，不能从同步宿主页调用")
        return func(context, *args)

    def _resolve_page_entry(self, session: _HookSession, page_id: str) -> PageRuntimeEntry:
        page = session.descriptor.pages.get(page_id)
        if not page:
            raise RuntimeError(f"未找到宿主页声明: {page_id}")
        return page

    def call_local_hook(
        self,
        handler_name: str,
        *args: Any,
        runtime_extra: dict[str, Any] | None = None,
        capability_surface: str | None = None,
    ) -> Any:
        if capability_surface is None:
            capability_surface = RUNTIME_SURFACE_HOSTED_UI_READONLY
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
            hook = session.descriptor.hooks.get(handler_name)
            with self._override_runtime(session.context, runtime_extra):
                return self._run_sync_callable(
                    hook,
                    owner=f"{self._module_name}.hooks.{handler_name}",
                    context=session.context,
                    args=args,
                )
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

        buffer = HostedUIDeclarationBuffer()
        session = self._create_session(
            force_reload=self._is_dev_link(),
            ui_declaration_buffer=buffer,
            capability_surface=RUNTIME_SURFACE_HOSTED_UI_DECLARE,
        )
        try:
            with self._override_runtime(session.context, runtime_extra or None):
                self._declared_page_schemas = {
                    page_id: dict(page.spec.schema)
                    for page_id, page in session.descriptor.pages.items()
                }
                self._set_context_tools(
                    session.context,
                    capability_surface=RUNTIME_SURFACE_HOSTED_UI_READONLY,
                    declared_page_schemas=self._declared_page_schemas,
                )
        finally:
            buffer.seal()
        self._active_session = session
        return None

    def call_page_handler(
        self,
        handler_name: str,
        page_id: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        normalized_params = dict(params) if isinstance(params, dict) else None
        session = self._active_session
        if session is None:
            session = self._create_session(
                force_reload=self._is_dev_link(),
                capability_surface=RUNTIME_SURFACE_HOSTED_UI_READONLY,
                declared_page_schemas=self._declared_page_schemas or None,
            )
        try:
            page = self._resolve_page_entry(session, page_id)
            handler = page.get_handler(handler_name)
            with self._override_runtime(
                session.context,
                {
                    "page_id": page_id,
                    "params": normalized_params,
                },
            ):
                return self._run_sync_callable(
                    handler,
                    owner=f"{page.module_name}.{handler_name}",
                    context=session.context,
                    args=(page_id, normalized_params),
                )
        finally:
            if self._active_session is session:
                self._active_session = None

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
        session = self._active_session
        if session is None:
            session = self._create_session(
                force_reload=self._is_dev_link(),
                capability_surface=RUNTIME_SURFACE_HOSTED_UI_READONLY,
                declared_page_schemas=self._declared_page_schemas or None,
            )
        try:
            page = self._resolve_page_entry(session, page_id)
            handler = page.get_handler(handler_name)
            with self._override_runtime(
                session.context,
                {
                    "page_id": page_id,
                    "table_id": table_id,
                    "params": normalized_params,
                },
            ):
                return self._run_sync_callable(
                    handler,
                    owner=f"{page.module_name}.{handler_name}",
                    context=session.context,
                    args=(table_id, normalized_query, normalized_params),
                )
        finally:
            if self._active_session is session:
                self._active_session = None
