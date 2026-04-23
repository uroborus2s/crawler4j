from contextlib import ExitStack
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QLabel, QPushButton

from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource
from src.core.mms.module_loader import purge_module_namespace
from src.core.mms.service import get_module_service
from src.core.mms.ui.managed_page_renderer import ManagedPageRenderer


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


def test_managed_page_renderer_declares_schema_loads_data_and_handles_actions(qtbot, tmp_path):
    module_name = "hosted_page_module"
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
                    "load_handler": "load_dashboard_page",
                    "children": [
                        {"type": "Text", "style": "title", "binding": "title"},
                        {"type": "Text", "style": "body", "binding": "load_count_text"},
                        {"type": "Button", "label": "刷新", "action": {"type": "reload"}},
                        {
                            "type": "Button",
                            "label": "打开账号页",
                            "action": {"type": "open_page", "page_id": "accounts"},
                        },
                        {
                            "type": "DataTable",
                            "table_id": "metrics",
                            "title": "统计明细",
                            "data_source": {"type": "binding", "binding": "rows"},
                            "columns": [
                                {"key": "metric", "label": "指标"},
                                {"key": "value", "label": "值"},
                            ],
                        },
                    ],
                },
            )
            context.tools.call(
                "ui.declare_page",
                page_id="accounts",
                schema={
                    "type": "Page",
                    "load_handler": "load_accounts_page",
                    "children": [
                        {"type": "Text", "style": "title", "binding": "title"},
                    ],
                },
            )


        def load_dashboard_page(context: TaskContext, page_id: str, params=None):
            count = int(context.tools.call("db.get_state", key="dashboard_load_count") or 0) + 1
            context.tools.call("db.set_state", key="dashboard_load_count", value=count)
            return {
                "title": "今日运营看板",
                "load_count_text": f"第 {count} 次加载",
                "rows": [{"metric": "活跃账号", "value": str(10 + count)}],
            }


        def load_accounts_page(context: TaskContext, page_id: str, params=None):
            del context, page_id, params
            return {"title": "账号页"}
        """,
    )
    service, original_registry = _register_dev_link_module(module_name, module_dir)
    opened_pages: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
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
        service.registry = original_registry
        purge_module_namespace(module_name)


def test_managed_page_renderer_row_action_opens_page_with_row_params(qtbot, tmp_path):
    module_name = "hosted_page_row_action_module"
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
            context.tools.call(
                "ui.declare_page",
                page_id="details",
                schema={
                    "type": "Page",
                    "load_handler": "load_details_page",
                    "children": [{"type": "Text", "binding": "title"}],
                },
            )


        def load_dashboard_page(context: TaskContext, page_id: str, params=None):
            del context, page_id, params
            return {
                "rows": [
                    {"account_id": "acct-001", "status": "active"},
                    {"account_id": "acct-002", "status": "blocked"},
                ],
            }


        def load_details_page(context: TaskContext, page_id: str, params=None):
            del context, page_id, params
            return {"title": "详情"}
        """,
    )
    service, original_registry = _register_dev_link_module(module_name, module_dir)
    calls: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
            open_page_callback=lambda page_id, params=None: calls.append((page_id, params)),
        )
        qtbot.addWidget(page)

        page._data_table_widgets["accounts"].cellClicked.emit(1, 0)
        assert calls == [("details", {"account_id": "acct-002"})]
    finally:
        service.registry = original_registry
        purge_module_namespace(module_name)


def test_managed_page_renderer_row_action_without_params_does_not_forward_row_payload(qtbot, tmp_path):
    module_name = "hosted_page_no_row_params_module"
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
            context.tools.call(
                "ui.declare_page",
                page_id="details",
                schema={
                    "type": "Page",
                    "load_handler": "load_details_page",
                    "children": [{"type": "Text", "binding": "title"}],
                },
            )


        def load_dashboard_page(context: TaskContext, page_id: str, params=None):
            del context, page_id, params
            return {
                "rows": [
                    {"account_id": "acct-001", "status": "active"},
                    {"account_id": "acct-002", "status": "blocked"},
                ],
            }


        def load_details_page(context: TaskContext, page_id: str, params=None):
            del context, page_id, params
            return {"title": "详情"}
        """,
    )
    service, original_registry = _register_dev_link_module(module_name, module_dir)
    calls: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
            open_page_callback=lambda page_id, params=None: calls.append((page_id, params)),
        )
        qtbot.addWidget(page)

        page._data_table_widgets["accounts"].cellClicked.emit(1, 0)
        assert calls == [("details", None)]
    finally:
        service.registry = original_registry
        purge_module_namespace(module_name)


def test_managed_page_renderer_refresh_clears_removed_stale_ui_schema(qtbot, tmp_path):
    from src.core.persistence import get_module_data_store

    module_name = "stale_hosted_page_module"
    module_dir = _write_runtime_module(
        tmp_path,
        module_name,
        """
        from crawler4j_sdk import TaskContext


        def declare_ui(context: TaskContext):
            return None
        """,
    )
    store = get_module_data_store()
    store.write_page_schema(
        module_name,
        "dashboard",
        {
            "type": "Page",
            "title": "旧看板",
            "load_handler": "load_dashboard_page",
            "children": [{"type": "Text", "text": "stale"}],
        },
    )
    store.write_page_schema(
        module_name,
        "accounts",
        {
            "type": "Page",
            "title": "旧账号页",
            "load_handler": "load_accounts_page",
            "children": [{"type": "Text", "text": "legacy"}],
        },
    )
    service, original_registry = _register_dev_link_module(module_name, module_dir)

    try:
        page = ManagedPageRenderer(module_name, "dashboard")
        qtbot.addWidget(page)

        assert page._status_label.text() == "未声明页面 schema: dashboard"
        assert store.read_page_schema(module_name, "dashboard") == {}
        assert store.read_page_schema(module_name, "accounts") == {}
    finally:
        service.registry = original_registry
        purge_module_namespace(module_name)


def test_managed_page_renderer_supports_navigation_params_and_row_actions(qtbot, tmp_path):
    module_name = "hosted_page_navigation_module"
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
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "title": "账号列表",
                            "data_source": {"type": "binding", "binding": "rows"},
                            "columns": [
                                {"key": "phone", "label": "手机号"},
                                {"key": "status", "label": "状态"},
                            ],
                            "row_action": {
                                "type": "open_page",
                                "page_id": "account_details",
                                "params": {
                                    "phone": {"binding": "phone"},
                                    "status": {"binding": "status"},
                                },
                            },
                        },
                    ],
                },
            )
            context.tools.call(
                "ui.declare_page",
                page_id="account_details",
                schema={
                    "type": "Page",
                    "load_handler": "load_account_details_page",
                    "children": [{"type": "Text", "binding": "title"}],
                },
            )


        def load_dashboard_page(context: TaskContext, page_id: str, params=None):
            selected_phone = "none"
            params_state = "none" if params is None else "dict"
            if isinstance(params, dict):
                selected_phone = str(params.get("phone") or "none")
            return {
                "selected_phone": f"params:{params_state}|selected:{selected_phone}",
                "selected": {"phone": selected_phone},
                "rows": [
                    {"phone": "13800138000", "status": "active"},
                    {"phone": "13900139000", "status": "blocked"},
                ],
            }


        def load_account_details_page(context: TaskContext, page_id: str, params=None):
            del context, page_id, params
            return {"title": "详情页"}
        """,
    )
    service, original_registry = _register_dev_link_module(module_name, module_dir)
    opened_pages: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
            open_page_callback=lambda page_id, params=None: opened_pages.append((page_id, params)),
        )
        qtbot.addWidget(page)

        assert any(label.text() == "params:none|selected:none" for label in page.findChildren(QLabel))

        page.set_navigation_params({"phone": "13800138000"})
        qtbot.waitUntil(
            lambda: any(
                label.text() == "params:dict|selected:13800138000"
                for label in page.findChildren(QLabel)
            )
        )

        button = next(button for button in page.findChildren(QPushButton) if button.text() == "打开详情页")
        button.click()

        page._data_table_widgets["accounts"].cellClicked.emit(1, 0)
        assert opened_pages == [
            ("account_details", {"phone": "13800138000", "source": "dashboard"}),
            ("account_details", {"phone": "13900139000", "status": "blocked"}),
        ]
    finally:
        service.registry = original_registry
        purge_module_namespace(module_name)
