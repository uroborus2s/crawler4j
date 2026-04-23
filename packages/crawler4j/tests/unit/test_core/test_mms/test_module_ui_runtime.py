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
        page_payload = bridge.call_page_handler(
            "load_dashboard_page",
            "dashboard",
            None,
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
        "load_handler": "load_dashboard_page",
        "children": [{"type": "Text", "text": "legacy"}],
    }
    legacy_accounts_page = {
        "type": "Page",
        "title": "旧账号页",
        "load_handler": "load_accounts_page",
        "children": [{"type": "Text", "text": "legacy"}],
    }
    store.write_page_schema(module_name, "dashboard", legacy_page)
    store.write_page_schema(module_name, "accounts", legacy_accounts_page)
    bridge = ModuleUIRuntimeBridge(module_name)

    try:
        with pytest.raises(RuntimeError, match="declare_ui boom"):
            bridge.declare_ui()

        assert store.read_page_schema(module_name, "dashboard") == legacy_page
        assert store.read_page_schema(module_name, "accounts") == legacy_accounts_page
        assert store.read_page_schema(module_name, "next_dashboard") == {}
    finally:
        service.registry = original_registry
        purge_module_namespace(module_name)


def test_module_ui_runtime_bridge_declare_ui_stages_pages_without_persisting_to_store(tmp_path):
    module_name = "staged_only_bridge_module"
    module_dir = _write_runtime_module(
        tmp_path,
        module_name,
        """
        from crawler4j_sdk import TaskContext


        def declare_ui(context: TaskContext):
            context.tools.call(
                "ui.declare_page",
                page_id="dashboard",
                schema={
                    "type": "Page",
                    "title": "今日看板",
                    "load_handler": "load_dashboard_page",
                    "children": [],
                },
            )


        def load_dashboard_page(context: TaskContext, page_id: str, params=None):
            return {"page_id": page_id, "params": params}
        """,
    )
    service, original_registry = _register_dev_link_module(module_name, module_dir)
    store = get_module_data_store()
    bridge = ModuleUIRuntimeBridge(module_name)

    try:
        bridge.declare_ui()

        assert bridge.get_declared_page("dashboard")["title"] == "今日看板"
        assert store.read_page_schema(module_name, "dashboard") == {}
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
        first_payload = bridge.call_page_handler(
            "load_dashboard_page",
            "dashboard",
            None,
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


def test_module_ui_runtime_bridge_scopes_hosted_ui_tools_by_hook_type(tmp_path):
    module_name = "scoped_bridge_module"
    module_dir = _write_runtime_module(
        tmp_path,
        module_name,
        """
        from crawler4j_sdk import TaskContext


        OBSERVED = {}


        def declare_ui(context: TaskContext):
            OBSERVED["declare_tools"] = [spec.name for spec in context.tools.list_tools()]
            OBSERVED["declare_has_get_page"] = context.tools.has_tool("ui.get_page")
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
            OBSERVED["load_tools"] = [spec.name for spec in context.tools.list_tools()]
            OBSERVED["load_has_declare_page"] = context.tools.has_tool("ui.declare_page")
            OBSERVED["load_has_get_page"] = context.tools.has_tool("ui.get_page")
            OBSERVED["load_page_id"] = context.runtime.get("page_id")
            OBSERVED["load_params"] = context.runtime.get("params")
            OBSERVED["load_schema_type"] = context.tools.call("ui.get_page", page_id=page_id).get("type")
            try:
                context.tools.call("db.set_state", key="hosted_ui_load", value=1)
            except Exception as exc:
                OBSERVED["load_write_error"] = type(exc).__name__
            return dict(OBSERVED)


        def query_dashboard_metrics(context: TaskContext, table_id: str, query, params=None):
            OBSERVED["query_tools"] = [spec.name for spec in context.tools.list_tools()]
            OBSERVED["query_has_declare_page"] = context.tools.has_tool("ui.declare_page")
            OBSERVED["query_page_id"] = context.runtime.get("page_id")
            OBSERVED["query_table_id"] = context.runtime.get("table_id")
            OBSERVED["query_params"] = context.runtime.get("params")
            OBSERVED["query_rows_before"] = context.tools.call("db.list_records", dataset="metrics")
            try:
                context.tools.call("db.append_event", dataset="metrics_events", event_type="query")
            except Exception as exc:
                OBSERVED["query_write_error"] = type(exc).__name__
            return {
                "rows": [],
                "total": 0,
                "page": 1,
                "page_size": 20,
                "observed": dict(OBSERVED),
            }
        """,
    )
    service, original_registry = _register_dev_link_module(module_name, module_dir)
    bridge = ModuleUIRuntimeBridge(module_name)

    try:
        bridge.declare_ui(page_id="dashboard", params={"phone": "13800138000"})
        page_payload = bridge.call_page_handler(
            "load_dashboard_page",
            "dashboard",
            {"phone": "13800138000"},
        )
        query_payload = bridge.call_query_handler(
            "query_dashboard_metrics",
            "metrics",
            {"page": 1, "page_size": 20, "sort": []},
            {"phone": "13800138000"},
            page_id="dashboard",
        )

        assert page_payload["declare_tools"] == ["ui.declare_page"]
        assert page_payload["declare_has_get_page"] is False
        assert page_payload["load_tools"] == [
            "db.list_records",
            "db.query_events",
            "db.query_view",
            "ui.get_page",
        ]
        assert page_payload["load_has_declare_page"] is False
        assert page_payload["load_has_get_page"] is True
        assert page_payload["load_page_id"] == "dashboard"
        assert page_payload["load_params"] == {"phone": "13800138000"}
        assert page_payload["load_schema_type"] == "Page"
        assert page_payload["load_write_error"] == "KeyError"
        assert query_payload["observed"]["query_tools"] == [
            "db.list_records",
            "db.query_events",
            "db.query_view",
            "ui.get_page",
        ]
        assert query_payload["observed"]["query_has_declare_page"] is False
        assert query_payload["observed"]["query_page_id"] == "dashboard"
        assert query_payload["observed"]["query_table_id"] == "metrics"
        assert query_payload["observed"]["query_params"] == {"phone": "13800138000"}
        assert query_payload["observed"]["query_rows_before"] == []
        assert query_payload["observed"]["query_write_error"] == "KeyError"
    finally:
        service.registry = original_registry
        purge_module_namespace(module_name)
