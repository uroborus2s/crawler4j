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


def _write_hosted_page_module(base_dir: Path, module_name: str) -> Path:
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
    (module_dir / "module_runtime.py").write_text(
        dedent(
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
                                "label": "打开账号管理",
                                "action": {"type": "open_page", "entry": "core:data_table:accounts"},
                            },
                            {
                                "type": "DataTable",
                                "title": "统计明细",
                                "binding": "rows",
                                "columns": [
                                    {"key": "metric", "label": "指标"},
                                    {"key": "value", "label": "值"},
                                ],
                            },
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
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return module_dir


def test_managed_page_renderer_declares_schema_loads_data_and_handles_actions(qtbot, tmp_path):
    module_name = "hosted_page_module"
    module_dir = _write_hosted_page_module(tmp_path, module_name)
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
    opened_entries: list[str] = []

    try:
        page = ManagedPageRenderer(module_name, "dashboard", open_entry_callback=opened_entries.append)
        qtbot.addWidget(page)

        assert any(label.text() == "今日运营看板" for label in page.findChildren(QLabel))
        assert any(label.text() == "第 1 次加载" for label in page.findChildren(QLabel))
        assert page._data_table_widgets
        first_table = next(iter(page._data_table_widgets.values()))
        assert first_table.item(0, 0).text() == "活跃账号"
        assert first_table.item(0, 1).text() == "11"

        reload_button = next(
            button
            for button in page.findChildren(QPushButton)
            if button.text() == "刷新"
        )
        reload_button.click()

        qtbot.waitUntil(lambda: any(label.text() == "第 2 次加载" for label in page.findChildren(QLabel)))

        open_button = next(
            button
            for button in page.findChildren(QPushButton)
            if button.text() == "打开账号管理"
        )
        open_button.click()

        assert opened_entries == ["core:data_table:accounts"]
    finally:
        service.registry = original_registry
        purge_module_namespace(module_name)


def test_managed_page_renderer_refresh_clears_removed_stale_ui_schema(qtbot, tmp_path):
    from src.core.persistence import get_module_data_store

    module_name = "hosted_page_module"
    module_dir = tmp_path / module_name
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
    (module_dir / "module_runtime.py").write_text(
        dedent(
            """
            from crawler4j_sdk import TaskContext


            def declare_ui(context: TaskContext):
                return None
            """
        ).strip()
        + "\n",
        encoding="utf-8",
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
    store.write_data_table_schema(
        module_name,
        "accounts",
        {
            "title": "旧账号表",
            "dataset": "accounts",
            "columns": [{"key": "phone", "label": "手机号"}],
        },
    )

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

    try:
        page = ManagedPageRenderer(module_name, "dashboard")
        qtbot.addWidget(page)

        assert page._status_label.text() == "未声明页面 schema: dashboard"
        assert store.read_page_schema(module_name, "dashboard") == {}
        assert store.read_data_table_schema(module_name, "accounts") == {}
    finally:
        service.registry = original_registry
        purge_module_namespace(module_name)
