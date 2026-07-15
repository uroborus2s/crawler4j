"""模块宿主页运行时桥接。"""

from __future__ import annotations

import asyncio
import inspect
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from crawler4j_contracts import HostedDataTableQuery, TaskContext

from src.core.atm.runtime_capabilities import (
    HostedUIDeclarationBuffer,
    RUNTIME_SURFACE_FULL,
    RUNTIME_SURFACE_HOSTED_UI_ACTION,
    RUNTIME_SURFACE_HOSTED_UI_DECLARE,
    RUNTIME_SURFACE_HOSTED_UI_READONLY,
    build_runtime_capabilities,
)
from src.core.foundation.logging import logger
from src.core.mms.models import ModuleInfo, ModuleSource
from src.core.mms.runtime_descriptor import ModuleRuntimeDescriptorV2, PageRuntimeEntry, invoke_runtime_callable
from src.core.mms.service import get_module_service
from src.core.mms.settings_store import get_module_settings_store


@dataclass
class _HostedUISession:
    context: TaskContext
    descriptor: ModuleRuntimeDescriptorV2


class ModuleUIRuntimeBridge:
    """复用模块宿主页声明、页面处理器调用与 DevLink reload 语义。"""

    def __init__(self, module_name: str, module_info: ModuleInfo | None = None):
        self._module_name = module_name
        self._module_info = module_info
        self._mms = get_module_service()
        self._active_session: _HostedUISession | None = None
        self._declared_page_schemas: dict[str, dict[str, Any]] = {}

    def _resolve_module_info(self) -> ModuleInfo | None:
        return self._module_info or self._mms.registry.get_module(self._module_name)

    def _is_dev_link(self) -> bool:
        module = self._resolve_module_info()
        return bool(module and module.source == ModuleSource.DEV_LINK)

    def _is_v2_module(self) -> bool:
        module = self._resolve_module_info()
        runtime_api = str(getattr(getattr(module, "manifest", None), "runtime_api", "") or "").strip()
        return runtime_api == "core-native-v2"

    def build_task_context(
        self,
        *,
        runtime_extra: dict[str, Any] | None = None,
        ui_declaration_buffer: HostedUIDeclarationBuffer | None = None,
        capability_surface: str = RUNTIME_SURFACE_FULL,
        declared_page_schemas: dict[str, dict[str, Any]] | None = None,
        hosted_form_tools: Any | None = None,
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
            hosted_form_tools=hosted_form_tools,
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
        hosted_form_tools: Any | None = None,
    ) -> _HostedUISession:
        context = self.build_task_context(
            ui_declaration_buffer=ui_declaration_buffer,
            capability_surface=capability_surface,
            declared_page_schemas=declared_page_schemas,
            hosted_form_tools=hosted_form_tools,
        )
        descriptor = self._mms.get_runtime_descriptor_v2(
            self._module_name,
            context,
            force_reload=force_reload,
        )
        return _HostedUISession(context=context, descriptor=descriptor)

    def _set_context_tools(
        self,
        context: TaskContext,
        *,
        ui_declaration_buffer: HostedUIDeclarationBuffer | None = None,
        capability_surface: str = RUNTIME_SURFACE_FULL,
        declared_page_schemas: dict[str, dict[str, Any]] | None = None,
        hosted_form_tools: Any | None = None,
    ) -> None:
        capabilities = build_runtime_capabilities(
            self._module_name,
            ui_declaration_buffer=ui_declaration_buffer,
            surface=capability_surface,
            declared_page_schemas=declared_page_schemas,
            hosted_form_tools=hosted_form_tools,
        )
        context.tools = capabilities.tools
        context.db = capabilities.db
        binder = getattr(context.tools, "bind_task_context", None)
        if callable(binder):
            binder(context)

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
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        if func is None or not callable(func):
            raise RuntimeError(f"{owner} 未定义或不可调用")
        result = func(context, *args, **dict(kwargs or {}))
        if inspect.isawaitable(result):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(result)
            if inspect.iscoroutine(result):
                result.close()
            raise RuntimeError(f"{owner} 是 async，当前同步宿主页调用缺少可等待的执行入口")
        return result

    def _resolve_page_entry(self, session: _HostedUISession, page_id: str) -> PageRuntimeEntry:
        page = session.descriptor.pages.get(page_id)
        if not page:
            raise RuntimeError(f"未找到宿主页声明: {page_id}")
        return page

    def call_ui_action_sync(
        self,
        action_name: str,
        *args: Any,
        runtime_extra: dict[str, Any] | None = None,
        capability_surface: str | None = None,
        hosted_form_tools: Any | None = None,
    ) -> Any:
        if capability_surface is None:
            capability_surface = RUNTIME_SURFACE_HOSTED_UI_ACTION
        isolated_session = hosted_form_tools is not None
        session = None if isolated_session else self._active_session
        if session is None:
            session = self._create_session(
                force_reload=self._is_dev_link(),
                capability_surface=capability_surface,
                declared_page_schemas=self._declared_page_schemas or None,
                hosted_form_tools=hosted_form_tools,
            )
        else:
            self._set_context_tools(
                session.context,
                capability_surface=capability_surface,
                declared_page_schemas=self._declared_page_schemas or None,
                hosted_form_tools=hosted_form_tools,
            )
        try:
            descriptor = self._mms.get_runtime_descriptor_v2(self._module_name, session.context)
            ui_action = descriptor.ui_actions.get(str(action_name or "").strip())
            with self._override_runtime(session.context, runtime_extra):
                return self._run_sync_callable(
                    ui_action.target if ui_action else None,
                    owner=f"{self._module_name}.ui_action.{action_name}",
                    context=session.context,
                    args=args,
                )
        finally:
            if self._active_session is session:
                self._active_session = None

    async def call_ui_action_async(
        self,
        action_name: str,
        params: dict[str, Any] | None = None,
        *,
        runtime_extra: dict[str, Any] | None = None,
        capability_surface: str = RUNTIME_SURFACE_HOSTED_UI_ACTION,
        hosted_form_tools: Any | None = None,
    ) -> Any:
        normalized_action = str(action_name or "").strip()
        if not normalized_action:
            raise RuntimeError("ui_action 名称不能为空")
        normalized_params = dict(params or {}) if isinstance(params, dict) else {}
        isolated_session = hosted_form_tools is not None
        session = None if isolated_session else self._active_session
        if session is None:
            session = self._create_session(
                force_reload=self._is_dev_link(),
                capability_surface=capability_surface,
                declared_page_schemas=self._declared_page_schemas or None,
                hosted_form_tools=hosted_form_tools,
            )
        else:
            self._set_context_tools(
                session.context,
                capability_surface=capability_surface,
                declared_page_schemas=self._declared_page_schemas or None,
                hosted_form_tools=hosted_form_tools,
            )
        try:
            descriptor = self._mms.get_runtime_descriptor_v2(self._module_name, session.context)
            ui_action = descriptor.ui_actions.get(normalized_action)
            if ui_action is None:
                raise RuntimeError(f"ui_action 不存在: {normalized_action}")
            with self._override_runtime(session.context, runtime_extra):
                return await invoke_runtime_callable(ui_action.target, session.context, **normalized_params)
        finally:
            if self._active_session is session:
                self._active_session = None

    def call_ui_action(
        self,
        action_name: str,
        params: dict[str, Any] | None = None,
        *,
        runtime_extra: dict[str, Any] | None = None,
        capability_surface: str = RUNTIME_SURFACE_HOSTED_UI_ACTION,
        hosted_form_tools: Any | None = None,
    ) -> Any:
        coroutine = self.call_ui_action_async(
            action_name,
            params,
            runtime_extra=runtime_extra,
            capability_surface=capability_surface,
            hosted_form_tools=hosted_form_tools,
        )
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
        coroutine.close()
        raise RuntimeError("ui_action 是 async，当前同步宿主页调用缺少可等待的执行入口")

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
        query: HostedDataTableQuery | dict[str, Any] | None,
        *,
        page_id: str,
    ) -> Any:
        normalized_query = (
            query
            if isinstance(query, HostedDataTableQuery)
            else HostedDataTableQuery.from_mapping(query if isinstance(query, dict) else None)
        )
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
                },
            ):
                return self._run_sync_callable(
                    handler,
                    owner=f"{page.module_name}.{handler_name}",
                    context=session.context,
                    args=(normalized_query,),
                )
        finally:
            if self._active_session is session:
                self._active_session = None
