from __future__ import annotations

import time
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.core.mms.ui.module_ui_runtime import ModuleUIRuntimeBridge
from src.core.persistence import get_module_data_store

from ._core_native_v1 import make_manifest, make_page_info, register_module, restore_module, write_module_tree


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def _sync_managed_dataset(module_name: str, module_root, resource_id: str) -> None:
    from src.core.mms.data_contract import normalize_manifest_data

    manifest_data = normalize_manifest_data(
        {
            "resources": [
                {
                    "id": resource_id,
                    "storage_mode": "managed_dataset",
                    "schema": {
                        "version": 1,
                        "columns": [{"name": "id", "type": "text", "required": True}],
                    },
                }
            ],
            "views": [],
            "queries": [],
            "seeds": [],
        }
    )
    get_module_data_store().sync_manifest_data(module_name, module_root, manifest_data)


def test_module_ui_runtime_bridge_reads_page_schema_and_handlers_from_descriptor(tmp_path):
    module_name = "runtime_bridge_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import PageSpec, TaskContext

            PAGE = PageSpec(
                id="dashboard",
                label="Dashboard",
                icon="📊",
                schema={
                    "type": "Page",
                    "title": "今日看板",
                    "load_handler": "load_dashboard_page",
                    "children": [],
                },
            )


            def load_dashboard_page(context: TaskContext, page_id: str, params: dict | None = None):
                return {"page_id": page_id, "params": params, "mode": context.config.get("mode", "unset")}
            """,
            "hooks/create_account_from_ui.py": """
            from crawler4j_contracts import TaskContext


            def handle(context: TaskContext, payload: dict):
                return {"payload": dict(payload), "mode": context.config.get("mode", "unset")}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard", label="Dashboard", icon="📊")])
    service, original_registry, _ = register_module(module_name, module_dir, manifest=manifest)
    bridge = ModuleUIRuntimeBridge(module_name)

    try:
        bridge.declare_ui()

        assert bridge.get_declared_page("dashboard") == {
            "type": "Page",
            "title": "今日看板",
            "load_handler": "load_dashboard_page",
            "children": [],
        }
        assert bridge.call_page_handler(
            "load_dashboard_page",
            "dashboard",
            {"phone": "13800138000"},
        ) == {
            "page_id": "dashboard",
            "params": {"phone": "13800138000"},
            "mode": "unset",
        }
        assert bridge.call_local_hook("create_account_from_ui", {"id": "u1"}) == {
            "payload": {"id": "u1"},
            "mode": "unset",
        }
    finally:
        restore_module(service, original_registry, module_name)


def test_module_ui_runtime_bridge_reads_grouped_page_schema_and_handlers_from_descriptor(tmp_path):
    module_name = "runtime_bridge_grouped_page_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/account/detail.py": """
            from crawler4j_contracts import PageSpec, TaskContext

            PAGE = PageSpec(
                id="account_detail",
                label="Account Detail",
                icon="📋",
                schema={
                    "type": "Page",
                    "title": "账号详情",
                    "load_handler": "load_account_detail_page",
                    "children": [],
                },
            )


            def load_account_detail_page(
                context: TaskContext,
                page_id: str,
                params: dict | None = None,
            ):
                del context
                return {"page_id": page_id, "params": params}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("account_detail", label="Account Detail", icon="📋")])
    service, original_registry, _ = register_module(module_name, module_dir, manifest=manifest)
    bridge = ModuleUIRuntimeBridge(module_name)

    try:
        bridge.declare_ui()

        assert bridge.get_declared_page("account_detail") == {
            "type": "Page",
            "title": "账号详情",
            "load_handler": "load_account_detail_page",
            "children": [],
        }
        assert bridge.call_page_handler(
            "load_account_detail_page",
            "account_detail",
            {"account_id": "acct-001"},
        ) == {
            "page_id": "account_detail",
            "params": {"account_id": "acct-001"},
        }
    finally:
        restore_module(service, original_registry, module_name)


def test_module_ui_runtime_bridge_does_not_persist_page_schema_to_store(tmp_path):
    module_name = "staged_only_bridge_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import PageSpec

            PAGE = PageSpec(
                id="dashboard",
                label="Dashboard",
                schema={
                    "type": "Page",
                    "title": "只存在于 descriptor",
                    "load_handler": "load_dashboard_page",
                    "children": [],
                },
            )


            def load_dashboard_page(context, page_id, params=None):
                return {"page_id": page_id}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard")])
    service, original_registry, _ = register_module(module_name, module_dir, manifest=manifest)
    bridge = ModuleUIRuntimeBridge(module_name)
    store = get_module_data_store()

    try:
        bridge.declare_ui()

        assert bridge.get_declared_page("dashboard")["title"] == "只存在于 descriptor"
        assert store.read_page_schema(module_name, "dashboard") == {}
    finally:
        restore_module(service, original_registry, module_name)


def test_module_ui_runtime_bridge_reloads_dev_link_descriptor_between_sessions(tmp_path, monkeypatch):
    module_name = "reloadable_bridge_module"
    config_state = {"mode": "old"}
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import PageSpec, TaskContext

            PAGE = PageSpec(
                id="dashboard",
                label="Dashboard",
                schema={
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "children": [],
                },
            )


            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                return {"version": "v1", "mode": context.config.get("mode")}
            """,
            "hooks/create_account_from_ui.py": """
            from crawler4j_contracts import TaskContext


            def handle(context: TaskContext, payload: dict):
                return {"version": "v1", "mode": context.config.get("mode"), "payload": dict(payload)}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard")])
    service, original_registry, _ = register_module(module_name, module_dir, manifest=manifest)
    monkeypatch.setattr(
        "src.core.mms.ui.module_ui_runtime.get_module_settings_store",
        lambda: SimpleNamespace(read_module_settings=lambda _module_name: dict(config_state)),
    )
    bridge = ModuleUIRuntimeBridge(module_name)

    try:
        bridge.declare_ui()
        first_payload = bridge.call_page_handler("load_dashboard_page", "dashboard", None)

        config_state["mode"] = "new"
        time.sleep(1.1)
        write_module_tree(
            tmp_path,
            module_name,
            files={
                "pages/dashboard.py": """
                from crawler4j_contracts import PageSpec, TaskContext

                PAGE = PageSpec(
                    id="dashboard",
                    label="Dashboard",
                    schema={
                        "type": "Page",
                        "load_handler": "load_dashboard_page",
                        "children": [],
                    },
                )


                def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                    return {"version": "v2", "mode": context.config.get("mode")}
                """,
                "hooks/create_account_from_ui.py": """
                from crawler4j_contracts import TaskContext


                def handle(context: TaskContext, payload: dict):
                    return {"version": "v2", "mode": context.config.get("mode"), "payload": dict(payload)}
                """,
            },
        )

        later_payload = bridge.call_local_hook("create_account_from_ui", {"id": "u1"})

        assert first_payload == {"version": "v1", "mode": "old"}
        assert later_payload == {"version": "v2", "mode": "new", "payload": {"id": "u1"}}
    finally:
        restore_module(service, original_registry, module_name)


def test_module_ui_runtime_bridge_preserves_previous_schema_when_reload_fails(tmp_path):
    module_name = "atomic_bridge_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import PageSpec

            PAGE = PageSpec(
                id="dashboard",
                label="Dashboard",
                schema={
                    "type": "Page",
                    "title": "旧看板",
                    "load_handler": "load_dashboard_page",
                    "children": [],
                },
            )


            def load_dashboard_page(context, page_id, params=None):
                return {}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard")])
    service, original_registry, _ = register_module(module_name, module_dir, manifest=manifest)
    bridge = ModuleUIRuntimeBridge(module_name)

    try:
        bridge.declare_ui()
        assert bridge.get_declared_page("dashboard")["title"] == "旧看板"

        time.sleep(1.1)
        (module_dir / "pages" / "dashboard.py").write_text(
            "from missing_runtime_dependency import nope\n",
            encoding="utf-8",
        )

        with pytest.raises(RuntimeError, match="无法导入"):
            bridge.declare_ui()

        assert bridge.get_declared_page("dashboard")["title"] == "旧看板"
    finally:
        restore_module(service, original_registry, module_name)


def test_module_ui_runtime_bridge_scopes_page_and_query_handlers_to_readonly_tools(tmp_path):
    module_name = "scoped_bridge_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import PageSpec, TaskContext

            OBSERVED = {}

            PAGE = PageSpec(
                id="dashboard",
                label="Dashboard",
                schema={
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "metrics",
                            "title": "统计明细",
                            "data_source": {"type": "query_handler", "handler": "query_dashboard_metrics"},
                            "columns": [
                                {"key": "metric", "label": "指标"},
                                {"key": "value", "label": "值"},
                            ],
                        },
                    ],
                },
            )


            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                OBSERVED["load_tools"] = [spec.name for spec in context.tools.list_tools()]
                OBSERVED["load_has_get_page"] = context.tools.has_tool("ui.get_page")
                OBSERVED["load_page_id"] = context.runtime.get("page_id")
                OBSERVED["load_params"] = context.runtime.get("params")
                OBSERVED["load_schema_type"] = context.tools.call("ui.get_page", page_id=page_id).get("type")
                try:
                    context.db.into("metrics").replace([])
                except Exception as exc:
                    OBSERVED["load_write_error"] = type(exc).__name__
                return dict(OBSERVED)


            def query_dashboard_metrics(context: TaskContext, table_id: str, query, params=None):
                OBSERVED["query_tools"] = [spec.name for spec in context.tools.list_tools()]
                OBSERVED["query_page_id"] = context.runtime.get("page_id")
                OBSERVED["query_table_id"] = context.runtime.get("table_id")
                OBSERVED["query_params"] = context.runtime.get("params")
                OBSERVED["query_rows_before"] = context.db.from_("metrics").execute()
                try:
                    context.db.into("metrics").replace([])
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
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard")])
    manifest.data = {
        "resources": [
            {
                "resource_id": "metrics",
                "storage_mode": "managed_dataset",
                "record_key_field": "id",
                "schema": {
                    "version": 1,
                    "columns": [{"name": "id", "type": "text", "required": True}],
                },
                "indexes": {},
                "cleanup_policy": "delete_rows",
            }
        ],
        "views": [],
        "queries": [],
        "seeds": [],
    }
    service, original_registry, _ = register_module(module_name, module_dir, manifest=manifest)
    bridge = ModuleUIRuntimeBridge(module_name)

    try:
        _sync_managed_dataset(module_name, module_dir, "metrics")
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

        assert page_payload["load_tools"] == ["ui.get_page"]
        assert page_payload["load_has_get_page"] is True
        assert page_payload["load_page_id"] == "dashboard"
        assert page_payload["load_params"] == {"phone": "13800138000"}
        assert page_payload["load_schema_type"] == "Page"
        assert page_payload["load_write_error"] == "RuntimeError"
        assert query_payload["observed"]["query_tools"] == ["ui.get_page"]
        assert query_payload["observed"]["query_page_id"] == "dashboard"
        assert query_payload["observed"]["query_table_id"] == "metrics"
        assert query_payload["observed"]["query_params"] == {"phone": "13800138000"}
        assert query_payload["observed"]["query_rows_before"] == []
        assert query_payload["observed"]["query_write_error"] == "RuntimeError"
    finally:
        restore_module(service, original_registry, module_name)
