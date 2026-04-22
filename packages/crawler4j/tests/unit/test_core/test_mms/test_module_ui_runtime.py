from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource
from src.core.mms.module_loader import purge_module_namespace
from src.core.mms.service import get_module_service
from src.core.mms.ui.module_ui_runtime import ModuleUIRuntimeBridge
from src.core.persistence import get_module_data_store


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def _write_runtime_module(base_dir: Path, module_name: str, runtime_code: str) -> Path:
    module_dir = base_dir / module_name
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "__init__.py").write_text(
        dedent(
            """
            import importlib

            _runtime_module = None


            def _load_runtime_module():
                global _runtime_module
                if _runtime_module is None:
                    _runtime_module = importlib.import_module(f"{__name__}.module_runtime")
                return _runtime_module


            def __getattr__(name: str):
                runtime_module = _load_runtime_module()
                if hasattr(runtime_module, name):
                    return getattr(runtime_module, name)
                raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (module_dir / "module_runtime.py").write_text(dedent(runtime_code).strip() + "\n", encoding="utf-8")
    return module_dir


def _register_dev_link_module(module_name: str, module_dir: Path):
    service = get_module_service()
    original_registry = service.registry
    service.registry = SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name=module_name,
            manifest=ModuleManifest(name=module_name),
            path=module_dir,
            source=ModuleSource.DEV_LINK,
        )
        if name in {module_name, module_name.split(".")[0]}
        else None
    )
    return service, original_registry


def test_module_ui_runtime_bridge_reuses_same_module_instance_within_refresh_cycle(tmp_path):
    module_name = "runtime_bridge_module"
    module_dir = _write_runtime_module(
        tmp_path,
        module_name,
        """
        from crawler4j_sdk import TaskContext


        STATE = {"count": 0}


        def declare_ui(context: TaskContext):
            STATE["count"] += 1
            context.tools.call(
                "ui.declare_page",
                page_id="dashboard",
                schema={
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "children": [],
                },
            )


        def load_dashboard_page(context: TaskContext, page_id: str, params=None):
            return {"module_state": STATE["count"], "page_id": page_id}


        def create_account_from_ui(context: TaskContext, payload: dict):
            return {"module_state": STATE["count"], "payload": dict(payload)}
        """,
    )
    service, original_registry = _register_dev_link_module(module_name, module_dir)
    bridge = ModuleUIRuntimeBridge(module_name)

    try:
        bridge.declare_ui()
        page_payload = bridge.call_local_hook(
            "load_dashboard_page",
            "dashboard",
            None,
            runtime_extra={"page_id": "dashboard"},
        )
        bridge.declare_ui()
        create_payload = bridge.call_local_hook("create_account_from_ui", {"id": "u1"})

        assert page_payload == {"module_state": 1, "page_id": "dashboard"}
        assert create_payload == {"module_state": 1, "payload": {"id": "u1"}}
    finally:
        service.registry = original_registry
        purge_module_namespace(module_name)


def test_module_ui_runtime_bridge_keeps_previous_ui_schema_when_declare_ui_fails(tmp_path):
    module_name = "atomic_bridge_module"
    module_dir = _write_runtime_module(
        tmp_path,
        module_name,
        """
        from crawler4j_sdk import TaskContext


        def declare_ui(context: TaskContext):
            context.tools.call(
                "ui.declare_page",
                page_id="next_dashboard",
                schema={
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "children": [],
                },
            )
            context.tools.call(
                "ui.declare_data_table",
                view_id="next_accounts",
                schema={
                    "title": "新账号表",
                    "dataset": "next_accounts",
                    "columns": [{"key": "phone", "label": "手机号"}],
                },
            )
            raise RuntimeError("declare_ui boom")


        def load_dashboard_page(context: TaskContext, page_id: str, params=None):
            return {}
        """,
    )
    service, original_registry = _register_dev_link_module(module_name, module_dir)
    store = get_module_data_store()
    legacy_page = {
        "type": "Page",
        "title": "旧看板",
        "children": [{"type": "Text", "text": "legacy"}],
    }
    legacy_table = {
        "title": "旧账号表",
        "dataset": "accounts",
        "columns": [{"key": "phone", "label": "手机号"}],
    }
    store.write_page_schema(module_name, "dashboard", legacy_page)
    store.write_data_table_schema(module_name, "accounts", legacy_table)
    bridge = ModuleUIRuntimeBridge(module_name)

    try:
        with pytest.raises(RuntimeError, match="declare_ui boom"):
            bridge.declare_ui()

        assert store.read_page_schema(module_name, "dashboard") == legacy_page
        assert store.read_data_table_schema(module_name, "accounts") == legacy_table
        assert store.read_page_schema(module_name, "next_dashboard") == {}
        assert store.read_data_table_schema(module_name, "next_accounts") == {}
    finally:
        service.registry = original_registry
        purge_module_namespace(module_name)


def test_module_ui_runtime_bridge_drops_consumed_session_before_later_hooks(tmp_path, monkeypatch):
    module_name = "refreshable_bridge_module"
    config_state = {"mode": "old"}
    module_dir = _write_runtime_module(
        tmp_path,
        module_name,
        """
        from crawler4j_sdk import TaskContext


        MODULE_VERSION = "v1"
        STATE = {"count": 0}


        def declare_ui(context: TaskContext):
            STATE["count"] += 1
            context.tools.call(
                "ui.declare_page",
                page_id="dashboard",
                schema={
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "children": [],
                },
            )


        def load_dashboard_page(context: TaskContext, page_id: str, params=None):
            return {
                "version": MODULE_VERSION,
                "mode": context.config.get("mode"),
                "state": STATE["count"],
            }


        def create_account_from_ui(context: TaskContext, payload: dict):
            return {
                "version": MODULE_VERSION,
                "mode": context.config.get("mode"),
                "state": STATE["count"],
                "payload": dict(payload),
            }
        """,
    )
    service, original_registry = _register_dev_link_module(module_name, module_dir)
    monkeypatch.setattr(
        "src.core.mms.ui.module_ui_runtime.get_module_settings_store",
        lambda: SimpleNamespace(read_module_settings=lambda _module_name: dict(config_state)),
    )
    bridge = ModuleUIRuntimeBridge(module_name)

    try:
        bridge.declare_ui()
        first_payload = bridge.call_local_hook(
            "load_dashboard_page",
            "dashboard",
            None,
            runtime_extra={"page_id": "dashboard"},
        )

        config_state["mode"] = "new"
        (module_dir / "module_runtime.py").write_text(
            dedent(
                """
                from crawler4j_sdk import TaskContext


                MODULE_VERSION = "v2"
                STATE = {"count": 0}


                def declare_ui(context: TaskContext):
                    STATE["count"] += 1
                    context.tools.call(
                        "ui.declare_page",
                        page_id="dashboard",
                        schema={
                            "type": "Page",
                            "load_handler": "load_dashboard_page",
                            "children": [],
                        },
                    )


                def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                    return {
                        "version": MODULE_VERSION,
                        "mode": context.config.get("mode"),
                        "state": STATE["count"],
                    }


                def create_account_from_ui(context: TaskContext, payload: dict):
                    return {
                        "version": MODULE_VERSION,
                        "mode": context.config.get("mode"),
                        "state": STATE["count"],
                        "payload": dict(payload),
                    }
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        later_payload = bridge.call_local_hook("create_account_from_ui", {"id": "u1"})

        assert first_payload == {"version": "v1", "mode": "old", "state": 1}
        assert later_payload == {
            "version": "v2",
            "mode": "new",
            "state": 0,
            "payload": {"id": "u1"},
        }
    finally:
        service.registry = original_registry
        purge_module_namespace(module_name)
