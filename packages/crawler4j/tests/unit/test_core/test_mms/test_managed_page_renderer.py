from __future__ import annotations

import builtins
from contextlib import ExitStack
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QLabel, QPushButton

from src.core.mms.ui.managed_page_renderer import ManagedPageRenderer

from ._core_native_v1 import make_manifest, make_page_info, register_module, restore_module, write_module_tree


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def test_managed_page_renderer_loads_page_data_refreshes_and_handles_open_page(qtbot, tmp_path):
    module_name = "hosted_page_module"
    load_key = "_hosted_page_module_load_count"
    setattr(builtins, load_key, 0)
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": f"""
            import builtins

            from crawler4j_contracts import PageSpec, TaskContext

            LOAD_COUNT_KEY = "{load_key}"

            PAGE = PageSpec(
                id="dashboard",
                label="Dashboard",
                icon="📊",
                schema={{
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "children": [
                        {{"type": "Text", "style": "title", "binding": "title"}},
                        {{"type": "Text", "style": "body", "binding": "load_count_text"}},
                        {{"type": "Button", "label": "刷新", "action": {{"type": "reload"}}}},
                        {{"type": "Button", "label": "打开账号页", "action": {{"type": "open_page", "page_id": "accounts"}}}},
                        {{
                            "type": "DataTable",
                            "table_id": "metrics",
                            "title": "统计明细",
                            "data_source": {{"type": "binding", "binding": "rows"}},
                            "columns": [
                                {{"key": "metric", "label": "指标"}},
                                {{"key": "value", "label": "值"}},
                            ],
                        }},
                    ],
                }},
            )


            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                del context, page_id, params
                count = int(getattr(builtins, LOAD_COUNT_KEY, 0)) + 1
                setattr(builtins, LOAD_COUNT_KEY, count)
                return {{
                    "title": "今日运营看板",
                    "load_count_text": f"第 {{count}} 次加载",
                    "rows": [{{"metric": "活跃账号", "value": str(10 + count)}}],
                }}
            """,
            "pages/accounts.py": """
            from crawler4j_contracts import PageSpec, TaskContext

            PAGE = PageSpec(
                id="accounts",
                label="Accounts",
                icon="📋",
                schema={
                    "type": "Page",
                    "load_handler": "load_accounts_page",
                    "children": [{"type": "Text", "style": "title", "binding": "title"}],
                },
            )


            def load_accounts_page(context: TaskContext, page_id: str, params=None):
                del context, page_id, params
                return {"title": "账号页"}
            """,
        },
    )
    manifest = make_manifest(
        module_name,
        pages=[
            make_page_info("dashboard", label="今日运营看板", icon="📊"),
            make_page_info("accounts", label="账号管理", icon="📋"),
        ],
    )
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    opened_pages: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
            module_info=module_info,
            open_page_callback=lambda page_id, params=None: opened_pages.append((page_id, params)),
        )
        qtbot.addWidget(page)

        assert any(label.text() == "今日运营看板" for label in page.findChildren(QLabel))
        assert any(label.text() == "第 1 次加载" for label in page.findChildren(QLabel))
        first_table = page._data_table_widgets["metrics"]
        assert first_table.item(0, 0).text() == "活跃账号"
        assert first_table.item(0, 1).text() == "11"

        reload_button = next(button for button in page.findChildren(QPushButton) if button.text() == "刷新")
        reload_button.click()
        qtbot.waitUntil(lambda: any(label.text() == "第 2 次加载" for label in page.findChildren(QLabel)))

        open_button = next(button for button in page.findChildren(QPushButton) if button.text() == "打开账号页")
        open_button.click()
        assert opened_pages == [("accounts", None)]
    finally:
        restore_module(service, original_registry, module_name)
        delattr(builtins, load_key)


def test_managed_page_renderer_scopes_load_and_query_handlers_to_readonly_tools(qtbot, tmp_path):
    module_name = "hosted_page_readonly_tools_module"
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
                    "children": [
                        {"type": "Text", "style": "body", "binding": "load_tools"},
                        {"type": "Text", "style": "body", "binding": "load_write_error"},
                        {
                            "type": "DataTable",
                            "table_id": "stats",
                            "title": "统计明细",
                            "data_source": {"type": "query_handler", "handler": "query_stats_table"},
                            "columns": [
                                {"key": "metric", "label": "指标"},
                                {"key": "value", "label": "值"},
                            ],
                        },
                    ],
                },
            )


            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                del page_id, params
                load_tools = ",".join(spec.name for spec in context.tools.list_tools())
                try:
                    context.tools.call("db.set_state", key="hosted_ui_load", value=1)
                except Exception as exc:
                    load_write_error = type(exc).__name__
                return {
                    "load_tools": load_tools,
                    "load_write_error": load_write_error,
                }


            def query_stats_table(context: TaskContext, table_id: str, query, params=None):
                del table_id, query, params
                query_tools = ",".join(spec.name for spec in context.tools.list_tools())
                try:
                    context.tools.call("db.replace_records", dataset="hosted_ui_query", records=[])
                except Exception as exc:
                    query_write_error = type(exc).__name__
                return {
                    "rows": [
                        {"metric": "query_tools", "value": query_tools},
                        {"metric": "query_write_error", "value": query_write_error},
                    ],
                    "total": 2,
                    "page": 1,
                    "page_size": 20,
                }
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)

    try:
        page = ManagedPageRenderer(module_name, "dashboard", module_info=module_info)
        qtbot.addWidget(page)

        readonly_tools = "db.list_records,db.query_events,db.query_view,ui.get_page"
        assert any(label.text() == readonly_tools for label in page.findChildren(QLabel))
        assert any(label.text() == "KeyError" for label in page.findChildren(QLabel))

        table = page._data_table_widgets["stats"]
        qtbot.waitUntil(lambda: table.item(1, 1) is not None)

        assert table.item(0, 0).text() == "query_tools"
        assert table.item(0, 1).text() == readonly_tools
        assert table.item(1, 0).text() == "query_write_error"
        assert table.item(1, 1).text() == "KeyError"
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_row_action_opens_page_with_row_params(qtbot, tmp_path):
    module_name = "hosted_page_row_action_module"
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
                    "load_handler": "load_dashboard_page",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "title": "账号总览",
                            "data_source": {"type": "binding", "binding": "rows"},
                            "columns": [
                                {"key": "account_id", "label": "账号"},
                                {"key": "status", "label": "状态"},
                            ],
                            "row_action": {
                                "type": "open_page",
                                "page_id": "details",
                                "params": {
                                    "account_id": {"binding": "account_id"},
                                },
                            },
                        },
                    ],
                },
            )


            def load_dashboard_page(context, page_id, params=None):
                del context, page_id, params
                return {
                    "rows": [
                        {"account_id": "acct-001", "status": "active"},
                        {"account_id": "acct-002", "status": "blocked"},
                    ],
                }
            """,
            "pages/details.py": """
            from crawler4j_contracts import PageSpec

            PAGE = PageSpec(
                id="details",
                label="Details",
                schema={
                    "type": "Page",
                    "load_handler": "load_details_page",
                    "children": [{"type": "Text", "binding": "title"}],
                },
            )


            def load_details_page(context, page_id, params=None):
                del context, page_id, params
                return {"title": "详情"}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard"), make_page_info("details")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    calls: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
            module_info=module_info,
            open_page_callback=lambda page_id, params=None: calls.append((page_id, params)),
        )
        qtbot.addWidget(page)

        page._data_table_widgets["accounts"].cellClicked.emit(1, 0)
        assert calls == [("details", {"account_id": "acct-002"})]
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_row_action_without_params_does_not_forward_row_payload(qtbot, tmp_path):
    module_name = "hosted_page_no_row_params_module"
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
                    "load_handler": "load_dashboard_page",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "title": "账号总览",
                            "data_source": {"type": "binding", "binding": "rows"},
                            "columns": [
                                {"key": "account_id", "label": "账号"},
                                {"key": "status", "label": "状态"},
                            ],
                            "row_action": {
                                "type": "open_page",
                                "page_id": "details",
                            },
                        },
                    ],
                },
            )


            def load_dashboard_page(context, page_id, params=None):
                del context, page_id, params
                return {
                    "rows": [
                        {"account_id": "acct-001", "status": "active"},
                        {"account_id": "acct-002", "status": "blocked"},
                    ],
                }
            """,
            "pages/details.py": """
            from crawler4j_contracts import PageSpec

            PAGE = PageSpec(
                id="details",
                label="Details",
                schema={
                    "type": "Page",
                    "load_handler": "load_details_page",
                    "children": [{"type": "Text", "binding": "title"}],
                },
            )


            def load_details_page(context, page_id, params=None):
                del context, page_id, params
                return {"title": "详情"}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard"), make_page_info("details")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    calls: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
            module_info=module_info,
            open_page_callback=lambda page_id, params=None: calls.append((page_id, params)),
        )
        qtbot.addWidget(page)

        page._data_table_widgets["accounts"].cellClicked.emit(1, 0)
        assert calls == [("details", None)]
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_supports_navigation_params_and_button_actions(qtbot, tmp_path):
    module_name = "hosted_page_navigation_module"
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
                    "load_handler": "load_dashboard_page",
                    "children": [
                        {"type": "Text", "style": "body", "binding": "selected_phone"},
                        {
                            "type": "Button",
                            "label": "打开详情页",
                            "action": {
                                "type": "open_page",
                                "page_id": "account_details",
                                "params": {
                                    "phone": {"binding": "selected.phone"},
                                    "source": {"value": "dashboard"},
                                },
                            },
                        },
                    ],
                },
            )


            def load_dashboard_page(context, page_id, params=None):
                del context, page_id
                selected_phone = "none"
                params_state = "none" if params is None else "dict"
                if isinstance(params, dict):
                    selected_phone = str(params.get("phone") or "none")
                return {
                    "selected_phone": f"params:{params_state}|selected:{selected_phone}",
                    "selected": {"phone": selected_phone},
                }
            """,
            "pages/account_details.py": """
            from crawler4j_contracts import PageSpec

            PAGE = PageSpec(
                id="account_details",
                label="Account Details",
                schema={
                    "type": "Page",
                    "load_handler": "load_account_details_page",
                    "children": [{"type": "Text", "binding": "title"}],
                },
            )


            def load_account_details_page(context, page_id, params=None):
                del context, page_id, params
                return {"title": "详情页"}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard"), make_page_info("account_details")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    opened_pages: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
            module_info=module_info,
            open_page_callback=lambda page_id, params=None: opened_pages.append((page_id, params)),
            initial_params={"phone": "13800138000"},
        )
        qtbot.addWidget(page)

        assert any(
            label.text() == "params:dict|selected:13800138000"
            for label in page.findChildren(QLabel)
        )

        open_button = next(button for button in page.findChildren(QPushButton) if button.text() == "打开详情页")
        open_button.click()

        assert opened_pages == [("account_details", {"phone": "13800138000", "source": "dashboard"})]
    finally:
        restore_module(service, original_registry, module_name)
